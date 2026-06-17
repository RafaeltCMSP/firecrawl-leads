"""Cliente Chatwoot: cria contatos a partir dos leads qualificados.

Cada lead vira um contato com atributos customizados (score, temperatura, parecer)
e a mensagem de abordagem entra como nota/conteudo inicial.
"""
import re

import requests

import config
from src.models import Lead


def _e164_br(raw: str) -> str:
    """Normaliza telefone brasileiro para +55XXXXXXXXXXX (best effort)."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("55"):
        return "+" + digits
    if len(digits) >= 10:
        return "+55" + digits
    return ""


class ChatwootClient:
    def __init__(self):
        self.base_url = config.CHATWOOT_BASE_URL.rstrip("/")
        self.token = config.CHATWOOT_API_TOKEN
        self.account_id = config.CHATWOOT_ACCOUNT_ID
        self.inbox_id = config.CHATWOOT_INBOX_ID
        self.timeout = config.REQUEST_TIMEOUT

    def _headers(self):
        return {"api_access_token": self.token, "Content-Type": "application/json"}

    def _url(self, path):
        return f"{self.base_url}/api/v1/accounts/{self.account_id}{path}"

    def create_contact(self, lead: Lead) -> dict:
        """Cria o contato no Chatwoot e retorna o payload da API."""
        phone = _e164_br(lead.whatsapp or lead.phone)
        body = {
            "name": lead.name or lead.domain,
            "email": lead.email or None,
            "phone_number": phone or None,
            "additional_attributes": {
                "company_name": lead.name or lead.domain,
                "site": lead.url,
            },
            "custom_attributes": {
                "nicho": lead.niche,
                "localidade": lead.location,
                "opportunity_score": lead.opportunity_score,
                "quality_score": lead.quality_score,
                "lead_temp": lead.lead_temp,
                "anuncios": lead.ad_pixels or "nenhum",
                "redes_sociais": lead.social_count,
                "tem_google": "sim" if lead.has_maps else "nao",
                "parecer_site": lead.site_quality,
                "canais_faltando": lead.missing_channels,
                "gancho_venda": lead.pitch_angle,
                "mensagem_whatsapp": lead.outreach,
            },
        }
        if self.inbox_id:
            body["inbox_id"] = int(self.inbox_id)

        r = requests.post(self._url("/contacts"), json=body, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def extract_id(payload: dict) -> str:
        try:
            return str(payload.get("payload", {}).get("contact", {}).get("id", ""))
        except Exception:  # noqa: BLE001
            return ""

    def ping(self):
        try:
            r = requests.get(self._url("/contacts?page=1"), headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            return True, "ok"
        except Exception as e:  # noqa: BLE001
            return False, str(e)
