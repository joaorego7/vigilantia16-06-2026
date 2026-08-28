# Vigilantia

Vigilantia é uma ferramenta de auditoria RGPD para websites, desenvolvida em Python. Analisa automaticamente sites em busca de não-conformidades com o Regulamento Geral sobre a Proteção de Dados (RGPD), gerando relatórios HTML detalhados com as não-conformidades encontradas, recomendações de correção e referências aos artigos legais aplicáveis.

> **Aviso legal:** Esta ferramenta é um apoio técnico e não substitui uma auditoria jurídica profissional. Ver [DISCLAIMER.md](DISCLAIMER.md) para mais informação.

---

## Índice

- [Quick Start (Guia Rápido)](#quick-start-guia-rápido)
- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Instalação Passo a Passo](#instalação-passo-a-passo)
- [Configuração](#configuração)
  - [Ficheiro .env](#1-criar-o-ficheiro-env)
  - [Base de Dados Local](#2-escolher-a-base-de-dados-local)
  - [Dashboard de Incidências](#3-configurar-o-dashboard-de-incidências-opcional)
  - [Referência de Variáveis de Ambiente](#referência-completa-de-variáveis-de-ambiente)
- [Como Usar](#como-usar)
  - [Modo interativo](#opção-a-modo-interativo-mais-simples)
  - [Modo linha de comandos](#opção-b-modo-por-linha-de-comandos)
  - [Modo por dados da empresa](#opção-c-modo-por-dados-da-empresa-sem-saber-o-url)
- [O Que Acontece Durante um Scan](#o-que-acontece-durante-um-scan)
- [Regras RGPD](#regras-rgpd)
- [Relatórios Gerados](#relatórios-gerados)
- [Consultar Dados na Base de Dados](#consultar-dados-na-base-de-dados)
- [Dashboard de Incidências](#dashboard-de-incidências)
- [Como Atualizar o Projeto](#como-atualizar-o-projeto)
- [Como Mudar de Base de Dados](#como-mudar-de-base-de-dados)
- [Testes](#testes)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Dependências](#dependências)
- [Resolução de Problemas](#resolução-de-problemas)
- [Autor](#autor)

---

## Quick Start (Guia Rápido)

Para quem quer começar **o mais rápido possível**:

```powershell
# 1. Clonar o repositório
git clone https://github.com/joaorego7/vigilantia16-06-2026.git
cd vigilantia16-06-2026

# 2. Criar e ativar o ambiente virtual
py -3.12 -m venv testes_env
.\testes_env\Scripts\Activate.ps1

# 3. Instalar dependências e browsers
pip install -r requirements.txt
playwright install

# 4. Correr a primeira análise (modo interativo)
python .\run_vigilantia_mvp.py
# Quando pedir o URL, escrever por exemplo: https://www.pcm.pt
```

O relatório HTML é gerado automaticamente em `relatorio.html` e em `reports/`.
A base de dados SQLite (`vigilantia.db`) é criada automaticamente — não precisa de configuração.

> Para funcionalidades avançadas (CLI com `vigilantia <url>`, SQL Server, dashboard), ver as secções abaixo.

---

## Funcionalidades

### Análise RGPD Automatizada
- **Scraping real** do site com Playwright (headless browser), incluindo execução de JavaScript e redirecionamentos
- **Deteção de banner de consentimento de cookies** (por texto, classes CSS, IDs e scripts de CMP conhecidos como OneTrust, Didomi, CookieBot, etc.)
- **Teste de cookies pré-consentimento**: identifica cookies de tracking/analytics instalados antes de qualquer opt-in
- **Análise de atributos de segurança dos cookies** (`Secure`, `HttpOnly`, `SameSite`)
- **Identificação de scripts de terceiros** (analytics, advertising, social)
- **Deteção de Google Analytics** sem anonimização de IP
- **Análise de formulários** que recolhem dados pessoais (email, nome, telefone, morada) sem aviso de finalidade junto ao formulário

### Análise da Política de Privacidade
- **Deteção automática** do link da política de privacidade na página principal
- **Análise multi-página**: segue páginas legais relacionadas (cookies, termos, contactos, RGPD/DPO) porque muitos sites espalham a informação exigida por várias páginas
- **Deteção de idioma** automática (português e inglês)
- **Verificação de 5 elementos obrigatórios do RGPD** no texto:
  - Direito de acesso (Art. 15)
  - Direito ao apagamento / "direito a ser esquecido" (Art. 17)
  - Transferências internacionais de dados (Art. 44-49)
  - Contacto do DPO — Encarregado de Proteção de Dados (Art. 37-39)
  - Prazo de conservação de dados (Art. 13/14)

### Motor de Regras Configurável
- **12 regras RGPD** (R01–R12) definidas em ficheiro YAML, editáveis sem alterar código Python
- Cada regra tem severidade (`high`, `medium`, `low`), artigo RGPD associado e recomendação de correção
- **Extensível**: basta adicionar novas regras ao ficheiro YAML e implementar a verificação correspondente no motor

### Descoberta de Sites por Dados da Empresa
- Encontra o site oficial de uma empresa a partir do **nome comercial** (pesquisa web + Racius + WHOIS)
- **Sistema de confiança** (`high`, `medium`, `low`) para evitar auditar o site errado
- Consulta o **registo público Racius** para obter NIF, morada e validar a empresa
- Obtém **nameservers** do domínio via WHOIS
- Inclui dados da empresa no relatório HTML e na base de dados

### Persistência e Base de Dados
- **SQLite** por omissão — zero configuração, portátil, funciona imediatamente
- **SQL Server (MSSQL)** disponível para cenários empresariais
- **Modo sem persistência** (`none`) para scans rápidos sem guardar dados
- 4 tabelas: `Websites`, `ScanRuns`, `Findings`, `Companies`
- **Auto-migração** de esquema em SQLite (cria tabelas novas automaticamente, mesmo em BDs já existentes)
- **Fail-soft**: falhas na base de dados **nunca** impedem a geração do relatório

### Dashboard de Incidências (MSSQL Remoto)
- Envia não-conformidades para um **painel MSSQL remoto** via Stored Procedure `[service].[create_notification]`
- Mapeia automaticamente regras para categorias e severidades do dashboard
- **Modo dry-run**: imprime o SQL que seria executado sem ligar à BD (para testar)
- Fail-soft: falhas no dashboard não impedem o fim do scan

### Relatórios HTML
- Relatórios profissionais com sumário de severidades, não-conformidades ordenadas por gravidade e recomendações
- **Histórico de scans**: cada relatório é guardado com timestamp em `reports/`
- **ID curto** de relatório para referência cruzada com a base de dados
- Secção de **dados da empresa** quando o scan parte de dados empresariais (nome legal, NIF, morada, nameservers)

### Testes e CI/CD
- Suite de **9 ficheiros de testes** com pytest
- Cobertura do motor de regras, scraper, analyzer, modelos, configuração de BD e integração CLI
- **CI automático** com GitHub Actions em cada `push`/`pull request` para `main`

---

## Requisitos

Antes de instalar, garantir que tem:

1. **Python 3.11 ou superior** (3.12 recomendado) — [download aqui](https://www.python.org/downloads/)
2. **PowerShell** (já vem com o Windows)
3. **Git** — [download aqui](https://git-scm.com/downloads)
4. **Ligação à internet** para instalação das dependências e dos browsers do Playwright

> **Verificar se o Python está instalado:**
> ```powershell
> python --version
> ```
> Deve mostrar algo como `Python 3.12.x`. Se não funcionar, tente `py --version`.

---

## Instalação Passo a Passo

### Passo 1: Clonar o repositório

```powershell
git clone https://github.com/joaorego7/vigilantia16-06-2026.git
cd vigilantia16-06-2026
```

### Passo 2: Criar o ambiente virtual

O ambiente virtual isola as dependências do projeto do resto do sistema.

```powershell
py -3.12 -m venv testes_env
```

> Se `py -3.12` não funcionar, usar:
> ```powershell
> python -m venv testes_env
> ```

### Passo 3: Ativar o ambiente virtual

```powershell
.\testes_env\Scripts\Activate.ps1
```

Quando estiver ativo, o terminal mostra `(testes_env)` no início da linha. **Este passo tem de ser repetido sempre que se abre um novo terminal.**

> **Se der erro de permissões (ExecutionPolicy):**
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### Passo 4: Instalar as dependências

```powershell
pip install -r requirements.txt
```

### Passo 5: Instalar os browsers do Playwright

O Playwright precisa de descarregar os browsers que usa para scraping:

```powershell
playwright install
```

### Passo 6 (opcional): Instalar o projeto como pacote

Só é necessário se quiser usar o comando `vigilantia <url>` diretamente no terminal.
O modo interativo (`run_vigilantia_mvp.py`) funciona sem este passo.

```powershell
pip install -e .
```

### Passo 7 (opcional): Criar o ficheiro `.env`

Para personalizar a configuração (base de dados, dashboard, etc.):

```powershell
Copy-Item .env.example .env
```

Depois editar o `.env` conforme necessário (ver secção [Configuração](#configuração)).

> **Se não criar o `.env`**, a ferramenta funciona com os valores por omissão: SQLite ativo, dashboard desativado.

---

## Configuração

### 1. Criar o ficheiro `.env`

Todas as configurações são lidas do ficheiro `.env` na raiz do projeto. Para começar:

```powershell
Copy-Item .env.example .env
```

O ficheiro `.env.example` tem todas as variáveis disponíveis com comentários explicativos. Se não criar o `.env`, os valores por omissão são usados (SQLite ativo, dashboard desativado).

### 2. Escolher a base de dados local

O Vigilantia suporta três modos de persistência, configuráveis pela variável `VIGILANTIA_DB_TYPE`:

| Modo | Valor | Quando usar |
|---|---|---|
| **SQLite** (padrão) | `sqlite` | Desenvolvimento, testes, uso individual. Zero configuração. |
| **SQL Server** | `mssql` | Ambientes empresariais com SQL Server já instalado. |
| **Sem persistência** | `none` | Scans rápidos sem guardar dados. Só gera o relatório HTML. |

#### Opção A: SQLite (recomendado — funciona sem configuração)

É o modo por omissão. Não precisa de alterar nada. O ficheiro `vigilantia.db` é criado automaticamente na raiz do projeto na primeira utilização.

No `.env`:
```
VIGILANTIA_DB_TYPE=sqlite
VIGILANTIA_SQLITE_PATH=vigilantia.db
```

> Pode mudar `VIGILANTIA_SQLITE_PATH` para guardar a BD noutro sítio.

#### Opção B: SQL Server (MSSQL)

**Forma assistida (recomendada):**

```powershell
python .\configurar_db.py
```

Este script interativo guia-o passo a passo:
1. Deteta os drivers ODBC disponíveis no sistema e pede para escolher um
2. Pede o nome/instância do servidor (ex: `localhost\SQLEXPRESS`)
3. Pede o nome da base de dados (ex: `Vigilantia`)
4. Pergunta se quer usar Autenticação Windows ou SQL (user/password)
5. Testa a ligação ao servidor
6. Se a BD não existir, pergunta se quer criá-la automaticamente
7. Pergunta se quer criar/inicializar as tabelas (a partir de `schema.sql`)
8. Guarda tudo no ficheiro `.env`

**Forma manual (editar o `.env` diretamente):**

```
VIGILANTIA_DB_TYPE=mssql
VIGILANTIA_DB_SERVER=localhost\SQLEXPRESS
VIGILANTIA_DB_NAME=Vigilantia
VIGILANTIA_DB_DRIVER=ODBC Driver 18 for SQL Server
VIGILANTIA_DB_TRUSTED=true
VIGILANTIA_DB_TRUST_CERT=true
```

Para autenticação SQL (user/password em vez de Windows):
```
VIGILANTIA_DB_TRUSTED=false
VIGILANTIA_DB_USER=o_meu_user
VIGILANTIA_DB_PASSWORD=a_minha_password
```

#### Opção C: Sem persistência

```
VIGILANTIA_DB_TYPE=none
```

Os scans continuam a funcionar normalmente, mas os dados não são guardados em base de dados. Apenas o relatório HTML é gerado.

#### Tabelas da Base de Dados

| Tabela | O que guarda |
|---|---|
| `Websites` | Sites analisados (URL, domínio, data de criação) |
| `ScanRuns` | Execuções de scan (website, estado, datas, referência ao relatório) |
| `Findings` | Não-conformidades encontradas (regra, descrição, evidência, severidade) |
| `Companies` | Dados da empresa (só preenchida no modo por dados da empresa) |

Em **SQLite**, todas as tabelas são criadas automaticamente na primeira ligação. Mesmo que a BD já exista de uma versão anterior, tabelas novas (como `Companies`) são adicionadas automaticamente.

### 3. Configurar o dashboard de incidências (opcional)

O dashboard é um painel MSSQL remoto que recebe as não-conformidades como notificações. **Só é necessário se tiver um servidor MSSQL remoto com a Stored Procedure `[service].[create_notification]`.**

#### Passo 1: Ativar no `.env`

```
VIGILANTIA_DASHBOARD_ENABLED=true
```

#### Passo 2: Configurar a ligação ao servidor remoto

```
VIGILANTIA_DASHBOARD_SERVER=nome_ou_ip_do_servidor
VIGILANTIA_DASHBOARD_NAME=nome_da_base_de_dados
VIGILANTIA_DASHBOARD_DRIVER=ODBC Driver 18 for SQL Server
VIGILANTIA_DASHBOARD_TRUSTED=false
VIGILANTIA_DASHBOARD_USER=o_meu_user
VIGILANTIA_DASHBOARD_PASSWORD=a_minha_password
VIGILANTIA_DASHBOARD_TRUST_CERT=true
```

#### Passo 3: Definir os parâmetros da Stored Procedure

```
VIGILANTIA_CLIENT_ID=1840264
VIGILANTIA_DEVICE_ID=0
VIGILANTIA_AUDIT_TYPE=website_audit
```

#### Testar sem ligar à BD (modo dry-run)

Para ver o SQL que seria executado sem realmente ligar ao servidor:

```
VIGILANTIA_DASHBOARD_ENABLED=true
VIGILANTIA_DASHBOARD_DRY_RUN=true
```

Corra um scan normalmente e o terminal mostrará as chamadas à SP que seriam feitas.

#### Demo do dashboard

Para ver um exemplo de como ficam os dados no formato do dashboard:

```powershell
python .\demo_dashboard.py
```

Cria uma BD SQLite fictícia (`demo_dashboard.db`) com dados de exemplo e mostra-os no terminal.

### Referência completa de variáveis de ambiente

| Variável | Valores | Padrão | Descrição |
|---|---|---|---|
| **Base de dados local** | | | |
| `VIGILANTIA_DB_TYPE` | `sqlite` / `mssql` / `none` | `sqlite` | Tipo de BD local |
| `VIGILANTIA_SQLITE_PATH` | caminho | `vigilantia.db` | Ficheiro SQLite |
| `VIGILANTIA_DB_SERVER` | hostname | `localhost\SQLEXPRESS` | Servidor MSSQL |
| `VIGILANTIA_DB_NAME` | nome | `Vigilantia` | Nome da BD MSSQL |
| `VIGILANTIA_DB_DRIVER` | driver ODBC | `ODBC Driver 18 for SQL Server` | Driver ODBC |
| `VIGILANTIA_DB_TRUSTED` | `true` / `false` | `true` | Autenticação Windows |
| `VIGILANTIA_DB_USER` | username | | Utilizador SQL |
| `VIGILANTIA_DB_PASSWORD` | password | | Password SQL |
| `VIGILANTIA_DB_TRUST_CERT` | `true` / `false` | `true` | Confiar no certificado |
| **Dashboard remoto** | | | |
| `VIGILANTIA_DASHBOARD_ENABLED` | `true` / `false` | `false` | Ativar envio |
| `VIGILANTIA_DASHBOARD_DRY_RUN` | `true` / `false` | `false` | Modo dry-run |
| `VIGILANTIA_DASHBOARD_SERVER` | hostname | | Servidor MSSQL |
| `VIGILANTIA_DASHBOARD_NAME` | nome | | Nome da BD |
| `VIGILANTIA_DASHBOARD_DRIVER` | driver ODBC | `ODBC Driver 18 for SQL Server` | Driver ODBC |
| `VIGILANTIA_DASHBOARD_TRUSTED` | `true` / `false` | `false` | Autenticação Windows |
| `VIGILANTIA_DASHBOARD_USER` | username | | Utilizador SQL |
| `VIGILANTIA_DASHBOARD_PASSWORD` | password | | Password SQL |
| `VIGILANTIA_DASHBOARD_TRUST_CERT` | `true` / `false` | `true` | Confiar no certificado |
| `VIGILANTIA_CLIENT_ID` | inteiro | `1` | ClientId para a SP |
| `VIGILANTIA_DEVICE_ID` | inteiro | `0` | DeviceId para a SP |
| `VIGILANTIA_AUDIT_TYPE` | texto | `website_audit` | Tipo de auditoria |

---

## Como Usar

> **Pré-requisito:** o ambiente virtual tem de estar ativo. Se o terminal não mostrar `(testes_env)` no início da linha, ativar com:
> ```powershell
> .\testes_env\Scripts\Activate.ps1
> ```

### Opção A: Modo interativo (mais simples)

1. Executar o script:
```powershell
python .\run_vigilantia_mvp.py
```

2. Quando o programa pedir, escrever o URL do site a analisar:
```text
https://www.pcm.pt
```

3. Aguardar que o scan termine (pode demorar 30s a 2min, dependendo do site).

4. O relatório é gerado automaticamente:
   - Último relatório: `relatorio.html` (na raiz do projeto)
   - Histórico: `reports/vigilantia_www_pcm_pt_20260828-101500.html`

### Opção B: Modo por linha de comandos

**Requisito extra:** instalar o projeto como pacote (uma única vez):
```powershell
pip install -e .
```

Depois, passar o URL diretamente:
```powershell
vigilantia https://www.pcm.pt
```

Se o comando `vigilantia` não funcionar, usar a alternativa:
```powershell
python -m vigilantia.cli https://www.pcm.pt
```

### Opção C: Modo por dados da empresa (sem saber o URL)

Se não souber o site da empresa, pode passar os dados da empresa em JSON. A ferramenta descobre o site oficial automaticamente (pesquisa web + Racius + WHOIS) e depois corre a análise RGPD:

**Passo 1:** Preparar os dados em JSON:
```powershell
vigilantia '{"company_name": "Feedzai", "country": "Portugal"}'
```

**Campos disponíveis:**

| Campo | Obrigatório? | Descrição |
|---|---|---|
| `company_name` | ✅ Sim | Nome comercial da empresa |
| `legal_name` | Não (recomendado) | Nome legal completo (melhora a pesquisa no Racius) |
| `country` | Não (recomendado) | País da empresa |
| `address` | Não | Morada da sede (melhora a validação no registo público) |

**Passo 2:** A ferramenta mostra o resultado da pesquisa (site encontrado, confiança, NIF, etc.) e decide se avança:

| Confiança | O que acontece |
|---|---|
| `high` | ✅ Continua automaticamente |
| `medium` | ⚠️ Avisa e continua |
| `low` | ❌ Cancela (usar `--force` para forçar) |
| Nenhum site encontrado | ❌ Cancela sempre (não há nada para analisar) |

**Passo 3:** Se a confiança for baixa mas quiser continuar na mesma:
```powershell
vigilantia '{"company_name": "Consultores"}' --force
```

> O `--force` só se aplica a este modo. Num scan por URL é ignorado.

**Exemplo completo com todos os campos:**
```powershell
$json = '{"company_name": "Ageas Portugal", "legal_name": "Ageas Portugal - Companhia de Seguros, S.A.", "country": "Portugal"}'
vigilantia $json
```

> No PowerShell, envolver o JSON em aspas simples. Para nomes com carateres especiais, usar uma variável como no exemplo acima.

**O que muda no relatório:** Quando o scan parte dos dados da empresa, o relatório HTML abre com uma secção extra *Dados da empresa* (nome legal, NIF, morada, nameservers, verificação no registo público). Esses dados ficam também na tabela `Companies` da BD.

---

## O Que Acontece Durante um Scan

Quando corre um scan, a ferramenta executa estes passos pela seguinte ordem:

```
1. Regista o início do scan na BD (Websites + ScanRuns)
       ↓
2. Scraper: abre o site com Playwright, extrai HTML, cookies,
   scripts, formulários, link da política de privacidade
       ↓
3. Análise da política de privacidade (multi-página):
   descarrega e analisa o texto, verifica os 5 elementos RGPD
       ↓
4. Motor de regras: avalia as 12 regras RGPD (R01-R12)
   e gera a lista de não-conformidades (findings)
       ↓
5. Teste de cookies pré-consentimento:
   classifica os cookies como tracking, funcional, etc.
       ↓
6. Geração do relatório HTML
   (guardado em reports/ e relatorio.html)
       ↓
7. Grava os findings e dados da empresa na BD
       ↓
8. Envia para o dashboard remoto (se ativo)
```

**No terminal**, durante o scan, vai ver:
- Resumo de severidades (quantos problemas graves, médios e baixos)
- Lista detalhada de cada não-conformidade com descrição, recomendação e evidência
- Resultado do teste de cookies (quantos cookies, quantos de tracking)
- Caminho do relatório gerado

**Se algo falhar na BD ou no dashboard**, o scan continua normalmente — apenas mostra um aviso `[BD] Aviso: ...` ou `[DASHBOARD] Aviso: ...` e gera o relatório na mesma (comportamento fail-soft).

---

## Regras RGPD

As 12 regras de conformidade estão definidas em [`rules/gdpr_rules.yaml`](rules/gdpr_rules.yaml), editáveis sem alterar código Python:

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
| **R12** | 🟢 `low` | N/A | Política de privacidade não pôde ser descarregada/analisada |

**Para adicionar uma nova regra:**
1. Abrir `rules/gdpr_rules.yaml` e acrescentar a entrada (seguir o formato das existentes)
2. Implementar a verificação correspondente em `src/vigilantia/analyzer/rule_engine.py`

---

## Relatórios Gerados

Cada análise gera **dois ficheiros**:

| Ficheiro | Localização | Descrição |
|---|---|---|
| Relatório com timestamp | `reports/vigilantia_www_pcm_pt_20260828-101500.html` | Histórico — nunca é sobrescrito |
| Último relatório | `relatorio.html` (raiz do projeto) | Sempre sobrescrito com o resultado mais recente |

**Para abrir um relatório**, basta fazer duplo clique no ficheiro HTML — abre no browser.

O relatório inclui:
- **Sumário de severidades** (quantos problemas high / medium / low)
- **Lista de não-conformidades** ordenada da mais grave para a menos grave
- Para cada não-conformidade: descrição, recomendação de correção, artigo RGPD e evidência
- **Cookies de tracking** encontrados antes do consentimento (nome, domínio)
- **ID curto do relatório** (8 caracteres, para referência cruzada com a BD)
- **Dados da empresa** (quando o scan partiu de dados empresariais)
- **Aviso legal** sobre as limitações da ferramenta

---

## Consultar Dados na Base de Dados

### SQLite (modo padrão)

Os dados ficam no ficheiro `vigilantia.db` na raiz do projeto. Para consultá-los:

**Opção 1:** Usar o [DB Browser for SQLite](https://sqlitebrowser.org/) (interface gráfica):
1. Descarregar e instalar o DB Browser
2. Abrir o ficheiro `vigilantia.db`
3. Ir ao separador "Browse Data" e escolher a tabela

**Opção 2:** Usar Python no terminal:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('vigilantia.db'); print([r for r in conn.execute('SELECT * FROM Websites')])"
```

### SQL Server (MSSQL)

**No terminal:**
```powershell
python .\view_db.py
```
Mostra um relatório unificado com todos os sites, scans e não-conformidades numa tabela.

**No SSMS (SQL Server Management Studio):**
1. Abrir o ficheiro [`report_search.sql`](report_search.sql) no SSMS
2. Alterar o `USE` para apontar para a base de dados correta (ex: `USE clientes_websites`)
3. Executar (F5) para obter um relatório completo e unificado

---

## Dashboard de Incidências

O dashboard é um painel MSSQL remoto que recebe as não-conformidades como notificações via Stored Procedure `[service].[create_notification]`.

### Mapeamento de regras para o dashboard

Cada regra é mapeada para uma categoria e um nível de severidade:

| Regra | Categoria no Dashboard | Nível |
|---|---|---|
| R01 | `missing_cookie_consent` | Conforme severidade |
| R02 | `tracking_cookies_before_consent` | Conforme severidade |
| R03 | `analytics_no_ip_anonymization` | Conforme severidade |
| R04 | `cookies_missing_secure_flags` | Conforme severidade |
| R05 | `missing_privacy_policy` | Conforme severidade |
| R06 | `policy_missing_right_of_access` | Conforme severidade |
| R07 | `policy_missing_right_to_erasure` | Conforme severidade |
| R08 | `policy_missing_international_transfers` | Conforme severidade |
| R09 | `policy_missing_dpo_contact` | Conforme severidade |
| R10 | `policy_missing_retention_period` | Conforme severidade |
| R11 | `forms_without_purpose_notice` | Conforme severidade |
| R12 | `privacy_policy_unreachable` | Conforme severidade |

Mapeamento de severidade: `high` → 1 (crítico), `medium` → 2 (médio), `low` → 3 (recomendação).

---

## Como Atualizar o Projeto

Quando houver atualizações no repositório:

### Passo 1: Ativar o ambiente virtual (se não estiver ativo)

```powershell
cd vigilantia16-06-2026
.\testes_env\Scripts\Activate.ps1
```

### Passo 2: Puxar as alterações do GitHub

```powershell
git pull origin main
```

### Passo 3: Atualizar as dependências (caso tenham mudado)

```powershell
pip install -r requirements.txt
```

### Passo 4: Atualizar os browsers do Playwright (se necessário)

```powershell
playwright install
```

### Passo 5: Reinstalar o pacote (se usar o comando `vigilantia`)

```powershell
pip install -e .
```

> **Nota:** o ficheiro `.env` **não é afetado** pelo `git pull` (está no `.gitignore`). As suas configurações locais mantêm-se.

---

## Como Mudar de Base de Dados

### De SQLite para SQL Server

1. Abrir o ficheiro `.env`
2. Alterar:
```
VIGILANTIA_DB_TYPE=mssql
VIGILANTIA_DB_SERVER=localhost\SQLEXPRESS
VIGILANTIA_DB_NAME=Vigilantia
VIGILANTIA_DB_DRIVER=ODBC Driver 18 for SQL Server
VIGILANTIA_DB_TRUSTED=true
VIGILANTIA_DB_TRUST_CERT=true
```
3. Executar o assistente para criar as tabelas:
```powershell
python .\configurar_db.py
```

### De SQL Server para SQLite

1. Abrir o ficheiro `.env`
2. Alterar:
```
VIGILANTIA_DB_TYPE=sqlite
VIGILANTIA_SQLITE_PATH=vigilantia.db
```
3. Não é preciso mais nada — as tabelas SQLite são criadas automaticamente.

### Desativar a base de dados

1. Abrir o ficheiro `.env`
2. Alterar:
```
VIGILANTIA_DB_TYPE=none
```

> **Nota:** os dados **não são migrados** automaticamente entre bases de dados. Cada tipo de BD mantém os seus próprios dados. Os relatórios HTML em `reports/` não são afetados.

---

## Testes

O projeto tem uma suite de testes automáticos com **9 ficheiros** (`pytest`):

| Ficheiro | O que testa |
|---|---|
| `test_analyzer.py` | Análise de texto da política de privacidade |
| `test_rule_engine.py` | Motor de regras RGPD (R01-R12) |
| `test_scraper.py` | Extractor do scraper (HTML → SiteData) |
| `test_fetcher.py` | Fetcher (Playwright) |
| `test_models.py` | Modelos de dados (Pydantic) |
| `test_db_config.py` | Configuração da base de dados |
| `test_db_repository.py` | Repositórios (Websites, ScanRuns, Findings, Companies) |
| `test_cli_db_integration.py` | Integração CLI + base de dados |
| `test_cli_company.py` | Integração CLI + descoberta de empresa |

### Correr os testes localmente

```powershell
# 1. Garantir que o ambiente virtual está ativo
.\testes_env\Scripts\Activate.ps1

# 2. Instalar o pytest (se ainda não estiver)
pip install pytest

# 3. Correr todos os testes
pytest -v
```

### CI/CD automático

Os testes correm automaticamente em cada `push` ou `pull request` para `main`, através do workflow definido em `.github/workflows/ci.yml`. O CI instala o Python 3.11, as dependências, os browsers do Playwright e corre `pytest -v`.

---

## Estrutura do Projeto

```
vigilantia16-06-2026/
├── run_vigilantia_mvp.py       # ponto de entrada interativo (pede URL por input)
├── configurar_db.py            # assistente interativo de configuração do SQL Server
├── view_db.py                  # consultar a BD no terminal (SQL Server)
├── verify_sites.py             # verificação independente de sites (requests + BeautifulSoup)
├── demo_dashboard.py           # demonstração do formato de dados do dashboard
├── report_search.sql           # query SQL para relatório unificado no SSMS
├── requirements.txt            # dependências do projeto
├── pyproject.toml              # configuração do pacote Python (setuptools)
├── .env                        # configuração local (NÃO versionado)
├── .env.example                # exemplo de .env com todas as variáveis e comentários
├── DISCLAIMER.md               # aviso legal sobre as limitações da ferramenta
├── relatorio.html              # último relatório gerado (sobrescrito a cada scan)
├── vigilantia.db               # base de dados SQLite (criada automaticamente)
├── rules/
│   └── gdpr_rules.yaml         # definição das 12 regras RGPD (R01-R12)
├── templates/
│   └── report.html.j2          # template Jinja2 do relatório HTML
├── reports/                    # relatórios gerados (histórico, um por scan)
├── src/vigilantia/
│   ├── cli.py                  # CLI (Typer) + lógica partilhada do scan
│   ├── paths.py                # caminhos absolutos (regras, templates, relatórios)
│   ├── reporter.py             # geração do relatório HTML (Jinja2)
│   ├── scraper/
│   │   ├── main.py             # orquestração do scraper (fetch + extract → SiteData)
│   │   ├── fetcher.py          # fetch do HTML com Playwright (headless browser)
│   │   ├── extractor.py        # extração de dados do HTML
│   │   ├── cookie_tester.py    # classificação de cookies (tracking, funcional, etc.)
│   │   └── company_info.py     # descoberta do site a partir de dados da empresa
│   ├── analyzer/
│   │   ├── rule_engine.py      # motor de regras RGPD (avalia R01-R12)
│   │   └── privacy_text.py     # análise da política de privacidade (multi-página)
│   ├── db/
│   │   ├── config.py           # configuração (DatabaseConfig + DashboardConfig)
│   │   ├── connection.py       # gestão de ligações (SQLite / MSSQL / Dashboard)
│   │   ├── repository.py       # repositórios (CRUD para as 4 tabelas)
│   │   ├── dashboard.py        # envio de incidências para o dashboard (SP)
│   │   └── schema.sql          # schema SQL Server (CREATE TABLE, índices)
│   └── models/
│       ├── site_data.py        # SiteData, Cookie, ThirdPartyScript, Form
│       └── finding.py          # Finding (resultado de uma regra RGPD)
├── tests/                      # testes automáticos (pytest, 9 ficheiros)
│   ├── test_analyzer.py
│   ├── test_rule_engine.py
│   ├── test_scraper.py
│   ├── test_fetcher.py
│   ├── test_models.py
│   ├── test_db_config.py
│   ├── test_db_repository.py
│   ├── test_cli_db_integration.py
│   └── test_cli_company.py
└── .github/workflows/ci.yml    # CI: testes em cada push/PR para main
```

---

## Dependências

O projeto usa `requirements.txt` para instalar as bibliotecas necessárias:

| Pacote | Versão | Para que serve |
|---|---|---|
| `playwright` | 1.61.0 | Scraping real de sites (abre o site num browser headless) |
| `beautifulsoup4` | 4.15.0 | Parsing e extração de dados do HTML |
| `requests` | 2.34.2 | HTTP requests (verificação independente, company_info) |
| `pydantic` | 2.13.4 | Validação de dados e modelos (SiteData, Finding, etc.) |
| `typer` | 0.26.8 | Interface de linha de comandos (CLI) |
| `PyYAML` | 6.0.3 | Leitura das regras RGPD do ficheiro YAML |
| `Jinja2` | 3.1.6 | Templates para gerar os relatórios HTML |
| `langdetect` | 1.0.9 | Deteção de idioma da política de privacidade |
| `pyodbc` | 5.2.0 | Ligação a SQL Server (MSSQL) |
| `python-dotenv` | 1.0.1 | Leitura de variáveis de ambiente do ficheiro `.env` |

Instalar tudo:
```powershell
pip install -r requirements.txt
```

---

## Resolução de Problemas

### "py não é reconhecido como comando"
Usar `python` em vez de `py`:
```powershell
python -m venv testes_env
```

### "Não é possível executar scripts neste sistema" (ExecutionPolicy)
Executar no PowerShell como administrador:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### "playwright: comando não encontrado"
Garantir que o ambiente virtual está ativo e usar:
```powershell
python -m playwright install
```

### "pyodbc: erro de compilação / C++ Build Tools"
O `pyodbc` precisa de compilador C++ no Windows. Duas opções:
1. Instalar os [C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Ou, se **não precisar de SQL Server**, ignorar o erro — a ferramenta funciona perfeitamente só com SQLite

### "[BD] Aviso: não foi possível registar o início do scan"
Isto é normal e não é um erro crítico. Significa que a BD não está acessível (SQL Server em baixo, driver em falta, etc.), mas o scan **continua normalmente** e o relatório é gerado na mesma. Para resolver:
- Se usa SQLite: verificar se `VIGILANTIA_DB_TYPE=sqlite` no `.env`
- Se usa MSSQL: verificar as credenciais e se o SQL Server está a correr
- Se não quer BD: usar `VIGILANTIA_DB_TYPE=none`

### "O relatório não aparece / onde ficou?"
- Último relatório: `relatorio.html` na raiz do projeto
- Histórico: pasta `reports/`
- Abrir com duplo clique — abre no browser

### "Os testes falham com erros de import"
Garantir que o ambiente virtual está ativo e que as dependências estão instaladas:
```powershell
.\testes_env\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pytest
pytest -v
```

---

## Autor

João Rêgo