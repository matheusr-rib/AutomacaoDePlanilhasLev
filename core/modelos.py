from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class TipoAcao(str, Enum):
    ABRIR = "ABRIR"
    FECHAR = "FECHAR"
    FECHAR_ABRIR = "FECHAR+ABRIR"


@dataclass
class CanonicalItem:
    """
    Representa uma linha padronizada de produto, independente do banco.
    """
    instituicao: str
    convenio: str
    produto_nome: str
    operacao: str
    parc_atual: str
    comissao_pct: float  # em percentual (ex: 8.5 = 8,5%)
    id_tabela_banco: Optional[str] = None
    id_produto_origem: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiffAction:
    tipo: TipoAcao
    item_interno: Optional[CanonicalItem]
    item_banco: Optional[CanonicalItem]
    motivo: str = ""
