# -*- coding: utf-8 -*-
"""
Created on Thu Jun 30 18:43:24 2022

@author: ling
"""

import dash
from dash import dcc, html
from dash.dependencies import Input, Output

from waitress import serve

import pandas as pd
import datetime

from config import HOST, PORT
from util import create_index_if_not_exist, get_init_params, load_base_env
from util import get_db_connection
from util import get_shareholding_delta_for_transaction_finder
from util import get_shareholding_time_series_for_top_participants
from ui_components import get_trend_analysis_tab, get_transaction_finder_tab

conn = get_db_connection()

create_index_if_not_exist(conn)

stock_map_list, min_date, max_date = get_init_params(conn)

app = dash.Dash(__name__)
app.config.suppress_callback_exceptions = True # Dynamic layout will trigger unnecessary warnings
app.layout = html.Div([
    dcc.Store(id='trend-analysis-store'),
    dcc.Store(id='transaction-finder-store'),
    dcc.Tabs(id="tabs", value='trend-analysis', children=[
        dcc.Tab(label='Trend Analysis', value='trend-analysis'),        
        dcc.Tab(label='Transaction Finder', value='transaction-finder')  
    ]),
    html.Div(id='tabs-content')
])



@app.callback(Output('tabs-content', 'children'),
              Input('tabs', 'value'))
def render_content(tab):
    if tab == 'trend-analysis':
        return get_trend_analysis_tab(stock_map_list, min_date, max_date)
    elif tab == 'transaction-finder':
        return get_transaction_finder_tab(stock_map_list, min_date, max_date)

@app.callback(
    Output('trend-analysis-store', 'data'),
    Output('transaction-finder-store', 'data'),
    Input('select-stock', 'value'),
    Input('select-date-range', 'start_date'),
    Input('select-date-range', 'end_date'),     
)
def on_stock_code_selected(selected_stock_code, start_date, end_date):
    
    start_date_object = datetime.date.fromisoformat(start_date)
    start_date_string = start_date_object.strftime('%Y-%m-%d')
        
    end_date_object = datetime.date.fromisoformat(end_date)
    end_date_string = end_date_object.strftime('%Y-%m-%d')
    
    df_trend_top = get_shareholding_time_series_for_top_participants(
        selected_stock_code, start_date_string, end_date_string, conn
    )
    
    df_shareholding_delta = get_shareholding_delta_for_transaction_finder(
        selected_stock_code, start_date_string, end_date_string, conn
    )
    return (
        df_trend_top.to_dict('records'),
        df_shareholding_delta.to_dict('records')
    )


@app.callback(
    Output('trend-plot', 'figure'),
    Output('dt-trend-analysis', 'data'),
    Input('trend-analysis-store', 'data'),
)
def on_trend_analysis_data_changed(data):
    top_participants = map(lambda d: (d['ParticipantID'], d['ParticipantName']), data[-10:])
    
    data_for_graph = []
    for participant_id, participant_name in top_participants:
        data_participant = list(filter(lambda d: d['ParticipantID'] == participant_id, data))
        data_for_graph.append({
            'name': participant_name,
            'mode': 'lines+markets',
            'x': pd.to_datetime(list(map(lambda d: d['DataDate'], data_participant))),
            'y': list(map(lambda d: d['FracOfShares'], data_participant)),
        })

    return dict(data=data_for_graph), data
    
@app.callback(
    Output('dt-top-changes-in-shareholding', 'data'),
    Output('dt-bottom-changes-in-shareholding', 'data'),
    Input('transaction-finder-store', 'data'),
    Input('input-threshold', 'value'),
)
def on_transaction_finder_data_changed(data, threshold):
    
    top_changes = list(
        sorted(
            filter(lambda d: d['ChangeInPercentShares'] >= threshold, data),
            key=lambda d: d['ChangeInPercentShares'],
            reverse=True # Desc
        )
    )
    bottom_changes = list(
        sorted(
            filter(lambda d: d['ChangeInPercentShares'] <= -threshold, data),
            key=lambda d: d['ChangeInPercentShares'],
            reverse=False # Asc
        )
    )
    return top_changes, bottom_changes

    
if __name__ == "__main__":
    env = load_base_env()
    
    if env == 'DEV':
        app.run_server(host=HOST, port=PORT, debug=True)
    elif env == 'PROD':
        serve(app.server, host=HOST, port=PORT,)