# -*- coding: utf-8 -*-
"""
Created on Tue Jun 28 09:07:00 2022

@author: ling
"""

import datetime
import pandas as pd
import glob

# Chrome
try:
    CHROME_DRIVER_PATH = glob.glob('chromedriver*.exe')[0]
except:
    raise Exception ("Chromedriver not found!")

HEADLESS = True

# DB
DB_NAME = 'ccass.db'
CCASS_TABLE_NAME = 'CCASS'
STOCK_MAP_TABLE_NAME = 'StockMap'


# Scraping Config
# URL
STOCK_CODE_LIST_URL = "https://www3.hkexnews.hk/sdw/search/ccass_stock_list.htm?sortby=stockcode&shareholdingdate="
MAIN_URL = "https://www.hkexnews.hk/sdw/search/searchsdw.aspx"

# Data
SHAREHOLDING_THRESHOLD_TO_SCRAPE = 0.1
NUMBER_OF_STOCKS_SCRAPED = 2000
DATE_RANGE_LIST = pd.bdate_range(
    start=datetime.date.today() - datetime.timedelta(days=365),
    end=datetime.date.today() - datetime.timedelta(days=1)
).to_list()

# Server config
HOST = '0.0.0.0'
PORT = 8000

# UI Config
TREND_TAB_DATA_COLUMNS = ['DataDate', 'ParticipantID', 'ParticipantName', 'FracOfShares']
CHANGES_DATA_COLUMNS = ['ParticipantID', 'ParticipantName', 'ChangeInPercentShares']