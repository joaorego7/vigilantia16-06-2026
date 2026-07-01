# src/analyzer/rule_engine.py

from typing import List

import yaml
from pydantic import BaseModel

from vigilantia.models.site_data import SiteData
from vigilantia.models.finding import Finding

# Comentário de cabeçalho:
# Este módulo implementa o motor de regras RGPD.
# Nesta fase, apenas carregamos o ficheiro YAML de regras
# e preparamos a infraestrutura para, no futuro, avaliá-las
# contra um objeto SiteData.


class RuleDefinition(BaseModel):
    """
    Represents a single GDPR rule loaded from YAML.
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
    Represents the full rules configuration loaded from YAML.
    """

    rules: List[RuleDefinition]


def load_rules_from_file(path: str) -> RulesConfig:
    """
    Load GDPR rules from a YAML file.

    :param path: Path to the YAML file containing GDPR rules.
    :return: RulesConfig object with all rule definitions.
    """
    # Comentário:
    # Abrimos o ficheiro YAML em modo de leitura e carregamos o conteúdo
    # para um dicionário Python, que depois é validado com Pydantic.
    with open(path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    return RulesConfig(**raw_data)


def evaluate_rules(
    site_data: SiteData,
    rules_config: RulesConfig,
    policy_flags: Dict[str, bool],
) -> List[Finding]:
    """
    Avalia as regras RGPD contra o SiteData e as flags da política de privacidade.

    :param site_data: Dados recolhidos sobre o site (cookies, formulários, etc.).
    :param rules_config: Conjunto de regras RGPD carregadas do ficheiro YAML.
    :param policy_flags: Dicionário de flags sobre a política de privacidade,
                         por exemplo, resultado de check_required_elements.
    :return: Lista de objetos Finding que representam não-conformidades.
    """
    findings: List[Finding] = []

    # =========================
    # Regra R05 - Política de privacidade ausente ou inacessível
    # =========================
    #
    # Lógica: se o campo privacy_policy_url do SiteData estiver vazio (None),
    # criamos uma não-conformidade correspondente à regra R05.
    if site_data.privacy_policy_url is None:
        maybe_rule = next(
            (rule for rule in rules_config.rules if rule.id == "R05"),
            None,
        )

        if maybe_rule is not None:
            finding = Finding(
                id=maybe_rule.id,
                name=maybe_rule.name,
                description=maybe_rule.description,
                severity=maybe_rule.severity,
                article=maybe_rule.article,
                recommendation=maybe_rule.recommendation,
                evidence="Campo privacy_policy_url em SiteData está vazio (None).",
            )
            findings.append(finding)

    # =========================
    # Regra R07 - Política não menciona direito ao apagamento
    # =========================
    #
    # Lógica: se a flag right_erasure for False, significa que o texto da
    # política analisado não contém nenhuma expressão relativa ao direito
    # ao apagamento / direito a ser esquecido.
    #
    # Só faz sentido avaliar esta regra se existir política (privacy_policy_url
    # não for None) e se já tivermos policy_flags calculadas.
    if site_data.privacy_policy_url is not None:
        # Obtém o valor da flag; se não existir, assume False como valor seguro.
        has_right_erasure = policy_flags.get("right_erasure", False)

        if not has_right_erasure:
            maybe_rule = next(
                (rule for rule in rules_config.rules if rule.id == "R07"),
                None,
            )

            if maybe_rule is not None:
                finding = Finding(
                    id=maybe_rule.id,
                    name=maybe_rule.name,
                    description=maybe_rule.description,
                    severity=maybe_rule.severity,
                    article=maybe_rule.article,
                    recommendation=maybe_rule.recommendation,
                    evidence=(
                        "Texto da política de privacidade analisado "
                        "não contém nenhuma referência ao direito ao apagamento."
                    ),
                )
                findings.append(finding)

    # No futuro, aqui acrescentas mais regras baseadas em:
    # - outros campos de site_data (cookies, formulários, banner de consentimento)
    # - outras flags da política (right_access, dpo_contact, retention_period, etc.)

    return findings