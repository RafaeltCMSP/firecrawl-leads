"""Orquestra o funil generico: buscar -> raspar -> detectar -> (enriquecer) ->
(MiniMax) -> salvar. Funciona para qualquer nicho e qualquer regiao."""
import re
import time

import config
from src import db, detector
from src.firecrawl_client import FirecrawlClient
from src.minimax_client import MiniMaxClient
from src.models import Lead

# Sugestoes de UI (nao restringem nada)
NICHE_SUGGESTIONS = [
    "imobiliaria", "clinica odontologica", "academia", "restaurante",
    "escritorio de advocacia", "clinica de estetica", "pet shop", "salao de beleza",
    "oficina mecanica", "loja de moveis", "escola de idiomas", "contabilidade",
]
LOCATION_SUGGESTIONS = [
    "Sao Paulo SP", "Rio de Janeiro RJ", "Belo Horizonte MG", "Curitiba PR",
    "Porto Alegre RS", "Campinas SP", "Salvador BA", "Brasilia DF", "Fortaleza CE",
]

# Portais/agregadores/diretorios que nao sao leads (sao plataformas, nao o negocio)
PORTALS = (
    "zapimoveis", "vivareal", "imovelweb", "quintoandar", "olx.", "chavesnamao",
    "wimoveis", "lopes.com.br", "lello", "loft.com.br", "imovelguide",
    "google.com", "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "tripadvisor", "ifood", "doctoralia", "yelp", "guiamais", "telelistas",
    "encontra", "apontador", "solutudo", "consultaremedios", "reclameaqui",
    "wikipedia", "mercadolivre", "booking.com", "airbnb", "guiatelefone",
    "guiafacil", "guialocal", "hotfrog", "cylex", "econodata", "cnpj",
    "tudosobre", "buscacuritiba", "comerciocuritiba", "listas", "paginasamarelas",
    "bing.com", "uol.com.br", "globo.com", "98pontos", "ondedormir",
)

# Marcadores de pagina de LISTA/ranking (nao e o negocio em si)
LISTICLE_HINTS = (
    "melhores", "/lista", "ranking", "guia-de", "top-10", "top10", "10-melhores",
    "as-melhores", "os-melhores", "/blog/", "/categoria/", "/diretorio",
)


def is_portal(url: str) -> bool:
    low = url.lower()
    if any(p in low for p in PORTALS):
        return True
    return any(h in low for h in LISTICLE_HINTS)


def build_queries(niche: str, location: str, variations: bool):
    niche = niche.strip()
    location = location.strip()
    base = f"{niche} {location}".strip()
    queries = [base]
    if variations:
        queries.append(f"{niche} em {location}".strip())
        queries.append(f"melhores {niche} {location}".strip())
    # remove duplicatas preservando ordem
    seen, out = set(), []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def search_candidates(niche, locations, limit_per_query, variations, fc,
                      skip_portals=True, on_log=None):
    seen, out = set(), []
    for location in locations:
        for query in build_queries(niche, location, variations):
            if on_log:
                on_log(f"Buscando: {query}")
            try:
                results = fc.search(query, limit=limit_per_query)
            except Exception as e:  # noqa: BLE001
                if on_log:
                    on_log(f"  erro na busca '{query}': {e}")
                continue
            for r in results:
                url = (r.get("url") or "").strip()
                if not url or url in seen:
                    continue
                if skip_portals and is_portal(url):
                    continue
                seen.add(url)
                out.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                    "niche": niche,
                    "location": location,
                })
            time.sleep(config.RATE_LIMIT_SECONDS)
    return out


def _apply_tech(lead: Lead, tech: dict):
    lead.ad_pixels = tech["ad_pixels"]
    lead.has_ads = tech["has_ads"]
    lead.analytics = tech["analytics"]
    lead.has_analytics = tech["has_analytics"]
    lead.cms = tech["cms"]
    lead.is_mobile = tech["is_mobile"]
    lead.is_https = tech["is_https"]
    lead.has_maps = tech["has_maps"]
    lead.google_business = tech["google_business"]
    for s in ("instagram", "facebook", "linkedin", "youtube", "tiktok", "twitter"):
        setattr(lead, s, tech[s])
    lead.social_count = tech["social_count"]
    lead.phone = tech["phone"]
    lead.whatsapp = tech["whatsapp"]
    lead.email = tech["email"]
    lead.reachable = tech["reachable"]
    lead.opportunity_score = tech["opportunity_score"]


