"""Deteccao tecnica via regex no HTML. Generico para qualquer nicho.

Cobre: pixels de anuncio, analytics, CMS, mobile/https, redes sociais,
Google Meu Negocio/Maps e contatos. Barato e instantaneo.
"""
import re
from urllib.parse import urlparse

# --- Anuncios pagos (quem TEM isso ja investe -> lead fraco pra agencia) ---
AD_PIXELS = {
    "Google Ads": r"googleadservices\.com|googleads\.g\.doubleclick|/gtag/js\?id=aw-|google_conversion",
    "Meta Pixel": r"connect\.facebook\.net/[^\"']+/fbevents\.js|fbq\(\s*['\"](?:init|track)",
    "TikTok Ads": r"analytics\.tiktok\.com",
    "LinkedIn Ads": r"snap\.licdn\.com",
}

# --- Mensuracao (indica maturidade digital, mas nao necessariamente anuncio) ---
ANALYTICS = {
    "Google Analytics": r"google-analytics\.com|/gtag/js\?id=g-|googletagmanager\.com/gtag",
    "Google Tag Manager": r"googletagmanager\.com/gtm",
    "Hotjar": r"static\.hotjar\.com",
    "MS Clarity": r"clarity\.ms",
}

# --- Plataforma/CMS ---
CMS_SIGNS = {
    "WordPress": r"wp-content|wp-includes",
    "Wix": r"static\.parastorage\.com|wixstatic|_wix|wix\.com",
    "Squarespace": r"squarespace\.com|static1\.squarespace",
    "Webflow": r"assets\.website-files\.com|webflow\.io",
    "Shopify": r"cdn\.shopify\.com",
    "Joomla": r"/components/com_|content=\"joomla",
    "Elementor": r"elementor",
}

SOCIAL_DOMAINS = {
    "instagram": r"instagram\.com/",
    "facebook": r"facebook\.com/",
    "linkedin": r"linkedin\.com/",
    "youtube": r"youtube\.com/",
    "tiktok": r"tiktok\.com/",
    "twitter": r"(?:twitter|x)\.com/",
}
SOCIAL_JUNK = ("/sharer", "/share.php", "/dialog", "/plugins", "/intent", "/tr?",
               "sharer.php", "/login", "/home", "/policies", "/help")

MAPS_RE = re.compile(
    r"https?://(?:www\.)?(?:google\.[a-z.]+/maps[^\s\"'<>)]+|maps\.google\.[a-z.]+/[^\s\"'<>)]+|"
    r"goo\.gl/maps/[^\s\"'<>)]+|maps\.app\.goo\.gl/[^\s\"'<>)]+)", re.I)

VIEWPORT_RE = re.compile(r"<meta[^>]+name=[\"']viewport[\"']", re.I)
PHONE_RE = re.compile(r"\(?\b\d{2}\)?[\s.\-]?9?\d{4}[\s.\-]?\d{4}\b")
WHATSAPP_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=|web\.whatsapp\.com/send\?phone=)\+?(\d{10,13})", re.I)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
EMAIL_BLOCKLIST = ("sentry", "example.com", "wixpress", "@2x", ".png", ".jpg", ".gif", "u003e", "domain.com")


def _match_keys(html, table):
    return [name for name, pat in table.items() if re.search(pat, html, re.I)]


def _first_social(html, domain_pat):
    pattern = re.compile(r'https?://(?:[a-z]{2,3}\.)?' + domain_pat + r'[^\s"\'<>)]+', re.I)
    for url in pattern.findall(html):
        low = url.lower()
        if any(j in low for j in SOCIAL_JUNK):
            continue
        # ignora link "vazio" (so o dominio)
        path = low.split("/", 3)
        if len(path) >= 4 and path[3].strip("/"):
            return url.rstrip('"\').,')
    return ""


def _clean_emails(html):
    out = []
    for e in EMAIL_RE.findall(html or ""):
        low = e.lower()
        if any(b in low for b in EMAIL_BLOCKLIST):
            continue
        if low not in out:
            out.append(low)
    return out


def detect(url: str, html: str) -> dict:
    html = html or ""

    ad_list = _match_keys(html, AD_PIXELS)
    analytics_list = _match_keys(html, ANALYTICS)
    cms_list = _match_keys(html, CMS_SIGNS)

    has_ads = len(ad_list) > 0
    is_mobile = bool(VIEWPORT_RE.search(html))
    is_https = url.lower().startswith("https://")

    socials = {k: _first_social(html, dom) for k, dom in SOCIAL_DOMAINS.items()}
    social_count = sum(1 for v in socials.values() if v)

    maps_m = MAPS_RE.search(html)
    google_business = maps_m.group(0) if maps_m else ""
    has_maps = bool(google_business)

    whats = WHATSAPP_RE.findall(html)
    phones = PHONE_RE.findall(html)
    emails = _clean_emails(html)
    whatsapp = whats[0] if whats else ""
    phone = phones[0] if phones else ""
    email = emails[0] if emails else ""
    reachable = bool(whatsapp or phone or email)

    # Score de oportunidade (MAIOR = melhor prospect). Maximo 100.
    score = 0
    if not has_ads:
        score += 35          # nao roda anuncio -> principal oportunidade
    if not is_mobile:
        score += 15          # site nao responsivo
    if not is_https:
        score += 10          # sem cadeado
    if social_count == 0:
        score += 20          # sem presenca social
    elif social_count == 1:
        score += 10
    if not has_maps:
        score += 10          # sem Google Maps/Meu Negocio aparente
    if reachable:
        score += 10          # da pra abordar
    opportunity_score = min(score, 100)

    return {
        "ad_pixels": ", ".join(ad_list),
        "has_ads": has_ads,
        "analytics": ", ".join(analytics_list),
        "has_analytics": len(analytics_list) > 0,
        "cms": ", ".join(cms_list) or "indefinido",
        "is_mobile": is_mobile,
        "is_https": is_https,
        "has_maps": has_maps,
        "google_business": google_business,
        "instagram": socials["instagram"],
        "facebook": socials["facebook"],
        "linkedin": socials["linkedin"],
        "youtube": socials["youtube"],
        "tiktok": socials["tiktok"],
        "twitter": socials["twitter"],
        "social_count": social_count,
        "whatsapp": whatsapp,
        "phone": phone,
        "email": email,
        "reachable": reachable,
        "opportunity_score": opportunity_score,
    }
