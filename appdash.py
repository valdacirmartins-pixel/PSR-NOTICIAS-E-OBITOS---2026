import dash
from dash import dcc, html, Input, Output, dash_table
import pandas as pd
import plotly.express as px
import folium
from folium.plugins import MarkerCluster
from dash.dcc import send_data_frame
import dash_auth
from sqlalchemy import create_engine
import os

# =========================
# CONFIGURAÇÃO E AUTENTICAÇÃO
# =========================
app = dash.Dash(__name__)
server = app.server

VALID_USERNAME_PASSWORD_PAIRS = {'MDHC': '1234'}
auth = dash_auth.BasicAuth(app, VALID_USERNAME_PASSWORD_PAIRS)

# =========================
# CONEXÃO DATABASE (MESMA DO SEU SCRIPT DE BUSCA)
# =========================
DATABASE_URL = "postgresql://postgres:rNKNNtAGmByHNfCuJHLsdoCHuzWOrMry@shuttle.proxy.rlwy.net:37781/railway"
engine = create_engine(DATABASE_URL)


def carregar_dados():
    try:
        # Lê a tabela que seu outro script preenche
        df = pd.read_sql("pop_rua", engine)
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df['quantidade'] = 1
        return df
    except:
        # Caso o banco esteja vazio ainda, cria um DF vazio com as colunas
        return pd.DataFrame(columns=['municipio', 'categoria', 'uf', 'latitude', 'longitude', 'data', 'quantidade'])


# =========================
# FUNÇÃO DO MAPA (CORRIGIDA PARA NUVEM)
# =========================
def gerar_mapa(df):
    # tiles="cartodbpositron" evita o erro de "Access Blocked" no Railway
    mapa = folium.Map(location=[-14, -55], zoom_start=4, tiles="cartodbpositron")
    cluster = MarkerCluster().add_to(mapa)

    for _, row in df.iterrows():
        if pd.isna(row['latitude']) or pd.isna(row['longitude']):
            continue

        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=10,
            fill=True,
            color='red',
            popup=f"{row['municipio']} - {row['categoria']}"
        ).add_to(cluster)

    return mapa._repr_html_()


# =========================
# LAYOUTS
# =========================
def layout_home():
    return html.Div([
        html.H1("📊 Painel População em Situação de Rua"),
        html.Img(src="https://www.gov.br/mdh/pt-br/assuntos/noticias/2023/logo-mdhc.png", style={"width": "200px"}),
        html.P("Monitoramento via Banco de Dados Railway (PostgreSQL)"),
        html.Button("Entrar no Painel", id="btn_entrar", style={'padding': '10px 20px', 'fontSize': '18px'})
    ], style={"textAlign": "center", "marginTop": "100px"})


def layout_dashboard():
    df_temp = carregar_dados()
    return html.Div(style={'padding': '20px'}, children=[
        html.H2("📊 Painel em Tempo Real - PSR"),

        html.Div(id='cards_resumo', style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),

        html.Div([
            dcc.Dropdown(id='filtro_uf', multi=True,
                         options=[{'label': i, 'value': i} for i in sorted(df_temp['uf'].dropna().unique())],
                         placeholder="Filtrar por UF"),
            dcc.Dropdown(id='filtro_categoria', multi=True,
                         options=[{'label': i, 'value': i} for i in sorted(df_temp['categoria'].unique())],
                         placeholder="Categoria")
        ], style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '10px'}),

        html.Br(),

        html.Div([
            html.Div([
                html.Iframe(id='mapa_html', style={'width': '100%', 'height': '600px', 'border': 'none'})
            ], style={'width': '60%'}),
            html.Div([
                dcc.Graph(id='grafico_categoria'),
                dcc.Graph(id='grafico_uf')
            ], style={'width': '40%'})
        ], style={'display': 'flex', 'gap': '10px'}),

        dash_table.DataTable(id='tabela', page_size=10, style_table={'marginTop': '20px'}),

        dcc.Interval(id='intervalo_att', interval=600000),  # Atualiza a cada 10 min
        html.Button("⬇️ Baixar Dados", id="btn_exportar"),
        dcc.Download(id="download_csv")
    ])


# =========================
# LÓGICA DE NAVEGAÇÃO
# =========================
app.layout = html.Div([
    dcc.Store(id="pagina", data="home"),
    html.Div(id="conteudo")
])


@app.callback(Output("pagina", "data"), Input("btn_entrar", "n_clicks"), prevent_initial_call=True)
def trocar(n): return "dashboard"


@app.callback(Output("conteudo", "children"), Input("pagina", "data"))
def renderizar(pagina):
    return layout_home() if pagina == "home" else layout_dashboard()


# =========================
# ATUALIZAÇÃO DO DASHBOARD
# =========================
@app.callback(
    [Output('mapa_html', 'srcDoc'),
     Output('grafico_categoria', 'figure'),
     Output('grafico_uf', 'figure'),
     Output('tabela', 'data'),
     Output('cards_resumo', 'children')],
    [Input('filtro_uf', 'value'),
     Input('filtro_categoria', 'value'),
     Input('intervalo_att', 'n_intervals')]
)
def atualizar(ufs, categorias, n):
    df = carregar_dados()

    if ufs:
        df = df[df['uf'].isin(ufs)]
    if categorias:
        df = df[df['categoria'].isin(categorias)]

    # Mapa
    mapa_res = gerar_mapa(df)

    # Gráficos
    fig_cat = px.pie(df, names='categoria', title="Distribuição por Categoria")
    fig_uf = px.bar(df['uf'].value_counts().reset_index(), x='uf', y='count', title="Notícias por UF")

    # Tabela e Cards
    tabela_data = df[['municipio', 'uf', 'categoria', 'data']].tail(100).to_dict('records')
    cards = [
        html.Div(f"Total de Registros: {len(df)}", style={'border': '1px solid #ccc', 'padding': '10px'}),
        html.Div(f"Cidades Afetadas: {df['municipio'].nunique()}",
                 style={'border': '1px solid #ccc', 'padding': '10px'})
    ]

    return mapa_res, fig_cat, fig_uf, tabela_data, cards


# =========================
# EXPORTAÇÃO
# =========================
@app.callback(Output("download_csv", "data"), Input("btn_exportar", "n_clicks"), prevent_initial_call=True)
def exportar(n):
    df = carregar_dados()
    return send_data_frame(df.to_csv, "relatorio_pop_rua.csv", index=False)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8050)





