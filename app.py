import streamlit as st
import requests
import json
import os
from html import escape as html_escape
from datetime import datetime

from youtube_analytics import config
from youtube_analytics.anthropic import post_messages
from youtube_analytics.parsing import parsear_dados
from youtube_analytics.github_client import fetch_raw_json_or, fetch_raw_text_or, put_repository_file

# ── CONFIG ──
REPO = config.REPO
GITHUB_TOKEN = st.secrets.get('TOKEN_PERSONAL_GITHUB', '') or st.secrets.get('GITHUB_TOKEN_PERSONAL', '') or os.environ.get('TOKEN_PERSONAL_GITHUB', '')
CLAUDE_API_KEY = st.secrets.get('CLAUDE_API_KEY', '') or os.environ.get('CLAUDE_API_KEY', '')
RAW_BASE = f'https://raw.githubusercontent.com/{REPO}/main'
API_BASE = f'https://api.github.com/repos/{REPO}/contents'

st.set_page_config(
    page_title='Capovilla Analytics',
    page_icon='▶️',
    layout='wide',
    initial_sidebar_state='collapsed'
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Outfit:wght@200;300;400;500;600;700&display=swap');

:root {
    --bg: #0a0a0b;
    --surface: #111113;
    --surface-2: #18181b;
    --surface-3: #1f1f23;
    --border: #27272a;
    --border-light: #3f3f46;
    --text: #fafafa;
    --text-2: #a1a1aa;
    --text-3: #71717a;
    --accent: #22d3ee;
    --accent-dim: rgba(34,211,238,0.12);
    --accent-glow: rgba(34,211,238,0.25);
    --green: #4ade80;
    --green-dim: rgba(74,222,128,0.12);
    --yellow: #facc15;
    --yellow-dim: rgba(250,204,21,0.12);
    --red: #f87171;
    --red-dim: rgba(248,113,113,0.12);
    --font-display: 'Outfit', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    --ease: cubic-bezier(0.16,1,0.3,1);
    --radius: 12px;
}

html, body, [class*="css"] {
    font-family: var(--font-display) !important;
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--bg) !important; }
.block-container { padding: 1.5rem 2.5rem 3rem !important; }

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-radius: 10px !important;
    padding: 3px !important;
    gap: 2px !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px !important;
    color: var(--text-3) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    font-family: var(--font-display) !important;
    padding: 7px 18px !important;
    letter-spacing: 0.01em !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text-2) !important; }
.stTabs [aria-selected="true"] {
    background: var(--surface-3) !important;
    color: var(--text) !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.4) !important;
}

/* ── INPUTS ── */
div[data-testid="stTextArea"] textarea,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
    font-family: var(--font-display) !important;
    font-size: 0.85rem !important;
}
div[data-testid="stTextArea"] textarea:focus,
div[data-testid="stTextInput"] input:focus { border-color: var(--accent) !important; }
div[data-testid="stSelectbox"] > div,
div[data-baseweb="select"] > div {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

/* ── BOTÕES ── */
div[data-testid="stButton"] > button {
    background: var(--accent-dim) !important;
    color: var(--accent) !important;
    font-weight: 600 !important;
    border: 1px solid rgba(34,211,238,0.25) !important;
    border-radius: 8px !important;
    font-family: var(--font-display) !important;
    font-size: 0.82rem !important;
    transition: all 0.3s var(--ease) !important;
    letter-spacing: 0.01em !important;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(34,211,238,0.2) !important;
    transform: translateY(-1px) !important;
}

/* ── METRIC ── */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    transition: background 0.3s;
}
[data-testid="stMetric"]:hover { background: var(--surface-2); }
[data-testid="stMetricLabel"] p {
    color: var(--text-3) !important;
    font-size: 0.65rem !important;
    font-family: var(--font-mono) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-size: 1.8rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.03em !important;
}
[data-testid="stMetricDelta"] { font-size: 0.7rem !important; font-family: var(--font-mono) !important; }

/* ── EXPANDER ── */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}

/* ── DIVIDER ── */
hr { border-color: var(--border) !important; margin: 1rem 0 !important; }

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] { border-radius: 10px; }

/* ── ALERTS ── */
[data-testid="stAlert"] { border-radius: 8px; font-family: var(--font-display) !important; }

/* ── PROGRESS ── */
[data-testid="stProgressBar"] > div { background: var(--accent) !important; }

/* ── CAPTION ── */
[data-testid="stCaptionContainer"] p {
    color: var(--text-3) !important;
    font-size: 0.65rem !important;
    font-family: var(--font-mono) !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    font-weight: 500 !important;
}

/* ── SIDEBAR HIDE ── */
[data-testid="collapsedControl"] { display: none; }

/* ── METRIC GRID ── */
.metrics-grid {
    display: grid;
    gap: 1px;
    background: var(--border);
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 24px;
}
.metric-card {
    background: var(--surface);
    padding: 24px 22px;
    position: relative;
    transition: background 0.3s;
}
.metric-card:hover { background: var(--surface-2); }
.metric-label {
    font-size: 0.65rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    margin-bottom: 12px;
    font-family: var(--font-mono);
}
.metric-value {
    font-size: 1.9rem;
    font-weight: 600;
    letter-spacing: -0.03em;
    line-height: 1;
    margin-bottom: 8px;
    color: var(--text);
}
.metric-trend {
    font-size: 0.68rem;
    font-family: var(--font-mono);
    font-weight: 400;
}
.trend-up   { color: var(--green); }
.trend-down { color: var(--red); }
.trend-flat { color: var(--yellow); }

/* ── HEALTH / FUNIL ── */
.health-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 24px;
}
.health-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}
.health-title {
    font-size: 0.65rem;
    font-family: var(--font-mono);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
}
.health-status {
    font-size: 0.65rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 100px;
    font-family: var(--font-mono);
}
.health-status.green { background: var(--green-dim); color: var(--green); }
.health-status.yellow { background: var(--yellow-dim); color: var(--yellow); }
.health-status.red { background: var(--red-dim); color: var(--red); }
.health-bar-track {
    height: 4px;
    background: var(--surface-3);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 16px;
}
.health-bar-fill { height: 100%; border-radius: 4px; transition: width 1s var(--ease); }
.health-indicators { display: grid; gap: 16px; }
.health-indicator { display: flex; flex-direction: column; gap: 4px; }
.health-indicator-label {
    font-size: 0.62rem;
    color: var(--text-3);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.health-indicator-value { font-size: 0.85rem; font-weight: 600; }

/* ── ALERT CARD ── */
.alert-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 12px;
    padding: 20px 24px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 24px;
}
.alert-icon {
    width: 34px;
    height: 34px;
    background: var(--accent-dim);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: var(--accent);
    font-size: 1rem;
}
.alert-content h3 { font-size: 0.88rem; font-weight: 600; margin-bottom: 4px; color: var(--text); }
.alert-content p { font-size: 0.78rem; color: var(--text-2); line-height: 1.5; font-weight: 300; }
.alert-tag {
    font-size: 0.6rem;
    font-family: var(--font-mono);
    padding: 3px 8px;
    border-radius: 4px;
    background: var(--accent-dim);
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 6px;
    display: inline-block;
}

/* ── SUGGESTION CARD ── */
.suggestion-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.suggestion-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.5;
}
.suggestion-badge {
    font-size: 0.6rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--accent);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.suggestion-badge::before {
    content: '';
    width: 5px; height: 5px;
    background: var(--accent);
    border-radius: 50%;
    flex-shrink: 0;
}
.suggestion-title {
    font-size: 1.25rem;
    font-weight: 600;
    line-height: 1.3;
    letter-spacing: -0.02em;
    margin-bottom: 10px;
    color: var(--text);
}
.suggestion-meta {
    display: flex;
    gap: 20px;
    margin-bottom: 18px;
    flex-wrap: wrap;
}
.meta-item { display: flex; flex-direction: column; gap: 3px; }
.meta-label {
    font-size: 0.6rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-3);
}
.meta-value { font-size: 0.95rem; font-weight: 600; color: var(--text); }
.meta-value.highlight { color: var(--green); }
.suggestion-hook {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 16px;
}
.hook-label {
    font-size: 0.6rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-3);
    margin-bottom: 6px;
}
.hook-text { font-size: 0.88rem; line-height: 1.5; color: var(--text); font-style: italic; }
.suggestion-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.68rem;
    font-family: var(--font-mono);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 500;
}
.pill-green { background: var(--green-dim); color: var(--green); }
.pill-cyan  { background: var(--accent-dim); color: var(--accent); }
.pill-yellow{ background: var(--yellow-dim); color: var(--yellow); }

