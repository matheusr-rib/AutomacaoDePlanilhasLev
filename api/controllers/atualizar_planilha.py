from pathlib import Path
from typing import List, Dict, Any

from core.diff_engine import DiffEngine
from core.modelos import DiffAction, TipoAcao

from bancos.hope.leitor_banco import ler_excel_banco
from bancos.hope.leitor_interno import ler_excel_interno
from bancos.hope.mapeador import (
    mapear_banco_para_itens,
    mapear_interno_para_itens,
)
from bancos.hope.regras import linha_abrir, linha_fechar
from bancos.hope.writer import escrever_planilha_hope

from padronizacao.servico_padronizacao import ServicoPadronizacao
from api.controllers.promover_padroes import promover_padroes


def processar_atualizacao(
    banco: str,
    caminho_banco: Path,
    caminho_interno: Path,
    caminho_saida: Path,
    caminho_validacao: Path | None = None,
) -> None:
    """
    Orquestra a atualização das planilhas.

    Ordem CORRETA:
    0) Aplica CSV de validação humana (se existir)
    1) Atualiza cache com histórico validado (interno)
    2) Processa banco novo
    3) Gera Excel DELTA (abrir / fechar)
    """
    banco = banco.upper().strip()
    if banco != "HOPE":
        raise ValueError(f"Banco não suportado: {banco}")

    # ======================================================
    # 0) APLICAR CSV DE VALIDAÇÃO HUMANA (ANTES DE TUDO)
    # ======================================================
    if caminho_validacao and caminho_validacao.exists():
        print(f"Aplicando validação humana: {caminho_validacao}")
        promover_padroes(caminho_validacao)

    # ======================================================
    # 1) LEITURA DOS ARQUIVOS
    # ======================================================
    linhas_banco: List[Dict[str, Any]] = ler_excel_banco(caminho_banco)
    linhas_interno: List[Dict[str, Any]] = ler_excel_interno(caminho_interno)

    # ======================================================
    # 2) SERVIÇO DE PADRONIZAÇÃO (CACHE + IA)
    # ======================================================
    servico_padronizacao = ServicoPadronizacao()

    cache_inicial = servico_padronizacao.cache.tamanho

    # ======================================================
    # 3) ATUALIZA CACHE COM HISTÓRICO VALIDADO (INTERNO)
    # ======================================================
    novas_chaves_cache = servico_padronizacao.atualizar_cache_com_interno(
        linhas_interno
    )

    # ======================================================
    # 4) MAPEAMENTO CANÔNICO
    # ======================================================
    itens_interno = mapear_interno_para_itens(linhas_interno)
    itens_banco = mapear_banco_para_itens(
        linhas_banco,
        servico_padronizacao=servico_padronizacao,
    )

    # ======================================================
    # 5) DIFF
    # ======================================================
    engine = DiffEngine()
    acoes: List[DiffAction] = engine.diff(itens_interno, itens_banco)

    # ======================================================
    # 6) LINHAS DE SAÍDA (DELTA)
    # ======================================================
    linhas_saida: List[Dict[str, Any]] = []

    for acao in acoes:
        if acao.tipo == TipoAcao.ABRIR and acao.item_banco:
            linhas_saida.append(linha_abrir(acao.item_banco))

        elif acao.tipo == TipoAcao.FECHAR and acao.item_interno:
            linhas_saida.append(linha_fechar(acao.item_interno))

        elif (
            acao.tipo == TipoAcao.FECHAR_ABRIR
            and acao.item_interno
            and acao.item_banco
        ):
            linhas_saida.append(linha_fechar(acao.item_interno))
            linhas_saida.append(linha_abrir(acao.item_banco))

    # ======================================================
    # 7) ESCREVER EXCEL FINAL
    # ======================================================
    escrever_planilha_hope(linhas_saida, caminho_saida)

    # ======================================================
    # 8) RESUMO DA EXECUÇÃO
    # ======================================================
    resumo_execucao = {
        "cache_inicial": cache_inicial,
        "cache_novas": novas_chaves_cache,
        "cache_final": servico_padronizacao.cache.tamanho,
        "consultas_cache": servico_padronizacao.metricas["consultas_cache"],
        "hits_cache": servico_padronizacao.metricas["hits_cache"],
        "chamadas_ia": servico_padronizacao.metricas["chamadas_ia"],
        "linhas_csv": servico_padronizacao.metricas["linhas_csv"],
    }

    print("\n===== RESUMO DA EXECUÇÃO =====")
    for k, v in resumo_execucao.items():
        print(f"{k}: {v}")
    print("================================\n")
