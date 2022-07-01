# -*- coding: utf-8 -*-
"""
Created on Thu Jun 30 18:43:24 2022

@author: ling
"""

import dash
from dash import dcc, html, no_update
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
    dcc.Store(id='transaction-finder-selected-participant'),
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

@app.callback(
    Output("dt-top-changes-in-shareholding", "selected_rows"),
    Output("dt-bottom-changes-in-shareholding", "selected_rows"),
    Output("transaction-finder-selected-participant", "data"),
    Input("dt-top-changes-in-shareholding", "selected_rows"),
    Input("dt-bottom-changes-in-shareholding", "selected_rows"),
    Input('dt-top-changes-in-shareholding', 'data'),
    Input('dt-bottom-changes-in-shareholding', 'data'),
    prevent_initial_call=True
)
def on_change_row_selected(top_selected_rows, bottom_selected_rows, top_change_data, bot_change_data):
    ctx = dash.callback_context
    trigger_id, trigger_props = ctx.triggered[0]["prop_id"].split(".")[0], ctx.triggered[0]["prop_id"].split(".")[1]
    
    # Unselect participant when filter has changed
    if trigger_props == 'data':
        return [], [], None
    # Below logic is to ensure only 1 participant is selected
    elif trigger_id == 'dt-top-changes-in-shareholding':
        if len(top_selected_rows):
            return top_selected_rows, [], top_change_data[top_selected_rows[0]]
        else:
            return [], no_update, no_update
    elif trigger_id == 'dt-bottom-changes-in-shareholding':
        if len(bottom_selected_rows):
            return [], bottom_selected_rows, bot_change_data[bottom_selected_rows[0]]
        else:
            return no_update, [], no_update

@app.callback(
    Output("dt-possible-exchanged-participants", "data"),
    Input('transaction-finder-store', 'data'),
    Input("transaction-finder-selected-participant", "data"),
    prevent_initial_call=True
)
def on_change_selected_participant(shareholding_data, selected_participant):
    # Empty table if no participant is selected
    if selected_participant is None:
        return []
    
    participant_change = selected_participant['ChangeInPercentShares']
    is_buyer = participant_change > 0
    
    # Get whole list of possible buyers/sellers (in opposite direction)
    shareholding_data = list(
        sorted(
            filter(
                lambda d: d['ChangeInPercentShares'] < 0 if is_buyer else d['ChangeInPercentShares'] > 0,
                shareholding_data
            ),
            key=lambda d: d['ChangeInPercentShares'],
            reverse=not is_buyer # Asc if participant is a buyer
        )
    )
    
    # Heuristic to get those the participant has possibly exchanged with
    results = []
    running_changes = 0
    for other_participant in shareholding_data:
        # For bigger buyer / sellers (who buys/sells more than 50% of the change of selected participant):
        #   Include all of them
        if abs(other_participant['ChangeInPercentShares']) >= 0.5 * abs(participant_change):
            results.append(other_participant)
            continue
        # For smaller buyer / sellers:
        #   Accumulate until the changes of them sum up to the change of selected participant
        if (running_changes <= abs(participant_change)):
            results.append(other_participant)
            running_changes += abs(other_participant['ChangeInPercentShares'])
    
    return results
    
    
if __name__ == "__main__":
    env = load_base_env()
    
    if env == 'DEV':
        app.run_server(host=HOST, port=PORT, debug=True)
    elif env == 'PROD':
        serve(app.server, host=HOST, port=PORT,)