/* ── KANBAN ── */
.kanban-section {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1px;
    background: var(--border);
    border-radius: 16px;
    overflow: hidden;
}
.kanban-col {
    background: var(--surface);
    padding: 18px;
    min-height: 180px;
}
.kanban-col-header {
    font-size: 0.62rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.kanban-col-header .count {
    background: var(--surface-3);
    padding: 1px 7px;
    border-radius: 4px;
    font-size: 0.58rem;
}
.kanban-card {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    transition: border-color 0.2s var(--ease);
}
.kanban-card:hover { border-color: var(--border-light); }
.kanban-card-title { font-size: 0.8rem; font-weight: 500; margin-bottom: 5px; line-height: 1.3; color: var(--text); }
.kanban-card-meta {
    font-size: 0.63rem;
    color: var(--text-3);
    font-family: var(--font-mono);
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

/* ── LINK TABLE / VÍDEOS ── */
.link-table {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    margin-bottom: 24px;
}
.link-table-header {
    padding: 18px 24px 12px;
    font-size: 0.65rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
}
.link-row {
    display: grid;
    padding: 12px 24px;
    border-top: 1px solid var(--border);
    align-items: center;
    transition: background 0.2s;
    gap: 12px;
}
.link-row:hover { background: var(--surface-2); }
.link-video { font-size: 0.82rem; font-weight: 500; color: var(--text); }
.link-rpm { font-size: 0.8rem; font-family: var(--font-mono); font-weight: 600; text-align: right; }

/* ── PATTERN ITEM ── */
.pattern-item {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: border-color 0.3s;
}
.pattern-item:hover { border-color: var(--border-light); }
.pattern-text { font-size: 0.82rem; line-height: 1.5; color: var(--text); margin-bottom: 5px; }
.pattern-evidence { font-size: 0.63rem; color: var(--text-3); font-family: var(--font-mono); }

/* ── GOAL ROW ── */
.goal-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
}
.goal-section-title {
    font-size: 0.65rem;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    margin-bottom: 20px;
}
.goal-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
}
.goal-row:last-child { border-bottom: none; }
.goal-name { font-size: 0.82rem; font-weight: 500; width: 160px; flex-shrink: 0; color: var(--text); }
.goal-bar-track { flex: 1; height: 5px; background: var(--surface-3); border-radius: 4px; overflow: hidden; }
.goal-bar-fill { height: 100%; border-radius: 4px; transition: width 1.2s var(--ease); }
.goal-numbers { font-size: 0.7rem; font-family: var(--font-mono); color: var(--text-2); width: 110px; text-align: right; flex-shrink: 0; }
.goal-projection { font-size: 0.6rem; color: var(--text-3); font-family: var(--font-mono); width: 90px; text-align: right; flex-shrink: 0; }

/* ── BOX / FUNIL (dashboard capovilla) ── */
.box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
}
.box-title {
    font-size: 0.6rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-3);
    margin-bottom: 14px;
}
.funil-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
}
.funil-label {
    font-size: 0.68rem;
    width: 50px;
    color: var(--text-2);
    text-transform: uppercase;
}
.funil-bar-track {
    flex: 1;
    height: 6px;
    background: var(--surface-3);
    border-radius: 3px;
    overflow: hidden;
}
.funil-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 1s var(--ease);
}
.funil-nums {
    font-size: 0.62rem;
    color: var(--text-3);
    min-width: 100px;
    text-align: right;
    white-space: nowrap;
    font-family: var(--font-mono);
}

/* ── VID CARD (legacy) ── */
.vid-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 8px;
    transition: border-color 0.2s;
}
.vid-card:hover { border-color: var(--border-light); }

/* ── COMP PILL ── */
.comp-pill {
    display: inline-block;
    background: var(--accent-dim);
    color: var(--accent);
    font-size: 0.62rem;
    padding: 2px 8px;
    border-radius: 4px;
    margin-top: 4px;
    font-family: var(--font-mono);
}

/* ── SCREEN HEADER ── */
.screen-header { margin-bottom: 28px; }
.screen-header h1 {
    font-size: 1.5rem;
    font-weight: 300;
    letter-spacing: -0.02em;
    color: var(--text);
    line-height: 1.2;
    margin: 0 0 6px;
}
.screen-header p { font-size: 0.8rem; color: var(--text-3); font-weight: 300; margin: 0; }

/* ── NAV DOT (pulsante) ── */
@keyframes pulse-dot {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34,211,238,0.4); }
    50%       { opacity: 0.7; box-shadow: 0 0 0 5px transparent; }
}
.nav-dot {
    display: inline-block;
    width: 7px; height: 7px;
    background: var(--accent);
    border-radius: 50%;
    animation: pulse-dot 2s ease-in-out infinite;
    vertical-align: middle;
    margin-right: 8px;
}
.nav-logo-text {
    font-family: var(--font-mono) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    color: var(--accent) !important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════
# FUNÇÕES DE DADOS
# ══════════════════════════════════════

@st.cache_data(ttl=300)
def carregar_dados():
    txt = fetch_raw_text_or(REPO, 'dados.txt', '')
    return txt if txt else None


@st.cache_data(ttl=60)
def carregar_arquivo(filename, default):
    if filename.endswith('.json'):
        return fetch_raw_json_or(REPO, filename, default)
    return fetch_raw_text_or(REPO, filename, default)


APRENDIZADOS_CREATOR_FILE = 'aprendizados_criador.json'
APRENDIZADOS_MAX_ENTRIES = 200
APRENDIZADOS_MAX_PROMPT_CHARS = 6000


def _normalize_title_match(s: str) -> str:
    if not s:
        return ''
    t = s.lower().strip()
    for ch in '\n\r\t':
        t = t.replace(ch, ' ')
    return ' '.join(t.split())


def _find_historico_video_match(historico: list, fila_item: dict):
    """Find matching historico row for a fila item (video_id first, then title)."""
    if not isinstance(fila_item, dict):
        return None
    video_id = (fila_item.get('video_id_youtube') or '').strip()
    if video_id:
        for h in historico:
            if not isinstance(h, dict):
                continue
            if (h.get('video_id') or '').strip() == video_id:
                return h
    titulo_pub = (fila_item.get('titulo_publicado') or fila_item.get('titulo_planejado') or '').strip()
    if titulo_pub:
        tn = _normalize_title_match(titulo_pub)
        if tn:
            for h in historico:
                if not isinstance(h, dict):
                    continue
                if _normalize_title_match(h.get('titulo', '')) == tn:
                    return h
    return None


def _format_aprendizados_para_prompt(entries: list) -> str:
    if not entries:
        return ''
    lines = []
    for e in entries[-25:]:
        if not isinstance(e, dict):
            continue
        data = e.get('data', '')[:16]
        tit = (e.get('titulo_publicado') or e.get('titulo_planejado') or '')[:80]
        notas = (e.get('notas') or '')[:1200]
        sid = e.get('sugestao_id') or ''
        if not notas:
            continue
        lines.append(f'[{data}] {tit}' + (f' (sugestão_id: {sid})' if sid else ''))
        lines.append(notas)
        if e.get('analise_ia'):
            lines.append('— Resumo IA: ' + str(e['analise_ia'])[:400])
        lines.append('')
    out = '\n'.join(lines).strip()
    if len(out) > APRENDIZADOS_MAX_PROMPT_CHARS:
        out = out[-APRENDIZADOS_MAX_PROMPT_CHARS:]
    return out


def contexto_com_aprendizados(contexto_base: str) -> str:
    """contexto.txt + últimas notas manuais (vínculos) para injetar nos prompts Claude."""
    raw = carregar_arquivo(APRENDIZADOS_CREATOR_FILE, [])
    entries = raw if isinstance(raw, list) else []
    bloco = _format_aprendizados_para_prompt(entries)
    base = (contexto_base or '').strip()
    marker = '--- NOTAS MANUAIS DO CRIADOR'
    if marker in base:
        base = base.split(marker, 1)[0].strip()
    if not bloco:
        return base
    return base + '\n\n--- NOTAS MANUAIS DO CRIADOR (intenção / vínculos) ---\n' + bloco


def salvar_github(filename, content):
    if not GITHUB_TOKEN:
        st.error('GITHUB_TOKEN não configurado nos secrets.')
        return False
    return put_repository_file(
        REPO,
        GITHUB_TOKEN,
        filename,
        content,
        message=f'Atualização {filename} {datetime.now().strftime("%d/%m/%Y %H:%M")}',
    )


def atualizar_secret_github(secret_name, secret_value):
    """Atualiza um secret no GitHub Actions via API."""
    # Buscar public key do repositório para encriptar o secret
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    r = requests.get(
        f'https://api.github.com/repos/{REPO}/actions/secrets/public-key',
        headers=headers, timeout=10
    )
    if r.status_code != 200:
        return False, f'Erro ao buscar chave pública: {r.status_code}'

    key_data = r.json()
    key_id = key_data['key_id']
    public_key = key_data['key']

    # Encriptar o secret com a chave pública (usando PyNaCl)
    try:
        from base64 import b64decode, b64encode
        from nacl import encoding, public as nacl_public

        public_key_bytes = b64decode(public_key)
        sealed_box = nacl_public.SealedBox(nacl_public.PublicKey(public_key_bytes))
        encrypted = sealed_box.encrypt(secret_value.encode('utf-8'))
        encrypted_b64 = b64encode(encrypted).decode('utf-8')
    except ImportError:
        return False, 'PyNaCl não instalado — instale com: pip install PyNaCl'
    except Exception as e:
        return False, f'Erro ao encriptar: {e}'

    # Atualizar o secret
    r2 = requests.put(
        f'https://api.github.com/repos/{REPO}/actions/secrets/{secret_name}',
        headers=headers,
        json={'encrypted_value': encrypted_b64, 'key_id': key_id},
        timeout=10
    )
    if r2.status_code in (201, 204):
        return True, 'Secret atualizado com sucesso!'
    return False, f'Erro ao atualizar secret: {r2.status_code} — {r2.text[:100]}'


def renovar_token_google():
    """
    Interface de renovação do token Google OAuth no Streamlit.
    Gera URL de autorização → usuário autoriza → cola o código → salva token.json no GitHub.
    """
    CLIENT_ID     = st.secrets.get('GOOGLE_CLIENT_ID', '')
    CLIENT_SECRET = st.secrets.get('GOOGLE_CLIENT_SECRET', '')

    SCOPES = [
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/yt-analytics.readonly',
        'https://www.googleapis.com/auth/yt-analytics-monetary.readonly',
    ]
    REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'  # modo offline — retorna código na tela

    if not CLIENT_ID or not CLIENT_SECRET:
        st.error('❌ GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET precisam estar nos Secrets do Streamlit.')
        st.info('Você encontra esses valores no Google Cloud Console → APIs e serviços → Credenciais → seu OAuth 2.0 Client → copiar Client ID e Client Secret.')
        return

    # Gerar URL de autorização
    import urllib.parse
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',  # força geração de refresh_token
    }
    auth_url = 'https://accounts.google.com/o/oauth2/auth?' + urllib.parse.urlencode(params)

    st.markdown('### Passo 1 — Autorizar acesso ao Google')
    st.markdown('Clique no link abaixo para autorizar. O Google vai mostrar um código na tela.')
    st.markdown(f'[🔗 Clique aqui para autorizar]({auth_url})', unsafe_allow_html=False)
    st.code(auth_url, language=None)

    st.divider()
    st.markdown('### Passo 2 — Cole o código aqui')
    codigo = st.text_input('Código de autorização (aparece na tela após autorizar):',
                           placeholder='4/0AX4XfWi...')

    if st.button('🔄 Gerar novo token e salvar', use_container_width=True, disabled=not codigo.strip()):
        with st.spinner('Trocando código por token...'):
            # Trocar código por tokens
            r = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': codigo.strip(),
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'redirect_uri': REDIRECT_URI,
                    'grant_type': 'authorization_code',
                },
                timeout=15
            )

            if r.status_code != 200:
                st.error(f'❌ Erro ao trocar código: {r.text[:200]}')
                return

            token_data = r.json()

            if 'refresh_token' not in token_data:
                st.error('❌ Token sem refresh_token. Tente de novo — pode ser que o acesso já esteja autorizado. Revogue o acesso em myaccount.google.com/permissions e tente novamente.')
                return

            # Montar token.json no formato que o Google Auth espera
            token_json = {
                'token': token_data.get('access_token', ''),
                'refresh_token': token_data.get('refresh_token', ''),
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'scopes': SCOPES,
                'expiry': None
            }
            token_str = json.dumps(token_json, indent=2)

        with st.spinner('Atualizando secret GOOGLE_TOKEN_JSON no GitHub Actions...'):
            ok, msg = atualizar_secret_github('GOOGLE_TOKEN_JSON', token_str)
            if ok:
                st.success('✅ Token renovado e salvo no GitHub Actions! O workflow vai funcionar normalmente agora.')
                st.balloons()
                st.caption('Próximo passo: rode o workflow manualmente no GitHub Actions para confirmar.')
            else:
                st.error(f'❌ {msg}')
                st.info('Alternativa: copie o token abaixo e cole manualmente no Secret GOOGLE_TOKEN_JSON do GitHub Actions.')
                st.code(token_str, language='json')

