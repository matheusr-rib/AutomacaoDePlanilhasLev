from __future__ import annotations

import re
import unicodedata
from typing import Set, Optional


# ==============================
# NORMALIZAÇÃO DE TEXTO
# ==============================

# caracteres que viram espaço
_RE_CLEAN = re.compile(
    r"[|\\/·•,:;()\[\]{}\-_]",
    flags=re.UNICODE
)

_RE_MULTI_SPACE = re.compile(r"\s+")

_RE_TAXA = re.compile(r"(\d{1,2}[.,]\d{2})\s*%?", re.IGNORECASE)


def normalizar_texto(s: str) -> str:
    """
    Normaliza texto para comparação:
    - remove acentos
    - uppercase
    - remove caracteres especiais
    - normaliza espaços
    """
    if not s:
        return ""

    # normaliza unicode (acentos)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))

    s = s.upper().strip()

    # substitui caracteres especiais por espaço
    s = _RE_CLEAN.sub(" ", s)

    # normaliza espaços
    s = _RE_MULTI_SPACE.sub(" ", s).strip()

    return s


# ==============================
# TOKENS / SIMILARIDADE
# ==============================

def tokens(s: str) -> Set[str]:
    """
    Retorna conjunto de tokens úteis para similaridade.
    """
    if not s:
        return set()
    return set(normalizar_texto(s).split())


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ==============================
# UF
# ==============================

_UFS = {
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS",
    "MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC",
    "SP","SE","TO"
}

_ESTADOS_PARA_UF = {
    "SAO PAULO": "SP",
    "RIO DE JANEIRO": "RJ",
    "MINAS GERAIS": "MG",
    "ESPIRITO SANTO": "ES",
    "PARANA": "PR",
    "SANTA CATARINA": "SC",
    "RIO GRANDE DO SUL": "RS",
    "BAHIA": "BA",
    "GOIAS": "GO",
    "TOCANTINS": "TO",
    "PERNAMBUCO": "PE",
    "CEARA": "CE",
    "MARANHAO": "MA",
    "PARA": "PA",
    "PIAUI": "PI",
    "RIO GRANDE DO NORTE": "RN",
    "PARAIBA": "PB",
    "SERGIPE": "SE",
    "ALAGOAS": "AL",
    "AMAZONAS": "AM",
    "RONDONIA": "RO",
    "RORAIMA": "RR",
    "ACRE": "AC",
    "AMAPA": "AP",
    "MATO GROSSO": "MT",
    "MATO GROSSO DO SUL": "MS",
    "DISTRITO FEDERAL": "DF",
}


def normalizar_uf(uf: str) -> Optional[str]:
    if not uf:
        return None

    u = normalizar_texto(uf)

    if u in _UFS:
        return u

    return _ESTADOS_PARA_UF.get(u)


# ==============================
# TAXA
# ==============================

def extrair_taxa(texto: str) -> Optional[float]:
    """
    Extrai a ÚLTIMA taxa do texto.
    (REFIN é tratado fora, no serviço)
    """
    if not texto:
        return None

    matches = _RE_TAXA.findall(texto)
    if not matches:
        return None

    try:
        return float(matches[-1].replace(",", "."))
    except Exception:
        return None


def formatar_taxa(taxa: float) -> str:
    """
    Formata taxa no padrão brasileiro: 2,25%
    """
    return f"{taxa:.2f}".replace(".", ",") + "%"
