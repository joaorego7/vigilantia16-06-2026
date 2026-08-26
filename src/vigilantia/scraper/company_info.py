"""
Módulo para obter o site oficial e dados de contacto de uma empresa.
Recebe um dicionário com os dados de uma empresa e devolve
o site oficial da empresa, dados de contacto (NIF, email, morada) e
informação de DNS (nameservers) do domínio.

Uso:
    from vigilantia.scraper.company_info import get_company_urls
    info = get_company_urls({"company_name": "Empresa Lda", "country": "PT"})

Usa pesquisa web (DuckDuckGo), o registo público de empresas Racius.com, e
consultas WHOIS diretas.

Visão geral do fluxo (ver get_company_urls no fundo do ficheiro):
    1. Pesquisa o nome da empresa no DuckDuckGo para encontrar o site oficial.
    2. Visita esse site e tenta extrair NIF, email e morada diretamente do site.
    3. Se faltar NIF ou morada, tenta complementar através do Racius.com
       (registo público de empresas), mas só confia cegamente no resultado
       se conseguir validar contra o legal_name/address/domínio já conhecidos.
    4. Faz um WHOIS ao domínio encontrado (nameservers) via socket, sem
       depender de ferramentas instaladas na máquina.
"""
import json
import re
import socket

import unicodedata

import requests
from bs4 import BeautifulSoup

# Domínios que aparecem nos resultados de pesquisa mas nunca são "o site
# oficial da empresa" — redes sociais, diretórios, agregadores de notícias.
# São ignorados quando escolhemos qual URL é o site da empresa.
#
# O racius.com está aqui por este motivo (nunca é o site oficial de
# ninguém), mas é usado noutro sítio do ficheiro (_REGISTRY_DOMAINS, dentro
# de _enrich_from_registry) como fonte deliberada de NIF/morada — são dois
# papéis diferentes, não há contradição entre os dois.
_EXCLUDED_DOMAINS = {
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "wikipedia.org", "crunchbase.com", "glassdoor.com",
    "indeed.com", "bloomberg.com", "yellowpages.com", "paginasamarelas.pt",
    "racius.com", "informadb.pt", "duckduckgo.com", "dnb.com", "directório-de-empresas.cybo.com",
    "www.northdata.com", "www.europages.com", "www.kompass.com", "www.yelp.com", "www.zoominfo.com",
    "www.bbb.org", "www.manta.com", "www.foursquare.com", "northdata.com"
}


