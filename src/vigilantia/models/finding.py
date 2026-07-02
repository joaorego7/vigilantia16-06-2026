# src/vigilantia/models/finding.py

from pydantic import BaseModel
from typing import Dict, Any


class Finding(BaseModel):
    """
    Representa uma não-conformidade RGPD encontrada na análise.

    Campos:
      - id: identificador único da regra (ex.: 'R05')
      - severity: gravidade do problema ('high', 'medium', 'low')
      - description: descrição do problema
      - evidence: prova concreta (dados sobre o site/política que suportam o finding)
      - recommendation: sugestão de correção para o site
    """
    id: str
    severity: str
    description: str
    evidence: Dict[str, Any]
    recommendation: str