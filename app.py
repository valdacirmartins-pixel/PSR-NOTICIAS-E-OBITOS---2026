from ddgs import DDGS
from newspaper import Article
import pandas as pd
import time
import random
from datetime import datetime
import psycopg2
from sqlalchemy import (create_engine)


# =========================
# CONEXÃO DATABASE (RAILWAY)
# =========================
import os
DATABASE_URL = "postgresql://postgres:rNKNNtAGmByHNfCuJHLsdoCHuzWOrMry@shuttle.proxy.rlwy.net:37781/railway"

engine = create_engine(DATABASE_URL)

# =========================
# MUNICÍPIOS BASE
# =========================
url_ibge = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/master/csv/municipios.csv"
df_municipios = pd.read_csv(url_ibge)

df_municipios["nome"] = df_municipios["nome"].str.lower()

coords = {
    row["nome"]: (row["latitude"], row["longitude"], row["codigo_uf"])
    for _, row in df_municipios.iterrows()
}

lista_municipios = list(coords.keys())

# =========================
# DETECTAR MUNICÍPIO
# =========================
def detectar_municipio(texto):
    for m in lista_municipios:
        if f" {m} " in texto:
            return m
    return None

# =========================
# CLASSIFICAÇÃO
# =========================
CATEGORIAS = {
    "Morte": ["morto", "morreu", "óbito", "falecimento"],
    "Violência": ["assassinado", "agredido", "espancado"],
    "Acidente": ["acidente", "atropelado"],
    "Outros": []
}

def classificar(texto):
    for categoria, palavras in CATEGORIAS.items():
        if any(p in texto for p in palavras):
            return categoria
    return "Outros"

# =========================
# PROCESSAR NOTÍCIA
# =========================
def processar(url):
    try:
        art = Article(url, language="pt")
        art.download()
        art.parse()

        texto = (art.text or "").lower()
        titulo = (art.title or "").lower()
        base = f" {titulo} {texto} "

        municipio = detectar_municipio(base)

        if municipio:
            lat, lon, uf = coords.get(municipio, (None, None, None))
        else:
            municipio = "Não identificado"
            lat, lon, uf = -14.2350, -51.9253, "NI"

        if lat is None:
            return None

        categoria = classificar(base)

        lat += random.uniform(-0.02, 0.02)
        lon += random.uniform(-0.02, 0.02)

        return {
            "titulo": art.title,
            "url": url,
            "municipio": municipio.title(),
            "uf": uf,
            "categoria": categoria,
            "latitude": lat,
            "longitude": lon,
            "data": datetime.now()
        }

    except:
        return None

# =========================
# BUSCA
# =========================
QUERIES = [
    "morador de rua morto",
    "morador de rua morreu",
    "sem teto morto",
    "assassinato morador de rua",
    "violência contra morador de rua"
]

urls = set()
tarefas = []

with DDGS() as ddgs:
    for q in QUERIES:
        for r in ddgs.text(q, region="br-pt", max_results=50):
            url = r["href"]
            if url not in urls:
                urls.add(url)
                tarefas.append(url)

# =========================
# PROCESSAMENTO
# =========================
dados = []

for url in tarefas:
    res = processar(url)
    if res:
        dados.append(res)
    time.sleep(random.uniform(0.2, 0.5))

df = pd.DataFrame(dados)

if df.empty:
    print("⚠️ Nenhum dado encontrado")
    exit()

# =========================
# MÉTRICAS
# =========================
df["qtd_municipio"] = df.groupby("municipio")["municipio"].transform("count")
df["qtd_categoria"] = df.groupby("categoria")["categoria"].transform("count")

# =========================
# SALVAR NO POSTGRESQL
# =========================
try:
    df.to_sql("pop_rua", engine, if_exists="append", index=False)
    print("✅ Dados enviados para o Railway com sucesso!")
except Exception as e:
    print("❌ Erro ao enviar para o banco:", e)

print("🚀 FINALIZADO")
