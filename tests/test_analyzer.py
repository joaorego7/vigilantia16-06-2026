# Importa Path para construir caminhos de ficheiros de forma segura e portátil
from pathlib import Path

# Importa funções do módulo de análise de texto da política de privacidade
from vigilantia.analyzer.privacy_text import (
    extract_plain_text,   # Extrai texto simples a partir de HTML
    detect_language,      # Deteta o idioma do texto (pt, en, etc.)
    check_required_elements,  # Verifica se o texto menciona direitos RGPD
)

# Importa funções e tipos do motor de regras RGPD
from vigilantia.analyzer.rule_engine import load_rules_from_file, RulesConfig
# load_rules_from_file: lê o ficheiro YAML com regras RGPD
# RulesConfig: modelo Pydantic que representa o conjunto de regras carregadas


def test_privacy_text_analysis_basic():
    """
    Teste básico para verificar se a análise de texto da política
    consegue detetar alguns elementos RGPD obrigatórios.
    """
    # HTML de exemplo que simula uma política de privacidade em português
    html = """
    <html>
      <body>
        <p>O responsável pelo tratamento dos dados é a Empresa X.</p>
        <p>Os titulares têm direito de acesso, direito de retificação e direito ao apagamento dos dados.</p>
        <p>Os dados são conservados pelo prazo de 2 anos. Os titulares podem apresentar reclamação à CNPD.</p>
      </body>
    </html>
    """

    # Converte o HTML em texto simples (sem tags, scripts, etc.)
    text = extract_plain_text(html)

    # Deteta o idioma do texto (espera-se que seja "pt" ou semelhante)
    lang = detect_language(text)

    # Verifica a presença de elementos RGPD no texto, usando o idioma detetado
    flags = check_required_elements(text, language=lang)

    # Asserções (testes) para garantir que certos elementos foram encontrados:
    # - Identidade do responsável pelo tratamento
    assert flags["identity_controller"] is True
    # - Direito de acesso aos dados
    assert flags["right_access"] is True
    # - Direito de retificação
    assert flags["right_rectification"] is True
    # - Direito ao apagamento (direito a ser esquecido)
    assert flags["right_erasure"] is True
    # - Indicação do prazo de conservação dos dados
    assert flags["retention_period"] is True
    # Poderias também testar o direito de reclamação, se quiseres:
    # assert flags["right_complaint"] is True


def test_load_rules_from_yaml():
    """
    Teste que verifica se o ficheiro YAML de regras RGPD
    é carregado corretamente para um objeto RulesConfig.
    """
    # Constrói o caminho para o ficheiro de regras: rules/gdpr_rules.yaml
    rules_path = Path("rules") / "gdpr_rules.yaml"

    # Carrega as regras a partir do ficheiro YAML para um objeto RulesConfig
    config: RulesConfig = load_rules_from_file(str(rules_path))

    # Garante que pelo menos uma regra foi carregada
    assert len(config.rules) >= 1

    # Pega na primeira regra para fazer verificações básicas
    first_rule = config.rules[0]

    # Verifica que o ID da regra começa por "R" (ex.: "R01", "R02")
    assert first_rule.id.startswith("R")

    # Verifica que o nome da regra não está vazio
    assert first_rule.name != ""