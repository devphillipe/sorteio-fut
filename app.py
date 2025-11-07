import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os

DB_FILE = "dados.db"

# -----------------------
# Funções de Banco de Dados
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS jogadores (
            nome TEXT PRIMARY KEY,
            media REAL DEFAULT 0,
            total_avaliacoes INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador TEXT,
            nota REAL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sorteios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_a TEXT,
            time_b TEXT,
            media_a REAL,
            media_b REAL
        )
    """)
    conn.commit()
    conn.close()


def adicionar_jogadores(nomes):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for nome in nomes:
        c.execute("INSERT OR IGNORE INTO jogadores (nome) VALUES (?)", (nome,))
    conn.commit()
    conn.close()


def registrar_avaliacao(jogador, nota):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO avaliacoes (jogador, nota) VALUES (?, ?)", (jogador, nota))
    # Atualiza média do jogador
    c.execute("SELECT media, total_avaliacoes FROM jogadores WHERE nome=?", (jogador,))
    media, total = c.fetchone()
    nova_media = (media * total + nota) / (total + 1)
    c.execute("UPDATE jogadores SET media=?, total_avaliacoes=? WHERE nome=?", (nova_media, total + 1, jogador))
    conn.commit()
    conn.close()


def carregar_jogadores():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM jogadores", conn)
    conn.close()
    return df


def salvar_sorteio(time_a, time_b, media_a, media_b):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sorteios (time_a, time_b, media_a, media_b) VALUES (?, ?, ?, ?)",
        (", ".join(time_a), ", ".join(time_b), media_a, media_b),
    )
    conn.commit()
    conn.close()


def carregar_sorteios():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM sorteios ORDER BY data DESC", conn)
    conn.close()
    return df


# -----------------------
# Inicialização
# -----------------------
init_db()

st.title("⚽ Sorteador de Times - Avaliações Anônimas")

menu = st.sidebar.radio("Navegação", ["Cadastrar Semana", "Avaliar Jogadores", "Sortear Times", "Histórico de Sorteios"])

# -----------------------
# 1️⃣ Cadastrar Semana
# -----------------------
if menu == "Cadastrar Semana":
    st.header("📅 Cadastrar nova lista de jogadores")
    st.info("Cole os nomes separados por vírgula. Exemplo: João, Pedro, Lucas")

    nomes_input = st.text_area("Lista de jogadores")
    if st.button("Salvar lista"):
        if nomes_input.strip():
            nomes = [n.strip() for n in nomes_input.split(",") if n.strip()]
            adicionar_jogadores(nomes)
            st.success(f"{len(nomes)} jogadores adicionados/atualizados!")
        else:
            st.warning("Por favor, insira pelo menos um nome.")

    st.subheader("Jogadores atuais")
    st.dataframe(carregar_jogadores())

# -----------------------
# 2️⃣ Avaliar Jogadores
# -----------------------
elif menu == "Avaliar Jogadores":
    st.header("📝 Avaliação Anônima")
    st.info("Avalie apenas os jogadores novos (sem média ainda).")

    df_jogadores = carregar_jogadores()
    novos = df_jogadores[df_jogadores["total_avaliacoes"] == 0]

    if novos.empty:
        st.success("✅ Nenhum jogador novo precisa ser avaliado.")
    else:
        st.write("Jogadores a serem avaliados:")
        avaliacoes = {}
        for _, row in novos.iterrows():
            avaliacoes[row["nome"]] = st.slider(f"{row['nome']}", 0, 10, 5)

        if st.button("Enviar avaliação"):
            for j, nota in avaliacoes.items():
                registrar_avaliacao(j, nota)
            st.success("Avaliações enviadas anonimamente com sucesso!")

# -----------------------
# 3️⃣ Sortear Times
# -----------------------
elif menu == "Sortear Times":
    st.header("🎯 Sorteio Balanceado")
    df = carregar_jogadores()
    if df.empty:
        st.warning("Nenhum jogador cadastrado.")
    else:
        st.subheader("📊 Médias atuais")
        st.dataframe(df[["nome", "media", "total_avaliacoes"]].sort_values(by="media", ascending=False))

        if st.button("Sortear Times Equilibrados"):
            # Ordena por média e distribui equilibradamente
            jogadores = df.sort_values(by="media", ascending=False).to_dict(orient="records")
            time_a, time_b = [], []
            soma_a, soma_b = 0, 0

            for j in jogadores:
                if soma_a <= soma_b:
                    time_a.append(j["nome"])
                    soma_a += j["media"]
                else:
                    time_b.append(j["nome"])
                    soma_b += j["media"]

            media_a = soma_a / len(time_a)
            media_b = soma_b / len(time_b)

            salvar_sorteio(time_a, time_b, media_a, media_b)

            st.success("✅ Sorteio realizado e salvo no histórico!")
            st.write("**Time A:**", ", ".join(time_a))
            st.write(f"Média Time A: {media_a:.2f}")
            st.write("**Time B:**", ", ".join(time_b))
            st.write(f"Média Time B: {media_b:.2f}")

# -----------------------
# 4️⃣ Histórico
# -----------------------
elif menu == "Histórico de Sorteios":
    st.header("📜 Histórico de Sorteios")
    df_hist = carregar_sorteios()
    if df_hist.empty:
        st.info("Ainda não há sorteios registrados.")
    else:
        st.dataframe(df_hist)
