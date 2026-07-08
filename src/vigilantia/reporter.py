# src/vigilantia/reporter.py
from jinja2 import Environment, FileSystemLoader
from typing import List

from vigilantia.models.finding import Finding
from vigilantia.paths import TEMPLATES_DIR

def generate_html_report(
    site_url: str, 
    findings: List[Finding],
    total_cookies: int = 0,
    tracking_cookies: list = None
) -> str:
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    low = sum(1 for f in findings if f.severity == "low")

    # Comentário (bug corrigido):
    # Antes usava-se FileSystemLoader("templates"), um caminho relativo que
    # só funcionava se o comando fosse executado a partir da raiz do
    # repositório. Agora usamos o caminho absoluto de paths.py.
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.html.j2")

    html = template.render(
        site_url=site_url,
        findings=findings,
        summary={"high": high, "medium": medium, "low": low},
        total_cookies=total_cookies,
        tracking_cookies=tracking_cookies or [],
        legal_disclaimer=(
            "Esta ferramenta é apenas um apoio técnico e não substitui uma auditoria jurídica profissional."
        ),
    )
    return html