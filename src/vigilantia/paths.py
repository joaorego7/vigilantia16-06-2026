# src/vigilantia/paths.py

from pathlib import Path

# Comentário geral:
# Este módulo centraliza os caminhos importantes do projeto (regras,
# templates, relatórios) como caminhos ABSOLUTOS, calculados a partir da
# localização deste ficheiro. Isto corrige o bug em que o comando falhava
# se não fosse executado a partir da raiz do repositório (ex.: "rules/gdpr_rules.yaml"
# ou FileSystemLoader("templates") não eram encontrados a partir de outra pasta).

# src/vigilantia/paths.py -> parents[0]=vigilantia, [1]=src, [2]=raiz do projeto
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

RULES_FILE: Path = PROJECT_ROOT / "rules" / "gdpr_rules.yaml"
TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
