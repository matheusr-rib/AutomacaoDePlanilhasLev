from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Set
import re

from .dicionario_cache import DicionarioCache
from .gerenciador_logs import GerenciadorLogs
from .motor_ia import MotorIA

from .extrator_sinais import ExtratorSinaisIA
from .indexador_cache import IndexadorCache
from .montador_padrao import MontadorPadrao
from .validador_saida import ValidadorSaida
from .normalizacao import normalizar_texto, extrair_taxa


# ==============================
# REGEX / HELPERS DE TAXA
# ==============================

# taxa padrão no final
_TAXA_FIM_REGEX = re.compile(r"(\d{1,2}[.,]\d{2})%$")

# taxa específica de REFIN (PRIORIDADE MÁXIMA)
_RE_REFIN_TAXA = re.compile(
    r"REFIN\s*(\d{1,2}[.,]\d{2})\s*%",
    re.IGNORECASE
)


def extrair_taxa_refin(texto: str) -> Optional[float]:
    """
    Regra de domínio:
    - Se existir REFIN, a taxa válida é a do REFIN
    - PORT nunca define taxa final
    """
    if not texto:
        return None
    m = _RE_REFIN_TAXA.search(texto)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None


def extrair_taxa_da_nomenclatura(produto: Any) -> str:
    if produto is None:
        return ""
    s = str(produto).strip().upper()
    m = _TAXA_FIM_REGEX.search(s)
    if not m:
        return ""
    return m.group(1)


def _normalizar_numero_str(v: Any, casas: int = 2) -> str:
    if v is None:
        return ""
    s = str(v).strip()
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


def _normalizar_prazo_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip().upper()
    if not s:
        return ""
    s = s.replace("MESES", "").replace("MES", "").replace("M", "").strip()
    s = re.sub(r"\s+", "", s)
    return s


# ==============================
# SERVIÇO PRINCIPAL
# ==============================

