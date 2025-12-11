# bancos/hope/regras.py

from datetime import date, timedelta
from typing import Dict, Any, List

from core.modelos import CanonicalItem
from bancos.hope.colunas_extras import COLUNAS_EXTRAS_HOPE


COLUNAS_COMUNS = [
    "ID",
    "Instituição",
    "Produto",
    "Família Produto",
    "Grupo Convênio",
    "Convênio",
    "Operação",
    "Parc. Atual",
    "Parc. Refin.",
    "% PMT Pagas",
    "% Taxa",
    "Idade",
    "% Comissão",
    "-",
    "Base Comissão",
    "% Mínima",
    "% Intermediária",
    "% Máxima",
    "% Fator",
    "% TAC",
    "Val. Teto TAC",
    "Faixa Val. Contrato",
    "Faixa Val. Seguro",
    "Vigência",
    "Término",
    "Complemento",
    "Venda Digital",
    "Visualização Restrita",
    "Val. Base Produção",
    "Id Tabela Banco",
]

COLUNAS_HOPE_SAIDA = COLUNAS_COMUNS + COLUNAS_EXTRAS_HOPE


def linha_fechar(item: CanonicalItem) -> Dict[str, Any]:
    """
    FECHAR → copiar linha original 100% igual e adicionar Término = ontem.
    """
    ontem = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")

    base = {col: "" for col in COLUNAS_HOPE_SAIDA}

    linha_original = item.extras.get("linha_original", {})

    for col in COLUNAS_HOPE_SAIDA:
        if col in linha_original:
            base[col] = linha_original[col]

    base["Término"] = ontem

    return base


def linha_abrir(item: CanonicalItem) -> Dict[str, Any]:
    """
    ABRIR → cria linha nova seguindo padrões HOPE.
    """
    hoje = date.today().strftime("%d/%m/%Y")

    base = {col: "" for col in COLUNAS_HOPE_SAIDA}

    # Campos principais
    base["Instituição"] = item.instituicao
    base["Produto"] = item.produto_nome
    base["Convênio"] = item.convenio
    base["Operação"] = item.operacao
    base["Parc. Atual"] = item.parc_atual
    base["% Comissão"] = f"{item.comissao_pct:.2f}".replace(".", ",")
    base["Id Tabela Banco"] = item.id_tabela_banco or ""
    base["Complemento"] = item.extras.get("Complemento", "")
    base["Família Produto"] = item.extras.get("Família Produto", "")
    base["Grupo Convênio"] = item.extras.get("Grupo Convênio", "")

    # Defaults HOPE
    base["Parc. Refin."] = "0"
    base["% PMT Pagas"] = "0"
    base["% Taxa"] = "0"
    base["Idade"] = "0-80"
    base["-"] = "%"

    # Base Comissão: regra PORTABILIDADE
    if item.operacao.upper() == "PORTABILIDADE":
        base["Base Comissão"] = "BRUTO"
    else:
        base["Base Comissão"] = "LÍQUIDO"

    base["% Mínima"] = ""
    base["% Intermediária"] = ""
    base["% Máxima"] = ""
    base["% Fator"] = "0"
    base["% TAC"] = "0"
    base["Val. Teto TAC"] = "0"
    base["Faixa Val. Contrato"] = "0,00-100.000,00-LÍQUIDO"
    base["Faixa Val. Seguro"] = "0"
    base["Vigência"] = hoje
    base["Término"] = ""

    base["Venda Digital"] = "SIM"
    base["Visualização Restrita"] = "NÃO"
    base["Val. Base Produção"] = ""

    # Colunas extras HOPE
    for col in COLUNAS_EXTRAS_HOPE:
        base[col] = ""

    return base
