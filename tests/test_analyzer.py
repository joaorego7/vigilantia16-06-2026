# Importa Path para construir caminhos de ficheiros de forma segura e portátil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Importa funções do módulo de análise de texto da política de privacidade
from vigilantia.analyzer.privacy_text import (
    extract_plain_text,   # Extrai texto simples a partir de HTML
    detect_language,      # Deteta o idioma do texto (pt, en, etc.)
    check_required_elements,  # Verifica se o texto menciona direitos RGPD
    analyze_privacy_policy_multi_page,  # Agrega elementos RGPD por várias páginas
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


def test_international_transfer_detected_via_named_destination():
    """
    Bug corrigido (caso real: pcm.pt): a política mencionava explicitamente
    que os dados são "transmitidas para os servidores do Google nos Estados
    Unidos", mas a lista de keywords só reconhecia terminologia jurídica
    genérica ("transferência internacional", "fora da UE"), nunca menções
    diretas a um destino concreto. Isto fazia a ferramenta reportar
    (incorretamente) que a política "não menciona transferências
    internacionais", quando na verdade menciona — só não usa o jargão
    jurídico esperado.
    """
    html = """
    <html>
      <body>
        <p>O responsável pelo tratamento dos dados é a Empresa X.</p>
        <p>
          As informações geradas pelos cookies serão transmitidas para os
          servidores do Google nos Estados Unidos.
        </p>
      </body>
    </html>
    """
    text = extract_plain_text(html)
    lang = detect_language(text)
    flags = check_required_elements(text, language=lang)

    assert flags["international_transfers"] is True


def test_retention_period_known_limitation_context_blind_keyword_match():
    """
    LIMITAÇÃO CONHECIDA (não corrigida) — documentada aqui deliberadamente
    para não ser esquecida, em vez de corrigida com uma heurística frágil.

    Caso real: pcm.pt usa a frase "prazo de conservação dos dados pessoais"
    apenas para descrever o que o titular pode PEDIR ao exercer o direito
    de acesso — nunca para DECLARAR o prazo real que a empresa aplica.
    check_required_elements() não distingue estes dois casos porque é
    keyword-matching sem análise de contexto/sintaxe: basta a frase
    aparecer em qualquer lado do texto. Isto é um falso positivo (a
    ferramenta assume que o prazo foi disclosed quando não foi).

    Nota: uma heurística de "número + unidade de tempo perto da keyword"
    falharia em políticas que descrevem CRITÉRIOS em vez de um prazo fixo
    (também aceite pelo RGPD), pelo que não foi implementada sem mais
    contexto sobre o custo de falsos negativos vs. falsos positivos.
    """
    html = """
    <html>
      <body>
        <p>
          O titular dos dados tem direito a aceder à informação sobre o
          prazo de conservação dos dados pessoais ou os critérios usados
          para o definir.
        </p>
      </body>
    </html>
    """
    text = extract_plain_text(html)
    lang = detect_language(text)
    flags = check_required_elements(text, language=lang)

    # Documenta o comportamento atual (falso positivo), não o desejável.
    assert flags["retention_period"] is True


def _mock_requests_get(pages: dict):
    """
    Cria um mock de requests.get() que devolve HTML diferente consoante o
    URL pedido, de acordo com o dicionário `pages` (url -> html). URLs não
    presentes em `pages` simulam uma resposta 403 (bloqueada).
    """
    def _side_effect(url, timeout=None, headers=None):
        response = MagicMock()
        if url in pages:
            response.ok = True
            response.status_code = 200
            response.text = pages[url]
        else:
            response.ok = False
            response.status_code = 403
        return response

    return _side_effect


def test_multi_page_analysis_finds_dpo_on_related_contact_page():
    """
    Caso de uso principal desta funcionalidade: o DPO não está mencionado
    na política de privacidade principal, mas está na página de
    "Contactos", linkada a partir dela. A análise multi-página deve
    encontrar isto, coisa que a análise de uma só página nunca conseguiria.
    """
    privacy_html = """
    <html><body>
      <p>Direito de acesso aos dados pessoais garantido.</p>
      <a href="/contactos">Contactos</a>
    </body></html>
    """
    contacts_html = """
    <html><body>
      <p>Encarregado de Proteção de Dados: dpo@example.com</p>
    </body></html>
    """
    pages = {
        "https://example.com/privacidade": privacy_html,
        "https://example.com/contactos": contacts_html,
    }

    with patch("vigilantia.analyzer.privacy_text.requests.get", side_effect=_mock_requests_get(pages)):
        flags, evidence_urls, pages_analyzed = analyze_privacy_policy_multi_page(
            "https://example.com/privacidade"
        )

    assert flags["right_access"] is True
    assert flags["dpo_contact"] is True
    assert evidence_urls["dpo_contact"] == "https://example.com/contactos"
    assert "https://example.com/contactos" in pages_analyzed


def test_multi_page_analysis_ignores_page_that_fails_to_download():
    """
    Se uma página relacionada falhar (ex.: HTTP 403), a análise deve
    continuar com as restantes em vez de abortar tudo.
    """
    privacy_html = """
    <html><body>
      <p>Direito de acesso aos dados pessoais garantido.</p>
      <a href="/cookies">Política de Cookies</a>
    </body></html>
    """
    # Nota: "https://example.com/cookies" NÃO está em `pages`, logo o mock
    # simula um 403 para essa página.
    pages = {"https://example.com/privacidade": privacy_html}

    with patch("vigilantia.analyzer.privacy_text.requests.get", side_effect=_mock_requests_get(pages)):
        flags, evidence_urls, pages_analyzed = analyze_privacy_policy_multi_page(
            "https://example.com/privacidade"
        )

    assert flags["right_access"] is True
    assert pages_analyzed == ["https://example.com/privacidade"]


def test_multi_page_analysis_respects_max_pages():
    """
    Garante que o limite max_pages é respeitado, mesmo quando há mais
    páginas relacionadas disponíveis do que o limite permite analisar.
    """
    def _page_html(next_link):
        return f'<html><body><p>Direito de acesso.</p><a href="{next_link}">Termos</a></body></html>'

    pages = {
        "https://example.com/p1": _page_html("/p2"),
        "https://example.com/p2": _page_html("/p3"),
        "https://example.com/p3": _page_html("/p4"),
        "https://example.com/p4": _page_html("/p5"),
        "https://example.com/p5": _page_html("/p6"),
    }

    with patch("vigilantia.analyzer.privacy_text.requests.get", side_effect=_mock_requests_get(pages)):
        _, _, pages_analyzed = analyze_privacy_policy_multi_page(
            "https://example.com/p1", max_pages=3
        )

    assert len(pages_analyzed) <= 3


def test_multi_page_analysis_raises_when_no_page_is_reachable():
    """
    Se nem a página inicial for acessível, deve continuar a lançar
    ValueError (comportamento preservado para acionar o R12 no cli.py).
    """
    with patch("vigilantia.analyzer.privacy_text.requests.get", side_effect=_mock_requests_get({})):
        with pytest.raises(ValueError):
            analyze_privacy_policy_multi_page("https://example.com/privacidade")


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