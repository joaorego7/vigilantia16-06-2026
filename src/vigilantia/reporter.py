# src/vigilantia/reporter.py
import hashlib
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from typing import List

from vigilantia.models.finding import Finding
from vigilantia.paths import TEMPLATES_DIR

# Comentário:
# Ordem de gravidade usada para ordenar os findings no relatório
# (do mais grave para o menos grave), em vez de aparecerem pela
# ordem arbitrária em que as regras correm no motor.
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def generate_html_report(
    site_url: str, 
    findings: List[Finding],
    total_cookies: int = 0,
    tracking_cookies: list = None
) -> str:
    high = sum(1 for f in findings if f.severity == "high")
    medium = sum(1 for f in findings if f.severity == "medium")
    low = sum(1 for f in findings if f.severity == "low")

    # Ordenar por gravidade (high -> medium -> low) para leitura mais direta.
    sorted_findings = sorted(
        findings,
        key=lambda f: _SEVERITY_ORDER.get(f.severity, 99),
    )

    generated_at = datetime.now()

    # ID curto do relatório, derivado do site + timestamp, só para referência
    # (ex.: citar num relatório de estágio: "scan #a3f21c").
    report_id = hashlib.sha1(
        f"{site_url}-{generated_at.isoformat()}".encode("utf-8")
    ).hexdigest()[:8]

    # Comentário (bug corrigido):
    # Antes usava-se FileSystemLoader("templates"), um caminho relativo que
    # só funcionava se o comando fosse executado a partir da raiz do
    # repositório. Agora usamos o caminho absoluto de paths.py.
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.html.j2")

    html = template.render(
        site_url=site_url,
        findings=sorted_findings,
        summary={"high": high, "medium": medium, "low": low},
        total_cookies=total_cookies,
        tracking_cookies=tracking_cookies or [],
        report_id=report_id,
        generated_at=generated_at.strftime("%d/%m/%Y %H:%M"),
        legal_disclaimer=(
            "Esta ferramenta é apenas um apoio técnico e não substitui uma auditoria jurídica profissional."
        ),
    )
    return html