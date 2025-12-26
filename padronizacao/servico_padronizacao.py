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
)
from .indice_cache import IndiceCache


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
    - "120" == "120-120" -> "120"
    - "120 a 144" -> "120-144"
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

_RE_PROIBIDAS = re.compile(
    r"\b(" + "|".join(
        sorted({ascii_upper(p) for p in _PALAVRAS_PROIBIDAS_PRODUTO}, key=len, reverse=True)
    ) + r")\b"
)


def _limpar_produto_final(produto: str) -> str:
    """
    Garante que produto_padronizado:
    - esteja ASCII/UPPER
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
    1) cache em memória (execução) por chave canônica (id|taxa|prazo)
    2) cache persistido (JSON)
    3) regras determinísticas (inclui índice/catálogos)
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

        # cache por chave (id|taxa|prazo) - garante comportamento atual
        self._cache_execucao: Dict[str, Dict[str, Any]] = {}

        # cache adicional por "texto normalizado" (evita repetir regra/IA quando muda só ID/prazo)
        # OBS: isso NÃO substitui o cache por chave; é só um turbo.
        self._cache_por_texto: Dict[str, Dict[str, Any]] = {}

        self._logadas: Set[str] = set()

        self.metricas = {
            "consultas_cache": 0,
            "hits_cache": 0,
            "chamadas_ia": 0,
            "linhas_csv": 0,
            "hits_cache_texto": 0,
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
        """
        Mantém 100% do comportamento atual:
        - primeiro tenta cache por chave (id|taxa|prazo)
        - depois cache persistido
        - depois regras
        - por fim IA

        Turbo:
        - antes da IA, tenta cache por texto (produto_raw + convenio_raw + taxa + prazo normalizados)
        """
        chave = self._gerar_chave_manual(entrada)
        self.metricas["consultas_cache"] += 1

        # 1) cache execução por chave
        if chave and chave in self._cache_execucao:
            self.metricas["hits_cache"] += 1
            return self._cache_execucao[chave], 0.99

        # 2) cache persistido por chave
        if chave:
            achado = self.cache.get(chave)
            if achado is not None:
                self.metricas["hits_cache"] += 1
                achado = dict(achado)
                if achado.get("produto_padronizado"):
                    achado["produto_padronizado"] = _limpar_produto_final(achado["produto_padronizado"])
                achado = _garantir_familia_grupo(achado)
                # salva na execução por chave
                self._cache_execucao[chave] = achado
                return achado, 1.0

        # 3) regras determinísticas
        padrao = self._padronizar_por_regra(entrada)
        if padrao is not None:
            padrao = dict(padrao)
            if padrao.get("produto_padronizado"):
                padrao["produto_padronizado"] = _limpar_produto_final(padrao["produto_padronizado"])
            padrao = _garantir_familia_grupo(padrao)

            if chave:
                self._cache_execucao[chave] = padrao

            # cache extra por texto (pra evitar trabalho repetido em massa)
            key_texto = self._gerar_chave_texto(entrada)
            if key_texto:
                self._cache_por_texto[key_texto] = padrao

            return padrao, 0.98

        # 3.5) cache por texto (antes de IA) - turbo
        key_texto = self._gerar_chave_texto(entrada)
        if key_texto and key_texto in self._cache_por_texto:
            self.metricas["hits_cache_texto"] += 1
            padrao = dict(self._cache_por_texto[key_texto])
            if chave:
                self._cache_execucao[chave] = padrao
            return padrao, 0.97

        # 4) IA fallback
        self.metricas["chamadas_ia"] += 1
        sugestao, confianca = self.ia.sugerir_padrao(entrada)

        sugestao = dict(sugestao)
        if sugestao.get("produto_padronizado"):
            sugestao["produto_padronizado"] = _limpar_produto_final(sugestao["produto_padronizado"])
        sugestao = _garantir_familia_grupo(sugestao)

        if chave:
            self._cache_execucao[chave] = sugestao

        if key_texto:
            self._cache_por_texto[key_texto] = sugestao

        if chave and chave not in self._logadas:
            self.logger.registrar_sugestao(chave, entrada, sugestao, confianca)
            self.metricas["linhas_csv"] += 1
            self._logadas.add(chave)

        return sugestao, confianca

    # ======================================================
    # HELPERS DE MONTAGEM
    # ======================================================
    def _montar_produto(self, prefixo: str, meio: str, taxa: str, beneficio: bool) -> str:
        """
        prefixo: 'PREF. COTIA' / 'GOV. SP' / 'TJ - MG' / 'INST PREV GUARAPUAVA'
        meio: 'SEPREM' / 'SEC EDUCACAO' / 'HSPM' / 'IPAMV' / ''
        beneficio insere: ' - BENEFICIO' antes da taxa
        """
        base = prefixo.strip()

        if meio:
            base = f"{base} - {meio.strip()}"

        if beneficio:
            return f"{base} - BENEFICIO - {taxa}"
        return f"{base} - {taxa}"

    def _gerar_chave_texto(self, entrada: Dict[str, Any]) -> str:
        """
        Chave de “conteúdo” para reaproveitar padronização quando:
        - o texto do produto/convenio é igual,
        - taxa/prazo são iguais
        Mesmo que o ID mude, ainda dá pra aproveitar regra/IA.

        Isso melhora muito performance em massa.
        """
        produto_raw = entrada.get("produto_raw") or ""
        convenio_raw = entrada.get("convenio_raw") or ""
        if not produto_raw and not convenio_raw:
            return ""

        # normaliza taxa/prazo igual ao que você usa na chave principal (pra não dar mismatch)
        taxa_raw_norm = _normalizar_numero_str(entrada.get("taxa_raw"), casas=2).upper()
        prazo_raw_norm = _normalizar_prazo_str(entrada.get("prazo_raw"))

        return f"{ascii_upper(produto_raw)}|{ascii_upper(convenio_raw)}|{taxa_raw_norm}|{prazo_raw_norm}"

    # ======================================================
    # REGRAS DETERMINÍSTICAS (ORDEM IMPORTA)
    # ======================================================
    def _padronizar_por_regra(self, entrada: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        produto_raw = entrada.get("produto_raw", "") or ""
        convenio_raw = entrada.get("convenio_raw", "") or ""

        # Early exit
        if not produto_raw and not convenio_raw:
            return None

        texto = ascii_upper(produto_raw)
        conv = ascii_upper(convenio_raw)

        # Early exit (não tem pista nenhuma)
        if not texto and not conv:
            return None

        beneficio = tem_beneficio(texto) or tem_beneficio(conv) or ("CARTAO BENEFICIO" in texto)
        taxa = format_taxa_br(entrada.get("taxa_raw") or extrair_taxa_fim(texto))

        # ==================================================
        # AMAZONPREV — regra direta (prefeitura de Manaus)
        # ==================================================
        if "AMAZONPREV" in texto or "AMAZONPREV" in conv:
            cidade = "MANAUS"
            uf = "AM"
            produto = self._montar_produto(f"PREF. {cidade}", "AMAZONPREV", taxa, beneficio)
            return {
                "produto_padronizado": produto,
                "convenio_padronizado": f"PREF. {cidade} {uf}",
                "familia_produto": "PREFEITURAS",
                "grupo_convenio": "PREFEITURAS",
            }

        # ==================================================
        # INST PREV (REGRA NOVA – ÚNICA)
        #
        # Caso A (COM sigla/subproduto):
        #   "EMPRÉSTIMO - INST PREV VITÓRIA - IPAMV - 2.14%"
        #   -> Produto:  "PREF. VITORIA - IPAMV - 2,14%"
        #   -> Convênio: "PREF. VITORIA ES"
        #
        # Caso B (SEM sigla/subproduto):
        #   "EMPRÉSTIMO - INST PREV ITANHAEM - 1.99%"
        #   -> Produto:  "INST PREV ITANHAEM - 1,99%"
        #   -> Convênio: "PREF. ITANHAEM SP" (se UF resolvida)
        # ==================================================
        inst_sub = extrair_inst_prev_sub(texto)
        if inst_sub:
            cidade_sub, subproduto = inst_sub
            cidade = ascii_upper(cidade_sub or "")

            subproduto_norm = ascii_upper(subproduto or "")
            if subproduto_norm:
                # tenta corrigir cidade pelo catálogo do instituto (sigla)
                cidade_catalogo = cidade_por_inst_prev(subproduto_norm)
                if cidade_catalogo:
                    cidade = cidade_catalogo

            # resolve UF: indice -> fallback -> estado no texto -> UF solta
            uf = (
                self.indice.uf_prefeitura(cidade)
                or uf_por_cidade_fallback(cidade)
                or _extrair_uf_por_estado_no_texto(texto)
                or _extrair_uf_por_estado_no_texto(conv)
                or _extrair_uf_solto(texto)
                or _extrair_uf_solto(conv)
            )

            # ✅ Se tem UF: vira prefeitura e segue teu padrão oficial
            if uf:
                if subproduto_norm:
                    # COM subproduto: "PREF. CIDADE - SIGLA - TAXA"
                    produto = self._montar_produto(f"PREF. {cidade}", subproduto_norm, taxa, beneficio)
                else:
                    # SEM subproduto: "INST PREV CIDADE - TAXA" (exigência tua)
                    produto = self._montar_produto(f"INST PREV {cidade}", "", taxa, beneficio)

                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": f"PREF. {cidade} {uf}",
                    "familia_produto": "PREFEITURAS",
                    "grupo_convenio": "PREFEITURAS",
                }

            # ❗ Sem UF: ainda assim devolve “bonito”, mas marca MANUAL
            if subproduto_norm:
                produto = self._montar_produto(f"INST PREV {cidade}", subproduto_norm, taxa, beneficio)
            else:
                produto = self._montar_produto(f"INST PREV {cidade}", "", taxa, beneficio)

            return {
                "produto_padronizado": produto,
                "convenio_padronizado": "",
                "familia_produto": "MANUAL",
                "grupo_convenio": "MANUAL",
            }

        # INST PREV genérico (sem conseguir extrair subproduto)
        cidade_gen = extrair_inst_prev_gen(texto) or extrair_inst_prev_gen(conv)
        if cidade_gen:
            cidade = ascii_upper(cidade_gen)

            uf = (
                self.indice.uf_prefeitura(cidade)
                or uf_por_cidade_fallback(cidade)
                or _extrair_uf_por_estado_no_texto(texto)
                or _extrair_uf_por_estado_no_texto(conv)
                or _extrair_uf_solto(texto)
                or _extrair_uf_solto(conv)
            )

            produto = self._montar_produto(f"INST PREV {cidade}", "", taxa, beneficio)

            if uf:
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": f"PREF. {cidade} {uf}",
                    "familia_produto": "PREFEITURAS",
                    "grupo_convenio": "PREFEITURAS",
                }

            return {
                "produto_padronizado": produto,
                "convenio_padronizado": "",
                "familia_produto": "MANUAL",
                "grupo_convenio": "MANUAL",
            }

        # ==================================================
        # 0) CARTAO BENEFICIO
        # ==================================================
        if "CARTAO BENEFICIO" in texto or ("CARTAO" in texto and "BENEFICIO" in texto):
            uf = _extrair_uf_por_estado_no_texto(texto) or _extrair_uf_por_estado_no_texto(conv)
            if not uf and "GOIAS" in texto:
                uf = "GO"
            if uf:
                produto = self._montar_produto(f"GOV. {uf}", "", taxa, True)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": f"GOV-{uf}",
                    "familia_produto": "GOVERNOS",
                    "grupo_convenio": "ESTADUAL",
                }

        # ==================================================
        # 1) HSPM
        # ==================================================
        if "HSPM" in texto:
            produto = self._montar_produto("PREF. SAO PAULO", "HSPM", taxa, beneficio)
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
                "produto_padronizado": f"SIAPE - {taxa}",
                "convenio_padronizado": "FEDERAL SIAPE",
                "familia_produto": "FEDERAIS",
                "grupo_convenio": "FEDERAL",
            }

        # ==================================================
        # 3) Universidades
        # ==================================================
        if "USP" in texto:
            return {
                "produto_padronizado": f"USP - {taxa}",
                "convenio_padronizado": "GOV-SP",
                "familia_produto": "GOVERNOS",
                "grupo_convenio": "ESTADUAL",
            }

        if "UNICAMP" in texto:
            return {
                "produto_padronizado": f"UNICAMP - {taxa}",
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
                estado = (estado or "").strip()
                if estado:
                    uf = ESTADO_PARA_UF.get(estado, "")
            if uf:
                produto = f"TJ - {uf} - {taxa}"
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": f"TJ | {uf}",
                    "familia_produto": "TRIBUNAIS",
                    "grupo_convenio": "TRIBUNAIS",
                }

        # ==================================================
        # 5) COMBO/PORT com GOV
        # ==================================================
        if "GOV" in texto and ("COMBO" in texto or "PORT" in texto or "REFIN" in texto):
            uf = extrair_gov_uf(texto) or extrair_gov_uf(conv)
            if not uf:
                uf = _extrair_uf_por_estado_no_texto(texto) or _extrair_uf_por_estado_no_texto(conv)
            if not uf:
                return None

            taxa_refin = extrair_taxa_refin(texto) or taxa
            derivado = ""
            if "COMBO" in texto:
                derivado = extrair_derivado_gov_combo(texto, uf) or ""
            else:
                m = re.search(rf"\bGOV[.\s-]*{uf}\b\s*-\s*(.+?)\s*-\s*\d", texto)
                if m:
                    derivado = m.group(1).strip()

            if derivado and _RE_PROIBIDAS.search(derivado):
                derivado = ""

            convenio = self.indice.alias_convenio.get(f"GOV {uf}", f"GOV-{uf}")
            produto = self._montar_produto(f"GOV. {uf}", derivado, taxa_refin, beneficio)

            return {
                "produto_padronizado": produto,
                "convenio_padronizado": convenio,
                "familia_produto": "GOVERNOS",
                "grupo_convenio": "ESTADUAL",
            }

        # ==================================================
        # 6) GOV simples
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
                produto = self._montar_produto(f"GOV. {uf}", derivado, taxa, beneficio)
                return {
                    "produto_padronizado": produto,
                    "convenio_padronizado": convenio,
                    "familia_produto": "GOVERNOS",
                    "grupo_convenio": "ESTADUAL",
                }

        # ==================================================
        # 7) PREF explícito
        # ==================================================
        if "PREF" in texto or "PREF" in conv:
            cidade = extrair_pref_cidade_explicita(texto) or extrair_pref_cidade_explicita(conv)
            if cidade:
                cidade = ascii_upper(cidade)
                if cidade in {"SP", "SAO PAULO", "SAO-PAULO"}:
                    cidade = "SAO PAULO"

                uf = self.indice.uf_prefeitura(cidade)
                if not uf:
                    uf = _extrair_uf_solto(texto) or _extrair_uf_solto(conv) or "SP"

                convenio = f"PREF. {cidade} {uf}"
                produto = self._montar_produto(f"PREF. {cidade}", "", taxa, beneficio)
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
            cidade_pura = ascii_upper(cidade_pura)
            if cidade_pura in {"SP"}:
                cidade_pura = "SAO PAULO"

            if self.indice.eh_prefeitura(cidade_pura):
                uf = self.indice.uf_prefeitura(cidade_pura) or "SP"
                convenio = f"PREF. {cidade_pura} {uf}"
                produto = self._montar_produto(f"PREF. {cidade_pura}", "", taxa, beneficio)
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
            sigla = ascii_upper(sigla)
            cidade = ascii_upper(cidade)

            if cidade in {"SP"}:
                cidade = "SAO PAULO"

            if self.indice.eh_prefeitura(cidade):
                uf = self.indice.uf_prefeitura(cidade) or "SP"
                convenio = f"PREF. {cidade} {uf}"
                produto = self._montar_produto(f"PREF. {cidade}", sigla, taxa, beneficio)
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
