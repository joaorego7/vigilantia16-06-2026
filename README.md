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
│   ├── scraper/                 # fetch (Playwright), extração de dados do HTML, teste de cookies
│   ├── analyzer/                # motor de regras e análise de texto da política de privacidade
│   └── models/                  # modelos de dados (Pydantic)
├── tests/                      # suite de testes automáticos (pytest)
└── .github/workflows/ci.yml    # CI: corre os testes em cada push/PR
```

## Autor

João Rêgo