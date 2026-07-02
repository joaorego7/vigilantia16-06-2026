# src/analyzer/rule_engine.py

from typing import List, Dict  # já está certo

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
    findings: List[Finding] = []

    # =========================
    # Regra R05 - Política de privacidade ausente ou inacessível
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
                    "message": "Campo privacy_policy_url em SiteData está vazio (None).",
                    "field": "privacy_policy_url",
                    "value": None,
                },
            )
            findings.append(finding)

    # =========================
    # Regra R07 - Política não menciona direito ao apagamento
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
                            "não contém nenhuma referência ao direito ao apagamento."
                        ),
                        "flag": "right_erasure",
                        "value": False,
                    },
                )
                findings.append(finding)

    return findings