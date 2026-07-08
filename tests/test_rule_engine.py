# tests/test_rule_engine.py
#
# Comentário:
# Testes de regressão para os bugs corrigidos no motor de regras:
# 1) evaluate_rules() rebentava com UnboundLocalError (findings usada
#    antes de ser inicializada).
# 2) A regra R09 (DPO) usava a chave errada ("mentions_dpo" em vez de
#    "dpo_contact") e por isso disparava sempre, mesmo quando o DPO
#    estava mencionado na política.
# 3) A regra R11 (formulários sem aviso de privacidade) estava definida
#    no YAML mas não tinha lógica associada no motor.

from vigilantia.analyzer.rule_engine import load_rules_from_file, evaluate_rules
from vigilantia.models.site_data import SiteData, Cookie, Form, ThirdPartyScript
from vigilantia.paths import RULES_FILE


def _base_site_data(**overrides) -> SiteData:
    defaults = dict(
        url="https://example.com",
        final_url="https://example.com",
        language="pt",
        cookies=[],
        third_party_scripts=[],
        forms=[],
        privacy_policy_url="https://example.com/privacy",
        consent_banner_detected=True,
    )
    defaults.update(overrides)
    return SiteData(**defaults)


def test_evaluate_rules_does_not_raise_unbound_local_error():
    """
    Bug corrigido: evaluate_rules() rebentava com UnboundLocalError
    assim que a primeira regra (R01) tentava adicionar um finding,
    porque 'findings' só era declarada mais tarde na função.
    """
    site_data = _base_site_data(
        consent_banner_detected=False,
        cookies=[
            Cookie(name="_ga", domain=".example.com", path="/", secure=True, httpOnly=True),
        ],
    )
    rules_config = load_rules_from_file(str(RULES_FILE))

    # Não deve lançar UnboundLocalError (nem qualquer outra exceção).
    findings = evaluate_rules(site_data, rules_config, policy_flags={})

    # Com banner ausente e cookie de tracking presente, R01 e R02 devem disparar.
    finding_ids = {f.id for f in findings}
    assert "R01" in finding_ids
    assert "R02" in finding_ids


def test_dpo_rule_does_not_fire_when_policy_mentions_dpo():
    """
    Bug corrigido: a regra R09 usava a chave 'mentions_dpo', que nunca
    existia no dicionário de policy_flags (a chave real é 'dpo_contact'),
    pelo que a regra disparava sempre, mesmo com o DPO mencionado.
    """
    site_data = _base_site_data()
    rules_config = load_rules_from_file(str(RULES_FILE))

    policy_flags_with_dpo = {"dpo_contact": True}
    findings = evaluate_rules(site_data, rules_config, policy_flags_with_dpo)
    assert "R09" not in {f.id for f in findings}

    policy_flags_without_dpo = {"dpo_contact": False}
    findings = evaluate_rules(site_data, rules_config, policy_flags_without_dpo)
    assert "R09" in {f.id for f in findings}


def test_r11_fires_for_form_with_personal_data_and_no_notice():
    """
    A regra R11 estava definida no YAML mas sem lógica implementada.
    Um formulário com campo de email e sem aviso de privacidade perto
    deve gerar o finding R11.
    """
    site_data = _base_site_data(
        forms=[
            Form(action="/submit", method="POST", fields=["email", "nome"], has_nearby_privacy_notice=False),
        ],
    )
    rules_config = load_rules_from_file(str(RULES_FILE))
    findings = evaluate_rules(site_data, rules_config, policy_flags={})

    assert "R11" in {f.id for f in findings}


def test_r11_does_not_fire_when_notice_is_present():
    site_data = _base_site_data(
        forms=[
            Form(action="/submit", method="POST", fields=["email"], has_nearby_privacy_notice=True),
        ],
    )
    rules_config = load_rules_from_file(str(RULES_FILE))
    findings = evaluate_rules(site_data, rules_config, policy_flags={})

    assert "R11" not in {f.id for f in findings}


def test_r03_does_not_raise_typeerror_on_httpurl():
    """
    Bug corrigido: script.src é um HttpUrl do Pydantic, não uma string.
    "google-analytics" in script.src lançava TypeError: argument of type
    'HttpUrl' is not iterable. A regra R03 deve conseguir avaliar o script
    sem rebentar, e deve disparar porque falta a anonimização de IP.
    """
    site_data = _base_site_data(
        third_party_scripts=[
            ThirdPartyScript(src="https://www.google-analytics.com/analytics.js", category="analytics"),
        ],
    )
    rules_config = load_rules_from_file(str(RULES_FILE))

    findings = evaluate_rules(site_data, rules_config, policy_flags={})
    assert "R03" in {f.id for f in findings}


def test_all_rules_in_yaml_are_syntactically_loadable():
    """Garante que o YAML de regras completo (R01-R11) carrega sem erros."""
    rules_config = load_rules_from_file(str(RULES_FILE))
    rule_ids = {r.id for r in rules_config.rules}
    expected_ids = {f"R{i:02d}" for i in range(1, 12)}
    assert expected_ids.issubset(rule_ids)
