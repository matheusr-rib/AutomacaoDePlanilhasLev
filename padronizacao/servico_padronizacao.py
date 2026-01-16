from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Set, List
import re
from .catalogos_inst_prev import cidade_por_inst_prev, uf_por_cidade_fallback
from .motor_ia import MotorIA
from .gerenciador_logs import GerenciadorLogs
from .dicionario_cache import DicionarioCache
from .utils_padronizacao import (
    ascii_upper,
    format_taxa_br,
    extrair_taxa_fim,
    extrair_taxa_refin,
    tem_beneficio,
    ESTADO_PARA_UF,
    extrair_gov_uf,
    extrair_derivado_gov_combo,
    extrair_pref_cidade_explicita,
    extrair_cidade_pura,
    extrair_sigla_e_cidade,
    extrair_inst_prev_sub,
    extrair_inst_prev_gen,
    extrair_tj_uf,
    extrair_tj_estado,
    tem_seguro
)
from .indice_cache import IndiceCache
from .catalogos_inst_prev import cidade_por_inst_prev, uf_por_cidade_fallback


# ==========================================================
# NORMALIZAÇÕES BÁSICAS (CHAVE)
# ==========================================================

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
    """
    if valor is None:
        return ""

    s = str(valor).strip().upper()
    if not s:
        return ""

    nums = re.findall(r"\d+", s)
    if not nums:
        return ""

    if len(nums) == 1:
        return nums[0]

    ini, fim = nums[0], nums[1]
    if ini == fim:
        return ini

    return f"{ini}-{fim}"


# ==========================================================
# SANITIZAÇÃO FINAL (OBRIGATÓRIA)
# ==========================================================

# palavras proibidas no PRODUTO (nunca podem aparecer no produto_padronizado)
_PALAVRAS_PROIBIDAS_PRODUTO: List[str] = [
    "EMPRESTIMO", "EMPRÉSTIMO",
    "CARTAO", "CARTÃO",
    "REFIN",
    "PORT", "PORTAB", "PORTABILIDADE",
    "COMBO",
    "CONSIGNADO",
    "BRUTO",
    "LIQUIDO", "LÍQUIDO",
]

# regex pra remover tokens proibidos como palavras inteiras
_RE_PROIBIDAS = re.compile(
    r"\b(" + "|".join(
        sorted({ascii_upper(p) for p in _PALAVRAS_PROIBIDAS_PRODUTO}, key=len, reverse=True)
    ) + r")\b"
)

def _convenio_tem_uf(convenio: str) -> bool:
    """
    Retorna True se o convênio contém UF válida no final.
    Exemplos válidos:
      - PREF. SAO PAULO SP
      - GOV-SP
      - TJ | MG
    """
    if not convenio:
        return False

    t = ascii_upper(convenio)

    return bool(
        re.search(r"\b[A-Z]{2}$", t) or          # PREF. X XX
        re.search(r"\bGOV-[A-Z]{2}$", t) or      # GOV-SP
        re.search(r"\|\s*[A-Z]{2}$", t)          # TJ | SP
    )

def _limpar_produto_final(produto: str) -> str:
    """
    Garante que produto_padronizado:
    - esteja ASCII/UPPER (ascii_upper)
    - NÃO contenha palavras proibidas
    - não fique com hífens quebrados tipo 'GOV. AC - - 1,90%'
    """
    t = ascii_upper(produto)

    # remove palavras proibidas como tokens
    t = _RE_PROIBIDAS.sub("", t)

    # limpa traços duplicados / espaços
    t = re.sub(r"\s*-\s*-\s*", " - ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()

    # se terminar com "-" por remoção de token, remove
    t = re.sub(r"\s*-\s*$", "", t).strip()

    # se ficar vazio, devolve vazio (o caller decide fallback)
    return t


def _garantir_familia_grupo(padrao: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nunca deixa familia/grupo vazios.
    Se não tiver certeza, MANUAL/MANUAL.
    """
    fam = (padrao.get("familia_produto") or "").strip()
    grp = (padrao.get("grupo_convenio") or "").strip()

    if not fam or not grp:
        padrao["familia_produto"] = "MANUAL"
        padrao["grupo_convenio"] = "MANUAL"
        if "convenio_padronizado" not in padrao or padrao.get("convenio_padronizado") is None:
            padrao["convenio_padronizado"] = ""
    return padrao


