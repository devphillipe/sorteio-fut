# app.py
import streamlit as st
import pandas as pd
import sqlite3
import os
from typing import List, Tuple

DB_FILE = "dados.db"

# -----------------------
# Banco de dados
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Jogadores (resumo)
    c.execute("""
        CREATE TABLE IF NOT EXISTS jogadores (
            nome TEXT PRIMARY KEY,
            media REAL DEFAULT 0,
            total_avaliacoes INTEGER DEFAULT 0
        )
    """)

    # Avaliações com 4 atributos e overall
    c.execute("""
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogador TEXT,
            chute REAL,
            forca REAL,
            agilidade REAL,
            drible REAL,
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

def adicionar_jogadores(nomes: List[str]):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for nome in nomes:
        c.execute("INSERT OR IGNORE INTO jogadores (nome) VALUES (?)", (nome,))
    conn.commit()
    conn.close()

def registrar_avaliacao(jogador: str, chute: float, forca: float, agilidade: float, drible: float):
    overal = (chute + forca + agilidade + drible) / 4.0
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT INTO avaliacoes (jogador, chute, forca, agilidade, drible, overal)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (jogador, chute, forca, agilidade, drible, overal))

    c.execute("SELECT media, total_avaliacoes FROM jogadores WHERE nome=?", (jogador,))
    row = c.fetchone()
    if row:
        media, total = row
    else:
        media, total = 0.0, 0

    nova_media = (media * total + overal) / (total + 1)
    c.execute("UPDATE jogadores SET media=?, total_avaliacoes=? WHERE nome=?", (nova_media, total + 1, jogador))

    conn.commit()
    conn.close()

def carregar_jogadores_resumo() -> pd.DataFrame:
    """
    Retorna tabela com: nome, media (overall), total_avaliacoes,
    e médias por atributo (chute_avg, forca_avg, agilidade_avg, drible_avg).
    """
    conn = sqlite3.connect(DB_FILE)
    # pega resumo por atributos da tabela avaliacoes
    q = """
    SELECT j.nome,
           j.media,
           j.total_avaliacoes,
           COALESCE(a.chute_avg, 0) AS chute_avg,
           COALESCE(a.forca_avg, 0) AS forca_avg,
           COALESCE(a.agilidade_avg, 0) AS agilidade_avg,
           COALESCE(a.drible_avg, 0) AS drible_avg,
           COALESCE(a.overal_avg, 0) AS overal_avg
    FROM jogadores j
    LEFT JOIN (
        SELECT jogador,
               AVG(chute) AS chute_avg,
               AVG(forca) AS forca_avg,
               AVG(agilidade) AS agilidade_avg,
               AVG(drible) AS drible_avg,
               AVG(overal) AS overal_avg,
               COUNT(*) as cnt
        FROM avaliacoes
        GROUP BY jogador
    ) a ON a.jogador = j.nome
    ORDER BY j.nome
    """
    df = pd.read_sql(q, conn)
    conn.close()
    return df

def carregar_jogadores_para_sorteio() -> pd.DataFrame:
    """Retorna jogadores com media (usada para sortear)."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT nome, media FROM jogadores", conn)
    conn.close()
    return df

def salvar_sorteio(time_a: List[str], time_b: List[str], time_c: List[str], media_a: float, media_b: float, media_c: float):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sorteios (time_a, time_b, time_c, media_a, media_b, media_c) VALUES (?, ?, ?, ?, ?, ?)",
        (", ".join(time_a) if time_a else None,
         ", ".join(time_b) if time_b else None,
         ", ".join(time_c) if time_c else None,
         media_a, media_b, media_c)
    )
    conn.commit()
    conn.close()

def carregar_sorteios() -> pd.DataFrame:
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM sorteios ORDER BY data DESC", conn)
    conn.close()
    return df

def resetar_avaliacoes():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM avaliacoes")
    c.execute("UPDATE jogadores SET media = 0, total_avaliacoes = 0")
    conn.commit()
    conn.close()

