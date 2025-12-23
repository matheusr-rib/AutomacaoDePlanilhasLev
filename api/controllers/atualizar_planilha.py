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
from core.utils import log_info


def processar_atualizacao(
    banco: str,
    caminho_banco: Path,
    caminho_interno: Path,
    caminho_saida: Path,
    caminho_validacao: Path | None = None,
    caminho_logs: Path | None = None,
    habilitar_logs: bool = False,
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

    log_info("Iniciando atualização de condições")
    log_info(f"Banco selecionado: {banco}")

    # ======================================================
    # 0) APLICAR CSV DE VALIDAÇÃO HUMANA
    # ======================================================
    if caminho_validacao and caminho_validacao.exists():
        log_info(f"Aplicando validação humana: {caminho_validacao}")
        promover_padroes(caminho_validacao)
    else:
        log_info("Nenhuma validação humana a aplicar")

    # ======================================================
    # 1) LEITURA DOS ARQUIVOS
    # ======================================================
    log_info("Lendo planilha do banco...")
    linhas_banco: List[Dict[str, Any]] = ler_excel_banco(caminho_banco)
    log_info(f"→ {len(linhas_banco)} linhas carregadas do banco")

    log_info("Lendo planilha interna...")
    linhas_interno: List[Dict[str, Any]] = ler_excel_interno(caminho_interno)
    log_info(f"→ {len(linhas_interno)} linhas carregadas do sistema interno")

    # ======================================================
    # 2) SERVIÇO DE PADRONIZAÇÃO
    # ======================================================
    log_info("Inicializando serviço de padronização (cache + IA)")
    servico_padronizacao = ServicoPadronizacao(
        caminho_csv_logs=caminho_logs,
        habilitar_logs=habilitar_logs,
    )

    cache_inicial = servico_padronizacao.cache.tamanho
    log_info(f"Cache inicial: {cache_inicial} entradas")

    # ======================================================
    # 3) ATUALIZA CACHE COM HISTÓRICO VALIDADO
    # ======================================================
    log_info("Atualizando cache com histórico do sistema interno...")
    novas_chaves_cache = servico_padronizacao.atualizar_cache_com_interno(
        linhas_interno
    )
    log_info(
        f"→ Cache atualizado | novas chaves: {novas_chaves_cache} | "
        f"total atual: {servico_padronizacao.cache.tamanho}"
    )

    # ======================================================
    # 4) MAPEAMENTO CANÔNICO
    # ======================================================
    log_info("Mapeando itens internos...")
    itens_interno = mapear_interno_para_itens(linhas_interno)

    log_info("Mapeando itens do banco (padronização em andamento)...")
    itens_banco = mapear_banco_para_itens(
        linhas_banco,
        servico_padronizacao=servico_padronizacao,
    )

    # ======================================================
    # 5) DIFF
    # ======================================================
    log_info("Calculando diferenças (diff interno x banco)...")
    engine = DiffEngine()
    acoes: List[DiffAction] = engine.diff(itens_interno, itens_banco)

    qtd_abrir = sum(1 for a in acoes if a.tipo == TipoAcao.ABRIR)
    qtd_fechar = sum(1 for a in acoes if a.tipo == TipoAcao.FECHAR)
    qtd_atualizar = sum(1 for a in acoes if a.tipo == TipoAcao.FECHAR_ABRIR)

    log_info(
        f"→ Diff calculado | Abrir: {qtd_abrir} | "
        f"Fechar: {qtd_fechar} | Atualizar: {qtd_atualizar}"
    )

    # ======================================================
    # 6) LINHAS DE SAÍDA
    # ======================================================
    log_info("Montando linhas de saída (DELTA)...")
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

    log_info(f"→ {len(linhas_saida)} linhas geradas no Excel final")

    # ======================================================
    # 7) ESCREVER EXCEL FINAL
    # ======================================================
    log_info("Gerando planilha final...")
    escrever_planilha_hope(linhas_saida, caminho_saida)
    log_info("Planilha gerada com sucesso ✅")

    # ======================================================
    # 8) LOGS MANUAIS (SE HABILITADOS)
    # ======================================================
    gravadas = servico_padronizacao.flush_logs()
    if gravadas:
        log_info(f"{gravadas} sugestões gravadas no CSV de validação")

    # ======================================================
    # 9) RESUMO FINAL
    # ======================================================
    print("\n===== RESUMO DA EXECUÇÃO =====")
    print(f"cache_inicial: {cache_inicial}")
    print(f"cache_novas: {novas_chaves_cache}")
    print(f"cache_final: {servico_padronizacao.cache.tamanho}")
    print(f"consultas_cache: {servico_padronizacao.metricas['consultas_cache']}")
    print(f"hits_cache: {servico_padronizacao.metricas['hits_cache']}")
    print(f"chamadas_ia: {servico_padronizacao.metricas['chamadas_ia']}")
    print(f"linhas_csv: {servico_padronizacao.metricas['linhas_csv']}")
    print("================================\n")