def claude_api(prompt, max_tokens=2000, web_search=False):
    """Chamada centralizada à API do Claude com ou sem web search."""
    body = {
        'model': 'claude-opus-4-5',
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    if web_search:
        body['tools'] = [{"type": "web_search_20250305", "name": "web_search"}]
    return post_messages(
        CLAUDE_API_KEY, body, timeout=120, http_error_detail=True
    )


def claude_api_sonnet(prompt, max_tokens=1500):
    """Versão econômica do Claude API usando Sonnet — para resumos de concorrentes."""
    return post_messages(
        CLAUDE_API_KEY,
        {
            'model': 'claude-sonnet-4-6',
            'max_tokens': max_tokens,
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=60,
        http_error_detail=False,
    )


def resumir_transcricao_concorrente(titulo, descricao, transcricao):
    """Gera análise cirúrgica completa de um vídeo de concorrente via Sonnet."""
    conteudo = f"Título: {titulo}\nDescrição: {descricao[:400]}"
    if transcricao:
        conteudo += f"\n\nTranscrição completa:\n{transcricao}"

    prompt = f"""Você é um analista cirúrgico de conteúdo do YouTube especializado no mercado brasileiro de games e tecnologia.

Analise este vídeo com profundidade máxima baseando-se na transcrição completa:

{conteudo}

Produza uma análise detalhada com os seguintes campos. Cite palavras e momentos reais da transcrição:

**TOM E LINGUAGEM**
Vocabulário específico, nível de formalidade, ritmo da fala, uso de humor ou ironia, grau de intimidade. Cite frases reais. Que emoção domina?

**GANCHO DE ABERTURA**
O que o criador diz nos primeiros 30 segundos. Por que funciona ou não como gancho. Qual promessa ou tensão cria.

**JORNADA NARRATIVA**
Mapeie os blocos em ordem: como cada seção se conecta, qual é o fio condutor emocional, onde acelera e desacelera.

**GATILHOS EMOCIONAIS**
Quais gatilhos aparecem: nostalgia, medo de perder, pertencimento, culpa, merecimento, status, economia. Onde exatamente na transcrição.

**OBJETIVO E CTA**
O que quer que o espectador faça ao terminar. Como converte — link, produto, inscrição. Explícito ou subliminar?

**PONTOS FORTES**
O que funciona excepcionalmente bem — cite momentos específicos.

**LACUNAS E OPORTUNIDADES**
O que o público quer saber mas não foi respondido. Que ângulo emocional ficou inexplorado.

**MODELO REPLICÁVEL**
Esqueleto narrativo: gancho → desenvolvimento → virada → fechamento.

Máximo 80 palavras por campo. Responda em português brasileiro."""

    texto, _ = claude_api_sonnet(prompt, max_tokens=1500)
    return texto or ''


def varrer_concorrente_novo(nome, handle, youtube_api_key=None):
    """
    Quando um novo concorrente é adicionado pelo app:
    - Busca os 10 vídeos mais recentes via YouTube Data API
    - Coleta transcrições via Apify
    - Gera resumo cirúrgico de cada um via Claude Sonnet
    Retorna lista de videos_recentes já com resumos.
    """
    YT_API_KEY = st.secrets.get('YOUTUBE_API_KEY', '') or os.environ.get('YOUTUBE_API_KEY', '')
    APIFY_KEY  = st.secrets.get('APIFY_API_KEY', '') or os.environ.get('APIFY_API_KEY', '')

    if not YT_API_KEY:
        return []

    try:
        handle_limpo = handle.replace('@', '')

        # Buscar channel_id
        r = requests.get(
            'https://www.googleapis.com/youtube/v3/search',
            params={'part': 'snippet', 'q': handle_limpo, 'type': 'channel',
                    'maxResults': 1, 'key': YT_API_KEY},
            timeout=10
        )
        if r.status_code != 200 or not r.json().get('items'):
            return []

        channel_id = r.json()['items'][0]['snippet']['channelId']

        # Buscar 10 vídeos mais recentes
        r2 = requests.get(
            'https://www.googleapis.com/youtube/v3/search',
            params={'part': 'snippet', 'channelId': channel_id, 'type': 'video',
                    'order': 'date', 'maxResults': 10, 'key': YT_API_KEY},
            timeout=10
        )
        if r2.status_code != 200:
            return []

        video_ids = [i['id']['videoId'] for i in r2.json().get('items', [])]
        if not video_ids:
            return []

        # Buscar estatísticas
        r3 = requests.get(
            'https://www.googleapis.com/youtube/v3/videos',
            params={'part': 'statistics,snippet', 'id': ','.join(video_ids), 'key': YT_API_KEY},
            timeout=10
        )
        if r3.status_code != 200:
            return []

        videos = []
        for v in r3.json().get('items', []):
            s = v['statistics']
            views = int(s.get('viewCount', 0))
            likes = int(s.get('likeCount', 0))
            videos.append({
                'id': v['id'],
                'titulo': v['snippet']['title'],
                'descricao': v['snippet'].get('description', '')[:400],
                'views': views,
                'likes': likes,
                'comentarios': int(s.get('commentCount', 0)),
                'publicado': v['snippet'].get('publishedAt', '')[:10],
                'engajamento': round((likes / views * 100), 2) if views > 0 else 0,
                'transcricao': '',
                'resumo_ia': ''
            })

        # Transcrições via Apify (10 vídeos, com delay)
        if APIFY_KEY:
            import time
            for v in videos:
                url = (f'https://api.apify.com/v2/acts/karamelo~youtube-transcripts'
                       f'/run-sync-get-dataset-items?token={APIFY_KEY}')
                try:
                    resp = requests.post(
                        url,
                        headers={'Content-Type': 'application/json'},
                        json={'urls': [f'https://www.youtube.com/watch?v={v["id"]}'], 'language': 'pt'},
                        timeout=90
                    )
                    if resp.status_code in (200, 201):
                        dados = resp.json()
                        if dados and isinstance(dados, list):
                            item = dados[0]
                            transcript = (item.get('transcript') or item.get('text') or
                                         item.get('content') or item.get('captions') or '')
                            if isinstance(transcript, list):
                                texto = ' '.join([t.get('text', '') if isinstance(t, dict) else str(t) for t in transcript])
                            else:
                                texto = str(transcript)
                            texto = texto.replace('\n', ' ').strip()
                            if texto and len(texto) > 20:
                                v['transcricao'] = texto
                except:
                    pass
                time.sleep(3)

        # Resumo cirúrgico via Claude Sonnet para cada vídeo com transcrição
        for v in videos:
            if v.get('transcricao') or v.get('descricao'):
                resumo = resumir_transcricao_concorrente(
                    v['titulo'], v.get('descricao', ''), v.get('transcricao', '')
                )
                v['resumo_ia'] = resumo
                v['transcricao'] = ''  # descartar transcrição bruta

        return videos

    except Exception as e:
        st.warning(f'Varredura automática falhou: {e}')
        return []


def analisar_concorrente(nome, handle):
    prompt = f"""Canal YouTube: {nome} ({handle}).
Responda APENAS com JSON válido, sem texto adicional:
{{"temas_comuns": ["tema1", "tema2", "tema3"], "pontos_fortes": "frase curta", "lacuna_emocional": "o que não explora"}}"""
    texto, erro = claude_api(prompt, max_tokens=300)
    if texto:
        import re
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            try: return json.loads(match.group())
            except: pass
    return {}


def gerar_sugestoes(dados_texto, contexto, historico, concorrentes):
    """Gera sugestões usando dados reais + transcrições + funil editorial."""

    # Histórico resumido
    hist = ''
    if historico:
        acertos = [h for h in historico if h.get('resultado') == 'acima_do_esperado']
        hist = f"\nHistórico: {len(historico)} vídeos, {len(acertos)} acima do esperado."
        for h in historico[-5:]:
            if h.get('rpm_real'):
                hist += f"\n- '{h['titulo'][:45]}' → RPM real R${h['rpm_real']:.2f} (previsto R${h.get('rpm_previsto',0):.2f}) [{h.get('origem','—')}]"

    # Padrões automáticos da Fase C
    padroes = carregar_arquivo('padroes.txt', '')
    padroes_secao = f"\nPADRÕES AUTOMÁTICOS DEDUZIDOS DO HISTÓRICO:\n{padroes}" if padroes else ''

    # Meu estilo narrativo — resumo estruturado gerado a partir da transcrição completa
    transcricoes_canal = carregar_arquivo('transcricoes_canal.json', [])
    meu_estilo = ''
    if transcricoes_canal:
        meu_estilo = '\nMEU ESTILO NARRATIVO (análise dos meus vídeos a partir da transcrição completa):\n'
        for t in transcricoes_canal[:3]:
            if t.get('resumo_ia'):
                meu_estilo += f"\nVídeo: {t['titulo'][:60]}\n"
                meu_estilo += f"{t['resumo_ia']}\n"

    # Dados reais dos concorrentes — resumos estruturados gerados da transcrição completa
    comps_texto = ''
    if concorrentes:
        for c in concorrentes:
            videos = c.get('videos_recentes', [])
            if not videos:
                comps_texto += f"\n**{c['nome']}** ({c.get('handle','')}) — sem dados ainda\n"
                continue
            comps_texto += f"\n**{c['nome']}** ({c.get('handle','')}) — {c.get('pais','')}\n"
            comps_texto += f"Lacuna identificada: {c.get('lacuna','—')}\n"
            comps_texto += "Vídeos recentes sobre games:\n"
            for v in videos[:4]:
                eng = v.get('engajamento', 0)
                comps_texto += (
                    f"\n  • {v['titulo'][:65]} | "
                    f"Views: {v.get('views',0):,} | "
                    f"Engajamento: {eng}%\n"
                )
                # Resumo estruturado completo — gerado da transcrição inteira
                if v.get('resumo_ia'):
                    comps_texto += f"{v['resumo_ia']}\n"
    else:
        comps_texto = 'Nenhum concorrente cadastrado ainda.'

    # Funil editorial — lacuna identificada automaticamente
    funil = carregar_arquivo('funil.json', {})
    lacuna_funil = funil.get('lacuna', '')
    lacuna_desc = funil.get('lacuna_descricao', '')
    topo_c = funil.get('topo_count', 0)
    meio_c = funil.get('meio_count', 0)
    fundo_c = funil.get('fundo_count', 0)
    funil_secao = ''
    if funil and funil.get('total_videos', 0) > 0:
        funil_secao = f"""
FUNIL EDITORIAL ATUAL (baseado em dados reais de RPM):
- Topo (atração): {topo_c} vídeos | RPM médio R${funil.get('topo_rpm_medio', 0):.0f} | Receita R${funil.get('topo_receita_total', 0):.0f}
- Meio (consideração): {meio_c} vídeos | RPM médio R${funil.get('meio_rpm_medio', 0):.0f} | Receita R${funil.get('meio_receita_total', 0):.0f}
- Fundo (conversão): {fundo_c} vídeos | RPM médio R${funil.get('fundo_rpm_medio', 0):.0f} | Receita R${funil.get('fundo_receita_total', 0):.0f}
LACUNA IDENTIFICADA: {lacuna_desc}
PRÓXIMO VÍDEO DEVE SER DE: {lacuna_funil.upper() if lacuna_funil != 'nenhuma' else 'qualquer etapa'}"""

    prompt = f"""Você é o sistema de curadoria do canal Guilherme Capovilla (@guilhermecapovilla).

IDENTIDADE DO CANAL:
- Canal brasileiro de videogames — consoles desbloqueados, lifestyle gamer
- Público: adulto brasileiro (25-45 anos) que sente culpa de gastar com videogame mas merece
- Monetização principal: afiliado Shopee + AdSense
- Diferencial: NÃO é técnico — é emocional, de identificação, nostalgia e desejo
- Tom: vida adulta, merecimento, nostalgia (lan house, locadora), leveza
- Linguagem: "destravado", "zerou", "jogar demais", "se mereça"

DADOS REAIS DO CANAL (últimos 28 dias):
{dados_texto[:2000]}

APRENDIZADOS DO CRIADOR:
{contexto}
{hist}
{padroes_secao}

{meu_estilo}

DADOS REAIS DOS CONCORRENTES (coletados automaticamente hoje):
{comps_texto}

{funil_secao}

INSTRUÇÕES:
1. Leia o funil editorial — identifique qual etapa está com lacuna
2. As sugestões DEVEM preencher a lacuna do funil — se o canal precisa de vídeo de MEIO, sugira meio
3. Analise as transcrições dos concorrentes para identificar ângulos não explorados
4. Cruze com RPM histórico — Switch Lite destravado tem RPM absurdamente alto

Sugira EXATAMENTE 2 temas. Para cada:

**SUGESTÃO X — [Título emocional em português brasileiro]**
- Etapa do funil: [TOPO / MEIO / FUNDO] — por que esse vídeo pertence a essa etapa
- Score: X/100 (RPM histórico 30% + lacuna do funil 25% + engajamento concorrência 25% + afiliado Shopee 20%)
- RPM esperado: R$ X
- Afiliado Shopee: produto específico disponível no Brasil
- Concorrente referência: [nome] fez [título] — você faria com [ângulo emocional diferente]
- Por que agora: [dado real do funil] + [o que as transcrições mostraram]
- Thumbnail: [o que aparece] + [texto em destaque] + [emoção]
- Abertura sugerida: [primeira frase — o gancho emocional]

Pelo menos 1 sugestão deve ser da etapa com lacuna identificada no funil.

CRITÉRIO QUANDO FUNIL EQUILIBRADO:
Se o funil estiver equilibrado (sem lacuna crítica), priorize sempre FUNDO de funil —
vídeos de conversão geram RPM absurdamente maior no seu canal (R$307 vs R$4).
A exceção é se o canal precisar de crescimento de inscritos — aí priorize TOPO.
Nunca sugira dois vídeos da mesma etapa.

Só sugira score acima de 60. Seja cirúrgico."""

    texto, erro = claude_api(prompt, max_tokens=3000, web_search=False)
    return texto or erro


def sugerir_tema_similar(titulo_video, rpm, dados_texto, contexto):
    """Sugere um tema similar a um vídeo que performou bem."""
    prompt = f"""Canal Guilherme Capovilla (@guilhermecapovilla).

O vídeo "{titulo_video}" teve RPM de R${rpm:.2f} — um resultado {'excelente' if rpm > 100 else 'bom' if rpm > 20 else 'moderado'}.

DADOS DO CANAL:
{dados_texto[:1500]}

CONTEXTO:
{contexto[:400]}

Com base no que funcionou nesse vídeo, sugira 1 tema similar que:
- Aproveite o mesmo público e intenção de compra
- Tenha ângulo emocional diferente (não repita o mesmo vídeo)
- Mantenha potencial de RPM alto

Responda com:
**Título sugerido:** [título emocional]
**Por que funciona:** [2 frases]
**Diferencial:** [o que muda em relação ao original]
**Afiliado:** [produto Shopee]"""

    texto, erro = claude_api(prompt, max_tokens=500)
    return texto or erro


def gerar_script(tema, dados_texto, contexto):
    prompt = f"""Roteirista do canal Guilherme Capovilla.

TEMA: {tema}
CONTEXTO: {contexto[:500]}

Script completo:
- Abertura emocional com gancho forte (0:00–0:45)
- Bloco 1: nostalgia / contexto de vida adulta (0:45–3:00)
- Bloco 2: conteúdo principal com afiliado Shopee inserido naturalmente
- Bloco 3: virada emocional — a grande sacada
- Fechamento suave com CTA

Tom: adulto que merece se divertir mas sente culpa. Não técnico. Emocional."""
    texto, erro = claude_api(prompt, max_tokens=2500)
    return texto or erro




def analisar_aprendizado_sugestao(sugestao_texto, titulo_publicado, rpm_real, rpm_previsto):
    """
    Claude analisa o que acertou e o que mudou entre a sugestão e o vídeo real.
    Gera relatório de aprendizado para calibrar próximas sugestões.
    """
    if not CLAUDE_API_KEY:
        return ''

    prompt = f"""Você é o sistema de aprendizado do canal Guilherme Capovilla.

SUGESTÃO ORIGINAL DO SISTEMA:
{sugestao_texto[:800]}

VÍDEO PUBLICADO:
Título: {titulo_publicado}
RPM real: R${rpm_real:.0f}
RPM previsto: R${rpm_previsto:.0f}
Resultado: {"ACERTOU ✅" if rpm_real >= rpm_previsto * 0.9 else "ERROU ❌" if rpm_real < rpm_previsto * 0.5 else "PARCIAL ➖"}

Analise e responda em português brasileiro com esses campos:

**O QUE O SISTEMA ACERTOU**
O que da sugestão original foi mantido e funcionou — console, ângulo emocional, etapa do funil, afiliado.

**O QUE VOCÊ MUDOU**
O que foi diferente do sugerido — título, ângulo, abordagem. Por que faz sentido essa mudança.

**APRENDIZADO PARA PRÓXIMAS SUGESTÕES**
O que o sistema deve calibrar: qual elemento gerou mais resultado, qual ajuste você fez que funcionou melhor que o sugerido.

**PADRÃO IDENTIFICADO**
Uma frase sobre o padrão de conteúdo que gera RPM alto no seu canal, baseado nesse resultado.

Seja específico e baseado nos dados reais."""

    texto, _ = claude_api(prompt, max_tokens=600)
    return texto or ''


def gerar_sugestao_semana(dados_texto, contexto, concorrentes, funil):
    """
    Gera UMA sugestão forte para esta semana.
    Salva em sugestao_semana.json para aparecer automaticamente na aba Vídeos.
    """
    lacuna = funil.get('lacuna', 'fundo') if funil else 'fundo'
    lacuna_desc = funil.get('lacuna_descricao', '') if funil else ''

    comps_texto = ''
    if concorrentes:
        for c in concorrentes[:3]:
            videos = c.get('videos_recentes', [])[:2]
            if videos:
                comps_texto += f"\n{c['nome']}: "
                for v in videos:
                    comps_texto += f"{v['titulo'][:50]} ({v.get('engajamento',0)}% eng) "
                    if v.get('resumo_ia'):
                        comps_texto += f"| {v['resumo_ia'][:100]}"

    prompt = f"""Você é o sistema de curadoria do canal Guilherme Capovilla (@guilhermecapovilla).

Canal brasileiro de videogames — consoles desbloqueados, lifestyle gamer adulto brasileiro.
Monetização: afiliado Shopee + AdSense. RPM Switch Lite destravado = R$295+ (10x acima de qualquer outro tema).

DADOS DO CANAL (28 dias):
{dados_texto[:1500]}

CONTEXTO EDITORIAL (inclui notas manuais do criador quando houver):
{contexto[:3500]}

FUNIL: lacuna em {lacuna.upper()} — {lacuna_desc}

CONCORRENTES RECENTES:
{comps_texto[:800]}

Sugira EXATAMENTE 1 vídeo para esta semana. O mais importante, mais rentável, mais oportuno agora.

Responda em JSON:
{{
  "titulo": "título emocional em português",
  "etapa_funil": "topo|meio|fundo",
  "rpm_esperado": 150,
  "motivo": "por que este vídeo agora — 2 frases diretas baseadas nos dados",
  "afiliado": "produto Shopee específico",
  "gancho": "primeira frase do vídeo",
  "score": 85
}}"""

    texto, _ = claude_api(prompt, max_tokens=400)
    if texto:
        import re
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {}


def gerar_sugestao_tema_livre(tema, dados_texto, contexto, funil, brief=''):
    """Gera sugestão específica para um tema que o usuário digitou — fiel ao tema, sem pivot forçado."""
    lacuna = funil.get('lacuna', 'fundo') if funil else 'fundo'
    lacuna_desc = (funil.get('lacuna_descricao', '') if funil else '') or ''
    brief = (brief or '').strip()
    brief_sec = ''
    if brief:
        brief_sec = f'\nENTREGA DESEJADA PELO CRIADOR (obrigatório respeitar):\n{brief[:2000]}\n'

    prompt = f"""Canal Guilherme Capovilla (@guilhermecapovilla) — videogames, consoles, lifestyle gamer adulto brasileiro.
Tom: emocional, nostalgia, merecimento; monetização com afiliado Shopee quando couber no tema.

REGRAS OBRIGATÓRIAS PARA ESTA TAREFA:
- O usuário definiu o TEMA abaixo. Título, gancho, ângulo do vídeo e produto de afiliado DEVEM ser diretamente sobre ESSE tema.
- É PROIBIDO mudar o foco para Nintendo Switch, Switch Lite ou outro console/tema que NÃO apareça explicitamente no "TEMA SOLICITADO" ou na "ENTREGA DESEJADA".
- Não sugira "o vídeo mais rentável do canal" nem substitua o tema pelo que historicamente monetiza mais.
- Use os dados do canal só para tom, formato e realismo de RPM esperado para ESTE tema — não para trocar o tema.

TEMA SOLICITADO: {tema}
{brief_sec}
DADOS DO CANAL (referência): {dados_texto[:900]}
CONTEXTO EDITORIAL + NOTAS DO CRIADOR: {contexto[:3500]}
FUNIL: lacuna sugerida em {lacuna.upper()} — {lacuna_desc}
(Ajuste etapa_funil se fizer sentido para o tema pedido, sem abandonar o tema.)

Gere UMA sugestão de vídeo sobre "{tema}". Responda APENAS em JSON válido:
{{
  "titulo": "título emocional em português",
  "etapa_funil": "topo|meio|fundo",
  "rpm_esperado": 80,
  "motivo": "por que este tema + este ângulo — 2 frases",
  "afiliado": "produto Shopee específico alinhado ao tema (não genérico de outro console)",
  "gancho": "primeira frase do vídeo",
  "score": 75
}}"""

    texto, _ = claude_api(prompt, max_tokens=450)
    if texto:
        import re
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {}


def funil_editorial_html(funil, box_id='funil-box-producao'):
    """
    Bloco HTML alinhado ao #funil-box do capovilla-dashboard.html.
    Barras por % de receita por etapa; se receita total = 0, usa % de contagem.
    """
    if not funil or funil.get('total_videos', 0) == 0:
        return None
    total_vids = int(funil.get('total_videos', 0))
    rec_topo = float(funil.get('topo_receita_total', 0) or 0)
    rec_meio = float(funil.get('meio_receita_total', 0) or 0)
    rec_fundo = float(funil.get('fundo_receita_total', 0) or 0)
    total_rec = rec_topo + rec_meio + rec_fundo
    topo_c = int(funil.get('topo_count', 0) or 0)
    meio_c = int(funil.get('meio_count', 0) or 0)
    fundo_c = int(funil.get('fundo_count', 0) or 0)
    total_count = max(topo_c + meio_c + fundo_c, 1)

    parts = [
        f'<div class="box" id="{html_escape(box_id, quote=True)}">',
        f'<div class="box-title">Funil editorial · {total_vids} vídeos</div>',
    ]
    stages = [
        ('Topo', topo_c, float(funil.get('topo_rpm_medio', 0) or 0), rec_topo, 'var(--red)'),
        ('Meio', meio_c, float(funil.get('meio_rpm_medio', 0) or 0), rec_meio, 'var(--yellow)'),
        ('Fundo', fundo_c, float(funil.get('fundo_rpm_medio', 0) or 0), rec_fundo, 'var(--green)'),
    ]
    for label, count, rpm_m, rec, color in stages:
        if total_rec > 0:
            pct = max((rec / total_rec) * 100, 2.0)
        else:
            pct = max((count / total_count) * 100, 2.0) if total_count else 2.0
        rec_i = int(round(rec))
        rpm_i = int(round(rpm_m))
        parts.append(
            '<div class="funil-row">'
            f'<span class="funil-label">{label}</span>'
            '<div class="funil-bar-track">'
            f'<div class="funil-bar-fill" style="width:{pct:.1f}%;background:{color}"></div>'
            '</div>'
            f'<span class="funil-nums">{count} vids · RPM R${rpm_i} · R${rec_i}</span>'
            '</div>'
        )
    lac_desc = funil.get('lacuna_descricao', '') or '—'
    parts.append(
        '<div style="margin-top:10px;font-size:0.62rem;color:var(--text-3)">'
        f'Lacuna: {html_escape(str(lac_desc))}</div>'
    )
    parts.append('</div>')

    lacuna = funil.get('lacuna', '')
    if lacuna and str(lacuna).lower() != 'nenhuma':
        desc = html_escape(str(funil.get('lacuna_descricao', '')))
        lac_u = html_escape(str(lacuna).upper())
        parts.append(
            '<div class="alert-card" style="margin-top:8px;">'
            '<div class="alert-icon">⚡</div>'
            '<div class="alert-content">'
            '<h3>Lacuna detectada</h3>'
            f'<p>{desc}</p>'
            f'<span class="alert-tag">próximo → {lac_u}</span>'
            '</div></div>'
        )
    return ''.join(parts)


def adicionar_sugestao_a_fila(sug_id, titulo, rpm_prev, funil_etapa=''):
    """Adiciona vídeo aprovado na fila de produção a partir de uma sugestão (ID rastreável)."""
    fila = carregar_arquivo('fila_producao.json', [])
    if any(f.get('sugestao_id') == sug_id for f in fila):
        return False
    fila.append({
        'sugestao_id': sug_id,
        'titulo_planejado': titulo,
        'titulo_publicado': None,
        'video_id_youtube': None,
        'rpm_previsto': rpm_prev,
        'funil': funil_etapa or 'topo',
        'status': 'planejado',
        'data_planejamento': datetime.now().strftime('%Y-%m-%d'),
        'data_publicacao': None,
        'origem': 'sugestao_pendente',
    })
    pendentes = carregar_arquivo('sugestoes_pendentes.json', [])
    for p in pendentes:
        if p.get('id') == sug_id:
            p['titulo_real'] = titulo
            p['status'] = 'em_producao'
    salvar_github('sugestoes_pendentes.json', pendentes)
    salvar_github('fila_producao.json', fila)
    return True


# ══════════════════════════════════════════════════════════════════════
# COMPONENT IMPORT
# ══════════════════════════════════════════════════════════════════════
from components.dashboard import render_dashboard

# ══════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════
dados_raw = carregar_dados()
dados_ok  = bool(dados_raw and dados_raw.strip() not in ['inicializando', '', 'null'])
_dados    = parsear_dados(dados_raw) if dados_ok else {}


# ══════════════════════════════════════════════════════════════════════
# DATA ADAPTERS — convert Python JSON formats to HTML component format
# ══════════════════════════════════════════════════════════════════════

def _funil_para_componente(funil_json: dict) -> dict:
    """funil.json {topo:[...], meio:[...], fundo:[...]} → {topo:{count,rpm_medio,receita}, …}"""
    out = {}
    total = 0
    for etapa in ('topo', 'meio', 'fundo'):
        videos = funil_json.get(etapa, [])
        if isinstance(videos, list):
            count   = len(videos)
            receita = sum(v.get('receita', 0) for v in videos)
            rpm_sum = sum(v.get('rpm', 0) for v in videos)
            rpm_med = rpm_sum / count if count else 0
        else:
            count = receita = rpm_med = 0
        out[etapa] = {'count': count, 'rpm_medio': round(rpm_med, 2), 'receita': round(receita, 2)}
        total += count
    lacuna_raw = funil_json.get('lacuna', funil_json.get('lacuna_descricao', ''))
    out['lacuna']           = lacuna_raw or 'nenhuma'
    out['lacuna_descricao'] = funil_json.get('lacuna_descricao', lacuna_raw or 'Funil equilibrado')
    out['total'] = total
    return out


def _fila_para_componente(fila_json: list, historico: list | None = None) -> list:
    """fila_producao.json items → HTML-compatible format"""
    result = []
    status_map = {'planejado': 'planejado', 'gravando': 'gravando',
                  'publicado': 'publicado', 'concluido': 'concluido'}
    hist = historico if isinstance(historico, list) else []
    for item in fila_json:
        titulo = item.get('titulo_publicado') or item.get('titulo_planejado', '')
        h_match = _find_historico_video_match(hist, item) if hist else None
        linked_sug_id = ''
        has_notas_criador = False
        if isinstance(h_match, dict):
            linked_sug_id = str(h_match.get('sugestao_id') or '').strip()
            has_notas_criador = bool(str(h_match.get('notas_criador') or '').strip())
        is_linked = bool(linked_sug_id or has_notas_criador)
        result.append({
            'id':       item.get('sugestao_id') or f'item-{len(result)+1}',
            'sugestao_id': item.get('sugestao_id'),
            'titulo':   titulo,
            'rpm':      item.get('rpm_previsto', 0),
            'funil':    item.get('funil', 'topo'),
            'status':   status_map.get(item.get('status', 'planejado'), 'planejado'),
            'origem':   item.get('origem', 'ideia_propria'),
            'data':     (item.get('data_publicacao') or item.get('data_planejamento', ''))[:10],
            'views':    item.get('views', 0),
            'video_id': item.get('video_id_youtube', ''),
            'is_linked_real': is_linked,
            'linked_sugestao_id': linked_sug_id,
        })
    return result


def _dados_para_componente(dados_parsed: dict) -> dict:
    """parsear_dados() output → HTML {canal, analytics28d, top_rpm, receita_diaria, receita_console}"""
    def _int(k):
        try: return int(str(dados_parsed.get(k, 0) or 0).replace(',', '').replace('.', '').split()[0])
        except: return 0
    def _float(k):
        try: return float(str(dados_parsed.get(k, 0) or 0).replace(',', '.').replace('R$', '').strip())
        except: return 0.0

    inscritos      = _int('Inscritos')
    views_totais   = _int('Views totais')
    total_videos   = _int('Total de vídeos') or _int('Total videos') or _int('Videos')
    views_28d      = _int('Views')
    horas_28d      = _float('Horas assistidas')
    novos          = _int('Novos inscritos')
    receita_brl    = _float('Receita BRL')
    cotacao        = _float('Cotação USD/BRL') or 5.15

    top_rpm = []
    for v in dados_parsed.get('videos_receita', [])[:10]:
        top_rpm.append({
            'titulo': v.get('titulo', ''),
            'brl':    v.get('receita', 0),
            'views':  v.get('views', 0),
            'rpm':    v.get('rpm', 0),
        })

    receita_diaria = []
    for r in dados_parsed.get('receita_diaria', []):
        receita_diaria.append({'d': r.get('data', ''), 'brl': r.get('brl', 0)})

    # Receita por console (heuristic from video titles)
    console_map: dict = {}
    for v in dados_parsed.get('videos_receita', []):
        titulo = (v.get('titulo') or '').lower()
        rec    = v.get('receita', 0)
        if 'switch' in titulo:   console_map['Switch'] = console_map.get('Switch', 0) + rec
        elif 'ps4' in titulo or 'playstation 4' in titulo:
            console_map['PS4'] = console_map.get('PS4', 0) + rec
        elif 'steam deck' in titulo: console_map['Steam Deck'] = console_map.get('Steam Deck', 0) + rec
        elif 'xbox' in titulo:   console_map['Xbox'] = console_map.get('Xbox', 0) + rec
        else:                    console_map['Outros'] = console_map.get('Outros', 0) + rec
    total_console = sum(console_map.values()) or 1
    receita_console = [
        {'console': k, 'receita': round(v, 2), 'pct': round(v / total_console * 100)}
        for k, v in sorted(console_map.items(), key=lambda x: -x[1])
    ]

    return {
        'canal': {'inscritos': inscritos, 'views_totais': views_totais, 'total_videos': total_videos, 'cotacao': cotacao},
        'analytics28d': {'views': views_28d, 'horas': horas_28d, 'novos_inscritos': novos, 'receita_brl': receita_brl},
        'top_rpm': top_rpm,
        'receita_diaria': receita_diaria,
        'receita_console': receita_console,
    }


def _parse_receita_day(raw_day: str, ref_year: int):
    if not raw_day:
        return None
    txt = str(raw_day).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    # Some collectors may return day/month without year.
    try:
        d = datetime.strptime(txt, '%d/%m').date()
        return d.replace(year=ref_year)
    except ValueError:
        return None


def _calcular_receita_trimestre_atual(receita_diaria: list) -> tuple:
    """Soma receita diária do trimestre atual (UTC)."""
    now_utc = datetime.utcnow()
    q_start_month = ((now_utc.month - 1) // 3) * 3 + 1
    q_end_month = q_start_month + 2

    total = 0.0
    has_points = False
    for row in receita_diaria or []:
        if not isinstance(row, dict):
            continue
        day = _parse_receita_day(row.get('d', ''), now_utc.year)
        if day is None:
            continue
        if day.year == now_utc.year and q_start_month <= day.month <= q_end_month:
            try:
                total += float(row.get('brl', 0) or 0)
                has_points = True
            except (TypeError, ValueError):
                continue
    return round(total, 2), has_points


def _metas_para_componente(
    metas_json: dict,
    historico: list,
    receita_q2_calculada=None,
    receita_q2_has_data=False,
) -> dict:
    """metas.json → HTML metas format (adds accuracy + padroes)"""
    m = metas_json
    # Compute accuracy from historico
    vinculados = [h for h in historico if h.get('sugestao_id') and h.get('rpm_real') is not None and h.get('rpm_previsto')]
    acertos = sum(1 for h in vinculados if h.get('rpm_real', 0) >= h.get('rpm_previsto', 1) * 0.7)
    pct_acerto = round(acertos / len(vinculados) * 100) if vinculados else 0

    receita_q2_valor = receita_q2_calculada if receita_q2_calculada is not None else m.get('receita_q2', 0)
    return {
        'anual': {
            'desc':     m.get('meta_anual_desc', m.get('descricao', '—')),
            'atingida': m.get('meta_anual_atingida', False),
        },
        'ano': {
            'receita':  m.get('receita_ano', m.get('meta_receita_anual', 30000)),
            'inscritos': m.get('inscritos_ano', m.get('meta_inscritos_anual', 10000)),
            'videos':   m.get('videos_ano', m.get('meta_videos_anual', 52)),
        },
        'q2': {
            'receita':  m.get('meta_receita_q2', 8000),
            'inscritos': m.get('meta_inscritos_q2', 3000),
            'videos':   m.get('meta_videos_q2', 13),
        },
        'atual': {
            'receita_ytd':  m.get('receita_ytd', 0),
            'inscritos_ytd': m.get('inscritos_ytd', 0),
            'videos_ytd':   m.get('videos_ytd', 0),
            'receita_q2':   receita_q2_valor,
            'receita_q2_has_data': bool(receita_q2_has_data),
            'inscritos_q2': m.get('inscritos_q2', 0),
            'videos_q2':    m.get('videos_q2', 0),
        },
        'accuracy': {
            'overall': pct_acerto,
            'trend':   f'+{pct_acerto}% (histórico)',
            'months':  [],
        },
        'padroes': m.get('padroes', []),
    }


def _historico_links(historico: list, sugestoes_pendentes: list) -> list:
    """Build the historico_links array for the HTML component."""
    sug_map = {s.get('id', ''): s for s in sugestoes_pendentes}
    links = []
    for h in historico[-10:]:
        sug_id   = h.get('sugestao_id', '')
        sug_obj  = sug_map.get(sug_id, {})
        sug_text = sug_obj.get('texto') or sug_id or 'Manual'
        rpm_real = h.get('rpm_real', 0)
        rpm_prev = h.get('rpm_previsto', 0)
        ok_val   = None
        if rpm_real and rpm_prev:
            ok_val = rpm_real >= rpm_prev * 0.7
        links.append({
            'video':    h.get('titulo', h.get('titulo_video', ''))[:40],
            'sug':      sug_text[:40],
            'rpm_real': rpm_real,
            'rpm_prev': rpm_prev,
            'ok':       ok_val,
        })
    return links


def _config_status() -> dict:
    """Build the config status dict for the HTML component."""
    files_to_check = [
        'dados.txt', 'concorrentes.json', 'historico.json', 'funil.json',
        'transcricoes_canal.json', 'fila_producao.json', 'sugestoes_pendentes.json',
        'sugestao_semana.json', 'contexto.txt', 'metas.json', APRENDIZADOS_CREATOR_FILE,
    ]
    now_str = datetime.now().strftime('%d/%m %H:%M')
    files_status = []
    for fname in files_to_check:
        status = 'ok' if carregar_arquivo(fname, None) is not None else 'err'
        files_status.append({'name': fname, 'status': status, 'update': now_str})

    token_ok = bool(GITHUB_TOKEN)
    return {
        'token': {
            'status': 'ok' if token_ok else 'err',
            'expira': '—',
            'msg':    'Token configurado' if token_ok else 'Token ausente — configure nas Secrets',
        },
        'files': files_status,
    }


def _prepare_component_props(loading=False, loading_msg='', result_payload=None) -> dict:
    """Build all props for the render_dashboard() call."""
    historico       = carregar_arquivo('historico.json', [])
    fila_json       = carregar_arquivo('fila_producao.json', [])
    concorrentes    = carregar_arquivo('concorrentes.json', [])
    funil_json      = carregar_arquivo('funil.json', {})
    sugestao_semana = carregar_arquivo('sugestao_semana.json', {})
    pend_json       = carregar_arquivo('sugestoes_pendentes.json', [])
    metas_json      = carregar_arquivo('metas.json', {})
    contexto        = carregar_arquivo('contexto.txt', '')

    # Normalise sugestoes_pendentes to HTML format
    sugestoes_pendentes = []
    for s in pend_json:
        sugestoes_pendentes.append({
            'id':     s.get('id', ''),
            'texto':  s.get('texto') or s.get('titulo_real', ''),
            'data':   s.get('data', ''),
            'status': s.get('status', 'pendente'),
        })

    dados_comp = _dados_para_componente(_dados)
    receita_q2_calculada, receita_q2_has_data = _calcular_receita_trimestre_atual(
        dados_comp.get('receita_diaria', [])
    )

    return dict(
        dados              = dados_comp,
        fila               = _fila_para_componente(fila_json, historico),
        concorrentes       = concorrentes,
        funil              = _funil_para_componente(funil_json),
        sugestao_semana    = sugestao_semana,
        sugestoes_pendentes= sugestoes_pendentes,
        metas              = _metas_para_componente(
            metas_json,
            historico,
            receita_q2_calculada=receita_q2_calculada,
            receita_q2_has_data=receita_q2_has_data,
        ),
        historico_links    = _historico_links(historico, pend_json),
        historico          = historico,
        contexto           = contexto,
        config             = _config_status(),
        loading            = loading,
        loading_msg        = loading_msg,
        result_payload     = result_payload or {},
    )


# ══════════════════════════════════════════════════════════════════════
# ACTION DISPATCHER
# ══════════════════════════════════════════════════════════════════════

def _dispatch_action(action_data: dict) -> bool:
    """Handle actions from the HTML component. Returns True if st.rerun() should be called."""
    rid = action_data.get('request_id') if isinstance(action_data, dict) else None
    if rid and st.session_state.get('_dashboard_processed_request_id') == rid:
        return False

    def _mark_done() -> bool:
        if rid:
            st.session_state['_dashboard_processed_request_id'] = rid
        return True

    action  = action_data.get('action', '')
    fila    = carregar_arquivo('fila_producao.json', [])
    concs   = carregar_arquivo('concorrentes.json', [])
    hist    = carregar_arquivo('historico.json', [])
    ctx     = contexto_com_aprendizados(carregar_arquivo('contexto.txt', ''))
    concs_j = carregar_arquivo('concorrentes.json', [])
    funil_j = carregar_arquivo('funil.json', {})
    pends   = carregar_arquivo('sugestoes_pendentes.json', [])
    ss      = carregar_arquivo('sugestao_semana.json', {})

    # ── Hero sugestão da semana ──────────────────────────────────────
    if action == 'accept_suggestion':
        titulo      = action_data.get('titulo', ss.get('titulo', ''))
        rpm         = action_data.get('rpm_esperado', ss.get('rpm_esperado', 0))
        etapa       = action_data.get('etapa_funil', ss.get('etapa_funil', 'topo'))
        sug_id      = action_data.get('sugestao_id') or f'semana_{datetime.now().strftime("%Y%m%d")}'
        fila.append({
            'sugestao_id': sug_id,
            'titulo_planejado': titulo,
            'titulo_publicado': None,
            'video_id_youtube': None,
            'rpm_previsto': rpm,
            'funil': etapa,
            'status': 'planejado',
            'data_planejamento': datetime.now().strftime('%Y-%m-%d'),
            'data_publicacao': None,
            'origem': 'sugestao_semana',
        })
        salvar_github('fila_producao.json', fila)
        st.cache_data.clear()
        return _mark_done()

    if action == 'generate_suggestion':
        with st.spinner('Gerando sugestão...'):
            nova = gerar_sugestao_semana(dados_raw or '', ctx, concs_j, funil_j)
            if nova:
                nova['gerado_em'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                salvar_github('sugestao_semana.json', nova)
                st.cache_data.clear()
        return _mark_done()

    # ── Tema livre ──────────────────────────────────────────────────
    if action == 'dismiss_tema_livre':
        st.session_state.pop('_result_payload', None)
        return _mark_done()

    if action == 'generate_tema_livre':
        tema = (action_data.get('tema') or '').strip()
        brief = (action_data.get('brief') or '').strip()
        if not tema:
            return _mark_done()
        with st.spinner(f'Gerando sugestão para "{tema}"...'):
            nova = gerar_sugestao_tema_livre(tema, dados_raw or '', ctx, funil_j, brief=brief)
            if nova:
                nova['tema'] = tema
                if brief:
                    nova['brief'] = brief
                nova['type'] = 'tema_livre'
                st.session_state['_result_payload'] = nova
        return _mark_done()

    if action == 'accept_tema_livre':
        titulo = action_data.get('titulo', '')
        rpm    = action_data.get('rpm_esperado', 50)
        etapa  = action_data.get('etapa_funil', 'topo')
        tema   = action_data.get('tema', '')
        brief_a = (action_data.get('brief') or '').strip()
        entry = {
            'sugestao_id': None,
            'titulo_planejado': titulo,
            'titulo_publicado': None,
            'video_id_youtube': None,
            'rpm_previsto': rpm,
            'funil': etapa,
            'status': 'planejado',
            'data_planejamento': datetime.now().strftime('%Y-%m-%d'),
            'data_publicacao': None,
            'origem': f'tema_livre:{tema}',
        }
        if brief_a:
            entry['brief_criador'] = brief_a
        fila.append(entry)
        salvar_github('fila_producao.json', fila)
        st.session_state.pop('_result_payload', None)
        st.cache_data.clear()
        return _mark_done()

    # ── Adicionar à fila (manual) ────────────────────────────────────
    if action == 'add_to_queue':
        titulo = action_data.get('titulo', '')
        rpm    = action_data.get('rpm_previsto', 50)
        etapa  = action_data.get('funil', 'topo')
        if titulo.strip():
            fila.append({
                'sugestao_id': None,
                'titulo_planejado': titulo.strip(),
                'titulo_publicado': None,
                'video_id_youtube': None,
                'rpm_previsto': rpm,
                'funil': etapa,
                'status': 'planejado',
                'data_planejamento': datetime.now().strftime('%Y-%m-%d'),
                'data_publicacao': None,
                'origem': 'ideia_propria',
            })
            salvar_github('fila_producao.json', fila)
            st.cache_data.clear()
        return _mark_done()

    # ── Kanban actions ───────────────────────────────────────────────
    STATUS_NEXT = {'planejado': 'gravando', 'gravando': 'publicado', 'publicado': 'concluido'}
    STATUS_PREV = {'gravando': 'planejado', 'publicado': 'gravando', 'concluido': 'publicado'}

    KANBAN_STATUSES = ('planejado', 'gravando', 'publicado', 'concluido')

    if action == 'kanban_advance':
        idx = action_data.get('idx', -1)
        if 0 <= idx < len(fila):
            curr = fila[idx].get('status', 'planejado')
            fila[idx]['status'] = STATUS_NEXT.get(curr, curr)
            salvar_github('fila_producao.json', fila)
            st.cache_data.clear()
        return _mark_done()

    if action == 'kanban_back':
        idx = action_data.get('idx', -1)
        if 0 <= idx < len(fila):
            curr = fila[idx].get('status', 'planejado')
            fila[idx]['status'] = STATUS_PREV.get(curr, curr)
            salvar_github('fila_producao.json', fila)
            st.cache_data.clear()
        return _mark_done()

    if action == 'kanban_set_status':
        try:
            idx = int(action_data.get('idx', -1))
        except (TypeError, ValueError):
            idx = -1
        new_st = (action_data.get('status') or '').strip()
        if 0 <= idx < len(fila) and new_st in KANBAN_STATUSES:
            fila[idx]['status'] = new_st
            salvar_github('fila_producao.json', fila)
            st.cache_data.clear()
        return _mark_done()

    if action == 'kanban_delete':
        idx = action_data.get('idx', -1)
        if 0 <= idx < len(fila):
            fila.pop(idx)
            salvar_github('fila_producao.json', fila)
            st.cache_data.clear()
        return _mark_done()

    if action == 'kanban_publish':
        idx              = action_data.get('idx', -1)
        video_id         = action_data.get('video_id', '')
        titulo_publicado = action_data.get('titulo_publicado', '')
        if 0 <= idx < len(fila):
            fila[idx]['video_id_youtube'] = video_id
            fila[idx]['status']           = 'publicado'
            if titulo_publicado:
                fila[idx]['titulo_publicado'] = titulo_publicado
            fila[idx]['data_publicacao'] = datetime.now().strftime('%Y-%m-%d')
            salvar_github('fila_producao.json', fila)
            st.cache_data.clear()
        return _mark_done()

    if action == 'link_video':
        try:
            idx = int(action_data.get('idx', -1))
        except (TypeError, ValueError):
            idx = -1
        notas = (action_data.get('notas') or '').strip()
        sug_id = (action_data.get('sug_id') or '').strip() or None
        if not notas or idx < 0 or idx >= len(fila):
            return _mark_done()
        item = fila[idx]
        titulo_pub = (item.get('titulo_publicado') or item.get('titulo_planejado') or '').strip()
        video_id = (item.get('video_id_youtube') or '').strip()

        sug_texto = ''
        if sug_id:
            for p in pends:
                if p.get('id') == sug_id:
                    sug_texto = (p.get('texto') or p.get('titulo_real') or '')[:2000]
                    break

        rpm_real = 0.0
        rpm_prev = float(item.get('rpm_previsto') or 0)
        h_match = _find_historico_video_match(hist, item)
        if h_match is not None:
            rpm_real = float(h_match.get('rpm_real') or 0)
        current_link = (h_match or {}).get('sugestao_id')
        current_link = str(current_link or '').strip()
        if h_match is not None and sug_id and current_link and current_link != sug_id:
            st.session_state['_result_payload'] = {
                'type': 'link_feedback',
                'kind': 'warn',
                'message': 'Este vídeo já está vinculado. Desvincule antes de criar novo vínculo.',
            }
            return _mark_done()

        analise_ia = ''
        if sug_texto and titulo_pub and rpm_real > 0 and CLAUDE_API_KEY:
            analise_ia = analisar_aprendizado_sugestao(sug_texto, titulo_pub, rpm_real, rpm_prev)

        record = {
            'data': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'video_id_youtube': video_id or None,
            'titulo_planejado': item.get('titulo_planejado'),
            'titulo_publicado': item.get('titulo_publicado'),
            'notas': notas,
            'sugestao_id': sug_id,
            'rpm_previsto': item.get('rpm_previsto'),
            'origem_fila': item.get('origem'),
        }
        if analise_ia:
            record['analise_ia'] = analise_ia

        ap_list = carregar_arquivo(APRENDIZADOS_CREATOR_FILE, [])
        if not isinstance(ap_list, list):
            ap_list = []
        ap_list.append(record)
        if len(ap_list) > APRENDIZADOS_MAX_ENTRIES:
            ap_list = ap_list[-APRENDIZADOS_MAX_ENTRIES:]
        salvar_github(APRENDIZADOS_CREATOR_FILE, ap_list)

        hist_changed = False
        if h_match is not None:
            h_match['notas_criador'] = notas
            if sug_id and not h_match.get('sugestao_id'):
                h_match['sugestao_id'] = sug_id
            hist_changed = True
        if hist_changed:
            salvar_github('historico.json', hist)

        st.cache_data.clear()
        return _mark_done()

    if action == 'unlink_video':
        try:
            idx = int(action_data.get('idx', -1))
        except (TypeError, ValueError):
            idx = -1
        if idx < 0 or idx >= len(fila):
            return _mark_done()
        item = fila[idx]
        h_match = _find_historico_video_match(hist, item)
        if not isinstance(h_match, dict):
            st.session_state['_result_payload'] = {
                'type': 'link_feedback',
                'kind': 'warn',
                'message': 'Vínculo não encontrado no histórico para este vídeo.',
            }
            return _mark_done()
        has_sug = str(h_match.get('sugestao_id') or '').strip()
        has_notas = str(h_match.get('notas_criador') or '').strip()
        if not has_sug and not has_notas:
            st.session_state['_result_payload'] = {
                'type': 'link_feedback',
                'kind': 'warn',
                'message': 'Este vídeo já está sem vínculo ou notas de criador no histórico.',
            }
            return _mark_done()
        h_match['sugestao_id'] = None
        h_match.pop('notas_criador', None)
        salvar_github('historico.json', hist)
        st.session_state['_result_payload'] = {
            'type': 'link_feedback',
            'kind': 'ok',
            'message': 'Vínculo removido com sucesso.',
        }
        st.cache_data.clear()
        return _mark_done()

    if action == 'dismiss_link_feedback':
        rp = st.session_state.get('_result_payload', {})
        if isinstance(rp, dict) and rp.get('type') == 'link_feedback':
            st.session_state.pop('_result_payload', None)
        return _mark_done()

    # ── Lote IA ──────────────────────────────────────────────────────
    if action == 'generate_batch':
        obs = action_data.get('obs', '')
        with st.spinner('Gerando sugestões com IA (~30-60s)...'):
            texto = gerar_sugestoes(dados_raw or '', f'{ctx}\n{obs}', hist, concs_j)
            if texto:
                today = datetime.now().strftime('%Y%m%d')
                id1 = f'SUG-{today}-01'
                id2 = f'SUG-{today}-02'
                # Save to sugestoes_pendentes.json
                pend_atual = carregar_arquivo('sugestoes_pendentes.json', [])
                existing_ids = {p.get('id', '') for p in pend_atual}
                for sid, num in [(id1, 1), (id2, 2)]:
                    if sid not in existing_ids:
                        pend_atual.append({
                            'id': sid,
                            'numero': num,
                            'texto': f'Sugestão {num} — {today}',
                            'data': datetime.now().strftime('%Y-%m-%d'),
                            'status': 'pendente',
                            'rpm_previsto': 0,
                        })
                salvar_github('sugestoes_pendentes.json', pend_atual)
                st.session_state['_result_payload'] = {
                    'type': 'batch',
                    'texto': texto,
                    'id1': id1,
                    'id2': id2,
                }
                st.cache_data.clear()
        return _mark_done()

    if action == 'use_suggestion':
        sug_id = action_data.get('sug_id', '')
        titulo = action_data.get('titulo', '')
        rpm    = action_data.get('rpm_previsto', 150)
        adicionar_sugestao_a_fila(sug_id, titulo, rpm)
        st.cache_data.clear()
        return _mark_done()

    if action == 'generate_script':
        tema = action_data.get('tema', '')
        with st.spinner('Gerando script...'):
            script = gerar_script(tema, dados_raw or '', ctx)
            rp = st.session_state.get('_result_payload', {})
            rp['script'] = script
            st.session_state['_result_payload'] = rp
        return _mark_done()

    # ── Concorrentes ─────────────────────────────────────────────────
    if action == 'add_competitor':
        nome     = action_data.get('nome', '')
        handle   = action_data.get('handle', '')
        obs      = action_data.get('observacao', '')
        pais     = action_data.get('pais', '🇧🇷 Brasil')
        if nome and handle:
            with st.spinner(f'Analisando {handle}...'):
                analise = analisar_concorrente(nome, handle)
            novo = {
                'nome': nome,
                'handle': handle,
                'observacao': obs,
                'pais': pais,
                'analise_ia': analise if isinstance(analise, dict) else {},
                'lacuna': '',
                'ultima_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M'),
            }
            concs.append(novo)
            salvar_github('concorrentes.json', concs)
            st.cache_data.clear()
        return _mark_done()

    if action == 'delete_competitor':
        idx = action_data.get('idx', -1)
        if 0 <= idx < len(concs):
            concs.pop(idx)
            salvar_github('concorrentes.json', concs)
            st.cache_data.clear()
        return _mark_done()

    # ── Metas ────────────────────────────────────────────────────────
    if action == 'save_meta':
        metas_json = carregar_arquivo('metas.json', {})
        metas_json.update(action_data.get('metas', {}))
        salvar_github('metas.json', metas_json)
        st.cache_data.clear()
        return _mark_done()

    # ── Token renewal (fallback to session state flag) ───────────────
    if action == 'open_token_renewal':
        st.session_state['_show_token_renewal'] = True
        return _mark_done()

    return False


# ══════════════════════════════════════════════════════════════════════
# HIDE NATIVE STREAMLIT CHROME
# ══════════════════════════════════════════════════════════════════════
st.markdown(
    '<style>#MainMenu,footer,header{visibility:hidden;}'
    '.stDeployButton{display:none;}'
    'section[data-testid="stSidebar"]{display:none;}'
    'div[data-testid="stToolbar"]{display:none;}'
    '</style>',
    unsafe_allow_html=True
)

# ══════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════

# Token renewal page (triggered from Config tab)
if st.session_state.get('_show_token_renewal'):
    st.markdown('## Renovar Token Google OAuth')
    if st.button('← Voltar ao dashboard'):
        st.session_state.pop('_show_token_renewal', None)
        st.rerun()
    renovar_token_google()
else:
    result_payload = st.session_state.get('_result_payload', {})
    props = _prepare_component_props(result_payload=result_payload)

    action_result = render_dashboard(**props, key='dashboard')

    if action_result:
        did_rerun = _dispatch_action(action_result)
        if did_rerun:
            st.rerun()
