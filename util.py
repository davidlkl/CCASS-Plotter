# -*- coding: utf-8 -*-
"""
Created on Wed Jun 29 00:27:30 2022

@author: ling
"""

import pandas as pd
import datetime
import os
import sqlite3
import psycopg2


from config import (
    BASE_ENV, DB_TYPE, SQLITE_DB_NAME, QUEST_DB_CONN_STR,
    CCASS_TABLE_NAME, STOCK_MAP_TABLE_NAME, TREND_TAB_DATA_COLUMNS
)

def get_db_connection():
    if DB_TYPE == 'SQLITE':
        return sqlite3.connect(DB_NAME, check_same_thread=False)
    else:
        return psycopg2.connect(QUEST_DB_CONN_STR, connect_timeout=0)

def create_table(connection):
    cursor = connection.cursor()
    if isinstance(connection, sqlite3.Connection):
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS 
            {CCASS_TABLE_NAME}
            (DataDate, StockCode, ParticipantID, ParticipantName, ParticipantAddress, Shareholding, FracOfShares)
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS 
            {STOCK_MAP_TABLE_NAME}
            (DataDate, StockCode, StockName)
        """)
    elif isinstance(connection, psycopg2.extensions.connection):
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS 
            {CCASS_TABLE_NAME}(
              DataDate date,
              StockCode symbol CAPACITY 4096 index,
              ParticipantID symbol CAPACITY 2048,
              ParticipantName string,
              ParticipantAddress string,
              Shareholding long,
              FracOfShares double
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS 
            {STOCK_MAP_TABLE_NAME}(
              DataDate date,
              StockCode symbol CAPACITY 4096,
              StockName string
            )
        """)
    connection.commit()
    cursor.close()

def store_df_to_quest_db(df, connection, table_name):
    cursor = connection.cursor()
    df = df.apply(
        lambda s:
            pd.to_datetime(s).dt.date
            if 'date' in s.name.lower() else s,
        axis=0
    )
    # insert records by prepared statements
    for idx, row in df.iterrows():
      cursor.execute(f"""
        INSERT INTO {table_name}
        VALUES ({','.join(['%s']*len(row))});
        """, 
        tuple(row.values.tolist())
      )
    # commit records (bulk insert)
    connection.commit()
    cursor.close()    
    
def store_df_to_sqlite(df: pd.DataFrame, connection: sqlite3.Connection, table_name: str):
    df_new_data.to_sql(table_name, connection, if_exists='append', index=False)
    
def store_df_to_db(df: pd.DataFrame, connection: sqlite3.Connection, table_name: str):
    if isinstance(connection, sqlite3.Connection):
        store_df_to_sqlite(df, connection, table_name)
    elif isinstance(connection, psycopg2.extensions.connection):
        store_df_to_quest_db(df, connection, table_name)

def create_index_if_not_exist(conn):
    if DB_TYPE != 'SQLITE':
        return
    # SQLITE only
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
    if isinstance(conn, sqlite3.Connection):
        df_stock_map = pd.read_sql_query(f"""
            select * from (
            	select distinct stockCode, stockName from {STOCK_MAP_TABLE_NAME}
            )
            where stockCode in (select DISTINCT StockCode from {CCASS_TABLE_NAME})
            order by StockCode
        """, conn)
        df_stock_map['stockName'] = df_stock_map['stockName'].str.replace("'", '')
        df_stock_map = df_stock_map.drop_duplicates(subset=['stockCode', 'stockName'])
        stock_map_list = df_stock_map.to_dict('records')
        min_date_str, max_date_str = tuple(
            pd.read_sql_query(f"""
                Select min(DataDate), max(DataDate) from {CCASS_TABLE_NAME}
            """, conn)
            .iloc[0].values.tolist()
        )
    elif isinstance(conn, psycopg2.extensions.connection):
        df_stock_map = pd.read_sql_query(f"""
            with d1 as (select DISTINCT StockCode from {CCASS_TABLE_NAME})
            select distinct {STOCK_MAP_TABLE_NAME}.stockCode, stockName from {STOCK_MAP_TABLE_NAME}
            inner join d1
            on {STOCK_MAP_TABLE_NAME}.stockCode = d1.stockCode
            order by stockCode
        """, conn)
        df_stock_map['stockName'] = df_stock_map['stockName'].str.replace("'", '')
        df_stock_map = df_stock_map.drop_duplicates(subset=['stockCode', 'stockName'])
        stock_map_list = df_stock_map.to_dict('records')
        min_date_str, max_date_str = tuple(
            pd.read_sql_query(f"""
                Select 
                    to_str(min(DataDate), 'yyyy-MM-dd'),
                    to_str(max(DataDate), 'yyyy-MM-dd')
                from {CCASS_TABLE_NAME}
            """, conn)
            .iloc[0].values.tolist()
        )
    
    
    min_date = datetime.datetime.strptime(min_date_str, '%Y-%m-%d').date()
    max_date = datetime.datetime.strptime(max_date_str, '%Y-%m-%d').date()
    
    return stock_map_list, min_date, max_date

