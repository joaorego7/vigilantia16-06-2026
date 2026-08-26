# Vigilantia

Vigilantia é um projeto em Python para análise de websites, com foco em aspetos de conformidade, conteúdo e automatização de recolha de informação.

## Requisitos

- Python 3.12 recomendado
- PowerShell no Windows
- Ligação à internet para instalação das dependências e dos browsers do Playwright

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

### Configuração da Base de Dados (Recomendado)

Antes de correr a ferramenta, pode configurar a ligação à base de dados SQL Server de forma interativa e sem alterar diretamente os ficheiros de código. O script `configurar_db.py` deteta os drivers ODBC disponíveis no seu sistema, solicita as credenciais, testa a ligação e permite criar a base de dados e as tabelas (a partir do ficheiro `schema.sql`) de forma automatizada.

Para iniciar a configuração, execute:
```powershell
python .\configurar_db.py
```
Este comando criará ou atualizará o ficheiro `.env` na raiz do projeto com os parâmetros escolhidos.

As tabelas são `Websites`, `ScanRuns`, `Findings` e `Companies` (esta última só é preenchida
quando o scan é iniciado pelos dados de uma empresa — ver "Modo por dados da empresa").
Em SQLite (o modo por omissão, `VIGILANTIA_DB_TYPE=sqlite`) as tabelas são criadas
automaticamente na primeira ligação, incluindo em bases de dados criadas antes de a tabela
`Companies` existir.

### Consultar Dados no SSMS (SQL Server Management Studio)

Para além de usar o comando `python .\view_db.py` para visualizar os dados unificados no terminal, pode utilizar o script SQL pré-configurado **[`report_search.sql`](file:///c:/Users/Joao%20Rego/Desktop/vigilantia16-06-2026-original/report_search.sql)**.

Basta abrir este ficheiro no SSMS, certificar-se de que o comando `USE` aponta para a base de dados correta que configurou no assistente (ex: `clientes_websites`), e executar o script (pressionando **F5**) para obter um relatório completo e unificado de todos os scans e findings correlacionados numa única tabela.

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

## Relatórios gerados

Cada análise gera um relatório HTML guardado em `reports/`, com nome baseado no domínio e no
momento da análise (ex.: `reports/vigilantia_example_com_20260709-101500.html`), o que permite
manter um histórico de scans ao longo do tempo. É também sempre atualizada uma cópia com o
resultado mais recente em `relatorio.html`, na raiz do projeto.

## Testes

O projeto tem uma suite de testes automáticos (`pytest`), que cobre o motor de regras, o
extractor do scraper e o analisador de texto da política de privacidade:

```powershell
pip install pytest
pytest -v
```

Os testes correm também automaticamente em cada `push`/`pull request` para `main`, através do
workflow definido em `.github/workflows/ci.yml`.

## Dependências

O projeto usa um ficheiro `requirements.txt` para instalar as bibliotecas necessárias com `pip install -r requirements.txt`, o que permite recriar o ambiente noutro computador. [web:75][web:87]

## Notas

- O projeto utiliza Playwright, por isso pode ser necessário correr `playwright install` após instalar as dependências, para descarregar os browsers suportados. [web:135][web:164]
- Recomenda-se a utilização de um ambiente virtual para isolar as dependências do projeto. [web:75][web:165]

## Estrutura do projeto

```
vigilantia16-06-2026/
├── run_vigilantia_mvp.py      # ponto de entrada interativo (pede URL por input)
├── view_db.py                 # script para consultar a base de dados (websites e findings)
├── requirements.txt           # dependências do projeto
├── DISCLAIMER.md               # aviso legal sobre as limitações da ferramenta
├── rules/
│   └── gdpr_rules.yaml         # definição das regras RGPD (R01-R11)
├── templates/
│   └── report.html.j2          # template do relatório HTML
├── reports/                    # relatórios gerados por cada scan (histórico)
├── src/vigilantia/
│   ├── cli.py                   # ponto de entrada por linha de comandos + lógica partilhada
│   ├── paths.py                 # caminhos absolutos do projeto (regras, templates, relatórios)
│   ├── reporter.py              # geração do relatório HTML
│   ├── scraper/                 # fetch (Playwright), extração de dados do HTML, teste de cookies,
│   │                            # e descoberta do site a partir dos dados da empresa (company_info.py)
│   ├── analyzer/                # motor de regras e análise de texto da política de privacidade
│   ├── db/                      # acesso a dados (Websites, ScanRuns, Findings, Companies)
│   └── models/                  # modelos de dados (Pydantic)
├── tests/                      # suite de testes automáticos (pytest)
└── .github/workflows/ci.yml    # CI: corre os testes em cada push/PR
```

## Autor

João Rêgo