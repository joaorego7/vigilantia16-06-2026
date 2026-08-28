# Vigilantia

Vigilantia é uma ferramenta de auditoria RGPD para websites, desenvolvida em Python. Analisa automaticamente sites em busca de não-conformidades com o Regulamento Geral sobre a Proteção de Dados (RGPD), gerando relatórios HTML detalhados com as não-conformidades encontradas, recomendações de correção e referências aos artigos legais aplicáveis.

> **Aviso legal:** Esta ferramenta é um apoio técnico e não substitui uma auditoria jurídica profissional. Ver [DISCLAIMER.md](DISCLAIMER.md) para mais informação.

---

## Índice

- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
  - [Base de Dados Local](#base-de-dados-local)
  - [Dashboard de Incidências (MSSQL Remoto)](#dashboard-de-incidências-mssql-remoto)
  - [Variáveis de Ambiente (.env)](#variáveis-de-ambiente-env)
- [Execução](#execução)
  - [Modo interativo](#modo-interativo-pede-o-url-por-input)
  - [Modo linha de comandos](#modo-por-linha-de-comandos-url-como-argumento)
  - [Modo por dados da empresa](#modo-por-dados-da-empresa-sem-saber-o-url)
- [Regras RGPD](#regras-rgpd)
- [Relatórios gerados](#relatórios-gerados)
- [Consultar dados](#consultar-dados)
- [Dashboard de Incidências](#dashboard-de-incidências)
- [Testes](#testes)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Dependências](#dependências)
- [Autor](#autor)

---

## Funcionalidades

### Análise RGPD Automatizada
- **Scraping real** do site com Playwright (headless browser), incluindo execução de JavaScript e redirecionamentos
- **Deteção de banner de consentimento de cookies** (por texto, classes CSS, IDs e scripts de CMP conhecidos)
- **Teste de cookies pré-consentimento**: identifica cookies de tracking/analytics instalados antes de qualquer opt-in
- **Análise de atributos de segurança dos cookies** (`Secure`, `HttpOnly`, `SameSite`)
- **Identificação de scripts de terceiros** (analytics, advertising, social)
- **Deteção de Google Analytics** sem anonimização de IP
- **Análise de formulários** que recolhem dados pessoais sem aviso de finalidade junto ao formulário

### Análise da Política de Privacidade
- **Deteção automática** do link da política de privacidade na página principal
- **Análise multi-página**: segue páginas legais relacionadas (cookies, termos, contactos, RGPD/DPO) para não perder informação espalhada por várias páginas
- **Deteção de idioma** automática (português e inglês)
- **Verificação de elementos obrigatórios do RGPD** no texto:
  - Direito de acesso (Art. 15)
  - Direito ao apagamento (Art. 17)
  - Transferências internacionais (Art. 44-49)
  - Contacto do DPO (Art. 37-39)
  - Prazo de conservação de dados (Art. 13/14)

### Motor de Regras Configurável
- **12 regras RGPD** (R01–R12) definidas em YAML, editáveis sem alterar código
- Cada regra tem severidade (`high`, `medium`, `low`), artigo RGPD associado e recomendação de correção
- Extensível: basta adicionar novas regras ao ficheiro YAML e implementar a verificação correspondente

### Descoberta de Sites por Dados da Empresa
- Encontra o site oficial de uma empresa a partir do nome comercial (pesquisa web + Racius + WHOIS)
- **Sistema de confiança** (`high`, `medium`, `low`) para evitar auditar o site errado
- Consulta o **registo público Racius** para obter NIF, morada e validar a empresa
- Obtém **nameservers** do domínio via WHOIS
- Inclui dados da empresa no relatório e na base de dados

### Persistência e Base de Dados
- **SQLite** por omissão — zero configuração, portátil, funciona imediatamente
- **SQL Server (MSSQL)** disponível para cenários empresariais
- **Modo sem persistência** (`none`) para scans rápidos sem guardar dados
- Tabelas: `Websites`, `ScanRuns`, `Findings`, `Companies`
- **Auto-migração** de esquema em SQLite (cria tabelas automaticamente, incluindo em BDs já existentes)
- **Fail-soft**: falhas na base de dados nunca impedem a geração do relatório

### Dashboard de Incidências (MSSQL Remoto)
- Envia não-conformidades para um **painel MSSQL remoto** via Stored Procedure `[service].[create_notification]`
- Mapeia automaticamente regras para categorias e severidades do dashboard
- **Modo dry-run**: imprime o SQL que seria executado sem ligar à BD
- Fail-soft: falhas no dashboard não impedem o fim do scan

### Relatórios HTML
- Relatórios profissionais com sumário de severidades, não-conformidades ordenadas por gravidade e recomendações
- **Histórico de scans**: cada relatório é guardado com timestamp em `reports/`
- **ID curto** de relatório para referência cruzada com a base de dados
- Secção de **dados da empresa** quando o scan parte de dados empresariais

### Testes e CI/CD
- Suite de **9 ficheiros de testes** com pytest
- Cobertura do motor de regras, scraper, analyzer, modelos, configuração de BD e integração CLI
- **CI automático** com GitHub Actions em cada `push`/`pull request` para `main`

---

## Requisitos

- Python 3.11+ (3.12 recomendado)
- PowerShell no Windows
- Ligação à internet para instalação das dependências e dos browsers do Playwright

---

## Instalação

### Windows PowerShell

```powershell
git clone https://github.com/joaorego7/vigilantia16-06-2026.git
cd vigilantia16-06-2026
py -3.12 -m venv testes_env
.\testes_env\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install
```

### Alternativa, caso `py -3.12` não funcione

```powershell
python -m venv testes_env
.\testes_env\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install
```

### Passo opcional: instalar o projeto como pacote

Só é necessário se quiseres usar o comando `vigilantia <url>` (ver secção "Execução" abaixo).
O modo interativo (`run_vigilantia_mvp.py`) funciona sem este passo.
```powershell
pip install -e .
```

---

## Configuração

### Base de Dados Local

O Vigilantia suporta três modos de persistência local, configuráveis via a variável `VIGILANTIA_DB_TYPE` no ficheiro `.env`:

| Modo | `VIGILANTIA_DB_TYPE` | Descrição |
|---|---|---|
| **SQLite** (padrão) | `sqlite` | Base de dados portátil num único ficheiro. Zero configuração. Tabelas criadas automaticamente. |
| **SQL Server** | `mssql` | Para cenários empresariais. Requer configuração de servidor, credenciais e driver ODBC. |
| **Sem persistência** | `none` | Apenas gera o relatório HTML, sem guardar dados em base de dados. |

#### Usar SQLite (recomendado para desenvolvimento)

É o modo por omissão. Basta ter `VIGILANTIA_DB_TYPE=sqlite` no `.env` (ou não ter `.env` de todo — SQLite é o padrão). O ficheiro `vigilantia.db` é criado automaticamente na raiz do projeto.

Para mudar o caminho do ficheiro SQLite:
```
VIGILANTIA_SQLITE_PATH=caminho/para/outra.db
```

#### Usar SQL Server (MSSQL)

1. Executar o assistente interativo de configuração:
```powershell
python .\configurar_db.py
```

Este script:
- Deteta os drivers ODBC disponíveis no sistema
- Pede servidor, base de dados e credenciais
- Testa a ligação
- Cria a base de dados e as tabelas automaticamente (a partir de `schema.sql`)
- Guarda tudo no ficheiro `.env`

2. Ou configurar manualmente no `.env`:
```
VIGILANTIA_DB_TYPE=mssql
VIGILANTIA_DB_SERVER=localhost\SQLEXPRESS
VIGILANTIA_DB_NAME=Vigilantia
VIGILANTIA_DB_DRIVER=ODBC Driver 18 for SQL Server
VIGILANTIA_DB_TRUSTED=true
VIGILANTIA_DB_TRUST_CERT=true
```

Para autenticação SQL (em vez de Windows):
```
VIGILANTIA_DB_TRUSTED=false
VIGILANTIA_DB_USER=o_meu_user
VIGILANTIA_DB_PASSWORD=a_minha_password
```

#### Desativar persistência

Para correr scans sem guardar dados:
```
VIGILANTIA_DB_TYPE=none
```

#### Mudar de base de dados

Para **mudar de SQLite para SQL Server** (ou vice-versa), basta alterar `VIGILANTIA_DB_TYPE` no `.env`:

```powershell
# Antes (SQLite):
VIGILANTIA_DB_TYPE=sqlite

# Depois (SQL Server):
VIGILANTIA_DB_TYPE=mssql
VIGILANTIA_DB_SERVER=localhost\SQLEXPRESS
VIGILANTIA_DB_NAME=Vigilantia
```

Ou, de forma assistida:
```powershell
python .\configurar_db.py
```

> **Nota:** os dados não são migrados automaticamente entre bases de dados. Cada tipo de BD mantém os seus próprios dados.

#### Tabelas da Base de Dados

As tabelas são `Websites`, `ScanRuns`, `Findings` e `Companies` (esta última só é preenchida quando o scan é iniciado pelos dados de uma empresa — ver "Modo por dados da empresa").

Em SQLite (o modo por omissão) as tabelas são criadas automaticamente na primeira ligação, incluindo em bases de dados criadas antes de a tabela `Companies` existir (auto-migração).

### Dashboard de Incidências (MSSQL Remoto)

O Vigilantia pode enviar as não-conformidades encontradas para um **dashboard de incidências remoto** via SQL Server, chamando a Stored Procedure `[service].[create_notification]`.

#### Ativar o dashboard

No `.env`:
```
VIGILANTIA_DASHBOARD_ENABLED=true
VIGILANTIA_DASHBOARD_SERVER=servidor_remoto
VIGILANTIA_DASHBOARD_NAME=nome_da_bd
VIGILANTIA_DASHBOARD_DRIVER=ODBC Driver 18 for SQL Server
VIGILANTIA_DASHBOARD_TRUSTED=false
VIGILANTIA_DASHBOARD_USER=user
VIGILANTIA_DASHBOARD_PASSWORD=password
VIGILANTIA_DASHBOARD_TRUST_CERT=true

# Parâmetros da SP
VIGILANTIA_CLIENT_ID=1840264
VIGILANTIA_DEVICE_ID=0
VIGILANTIA_AUDIT_TYPE=website_audit
```

#### Modo dry-run (testar sem ligar à BD)

```
VIGILANTIA_DASHBOARD_ENABLED=true
VIGILANTIA_DASHBOARD_DRY_RUN=true
```

Imprime no terminal o SQL que seria executado para cada finding, sem estabelecer ligação ao servidor remoto.

#### Demo do dashboard

Para ver como ficam os dados no formato do dashboard:
```powershell
python .\demo_dashboard.py
```

Cria uma BD SQLite fictícia (`demo_dashboard.db`) com dados de exemplo no formato da tabela `Notifications`.

### Variáveis de Ambiente (.env)

Todas as configurações são lidas do ficheiro `.env` na raiz do projeto. Copiar o `.env.example` como ponto de partida:

```powershell
Copy-Item .env.example .env
```

Depois editar o `.env` conforme necessário. As variáveis disponíveis são:

| Variável | Valores | Descrição |
|---|---|---|
| `VIGILANTIA_DB_TYPE` | `sqlite` / `mssql` / `none` | Tipo de BD local |
| `VIGILANTIA_SQLITE_PATH` | caminho | Ficheiro SQLite (só com `sqlite`) |
| `VIGILANTIA_DB_SERVER` | hostname | Servidor MSSQL (só com `mssql`) |
| `VIGILANTIA_DB_NAME` | nome | Nome da BD MSSQL |
| `VIGILANTIA_DB_DRIVER` | driver ODBC | Driver ODBC para MSSQL |
| `VIGILANTIA_DB_TRUSTED` | `true` / `false` | Autenticação Windows |
| `VIGILANTIA_DB_USER` | username | Utilizador SQL (se `TRUSTED=false`) |
| `VIGILANTIA_DB_PASSWORD` | password | Password SQL (se `TRUSTED=false`) |
| `VIGILANTIA_DB_TRUST_CERT` | `true` / `false` | Confiar no certificado do servidor |
| `VIGILANTIA_DASHBOARD_ENABLED` | `true` / `false` | Ativar envio para dashboard |
| `VIGILANTIA_DASHBOARD_DRY_RUN` | `true` / `false` | Modo dry-run do dashboard |
| `VIGILANTIA_DASHBOARD_SERVER` | hostname | Servidor MSSQL do dashboard |
| `VIGILANTIA_DASHBOARD_NAME` | nome | Nome da BD do dashboard |
| `VIGILANTIA_DASHBOARD_DRIVER` | driver ODBC | Driver ODBC do dashboard |
| `VIGILANTIA_DASHBOARD_TRUSTED` | `true` / `false` | Autenticação Windows no dashboard |
| `VIGILANTIA_DASHBOARD_USER` | username | Utilizador SQL do dashboard |
| `VIGILANTIA_DASHBOARD_PASSWORD` | password | Password SQL do dashboard |
| `VIGILANTIA_DASHBOARD_TRUST_CERT` | `true` / `false` | Confiar no certificado do dashboard |
| `VIGILANTIA_CLIENT_ID` | inteiro | ClientId para a SP do dashboard |
| `VIGILANTIA_DEVICE_ID` | inteiro | DeviceId para a SP do dashboard |
| `VIGILANTIA_AUDIT_TYPE` | texto | Tipo de auditoria (ex: `website_audit`) |

---

## Execução

Existem dois pontos de entrada equivalentes (ambos correm a mesma lógica):

### Modo interativo (pede o URL por input)
```powershell
python .\run_vigilantia_mvp.py
```
Depois de executar, introduza o URL do site a analisar quando o programa pedir.

Exemplo:
```text
https://example.com
```

### Modo por linha de comandos (URL como argumento)

Para usar este modo, instale primeiro o projeto como pacote (uma única vez, dentro do
ambiente virtual):
```powershell
pip install -e .
```

Depois, o URL pode ser passado diretamente como argumento:
```powershell
vigilantia https://example.com
```
(equivalente a `python -m vigilantia.cli https://example.com`, caso o comando `vigilantia`
não fique disponível no PATH)

### Modo por dados da empresa (sem saber o URL)

Se não souber o site da empresa, pode passar os dados da empresa em JSON em vez do URL.
A ferramenta descobre o site oficial (pesquisa web + registo público Racius + WHOIS, em
`src/vigilantia/scraper/company_info.py`), mostra o que encontrou, e só depois corre a
análise RGPD normal sobre esse site:

```powershell
vigilantia '{"company_name": "Feedzai", "country": "Portugal"}'
```

Campos aceites: `company_name` (obrigatório), `legal_name`, `country` e `address`
(opcionais, mas melhoram bastante a precisão da pesquisa e da validação no Racius).

No PowerShell, envolva o JSON em aspas simples. Para nomes com carateres especiais é mais
seguro usar uma variável:

```powershell
$json = '{"company_name": "Ageas Portugal", "legal_name": "Ageas Portugal - Companhia de Seguros, S.A.", "country": "Portugal"}'
vigilantia $json
```

**Confiança na identificação do site.** Antes de analisar, a ferramenta avalia o quanto
confia no site que encontrou:

| Situação | Comportamento |
|---|---|
| Nenhum site encontrado | Cancela (código de saída 1). O `--force` não ajuda: não há URL nenhum. |
| Confiança `low` | Cancela, para não auditar o site errado. Sugere acrescentar `legal_name`/`address`, ou repetir com `--force`. |
| Confiança `medium` | Avisa e continua, sem precisar de `--force`. |
| Confiança `high` | Continua (mensagem apenas informativa). |
| NIF/morada não confirmados no Racius | Nunca cancela — é sobre a fiabilidade dos dados, não sobre a identidade do site. O aviso vai também para o relatório. |

```powershell
vigilantia '{"company_name": "Consultores"}' --force
```

O `--force` só tem efeito neste modo; num scan por URL é ignorado.

**O que muda no resultado.** Quando o scan arranca pelos dados da empresa, o relatório HTML
passa a abrir com uma secção *Dados da empresa* (nome, NIF, morada, nameservers e se os
dados foram confirmados no registo público), e esses dados ficam também guardados na tabela
`Companies` da base de dados. Um scan normal por URL continua exatamente como antes: sem
essa secção e sem registo na `Companies`.

---

## Regras RGPD

As 12 regras de conformidade estão definidas em [`rules/gdpr_rules.yaml`](rules/gdpr_rules.yaml), editáveis sem alterar código:

| Regra | Severidade | Artigo RGPD | O que verifica |
|---|---|---|---|
| **R01** | 🔴 `high` | Art. 6, 7 | Banner de consentimento em falta quando há cookies de tracking |
| **R02** | 🔴 `high` | Art. 6, 7 | Cookies de tracking instalados antes de qualquer consentimento |
| **R03** | 🟡 `medium` | Art. 5(1)(c) | Google Analytics sem anonimização de IP |
| **R04** | 🟡 `medium` | Art. 32 | Cookies sem atributos `Secure`/`HttpOnly` |
| **R05** | 🔴 `high` | Art. 13, 14 | Política de privacidade em falta ou sem link na página principal |
| **R06** | 🟡 `medium` | Art. 15 | Política não menciona o direito de acesso |
| **R07** | 🟡 `medium` | Art. 17 | Política não menciona o direito ao apagamento |
| **R08** | 🟡 `medium` | Art. 44-49 | Política não menciona transferências internacionais |
| **R09** | 🟢 `low` | Art. 37-39 | Política não identifica o DPO ou contacto equivalente |
| **R10** | 🟡 `medium` | Art. 13(2)(a) | Política não indica o prazo de conservação de dados |
| **R11** | 🟡 `medium` | Art. 13 | Formulário recolhe dados pessoais sem aviso de finalidade |
| **R12** | 🟢 `low` | N/A | Política de privacidade não pôde ser descarregada/analisada (limitação da ferramenta) |

Para **adicionar uma nova regra**: basta acrescentar a entrada no ficheiro YAML e implementar a verificação correspondente em [`src/vigilantia/analyzer/rule_engine.py`](src/vigilantia/analyzer/rule_engine.py).

---

## Relatórios gerados

Cada análise gera um relatório HTML guardado em `reports/`, com nome baseado no domínio e no
momento da análise (ex.: `reports/vigilantia_example_com_20260709-101500.html`), o que permite
manter um histórico de scans ao longo do tempo. É também sempre atualizada uma cópia com o
resultado mais recente em `relatorio.html`, na raiz do projeto.

O relatório inclui:
- Sumário de severidades (high / medium / low)
- Lista de não-conformidades ordenada por gravidade
- Descrição, recomendação e artigo RGPD para cada não-conformidade
- Detalhe dos cookies de tracking encontrados antes do consentimento
- ID curto do relatório (para referência cruzada com a BD)
- Secção de dados da empresa (quando o scan parte de dados empresariais)
- Aviso legal sobre as limitações da ferramenta

---

## Consultar dados

### No terminal (SQLite)

```powershell
python .\view_db.py
```
Mostra um relatório unificado de todos os sites, scans e não-conformidades.

> **Nota:** o `view_db.py` original usa MSSQL. Para SQLite, os dados podem ser consultados diretamente com ferramentas como [DB Browser for SQLite](https://sqlitebrowser.org/) ou via Python.

### No SSMS (SQL Server Management Studio)

Para além do `view_db.py`, pode utilizar o script SQL pré-configurado [`report_search.sql`](report_search.sql):

1. Abrir no SSMS
2. Certificar-se de que o `USE` aponta para a base de dados correta (ex: `clientes_websites`)
3. Executar (F5) para obter um relatório completo e unificado

---

## Dashboard de Incidências

O dashboard é um painel MSSQL remoto que recebe as não-conformidades como notificações via Stored Procedure. O mapeamento de regras para categorias do dashboard é:

| Regra | Categoria no Dashboard |
|---|---|
| R01 | `missing_cookie_consent` |
| R02 | `tracking_cookies_before_consent` |
| R03 | `analytics_no_ip_anonymization` |
| R04 | `cookies_missing_secure_flags` |
| R05 | `missing_privacy_policy` |
| R06 | `policy_missing_right_of_access` |
| R07 | `policy_missing_right_to_erasure` |
| R08 | `policy_missing_international_transfers` |
| R09 | `policy_missing_dpo_contact` |
| R10 | `policy_missing_retention_period` |
| R11 | `forms_without_purpose_notice` |
| R12 | `privacy_policy_unreachable` |

Os níveis de severidade mapeiam para: `high` → 1 (crítico), `medium` → 2, `low` → 3 (recomendação).

Para ver uma demonstração do formato dos dados:
```powershell
python .\demo_dashboard.py
```

---

## Testes

O projeto tem uma suite de testes automáticos (`pytest`) com 9 ficheiros de testes:

| Ficheiro | O que testa |
|---|---|
| `test_analyzer.py` | Análise de texto da política de privacidade |
| `test_rule_engine.py` | Motor de regras RGPD |
| `test_scraper.py` | Extractor do scraper (HTML → SiteData) |
| `test_fetcher.py` | Fetcher (Playwright) |
| `test_models.py` | Modelos de dados (Pydantic) |
| `test_db_config.py` | Configuração da base de dados |
| `test_db_repository.py` | Repositórios (Websites, ScanRuns, Findings, Companies) |
| `test_cli_db_integration.py` | Integração CLI + base de dados |
| `test_cli_company.py` | Integração CLI + descoberta de empresa |

Para correr os testes:

```powershell
pip install pytest
pytest -v
```

Os testes correm também automaticamente em cada `push`/`pull request` para `main`, através do
workflow definido em `.github/workflows/ci.yml`.

---

## Estrutura do projeto

```
vigilantia16-06-2026/
├── run_vigilantia_mvp.py       # ponto de entrada interativo (pede URL por input)
├── configurar_db.py            # assistente interativo de configuração do SQL Server
├── view_db.py                  # script para consultar a base de dados (websites e findings)
├── verify_sites.py             # verificação independente de sites (requests + BeautifulSoup)
├── demo_dashboard.py           # demonstração do formato de dados do dashboard
├── report_search.sql           # query SQL para relatório unificado no SSMS
├── requirements.txt            # dependências do projeto
├── pyproject.toml              # configuração do pacote Python (setuptools)
├── .env                        # configuração local (não versionado)
├── .env.example                # exemplo de configuração com todas as variáveis disponíveis
├── DISCLAIMER.md               # aviso legal sobre as limitações da ferramenta
├── rules/
│   └── gdpr_rules.yaml         # definição das 12 regras RGPD (R01-R12)
├── templates/
│   └── report.html.j2          # template Jinja2 do relatório HTML
├── reports/                    # relatórios gerados por cada scan (histórico)
├── src/vigilantia/
│   ├── cli.py                  # ponto de entrada CLI (Typer) + lógica partilhada do scan
│   ├── paths.py                # caminhos absolutos do projeto (regras, templates, relatórios)
│   ├── reporter.py             # geração do relatório HTML (Jinja2)
│   ├── scraper/
│   │   ├── fetcher.py          # fetch do HTML com Playwright (headless browser)
│   │   ├── extractor.py        # extração de dados do HTML (cookies, scripts, formulários, política)
│   │   ├── cookie_tester.py    # classificação de cookies (tracking, funcional, etc.)
│   │   ├── company_info.py     # descoberta do site a partir de dados da empresa
│   │   └── main.py             # orquestração do scraper (fetch + extract → SiteData)
│   ├── analyzer/
│   │   ├── rule_engine.py      # motor de regras RGPD (avalia R01-R12)
│   │   └── privacy_text.py     # análise de texto da política de privacidade (multi-página)
│   ├── db/
│   │   ├── config.py           # configuração da BD (DatabaseConfig + DashboardConfig)
│   │   ├── connection.py       # gestão de ligações (SQLite / MSSQL / Dashboard)
│   │   ├── repository.py       # repositórios (Websites, ScanRuns, Findings, Companies)
│   │   ├── dashboard.py        # envio de incidências para o dashboard remoto (SP)
│   │   └── schema.sql          # schema SQL Server (tabelas, índices, constraints)
│   └── models/
│       ├── site_data.py        # SiteData, Cookie, ThirdPartyScript, Form (Pydantic)
│       └── finding.py          # Finding (resultado de uma regra RGPD)
├── tests/                      # suite de testes automáticos (pytest, 9 ficheiros)
└── .github/workflows/ci.yml    # CI: corre os testes em cada push/PR para main
```

---

## Dependências

O projeto usa `requirements.txt` para instalar as bibliotecas necessárias:

| Pacote | Utilização |
|---|---|
| `playwright` | Scraping real de sites (headless browser) |
| `beautifulsoup4` | Parsing e extração de dados do HTML |
| `requests` | HTTP requests (verificação independente, company_info) |
| `pydantic` | Validação de dados e modelos |
| `typer` | Interface de linha de comandos (CLI) |
| `PyYAML` | Leitura das regras RGPD |
| `Jinja2` | Templates dos relatórios HTML |
| `langdetect` | Deteção de idioma da política de privacidade |
| `pyodbc` | Ligação a SQL Server (MSSQL) |
| `python-dotenv` | Leitura de variáveis do ficheiro `.env` |

Instalar tudo:
```powershell
pip install -r requirements.txt
```

### Notas adicionais

- O projeto utiliza Playwright, por isso é necessário correr `playwright install` após instalar as dependências, para descarregar os browsers suportados.
- Recomenda-se a utilização de um ambiente virtual para isolar as dependências do projeto.
- O `pyodbc` requer os C++ Build Tools para compilar no Windows. Se não precisar de SQL Server, a ferramenta funciona perfeitamente só com SQLite.

---

## Autor

João Rêgo