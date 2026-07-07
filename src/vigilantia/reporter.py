# src/vigilantia/reporter.py
from jinja2 import Environment, FileSystemLoader
from typing import List

from vigilantia.models.finding import Finding  # ajusta este caminho ao teu projeto

def generate_html_report(
    site_url: str, 
    findings: List[Finding],
    total_cookies: int = 0,
    tracking_cookies: list = None
) -> str:
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    low = sum(1 for f in findings if f.severity == "low")

    env = Environment(loader=FileSystemLoader("templates"))
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