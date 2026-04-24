import dash
from dash import dcc, html, Input, Output, dash_table
import pandas as pd
import plotly.express as px
import glob
import folium
from folium.plugins import MarkerCluster
from dash.dcc import send_data_frame

app = dash.Dash(__name__)
server = app.server
import dash_auth


import dash_auth

VALID_USERNAME_PASSWORD_PAIRS = {
    'MDHC': '1234'
}

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)
# =========================
# CARREGAR CSV (
# =========================
# vai buscar qualquer arquivo que comece com esses nomes na pasta do projeto
try:
    arq_noticias = glob.glob("pop_rua_20260414_*.csv")[0]
    df_noticias = pd.read_csv(arq_noticias, sep=None, engine='python', encoding='latin-1', on_bad_lines='skip')

    arq_obitos = glob.glob("pop_rua_Obito_20260416_*.csv")[0]
    df_obitos = pd.read_csv(arq_obitos, sep=";", engine='python', encoding='utf-8-sig', on_bad_lines='skip')
except IndexError:
    print("Erro: Arquivos CSV não encontrados na pasta raiz!")
# =========================
# TRATAMENTO
# =========================
def tratar(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

    for col in ['municipio','categoria','uf','latitude','longitude','data']:
        if col not in df.columns:
            df[col] = None

    for col in df.select_dtypes(include='object'):
        df[col] = df[col].astype(str).str.strip()

    df['municipio'] = df['municipio'].fillna("Não informado")
    df['categoria'] = df['categoria'].fillna("Outros")
    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df['quantidade'] = 1

    return df

df_noticias = tratar(df_noticias)
df_obitos = tratar(df_obitos)
df_total = pd.concat([df_noticias, df_obitos])

# =========================
# MAPA
# =========================
def gerar_mapa(df):
    mapa = folium.Map(location=[-14, -55], zoom_start=4)
    cluster = MarkerCluster().add_to(mapa)

    for _, row in df.iterrows():
        if pd.isna(row['latitude']) or pd.isna(row['longitude']):
            continue

        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=min(row['quantidade']*2, 15),
            fill=True,
            popup=f"{row['municipio']} - {row['quantidade']}"
        ).add_to(cluster)

    mapa.save("mapa.html")

# =========================
# TELA HOME
# =========================
def layout_home():
    return html.Div([
        html.H1("📊 Painel População em Situação de Rua"),

        html.Img(
            src="https://www.gov.br/mdh/pt-br/assuntos/noticias/2023/logo-mdhc.png",
            style={"width": "200px"}
        ),

        html.P("Sistema de monitoramento de notícias e óbitos no Brasil"),

        html.Button("Entrar no Painel", id="btn_entrar")
    ], style={"textAlign": "center", "marginTop": "100px"})

