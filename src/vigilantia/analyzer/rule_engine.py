from typing import List, Dict

import yaml
from pydantic import BaseModel

from vigilantia.models.site_data import SiteData
from vigilantia.models.finding import Finding


class RuleDefinition(BaseModel):
    """
    Representa UMA regra RGPD, tal como está definida no ficheiro
    rules/gdpr_rules.yaml. Cada campo corresponde a uma chave do YAML.

    Campos:
      - id: identificador único da regra (ex.: "R05"). É esta string que liga
        a definição (aqui, no YAML) à lógica de deteção (em evaluate_rules).
      - name: nome curto da regra, em inglês por convenção neste ficheiro.
      - description: explicação do problema que a regra deteta.
      - check: descrição em texto livre da condição verificada (é só
        documentação/legibilidade — não é código executado automaticamente).
      - severity: gravidade da regra ("high", "medium" ou "low").
      - article: artigo do RGPD relevante, para referência jurídica.
      - recommendation: sugestão de correção, mostrada ao utilizador no relatório.
    """
    id: str
    name: str
    description: str
    check: str
    severity: str
    article: str
    recommendation: str


class RulesConfig(BaseModel):
    """
    Contentor simples que agrupa todas as RuleDefinition carregadas do YAML.
    """
    rules: List[RuleDefinition]


