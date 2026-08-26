# src/vigilantia/cli.py

import json
from datetime import datetime
from urllib.parse import urlparse

import typer
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, ValidationError

from vigilantia.scraper.main import build_site_data
from vigilantia.scraper.cookie_tester import analyze_cookies
from vigilantia.analyzer.privacy_text import (
    analyze_privacy_policy_multi_page,
    extract_plain_text,
    detect_language,
    check_required_elements,
)
from vigilantia.analyzer.rule_engine import load_rules_from_file, evaluate_rules
from vigilantia.reporter import generate_html_report
from vigilantia.paths import RULES_FILE, REPORTS_DIR
from vigilantia.db.connection import get_connection
from vigilantia.db.repository import (
    WebsiteRepository,
    ScanRunRepository,
    FindingRepository,
    CompanyRepository,
)
from vigilantia.db.dashboard import report_findings_to_dashboard
from collections import Counter
from typing import Optional


# Carrega o ficheiro .env (se existir) para os.environ, ANTES de qualquer
# scan correr. Bug corrigido (Semana 2): python-dotenv já estava listado
# em requirements.txt/pyproject.toml desde a Semana 1, mas load_dotenv()
# nunca era chamado em lado nenhum — DatabaseConfig.from_env() lê
# os.getenv() diretamente, pelo que sem esta chamada as variáveis
# VIGILANTIA_DB_* do .env nunca chegavam a ser vistas pela aplicação
# (só funcionava se estivessem exportadas manualmente na shell).
load_dotenv()

app = typer.Typer(help="Vigilantia - RGPD audit tool for websites (MVP).")


class UrlModel(BaseModel):
    target_url: HttpUrl


def _slugify_domain(url: str) -> str:
    """
    Extrai o domínio de um URL e transforma-o num texto seguro para usar
    como nome de ficheiro (substitui pontos por underscores).

    Exemplo: "https://www.exemplo.pt/pagina" -> "www_exemplo_pt"

    :param url: URL completo do site.
    :return: Domínio "limpo", pronto a usar num nome de ficheiro. Se o URL
        não tiver um hostname válido, devolve "site" como valor por omissão.
    """
    domain = urlparse(url).hostname or "site"
    return domain.replace(".", "_")


def _persist_scan_start(url: str) -> Optional[int]:
    """
    Regista o início do scan na base de dados: garante que o Website
    existe (get_or_create) e cria o registo de ScanRun com Status='Running'.

    Comportamento fail-soft (decisão explícita para a Semana 2): se a
    base de dados não estiver acessível (SQL Server em baixo, driver ODBC
    em falta, credenciais erradas, etc.), esta função NUNCA interrompe o
    scan — apenas avisa no terminal e devolve None. O resto de run_scan()
    trata None como "sem persistência disponível para este scan" e
    continua exatamente como se a base de dados não existisse, incluindo
    a geração do relatório HTML. Esta escolha segue o mesmo espírito do
    bug já corrigido no fetcher.py (networkidle best-effort): uma
    dependência auxiliar não deve impedir a entrega do resultado principal.

    :param url: URL do site a analisar, tal como recebido pelo CLI.
    :return: ScanRunId (int) se o registo foi criado com sucesso, ou None
        se a base de dados não estiver disponível.
    """
    try:
        with get_connection() as conn:
            website_id = WebsiteRepository(conn).get_or_create(url)
            scan_run_id = ScanRunRepository(conn).start(website_id)
            return scan_run_id
    except Exception as exc:
        typer.echo(
            f"[BD] Aviso: não foi possível registar o início do scan na "
            f"base de dados ({exc}). A continuar sem persistência.\n"
        )
        return None