# =========================
# DASHBOARD
# =========================
def layout_dashboard():
    return html.Div(style={'padding': '20px'}, children=[

        html.H2("📊 Painel - População em Situação de Rua"),

        dcc.RadioItems(
            id='tipo_dado',
            options=[
                {'label': 'Notícias', 'value': 'noticias'},
                {'label': 'Óbitos', 'value': 'obitos'},
                {'label': 'Geral', 'value': 'geral'}
            ],
            value='noticias',
            inline=True
        ),

        html.Br(),

        html.Div(id='cards_resumo', style={'display': 'flex', 'gap': '15px'}),

        html.Br(),

        html.Div([
            dcc.Dropdown(id='filtro_uf', multi=True,
                         options=[{'label': i, 'value': i} for i in df_total['uf'].dropna().unique()],
                         placeholder="UF"),

            dcc.Dropdown(id='filtro_municipio', multi=True,
                         options=[{'label': i, 'value': i} for i in df_total['municipio'].unique()],
                         placeholder="Município"),

            dcc.Dropdown(id='filtro_categoria', multi=True,
                         options=[{'label': i, 'value': i} for i in df_total['categoria'].unique()],
                         placeholder="Categoria"),

            dcc.DatePickerRange(id='filtro_data')

        ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)', 'gap': '10px'}),

        html.Br(),

        html.Div([

            html.Div([
                html.Iframe(id='mapa_html', style={'width': '100%', 'height': '600px'})
            ], style={'width': '50%'}),

            html.Div([
                dcc.Graph(id='grafico_categoria'),
                dcc.Graph(id='grafico_uf'),
                dcc.Graph(id='grafico_tempo')
            ], style={'width': '50%'})

        ], style={'display': 'flex'}),

        html.Br(),

        dash_table.DataTable(
            id='tabela',
            columns=[
                {"name": "Município", "id": "municipio"},
                {"name": "Categoria", "id": "categoria"},
                {"name": "Quantidade", "id": "quantidade"},
            ],
            page_size=15
        ),

        html.Br(),

        html.Div(id='insight'),

        html.Br(),

        html.Button("⬇️ Exportar CSV", id="btn_exportar"),
        dcc.Download(id="download_csv")

    ])

# =========================
# LAYOUT PRINCIPAL
# =========================
app.layout = html.Div([
    dcc.Store(id="pagina", data="home"),
    html.Div(id="conteudo")
])

# =========================
# TROCA DE TELA
# =========================
@app.callback(
    Output("pagina", "data"),
    Input("btn_entrar", "n_clicks"),
    prevent_initial_call=True
)
def trocar(n):
    return "dashboard"

@app.callback(
    Output("conteudo", "children"),
    Input("pagina", "data")
)
def renderizar(pagina):
    if pagina == "home":
        return layout_home()
    return layout_dashboard()

# =========================
# CALLBACK PRINCIPAL
# =========================
@app.callback(
    [
        Output('mapa_html', 'srcDoc'),
        Output('grafico_categoria', 'figure'),
        Output('grafico_uf', 'figure'),
        Output('grafico_tempo', 'figure'),
        Output('tabela', 'data'),
        Output('cards_resumo', 'children'),
        Output('insight', 'children'),
    ],
    [
        Input('filtro_uf', 'value'),
        Input('filtro_municipio', 'value'),
        Input('filtro_categoria', 'value'),
        Input('filtro_data', 'start_date'),
        Input('filtro_data', 'end_date'),
        Input('tipo_dado', 'value'),
    ]
)
def atualizar(ufs, municipios, categorias, data_ini, data_fim, tipo):

    # selecionar base correta
    if tipo == 'noticias':
        df = df_noticias.copy()
    elif tipo == 'obitos':
        df = df_obitos.copy()
    else:
        df = df_total.copy()

    # filtros
    if ufs:
        df = df[df['uf'].isin(ufs)]
    if municipios:
        df = df[df['municipio'].isin(municipios)]
    if categorias:
        df = df[df['categoria'].isin(categorias)]
    if data_ini and data_fim:
        df = df[(df['data'] >= data_ini) & (df['data'] <= data_fim)]

    # mapa
    base = df.groupby(['municipio','latitude','longitude'], as_index=False)['quantidade'].sum()
    gerar_mapa(base)
    mapa_html = open("mapa.html", encoding='utf-8').read()

    # gráficos
    fig_cat = px.bar(df.groupby('categoria').size().reset_index(name='q'),
                     x='q', y='categoria', orientation='h')

    fig_uf = px.bar(df.groupby('uf').size().reset_index(name='q'),
                    x='q', y='uf', orientation='h')

    df_time = df.groupby(df['data'].dt.date).size().reset_index(name='q')
    fig_time = px.line(df_time, x='data', y='q')

    # tabela
    tabela = df.groupby(['municipio','categoria']).size().reset_index(name='quantidade')

    # cards
    cards = [
        html.Div(f"Total: {len(df)}"),
        html.Div(f"Municípios: {df['municipio'].nunique()}"),
        html.Div(f"Categorias: {df['categoria'].nunique()}")
    ]

    # insight
    insight = "Sem dados"
    if not df.empty:
        insight = f"Top município: {df.groupby('municipio').size().idxmax()}"

    return mapa_html, fig_cat, fig_uf, fig_time, tabela.to_dict('records'), cards, insight

# =========================
# EXPORTAR
# =========================
@app.callback(
    Output("download_csv", "data"),
    Input("btn_exportar", "n_clicks"),
    prevent_initial_call=True
)
def exportar(n):
    return send_data_frame(df_total.to_csv, "dados.csv", index=False)

# =========================
# RODAR
# =========================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8050)