class ServicoPadronizacao:
    """
    Serviço principal de padronização.

    GARANTIAS:
    - Cache só recebe dados do INTERNO
    - IA nunca escreve texto final
    - PORT/COMBO sempre usa taxa do REFIN
    """

    def __init__(
        self,
        caminho_cache: Optional[Path] = None,
        caminho_csv_logs: Optional[Path] = None,
    ):
        self.cache = DicionarioCache(
            caminho_cache or Path("padronizacao") / "dicionario_manual.json"
        )
        self.logger = GerenciadorLogs(caminho_csv_logs)

        self.ia = MotorIA()
        self.extrator = ExtratorSinaisIA(self.ia)
        self.montador = MontadorPadrao()
        self.validador = ValidadorSaida()

        self._indexador: Optional[IndexadorCache] = None

        self._cache_execucao: Dict[str, Dict[str, Any]] = {}
        self._logadas: Set[str] = set()

        self.metricas = {
            "consultas_cache": 0,
            "hits_cache": 0,
            "chamadas_ia": 0,
            "linhas_csv": 0,
            "resolvidos_sem_ia": 0,
            "selecao_guiada": 0,
            "estrutural": 0,
            "port_refin": 0,
        }

    # ==========================================================
    # ATUALIZA CACHE A PARTIR DO INTERNO
    # ==========================================================
    def atualizar_cache_com_interno(self, linhas_interno: list[Dict[str, Any]]) -> int:
        novas = 0

        for row in linhas_interno:
            entrada = {
                "id_raw": row.get("Código do Produto") or row.get("id_raw"),
                "taxa_raw": row.get("Taxa") or row.get("taxa_raw"),
                "prazo_raw": row.get("Prazo") or row.get("prazo_raw"),
                "produto_raw": row.get("Produto Padronizado") or row.get("produto_padronizado"),
                "convenio_raw": row.get("Convênio Padronizado") or row.get("convenio_padronizado"),
                "familia_produto": row.get("Família Produto") or row.get("familia_produto"),
                "grupo_convenio": row.get("Grupo Convênio") or row.get("grupo_convenio"),
            }

            chave = self._gerar_chave_manual(entrada)
            if not chave:
                continue

            padrao = {
                "produto_padronizado": entrada.get("produto_raw"),
                "convenio_padronizado": entrada.get("convenio_raw"),
                "familia_produto": entrada.get("familia_produto"),
                "grupo_convenio": entrada.get("grupo_convenio"),
            }

            if any(v for v in padrao.values()):
                if self.cache.get(chave) is None:
                    self.cache.set(chave, padrao)
                    novas += 1

        if novas:
            self.cache.salvar()
            self._indexador = None

        return novas

    # ==========================================================
    # PADRONIZAÇÃO PRINCIPAL
    # ==========================================================
    def padronizar(self, entrada: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        chave = self._gerar_chave_manual(entrada)
        self.metricas["consultas_cache"] += 1

        if chave and chave in self._cache_execucao:
            self.metricas["hits_cache"] += 1
            return self._cache_execucao[chave], 0.99

        if chave:
            achado = self.cache.get(chave)
            if achado is not None:
                self.metricas["hits_cache"] += 1
                self._cache_execucao[chave] = achado
                return achado, 1.0

        indexador = self._obter_indexador()
        texto_raw = f"{entrada.get('produto_raw', '')} {entrada.get('convenio_raw', '')}".strip()

        # ==============================
        # EXTRAÇÃO DE TAXA (COM REGRA REFIN)
        # ==============================

        taxa = self._extrair_taxa_float(entrada, texto_raw)

        # ==============================
        # IA EXTRAI SINAIS
        # ==============================
        self.metricas["chamadas_ia"] += 1
        sinais = self.extrator.extrair(entrada)
        self.metricas["estrutural"] += 1

        assinatura_alvo = self._assinatura_alvo(sinais)

        convenio_oficial = indexador.convenio_por_assinatura(assinatura_alvo)
        confianca = sinais.confianca

        if convenio_oficial:
            self.metricas["resolvidos_sem_ia"] += 1
            saida = self.montador.montar(
                sinais=sinais,
                taxa=taxa,
                indexador=indexador,
                convenio_oficial=convenio_oficial,
                texto_raw=texto_raw,
            )
            saida = self.validador.validar(saida, sinais, indexador, texto_raw)
            self._cache_execucao[chave] = saida
            return saida, max(confianca, 0.85)

        candidatos = indexador.match_convenio(sinais, assinatura_alvo, max_candidatos=10, limiar=0.45)

        if candidatos and candidatos[0].score >= 0.85 and (len(candidatos) == 1 or candidatos[1].score < 0.80):
            convenio_oficial = candidatos[0].convenio_oficial
            self.metricas["resolvidos_sem_ia"] += 1

            saida = self.montador.montar(
                sinais=sinais,
                taxa=taxa,
                indexador=indexador,
                convenio_oficial=convenio_oficial,
                texto_raw=texto_raw,
            )
            saida = self.validador.validar(saida, sinais, indexador, texto_raw)
            self._cache_execucao[chave] = saida
            return saida, max(confianca, 0.80)

        if candidatos:
            opcoes = [c.convenio_oficial for c in candidatos]
            self.metricas["chamadas_ia"] += 1
            self.metricas["selecao_guiada"] += 1

            resp, conf_sel = self.ia.sugerir_selecao_guiada(
                entrada=entrada,
                opcoes_convenio=opcoes,
                contexto={
                    "assinatura_alvo": assinatura_alvo,
                    "tipo": sinais.tipo,
                    "nome_base": sinais.nome_base,
                    "uf": sinais.uf,
                },
            )

            escolhido = (resp.get("opcao_escolhida") or "").strip()
            if escolhido and escolhido in opcoes:
                convenio_oficial = escolhido

                sub_ia = resp.get("subproduto")
                if sub_ia:
                    sub_norm = normalizar_texto(sub_ia)
                    if sub_norm and sub_norm in normalizar_texto(texto_raw):
                        sinais = sinais.__class__(
                            tipo=sinais.tipo,
                            nome_base=sinais.nome_base,
                            uf=sinais.uf,
                            subproduto=sub_norm,
                            confianca=max(sinais.confianca, conf_sel),
                        )

                saida = self.montador.montar(
                    sinais=sinais,
                    taxa=taxa,
                    indexador=indexador,
                    convenio_oficial=convenio_oficial,
                    texto_raw=texto_raw,
                )
                saida = self.validador.validar(saida, sinais, indexador, texto_raw)
                self._cache_execucao[chave] = saida

                self._logar_sugestao(chave, entrada, saida, conf_sel)
                return saida, conf_sel

        saida = self.montador.montar(
            sinais=sinais,
            taxa=taxa,
            indexador=indexador,
            convenio_oficial=None,
            texto_raw=texto_raw,
        )
        saida = self.validador.validar(saida, sinais, indexador, texto_raw)
        self._cache_execucao[chave] = saida

        self._logar_sugestao(chave, entrada, saida, confianca)
        return saida, confianca

    # ==========================================================
    # HELPERS
    # ==========================================================
    def _gerar_chave_manual(self, entrada: Dict[str, Any]) -> str:
        id_raw = (entrada.get("id_raw") or "").strip().upper()
        if not id_raw:
            return ""

        taxa_raw = _normalizar_numero_str(entrada.get("taxa_raw"), casas=2).upper()
        prazo_raw = _normalizar_prazo_str(entrada.get("prazo_raw"))
        return f"{id_raw}|{taxa_raw}|{prazo_raw}"

    def _obter_indexador(self) -> IndexadorCache:
        if self._indexador is None:
            self._indexador = IndexadorCache.construir(self.cache)
        return self._indexador

    def _extrair_taxa_float(self, entrada: Dict[str, Any], texto_raw: str) -> float:
        """
        REGRA DE DOMÍNIO (ORDEM DE PRIORIDADE):
        1) taxa do REFIN (se existir)
        2) taxa_raw explícita
        3) última taxa genérica do texto
        """

        # 1) PORT / COMBO / REFIN
        taxa_refin = extrair_taxa_refin(texto_raw)
        if taxa_refin is not None:
            self.metricas["port_refin"] += 1
            return taxa_refin

        # 2) taxa_raw
        tr = entrada.get("taxa_raw")
        try:
            if isinstance(tr, (int, float)):
                return float(tr)
            if isinstance(tr, str) and tr.strip():
                s = tr.replace("%", "").strip().replace(",", ".")
                return float(s)
        except Exception:
            pass

        # 3) fallback genérico
        t = extrair_taxa(texto_raw)
        if t is not None:
            return float(t)

        return 0.0

    def _assinatura_alvo(self, sinais) -> str:
        tipo = sinais.tipo
        base = normalizar_texto(sinais.nome_base)
        uf = sinais.uf

        if tipo == "GOV" and uf:
            return f"GOV {uf}"

        if tipo == "TJ" and uf:
            return f"TJ {uf}"

        if tipo == "SIAPE":
            return "SIAPE"

        if tipo == "PREF":
            cidade = base.replace("PREF", "").strip()
            if uf:
                return f"PREF {cidade} {uf}"
            return f"PREF {cidade}"

        if uf:
            return f"{base} {uf}"
        return base

    def _logar_sugestao(self, chave: str, entrada: Dict[str, Any], saida: Dict[str, Any], confianca: float) -> None:
        if not chave or chave in self._logadas:
            return
        try:
            self.logger.registrar_sugestao(chave, entrada, saida, confianca)
            self.metricas["linhas_csv"] += 1
            self._logadas.add(chave)
        except Exception:
            pass
