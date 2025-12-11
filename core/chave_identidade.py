from typing import Tuple
from .modelos import CanonicalItem

def chave_hope(item: CanonicalItem) -> Tuple:
    """
    Implementa a lógica de identidade HOPE:

    1) Se tiver id_produto_origem:
       ("HOPE", "IDORIGEM+PARC", id_produto_origem, operacao, parc_atual)
    2) Senão, se tiver id_tabela_banco:
       ("HOPE", "IDTAB+PARC", id_tabela_banco, operacao, parc_atual)
    3) Senão, fallback:
       ("HOPE", "FALLBACK", instituicao, convenio, produto_nome, operacao, parc_atual)
    """
    if item.id_produto_origem:
        return ("HOPE", "IDORIGEM+PARC", item.id_produto_origem, item.operacao, item.parc_atual)

    if item.id_tabela_banco:
        return ("HOPE", "IDTAB+PARC", item.id_tabela_banco, item.operacao, item.parc_atual)

    return (
        "HOPE",
        "FALLBACK",
        item.instituicao,
        item.convenio,
        item.produto_nome,
        item.operacao,
        item.parc_atual,
    )