def _strip_accents(text: str) -> str:
    """Remove acentos de um texto (ex: 'Jerónimo' -> 'Jeronimo').

    Usado antes de comparar nomes de empresas com domínios/textos, porque um
    domínio nunca tem acentos mas o nome da empresa pode ter (ex: a empresa
    "Jerónimo Martins" tem o domínio "jeronimomartins.com", sem acento)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _normalize(text: str) -> set[str]:
    """Converte um texto num conjunto de palavras em minúsculas e sem acentos.

    Serve para comparar duas strings por sobreposição de palavras (ex:
    verificar se o nome da empresa aparece dentro do texto de uma página),
    ignorando maiúsculas/minúsculas, acentos e pontuação."""
    return set(re.findall(r"[a-z0-9]+", _strip_accents(text.lower())))


def _is_excluded(domain: str) -> bool:
    """Diz se um domínio está na lista de exclusões (_EXCLUDED_DOMAINS),
    incluindo subdomínios (ex: 'en.wikipedia.org' conta como 'wikipedia.org')."""
    return any(domain == d or domain.endswith("." + d) for d in _EXCLUDED_DOMAINS)


def _search(query: str, num: int = 10) -> list[dict]:
    """Faz uma pesquisa no motor de busca DuckDuckGo (versão HTML, sem API key)
    e devolve uma lista de resultados, cada um com 'url' e 'snippet' (o texto
    de resumo que aparece por baixo do link nos resultados de pesquisa).

    Usa o endpoint html.duckduckgo.com, que devolve HTML simples (sem
    JavaScript), por isso é feito parsing com BeautifulSoup."""
    resp = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; GetCompanyUrl/1.0)"},
        timeout=15,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for result in soup.select(".result")[:num]:
        a = result.select_one("a.result__a")
        if not a or not a.get("href"):
            continue
        snippet_el = result.select_one(".result__snippet")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        results.append({"url": a["href"], "snippet": snippet})
    return results


# Ordem de prioridade dos níveis de confiança do URL escolhido: quanto menor
# o número, melhor. Usado para ordenar candidatos e escolher o melhor.
_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}

# Padrão para encontrar um NIF/NIPC (9 dígitos) junto de uma palavra-chave
# como "NIF:", "Contribuinte:", etc.
_NIF_PATTERN = re.compile(
    r"(?:NIF|NIPC|N\.?I\.?F\.?|Contribuinte)\s*[:\-]?\s*(\d{9})", re.IGNORECASE
)
# Padrão genérico de email.
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
# Padrão de código postal português (0000-000) seguido do nome da localidade
# (até 4 palavras capitalizadas a seguir, ex: "1249-300 Lisboa").
_POSTAL_CODE_PATTERN = re.compile(
    r"\d{4}-\d{3}\s+[A-ZÀ-Ú][\wÀ-ú]*(?:\s+[A-ZÀ-Ú][\wÀ-ú]*){0,3}"
)
# Palavras que, se aparecerem perto de um código postal no texto da página,
# indicam que aquele código postal é mesmo a morada da empresa (sede,
# escritório) e não outra coisa qualquer (ex: morada de um cliente exemplo).
_ADDRESS_CONTEXT_KEYWORDS = ("sede", "morada", "endereço", "endereco", "escritório", "escritorio", "address", "office")
# Palavras que, se aparecerem a seguir ao código postal capturado, indicam
# que o regex apanhou lixo (rodapé, botões, etc.) e não a morada real —
# usadas para cortar a captura antes dessas palavras.
_ADDRESS_STOP_WORDS = {
    "copyright", "all", "rights", "reserved", "todos", "direitos", "reservados",
    "get", "directions", "ver", "mapa", "map", "how", "navegar", "rota", "route",
}
# Domínios de email que são claramente placeholders/exemplos de formulários
# (ex: campo de contacto com "exemplo@exemplo.com" como texto de exemplo),
# nunca o email real da empresa — são ignorados na extração de email.
_PLACEHOLDER_EMAIL_DOMAINS = {"exemplo.com", "example.com", "test.com", "yourdomain.com", "domain.com", "email.com"}
# Palavras-chave em URLs de links que costumam apontar para a página
# "Sobre nós" de um site — é aí que a morada/NIF costumam aparecer.
_INFO_PAGE_KEYWORDS = ("sobre", "about", "contact", "quem-somos", "quemsomos")
# Palavras-chave em URLs de links que costumam apontar para a página de
# "Termos e Condições" / "Informação Legal" — outro sítio onde o NIF costuma
# aparecer (empresas grandes muitas vezes só o publicam aqui, não no "Sobre").
_LEGAL_PAGE_KEYWORDS = ("legal", "termos", "juridic", "privacidade", "impressum", "aviso-legal", "informacoes-legais")


def _fetch_page_text(url: str) -> str:
    """Descarrega o HTML de um URL (pedido HTTP simples, sem executar
    JavaScript). Por isso, sites que carregam o conteúdo principal via
    JavaScript (React, Vue, etc.) podem devolver pouco ou nenhum texto útil
    aqui — é uma limitação conhecida desta abordagem "leve"."""
    resp = requests.get(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; GetCompanyUrl/1.0)"}, timeout=10
    )
    resp.raise_for_status()
    return resp.text


def _find_info_page_urls(html: str, base_url: str) -> list[str]:
    """Procura, nos links (<a href>) da página, um link para a página "Sobre
    nós" e um link para a página "Termos/Informação Legal", usando as
    palavras-chave definidas acima. Devolve os URLs completos (resolvidos
    contra base_url) encontrados — no máximo um de cada tipo.

    Serve para sabermos que páginas extra visitar à procura de NIF/morada,
    já que raramente estão na página inicial do site."""
    from urllib.parse import urljoin

    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href_lower = a["href"].lower()
        if "sobre" not in found and any(kw in href_lower for kw in _INFO_PAGE_KEYWORDS):
            found["sobre"] = urljoin(base_url, a["href"])
        if "legal" not in found and any(kw in href_lower for kw in _LEGAL_PAGE_KEYWORDS):
            found["legal"] = urljoin(base_url, a["href"])
    return list(found.values())


def _extract_fields_from_text(combined_text: str) -> dict:
    """Extrai NIF, email, código postal e morada de um bloco de texto, por
    correspondência de padrões (regex) — sem inteligência artificial, por
    isso só apanha o que estiver escrito num formato reconhecível.

    Usada tanto para o texto do site oficial da empresa como para o texto de
    uma página do Racius.com (registo de empresas), por isso recebe só o
    texto já extraído (não sabe de onde veio).

    Lógica da morada (a parte mais complexa):
      1. Procura um código postal português (0000-000) no texto.
      2. Ignora "0000-000" (código genérico/placeholder que aparece em
         formulários de exemplo em alguns sites).
      3. Só aceita o código postal se houver uma palavra-chave de contexto
         (ex: "sede", "morada") nos ~120 caracteres antes dele — sem isso,
         é fácil apanhar um código postal qualquer que apareça na página
         (ex: de um exemplo, de outra morada mencionada) sem ser a da
         empresa.
      4. Tenta ainda recuar até à palavra-chave e apanhar o texto da rua/
         número antes do código postal, para dar uma morada mais completa
         (não só "código postal + cidade").
      5. Corta a captura no último ponto final antes do código postal (para
         não arrastar frases de marketing inteiras) e em palavras-lixo tipo
         "Copyright"/"Get Directions" (texto de rodapé/botões)."""
    details = {"nif": None, "email": None, "postal_code": None, "address": None}

    nif_match = _NIF_PATTERN.search(combined_text)
    if nif_match:
        details["nif"] = nif_match.group(1)

    for email_match in _EMAIL_PATTERN.finditer(combined_text):
        email = email_match.group(0).rstrip(".")
        if email.split("@")[-1].lower() not in _PLACEHOLDER_EMAIL_DOMAINS:
            details["email"] = email
            break

    text_lower = combined_text.lower()
    for match in _POSTAL_CODE_PATTERN.finditer(combined_text):
        if match.group(0).startswith("0000-000"):
            continue
        context_start = max(0, match.start() - 120)
        context = text_lower[context_start:match.start()]
        keyword = next((kw for kw in _ADDRESS_CONTEXT_KEYWORDS if kw in context), None)
        if not keyword:
            continue

        words = match.group(0).split()
        clean_words = []
        for w in words:
            if w.lower() in _ADDRESS_STOP_WORDS:
                break
            clean_words.append(w)
        if not clean_words:
            continue
        # remove palavras repetidas seguidas (ex: "Lisboa Lisboa Lisboa" que
        # aparece no Racius por causa da estrutura de breadcrumb da página)
        deduped_words = [w for i, w in enumerate(clean_words) if i == 0 or w.lower() != clean_words[i - 1].lower()]
        details["postal_code"] = " ".join(deduped_words)

        # tenta apanhar a morada completa (rua/número) antes do código postal,
        # a partir da última ocorrência da palavra-chave (ex: "Sede:") na janela de contexto
        kw_pos_in_context = context.rfind(keyword)
        street_start = context_start + kw_pos_in_context + len(keyword)
        street_part = combined_text[street_start:match.start()].strip(" :-–—\n,")
        # se houver uma frase completa (ponto final) no meio, fica só com o
        # que vem depois — evita apanhar frases de marketing inteiras
        last_sentence_end = max(street_part.rfind("."), street_part.rfind("!"), street_part.rfind("?"))
        if last_sentence_end != -1:
            street_part = street_part[last_sentence_end + 1:].strip(" :-–—\n,")
        if street_part and len(street_part) <= 100:
            details["address"] = f"{street_part}, {details['postal_code']}"
        else:
            details["address"] = details["postal_code"]
        break

    return details


def _extract_company_details(url: str) -> dict:
    """Visita o site oficial da empresa (e, se conseguir encontrar, também a
    página "Sobre nós" e/ou "Termos/Legal") e tenta extrair NIF, email e
    morada do texto combinado de todas essas páginas.

    Falha em silêncio (devolve tudo a None) se o site não responder — isto é
    propositado: um site em baixo não deve rebentar o script todo, só faz
    com que fiquemos sem estes dados extra."""
    try:
        html = _fetch_page_text(url)
    except Exception:
        return {"nif": None, "email": None, "postal_code": None, "address": None}

    pages_html = [html]
    for info_url in _find_info_page_urls(html, url)[:2]:
        try:
            pages_html.append(_fetch_page_text(info_url))
        except Exception:
            pass

    combined_text = "\n".join(
        BeautifulSoup(h, "html.parser").get_text(" ", strip=True) for h in pages_html
    )
    return _extract_fields_from_text(combined_text)


# Domínios de registo público de empresas usados para complementar dados
# (NIF, morada) quando o site oficial não os tem. Por agora só o Racius.
_REGISTRY_DOMAINS = ("racius.com",)


def _enrich_from_registry(
    company: dict, company_name: str, country: str, site_domain: str | None,
) -> dict:
    """Vai ao Racius.com (registo público de empresas portuguesas) tentar
    encontrar NIF/morada quando o site oficial não os tinha.

    ATENÇÃO — risco de empresa homónima (mesmo nome, empresa diferente):
    a pesquisa por nome pode devolver a página do Racius de uma empresa
    completamente diferente que só por coincidência tem um nome parecido.
    Isto é especialmente provável em empresas com nomes curtos, siglas, ou
    nomes comuns, mas pode acontecer com qualquer nome.

    Por isso, sempre que possível, tentamos VALIDAR se o resultado do
    Racius é mesmo a empresa certa, verificando se o texto da página do
    Racius contém:
      - o legal_name que o utilizador forneceu no input, OU
      - o address que o utilizador forneceu no input, OU
      - o próprio domínio do site oficial já confirmado (raramente resulta,
        porque o Racius normalmente não publica o site da empresa).

    Não tentamos adivinhar o legal_name automaticamente a partir do texto do
    site oficial: em sites de grupos empresariais (que mencionam várias
    subsidiárias/marcas na mesma página), o risco de apanhar o nome de uma
    entidade errada do grupo em vez da empresa-mãe é demasiado alto.

    Se não houver nenhuma forma de validar, o resultado é devolvido na
    mesma (para não perder informação), mas com "registry_verified": False,
    para quem lê o JSON saber que tem de confirmar manualmente antes de
    confiar nestes dados."""
    empty = {"nif": None, "email": None, "postal_code": None, "address": None, "registry_verified": None}

    legal_name_tokens = _normalize(company.get("legal_name", ""))
    address_tokens = _normalize(company.get("address", ""))

    # prefere pesquisar pelo legal_name (mais específico) quando existe,
    # senão usa o company_name (mais genérico, mais risco de ambiguidade)
    search_term = company.get("legal_name") or company_name
    query = " ".join(p for p in [search_term, country, "site:racius.com"] if p)
    try:
        results = _search(query)
    except Exception:
        return empty

    for item in results:
        url = item["url"]
        domain = re.sub(r"^www\.", "", url.split("/")[2]) if "//" in url else ""
        if not any(domain == d or domain.endswith("." + d) for d in _REGISTRY_DOMAINS):
            continue
        try:
            html = _fetch_page_text(url)
        except Exception:
            continue
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        text_tokens = _normalize(text[:2000])

        verified = (
            (bool(legal_name_tokens) and legal_name_tokens.issubset(text_tokens))
            or (bool(address_tokens) and bool(address_tokens & text_tokens))
            or (bool(site_domain) and site_domain.lower() in text.lower())
        )

        # mesmo sem conseguir validar, devolve os dados encontrados — mas
        # marcados como não verificados, para quem usar o resultado saber
        # que tem de confirmar manualmente (ver aviso no docstring acima)
        result = _extract_fields_from_text(text)
        result["registry_verified"] = verified
        return result

    return empty


def _whois_query(server: str, query: str, port: int = 43, timeout: float = 8) -> str:
    """Faz uma consulta WHOIS "à mão", em Python puro: abre uma ligação de
    rede (socket) diretamente à porta 43 de um servidor WHOIS, envia o nome
    de domínio pesquisado, e lê a resposta em texto simples.

    Não usa nenhuma biblioteca externa nem programa instalado na máquina
    (ex: o comando `whois` do sistema operativo) — só a biblioteca `socket`
    que já vem com o Python. O protocolo WHOIS em si é simples: manda-se o
    texto da pesquisa seguido de quebra de linha, e o servidor responde em
    texto e fecha a ligação."""
    with socket.create_connection((server, port), timeout=timeout) as sock:
        sock.sendall((query + "\r\n").encode())
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode(errors="replace")


def _find_whois_server(domain: str) -> str | None:
    """Descobre qual é o servidor WHOIS responsável por um domínio, a partir
    da terminação dele (TLD — ex: '.pt', '.com').

    Funciona perguntando primeiro ao servidor "raiz" da IANA
    (whois.iana.org, a entidade que gere a atribuição de domínios a nível
    mundial) qual é o servidor WHOIS certo para aquele TLD — a resposta
    inclui uma linha "whois: <servidor>" que aqui é extraída com regex."""
    tld = domain.rsplit(".", 1)[-1]
    try:
        text = _whois_query("whois.iana.org", tld)
    except Exception:
        return None
    match = re.search(r"whois:\s*(\S+)", text, re.IGNORECASE)
    return match.group(1) if match else None


def _fetch_whois_details(domain: str) -> dict:
    """Devolve os nameservers (servidores de DNS) configurados para um
    domínio, via consulta WHOIS."""
    details = {"nameservers": []}
    server = _find_whois_server(domain)
    if not server:
        return details

    try:
        text = _whois_query(server, domain)
    except Exception:
        return details

    details["nameservers"] = sorted(
        {ns.rstrip(".").lower() for ns in re.findall(r"Name Server:\s*(\S+)", text, re.IGNORECASE)}
    )

    return details


def get_company_urls(company: dict) -> dict:
    """Função principal — recebe o dicionário com os dados da empresa
    (mesma estrutura que chega no JSON pelo argumento da linha de comandos)
    e devolve o dicionário completo com o resultado.

    Campos aceites no input (só company_name é obrigatório):
      - company_name (obrigatório): nome da empresa a pesquisar.
      - legal_name: nome legal completo (ex: "Empresa Unipessoal, Lda.") —
        usado para tornar a pesquisa mais precisa e para validar o
        resultado do Racius (ver _enrich_from_registry).
      - country: país, ajuda a pesquisa a ser mais específica.
      - address: morada conhecida — também usada para validar resultados.

    Passos:
      1. Pesquisa "<nome> <país> official website" no DuckDuckGo.
      2. De entre os resultados, escolhe o melhor candidato a "site
         oficial": ignora redes sociais/diretórios (_is_excluded), e dá
         confiança "high" se o nome da empresa aparecer no próprio domínio,
         "medium" se a morada fornecida aparecer no resumo do resultado, ou
         "low" caso contrário (mais provável de estar errado).
      3. Visita esse site à procura de NIF/email/morada (_extract_company_details).
      4. Se faltar NIF ou morada, tenta complementar via Racius
         (_enrich_from_registry), marcando registry_verified consoante
         conseguiu confirmar ou não que é a empresa certa.
      5. Faz WHOIS ao domínio encontrado para obter os nameservers.
      6. Junta tudo num único dicionário, trocando valores em falta (None)
         por "not available" para ficar claro no output final."""
    company_name = company.get("company_name") or company.get("legal_name")
    if not company_name:
        raise ValueError("company_name é obrigatório")

    # 1. Pesquisa o site oficial da empresa
    query = " ".join(
        p for p in [company_name, company.get("country", ""), "official website"] if p
    )
    results = _search(query)

    name_tokens = _normalize(company_name)
    address_tokens = _normalize(company.get("address", ""))

    # 2. Escolhe o melhor candidato a "site oficial" entre os resultados
    candidates = []
    for item in results:
        url = item["url"]
        domain = re.sub(r"^www\.", "", url.split("/")[2]) if "//" in url else ""
        if not domain or _is_excluded(domain):
            continue
        label = domain.split(".")[0]
        domain_tokens = _normalize(label)
        label_plain = re.sub(r"[^a-z0-9]", "", _strip_accents(label.lower()))
        # confiança "high": o nome da empresa (ou parte dele) está no domínio
        # (ex: "Jerónimo Martins" -> "jeronimomartins.com")
        name_matches_domain = bool(name_tokens & domain_tokens) or all(
            t in label_plain for t in name_tokens
        )

        snippet_tokens = _normalize(item["snippet"])
        # confiança "medium": não bate no domínio, mas a morada fornecida
        # aparece no resumo do resultado de pesquisa
        address_matches_snippet = bool(address_tokens) and bool(
            address_tokens & snippet_tokens
        )

        if name_matches_domain:
            confidence = "high"
        elif address_matches_snippet:
            confidence = "medium"
        else:
            confidence = "low"

        candidates.append({"url": url, "domain": domain, "confidence": confidence})

    # ordena por confiança (high primeiro) e fica com o melhor
    candidates.sort(key=lambda c: _CONFIDENCE_RANK[c["confidence"]])
    best = candidates[0] if candidates else None

    # 3. Tenta extrair NIF/email/morada diretamente do site oficial
    details = _extract_company_details(best["url"]) if best else {
        "nif": None, "email": None, "postal_code": None, "address": None
    }
    details["registry_verified"] = None  # None = Racius nem chegou a ser consultado

    # 4. Se ainda faltar NIF ou morada, complementa via Racius
    if details["nif"] is None or details["address"] is None:
        # só passamos o domínio como sinal de validação se a confiança no
        # site oficial já era "high" — caso contrário arriscávamos validar
        # o Racius contra um site que já por si só podia estar errado
        site_domain = best["domain"] if best and best["confidence"] == "high" else None
        registry_details = _enrich_from_registry(
            company, company_name, company.get("country", ""), site_domain
        )
        for field, value in registry_details.items():
            if field == "registry_verified":
                if value is not None:
                    details["registry_verified"] = value
            elif details.get(field) is None and value is not None:
                details[field] = value

    # troca None por "not available" em todos os campos, exceto
    # registry_verified (que fica True/False/None, não faz sentido em texto)
    verified_flag = details.pop("registry_verified")
    details = {k: (v if v is not None else "not available") for k, v in details.items()}
    details["registry_verified"] = verified_flag

    # nota a explicar a origem/fiabilidade de nif, postal_code e address,
    # consoante o valor de registry_verified:
    #   True  -> dados do Racius confirmados contra legal_name/address/domínio
    #   False -> dados do Racius NÃO confirmados, podem ser de outra empresa
    #   None  -> Racius nem foi consultado (dados vieram do site oficial,
    #            quando existem, ou não há dados nenhuns disponíveis)
    has_extra_data = any(
        details[f] != "not available" for f in ("nif", "postal_code", "address")
    )
    if verified_flag is True:
        note = (
            "Dados de nif, postal_code e address confirmados através do "
            "Racius.com (bateram certo com o legal_name/address fornecidos)."
        )
    elif verified_flag is False:
        note = (
            "Dados de nif, postal_code e address não foram confirmados "
            "automaticamente (podem existir subsidiárias ou empresas com nome "
            "semelhante) — validar manualmente antes de usar."
        )
    elif has_extra_data:
        note = "Dados de nif, postal_code e address obtidos diretamente do site oficial da empresa."
    else:
        note = "not available"
    details["note"] = note

    # 5. WHOIS do domínio encontrado (nameservers)
    whois_details = _fetch_whois_details(best["domain"]) if best else {"nameservers": []}
    whois_details = {
        k: (v if v else "not available") for k, v in whois_details.items()
    }

    # 6. Junta tudo no resultado final
    return {
        "company_name": company_name,
        "query_used": query,
        "url": best["url"] if best else "not available",
        "domain": best["domain"] if best else "not available",
        "confidence": best["confidence"] if best else "not available",
        **details,
        **whois_details,
    }


