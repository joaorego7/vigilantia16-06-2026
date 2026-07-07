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

## Execução

```powershell
python .\run_vigilantia_mvp.py
```

Depois de executar, introduza o URL do site a analisar quando o programa pedir.

Exemplo:
```text
https://example.com
```

## Dependências

O projeto usa um ficheiro `requirements.txt` para instalar as bibliotecas necessárias com `pip install -r requirements.txt`, o que permite recriar o ambiente noutro computador. [web:75][web:87]

## Notas

- O projeto utiliza Playwright, por isso pode ser necessário correr `playwright install` após instalar as dependências, para descarregar os browsers suportados. [web:135][web:164]
- Recomenda-se a utilização de um ambiente virtual para isolar as dependências do projeto. [web:75][web:165]

## Estrutura esperada

- `run_vigilantia_mvp.py` — script principal
- `requirements.txt` — dependências do projeto
- `.gitignore` — ficheiros e pastas ignorados pelo Git

## Autor

João Rêgo