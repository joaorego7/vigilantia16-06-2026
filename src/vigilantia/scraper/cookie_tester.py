# src/vigilantia/scraper/cookie_tester.py

from typing import List, Dict, Any, Union

def classify_cookie(cookie: Any, url: str) -> str:
    """
    Classifica um cookie como 'Estritamente Necessário' ou 'Tracking/Outros'
    com base no seu nome e domínio. Aceita dicionários ou objetos do modelo Cookie.
    """
    if isinstance(cookie, dict):
        name = cookie.get("name", "").lower()
        domain = cookie.get("domain", "").lower()
    else:
        name = getattr(cookie, "name", "").lower()
        domain = getattr(cookie, "domain", "").lower()

    # Nomes conhecidos de cookies de tracking/analytics
    tracking_names = [
        "_ga", "_gid", "_gat", "amp_token", "_gac_", "__utma", "__utmb", "__utmc", "__utmt", "__utmz", # Google Analytics
        "_fbp", "_fbc", "fr", "tr", # Facebook
        "_pin_unauth", # Pinterest
        "uid", "ouid", "tuuid", # Vários ad networks
        "_tt_enable_cookie", "_ttp", # TikTok
        "lidc", "bcookie", "bscookie", # LinkedIn
        "muc_optin", "guest_id", "personalization_id", # Twitter
        "yandexuid", "ymex" # Yandex
    ]

    # Domínios conhecidos de tracking/ads
    tracking_domains = [
        ".google.com", ".doubleclick.net", ".facebook.com", ".twitter.com", 
        ".linkedin.com", ".tiktok.com", ".pinterest.com", ".amazon-adsystem.com",
        ".bing.com", "ads.yahoo.com"
    ]

    # Verifica pelo nome
    if any(name.startswith(tn) or name == tn for tn in tracking_names):
        return "Tracking/Analytics"

    # Verifica pelo domínio
    if any(domain.endswith(td) for td in tracking_domains):
        return "Tracking/Analytics"

    # Assume "Possível Necessário ou Funcional" para os restantes,
    # embora na prática possam ser tracking de primeira parte não conhecidos.
    return "Desconhecido/Necessário/Funcional"

def analyze_cookies(cookies: List[Any], url: str) -> Dict[str, List[Any]]:
    """
    Analisa uma lista de cookies e agrupa-os pela sua classificação.
    """
    results = {
        "Tracking/Analytics": [],
        "Desconhecido/Necessário/Funcional": []
    }

    for cookie in cookies:
        classification = classify_cookie(cookie, url)
        results[classification].append(cookie)

    return results
