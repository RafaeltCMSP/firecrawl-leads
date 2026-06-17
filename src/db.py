"""Persistencia em SQLite: salva, deduplica (por url) e mantem historico.

Faz migracao automatica: cria a tabela e adiciona colunas novas que faltarem
(ALTER TABLE), sem apagar dados existentes.
"""
import os
import sqlite3
from typing import List, Optional

import config
from src.models import Lead

# Ordem e nomes das colunas (espelha os campos do Lead persistidos)
COLUMNS = [
    "url", "domain", "name", "niche", "location",
    "ad_pixels", "has_ads", "analytics", "has_analytics",
    "cms", "is_mobile", "is_https", "has_maps",
    "instagram", "facebook", "linkedin", "youtube", "tiktok", "twitter",
    "social_count", "google_business",
    "phone", "whatsapp", "email", "reachable",
    "opportunity_score",
    "site_quality", "weaknesses", "missing_channels", "quality_score",
    "lead_temp", "pitch_angle", "outreach", "outreach_email",
    "status", "error", "chatwoot_id", "created_at",
]

# Tipos para o CREATE/ALTER
INT_COLS = {"has_ads", "has_analytics", "is_mobile", "is_https", "has_maps",
            "reachable", "social_count", "opportunity_score", "quality_score"}
REAL_COLS = {"created_at"}


def _coltype(c):
    if c in INT_COLS:
        return "INTEGER"
    if c in REAL_COLS:
        return "REAL"
    return "TEXT"


def _connect():
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        cols_sql = ",\n".join(
            f"{c} {_coltype(c)}" + (" PRIMARY KEY" if c == "url" else "")
            for c in COLUMNS
        )
        conn.execute(f"CREATE TABLE IF NOT EXISTS leads (\n{cols_sql}\n)")
        # migracao: adiciona colunas que faltarem
        existing = {r[1] for r in conn.execute("PRAGMA table_info(leads)")}
        for c in COLUMNS:
            if c not in existing:
                conn.execute(f"ALTER TABLE leads ADD COLUMN {c} {_coltype(c)}")


def exists(url: str) -> bool:
    with _connect() as conn:
        return conn.execute("SELECT 1 FROM leads WHERE url = ?", (url,)).fetchone() is not None


def get(url: str) -> Optional[Lead]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM leads WHERE url = ?", (url,)).fetchone()
        return Lead.from_row(dict(row)) if row else None


def upsert(lead: Lead):
    d = lead.to_dict()
    values = [d.get(c) for c in COLUMNS]
    placeholders = ",".join(["?"] * len(COLUMNS))
    updates = ",".join([f"{c}=excluded.{c}" for c in COLUMNS if c != "url"])
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO leads ({','.join(COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(url) DO UPDATE SET {updates}",
            values,
        )


def all_leads() -> List[Lead]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY opportunity_score DESC, created_at DESC"
        ).fetchall()
        return [Lead.from_row(dict(r)) for r in rows]


def update_status(url: str, status: str, chatwoot_id: str = ""):
    with _connect() as conn:
        conn.execute(
            "UPDATE leads SET status = ?, chatwoot_id = ? WHERE url = ?",
            (status, chatwoot_id, url),
        )
