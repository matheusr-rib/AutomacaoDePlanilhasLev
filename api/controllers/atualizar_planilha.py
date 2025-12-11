# api/controllers/atualizar_planilha.py

from pathlib import Path
from typing import List, Dict, Any

from core.diff_engine import DiffEngine
from core.modelos import DiffAction, TipoAcao

from bancos.hope.leitor_banco import ler_excel_banco
from bancos.hope.leitor_interno import ler_excel_interno
from bancos.hope.mapeador import mapear_banco_para_itens, mapear_interno_para_itens
from bancos.hope.regras import linha_abrir, linha_fechar
from bancos.hope.writer import escrever_planilha_hope


def processar_atualizacao(
    banco: str,
    caminho_banco: Path,
    caminho_interno: Path,
    caminho_saida: Path,
) -> None:
    """
    Orquestra o processo de atualização para um banco específico.
    Por enquanto, apenas HOPE.
    """
    banco = banco.upper().strip()

    if banco != "HOPE":
        raise ValueError(f"Banco não suportado: {banco}")

    # 1) Ler planilhas
    linhas_banco: List[Dict[str, Any]] = ler_excel_banco(caminho_banco)
    linhas_interno: List[Dict[str, Any]] = ler_excel_interno(caminho_interno)

    # 2) Mapear para CanonicalItem
    itens_banco = mapear_banco_para_itens(linhas_banco)
    itens_interno = mapear_interno_para_itens(linhas_interno)

    # 3) Gerar diferenças
    engine = DiffEngine()
    acoes: List[DiffAction] = engine.diff(itens_interno, itens_banco)

    # 4) Montar linhas finais (ABRIR / FECHAR / FECHAR+ABRIR)
    linhas_saida: List[Dict[str, Any]] = []

    for acao in acoes:
        if acao.tipo == TipoAcao.ABRIR and acao.item_banco:
            linhas_saida.append(linha_abrir(acao.item_banco))

        elif acao.tipo == TipoAcao.FECHAR and acao.item_interno:
            linhas_saida.append(linha_fechar(acao.item_interno))

        elif acao.tipo == TipoAcao.FECHAR_ABRIR and acao.item_interno and acao.item_banco:
            linhas_saida.append(linha_fechar(acao.item_interno))
            linhas_saida.append(linha_abrir(acao.item_banco))

    # 5) Escrever Excel final para HOPE
    escrever_planilha_hope(linhas_saida, caminho_saida)
