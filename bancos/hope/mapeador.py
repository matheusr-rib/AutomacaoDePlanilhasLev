# bancos/hope/mapeador.py

from typing import List, Dict, Any, Optional

from core.modelos import CanonicalItem
from core.utils import parse_percentual_br
from padronizacao.servico_padronizacao import ServicoPadronizacao
from padronizacao.parser_portabilidade import montar_complemento


def mapear_banco_para_itens(
    linhas: List[Dict[str, Any]],
    servico_padronizacao: Optional[ServicoPadronizacao] = None,
) -> List[CanonicalItem]:
    """Mapeia linhas do relatório do banco para CanonicalItem.

    Recebe opcionalmente um ServicoPadronizacao (injetado pelo controller),
    para que o cache (derivado do interno) seja usado na mesma execução.
    """
    servico = servico_padronizacao or ServicoPadronizacao()
    itens: List[CanonicalItem] = []

    for row in linhas:
        id_raw = str(row.get("Id do Produto na Origem", "")).strip()
        taxa_raw = str(row.get("Taxa a.m", "")).strip()

        # Prazo único ou faixa (ex.: 120 ou 96-120)
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

        padrao, _confianca = servico.padronizar(entrada_ia)

        produto_nome = padrao.get("produto_padronizado") or entrada_ia["produto_raw"]
        convenio = padrao.get("convenio_padronizado") or entrada_ia["convenio_raw"]
        familia = padrao.get("familia_produto") or ""
        grupo = padrao.get("grupo_convenio") or ""

        # Operação baseada no 'Tipo de Contrato'
        operacao = _mapear_operacao(row.get("Tipo de Contrato", ""))

        nomenclatura_original = row.get("Tabela/Nome do Produto", "")
        complemento = montar_complemento(id_raw, operacao, nomenclatura_original)

        extras = {
            "Família Produto": familia,
            "Grupo Convênio": grupo,
            "Complemento": complemento,
        }

        item = CanonicalItem(
            instituicao=str(row.get("Banco", "")).strip(),
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
    itens: List[CanonicalItem] = []

    for row in linhas:
        if str(row.get("Término", "")).strip():
            continue  # Linha encerrada no interno é ignorada

        item = CanonicalItem(
            instituicao=str(row.get("Instituição", "")),
            convenio=str(row.get("Convênio", "")),
            produto_nome=str(row.get("Produto", "")),
            operacao=str(row.get("Operação", "")),
            parc_atual=str(row.get("Parc. Atual", "")),
            comissao_pct=parse_percentual_br(row.get("% Comissão")),
            id_tabela_banco=str(row.get("Id Tabela Banco", "")),
            id_produto_origem=str(row.get("Id Tabela Banco", "")),
            extras={"linha_original": row},
        )

        itens.append(item)

    return itens


def _mapear_operacao(txt: str) -> str:
    """Mapeamento EXATO baseado nos valores reais enviados pelo banco HOPE na coluna 'Tipo de Contrato'."""
    if not txt:
        return ""

    t = str(txt).strip().upper()

    if t == "CONTRATO NOVO":
        return "NOVO"

    if t == "PORTABILIDADE":
        return "PORTABILIDADE"

    if t == "REFIN-PORTABILIDADE":
        return "PORTAB/REFIN"

    if t in ("CARTÃO C/ SAQUE", "CARTAO C/ SAQUE"):
        return "CARTÃO"

    return t
