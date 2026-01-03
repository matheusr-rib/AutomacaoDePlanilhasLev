# padronizacao/catalogos_inst_prev.py
"""
Catálogos determinísticos para Institutos Previdenciários (INST PREV).

Objetivo:
- Resolver cidade e UF sem IA
- Lookup O(1)
- Evitar regex pesada e loops
- Escalar com segurança conforme o cache cresce

Regra de ouro:
- Todas as chaves em ASCII_UPPER
"""

from __future__ import annotations

from pathlib import Path
import json
from .utils_padronizacao import ascii_upper


# ==========================================================
# INST PREV / SIGLA -> CIDADE
# ==========================================================
# Usado quando o banco manda:
#   INST PREV <CIDADE> - <SIGLA>
# ou
#   INST PREV <CIDADE> <SIGLA>
#
# A SIGLA tem prioridade sobre o texto livre
# ==========================================================
INST_PREV_PARA_CIDADE = {
    # ===== SÃO PAULO =====
    "IPREM": "SAO PAULO",
    "SPPREV": "SAO PAULO",
    "IPSM": "SAO MIGUEL ARCANJO",
    "IPREJ": "JUNDIAI",
    "IPREMU": "MOGI DAS CRUZES",
    "IPREMAR": "ARARAQUARA",
    "IPRECAM": "CAMPINAS",
    "IPREBA": "BARUERI",
    "IPREJAB": "JABOTICABAL",
    "IPREMO": "MOGI MIRIM",
    "IPREMA": "AMERICANA",
    "IPREJA": "JACAREI",
    "IPREPI": "PIRACICABA",
    "IPREVI": "ITAPEVI",
    "IPREIT": "ITATIBA",
    "IPRETA": "TAUBATE",
    "IPREMAU": "MAUA",
    "IPREEM": "EMBU DAS ARTES",

    # ===== MINAS GERAIS =====
    "PREVIFOR": "FORMIGA",
    "IPSEMG": "BELO HORIZONTE",
    "IPREMBH": "BELO HORIZONTE",
    "IPREMU": "UBERLANDIA",
    "IPREMC": "CONTAGEM",
    "IPREJL": "JUIZ DE FORA",
    "IPREOP": "OURO PRETO",
    "IPREMV": "VARGINHA",
    "IPREPC": "POCOS DE CALDAS",
    "IPREPD": "PATOS DE MINAS",

    # ===== ESPÍRITO SANTO =====
    "IPAMV": "VITORIA",
    "IPAM": "VILA VELHA",
    "IPREVES": "SERRA",
    "IPREVC": "CARIACICA",

    # ===== PARANÁ =====
    "IPMC": "CURITIBA",
    "IPREMU": "MARINGA",
    "IPREMG": "GUARAPUAVA",
    "IPREML": "LONDRINA",
    "IPREMF": "FOZ DO IGUACU",
    "IPREMP": "PONTA GROSSA",

    # ===== RIO DE JANEIRO =====
    "PREVI-RIO": "RIO DE JANEIRO",
    "PREVIRIO": "RIO DE JANEIRO",
    "IPREJ": "NITEROI",
    "IPRENI": "NITEROI",
    "IPREMQ": "QUEIMADOS",

    # ===== AMAZONAS =====
    "AMAZONPREV": "MANAUS",

    # ===== RIO GRANDE DO SUL =====
    "IPERGS": "PORTO ALEGRE",
    "IPREMPOA": "PORTO ALEGRE",
    "IPREMNH": "NOVO HAMBURGO",
    "IPREMCX": "CAXIAS DO SUL",
    "IPREMSM": "SANTA MARIA",

    # ===== SANTA CATARINA =====
    "IPREFLOR": "FLORIANOPOLIS",
    "IPREBLU": "BLUMENAU",
    "IPREJAR": "JARAGUA DO SUL",
    "IPREITA": "ITAJAI",
    "IPRECRI": "CRICIUMA",

    # ===== BAHIA =====
    "IPREV": "SALVADOR",
    "IPRES": "SALVADOR",
    "IPREVC": "VITORIA DA CONQUISTA",
    "IPREJUA": "JUAZEIRO",

    # ===== CEARÁ =====
    "IPM": "FORTALEZA",
    "IPREFOR": "FORTALEZA",
    "IPREJUA": "JUAZEIRO DO NORTE",
    "IPRESOB": "SOBRAL",

    # ===== PERNAMBUCO =====
    "RECIPREV": "RECIFE",
    "IPREOL": "OLINDA",
    "IPREJAB": "JABOATAO DOS GUARARAPES",

    # ===== GOIÁS =====
    "IPASGO": "GOIANIA",
    "IPREAN": "ANAPOLIS",
}


# ==========================================================
# CIDADE -> UF (fallback via JSON)
# ==========================================================
# Fonte: city_to_uf.json (todas as cidades brasileiras)
# ==========================================================

_BASE_DIR = Path(__file__).parent
_CIDADES_JSON = _BASE_DIR / "city_to_uf.json"

try:
    with open(_CIDADES_JSON, encoding="utf-8") as f:
        _CIDADE_PARA_UF_FALLBACK = json.load(f)
except Exception:
    # Falha controlada: sistema continua rodando
    _CIDADE_PARA_UF_FALLBACK = {}


# ==========================================================
# HELPERS (API pública do módulo)
# ==========================================================
def cidade_por_inst_prev(subproduto: str) -> str:
    """
    Retorna cidade baseada na sigla/subproduto do instituto.
    """
    if not subproduto:
        return ""
    return INST_PREV_PARA_CIDADE.get(ascii_upper(subproduto), "")


def uf_por_cidade_fallback(cidade: str) -> str:
    """
    Retorna UF baseada na cidade (fallback determinístico via JSON).
    """
    if not cidade:
        return ""
    return _CIDADE_PARA_UF_FALLBACK.get(ascii_upper(cidade), "")
