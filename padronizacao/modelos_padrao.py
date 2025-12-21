from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal


# ==============================
# TIPOS INSTITUCIONAIS PERMITIDOS
# ==============================

TipoInstitucional = Literal[
    "GOV",
    "PREF",
    "TJ",
    "SIAPE",
    "OUTROS",
]


# ==============================
# MODELO DE SINAIS EXTRAÍDOS
# ==============================

@dataclass(frozen=True)
class SinaisExtraidos:
    """
    Representa APENAS sinais estruturais extraídos do texto bruto.

    ⚠️ REGRAS IMPORTANTES:
    - NÃO contém texto final padronizado
    - NÃO contém taxa formatada
    - NÃO contém família ou grupo final
    - NÃO pode ser alterado após criado (frozen)

    Esse objeto é o ÚNICO retorno permitido da IA.
    """

    # Tipo institucional detectado
    tipo: TipoInstitucional

    # Nome base LIMPO (sem taxa, sem %)
    # Ex:
    #   "GOV SP"
    #   "PREF SETE LAGOAS"
    #   "HSPM"
    nome_base: str

    # UF explícita, se existir no texto
    # Ex: "SP", "MG"
    uf: Optional[str]

    # Subproduto explícito, se existir
    # Ex:
    #   "SPPREV"
    #   "EMBASA"
    #   None se não houver
    subproduto: Optional[str]

    # Confiança da extração (0.0 a 1.0)
    confianca: float

    def tem_subproduto(self) -> bool:
        """Indica se há subproduto explícito."""
        return bool(self.subproduto)

    def tem_uf(self) -> bool:
        """Indica se UF foi explicitamente detectada."""
        return bool(self.uf)

    def eh_confiavel(self, limiar: float) -> bool:
        """Indica se a confiança atende ao mínimo exigido."""
        return self.confianca >= limiar