def get_shareholding_delta_for_transaction_finder(stock_code: str, start_date_str: str,
    end_date_str: str, conn):
    if isinstance(conn, sqlite3.Connection):
        query = f"""
            with 
        	end_date_shareholding as (
        		select datadate, ParticipantID, ParticipantName, FracOfShares from {CCASS_TABLE_NAME}
        		WHERE StockCode = "{stock_code}"
        		and DataDate = (select max(DataDate) from {STOCK_MAP_TABLE_NAME} where DataDate <= "{end_date_str}")
        	), 
        	start_date_shareholding as (
        		select datadate, ParticipantID, ParticipantName, FracOfShares from {CCASS_TABLE_NAME}
        		WHERE StockCode = "{stock_code}"
        		and DataDate = (select max(DataDate) from {STOCK_MAP_TABLE_NAME} where DataDate <= "{start_date_str}")
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
    elif isinstance(conn, psycopg2.extensions.connection):
        query = f"""
            with dataDateRange as (
              select min(datadate) as MinDataDate, max(datadate) as MaxDataDate from {STOCK_MAP_TABLE_NAME}
              where stockCode = '{stock_code}'
              and datadate between '{start_date_str}' and '{end_date_str}'
            ), dataInDateRange as (
              select datadate, ParticipantID, ParticipantName, FracOfShares from {CCASS_TABLE_NAME}
              WHERE StockCode = '{stock_code}'
              and datadate between '{start_date_str}' and '{end_date_str}'
            ),
            end_date_shareholding as (
              select dataInDateRange.* from
              dataInDateRange inner join dataDateRange
              on dataInDateRange.DataDate = dataDateRange.MaxDataDate
            ),
            start_date_shareholding as (
              select dataInDateRange.* from
              dataInDateRange inner join dataDateRange
              on dataInDateRange.DataDate = dataDateRange.MinDataDate
            ),
        	joint_shareholding as (
        		select 
        			a.ParticipantID,
                    a.ParticipantName,
        			coalesce(b.FracOfShares, 0) as startFracOfShare,
        			a.FracOfShares as endFracOfShare
        		from end_date_shareholding a 
        		left outer join start_date_shareholding b
        		on a.ParticipantID = b.ParticipantID
        		UNION
        		select 
        			a.ParticipantID,
                    a.ParticipantName,
        			a.FracOfShares as startFracOfShare,
        			coalesce(b.FracOfShares, 0) as endFracOfShare
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
    if isinstance(conn, sqlite3.Connection):
        query = f"""
            with top10Participant as (
            	select ParticipantID from (
            		select ParticipantID, rank() over (order by Shareholding DESC) as rk from (
            			select ParticipantID, Shareholding from {CCASS_TABLE_NAME}
            			where
            				stockcode = "{stock_code}" and 
            				datadate = (select max(DataDate) from {STOCK_MAP_TABLE_NAME} where DataDate <= "{end_date_str}")
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
    elif isinstance(conn, psycopg2.extensions.connection):
        query = f"""
            with maxDataDate as (
              select max(datadate) as DataDate from {CCASS_TABLE_NAME} 
              where stockCode = '{stock_code}'
              and datadate <= '{end_date_str}'
            ),
            top10Participant as (
              select {CCASS_TABLE_NAME}.* from {CCASS_TABLE_NAME}
              inner join maxDataDate
              on {CCASS_TABLE_NAME}.DataDate = maxDataDate.DataDate
              where
                stockcode = '{stock_code}' 
              order by Shareholding desc
              limit 10
            )
            select a.* from (
              select {','.join(TREND_TAB_DATA_COLUMNS)} from {CCASS_TABLE_NAME} 
              where
              stockCode = '{stock_code}' AND
              datadate BETWEEN '{start_date_str}' and '{end_date_str}'
            ) a inner JOIN top10Participant
            on a.ParticipantID = top10Participant.ParticipantID
            order by DataDate, FracOfShares Desc
        """
    return pd.read_sql_query(query, conn)