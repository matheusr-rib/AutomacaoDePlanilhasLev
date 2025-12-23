from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Set
import re

from .motor_ia import MotorIA
from .gerenciador_logs import GerenciadorLogs
from .dicionario_cache import DicionarioCache


# taxa SEMPRE no final, ex: "2,19%"
_TAXA_FIM_REGEX = re.compile(r"(\d{1,2}[.,]\d{2})%$")


def extrair_taxa_da_nomenclatura(produto: Any) -> str:
    """
    Extrai a taxa do final da nomenclatura do produto.
    Ex:
      'GOV. RO - 1,76%' -> '1,76%'
    """
    if produto is None:
        return ""
    s = str(produto).strip()
    if not s:
        return ""

    m = _TAXA_FIM_REGEX.search(s)
    if not m:
        return ""

    return f"{m.group(1)}%"


def _normalizar_numero_str(valor: Any, casas: int = 2) -> str:
    if valor is None:
        return ""
    s = str(valor).strip()
    if not s:
        return ""

    s = s.replace("%", "").strip()

    try:
        if "," in s and "." in s:
            s_num = s.replace(".", "").replace(",", ".")
        else:
            s_num = s.replace(",", ".")
        f = float(s_num)
        return f"{f:.{casas}f}"
    except Exception:
        return s.replace(" ", "").upper()


def _normalizar_prazo_str(valor) -> str:
    """
    Normaliza prazo para chave canônica.

    Regras:
    - "96" -> "96"
    - "96-96" -> "96"
    - "96 A 96" -> "96"
    - "96/96" -> "96"
    - "96-120" -> "96-120"
    - None / vazio -> ""
    """
    if valor is None:
        return ""

    s = str(valor).strip().upper()
    if not s:
        return ""

    # extrai todos os números
    nums = re.findall(r"\d+", s)

    if not nums:
        return ""

    if len(nums) == 1:
        return nums[0]

    inicio, fim = nums[0], nums[1]

    # 🔥 REGRA-CHAVE DO SEU BUG
    if inicio == fim:
        return inicio

    return f"{inicio}-{fim}"


class ServicoPadronizacao:
    """
    Serviço de padronização com CACHE REAL.

    Ordem:
    1) cache em memória (execução)
    2) cache persistido (JSON)
    3) IA (fallback)
    """

    def __init__(
        self,
        caminho_cache: Optional[Path] = None,
        caminho_csv_logs: Optional[Path] = None,
        habilitar_logs: bool = False,
    ):
        self.cache = DicionarioCache(
            caminho_cache or Path("padronizacao") / "dicionario_manual.json"
        )
        self.ia = MotorIA()
        self.logger = GerenciadorLogs(caminho_csv_logs)

        self._cache_execucao: Dict[str, Dict[str, Any]] = {}
        self._logadas: Set[str] = set()

        # MÉTRICAS DA EXECUÇÃO
        self.metricas = {
            "consultas_cache": 0,
            "hits_cache": 0,
            "chamadas_ia": 0,
            "linhas_csv": 0,
        }

    # ==========================================================
    # CACHE AUTOMÁTICO A PARTIR DO INTERNO
    # ==========================================================
    def atualizar_cache_com_interno(self, linhas_interno: list[Dict[str, Any]]) -> int:
        """
        Alimenta o cache automaticamente usando a planilha interna (histórico validado).

        - NÃO sobrescreve chaves existentes
        - Usa a TAXA extraída da nomenclatura do Produto
        """
        novas = 0

        for row in linhas_interno:
            if str(row.get("Término", "")).strip():
                continue

            produto = str(row.get("Produto", "")).strip()
            taxa_raw = extrair_taxa_da_nomenclatura(produto)

            entrada = {
                "id_raw": str(row.get("Id Tabela Banco", "")).strip(),
                "taxa_raw": taxa_raw,
                "prazo_raw": str(row.get("Parc. Atual", "")).strip(),
            }

            chave = self._gerar_chave_manual(entrada)
            if not chave or chave in self.cache:
                continue

            padrao = {
                "produto_padronizado": produto,
                "convenio_padronizado": str(row.get("Convênio", "")).strip(),
                "familia_produto": str(row.get("Família Produto", "")).strip(),
                "grupo_convenio": str(row.get("Grupo Convênio", "")).strip(),
            }

            if any(v for v in padrao.values()):
                self.cache.set(chave, padrao)
                novas += 1

        if novas:
            self.cache.salvar()

        return novas

    # ==========================================================
    # PADRONIZAÇÃO (CACHE -> IA)
    # ==========================================================
    def padronizar(self, entrada: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        chave = self._gerar_chave_manual(entrada)

        self.metricas["consultas_cache"] += 1

        # cache da execução
        if chave in self._cache_execucao:
            self.metricas["hits_cache"] += 1
            return self._cache_execucao[chave], 0.99

        # cache persistido
        achado = self.cache.get(chave)
        if achado is not None:
            self.metricas["hits_cache"] += 1
            return achado, 1.0

        # IA (fallback)
        self.metricas["chamadas_ia"] += 1
        sugestao, confianca = self.ia.sugerir_padrao(entrada)

        self._cache_execucao[chave] = sugestao

        if chave and chave not in self._logadas:
            self.logger.registrar_sugestao(chave, entrada, sugestao, confianca)
            self.metricas["linhas_csv"] += 1
            self._logadas.add(chave)

        return sugestao, confianca

    # ==========================================================
    # CHAVE DO CACHE
    # ==========================================================
    def _gerar_chave_manual(self, entrada: Dict[str, Any]) -> str:
        id_raw = (entrada.get("id_raw") or "").strip().upper()
        if not id_raw:
            return ""

        taxa_raw = _normalizar_numero_str(entrada.get("taxa_raw"), casas=2).upper()
        prazo_raw = _normalizar_prazo_str(entrada.get("prazo_raw"))

        return f"{id_raw}|{taxa_raw}|{prazo_raw}"


    def flush_logs(self) -> int:
        """
        Se logs estiverem habilitados, grava o buffer no CSV 1x no final.
        Se logs estiverem desligados, retorna 0.
        """
        if hasattr(self, "logger") and self.logger:
            # GerenciadorLogs precisa ter .flush()
            if hasattr(self.logger, "flush"):
                return self.logger.flush()
        return 0
