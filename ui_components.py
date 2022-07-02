# -*- coding: utf-8 -*-
"""
Created on Thu Jun 30 18:43:24 2022

@author: ling
"""

from dash import dcc, html, dash_table
import datetime

from config import TREND_TAB_DATA_COLUMNS, CHANGES_DATA_COLUMNS

    
def get_trend_analysis_tab(stock_map_list: list, min_date: datetime.date, max_date: datetime.date):
    
    return html.Div([
        html.H3(children="CCASS Shareholding Trend"),
        html.P(
            children="""
            Analyze how shareholding of the top 10 participant (as of end date) changes
            """,
        ),
        html.Div([
            html.Div([
                html.H4("Select Stock Code"),
                dcc.Dropdown(
                    id="trend-analysis-select-stock",
                    options=[
                        {
                            "label": f"{stock['stockCode']} - {stock['stockName']}",
                            "value": f"{stock['stockCode']}"
                        } 
                        for stock in stock_map_list
                    ],
                    value='00001',
                    clearable=False,
                ),
            ], style=dict(width='33%')),
            html.Div([
                html.H4("Select Date Range"),
                dcc.DatePickerRange(
                    id="trend-analysis-select-date-range",
                    min_date_allowed=min_date,
                    max_date_allowed=max_date + datetime.timedelta(days=1),
                    start_date=min_date,
                    end_date=max_date,
                ),
            ], style=dict(width='33%', marginLeft='20px')),
        ], style=dict(display='flex')),
        html.Div([
            dcc.Graph(id='trend-plot'),
        ]),
        html.Div(
            get_data_table_as_children(
                title="Raw Shareholding Data for Top Participants",
                dt_id="dt-trend-analysis",
                columns=TREND_TAB_DATA_COLUMNS,
                sort_action='native',
                filter_action='native',
            )
        , style=dict(maxWidth='80%', marginLeft='30px')),
    ])

def get_transaction_finder_tab(stock_map_list: list, min_date: datetime.date, max_date: datetime.date):
    return html.Div([
        html.H3(children="CCASS Transaction Finder"),
        html.P([
            "Detect possible transactions between two participants.",
            html.Br(),
            "Participants with shareholding changes >= threshold (%) between start date and end date will be listed below.",
            html.Br(),
            "Select a participant to list the possible participants who may have exchanged shares with."
        ]),
        html.Div([
            html.Div([
                html.H4("Select Stock Code"),
                dcc.Dropdown(
                    id="transaction-finder-select-stock",
                    options=[
                        {
                            "label": f"{stock['stockCode']} - {stock['stockName']}",
                            "value": f"{stock['stockCode']}"
                        } 
                        for stock in stock_map_list
                    ],
                    value='00883',
                    clearable=False,
                ),
            ], style=dict(width='33%')),
            html.Div([
                html.H4("Select Date Range"),
                dcc.DatePickerRange(
                    id="transaction-finder-select-date-range",
                    min_date_allowed=min_date,
                    max_date_allowed=max_date + datetime.timedelta(days=1),
                    start_date=min_date,
                    end_date=max_date,
                ),
            ], style=dict(maxWidth='33%', marginLeft='20px')),
            html.Div([
                html.H4("Input Threshold (%)"),
                dcc.Input(id='transaction-finder-input-threshold', type='number', debounce=True, value=0.5, min=0.1, max=100, step=0.1),
            ], style=dict(width='33%', marginLeft='20px')),
        ], style=dict(display='flex')),
        html.Div([
            html.Div(
                get_data_table_as_children(
                    title="Participant with top Shareholding Changes",
                    dt_id="dt-top-changes-in-shareholding",
                    columns=CHANGES_DATA_COLUMNS,
                    sort_action='native',
                    row_selectable='single',
                    selected_rows=[],
                    cell_selectable=False,
                )
            , style=dict(maxWidth='40%', marginLeft='30px')),
            html.Div(
                get_data_table_as_children(
                    title="Participant with bottom Shareholding Changes",
                    dt_id="dt-bottom-changes-in-shareholding",
                    columns=CHANGES_DATA_COLUMNS,
                    sort_action='native',
                    row_selectable='single',
                    selected_rows=[],
                    cell_selectable=False,
                )
            , style=dict(maxWidth='40%', marginLeft='30px')),            
        ], style=dict(display='flex')),
        html.Div([
            html.Div(
                get_data_table_as_children(
                    title="Possibly exchanged with: ",
                    dt_id="dt-possible-exchanged-participants",
                    columns=CHANGES_DATA_COLUMNS,
                    sort_action='native',
                )
            , style=dict(maxWidth='80%', marginLeft='30px')),
        ]),
    ])

def get_data_table_as_children(title: str, dt_id: str, columns: list, **kwargs):
    return [
        html.H3(title),
        dash_table.DataTable(
            id = dt_id,
            columns = [{'name': col, 'id': col} for col in columns],
            style_header={'textAlign': 'left'},
            style_filter={'textAlign': 'left'},
            style_cell={'textAlign': 'left'},
            css=[{
                'selector': '.dash-spreadsheet td div',
                'rule': '''
                    line-height: 15px;
                    max-height: 30px; min-height: 30px; height: 30px;
                    display: block;
                    overflow-y: hidden;
                   ''' ,
                'selector': '.dash-filter input' ,
                'rule': '''
                    text-align: left !important;
                    padding-left: 5px !important;
                ''',
                'selector': '.dash-header span' ,
                'rule': '''
                    text-align: left !important;
                    margin-left: unset;
                ''',
            }],
            **kwargs
        )
    ]