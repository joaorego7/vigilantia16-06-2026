# tests/test_models.py

from vigilantia.models.site_data import SiteData, Cookie, ThirdPartyScript, Form
from vigilantia.models.finding import Finding
from pydantic import HttpUrl

# Comentário:
# Este teste verifica se conseguimos criar instâncias básicas dos modelos,
# garantindo que o "contrato" de dados é válido.
def test_create_basic_models():
    cookie = Cookie(
        name="_ga",
        domain=".example.com",
        path="/",
        secure=True,
        httpOnly=True,
        sameSite="Lax",
    )

    script = ThirdPartyScript(
        src="https://analytics.example.com/script.js",
        category="analytics",
    )

    form = Form(
        action="/submit",
        method="POST",
        fields=["email", "password"],
    )

    site_data = SiteData(
        url="https://example.com",
        final_url="https://example.com/home",
        language="en",
        cookies=[cookie],
        third_party_scripts=[script],
        forms=[form],
        privacy_policy_url="https://example.com/privacy",
        consent_banner_detected=True,
    )

    finding = Finding(
        id="R01",
        severity="high",
        description="Test finding",
        evidence={"cookies": ["_ga"]},
        recommendation="Add consent banner",
    )

    assert str(site_data.url) in {"https://example.com/", "https://example.com"}
    assert finding.id == "R01"