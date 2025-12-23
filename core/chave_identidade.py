from typing import Tuple
from .modelos import CanonicalItem
from core.utils import normalizar_parc_atual

def chave_hope(item: CanonicalItem) -> Tuple:
    parc_norm = normalizar_parc_atual(item.parc_atual)

    if item.id_produto_origem:
        return ("HOPE", "IDORIGEM+PARC", item.id_produto_origem, item.operacao, parc_norm)

    if item.id_tabela_banco:
        return ("HOPE", "IDTAB+PARC", item.id_tabela_banco, item.operacao, parc_norm)

    return (
        "HOPE",
        "FALLBACK",
        item.instituicao,
        item.convenio,
        item.produto_nome,
        item.operacao,
        parc_norm,
    )