def load_rules_from_file(path: str) -> RulesConfig:
    """
    Lê o ficheiro YAML de regras (ex.: rules/gdpr_rules.yaml) e converte-o
    num objeto RulesConfig validado pelo Pydantic.

    Se o YAML tiver uma regra com um campo em falta ou de tipo errado, o
    Pydantic levanta um erro de validação aqui mesmo, antes de a aplicação
    tentar usar essa regra — o que evita erros mais confusos mais tarde.

    :param path: Caminho para o ficheiro YAML de regras.
    :return: Objeto RulesConfig com a lista de regras carregadas.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    return RulesConfig(**raw_data)


def evaluate_rules(
    site_data: SiteData,
    rules_config: RulesConfig,
    policy_flags: Dict[str, bool],
) -> List[Finding]:
    """
    Função central do motor de regras: recebe os dados recolhidos do site
    (SiteData), a configuração de regras carregada do YAML (RulesConfig) e
    as "flags" resultantes da análise de texto da política de privacidade
    (policy_flags — ex.: {"dpo_contact": True, "retention_period": False}),
    e devolve a lista de não-conformidades (Finding) encontradas.

    Cada bloco de código abaixo corresponde a UMA regra (R01, R02, ..., R11):
    testa uma condição sobre site_data/policy_flags e, se a condição indicar
    um problema, procura a definição correspondente em rules_config (pelo
    "id") e cria um Finding com a severidade/descrição/recomendação vindas
    do YAML. Se a regra não estiver definida no YAML (maybe_rule is None),
    a condição é ignorada e nenhum finding é criado para essa regra — por
    isso é importante manter o YAML e este ficheiro sincronizados (ver
    comentário no topo de rules/gdpr_rules.yaml).

    :param site_data: Dados estruturados do site, recolhidos pelo scraper
        (cookies, scripts de terceiros, formulários, banner de consentimento, etc.).
    :param rules_config: Configuração de regras carregada do YAML (ver load_rules_from_file).
    :param policy_flags: Dicionário de flags sobre o conteúdo da política de
        privacidade (devolvido por check_required_elements em privacy_text.py).
        Fica vazio ({}) se não houver política de privacidade para analisar.
    :return: Lista de objetos Finding, um por cada não-conformidade detetada.
    """

    # Comentário:
    # 'findings' tem de ser inicializada aqui, ANTES de qualquer regra a usar.
    # (Bug corrigido: antes estava declarada a meio da função, depois de já
    # ser usada em R01-R04, o que causava UnboundLocalError em tempo de execução.)
    findings: List[Finding] = []

    # =========================
    # R01 - Banner de consentimento de cookies ausente
    # =========================
    has_banner = site_data.consent_banner_detected
    from vigilantia.scraper.cookie_tester import classify_cookie
    has_tracking_cookies = any(
        classify_cookie(cookie, str(site_data.final_url)) == "Tracking/Analytics"
        for cookie in (site_data.cookies or [])
    )

    if not has_banner and has_tracking_cookies:
        maybe_rule = next(
            (rule for rule in rules_config.rules if rule.id == "R01"),
            None,
        )

        if maybe_rule is not None:
            finding = Finding(
                id=maybe_rule.id,
                severity=maybe_rule.severity,
                description=maybe_rule.description,
                recommendation=maybe_rule.recommendation,
                evidence={
                    "message": (
                        "Foram encontrados cookies de rastreio "
                        "sem qualquer banner de consentimento visível."
                    ),
                },
            )
            findings.append(finding)

    # =========================
    # R02 - Cookies de rastreio carregados antes do consentimento
    # =========================
    # (Numa versão simples, assume-se que os cookies encontrados
    # foram carregados antes da obtenção de consentimento.)

    if has_tracking_cookies and not has_banner:
        maybe_rule = next(
            (rule for rule in rules_config.rules if rule.id == "R02"),
            None,
        )

        if maybe_rule is not None:
            finding = Finding(
                id=maybe_rule.id,
                severity=maybe_rule.severity,
                description=maybe_rule.description,
                recommendation=maybe_rule.recommendation,
                evidence={
                    "message": (
                        "Foram encontrados cookies de rastreio "
                        "antes da obtenção de consentimento."
                    ),
                },
            )
            findings.append(finding)

    # =========================
    # R03 - Scripts de analytics sem anonimização de IP
    # =========================
    for script in site_data.third_party_scripts or []:
        # Comentário (bug corrigido):
        # script.src é um HttpUrl do Pydantic, não uma string — não suporta
        # o operador "in" diretamente. É preciso converter para str primeiro.
        script_src = str(script.src)
        if (
            "google-analytics" in script_src
            or "gtag/js" in script_src
        ):
            has_anonymize_ip = (
                "anonymize_ip" in getattr(script, "config", "")
            )

            if not has_anonymize_ip:
                maybe_rule = next(
                    (rule for rule in rules_config.rules if rule.id == "R03"),
                    None,
                )

                if maybe_rule is not None:
                    finding = Finding(
                        id=maybe_rule.id,
                        severity=maybe_rule.severity,
                        description=maybe_rule.description,
                        recommendation=maybe_rule.recommendation,
                        evidence={
                            "message": (
                                "Foi detetado Google Analytics sem "
                                "anonimização de IP."
                            ),
                            "script": script_src,
                        },
                    )
                    findings.append(finding)

    # =========================
    # R04 - Cookies sem atributo Secure ou HttpOnly
    # =========================
    insecure_cookies = [
        cookie.name
        for cookie in (site_data.cookies or [])
        if (not cookie.secure or not cookie.httpOnly)
    ]

    if insecure_cookies:
        maybe_rule = next(
            (rule for rule in rules_config.rules if rule.id == "R04"),
            None,
        )

        if maybe_rule is not None:
            finding = Finding(
                id=maybe_rule.id,
                severity=maybe_rule.severity,
                description=maybe_rule.description,
                recommendation=maybe_rule.recommendation,
                evidence={
                    "message": (
                        "Foram encontrados cookies sem atributos "
                        "Secure/HttpOnly adequados."
                    ),
                    "cookies": insecure_cookies,
                },
            )
            findings.append(finding)

    # =========================
    # R05 - Política de privacidade ausente ou inacessível
    # =========================
    if site_data.privacy_policy_url is None:
        maybe_rule = next(
            (rule for rule in rules_config.rules if rule.id == "R05"),
            None,
        )

        if maybe_rule is not None:
            finding = Finding(
                id=maybe_rule.id,
                severity=maybe_rule.severity,
                description=maybe_rule.description,
                recommendation=maybe_rule.recommendation,
                evidence={
                    "message": (
                        "Não foi encontrado qualquer link para política "
                        "de privacidade na página analisada."
                    ),
                    "privacy_policy_url": None,
                },
            )
            findings.append(finding)

    # =========================
    # R06 - Política não menciona direito de acesso
    # =========================
    if site_data.privacy_policy_url is not None and not policy_flags.get("_policy_unreachable", False):
        has_right_access = policy_flags.get("right_access", False)

        if not has_right_access:
            maybe_rule = next(
                (rule for rule in rules_config.rules if rule.id == "R06"),
                None,
            )

            if maybe_rule is not None:
                finding = Finding(
                    id=maybe_rule.id,
                    severity=maybe_rule.severity,
                    description=maybe_rule.description,
                    recommendation=maybe_rule.recommendation,
                    evidence={
                        "message": (
                            "Texto da política de privacidade analisado "
                            "não contém referência ao direito de acesso aos dados."
                        ),
                        "flag": "right_access",
                        "value": False,
                    },
                )
                findings.append(finding)

    # =========================
    # R07 - Política não menciona direito ao apagamento
    # =========================
    if site_data.privacy_policy_url is not None and not policy_flags.get("_policy_unreachable", False):
        has_right_erasure = policy_flags.get("right_erasure", False)

        if not has_right_erasure:
            maybe_rule = next(
                (rule for rule in rules_config.rules if rule.id == "R07"),
                None,
            )

            if maybe_rule is not None:
                finding = Finding(
                    id=maybe_rule.id,
                    severity=maybe_rule.severity,
                    description=maybe_rule.description,
                    recommendation=maybe_rule.recommendation,
                    evidence={
                        "message": (
                            "Texto da política de privacidade analisado "
                            "não contém referência ao direito ao apagamento "
                            "/ direito a ser esquecido."
                        ),
                        "flag": "right_erasure",
                        "value": False,
                    },
                )
                findings.append(finding)

    # =========================
    # R08 - Política não menciona transferências internacionais
    # =========================
    if site_data.privacy_policy_url is not None and not policy_flags.get("_policy_unreachable", False):
        has_international_transfers = policy_flags.get(
            "international_transfers",
            False,
        )

        if not has_international_transfers:
            maybe_rule = next(
                (rule for rule in rules_config.rules if rule.id == "R08"),
                None,
            )

            if maybe_rule is not None:
                finding = Finding(
                    id=maybe_rule.id,
                    severity=maybe_rule.severity,
                    description=maybe_rule.description,
                    recommendation=maybe_rule.recommendation,
                    evidence={
                        "message": (
                            "Texto da política de privacidade analisado "
                            "não contém referência a transferências "
                            "internacionais de dados."
                        ),
                        "flag": "international_transfers",
                        "value": False,
                    },
                )
                findings.append(finding)

    # =========================
    # R09 - Política não identifica o DPO quando obrigatório
    # =========================
    if site_data.privacy_policy_url is not None and not policy_flags.get("_policy_unreachable", False):
        # Comentário (bug corrigido):
        # A chave usada aqui tinha de corresponder à chave devolvida por
        # check_required_elements() em privacy_text.py, que é "dpo_contact"
        # e não "mentions_dpo". Com a chave errada, esta regra disparava
        # SEMPRE (falso positivo), mesmo quando a política mencionava o DPO.
        mentions_dpo = policy_flags.get("dpo_contact", False)

        if not mentions_dpo:
            maybe_rule = next(
                (rule for rule in rules_config.rules if rule.id == "R09"),
                None,
            )

            if maybe_rule is not None:
                finding = Finding(
                    id=maybe_rule.id,
                    severity=maybe_rule.severity,
                    description=maybe_rule.description,
                    recommendation=maybe_rule.recommendation,
                    evidence={
                        "message": (
                            "Texto da política de privacidade analisado "
                            "não contém referência ao Encarregado de "
                            "Proteção de Dados (DPO) nem contactos associados."
                        ),
                        "flag": "mentions_dpo",
                        "value": False,
                    },
                )
                findings.append(finding)

    # =========================
    # R10 - Política não indica prazo de conservação dos dados
    # =========================
    if site_data.privacy_policy_url is not None and not policy_flags.get("_policy_unreachable", False):
        has_retention_period = policy_flags.get(
            "retention_period",
            False,
        )

        if not has_retention_period:
            maybe_rule = next(
                (rule for rule in rules_config.rules if rule.id == "R10"),
                None,
            )

            if maybe_rule is not None:
                finding = Finding(
                    id=maybe_rule.id,
                    severity=maybe_rule.severity,
                    description=maybe_rule.description,
                    recommendation=maybe_rule.recommendation,
                    evidence={
                        "message": (
                            "Texto da política de privacidade analisado "
                            "não indica qualquer prazo de conservação "
                            "dos dados pessoais."
                        ),
                        "flag": "retention_period",
                        "value": False,
                    },
                )
                findings.append(finding)

    # =========================
    # R12 - Política de privacidade não pôde ser verificada
    # =========================
    # Comentário (bug corrigido): quando o download da política falha (ex.:
    # HTTP 403 de um WAF, timeout de rede), policy_flags fica vazio e as
    # regras R06-R10 disparavam TODAS por omissão, reportando "não
    # conforme" para elementos que na verdade nunca foram lidos. Isto é
    # sinalizado por policy_flags["_policy_unreachable"], definido em
    # cli.py quando a exceção de download é apanhada. Aqui geramos, em vez
    # disso, um único finding claro a dizer que é preciso verificação manual.
    if site_data.privacy_policy_url is not None and policy_flags.get("_policy_unreachable", False):
        maybe_rule = next(
            (rule for rule in rules_config.rules if rule.id == "R12"),
            None,
        )

        if maybe_rule is not None:
            finding = Finding(
                id=maybe_rule.id,
                severity=maybe_rule.severity,
                description=maybe_rule.description,
                recommendation=maybe_rule.recommendation,
                evidence={
                    "message": (
                        "Não foi possível descarregar/analisar automaticamente "
                        "o conteúdo da política de privacidade (ex.: bloqueio "
                        "por proteção anti-bot, timeout de rede). Os requisitos "
                        "RGPD relacionados com o texto da política (direito de "
                        "acesso, apagamento, transferências internacionais, DPO, "
                        "prazo de conservação) não puderam ser verificados "
                        "automaticamente e requerem revisão manual."
                    ),
                    "privacy_policy_url": str(site_data.privacy_policy_url),
                },
            )
            findings.append(finding)

    # =========================
    # R11 - Formulários que recolhem dados pessoais sem aviso de finalidade
    # =========================
    # Comentário:
    # Esta regra estava definida no YAML mas não tinha lógica associada
    # (regra "morta"). Consideramos que um campo é "dado pessoal" quando o
    # seu nome bate com padrões comuns (email, telefone, morada, nome, etc.).
    # Se o formulário tiver pelo menos um desses campos e não houver um
    # aviso de privacidade perto dele (has_nearby_privacy_notice=False),
    # assinalamos a não-conformidade.
    personal_data_field_patterns = [
        "email", "e-mail", "mail", "telefone", "phone", "telemovel",
        "morada", "address", "nome", "name", "nif", "cc", "cartao",
        "nascimento", "birth", "password", "senha",
    ]

    def _form_has_personal_data(form) -> bool:
        """
        Verifica se um formulário tem pelo menos um campo cujo nome sugira
        que recolhe dados pessoais (ex.: um campo chamado "email" ou "telefone").

        Comparação simples e case-insensitive: verifica se algum dos padrões
        em personal_data_field_patterns aparece como substring do nome do campo.

        :param form: Objeto Form (de site_data.forms) a analisar.
        :return: True se pelo menos um campo do formulário parecer ser um dado pessoal.
        """
        return any(
            pattern in (field or "").lower()
            for field in form.fields
            for pattern in personal_data_field_patterns
        )

    forms_without_notice = [
        form
        for form in (site_data.forms or [])
        if _form_has_personal_data(form) and not getattr(form, "has_nearby_privacy_notice", False)
    ]

    if forms_without_notice:
        maybe_rule = next(
            (rule for rule in rules_config.rules if rule.id == "R11"),
            None,
        )

        if maybe_rule is not None:
            finding = Finding(
                id=maybe_rule.id,
                severity=maybe_rule.severity,
                description=maybe_rule.description,
                recommendation=maybe_rule.recommendation,
                evidence={
                    "message": (
                        "Foram encontrados formulários que recolhem dados "
                        "pessoais sem qualquer aviso de privacidade próximo."
                    ),
                    "forms": [
                        {"action": f.action, "fields": f.fields}
                        for f in forms_without_notice
                    ],
                },
            )
            findings.append(finding)

    return findings