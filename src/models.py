"""Estrutura de um Lead (generico: qualquer nicho, qualquer regiao)."""
import time
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse


@dataclass
class Lead:
    url: str
    domain: str = ""
    name: str = ""
    niche: str = ""           # nicho buscado (imobiliaria, clinica, academia...)
    location: str = ""        # localidade buscada / detectada

    # Trafego pago e mensuracao (separados)
    ad_pixels: str = ""       # Google Ads, Meta Pixel... (investe em anuncio)
    has_ads: bool = False
    analytics: str = ""       # GA, GTM, Hotjar, Clarity
    has_analytics: bool = False

    # Tecnologia do site
    cms: str = ""             # WordPress, Wix, Webflow, custom...
    is_mobile: bool = False
    is_https: bool = False
    has_maps: bool = False    # embed do Google Maps no site

    # Presenca digital (redes / google)
    instagram: str = ""
    facebook: str = ""
    linkedin: str = ""
    youtube: str = ""
    tiktok: str = ""
    twitter: str = ""
    social_count: int = 0
    google_business: str = "" # url do perfil/maps se encontrado

    # Contatos
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    reachable: bool = False

    # Score de oportunidade (0-100, MAIOR = melhor prospect)
    opportunity_score: int = 0

    # Analise MiniMax
    site_quality: str = ""    # parecer textual
    weaknesses: str = ""      # pontos fracos (texto/lista)
    missing_channels: str = "" # canais faltando (sem instagram, sem google...)
    quality_score: int = 0    # 0-100 (menor = pior site = melhor oportunidade)
    lead_temp: str = ""       # quente / morno / frio
    pitch_angle: str = ""     # gancho de venda
    outreach: str = ""        # mensagem WhatsApp
    outreach_email: str = ""  # assunto + corpo de e-mail

    # Meta
    status: str = "novo"      # novo | qualificado | descartado | enviado_chatwoot | erro
    error: str = ""
    chatwoot_id: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.domain and self.url:
            self.domain = urlparse(self.url).netloc.lower()

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict):
        valid = {k: row[k] for k in row.keys() if k in cls.__annotations__}
        return cls(**valid)

    @property
    def socials_list(self):
        pairs = [("Instagram", self.instagram), ("Facebook", self.facebook),
                 ("LinkedIn", self.linkedin), ("YouTube", self.youtube),
                 ("TikTok", self.tiktok), ("Twitter/X", self.twitter)]
        return [(n, u) for n, u in pairs if u]

    @property
    def is_good_lead(self) -> bool:
        """Bom prospect = nao roda anuncio pago E da pra contatar."""
        return (not self.has_ads) and self.reachable
