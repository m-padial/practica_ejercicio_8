import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objs as go
import boto3
import os
from dateutil import parser
from decimal import Decimal
import requests

# --- 1. Cargar datos desde FastAPI
API_URL = os.environ.get("API_URL", "https://<tu-app-runner>.awsapprunner.com")

def cargar_datos_desde_api():
    try:
        response = requests.get(f"{API_URL}/datos-todos")
        if response.status_code == 200:
            items = response.json().get("items", [])
            df = pd.DataFrame(items)

            # Convertir tipos numéricos y fechas
            df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
            df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
            df["σ"] = pd.to_numeric(df["σ"], errors="coerce")
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date.astype(str)


            def normalizar_fecha(fecha):
                try:
                    return pd.to_datetime(fecha).date()
                except:
                    return None

            df["vencimiento"] = df["vencimiento"].apply(normalizar_fecha)
            df["vencimiento_str"] = df["vencimiento"].astype(str)
            return df
        else:
            print(f"⚠️ Error en API: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        print(f"❌ Error accediendo a la API: {e}")
        return pd.DataFrame()

df_resultado = cargar_datos_desde_api()
vencimientos = sorted(df_resultado["vencimiento_str"].dropna().unique())
fechas_disponibles = sorted(df_resultado["fecha"].dropna().unique())

# --- 2. Inicializar Dash
app = dash.Dash(__name__)
server = app.server
app.title = "Skew de Volatilidad - MINI IBEX"

vencimientos = sorted(df_resultado["vencimiento"].dropna().unique())

# --- 3. Layout
# --- 3. Layout
app.layout = html.Div(
    style={'fontFamily': 'Segoe UI, sans-serif', 'backgroundColor': '#f5f6fa', 'padding': '30px'},
    children=[
        html.H1("📊 Skew de Volatilidad - MINI IBEX", style={
            'textAlign': 'center',
            'color': '#2f3640',
            'marginBottom': '30px'
        }),

        html.Div([
            html.Label("Selecciona vencimiento:", style={
                'fontWeight': 'bold',
                'marginBottom': '10px',
                'display': 'block'
            }),
            dcc.Dropdown(
                id='vencimiento-dropdown',
                options=[{'label': str(v), 'value': v} for v in vencimientos],
                value=vencimientos[0] if vencimientos else None,
                style={'width': '100%', 'padding': '5px'}
            ),

            html.Br(),

            html.Label("Selecciona hasta 2 fechas:", style={
                'fontWeight': 'bold',
                'marginBottom': '10px',
                'display': 'block'
            }),
            dcc.Dropdown(
                id='fecha-dropdown',
                options=[{'label': str(f), 'value': f} for f in fechas_disponibles],
                value=[fechas_disponibles[-1]] if fechas_disponibles else [],
                multi=True,
                style={'width': '100%', 'padding': '5px'}
            )
        ], style={
            'width': '40%',
            'margin': '0 auto 40px auto',
            'backgroundColor': '#ffffff',
            'padding': '20px',
            'borderRadius': '10px',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'
        }),

        html.Div([
            dcc.Graph(
                id='vol-skew-graph',
                config={'displayModeBar': False},
                style={'height': '600px'}
            )
        ], style={
            'maxWidth': '900px',
            'margin': '0 auto 30px auto',
            'backgroundColor': '#ffffff',
            'padding': '20px',
            'borderRadius': '10px',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'
        }),

        html.Details([
            html.Summary('📄 Ver datos usados en el gráfico', style={
                'fontWeight': 'bold',
                'cursor': 'pointer'
            }),
            html.Div(id='data-table', style={'marginTop': '20px'})
        ], style={
            'width': '90%',
            'margin': '0 auto',
            'backgroundColor': '#ffffff',
            'padding': '20px',
            'borderRadius': '10px',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'
        })
    ]
)

# --- 4. Callback
@app.callback(
    Output('vol-skew-graph', 'figure'),
    Output('data-table', 'children'),
    Input('vencimiento-dropdown', 'value'),
    Input('fecha-dropdown', 'value')
)
def update_graph(vencimiento_seleccionado, fechas):
    if not fechas or len(fechas) > 2:
        return {}, html.Div("⚠️ Selecciona una o dos fechas como máximo.")

    traces = []
    all_data = []

    for fecha in fechas:
        df_vto = df_resultado[
            (df_resultado['vencimiento_str'] == vencimiento_seleccionado) &
            (df_resultado['fecha'] == fecha)
        ]
        if df_vto.empty:
            continue

        df_calls = df_vto[df_vto['tipo'] == 'Call'].dropna(subset=['σ'])
        df_puts = df_vto[df_vto['tipo'] == 'Put'].dropna(subset=['σ'])

        if not df_calls.empty:
            traces.append(go.Scatter(
                x=df_calls['strike'],
                y=df_calls['σ'],
                mode='lines+markers',
                name=f'Calls {fecha}',
                marker=dict(symbol='circle'),
                line=dict(dash='dash'),
                marker_color='blue'
            ))

        if not df_puts.empty:
            traces.append(go.Scatter(
                x=df_puts['strike'],
                y=df_puts['σ'],
                mode='lines+markers',
                name=f'Puts {fecha}',
                marker=dict(symbol='square'),
                marker_color='orange'
            ))

        all_data.append(df_vto)

    df_concat = pd.concat(all_data) if all_data else pd.DataFrame()

    tabla = html.Div([
        dcc.Markdown("#### Datos utilizados"),
        dash_table.DataTable(
            columns=[{"name": i, "id": i} for i in ['fecha', 'strike', 'tipo', 'precio', 'σ']],
            data=df_concat[['fecha', 'strike', 'tipo', 'precio', 'σ']].to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'center',
                'padding': '8px',
                'fontFamily': 'Segoe UI',
            },
            style_header={
                'backgroundColor': '#2f3640',
                'color': 'white',
                'fontWeight': 'bold'
            },
            style_data_conditional=[
                {
                    'if': {'column_id': 'σ'},
                    'backgroundColor': '#f0f9ff',
                }
            ],
            page_size=20
        )
    ])

    figure = {
        'data': traces,
        'layout': go.Layout(
            title=f'Skew de Volatilidad - Vencimiento {vencimiento_seleccionado}',
            xaxis={'title': 'Strike'},
            yaxis={'title': 'Volatilidad Implícita (%)'},
            hovermode='closest',
            template='plotly_white'
        )
    }

    return figure, tabla

# --- 5. Run the server
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)