def _extrair_uf_por_estado_no_texto(texto_ascii: str) -> Optional[str]:
    """
    Ajuda em casos tipo "GOIAS" / "MINAS GERAIS" etc.
    Retorna UF se encontrar o nome do estado.
    """
    t = ascii_upper(texto_ascii)
    for estado, uf in ESTADO_PARA_UF.items():
        if estado in t:
            return uf
    return None


def _extrair_uf_solto(texto_ascii: str) -> Optional[str]:
    """
    Pega UF solto (2 letras) quando aparece como token.
    Útil em coisas tipo '... - SP - ...'
    """
    t = ascii_upper(texto_ascii)
    m = re.search(r"\b([A-Z]{2})\b", t)
    if not m:
        return None
    uf = m.group(1)
    if uf in {
        "TJ", "GO", "SP", "RJ", "MG", "ES", "BA", "PR", "SC", "RS", "DF", "MT", "MS",
        "AM", "AC", "AL", "AP", "CE", "MA", "PA", "PB", "PE", "PI", "RN", "RO", "RR",
        "SE", "TO"
    }:
        return uf
    return None


# ==========================================================
# SERVIÇO DE PADRONIZAÇÃO
# ==========================================================

class ServicoPadronizacao:
    """
    Ordem:
    1) cache em memória (execução)
    2) cache persistido (JSON)
    3) regras determinísticas
    4) IA (fallback)
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
        self.logger = GerenciadorLogs(caminho_csv_logs, habilitado=habilitar_logs)

        self._cache_execucao: Dict[str, Dict[str, Any]] = {}
        self._logadas: Set[str] = set()

        self.metricas = {
            "consultas_cache": 0,
            "hits_cache": 0,
            "chamadas_ia": 0,
            "linhas_csv": 0,
        }

        self.indice = IndiceCache()
        self._rebuild_indice()

    # ======================================================
    # ÍNDICE DERIVADO DO CACHE
    # ======================================================
    def _rebuild_indice(self):
        try:
            items = self.cache.items()
        except Exception:
            data = getattr(self.cache, "_data", {})
            items = data.items()
        self.indice.alimentar(items)

    # ======================================================
    # CACHE AUTOMÁTICO A PARTIR DO INTERNO
    # ======================================================
    def atualizar_cache_com_interno(self, linhas_interno: list[Dict[str, Any]]) -> int:
        novas = 0

        for row in linhas_interno:
            if str(row.get("Término", "")).strip():
                continue

            produto = str(row.get("Produto", "")).strip()
            taxa_raw = extrair_taxa_fim(produto)

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
            self._rebuild_indice()

        return novas

    # ======================================================
    # PADRONIZAÇÃO PRINCIPAL
    # ======================================================
    def padronizar(self, entrada: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        chave = self._gerar_chave_manual(entrada)
        self.metricas["consultas_cache"] += 1

        # =========================
        # 1) CACHE DE EXECUÇÃO
        # =========================
        if chave in self._cache_execucao:
            self.metricas["hits_cache"] += 1
            achado = dict(self._cache_execucao[chave])
            achado.setdefault("__ORIGEM_PADRONIZACAO", "CACHE")
            return achado, 0.99

        # =========================
        # 2) CACHE PERSISTIDO (JSON)
        # =========================
        achado = self.cache.get(chave)
        if achado is not None:
            self.metricas["hits_cache"] += 1
            achado = dict(achado)

            if achado.get("produto_padronizado"):
                achado["produto_padronizado"] = _limpar_produto_final(
                    achado["produto_padronizado"]
                )

            achado = _garantir_familia_grupo(achado)
            achado["__ORIGEM_PADRONIZACAO"] = "CACHE"

            if not _convenio_tem_uf(achado.get("convenio_padronizado", "")):
                achado["__ORIGEM_PADRONIZACAO"] = "MANUAL"

            self._cache_execucao[chave] = achado
            return achado, 1.0

        # =========================
        # 3) REGRAS DETERMINÍSTICAS
        # =========================
        padrao = self._padronizar_por_regra(entrada)
        if padrao is not None:
            padrao = dict(padrao)

            if padrao.get("produto_padronizado"):
                padrao["produto_padronizado"] = _limpar_produto_final(
                    padrao["produto_padronizado"]
                )

            padrao = _garantir_familia_grupo(padrao)
            padrao["__ORIGEM_PADRONIZACAO"] = "REGRA"

            if not _convenio_tem_uf(padrao.get("convenio_padronizado", "")):
                padrao["__ORIGEM_PADRONIZACAO"] = "MANUAL"

            self._cache_execucao[chave] = padrao
            return padrao, 0.98

        # =========================
        # 4) IA (FALLBACK FINAL)
        # =========================
        self.metricas["chamadas_ia"] += 1
        sugestao, confianca = self.ia.sugerir_padrao(entrada)

        sugestao = dict(sugestao)
        if sugestao.get("produto_padronizado"):
            sugestao["produto_padronizado"] = _limpar_produto_final(
                sugestao["produto_padronizado"]
            )

        sugestao = _garantir_familia_grupo(sugestao)
        sugestao["__ORIGEM_PADRONIZACAO"] = "IA"

        self._cache_execucao[chave] = sugestao

        if chave and chave not in self._logadas:
            self.logger.registrar_sugestao(chave, entrada, sugestao, confianca)
            self.metricas["linhas_csv"] += 1
            self._logadas.add(chave)

        return sugestao, confianca

    # ======================================================
    # HELPERS DE MONTAGEM
    # ======================================================
    def _montar_produto(self, prefixo: str, meio: str, taxa: str, beneficio: bool, seguro: bool) -> str:
        """
        prefixo: 'PREF. COTIA' / 'GOV. SP' / 'TJ - MG' / 'INST PREV GUARAPUAVA'
        meio: 'SEPREM' / 'SEC EDUCACAO' / 'HSPM' / ''
        beneficio insere: ' - BENEFICIO' antes da taxa
        seguro insere: ' - C/SEGURO' no final (após a taxa)
        """
        base = prefixo.strip()

        if meio:
            base = f"{base} - {meio.strip()}"

        if beneficio:
            base = f"{base} - BENEFICIO - {taxa}"
        else:
            base = f"{base} - {taxa}"

        if seguro:
            base = f"{base} - C/SEGURO"

        return base

    # ======================================================
    # REGRAS DETERMINÍSTICAS (ORDEM IMPORTA)
    # ======================================================
    def _padronizar_por_regra(self, entrada: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        texto_raw = entrada.get("produto_raw", "") or ""
        convenio_raw = entrada.get("convenio_raw", "") or ""

        texto = ascii_upper(texto_raw)
        conv = ascii_upper(convenio_raw)

        eh_combo = (
            "COMBO" in texto
        )

        if not texto and not conv:
            return None

        beneficio = tem_beneficio(texto) or tem_beneficio(conv) or ("CARTAO BENEFICIO" in texto)
        seguro = tem_seguro(texto) or ("SEGURO" in texto)

        if eh_combo:
                taxa = (
                    extrair_taxa_refin(texto)
                    or extrair_taxa_fim(texto)
                    or format_taxa_br(entrada.get("taxa_raw"))
                )
        else:
                    taxa = format_taxa_br(
                        extrair_taxa_fim(texto)
                        or entrada.get("taxa_raw")
                    )


        # ==================================================
        # AMAZONPREV — regra direta (prefeitura de Manaus)
        # Ex do banco: "EMPRÉSTIMO - AMAZONPREV - 2.50%"
        # Saída: "PREF. MANAUS - AMAZONPREV - 2,50%" | convênio "PREF. MANAUS AM"
        # ==================================================
        if "AMAZONPREV" in texto or "AMAZONPREV" in conv:
            uf = "AM"
            produto = self._montar_produto(f"GOV. {uf}", "AMAZONPREV", taxa, beneficio, seguro)
            return {
                "produto_padronizado": produto,
                "convenio_padronizado": f"GOV-{uf}",
                "familia_produto": "PREFEITURAS",
                "grupo_convenio": "PREFEITURAS",
            }


        # ==================================================
        # INST PREV (REGRA NOVA – ÚNICA)
        # ==================================================
        cidade_sub, subproduto = extrair_inst_prev_sub(texto)
        if cidade_sub:
            cidade = ascii_upper(cidade_sub)

            uf = (
                self.indice.uf_prefeitura(cidade)
                or uf_por_cidade_fallback(cidade)
                or extrair_gov_uf(texto)
                or extrair_gov_uf(conv)
                or _extrair_uf_por_estado_no_texto(texto)
                or _extrair_uf_por_estado_no_texto(conv)
            )

            # COM SIGLA DO INSTITUTO → PRODUTO COMEÇA COM PREF.
            if subproduto:
                produto = self._montar_produto(
                    f"PREF. {cidade}",
                    ascii_upper(subproduto),
                    taxa,
                    beneficio,
                    seguro
                )
            else:
                # SEM SIGLA → INST PREV <CIDADE>
                produto = self._montar_produto(
                    f"INST PREV {cidade}",
                    "",
                    taxa,
                    beneficio,
                    seguro
                )

            convenio_pad = (
                f"PREF. {cidade} {uf}"
                if uf
                else self.indice.alias_convenio.get(f"PREF. {cidade}", f"PREF. {cidade}")
            )

            return {
                "produto_padronizado": produto,
                "convenio_padronizado": convenio_pad,
                "familia_produto": "PREFEITURAS",
                "grupo_convenio": "PREFEITURAS",
            }

        # fallback genérico (INST PREV sem sigla)
        cidade_gen = extrair_inst_prev_gen(texto) or extrair_inst_prev_gen(conv)
        if cidade_gen:
            cidade = ascii_upper(cidade_gen)

            uf = (
                self.indice.uf_prefeitura(cidade)
                or uf_por_cidade_fallback(cidade)
                or extrair_gov_uf(texto)
                or extrair_gov_uf(conv)
                or _extrair_uf_por_estado_no_texto(texto)
                or _extrair_uf_por_estado_no_texto(conv)
            )

            produto = self._montar_produto(
                f"INST PREV {cidade}",
                "",
                taxa,
                beneficio,
                seguro
            )

            convenio_pad = (
                f"PREF. {cidade} {uf}"
                if uf
                else self.indice.alias_convenio.get(f"PREF. {cidade}", f"PREF. {cidade}")
            )

            return {
                "produto_padronizado": produto,
                "convenio_padronizado": convenio_pad,
                "familia_produto": "PREFEITURAS",
                "grupo_convenio": "PREFEITURAS",
            }

        if "CARTAO BENEFICIO" in texto or ("CARTAO" in texto and "BENEFICIO" in texto):
            uf = _extrair_uf_por_estado_no_texto(texto) or _extrair_uf_por_estado_no_texto(conv)
            if not uf and "GOIAS" in texto:
                uf = "GO"
            if uf:
                produto = self._montar_produto(f"GOV. {uf}", "", taxa, True, seguro)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": f"GOV-{uf}",
                    "familia_produto": "GOVERNOS",
                    "grupo_convenio": "ESTADUAL",
                }

        # ==================================================
        # 1) HSPM (especial)
        # ==================================================
        if "HSPM" in texto:
            produto = self._montar_produto("PREF. SAO PAULO", "HSPM", taxa, beneficio, seguro)
            return {
                "produto_padronizado": produto,
                "convenio_padronizado": "PREF. SAO PAULO SP",
                "familia_produto": "PREFEITURAS",
                "grupo_convenio": "PREFEITURAS",
            }

        # ==================================================
        # 2) SIAPE
        # ==================================================
        if "SIAPE" in texto or "SIAPE" in conv:
            return {
                "produto_padronizado": self._montar_produto("SIAPE", "", taxa, beneficio, seguro),
                "convenio_padronizado": "FEDERAL SIAPE",
                "familia_produto": "FEDERAIS",
                "grupo_convenio": "FEDERAL",
            }

        # ==================================================
        # 3) Universidades
        # ==================================================
        if "USP" in texto:
            return {
                "produto_padronizado": self._montar_produto("USP", "", taxa, beneficio, seguro),
                "convenio_padronizado": "GOV-SP",
                "familia_produto": "GOVERNOS",
                "grupo_convenio": "ESTADUAL",
            }

        if "UNICAMP" in texto:
            return {
                "produto_padronizado": self._montar_produto("UNICAMP", "", taxa, beneficio, seguro),
                "convenio_padronizado": "GOV-SP",
                "familia_produto": "GOVERNOS",
                "grupo_convenio": "ESTADUAL",
            }

        # ==================================================
        # 4) TRIBUNAIS (TJ)
        # ==================================================
        if "TJ" in texto or "TJ" in conv:
            uf = extrair_tj_uf(texto) or extrair_tj_uf(conv)
            if not uf:
                estado = extrair_tj_estado(texto) or extrair_tj_estado(conv)
                estado = estado.strip()
                if estado:
                    uf = ESTADO_PARA_UF.get(estado, "")
            if uf:
                produto = self._montar_produto(f"TJ - {uf}", "", taxa, beneficio, seguro)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": f"TJ | {uf}",
                    "familia_produto": "TRIBUNAIS",
                    "grupo_convenio": "TRIBUNAIS",
                }

        # ==================================================
        # 5) COMBO/PORT com GOV (NUNCA deixar PORT aparecer no produto)
        # ==================================================
        if eh_combo:

    # tenta extrair UF de qualquer forma válida
            uf = (
                extrair_gov_uf(texto)
                or extrair_gov_uf(conv)
                or _extrair_uf_por_estado_no_texto(texto)
                or _extrair_uf_por_estado_no_texto(conv)
            )

            # se ainda não tiver UF, deixa a regra seguir para PREF / INST PREV
            # (não retorna None aqui)
            derivado = ""

            if uf:
                if "COMBO" in texto:
                    derivado = extrair_derivado_gov_combo(texto, uf) or ""
                else:
                    m = re.search(rf"\b{uf}\b\s*-\s*(.+?)\s*-\s*\d", texto)
                    if m:
                        derivado = m.group(1).strip()

                if derivado and _RE_PROIBIDAS.search(derivado):
                    derivado = ""

                convenio = self.indice.alias_convenio.get(f"GOV {uf}", f"GOV-{uf}")

                produto = self._montar_produto(
                    f"GOV. {uf}",
                    derivado,
                    taxa,       # ← taxa já correta
                    beneficio,
                    seguro
                )

                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": convenio,
                    "familia_produto": "GOVERNOS",
                    "grupo_convenio": "ESTADUAL",
                }


        # ==================================================
        # 6) GOV simples (sem combo/port)
        # ==================================================
        if "GOV" in texto or "GOV" in conv:
            uf = extrair_gov_uf(texto) or extrair_gov_uf(conv)
            if not uf:
                uf = _extrair_uf_por_estado_no_texto(texto) or _extrair_uf_por_estado_no_texto(conv)
            if uf:
                derivado = ""
                m = re.search(rf"\bGOV[.\s-]*{uf}\b\s*-\s*(.+?)\s*-\s*\d", texto)
                if m:
                    derivado = m.group(1).strip()
                if derivado and _RE_PROIBIDAS.search(derivado):
                    derivado = ""

                convenio = self.indice.alias_convenio.get(f"GOV {uf}", f"GOV-{uf}")
                produto = self._montar_produto(f"GOV. {uf}", derivado, taxa, beneficio, seguro)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": convenio,
                    "familia_produto": "GOVERNOS",
                    "grupo_convenio": "ESTADUAL",
                }

        # ==================================================
        # 7) PREF explícito (PREF ...), incluindo PREF SP => SAO PAULO
        # ==================================================
        if "PREF" in texto or "PREF" in conv:
            cidade = extrair_pref_cidade_explicita(texto) or extrair_pref_cidade_explicita(conv)
            if cidade:
                if cidade in {"SP", "SAO PAULO", "SAO-PAULO"}:
                    cidade = "SAO PAULO"

                uf = (
                    self.indice.uf_prefeitura(cidade)
                    or uf_por_cidade_fallback(cidade)
                    or _extrair_uf_solto(texto)
                    or _extrair_uf_solto(conv)
                )

                if not uf:
                    return None

                convenio = f"PREF. {cidade} {uf}"
                produto = self._montar_produto(f"PREF. {cidade}", "", taxa, beneficio, seguro)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": convenio,
                    "familia_produto": "PREFEITURAS",
                    "grupo_convenio": "PREFEITURAS",
                }

        # ==================================================
        # 8) PREF implícito (cidade pura)
        # ==================================================
        cidade_pura = extrair_cidade_pura(texto)
        if cidade_pura:
            if cidade_pura in {"SP"}:
                cidade_pura = "SAO PAULO"

            if self.indice.eh_prefeitura(cidade_pura):
                uf = self.indice.uf_prefeitura(cidade_pura) or uf_por_cidade_fallback(cidade_pura)
                if not uf:
                    return None
                convenio = f"PREF. {cidade_pura} {uf}"
                produto = self._montar_produto(f"PREF. {cidade_pura}", "", taxa, beneficio, seguro)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": convenio,
                    "familia_produto": "PREFEITURAS",
                    "grupo_convenio": "PREFEITURAS",
                }

        # ==================================================
        # 9) Derivado prefeitura (SIGLA + CIDADE)
        # ==================================================
        sigla_cidade = extrair_sigla_e_cidade(texto)
        if sigla_cidade:
            sigla, cidade = sigla_cidade

            if cidade in {"SP"}:
                cidade = "SAO PAULO"

            if self.indice.eh_prefeitura(cidade):
                uf = self.indice.uf_prefeitura(cidade) or uf_por_cidade_fallback(cidade)
                if not uf:
                    return None
                convenio = f"PREF. {cidade} {uf}"
                produto = self._montar_produto(f"PREF. {cidade}", sigla, taxa, beneficio, seguro)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": convenio,
                    "familia_produto": "PREFEITURAS",
                    "grupo_convenio": "PREFEITURAS",
                }
        return None



    # ======================================================
    # CHAVE DO CACHE
    # ======================================================
    def _gerar_chave_manual(self, entrada: Dict[str, Any]) -> str:
        id_raw = (entrada.get("id_raw") or "").strip().upper()
        if not id_raw:
            return ""

        taxa_raw = _normalizar_numero_str(entrada.get("taxa_raw"), casas=2).upper()
        prazo_raw = _normalizar_prazo_str(entrada.get("prazo_raw"))

        return f"{id_raw}|{taxa_raw}|{prazo_raw}"

    # ======================================================
    # FLUSH DE LOGS (SEGURANÇA)
    # ======================================================
    def flush_logs(self) -> int:
        if hasattr(self, "logger") and self.logger:
            if hasattr(self.logger, "flush"):
                return self.logger.flush()
        return 0