# -----------------------
# Lógica de Sorteio
# -----------------------
def distribuir_times_balanceado(jogadores: List[Tuple[str, float]]) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    jogadores: lista de (nome, media) já ordenada por media desc (opcional).
    Retorna: time_a, time_b, time_c, reservas
    Regras:
      - Cada time tem no máximo 5 jogadores.
      - Se houver > 10 jogadores, cria time C (até 5).
      - Se houver mais que 15, coloca extras em 'reservas'.
      - Balanceamento: atribui sempre ao time com menor soma atual considerando capacidade.
    """
    # copia
    players = list(jogadores)
    # ordenar por media descendente (melhores primeiro)
    players.sort(key=lambda x: x[1], reverse=True)

    time_a = []
    time_b = []
    time_c = []
    reservas = []
    soma_a = soma_b = soma_c = 0.0

    # define capacidade por time
    cap_a = cap_b = 5
    cap_c = 5 if len(players) > 10 else 0

    for nome, media in players:
        # escolher time elegível com menor soma (e espaço)
        choices = []
        if len(time_a) < cap_a:
            choices.append(("A", soma_a))
        if len(time_b) < cap_b:
            choices.append(("B", soma_b))
        if cap_c and len(time_c) < cap_c:
            choices.append(("C", soma_c))

        if not choices:
            reservas.append(nome)
            continue

        # pega time com menor soma
        choices.sort(key=lambda x: x[1])
        pick = choices[0][0]

        if pick == "A":
            time_a.append(nome)
            soma_a += media
        elif pick == "B":
            time_b.append(nome)
            soma_b += media
        else:
            time_c.append(nome)
            soma_c += media

    return time_a, time_b, time_c, reservas

# -----------------------
# Inicialização app
# -----------------------
init_db()
st.set_page_config(page_title="Sorteador de Times ⚽", page_icon="⚽", layout="centered")

# CSS / Estilo moderno
st.markdown(
    """
    <style>
    .main { background-color: #f7fbfe; padding: 18px; border-radius: 12px; }
    h1, h2, h3 { color: #0f172a; text-align: center; }
    .team-card {
        background-color: #ffffff;
        padding: 12px;
        border-radius: 12px;
        box-shadow: 0 6px 18px rgba(15,23,42,0.06);
        margin-bottom: 12px;
    }
    .team-title { font-size: 1.1rem; font-weight: 700; color: #0b5cff; text-align:center; }
    .player { text-align: left; padding: 4px 0; color: #334155; }
    .small-muted { color: #64748b; font-size:12px; }
    .footer { text-align:center; color:#94a3b8; margin-top:18px; font-size:13px }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🎲 Sorteador de Times - Estilo FIFA (Overall por atributos)")
st.write("Avalie cada jogador em **Chute, Força, Agilidade e Drible** → o sistema calcula o **Overall** e faz sorteios balanceados (times de 5).")

# Sidebar menu
menu = st.sidebar.selectbox("Navegação", ["Cadastrar Semana", "Avaliar Jogadores", "Sortear Times", "Histórico de Sorteios"])

# -----------------------
# Cadastrar Semana
# -----------------------
if menu == "Cadastrar Semana":
    st.header("📅 Cadastrar nova lista de jogadores")
    st.info("Cole os nomes separados por vírgula ou um por linha. Exemplo:\nAna, Carlos, Pedro\nou\nAna\nCarlos\nPedro")

    nomes_input = st.text_area("Lista de jogadores", height=140, placeholder="Um por linha ou separados por vírgula")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Salvar lista"):
            if nomes_input.strip():
                # aceita linhas ou vírgulas
                if "," in nomes_input:
                    nomes = [n.strip() for n in nomes_input.split(",") if n.strip()]
                else:
                    nomes = [n.strip() for n in nomes_input.splitlines() if n.strip()]
                adicionar_jogadores(nomes)
                st.success(f"{len(nomes)} jogadores adicionados/atualizados!")
            else:
                st.warning("Por favor, insira ao menos um nome.")
    with col2:
        if st.button("Atualizar tabela"):
            st.experimental_rerun()

    st.subheader("Jogadores (resumo de médias por atributo)")
    df_resumo = carregar_jogadores_resumo()
    if df_resumo.empty:
        st.info("Nenhum jogador cadastrado ainda.")
    else:
        # mostra tabela com colunas úteis
        df_show = df_resumo[["nome", "total_avaliacoes", "chute_avg", "forca_avg", "agilidade_avg", "drible_avg", "overal_avg"]]
        df_show = df_show.rename(columns={
            "nome":"Nome",
            "total_avaliacoes":"Aval.",
            "chute_avg":"Chute",
            "forca_avg":"Força",
            "agilidade_avg":"Agilidade",
            "drible_avg":"Drible",
            "overal_avg":"Overall"
        })
        st.dataframe(df_show.style.format({
            "Chute":"{:.2f}", "Força":"{:.2f}", "Agilidade":"{:.2f}", "Drible":"{:.2f}", "Overall":"{:.2f}"
        }), height=300)

    st.divider()
    st.subheader("🔄 Resetar Avaliações")
    st.warning("Isso apagará todas as notas e zerará as médias dos jogadores (mantendo a lista de jogadores e histórico de sorteios).")
    if st.button("Resetar todas as avaliações"):
        resetar_avaliacoes()
        st.success("✅ Avaliações resetadas.")
        st.experimental_rerun()

# -----------------------
# Avaliar Jogadores
# -----------------------
elif menu == "Avaliar Jogadores":
    st.header("📝 Avaliar Jogadores (anônimo)")
    st.info("Cada jogador recebe 4 notas (0–10). O Overall é calculado automaticamente (média simples).")

    df = carregar_jogadores_resumo()
    if df.empty:
        st.warning("Nenhum jogador cadastrado. Vá em 'Cadastrar Semana' para adicionar jogadores.")
    else:
        # organizar inputs
        st.write("Apenas ajuste os sliders e clique em **Enviar avaliações**. Avaliações são anônimas.")
        avaliacoes_temp = {}
        for _, row in df.iterrows():
            nome = row["nome"]
            st.markdown(f"---\n**{nome}**")
            c1, c2 = st.columns(2)
            with c1:
                chute = st.slider(f"Chute — {nome}", 0, 10, 5, key=f"chute_{nome}")
                forca = st.slider(f"Força — {nome}", 0, 10, 5, key=f"forca_{nome}")
            with c2:
                agilidade = st.slider(f"Agilidade — {nome}", 0, 10, 5, key=f"agilidade_{nome}")
                drible = st.slider(f"Drible — {nome}", 0, 10, 5, key=f"drible_{nome}")
            avaliacoes_temp[nome] = (chute, forca, agilidade, drible)

        if st.button("Enviar avaliações"):
            for jogador, vals in avaliacoes_temp.items():
                registrar_avaliacao(jogador, *vals)
            st.success("✅ Avaliações enviadas com sucesso!")
            st.experimental_rerun()

# -----------------------
# Sortear Times
# -----------------------
elif menu == "Sortear Times":
    st.header("🎯 Sortear Times (balanceado por Overall)")
    st.info("Cada time terá até 5 jogadores. Se houver mais de 10 jogadores, será criado o Time C (até 5).")

    df = carregar_jogadores_para_sorteio()
    if df.empty:
        st.warning("Nenhum jogador cadastrado.")
    else:
        st.subheader("Overalls atuais")
        st.dataframe(df.sort_values(by="media", ascending=False).rename(columns={"nome":"Nome", "media":"Overall"}).style.format({"Overall":"{:.2f}"}), height=250)

        if st.button("🔄 Sortear Times Equilibrados"):
            players = list(df.itertuples(index=False, name=None))  # list of (nome, media)
            # garantir forma (nome, media)
            players = [(p[0], float(p[1] or 0.0)) for p in players]

            time_a, time_b, time_c, reservas = distribuir_times_balanceado(players)

            # calcular médias
            def media_time(lista):
                if not lista: return 0.0
                # pegar medias originais
                lookup = {n:m for n,m in players}
                s = sum(lookup.get(n, 0.0) for n in lista)
                return s / len(lista)

            media_a = media_time(time_a)
            media_b = media_time(time_b)
            media_c = media_time(time_c)

            salvar_sorteio(time_a, time_b, time_c, media_a, media_b, media_c)

            st.success("✅ Sorteio realizado e salvo!")

            # Exibição moderna: 3 colunas
            cols = st.columns(3)
            with cols[0]:
                st.markdown('<div class="team-card">', unsafe_allow_html=True)
                st.markdown('<div class="team-title">🔵 Time A</div>', unsafe_allow_html=True)
                if time_a:
                    for p in time_a:
                        st.markdown(f'<div class="player">• {p}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="small-muted">Média: {media_a:.2f} — Jogadores: {len(time_a)}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="player">—</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with cols[1]:
                st.markdown('<div class="team-card">', unsafe_allow_html=True)
                st.markdown('<div class="team-title">🔴 Time B</div>', unsafe_allow_html=True)
                if time_b:
                    for p in time_b:
                        st.markdown(f'<div class="player">• {p}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="small-muted">Média: {media_b:.2f} — Jogadores: {len(time_b)}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="player">—</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with cols[2]:
                st.markdown('<div class="team-card">', unsafe_allow_html=True)
                st.markdown('<div class="team-title">🟢 Time C</div>', unsafe_allow_html=True)
                if time_c:
                    for p in time_c:
                        st.markdown(f'<div class="player">• {p}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="small-muted">Média: {media_c:.2f} — Jogadores: {len(time_c)}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="player">(não criado)</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            if reservas:
                st.divider()
                st.subheader("Reservas / Extras (além das 15 vagas)")
                st.write(", ".join(reservas))

            st.divider()
            if st.button("Novo Sorteio"):
                st.experimental_rerun()

# -----------------------
# Histórico de Sorteios
# -----------------------
elif menu == "Histórico de Sorteios":
    st.header("📜 Histórico de Sorteios")
    df_hist = carregar_sorteios()
    if df_hist.empty:
        st.info("Ainda não há sorteios registrados.")
    else:
        # mostra as últimas entradas com colunas úteis
        df_show = df_hist.copy()
        df_show = df_show[["data", "time_a", "time_b", "time_c", "media_a", "media_b", "media_c"]]
        df_show = df_show.rename(columns={
            "data":"Data",
            "time_a":"Time A",
            "time_b":"Time B",
            "time_c":"Time C",
            "media_a":"Média A",
            "media_b":"Média B",
            "media_c":"Média C"
        })
        st.dataframe(df_show, height=350)

st.markdown('<div class="footer">Desenvolvido com ❤️ — Layout Moderno | Avaliações anônimas</div>', unsafe_allow_html=True)