# -*- coding: utf-8 -*-
"""
Created on Mon Jun 27 21:32:39 2022

@author: ling
"""

import pandas as pd
import numpy as np
import datetime

from concurrent.futures import ThreadPoolExecutor
import threading

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.command import Command

from bs4 import BeautifulSoup

from config import HEADLESS, CHROME_DRIVER_PATH
from config import CCASS_TABLE_NAME, STOCK_MAP_TABLE_NAME
from config import STOCK_CODE_LIST_URL, MAIN_URL
from config import DATE_RANGE_LIST, SHAREHOLDING_THRESHOLD_TO_SCRAPE, NUMBER_OF_STOCKS_SCRAPED

from util import get_db_connection

db_lock = threading.Lock()


def acquire_lock(func):
    def inner_func(*args, **kwargs):
        with db_lock:
            func(*args, **kwargs)
    return inner_func

class CCASSScraper:
    
    def __init__(self, threadIdx : int = 0):
        self.threadIdx = threadIdx
        self.scraped_CCASS_date_stockCode = set()
        self.scraped_stock_map = pd.DataFrame()
        self.driver = None
        
    
    def __enter__(self):
        self.conn = get_db_connection()
        if self.threadIdx == 0:
            self.create_table()
        self.initialize_chrome_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
        if self.conn:
            self.conn.close()
        
    @acquire_lock
    def create_table(self):
        self.cursor = self.conn.cursor()
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS 
            {CCASS_TABLE_NAME}
            (DataDate, StockCode, ParticipantID, ParticipantName, ParticipantAddress, Shareholding, FracOfShares)
        """)
        self.cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS 
            {STOCK_MAP_TABLE_NAME}
            (DataDate, StockCode, StockName)
        """)
        self.conn.commit()
        self.cursor.close()
    
    def initialize_chrome_driver(self):
        if HEADLESS:
            options = Options()
            options.add_argument('--headless')
        else:
            options = None
        
        if not self.driver:
            self.driver = webdriver.Chrome(CHROME_DRIVER_PATH, options=options)
    
    def get_stock_code_list(self, date: datetime.date)-> pd.DataFrame:
        if not self.check_if_stock_map_scraped(date):
            self.scraped_stock_map = self.scrape_stock_code_list(date)
            print(f"Loading {len(self.scraped_stock_map)} rows into {STOCK_MAP_TABLE_NAME}")
            self.store_df_to_db(self.scraped_stock_map, STOCK_MAP_TABLE_NAME)
        return self.scraped_stock_map
    
    def scrape_stock_code_list(self, date: datetime.date) -> pd.DataFrame:
        print(f"{self.threadIdx}: Scraping stock code list")
        url = (
            STOCK_CODE_LIST_URL + date.strftime('%Y%m%d')
        )
        self.driver.get(url)
        
        table = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((
                By.TAG_NAME,
                'table'
            ))
        )
        
        soup = BeautifulSoup(self.driver.page_source, 'lxml')
        
        table = soup.find('table')
        table_columns = [
            'StockCode', 'StockName'    
        ]
        # Skipping header row (hence index starts from 1)
        table_rows = table.find_all('tr')[1:NUMBER_OF_STOCKS_SCRAPED+2]
        table_rows_data = []
        for table_row in table_rows:
            table_rows_data.append([td.get_text(strip=True) for td in table_row.find_all('td')])
        df = pd.DataFrame(data=table_rows_data, columns=table_columns).dropna()
        df['DataDate'] = date.strftime('%Y-%m-%d')
        df = df[['DataDate', *table_columns]]
        return df
    
    @acquire_lock
    def load_existing_date_stockCode(self, date_str: str):
        self.scraped_CCASS_date_stockCode = set(
            pd.read_sql_query(f'Select Distinct StockCode from {CCASS_TABLE_NAME} where DataDate = "{date_str}"', self.conn)
            .set_index('StockCode').index.tolist()
        )
    
    @acquire_lock
    def load_existing_stock_map_by_date(self, date_str: str):
        self.scraped_stock_map = (
            pd.read_sql_query(
                f'Select StockCode, StockName from {STOCK_MAP_TABLE_NAME} where DataDate = "{date_str}"',
                self.conn
            )
        )
        
    def check_if_CCASS_scraped(self, date: datetime.date, stock_code: str) -> bool:
        if not self.scraped_CCASS_date_stockCode:
            self.load_existing_date_stockCode(date.strftime('%Y-%m-%d'))
        return stock_code in self.scraped_CCASS_date_stockCode
    
    def check_if_stock_map_scraped(self, date: datetime.date) -> bool:
        if self.scraped_stock_map.empty:
            self.load_existing_stock_map_by_date(date.strftime('%Y-%m-%d'))
        return (not self.scraped_stock_map.empty)
    
    def select_date_in_browser(self, date: datetime.date):
        date_picker = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'txtShareholdingDate'))
        )
        date_picker.click()
        year, month, day = date.year, date.month, date.day
        self.driver.find_element_by_xpath(f'//*[@id="date-picker"]//b[@class="year"]//button[@data-value={year}]').click()
        self.driver.find_element_by_xpath(f'//*[@id="date-picker"]//b[@class="month"]//button[@data-value={month-1}]').click()
        self.driver.find_element_by_xpath(f'//*[@id="date-picker"]//b[@class="day"]//button[@data-value={day}]').click()
        date_picker.click()
        
    def input_stock_code(self, stock_code: str):
        stock_code_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'txtStockCode'))
        )
        # Seems in-browser JS is more stable than sendkeys under multi-thread
        self.driver.execute_script(
            f"document.getElementById('txtStockCode').value = '{stock_code}'"
        )
    
    def click_search_btn(self):
        search_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, 'btnSearch'))
        )
        search_button.click()
        

    def parse_shareholding_table(self, date: datetime.date, stock_code: str) -> pd.DataFrame:
        soup = BeautifulSoup(self.driver.page_source, 'lxml')
        
        table = soup.find(attrs={'class':'search-details-table-container table-mobile-list-container'})
        table_columns = [
            'ParticipantID', 'ParticipantName', 'ParticipantAddress', 'Shareholding', 'FracOfShares'    
        ]
        if not table:
            # print("Skipping as table not found")
            return pd.DataFrame()
        table_rows = table.find_all('tr')[1:]
        table_rows_data = []
        for table_row in table_rows:
            table_rows_data.append([td.get_text(strip=True) for td in table_row.find_all('div', attrs={'class': 'mobile-list-body'})])
        df = pd.DataFrame(data=table_rows_data, columns=table_columns[:len(table_rows_data[0])])
        df['ParticipantID'] = np.where(df['ParticipantID']=='', 'None', df['ParticipantID'])
        df['Shareholding'] = pd.to_numeric(df['Shareholding'].str.replace(',', ''))
        if 'FracOfShares' in df.columns:
            df['FracOfShares'] = pd.to_numeric(df['FracOfShares'].str.replace('%', ''))
        else:
            df['FracOfShares'] = df['Shareholding'] / df['Shareholding'].sum() * 100
        # Only store those with % of shares > 0.1%
        df = df[df['FracOfShares'] > SHAREHOLDING_THRESHOLD_TO_SCRAPE]
        df['StockCode'] = stock_code
        df['DataDate'] = date.strftime('%Y-%m-%d')
        df = df[['DataDate', 'StockCode', *table_columns]]
        return df
    
    @acquire_lock
    def store_df_to_db(self, df_new_data: pd.DataFrame, table_name: str):
        try:
            df_new_data.to_sql(table_name, self.conn, if_exists='append', index=False)
        except:
            print('write error')
        
    def scrape_one_page(self, date: datetime.date, stock_code: str) -> bool:
        if self.check_if_CCASS_scraped(date, stock_code):
            # print("Already scraped, skipping")
            return False
        
        self.input_stock_code(stock_code)
        
        self.click_search_btn()
        
        parsed_df = self.parse_shareholding_table(date, stock_code)
        if parsed_df.empty:
            return False
        
        if self.scraped_df.empty:
            self.scraped_df = parsed_df
        else:
            self.scraped_df = pd.concat([
                self.scraped_df, parsed_df
            ])
        return True
    
    def scrape_for_one_day(self, date: datetime.date):
        df_stock_list = self.get_stock_code_list(date)
        
        self.driver.get(MAIN_URL)
        self.select_date_in_browser(date)
        
        self.scraped_df = pd.DataFrame()
        run_count = 0
        has_data_count = 0 # Not every stock has table to be scraped
        buffer_size = 50
        for stock_code in df_stock_list['StockCode'].values.tolist():
            has_data = self.scrape_one_page(date, stock_code)
            if run_count % 100 == 0:
                print(f"{self.threadIdx}: Scraped for {date.strftime('%Y-%m-%d')}, {stock_code}, ({has_data_count}, {run_count}) out of {len(df_stock_list)}")
            run_count += 1
            has_data_count += has_data * 1
            if has_data_count % buffer_size == (buffer_size-1):
                print(f"{self.threadIdx}: Loading {len(self.scraped_df)} rows into db")
                self.store_df_to_db(self.scraped_df, CCASS_TABLE_NAME)
                self.scraped_df = pd.DataFrame()
                
        if not self.scraped_df.empty:
            print(f"{self.threadIdx}: Loading {len(self.scraped_df)} rows into db")
            self.store_df_to_db(self.scraped_df, CCASS_TABLE_NAME)
        
        print(f"Finished scraping for {date.strftime('%Y-%m-%d')}")
        

# Func to be executed by thread
def scrape_task(threadId: int, date: datetime.date,):
    print(threadId, date)
    
    with CCASSScraper(threadId) as scraper:
        scraper.scrape_for_one_day(date)


def main():
    scrape_task(0, DATE_RANGE_LIST[::-1][0])
    
    # executor = ThreadPoolExecutor(max_workers=12)
    # jobs = [executor.submit(scrape_task, i, DATE_RANGE_LIST[::-1][i]) for i in range(0, len(DATE_RANGE_LIST))]
    
        
if __name__ == '__main__':
    main()