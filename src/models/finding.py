# src/models/finding.py

from pydantic import BaseModel
from typing import Any, Dict

# Comentário de cabeçalho:
# Esta classe representa uma não-conformidade encontrada na análise RGPD,
# incluindo a gravidade, descrição, evidências e recomendação.
class Finding(BaseModel):
    id: str                 # identificador único da regra (ex: "R01")
    severity: str           # nível de gravidade (ex: "high", "medium", "low")
    description: str        # descrição legível do problema
    evidence: Dict[str, Any]  # dados concretos que justificam o finding
    recommendation: str     # sugestão de correção para o problema