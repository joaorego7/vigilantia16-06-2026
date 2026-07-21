# tests/test_fetcher.py
#
# Testes para o módulo scraper/fetcher.py, em particular para o bug
# corrigido em que domínios cuja rede nunca fica "idle" (anúncios,
# analytics, websockets, chat widgets) faziam o fetch falhar sempre,
# impedindo a geração de relatório.

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from vigilantia.scraper.fetcher import fetch_page, FetchConfig


def _make_mock_playwright(response_ok=True, response_status=200, networkidle_times_out=False):
    """
    Constrói um mock de sync_playwright() que simula:
      - goto() bem-sucedido com domcontentloaded (sempre rápido/fiável)
      - wait_for_load_state("networkidle") que pode ou não exceder o timeout,
        conforme o cenário de teste que queremos exercitar.
    """
    mock_response = MagicMock()
    mock_response.ok = response_ok
    mock_response.status = response_status

    mock_page = MagicMock()
    mock_page.goto.return_value = mock_response
    mock_page.url = "https://example.com/"
    mock_page.content.return_value = "<html><body>OK</body></html>"

    if networkidle_times_out:
        mock_page.wait_for_load_state.side_effect = PlaywrightTimeoutError("networkidle timeout")

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_context.cookies.return_value = []

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = MagicMock()
    mock_chromium.launch.return_value = mock_browser

    mock_p = MagicMock()
    mock_p.chromium = mock_chromium

    mock_playwright_cm = MagicMock()
    mock_playwright_cm.__enter__.return_value = mock_p
    mock_playwright_cm.__exit__.return_value = False

    return mock_playwright_cm, mock_page


def test_fetch_page_succeeds_even_if_networkidle_never_settles():
    """
    Cenário do bug real: um domínio cuja rede nunca fica "idle" (ex.: scripts
    de analytics em polling contínuo). Antes da correção, isto fazia o fetch
    falhar sempre (ValueError) e nenhum relatório era gerado. Depois da
    correção, a espera por networkidle é best-effort e o fetch deve ter
    sucesso na mesma, usando o HTML já obtido após domcontentloaded.
    """
    mock_cm, mock_page = _make_mock_playwright(networkidle_times_out=True)

    with patch("vigilantia.scraper.fetcher.sync_playwright", return_value=mock_cm):
        result = fetch_page("https://example.com")

    assert result.html == "<html><body>OK</body></html>"
    assert result.final_url == "https://example.com/"
    # Confirma que a fase 1 (domcontentloaded) foi usada, não networkidle.
    _, kwargs = mock_page.goto.call_args
    assert kwargs["wait_until"] == "domcontentloaded"


def test_fetch_page_converts_timeout_to_milliseconds_correctly():
    """
    Bug corrigido: o timeout passado ao Playwright estava a ser multiplicado
    por 3000 em vez de 1000 (Playwright espera milissegundos). Este teste
    garante que timeout_seconds=20 resulta em timeout=20000 no goto().
    """
    mock_cm, mock_page = _make_mock_playwright()

    with patch("vigilantia.scraper.fetcher.sync_playwright", return_value=mock_cm):
        fetch_page("https://example.com", config=FetchConfig(timeout_seconds=20))

    _, kwargs = mock_page.goto.call_args
    assert kwargs["timeout"] == 20000


def test_fetch_page_still_fails_on_non_ok_response():
    """
    Garante que a correção não afeta o comportamento correto de falhar
    quando o servidor responde com um código de erro HTTP (ex.: 500).
    """
    mock_cm, _ = _make_mock_playwright(response_ok=False, response_status=500)

    with patch("vigilantia.scraper.fetcher.sync_playwright", return_value=mock_cm):
        with pytest.raises(ValueError, match="HTTP 500"):
            fetch_page("https://example.com")


def test_fetch_page_still_fails_when_domcontentloaded_times_out():
    """
    Garante que um timeout genuíno na fase 1 (domcontentloaded) — página
    verdadeiramente inacessível/muito lenta a responder — continua a
    resultar em falha clara, em vez de ficar pendurado indefinidamente.
    """
    mock_cm, mock_page = _make_mock_playwright()
    mock_page.goto.side_effect = PlaywrightTimeoutError("domcontentloaded timeout")

    with patch("vigilantia.scraper.fetcher.sync_playwright", return_value=mock_cm):
        with pytest.raises(ValueError, match="Timeout error"):
            fetch_page("https://example.com")