def _persist_scan_result(
    scan_run_id: Optional[int],
    findings: list,
    report_id: str,
) -> None:
    """
    Grava o resultado de um scan bem-sucedido na base de dados: um registo
    dbo.Findings por cada não-conformidade encontrada, e marca o ScanRun
    correspondente como concluído (Status='Completed'), associando o
    report_id do relatório HTML gerado (ScanRuns.ReportRef).

    Fail-soft: se scan_run_id for None (a fase inicial já falhou) ou se a
    escrita falhar agora por qualquer motivo, apenas avisa e devolve —
    nunca interrompe o fluxo do CLI, que já gerou o relatório HTML antes
    de esta função ser chamada.

    :param scan_run_id: ScanRunId devolvido por _persist_scan_start(), ou
        None se a base de dados não estava disponível no início do scan.
    :param findings: Lista de Finding encontrados pelo motor de regras.
    :param report_id: ID curto do relatório HTML gerado por
        generate_html_report(), para cruzar o ScanRun com o ficheiro.
    """
    if scan_run_id is None:
        return

    try:
        with get_connection() as conn:
            FindingRepository(conn).insert_many(scan_run_id, findings)
            ScanRunRepository(conn).complete(scan_run_id, report_ref=report_id)
    except Exception as exc:
        typer.echo(
            f"[BD] Aviso: não foi possível gravar os resultados do scan na "
            f"base de dados ({exc}).\n"
        )


def _persist_scan_failure(scan_run_id: Optional[int], error_message: str) -> None:
    """
    Marca um ScanRun como falhado (Status='Failed') quando o scraper não
    consegue sequer obter os dados do site (ver ValueError em run_scan()).

    Fail-soft: se scan_run_id for None ou a própria escrita falhar, apenas
    avisa — o erro original do scraper já foi mostrado ao utilizador antes
    de chegarmos aqui.

    :param scan_run_id: ScanRunId devolvido por _persist_scan_start(), ou
        None se a base de dados não estava disponível.
    :param error_message: Mensagem de erro do scraper, guardada em
        ScanRuns.ErrorMessage para diagnóstico posterior.
    """
    if scan_run_id is None:
        return

    try:
        with get_connection() as conn:
            ScanRunRepository(conn).fail(scan_run_id, error_message)
    except Exception as exc:
        typer.echo(
            f"[BD] Aviso: não foi possível registar a falha do scan na "
            f"base de dados ({exc}).\n"
        )


def _persist_company(url: str, company_result: Optional[dict]) -> None:
    """
    Grava na base de dados os dados da empresa dona do site (tabela Companies,
    um registo por Website), quando o scan arrancou a partir dos dados de uma
    empresa em vez de um URL. Num scan normal por URL não há nada a gravar e a
    função devolve logo.

    Fail-soft, como o resto da persistência: se a base de dados não estiver
    disponível, avisa no terminal e devolve — o relatório já está em disco e
    já contém estes dados.

    :param url: URL analisado, usado para encontrar/criar o Website.
    :param company_result: Resultado de get_company_urls(), ou None.
    """
    if not company_result:
        return

    name = (
        _clean_company_value(company_result.get("company_name"))
        or _clean_company_value(company_result.get("legal_name"))
        or url
    )

    try:
        with get_connection() as conn:
            website_id = WebsiteRepository(conn).get_or_create(url)
            CompanyRepository(conn).upsert(
                website_id,
                name=name,
                legal_name=_clean_company_value(company_result.get("legal_name")),
                nif=_clean_company_value(company_result.get("nif")),
                address=_clean_company_value(company_result.get("address")),
                registry_verified=company_result.get("registry_verified"),
                note=_clean_company_value(company_result.get("note")),
                nameservers=_company_nameservers(company_result),
            )
    except Exception as exc:
        typer.echo(
            f"[BD] Aviso: não foi possível gravar os dados da empresa na "
            f"base de dados ({exc}).\n"
        )


def _report_to_dashboard(url: str, findings: list) -> None:
    """
    Reporta as não-conformidades encontradas para o dashboard de incidências (MSSQL remoto).
    Comportamento fail-soft: se o dashboard remoto falhar, avisa no terminal e continua.
    """
    try:
        report_findings_to_dashboard(url, findings)
    except Exception as exc:
        typer.echo(
            f"[DASHBOARD] Aviso: não foi possível enviar os dados para o "
            f"dashboard remoto ({exc}).\n"
        )