def enrich_lead(lead: Lead, fc: FirecrawlClient, on_log=None):
    """Busca extra pelo nome do negocio para achar redes/Google que nao estao no site."""
    name = lead.name or lead.domain
    query = f"{name} {lead.location}".strip()
    try:
        results = fc.search(query, limit=5)
    except Exception as e:  # noqa: BLE001
        if on_log:
            on_log(f"  enrich falhou: {e}")
        return
    social_fields = {
        "instagram": "instagram.com/", "facebook": "facebook.com/",
        "linkedin": "linkedin.com/", "youtube": "youtube.com/",
        "tiktok": "tiktok.com/", "twitter": None,
    }
    for r in results:
        u = (r.get("url") or "")
        low = u.lower()
        for field, frag in social_fields.items():
            if frag and frag in low and not getattr(lead, field):
                setattr(lead, field, u)
        if ("google.com/maps" in low or "maps.app.goo.gl" in low) and not lead.google_business:
            lead.google_business = u
            lead.has_maps = True
    lead.social_count = sum(1 for s in ("instagram", "facebook", "linkedin", "youtube", "tiktok", "twitter")
                            if getattr(lead, s))


def process_candidate(cand, fc, mm=None, use_minimax=True, deep_enrich=False, on_log=None) -> Lead:
    url = cand["url"]
    lead = Lead(url=url, niche=cand.get("niche", ""), location=cand.get("location", ""),
                name=(cand.get("title") or "").strip())
    try:
        scraped = fc.scrape(url, formats=["rawHtml", "markdown"])
        html = scraped.get("rawHtml") or scraped.get("html") or ""
        markdown = scraped.get("markdown") or ""

        tech = detector.detect(url, html)
        _apply_tech(lead, tech)
        lead.status = "qualificado" if lead.is_good_lead else "descartado"

        if deep_enrich and (lead.social_count == 0 or not lead.google_business):
            enrich_lead(lead, fc, on_log=on_log)
            tech["social_count"] = lead.social_count
            for s in ("instagram", "facebook", "linkedin", "youtube", "tiktok", "twitter"):
                tech[s] = getattr(lead, s)

        if use_minimax and mm is not None:
            try:
                a = mm.analyze(niche=cand.get("niche", ""), name_hint=cand.get("title", ""),
                               url=url, location=cand.get("location", ""), tech=tech, markdown=markdown)
                if a:
                    lead.name = a.get("nome") or lead.name
                    lead.niche = a.get("segmento") or lead.niche
                    lead.location = a.get("regiao") or lead.location
                    lead.phone = a.get("telefone") or lead.phone
                    lead.whatsapp = a.get("whatsapp") or lead.whatsapp
                    lead.email = a.get("email") or lead.email
                    lead.site_quality = a.get("qualidade_site", "")
                    lead.weaknesses = "; ".join(a.get("pontos_fracos", []) or []) if isinstance(a.get("pontos_fracos"), list) else str(a.get("pontos_fracos", ""))
                    lead.missing_channels = "; ".join(a.get("canais_faltando", []) or []) if isinstance(a.get("canais_faltando"), list) else str(a.get("canais_faltando", ""))
                    lead.lead_temp = (a.get("lead_temp") or "").lower()
                    lead.pitch_angle = a.get("gancho_venda", "")
                    lead.outreach = a.get("mensagem_whatsapp", "")
                    subj = a.get("assunto_email", "")
                    body = a.get("mensagem_email", "")
                    lead.outreach_email = (f"Assunto: {subj}\n\n{body}").strip() if (subj or body) else ""
                    try:
                        lead.quality_score = int(a.get("quality_score", 0))
                    except (TypeError, ValueError):
                        lead.quality_score = 0
                    lead.reachable = bool(lead.whatsapp or lead.phone or lead.email)
            except Exception as e:  # noqa: BLE001
                lead.error = f"minimax: {e}"
                if on_log:
                    on_log(f"  MiniMax falhou em {url}: {e}")
    except Exception as e:  # noqa: BLE001
        lead.status = "erro"
        lead.error = str(e)
        if on_log:
            on_log(f"  erro ao raspar {url}: {e}")

    db.upsert(lead)
    return lead
