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


def evaluate_rules(site_data: SiteData, rules_config: RulesConfig) -> List[Finding]:
    """
    Evaluate GDPR rules against the given SiteData instance.

    :param site_data: Collected data about a website.
    :param rules_config: Loaded GDPR rules configuration.
    :return: List of Finding objects representing non-compliances.
    """
    findings: List[Finding] = []

    # Comentário:
    # Nesta fase, ainda não implementamos a lógica real de avaliação.
    # Vamos apenas devolver uma lista vazia, servindo de esqueleto
    # para as próximas semanas, onde as expressões 'check' serão avaliadas.
    #
    # Mais tarde, iremos transformar o SiteData em um conjunto de variáveis
    # (por exemplo, forms_count, privacy_policy_url, etc.) e avaliar as
    # expressões definidas em cada regra.
    return findings