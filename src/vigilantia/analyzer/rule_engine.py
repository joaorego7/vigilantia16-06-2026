from typing import List, Dict

import yaml
from pydantic import BaseModel

from vigilantia.models.site_data import SiteData
from vigilantia.models.finding import Finding


class RuleDefinition(BaseModel):
    id: str
    name: str
    description: str
    check: str
    severity: str
    article: str
    recommendation: str


class RulesConfig(BaseModel):
    rules: List[RuleDefinition]


def load_rules_from_file(path: str) -> RulesConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    return RulesConfig(**raw_data)


def evaluate_rules(
    site_data: SiteData,
    rules_config: RulesConfig,
    policy_flags: Dict[str, bool],
) -> List[Finding]:

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
        if (
            "google-analytics" in script.src
            or "gtag/js" in script.src
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
                            "script": script.src,
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

    findings: List[Finding] = []

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
    if site_data.privacy_policy_url is not None:
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
    if site_data.privacy_policy_url is not None:
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
    if site_data.privacy_policy_url is not None:
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
    if site_data.privacy_policy_url is not None:
        mentions_dpo = policy_flags.get("mentions_dpo", False)

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
    if site_data.privacy_policy_url is not None:
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

    return findings