import re
from typing import Dict
from .utils_padronizacao import ascii_upper


class IndiceCache:
    """
    Índices derivados do cache persistido, para inferência sem IA.

    Objetivo:
    - Descobrir UF de prefeitura a partir do nome da cidade
    - Saber se uma cidade é prefeitura
    - Normalizar aliases de convênios (GOV / PREF)
    """

    def __init__(self):
        self.cidade_para_uf: Dict[str, str] = {}
        self.cidade_para_tipo: Dict[str, str] = {}   # "PREF"
        self.alias_convenio: Dict[str, str] = {}     # aliases fortes

    # ======================================================
    # ALIMENTAÇÃO A PARTIR DO CACHE MANUAL
    # ======================================================
    def alimentar(self, cache_items):
        """
        cache_items: iterable de (chave, padrao)
        """
        self.cidade_para_uf.clear()
        self.cidade_para_tipo.clear()
        self.alias_convenio.clear()

        for _, padrao in cache_items:
            conv_raw = padrao.get("convenio_padronizado", "") or ""
            conv = ascii_upper(conv_raw)

            prod_raw = padrao.get("produto_padronizado", "") or ""
            prod = ascii_upper(prod_raw)

            if not conv and not prod:
                continue

            # ==================================================
            # PREFEITURA — FORMATO PADRÃO
            # PREF. CIDADE UF
            # ==================================================
            m_pref = re.match(r"^PREF\.\s+(.+?)\s+([A-Z]{2})$", conv)
            if m_pref:
                cidade, uf = m_pref.groups()
                self._registrar_prefeitura(cidade, uf)
                continue

            # ==================================================
            # PREFEITURA — FORMAS ALTERNATIVAS (DEFENSIVO)
            # PREF CIDADE UF
            # ==================================================
            m_pref_alt = re.match(r"^PREF\s+(.+?)\s+([A-Z]{2})$", conv)
            if m_pref_alt:
                cidade, uf = m_pref_alt.groups()
                self._registrar_prefeitura(cidade, uf)
                continue

            # ==================================================
            # GOV — FORMATO PADRÃO
            # GOV-SP
            # ==================================================
            m_gov = re.match(r"^GOV[-\s]?([A-Z]{2})$", conv)
            if m_gov:
                uf = m_gov.group(1)
                self._registrar_gov(uf)
                continue

            # ==================================================
            # GOV — FORMAS ALTERNATIVAS
            # GOV. SP / GOV SP
            # ==================================================
            m_gov_alt = re.match(r"^GOV[.\s]+([A-Z]{2})$", conv)
            if m_gov_alt:
                uf = m_gov_alt.group(1)
                self._registrar_gov(uf)
                continue

            # ==================================================
            # APRENDIZADO DE PREFEITURA VIA CONVÊNIO (REGRA MESTRE)
            #
            # Independe do produto:
            # - PREF. FORMIGA MG
            # - PREF. GUARAPUAVA PR
            # ==================================================
            m_pref_conv = re.match(r"^PREF\.\s+(.+?)\s+([A-Z]{2})$", conv)
            if m_pref_conv:
                cidade, uf = m_pref_conv.groups()
                self._registrar_prefeitura(cidade, uf)
                continue

            # ==================================================
            # INST PREV — aprendizado defensivo a partir do PRODUTO
            # (fallback, caso convênio esteja vazio)
            # ==================================================
            if prod.startswith("INST PREV"):
                m_inst = re.match(r"^INST PREV\s+(.+?)(?:\s*-\s*|$)", prod)
                if not m_inst:
                    continue

                cidade = m_inst.group(1).strip()

                # tenta extrair UF do convênio (se existir)
                m_uf = re.match(r"^PREF\.?\s+(.+?)\s+([A-Z]{2})$", conv)
                if m_uf:
                    cidade_conv, uf = m_uf.groups()
                    if ascii_upper(cidade_conv) == ascii_upper(cidade):
                        self._registrar_prefeitura(cidade, uf)

    # ======================================================
    # REGISTROS INTERNOS
    # ======================================================
    def _registrar_prefeitura(self, cidade: str, uf: str):
        cidade_u = ascii_upper(cidade)
        uf_u = ascii_upper(uf)

        if not cidade_u or not uf_u:
            return

        self.cidade_para_uf[cidade_u] = uf_u
        self.cidade_para_tipo[cidade_u] = "PREF"

        # aliases fortes
        self.alias_convenio[f"PREF {cidade_u}"] = f"PREF. {cidade_u} {uf_u}"
        self.alias_convenio[f"PREF. {cidade_u}"] = f"PREF. {cidade_u} {uf_u}"
        self.alias_convenio[f"PREF {cidade_u} {uf_u}"] = f"PREF. {cidade_u} {uf_u}"

        # casos especiais
        if cidade_u in ("SAO PAULO", "SP"):
            self.alias_convenio["PREF SP"] = "PREF. SAO PAULO SP"
            self.alias_convenio["PREF. SP"] = "PREF. SAO PAULO SP"

    def _registrar_gov(self, uf: str):
        uf_u = ascii_upper(uf)
        if not uf_u:
            return

        self.alias_convenio[f"GOV {uf_u}"] = f"GOV-{uf_u}"
        self.alias_convenio[f"GOV. {uf_u}"] = f"GOV-{uf_u}"
        self.alias_convenio[f"GOV-{uf_u}"] = f"GOV-{uf_u}"

    # ======================================================
    # CONSULTAS
    # ======================================================
    def uf_prefeitura(self, cidade: str) -> str:
        return self.cidade_para_uf.get(ascii_upper(cidade), "")

    def eh_prefeitura(self, cidade: str) -> bool:
        return self.cidade_para_tipo.get(ascii_upper(cidade)) == "PREF"
