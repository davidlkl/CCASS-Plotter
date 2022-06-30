# -*- coding: utf-8 -*-
"""
Created on Wed Jun 29 00:27:30 2022

@author: ling
"""

import pandas as pd
import datetime
import os
import sqlite3
from dotenv import load_dotenv

from config import DB_NAME, CCASS_TABLE_NAME, STOCK_MAP_TABLE_NAME, TREND_TAB_DATA_COLUMNS

# DEV / PROD
def load_base_env() -> str:
    load_dotenv()    
    return os.getenv("BASE_ENV")

def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def create_index_if_not_exist(conn):
    cursor = conn.cursor()
    cursor.execute(f"""
      CREATE INDEX if not exists index_stock_code on {CCASS_TABLE_NAME}(StockCode)
    """)
    cursor.execute(f"""
      CREATE INDEX if not exists index_date on {CCASS_TABLE_NAME}(DataDate)
    """)
    cursor.execute(f"""
      CREATE INDEX if not exists index_stock_code_date on {CCASS_TABLE_NAME}(StockCode, DataDate)
    """)
    cursor.execute(f"""
      CREATE INDEX if not exists index_stock_map_date on {STOCK_MAP_TABLE_NAME}(DataDate)
    """)
    cursor.execute(f"""
      CREATE INDEX if not exists index_stock_map_code on {STOCK_MAP_TABLE_NAME}(StockCode)
    """)
    cursor.execute(f"""
      CREATE INDEX if not exists index_stock_map_code_date on {STOCK_MAP_TABLE_NAME}(DataDate, StockCode)
    """)
    cursor.close()

def get_init_params(conn):
    stock_map_list = pd.read_sql_query(f"""
        select * from (
        	select distinct stockCode, stockName from {STOCK_MAP_TABLE_NAME}
        )
        where stockCode in (select DISTINCT StockCode from {CCASS_TABLE_NAME})
        order by StockCode
    """, conn).to_dict('records')
    
    
    min_date_str, max_date_str = tuple(
        pd.read_sql_query(f"""
            Select min(DataDate), max(DataDate) from {CCASS_TABLE_NAME}
        """, conn)
        .iloc[0].values.tolist()
    )
    min_date = datetime.datetime.strptime(min_date_str, '%Y-%m-%d').date()
    max_date = datetime.datetime.strptime(max_date_str, '%Y-%m-%d').date()
    
    return stock_map_list, min_date, max_date

def get_shareholding_delta_for_transaction_finder(stock_code: str, start_date_str: str,
    end_date_str: str, conn):
    
    query = f"""
        with 
    	end_date_shareholding as (
    		select datadate, ParticipantID, ParticipantName, FracOfShares from {CCASS_TABLE_NAME}
    		WHERE StockCode = "{stock_code}"
    		and DataDate = "{end_date_str}"
    	), 
    	start_date_shareholding as (
    		select datadate, ParticipantID, ParticipantName, FracOfShares from {CCASS_TABLE_NAME}
    		WHERE StockCode = "{stock_code}"
    		and DataDate = "{start_date_str}"
    	),
    	joint_shareholding as (
    		select 
    			a.ParticipantID,
                a.ParticipantName,
    			ifnull(b.DataDate, "{start_date_str}")  as startDataDate,
    			ifnull(b.FracOfShares, 0) as startFracOfShare,
    			a.DataDate as endDataDate,
    			a.FracOfShares as endFracOfShare
    		from end_date_shareholding a 
    		left outer join start_date_shareholding b
    		on a.ParticipantID = b.ParticipantID
    		UNION
    		select 
    			a.ParticipantID,
                a.ParticipantName,
    			a.DataDate as startDataDate,
    			a.FracOfShares as startFracOfShare,
    			ifnull(b.DataDate, "{end_date_str}") as endDataDate,
    			ifnull(b.FracOfShares,0) as endFracOfShare
    		from start_date_shareholding a 
    		left outer join end_date_shareholding b
    		on a.ParticipantID = b.ParticipantID
    	),
    	final_table as (
    		select
    			joint_shareholding.*,
    			round((endFracOfShare - startFracOfShare), 2) as ChangeInPercentShares
    		from joint_shareholding
    	)

        select * from final_table
        order by ChangeInPercentShares desc
    """
    
    return pd.read_sql_query(query, conn)

def get_shareholding_time_series_for_top_participants(stock_code: str, start_date_str: str,
    end_date_str: str, conn):
    
    query = f"""
        with top10Participant as (
        	select ParticipantID from (
        		select ParticipantID, rank() over (order by Shareholding DESC) as rk from (
        			select ParticipantID, Shareholding from {CCASS_TABLE_NAME}
        			where
        				stockcode = "{stock_code}" and 
        				datadate = (select max(datadate) from {CCASS_TABLE_NAME} where StockCode = "{stock_code}")
        		)
        	) WHERE rk <= 10
        )
        Select {','.join(TREND_TAB_DATA_COLUMNS)} from {CCASS_TABLE_NAME}
        where 
            StockCode = "{stock_code}" and
            DataDate between "{start_date_str}" and "{end_date_str}" and
            ParticipantID in top10Participant
        order by 
            DataDate, FracOfShares desc
    """
    
    return pd.read_sql_query(query, conn)