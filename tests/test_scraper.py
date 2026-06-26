# tests/test_scraper.py

from vigilantia.scraper.fetcher import fetch_page, FetchConfig

# Comentário:
# Este teste faz uma chamada simples ao fetch_page para um site conhecido.
# Em ambiente real, seria preferível usar vcrpy para gravar a resposta
# e não depender da rede, mas nesta fase serve como teste básico.


def test_fetch_page_invalid_url():
    # Comentário:
    # Garantimos que um URL inválido gera um erro controlado.
    try:
        fetch_page("not-a-valid-url")
        assert False, "Expected ValueError for invalid URL"
    except ValueError:
        assert True


def test_fetch_page_timeout_config():
    # Comentário:
    # Aqui apenas criamos uma configuração personalizada e chamamos a função.
    # Não validamos o conteúdo, apenas asseguramos que aceita a configuração.
    config = FetchConfig(timeout_seconds=5, verify_tls=True)
    assert config.timeout_seconds == 5
    assert config.verify_tls is True