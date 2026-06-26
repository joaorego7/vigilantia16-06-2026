# tests/test_analyzer.py

from vigilantia.analyzer.rule_engine import load_rules_from_file, RulesConfig
from pathlib import Path

# Comentário:
# Este teste verifica se o ficheiro YAML de regras é carregado corretamente
# e se o número de regras é o esperado.


def test_load_rules_from_yaml():
    rules_path = Path("rules") / "gdpr_rules.yaml"
    config: RulesConfig = load_rules_from_file(str(rules_path))

    assert len(config.rules) >= 1
    first_rule = config.rules[0]
    assert first_rule.id.startswith("R")
    assert first_rule.name != ""