# ---------------------------------------------------------------------------
# Integração com a descoberta do site a partir dos dados da empresa
#
# O motor já existe no projeto, em vigilantia/scraper/company_info.py, e é
# consumido aqui tal como está: este ficheiro não é alterado pela integração,
# e a dependência é só num sentido — o cli conhece o company_info, o
# company_info não sabe nada sobre a análise RGPD.
#
# O import é feito dentro da função, e não no topo do módulo, para que um
# problema neste componente opcional (ficheiro removido, dependência em
# falta) nunca impeça o `vigilantia scan <url>` normal de funcionar.
# ---------------------------------------------------------------------------


def _load_get_company_urls():
    """
    Importa a função get_company_urls() de vigilantia/scraper/company_info.py.

    :return: A função get_company_urls.
    :raises typer.Exit: código 1, com mensagem clara, se o import falhar.
    """
    try:
        from vigilantia.scraper.company_info import get_company_urls
        return get_company_urls
    except ImportError as exc:
        typer.echo(
            "[ERRO] Não foi possível carregar o módulo de descoberta do site da "
            f"empresa (vigilantia/scraper/company_info.py): {exc}"
        )
        raise typer.Exit(code=1)


def _clean_company_value(value):
    """
    Normaliza um valor devolvido pelo get_company_urls().

    O motor usa a string "not available" para assinalar "não encontrado" —
    útil no output JSON do script standalone, mas não é algo que se queira
    ver impresso num relatório. Convertemos esses casos (e strings vazias)
    para None, para que o template simplesmente omita o campo.

    :param value: Valor tal como veio do resultado de get_company_urls().
    :return: O valor original, ou None se não houver informação útil.
    """
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in ("", "not available"):
        return None
    return value


def _echo_company_resolution(result: dict) -> None:
    """
    Mostra no terminal o resumo da resolução do site (company_info),
    antes de a análise RGPD arrancar, para o utilizador poder confirmar que
    está prestes a auditar o site certo.

    :param result: Dicionário devolvido por get_company_urls().
    """
    typer.echo("=== Resolução do site a partir dos dados da empresa ===")
    typer.echo(f"Empresa: {_clean_company_value(result.get('company_name')) or '(sem nome)'}")

    query = _clean_company_value(result.get("query_used"))
    if query:
        typer.echo(f"Pesquisa usada: {query}")

    url = _clean_company_value(result.get("url"))
    domain = _clean_company_value(result.get("domain"))
    confidence = _clean_company_value(result.get("confidence"))
    typer.echo(f"Site: {url or '(nenhum encontrado)'}")
    if domain:
        typer.echo(f"Domínio: {domain}")
    typer.echo(f"Confiança: {confidence or 'desconhecida'}")

    nif = _clean_company_value(result.get("nif"))
    address = _clean_company_value(result.get("address"))
    email = _clean_company_value(result.get("email"))
    if nif:
        typer.echo(f"NIF: {nif}")
    if address:
        typer.echo(f"Morada: {address}")
    if email:
        typer.echo(f"Email: {email}")

    verified = result.get("registry_verified")
    if verified is True:
        typer.echo("Registo público (Racius): dados confirmados")
    elif verified is False:
        typer.echo("Registo público (Racius): dados NÃO confirmados")
    else:
        typer.echo("Registo público (Racius): não consultado")

    note = _clean_company_value(result.get("note"))
    if note:
        typer.echo(f"Nota: {note}")

    nameservers = _company_nameservers(result)
    if nameservers:
        typer.echo(f"Nameservers: {', '.join(nameservers)}")

    typer.echo("")


def _company_nameservers(result: dict) -> list:
    """
    Devolve os nameservers do resultado de get_company_urls() como lista.

    Nota: quando o WHOIS não devolve nada, o motor troca a lista vazia pela
    string "not available" — por isso não se pode assumir que este campo é
    sempre uma lista.

    :param result: Dicionário devolvido por get_company_urls().
    :return: Lista de nameservers (vazia se não houver informação).
    """
    value = _clean_company_value(result.get("nameservers"))
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(ns) for ns in value]


