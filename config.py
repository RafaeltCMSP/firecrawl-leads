"""Carrega configuracoes. Funciona em dois ambientes:
- Local: le do arquivo .env (python-dotenv).
- Streamlit Cloud: le de st.secrets (painel Secrets), copiado para o ambiente.
Importado por app.py e pelos modulos em src/.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Em Streamlit Cloud nao ha .env; os segredos vem de st.secrets.
# Copiamos para os.environ para o restante do codigo continuar usando os.getenv.
try:  # pragma: no cover - so executa quando rodando dentro do Streamlit
    import streamlit as st  # noqa: E402

    if hasattr(st, "secrets"):
        for _k, _v in dict(st.secrets).items():
            if isinstance(_v, (str, int, float, bool)):
                os.environ.setdefault(_k, str(_v))
except Exception:  # noqa: BLE001 - sem secrets configurados / fora do streamlit
    pass


def _get(name, default=""):
    return os.getenv(name, default) or default


# Firecrawl
FIRECRAWL_BASE_URL = _get("FIRECRAWL_BASE_URL", "https://automate-firecrawl.hr91bv.easypanel.host").rstrip("/")
FIRECRAWL_API_KEY = _get("FIRECRAWL_API_KEY")

# MiniMax
MINIMAX_API_KEY = _get("MINIMAX_API_KEY")
MINIMAX_BASE_URL = _get("MINIMAX_BASE_URL", "https://api.minimax.io/v1").rstrip("/")
MINIMAX_MODEL = _get("MINIMAX_MODEL", "MiniMax-Text-01")
MINIMAX_GROUP_ID = _get("MINIMAX_GROUP_ID")

# Chatwoot
CHATWOOT_BASE_URL = _get("CHATWOOT_BASE_URL").rstrip("/")
CHATWOOT_API_TOKEN = _get("CHATWOOT_API_TOKEN")
CHATWOOT_ACCOUNT_ID = _get("CHATWOOT_ACCOUNT_ID")
CHATWOOT_INBOX_ID = _get("CHATWOOT_INBOX_ID")

# Negocio / oferta (usado no prompt do MiniMax para personalizar a abordagem)
AGENCY_OFFER = _get(
    "AGENCY_OFFER",
    "gestao de trafego pago, anuncios online (Google e Meta) e presenca digital",
)
DEFAULT_NICHE = _get("DEFAULT_NICHE", "imobiliaria")

# Ajustes gerais
DB_PATH = _get("DB_PATH", "data/leads.db")
REQUEST_TIMEOUT = int(_get("REQUEST_TIMEOUT", "90"))
RATE_LIMIT_SECONDS = float(_get("RATE_LIMIT_SECONDS", "1.5"))


def minimax_enabled() -> bool:
    return bool(MINIMAX_API_KEY and "coloque" not in MINIMAX_API_KEY.lower())


def chatwoot_enabled() -> bool:
    return bool(CHATWOOT_BASE_URL and CHATWOOT_API_TOKEN and CHATWOOT_ACCOUNT_ID)
