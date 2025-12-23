import re
from typing import Dict, Any
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
        self.alias_convenio: Dict[str, str] = {}     # "GOV SP" -> "GOV-SP", "PREF COTIA" -> "PREF. COTIA SP"

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
            conv_raw = padrao.get("convenio_padronizado", "")
            conv = ascii_upper(conv_raw)

            if not conv:
                continue

            # ==================================================
            # PREFEITURA — FORMATO PADRÃO
            # PREF. CIDADE UF
            # ==================================================
            m_pref = re.match(r"^PREF\.\s+(.+?)\s+([A-Z]{2})$", conv)
            if m_pref:
                cidade, uf = m_pref.groups()
                cidade = cidade.strip()
                uf = uf.strip()

                self._registrar_prefeitura(cidade, uf, conv_raw)
                continue

            # ==================================================
            # PREFEITURA — FORMAS ALTERNATIVAS (DEFENSIVO)
            # PREF CIDADE UF
            # ==================================================
            m_pref_alt = re.match(r"^PREF\s+(.+?)\s+([A-Z]{2})$", conv)
            if m_pref_alt:
                cidade, uf = m_pref_alt.groups()
                cidade = cidade.strip()
                uf = uf.strip()

                self._registrar_prefeitura(cidade, uf, conv_raw)
                continue

            # ==================================================
            # GOV — FORMATO PADRÃO
            # GOV-SP
            # ==================================================
            m_gov = re.match(r"^GOV[-\s]?([A-Z]{2})$", conv)
            if m_gov:
                uf = m_gov.group(1).strip()
                self._registrar_gov(uf, conv_raw)
                continue

            # ==================================================
            # GOV — FORMAS ALTERNATIVAS
            # GOV. SP / GOV SP
            # ==================================================
            m_gov_alt = re.match(r"^GOV[.\s]+([A-Z]{2})$", conv)
            if m_gov_alt:
                uf = m_gov_alt.group(1).strip()
                self._registrar_gov(uf, conv_raw)
                continue

            # ==================================================
            # INST PREV — APRENDE COMO PREFEITURA
            # Ex: INST PREV VITORIA -> usa convênio da prefeitura
            # ==================================================
            if conv.startswith("INST PREV"):
                # tenta extrair cidade
                m_inst = re.match(r"^INST PREV\s+(.+)$", conv)
                if m_inst:
                    cidade = m_inst.group(1).strip()
                    # UF só será conhecida se já existir no índice
                    uf = self.cidade_para_uf.get(cidade)
                    if uf:
                        self._registrar_prefeitura(cidade, uf, f"PREF. {cidade} {uf}")

    # ======================================================
    # REGISTROS INTERNOS
    # ======================================================
    def _registrar_prefeitura(self, cidade: str, uf: str, convenio_original: str):
        cidade_u = ascii_upper(cidade)
        uf_u = ascii_upper(uf)

        self.cidade_para_uf[cidade_u] = uf_u
        self.cidade_para_tipo[cidade_u] = "PREF"

        # aliases fortes
        self.alias_convenio[f"PREF {cidade_u}"] = f"PREF. {cidade_u} {uf_u}"
        self.alias_convenio[f"PREF. {cidade_u}"] = f"PREF. {cidade_u} {uf_u}"
        self.alias_convenio[f"PREF {cidade_u} {uf_u}"] = f"PREF. {cidade_u} {uf_u}"

        # casos tipo PREF SP
        if cidade_u == "SAO PAULO" or cidade_u == "SP":
            self.alias_convenio["PREF SP"] = "PREF. SAO PAULO SP"
            self.alias_convenio["PREF. SP"] = "PREF. SAO PAULO SP"

    def _registrar_gov(self, uf: str, convenio_original: str):
        uf_u = ascii_upper(uf)

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