def _resolve_company(company_json: str, force: bool = False) -> dict:
    """
    Resolve o site oficial de uma empresa a partir dos seus dados em JSON,
    usando o company_info, e decide se a análise RGPD deve prosseguir.

    Gate de confiança aplicado ao resultado:
      - sem site encontrado -> bloqueia sempre (não há nada para analisar,
        e o --force não ajuda);
      - confidence "low"    -> bloqueia por omissão; com --force avisa e segue;
      - confidence "medium" -> avisa e segue (sem precisar de --force);
      - confidence "high"   -> segue, mensagem apenas informativa;
      - registry_verified False -> nunca bloqueia (é sobre a fiabilidade do
        NIF/morada, não sobre a identidade do site); o aviso segue também
        para o relatório final, através do campo `note`.

    :param company_json: String JSON com os dados da empresa (campo
        "company_name" obrigatório; "legal_name", "country" e "address"
        opcionais mas recomendados).
    :param force: Se True, prossegue mesmo com confiança baixa.
    :return: Dicionário de get_company_urls(), com o "legal_name" do input
        acrescentado quando existe (o resultado original não é alterado —
        trabalhamos sobre uma cópia).
    :raises typer.Exit: código 1 em qualquer erro desta fase (JSON inválido,
        falha na resolução, ou gate de confiança).
    """
    try:
        company = json.loads(company_json)
    except json.JSONDecodeError as exc:
        typer.echo(f"[ERRO] Dados da empresa inválidos: não é JSON válido ({exc.msg}).")
        typer.echo(
            "Exemplo: vigilantia scan '{\"company_name\": \"Feedzai\", \"country\": \"Portugal\"}'"
        )
        raise typer.Exit(code=1)

    if not isinstance(company, dict):
        typer.echo("[ERRO] Os dados da empresa têm de ser um objeto JSON (ex: {\"company_name\": \"...\"}).")
        raise typer.Exit(code=1)

    company_name = str(company.get("company_name") or "").strip()
    if not company_name:
        typer.echo("[ERRO] Falta o campo obrigatório \"company_name\" nos dados da empresa.")
        raise typer.Exit(code=1)

    get_company_urls = _load_get_company_urls()

    typer.echo(f"\nA procurar o site oficial de: {company_name}\n")
    try:
        result = get_company_urls(company)
    except Exception as exc:
        typer.echo(f"[ERRO] Não foi possível resolver o site da empresa ({exc}).")
        raise typer.Exit(code=1)

    if not isinstance(result, dict):
        typer.echo("[ERRO] A descoberta do site devolveu um resultado inesperado.")
        raise typer.Exit(code=1)

    # Cópia local: o resultado devolvido nunca é alterado no sítio.
    result = dict(result)
    # O motor não devolve "legal_name" (só o usa para pesquisar e validar),
    # por isso transportamos o que veio no input para o relatório e para a
    # base de dados. Se não foi fornecido, fica ausente — o nome comercial
    # (company_name) é usado como alternativa onde for preciso mostrar um nome.
    if not _clean_company_value(result.get("legal_name")):
        result["legal_name"] = _clean_company_value(company.get("legal_name"))

    _echo_company_resolution(result)

    url = _clean_company_value(result.get("url"))
    if not url:
        typer.echo(
            "[ERRO] Não foi encontrado nenhum site oficial para esta empresa — "
            "sem URL não há nada para analisar (o --force não resolve este caso)."
        )
        typer.echo(
            "Sugestão: acrescentar \"legal_name\" e/ou \"address\" aos dados da "
            "empresa, ou analisar o site diretamente com: vigilantia scan <url>"
        )
        raise typer.Exit(code=1)

    confidence = str(_clean_company_value(result.get("confidence")) or "").lower()

    if confidence == "low":
        if not force:
            typer.echo(
                f"[ERRO] Confiança BAIXA em {url} como site oficial de \"{company_name}\". "
                "Análise cancelada para não auditar o site errado."
            )
            typer.echo(
                "Sugestões: acrescentar \"legal_name\" e/ou \"address\" aos dados da "
                "empresa para melhorar a pesquisa, ou repetir o comando com --force "
                "se este for mesmo o site pretendido."
            )
            raise typer.Exit(code=1)
        typer.echo(
            f"[AVISO] Confiança BAIXA em {url}, mas foi pedido --force: a prosseguir. "
            "Confirmar que o relatório diz respeito ao site certo.\n"
        )
    elif confidence == "medium":
        typer.echo(
            f"[AVISO] Confiança MÉDIA em {url} como site oficial. A análise prossegue, "
            "mas convém confirmar o site antes de usar o relatório.\n"
        )

    if result.get("registry_verified") is False:
        typer.echo(
            "[AVISO] NIF/morada obtidos no registo público NÃO foram confirmados — "
            "podem pertencer a outra empresa com nome semelhante. Este aviso fica "
            "também registado no relatório final.\n"
        )

    return result


