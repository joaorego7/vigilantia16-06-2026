# tests/test_scraper.py

from vigilantia.scraper.extractor import (
    extract_third_party_scripts,
    extract_forms,
    extract_privacy_policy_url,
    detect_consent_banner,
    build_site_data,
    find_related_legal_links,
)


def test_extract_third_party_scripts_basic():
    # Comentário:
    # HTML de exemplo com um script interno e um script de terceiros.
    html = """
    <html>
      <head>
        <script src="/static/app.js"></script>
        <script src="https://analytics.example.com/script.js"></script>
      </head>
      <body></body>
    </html>
    """

    scripts = extract_third_party_scripts(html, page_url="https://example.com")
    assert len(scripts) == 1
    # Comentário:
    # Convertendo o HttpUrl em string para verificar o domínio.
    assert "analytics.example.com" in str(scripts[0].src)



def test_extract_forms_basic():
    html = """
    <html>
      <body>
        <form action="/submit" method="post">
          <input type="text" name="email" />
          <input type="password" name="password" />
        </form>
      </body>
    </html>
    """

    forms = extract_forms(html, page_url="https://example.com")
    assert len(forms) == 1
    form = forms[0]
    assert form.method == "POST"
    assert "email" in form.fields
    assert "password" in form.fields


def test_extract_privacy_policy_url_basic():
    html = """
    <html>
      <body>
        <a href="/privacy">Política de Privacidade</a>
      </body>
    </html>
    """

    url = extract_privacy_policy_url(html, page_url="https://example.com")
    assert url == "https://example.com/privacy"


def test_detect_consent_banner_basic():
    html = """
    <html>
      <body>
        <div>Este site utiliza cookies. Por favor, aceite cookies para continuar.</div>
      </body>
    </html>
    """

    detected = detect_consent_banner(html)
    assert detected is True


def test_build_site_data_basic():
    html = """
    <html>
      <head>
        <script src="/static/app.js"></script>
        <script src="https://analytics.example.com/script.js"></script>
      </head>
      <body>
        <form action="/submit" method="post">
          <input type="text" name="email" />
        </form>
        <a href="/privacy">Política de Privacidade</a>
        <div>Este site utiliza cookies. Por favor, aceite cookies para continuar.</div>
      </body>
    </html>
    """

    site_data = build_site_data(
        html=html,
        page_url="https://example.com",
        final_url="https://example.com",
        language="pt",
    )

    assert len(site_data.third_party_scripts) == 1
    assert len(site_data.forms) == 1
    assert str(site_data.privacy_policy_url) == "https://example.com/privacy"
    assert site_data.consent_banner_detected is True


def test_find_related_legal_links_matches_by_link_text():
    """
    Deve encontrar links para páginas legais relacionadas (cookies, termos,
    contactos) a partir do texto visível do link, mantendo só o mesmo domínio.
    """
    html = """
    <html>
      <body>
        <footer>
          <a href="/politica-cookies">Política de Cookies</a>
          <a href="/termos-condicoes">Termos e Condições</a>
          <a href="/contactos">Contactos</a>
          <a href="/sobre-nos">Sobre Nós</a>
          <a href="https://outro-dominio.com/privacidade">Política de outro site</a>
        </footer>
      </body>
    </html>
    """
    links = find_related_legal_links(html, page_url="https://example.com/politica-de-privacidade")

    assert "https://example.com/politica-cookies" in links
    assert "https://example.com/termos-condicoes" in links
    assert "https://example.com/contactos" in links
    # "Sobre Nós" não é uma página legal/RGPD, não deve ser incluída.
    assert "https://example.com/sobre-nos" not in links
    # Domínio diferente, não deve ser seguido mesmo com texto relevante.
    assert "https://outro-dominio.com/privacidade" not in links


def test_find_related_legal_links_respects_max_links_and_exclude():
    """
    Deve respeitar o limite max_links e não repetir URLs já em exclude_urls.
    """
    html = """
    <html>
      <body>
        <a href="/cookies">Cookies</a>
        <a href="/termos">Termos</a>
        <a href="/contactos">Contactos</a>
        <a href="/rgpd">RGPD</a>
      </body>
    </html>
    """
    links = find_related_legal_links(
        html,
        page_url="https://example.com/privacidade",
        exclude_urls={"https://example.com/cookies"},
        max_links=2,
    )

    assert "https://example.com/cookies" not in links
    assert len(links) == 2