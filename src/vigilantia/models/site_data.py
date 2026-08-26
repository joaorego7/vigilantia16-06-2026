# src/models/site_data.py

from typing import List, Optional
from pydantic import BaseModel, HttpUrl

# Comentário de cabeçalho:
# Esta classe representa um cookie encontrado no site, incluindo atributos
# relevantes para a segurança e conformidade RGPD.
class Cookie(BaseModel):
    name: str          # nome do cookie (ex: "_ga", "session_id")
    domain: str        # domínio a que pertence (ex: ".google.com")
    path: str          # caminho no site (normalmente "/")
    secure: bool       # indica se o cookie só é enviado via HTTPS
    httpOnly: bool     # indica se o cookie é inacessível a JavaScript
    sameSite: Optional[str] = None  # proteção contra CSRF (ex: "Lax", "Strict")


# Comentário de cabeçalho:
# Esta classe representa um script de terceiros carregado pelo site,
# útil para identificar serviços de tracking e transferência de dados.
class ThirdPartyScript(BaseModel):
    src: str           # endereço do script externo (ou "inline" para scripts embebidos)
    category: str      # categoria (ex: "analytics", "advertising", "social")


# Comentário de cabeçalho:
# Esta classe representa um formulário HTML presente na página,
# incluindo o método, o destino e os campos existentes.
class Form(BaseModel):
    action: Optional[str]  # URL para onde o formulário envia os dados
    method: str            # método HTTP (ex: "GET", "POST")
    fields: List[str]      # lista com os nomes dos campos (ex: ["email", "password"])
    has_nearby_privacy_notice: bool = False  # existe texto de privacidade perto do formulário?


# Comentário de cabeçalho:
# Esta classe agrega toda a informação recolhida pelo scraper para um site.
# É o "contrato" entre o módulo scraper e o módulo analyzer.
class SiteData(BaseModel):
    url: HttpUrl                       # URL original fornecido pelo utilizador
    final_url: HttpUrl                 # URL final após redirecionamentos
    language: str                      # idioma detetado (ex: "pt", "en")
    cookies: List[Cookie]              # lista de todos os cookies encontrados
    third_party_scripts: List[ThirdPartyScript]  # scripts externos carregados
    forms: List[Form]                  # formulários encontrados na página
    privacy_policy_url: Optional[HttpUrl] = None # link para a política de privacidade
    consent_banner_detected: bool      # indica se foi detetado um banner de consentimento

    # --- Dados da empresa (opcionais) ---
    #
    # Preenchidos apenas quando o scan é iniciado a partir dos dados de uma
    # empresa (ver vigilantia/scraper/company_info.py e o comando `scan` em
    # cli.py). Num scan normal por URL ficam todos a None / lista vazia, pelo
    # que nada muda para quem já usava o SiteData. São apenas informativos:
    # o motor de regras RGPD não os lê nem os avalia.
    company_legal_name: Optional[str] = None          # nome legal completo da empresa
    company_nif: Optional[str] = None                 # NIF / número de contribuinte
    company_address: Optional[str] = None             # morada da sede
    company_registry_verified: Optional[bool] = None  # dados confirmados no registo público (Racius)?
    company_note: Optional[str] = None                # nota sobre a origem/fiabilidade dos dados
    company_nameservers: List[str] = []               # nameservers do domínio (WHOIS)