def run_scan(    url: str,
    company_result: Optional[dict] = None,
) -> None:
    """
    Executa a análise RGPD completa para o URL indicado:
    - scraping real do site (Playwright + extractor)
    - análise da política de privacidade
    - avaliação das regras RGPD (motor de regras)
    - teste de cookies pré-consentimento
    - geração do relatório HTML (com histórico em /reports)

    Esta função é partilhada pelos dois pontos de entrada do projeto
    (o comando `vigilantia scan <url>` e o script interativo
    run_vigilantia_mvp.py), para evitar lógica duplicada e divergente.

    :param url: URL do site a analisar.
    :param company_result: Resultado de get_company_urls() (opcional). Quando o
        scan arranca a partir dos dados de uma empresa, os campos relevantes
        (nome legal, NIF, morada, verificação no registo público, nota e
        nameservers) são juntos ao SiteData para aparecerem no relatório.
        São puramente informativos: o motor de regras RGPD não os lê, pelo
        que nenhuma regra muda de resultado por causa deles.
    """
    typer.echo(f"\nA iniciar análise RGPD para: {url}\n")

    # 0) Regista o início do scan na base de dados (Website + ScanRun).
    # Fail-soft: se a BD não estiver disponível, scan_run_id fica None e
    # o resto do scan prossegue normalmente, só sem persistência.
    scan_run_id = _persist_scan_start(url)

    # 1) Scraper → SiteData (scripts, formulários, cookies, política, banner)
    try:
        site_data = build_site_data(url)
    except ValueError as exc:
        typer.echo(f"Erro no scraper: {exc}")
        _persist_scan_failure(scan_run_id, str(exc))
        raise typer.Exit(code=1)

    # 1b) Dados da empresa (opcional) → SiteData
    #
    # Quando o scan arrancou a partir dos dados de uma empresa (company_info),
    # juntamos aqui os campos devolvidos por esse script ao SiteData, usando
    # model_copy(update=...) — o padrão Pydantic já usado no resto do projeto.
    # A partir deste ponto o SiteData transporta também a identificação da
    # empresa, que o reporter usa para a secção "Dados da empresa" do
    # relatório HTML. Num scan normal por URL, company_result é None e nada
    # disto acontece.
    if company_result:
        site_data = site_data.model_copy(
            update={
                "company_legal_name": (
                    _clean_company_value(company_result.get("legal_name"))
                    or _clean_company_value(company_result.get("company_name"))
                ),
                "company_nif": _clean_company_value(company_result.get("nif")),
                "company_address": _clean_company_value(company_result.get("address")),
                "company_registry_verified": company_result.get("registry_verified"),
                "company_note": _clean_company_value(company_result.get("note")),
                "company_nameservers": _company_nameservers(company_result),
            }
        )

    # 2) Política de privacidade → flags (direitos RGPD mencionados no texto)
    #
    # Bug corrigido: antes, uma falha de download deixava policy_flags={},
    # e o motor de regras interpretava "flag ausente" como "elemento RGPD
    # não mencionado", gerando 5 findings falsos (R06-R10). Agora marcamos
    # explicitamente com "_policy_unreachable" quando NENHUMA página pôde
    # ser lida, para o motor de regras gerar um único aviso (R12) em vez
    # disso.
    #
    # Melhoria: em vez de analisar só a página da política principal,
    # seguimos também um pequeno número de páginas legais relacionadas do
    # mesmo site (cookies, termos, contactos, RGPD/DPO dedicado), porque
    # muitos sites espalham a informação exigida pelo RGPD por várias
    # páginas (ex.: contacto do DPO só na página de "Contactos").
    policy_flags: dict = {}
    policy_pages_analyzed: list = []
    if site_data.privacy_policy_url is not None:
        try:
            policy_flags, policy_evidence_urls, policy_pages_analyzed = (
                analyze_privacy_policy_multi_page(str(site_data.privacy_policy_url))
            )
            if len(policy_pages_analyzed) > 1:
                typer.echo(
                    f"Política de privacidade analisada em {len(policy_pages_analyzed)} "
                    f"páginas relacionadas do site:"
                )
                for page in policy_pages_analyzed:
                    typer.echo(f"  - {page}")
                typer.echo("")
        except ValueError as exc:
            typer.echo(f"Erro ao analisar política de privacidade: {exc}")
            policy_flags = {"_policy_unreachable": True}

    # 3) Motor de regras → findings
    rules_config = load_rules_from_file(str(RULES_FILE))
    findings = evaluate_rules(site_data, rules_config, policy_flags)

    # 4) Resumo de severidades
    severity_counts = Counter(f.severity for f in findings)
    typer.echo("=== Resumo de severidades ===")
    typer.echo(f"Problemas graves (high): {severity_counts.get('high', 0)}")
    typer.echo(f"Problemas médios (medium): {severity_counts.get('medium', 0)}")
    typer.echo(f"Problemas baixos (low): {severity_counts.get('low', 0)}")
    typer.echo("")

    # 5) Lista detalhada de não-conformidades
    if findings:
        typer.echo("=== Detalhe das não-conformidades ===")
        for f in findings:
            typer.echo(f"[{f.severity.upper()}] {f.id}")
            typer.echo(f"  {f.description}")
            typer.echo(f"  Recomendação: {f.recommendation}")
            if isinstance(f.evidence, dict):
                typer.echo(f"  Evidência: {f.evidence.get('message')}")
            else:
                typer.echo(f"  Evidência: {f.evidence}")
            typer.echo("")
    else:
        typer.echo("Nenhuma não-conformidade RGPD detetada nas regras atuais.\n")

    # 6) Teste de cookies pré-consentimento
    typer.echo("=== Teste de Cookies Pré-Consentimento ===")
    cookies = site_data.cookies
    typer.echo(f"Foram encontrados {len(cookies)} cookies instalados ANTES de qualquer consentimento.")

    analysis = analyze_cookies(cookies, url)
    tracking_cookies = analysis.get("Tracking/Analytics", [])

    if tracking_cookies:
        typer.echo(f"\n>> ATENÇÃO: Foram detetados {len(tracking_cookies)} cookies de tracking/analytics!")
        for idx, c in enumerate(tracking_cookies, 1):
            typer.echo(f"  {idx}. Nome: {c.name} | Domínio: {c.domain}")
        typer.echo("Isto é uma possível violação grave do RGPD (falta de opt-in).")
    else:
        typer.echo("\n>> Não foram detetados cookies de tracking óbvios antes do consentimento.")
    typer.echo("")

    # 7) Geração do relatório HTML, com histórico por site + timestamp
    html, report_id = generate_html_report(
        site_url=url,
        findings=findings,
        total_cookies=len(cookies),
        tracking_cookies=tracking_cookies,
        site_data=site_data,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS_DIR / f"vigilantia_{_slugify_domain(url)}_{timestamp}.html"
    report_path.write_text(html, encoding="utf-8")

    # Mantém também uma cópia "relatorio.html" na raiz, com o resultado mais recente,
    # para compatibilidade com quem já usa esse nome de ficheiro.
    latest_path = REPORTS_DIR.parent / "relatorio.html"
    latest_path.write_text(html, encoding="utf-8")

    typer.echo(f"[+] Relatório guardado em: {report_path}")
    typer.echo(f"[+] Última versão também disponível em: {latest_path}\n")

    # 8) Grava os findings na base de dados e conclui o ScanRun.
    # Fail-soft: corre DEPOIS do relatório já estar em disco, para que uma
    # falha aqui nunca ponha em causa a entrega do relatório ao utilizador.
    _persist_scan_result(scan_run_id, findings, report_id)

    # 8b) Grava os dados da empresa (tabela Companies), se este scan tiver
    # arrancado a partir dos dados de uma empresa. Também fail-soft.
    _persist_company(url, company_result)

    # 9) Envia as não-conformidades para o dashboard de incidências (MSSQL remoto).
    # Fail-soft: falhas no dashboard não impedem o fim do scan.
    _report_to_dashboard(url, findings)


@app.command()
def scan(
    target: str = typer.Argument(
        ...,
        help=(
            "URL do site (ex: https://example.com) OU os dados da empresa em JSON "
            "(ex: '{\"company_name\": \"Feedzai\", \"country\": \"Portugal\"}'), "
            "caso em que o site oficial é descoberto automaticamente."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Analisar mesmo quando a confiança na identificação do site a partir "
            "dos dados da empresa for baixa. Não tem efeito quando é passado um URL."
        ),
    ),
):
    """
    Comando do Typer que expõe run_scan() na linha de comandos.

    Aceita duas formas do mesmo pedido:

      1. Um URL, como sempre:
         vigilantia scan https://exemplo.pt

      2. Os dados da empresa em JSON (começa por "{"), caso em que o site
         oficial é primeiro descoberto pelo company_info e só depois
         analisado — e os dados da empresa (NIF, morada, verificação no
         registo público, nameservers) passam a constar do relatório:
         vigilantia scan '{\"company_name\": \"Feedzai\", \"country\": \"Portugal\"}'

    Como esta é a única @app.command() definida, o Typer trata-a como
    comando por omissão da aplicação — ou seja, usa-se
    "vigilantia https://exemplo.pt" diretamente, sem escrever a palavra
    "scan" (isso daria erro de "unexpected extra argument").

    Em ambos os casos, antes de chamar run_scan() valida-se o formato do URL
    com o UrlModel (Pydantic), para dar um erro claro em português caso o URL
    esteja mal formado, em vez de deixar o erro rebentar mais fundo no scraper.

    :param target: URL do site a analisar, ou JSON com os dados da empresa.
    :param force: Prosseguir mesmo com confiança baixa na resolução do site
        (só se aplica quando é passado o JSON da empresa).
    """
    company_result = None

    if target.lstrip().startswith("{"):
        # Fase de resolução da empresa: qualquer erro aqui (JSON inválido,
        # falha na pesquisa, confiança insuficiente) termina com código 1,
        # antes de o scraper sequer arrancar.
        company_result = _resolve_company(target, force=force)
        url = _clean_company_value(company_result.get("url"))
    else:
        url = target
        if force:
            typer.echo(
                "[AVISO] --force só se aplica quando são passados os dados da "
                "empresa em JSON; a ser ignorado.\n"
            )

    try:
        UrlModel(target_url=url)
    except ValidationError:
        typer.echo("URL inválido. Por favor, forneça um URL completo (ex: https://example.com).")
        raise typer.Exit(code=1)

    run_scan(url, company_result=company_result)


def main():
    """
    Ponto de entrada do pacote instalado (ver [project.scripts] em
    pyproject.toml, que liga o comando "vigilantia" a esta função).
    Delega toda a lógica de parsing de argumentos para a aplicação Typer.
    """
    app()


if __name__ == "__main__":
    main()
