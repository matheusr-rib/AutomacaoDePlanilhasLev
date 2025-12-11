# bancos/hope/mapeador.py

from typing import List, Dict, Any
from core.modelos import CanonicalItem
from core.utils import parse_percentual_br
from padronizacao.servico_padronizacao import ServicoPadronizacao
from padronizacao.parser_portabilidade import montar_complemento


servico_padronizacao = ServicoPadronizacao()


def mapear_banco_para_itens(linhas: List[Dict[str, Any]]) -> List[CanonicalItem]:
    itens = []

    for row in linhas:
        id_raw = str(row.get("Id do Produto na Origem", "")).strip()
        taxa_raw = str(row.get("Taxa a.m", "")).strip()

        prazo_ini = str(row.get("Prazo Inicial", "")).strip()
        prazo_fim = str(row.get("Prazo Final", "")).strip()
        prazo_raw = prazo_ini if prazo_ini == prazo_fim else f"{prazo_ini}-{prazo_fim}"

        entrada_ia = {
            "id_raw": id_raw,
            "taxa_raw": taxa_raw,
            "prazo_raw": prazo_raw,
            "produto_raw": row.get("Tabela/Nome do Produto", ""),
            "convenio_raw": row.get("Convênio", ""),
        }

        padrao, confianca = servico_padronizacao.padronizar(entrada_ia)

        produto_nome = padrao.get("produto_padronizado") or entrada_ia["produto_raw"]
        convenio = padrao.get("convenio_padronizado") or entrada_ia["convenio_raw"]
        familia = padrao.get("familia_produto")
        grupo = padrao.get("grupo_convenio")

        operacao = _mapear_operacao(row.get("Tipo de Contrato", ""))

        complemento = montar_complemento(id_raw, operacao, produto_nome)

        extras = {
            "Família Produto": familia or "",
            "Grupo Convênio": grupo or "",
            "Complemento": complemento,
        }

        item = CanonicalItem(
            instituicao=row.get("Banco", "").strip(),
            convenio=convenio,
            produto_nome=produto_nome,
            operacao=operacao,
            parc_atual=prazo_raw,
            comissao_pct=parse_percentual_br(row.get("À Vista Empresa")),
            id_tabela_banco=id_raw,
            id_produto_origem=id_raw,
            extras=extras,
        )

        itens.append(item)

    return itens


def mapear_interno_para_itens(linhas: List[Dict[str, Any]]) -> List[CanonicalItem]:
    itens = []

    for row in linhas:
        if row.get("Término", "").strip():
            continue  # linha encerrada no interno = ignorada

        item = CanonicalItem(
            instituicao=row.get("Instituição", ""),
            convenio=row.get("Convênio", ""),
            produto_nome=row.get("Produto", ""),
            operacao=row.get("Operação", ""),
            parc_atual=row.get("Parc. Atual", ""),
            comissao_pct=parse_percentual_br(row.get("% Comissão")),
            id_tabela_banco=row.get("Id Tabela Banco", ""),
            id_produto_origem=row.get("Id Tabela Banco", ""),
            extras={"linha_original": row},
        )

        itens.append(item)

    return itens


def _mapear_operacao(txt: str) -> str:
    t = (txt or "").upper()
    if "PORT" in t:
        return "PORTABILIDADE"
    if "REFIN" in t and "PORT" in t:
        return "PORTAB/REFIN"
    if "CART" in t:
        return "CARTÃO"
    if "NOVO" in t:
        return "NOVO"
    return t or ""
