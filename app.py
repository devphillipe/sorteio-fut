import streamlit as st
import pandas as pd
import sqlite3
import os

DB_FILE = "dados.db"

# -----------------------
# Funções de Banco de Dados
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Jogadores
    c.execute("""
        CREATE TABLE IF NOT EXISTS jogadores (
            nome TEXT PRIMARY KEY,
            media REAL DEFAULT 0,
            total_avaliacoes INTEGER DEFAULT 0
        )
    """)

    # Avaliações com 4 atributos
    c.execute("""
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador TEXT,
            forca REAL,
            chute REAL,
            drible REAL,
            agilidade REAL,
            overal REAL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Sorteios
    c.execute("""
        CREATE TABLE IF NOT EXISTS sorteios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_a TEXT,
            time_b TEXT,
            time_c TEXT,
            media_a REAL,
            media_b REAL,
            media_c REAL
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


def registrar_avaliacao(jogador, forca, chute, drible, agilidade):
    overal = (forca + chute + drible + agilidade) / 4
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Insere avaliação completa
    c.execute("""
        INSERT INTO avaliacoes (jogador, forca, chute, drible, agilidade, overal)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (jogador, forca, chute, drible, agilidade, overal))

    # Atualiza média geral do jogador
    c.execute("SELECT media, total_avaliacoes FROM jogadores WHERE nome=?", (jogador,))
    media, total = c.fetchone()
    nova_media = (media * total + overal) / (total + 1)
    c.execute("UPDATE jogadores SET media=?, total_avaliacoes=? WHERE nome=?", (nova_media, total + 1, jogador))
    conn.commit()
    conn.close()


def carregar_jogadores():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM jogadores", conn)
    conn.close()
    return df


def salvar_sorteio(time_a, time_b, time_c, media_a, media_b, media_c):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sorteios (time_a, time_b, time_c, media_a, media_b, media_c) VALUES (?, ?, ?, ?, ?, ?)",
        (
            ", ".join(time_a) if time_a else None,
            ", ".join(time_b) if time_b else None,
            ", ".join(time_c) if time_c else None,
            media_a,
            media_b,
            media_c,
        ),
    )
    conn.commit()
    conn.close()


def carregar_sorteios():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM sorteios ORDER BY data DESC", conn)
    conn.close()
    return df


def resetar_avaliacoes():
    """Zera médias e avaliações (mantém histórico de sorteios)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM avaliacoes")
    c.execute("UPDATE jogadores SET media = 0, total_avaliacoes = 0")
    conn.commit()
    conn.close()


# -----------------------
# Inicialização
# -----------------------
init_db()

st.set_page_config(page_title="Sorteador de Times ⚽", page_icon="⚽", layout="centered")
st.title("⚽ Sorteador de Times - Estilo FIFA")

menu = st.sidebar.radio(
    "Navegação",
    ["Cadastrar Semana", "Avaliar Jogadores", "Sortear Times", "Histórico de Sorteios"]
)

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

    st.divider()
    st.subheader("🔄 Resetar Avaliações")
    st.warning("Isso apagará todas as notas e zerará as médias dos jogadores, mas manterá o histórico dos sorteios.")
    if st.button("Resetar todas as avaliações"):
        resetar_avaliacoes()
        st.success("✅ Todas as avaliações foram resetadas com sucesso!")

# -----------------------
# 2️⃣ Avaliar Jogadores
# -----------------------
elif menu == "Avaliar Jogadores":
    st.header("📝 Avaliação estilo FIFA")
    st.info("Avalie os atributos de cada jogador anonimamente — várias pessoas podem avaliar ao mesmo tempo.")

    df_jogadores = carregar_jogadores()

    if df_jogadores.empty:
        st.warning("Nenhum jogador cadastrado.")
    else:
        avaliacoes = {}
        for _, row in df_jogadores.iterrows():
            st.subheader(f"⚽ {row['nome']}")
            col1, col2 = st.columns(2)
            with col1:
                forca = st.slider(f"Força ({row['nome']})", 0, 10, 5, key=f"forca_{row['nome']}")
                chute = st.slider(f"Chute ({row['nome']})", 0, 10, 5, key=f"chute_{row['nome']}")
            with col2:
                drible = st.slider(f"Drible ({row['nome']})", 0, 10, 5, key=f"drible_{row['nome']}")
                agilidade = st.slider(f"Agilidade ({row['nome']})", 0, 10, 5, key=f"agilidade_{row['nome']}")
            avaliacoes[row["nome"]] = (forca, chute, drible, agilidade)

        if st.button("Enviar avaliações"):
            for j, (forca, chute, drible, agilidade) in avaliacoes.items():
                registrar_avaliacao(j, forca, chute, drible, agilidade)
            st.success("✅ Avaliações enviadas anonimamente com sucesso!")

# -----------------------
# 3️⃣ Sortear Times
# -----------------------
elif menu == "Sortear Times":
    st.header("🎯 Sorteio Balanceado (Times de 5 jogadores)")
    df = carregar_jogadores()
    if df.empty:
        st.warning("Nenhum jogador cadastrado.")
    else:
        st.subheader("📊 Overal atual")
        st.dataframe(df[["nome", "media", "total_avaliacoes"]].sort_values(by="media", ascending=False))

        if st.button("Sortear Times Equilibrados"):
            jogadores = df.sort_values(by="media", ascending=False).to_dict(orient="records")

            time_a, time_b, time_c = [], [], []
            soma_a, soma_b, soma_c = 0, 0, 0

            for j in jogadores:
                # Decide qual time tem menor média e espaço disponível
                if len(time_a) < 5 and (soma_a <= soma_b and soma_a <= soma_c):
                    time_a.append(j["nome"])
                    soma_a += j["media"]
                elif len(time_b) < 5 and (soma_b <= soma_a and soma_b <= soma_c):
                    time_b.append(j["nome"])
                    soma_b += j["media"]
                else:
                    time_c.append(j["nome"])
                    soma_c += j["media"]

            # Calcular médias (evita divisão por zero)
            media_a = soma_a / len(time_a) if time_a else 0
            media_b = soma_b / len(time_b) if time_b else 0
            media_c = soma_c / len(time_c) if time_c else 0

            salvar_sorteio(time_a, time_b, time_c, media_a, media_b, media_c)

            st.success("✅ Sorteio realizado e salvo no histórico!")
            st.write("### 🅰️ Time A")
            st.write(", ".join(time_a))
            st.write(f"Média Time A: {media_a:.2f}")

            st.write("### 🅱️ Time B")
            st.write(", ".join(time_b))
            st.write(f"Média Time B: {media_b:.2f}")

            if time_c:
                st.write("### 🇨 Time C")
                st.write(", ".join(time_c))
                st.write(f"Média Time C: {media_c:.2f}")

# -----------------------
# 4️⃣ Histórico de Sorteios
# -----------------------
elif menu == "Histórico de Sorteios":
    st.header("📜 Histórico de Sorteios")
    df_hist = carregar_sorteios()
    if df_hist.empty:
        st.info("Ainda não há sorteios registrados.")
    else:
        st.dataframe(df_hist)