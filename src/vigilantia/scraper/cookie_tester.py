# src/vigilantia/scraper/cookie_tester.py

from typing import List, Dict, Any, Union

def classify_cookie(cookie: Any, url: str) -> str:
    """
    Classifica um único cookie em duas categorias possíveis: "Tracking/Analytics"
    (cookies conhecidos de publicidade/análise de terceiros) ou
    "Desconhecido/Necessário/Funcional" (tudo o resto).

    A classificação é feita por duas heurísticas simples, aplicadas por ordem:
      1. Nome do cookie começa por/é igual a um nome conhecido (ex.: "_ga", "_fbp");
      2. Domínio do cookie termina num domínio conhecido de tracking (ex.: ".google.com").
    Se nenhuma das duas corresponder, o cookie é considerado "Desconhecido/
    Necessário/Funcional" — o que NÃO significa necessariamente que seja seguro;
    apenas que não bate certo com nenhum padrão conhecido nesta lista.

    :param cookie: O cookie a classificar. Aceita tanto um dicionário (formato
        devolvido pelo Playwright) como um objeto do modelo Cookie (Pydantic).
    :param url: URL do site a que o cookie pertence. Atualmente não é usado
        dentro da função (a classificação é feita só pelo nome/domínio do
        cookie), mas mantém-se como parâmetro para permitir, no futuro,
        comparar o domínio do cookie com o domínio do site analisado.
    :return: Uma das duas strings: "Tracking/Analytics" ou
        "Desconhecido/Necessário/Funcional".
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
    Analisa uma lista de cookies e agrupa-os por classificação, chamando
    classify_cookie() para cada um.

    Usado principalmente para isolar rapidamente os cookies de tracking
    (chave "Tracking/Analytics" do dicionário devolvido), que é o que a
    secção "Teste de Cookies Pré-Consentimento" do CLI apresenta ao utilizador.

    :param cookies: Lista de cookies a analisar (dicionários ou objetos Cookie).
    :param url: URL do site a que os cookies pertencem (ver nota em classify_cookie).
    :return: Dicionário com duas chaves fixas — "Tracking/Analytics" e
        "Desconhecido/Necessário/Funcional" — cada uma associada à lista de
        cookies que caíram nessa categoria.
    """
    results = {
        "Tracking/Analytics": [],
        "Desconhecido/Necessário/Funcional": []
    }

    for cookie in cookies:
        classification = classify_cookie(cookie, url)
        results[classification].append(cookie)

    return results
