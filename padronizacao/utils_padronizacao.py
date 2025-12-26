import re
import unicodedata
from typing import Optional, Tuple, Dict, Set

# =====================================================
# NORMALIZAÇÃO ASCII (sem acento) + UPPER
# =====================================================
def ascii_upper(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def format_taxa_br(taxa_str: str) -> str:
    """
    '2.5' / '2,50' / '2.50%' / '2,50%' -> '2,50%'
    """
    if not taxa_str:
        return ""
    s = str(taxa_str).strip().replace("%", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".") if (s.count(",") == 1 and s.count(".") > 1) else s.replace(",", ".")
    try:
        v = float(s)
        return f"{v:.2f}".replace(".", ",") + "%"
    except Exception:
        s2 = ascii_upper(taxa_str).replace(".", ",")
        return s2 if s2.endswith("%") else (s2 + "%")


# =====================================================
# EXTRAÇÃO DE TAXA
# =====================================================
_TAXA_FIM_REGEX = re.compile(r"(\d{1,2}[.,]\d{2})%?$")
_TAXA_REFIN_REGEX = re.compile(r"REFIN\s*(\d{1,2}[.,]\d{2})%?", re.I)


def extrair_taxa_fim(texto: str) -> str:
    """
    Pega a taxa no final do texto.
    """
    if not texto:
        return ""
    t = ascii_upper(texto)
    m = _TAXA_FIM_REGEX.search(t)
    return format_taxa_br(m.group(1)) if m else ""


def extrair_taxa_refin(texto: str) -> str:
    """
    Pega a taxa depois de 'REFIN' (COMBO).
    """
    if not texto:
        return ""
    t = ascii_upper(texto)
    m = _TAXA_REFIN_REGEX.search(t)
    return format_taxa_br(m.group(1)) if m else ""


# =====================================================
# FLAGS
# =====================================================
def tem_beneficio(texto: str) -> bool:
    return "BENEFICIO" in ascii_upper(texto)


# =====================================================
# ESTADO -> UF (TRIBUNAIS / AJUDAS)
# =====================================================
ESTADO_PARA_UF: Dict[str, str] = {
    "ACRE": "AC",
    "ALAGOAS": "AL",
    "AMAPA": "AP",
    "AMAZONAS": "AM",
    "BAHIA": "BA",
    "CEARA": "CE",
    "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES",
    "GOIAS": "GO",
    "MARANHAO": "MA",
    "MATO GROSSO": "MT",
    "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG",
    "PARA": "PA",
    "PARAIBA": "PB",
    "PARANA": "PR",
    "PERNAMBUCO": "PE",
    "PIAUI": "PI",
    "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS",
    "RONDONIA": "RO",
    "RORAIMA": "RR",
    "SANTA CATARINA": "SC",
    "SAO PAULO": "SP",
    "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


def normalizar_token_uf(token: str) -> str:
    """
    Normaliza um token que pode representar UF/Estado.

    - "GOIAS" -> "GO"
    - "MINAS GERAIS" -> "MG"
    - "SP" -> "SP"
    """
    t = ascii_upper(token)
    if not t:
        return ""
    if t in ESTADO_PARA_UF:
        return ESTADO_PARA_UF[t]
    # se já é UF
    if re.fullmatch(r"[A-Z]{2}", t):
        return t
    return t


# =====================================================
# SANITIZAÇÃO DE PRODUTO (ANTI-IA DOIDA)
# =====================================================

# Palavras proibidas no produto_padronizado (sua lista oficial)
PALAVRAS_PROIBIDAS_PRODUTO: Set[str] = {
    "EMPRESTIMO",
    "EMPRÉSTIMO",
    "CARTAO",
    "CARTÃO",
    "REFIN",
    "PORT",
    "PORTAB",
    "PORTABILIDADE",
    "BRUTO",
    "LIQUIDO",
    "LÍQUIDO",
    "COMBO",
    "REFIN PORT",
    "CONSIGNADO",
    "PORT COMBO",
}

# variações comuns que podem aparecer como "segmentos" no meio
_SEGMENTOS_PROIBIDOS_EQUIVALENTES: Set[str] = {
    "REFIN-PORT",
    "REFIN/PORT",
    "PORT/REFIN",
    "REFIN PORT",
    "PORT COMBO",
    "REFIN PORTABILIDADE",
}


def limpar_separadores(s: str) -> str:
    """
    Normaliza separadores e espaços:
    - remove duplicidades de hífen
    - remove espaços extras
    """
    if not s:
        return ""
    s = ascii_upper(s)
    # normaliza separador " - "
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # remove " -  - "
    s = re.sub(r"(?:\s-\s){2,}", " - ", s).strip()
    # remove hífen no começo/fim
    s = re.sub(r"^\s*-\s*", "", s)
    s = re.sub(r"\s*-\s*$", "", s)
    return s.strip()


def sanitizar_produto_padronizado(produto: str) -> str:
    """
    Remove qualquer palavra/segmento proibido do produto_padronizado.

    Ex:
      "GOV. AC - PORT - 1,90%" -> "GOV. AC - 1,90%"
      "CARTAO BENEFICIO - CARTAO GOIAS - 4,50%" -> "BENEFICIO - GOIAS - 4,50%" (regra final vai corrigir no Servico)
    """
    if not produto:
        return ""

    s = limpar_separadores(produto)

    # separa por " - " (se não tiver, vira lista 1)
    partes = [p.strip() for p in s.split(" - ") if p.strip()]
    if not partes:
        return ""

    partes_limpas = []
    for p in partes:
        pu = ascii_upper(p)

        # remove match direto
        if pu in PALAVRAS_PROIBIDAS_PRODUTO:
            continue

        # remove equivalentes
        if pu in _SEGMENTOS_PROIBIDOS_EQUIVALENTES:
            continue

        # remove se a parte contém só palavra proibida + lixo
        if re.fullmatch(r"(EMPRESTIMO|EMPRÉSTIMO|CARTAO|CARTÃO|COMBO|PORT|PORTAB|PORTABILIDADE|REFIN|BRUTO|LIQUIDO|LÍQUIDO)", pu):
            continue

        partes_limpas.append(pu)

    out = " - ".join(partes_limpas)
    return limpar_separadores(out)


# =====================================================
# PREFEITURA: NORMALIZAÇÕES ESPECIAIS (PREF SP etc)
# =====================================================

# aliases de cidade que o banco costuma mandar errado / abreviado
_CIDADE_ALIASES: Dict[str, str] = {
    "SP": "SAO PAULO",
    "S P": "SAO PAULO",
    "S.P": "SAO PAULO",
    "S. P.": "SAO PAULO",
    "SAO PAULO": "SAO PAULO",
}


def normalizar_cidade_prefeitura(cidade: str) -> str:
    """
    Normaliza cidade para prefeitura.
    Ex:
      "SP" -> "SAO PAULO"
      "VITÓRIA" -> "VITORIA"
    """
    c = ascii_upper(cidade)
    c = c.replace(".", " ").strip()
    c = re.sub(r"\s+", " ", c).strip()

    if c in _CIDADE_ALIASES:
        return _CIDADE_ALIASES[c]

    # alguns bancos mandam "PREF SP" e o extractor pega "SP" ou "SP - ..."
    if c.startswith("SP "):
        return "SAO PAULO"

    return c


# =====================================================
# EXTRATORES (REGEX) - entradas do banco
# =====================================================

_RE_GOV_UF = re.compile(r"\bGOV[.\s-]*([A-Z]{2})\b")
_RE_COMBO = re.compile(r"\bCOMBO\b")
_RE_PORT_OU_REFIN = re.compile(r"\b(PORT|REFIN)\b")

_RE_PREF_EXPLICITA = re.compile(r"\bPREF[.]?\s+(.+?)(?:\s*-\s*|$)")
_RE_EMPRESTIMO_PREFIX = re.compile(r"^EMPR[ÉE]STIMO\s*-\s*", re.I)

_RE_PREF_CIDADE_PURA = re.compile(r"EMPR[ÉE]STIMO\s*-\s*([A-Z ]{2,}?)\s*-\s*\d", re.I)

_RE_SIGLA_CIDADE = re.compile(r"EMPR[ÉE]STIMO\s*-\s*([A-Z]{2,12})\s+([A-Z ]{3,}?)\s*-\s*\d", re.I)

_RE_INST_PREV_SUB = re.compile(r"INST\s+PREV\s+([A-Z ]+?)\s*-\s*([A-Z]{3,})\s*-\s*\d", re.I)
_RE_INST_PREV_GEN = re.compile(r"INST\s+PREV\s+(.+?)\s*-\s*\d", re.I)

_RE_TJ_ESTADO = re.compile(r"TJ\s*-\s*([A-Z ]{2,})", re.I)
_RE_TJ_UF = re.compile(r"\bTJ\s*-\s*([A-Z]{2})\b", re.I)


def extrair_gov_uf(texto: str) -> Optional[str]:
    t = ascii_upper(texto)
    m = _RE_GOV_UF.search(t)
    return m.group(1) if m else None


def extrair_derivado_gov_combo(texto: str, uf: str) -> str:
    """
    Entre 'GOV UF -' e '- PORT/REFIN'
    """
    t = ascii_upper(texto)
    m = re.search(rf"\bGOV[.\s-]*{uf}\b\s*-\s*(.+?)\s*-\s*(PORT|REFIN)\b", t)
    return m.group(1).strip() if m else ""


def extrair_pref_cidade_explicita(texto: str) -> str:
    """
    PREF CAIEIRAS - ...
    PREF. SAO JOSE DOS CAMPOS - ...
    PREF SP - ...
    """
    t = ascii_upper(texto)
    m = _RE_PREF_EXPLICITA.search(t)
    if not m:
        return ""
    cidade = m.group(1).strip()
    cidade = cidade.split(" - ")[0].strip()
    cidade = normalizar_cidade_prefeitura(cidade)
    return cidade


def extrair_cidade_pura(texto: str) -> str:
    """
    EMPRÉSTIMO - RIBEIRAO PRETO - 2.48%
    """
    t = ascii_upper(texto)
    m = _RE_PREF_CIDADE_PURA.search(t)
    return normalizar_cidade_prefeitura(m.group(1).strip()) if m else ""


def extrair_sigla_e_cidade(texto: str) -> Optional[Tuple[str, str]]:
    """
    EMPRÉSTIMO - SEPREM ITAPETININGA - 1.85%
    EMPRÉSTIMO - ISSM CAMACARI - 2.40%
    """
    t = ascii_upper(texto)
    m = _RE_SIGLA_CIDADE.search(t)
    if not m:
        return None
    sigla = m.group(1).strip()
    cidade = normalizar_cidade_prefeitura(m.group(2).strip())
    return sigla, cidade


def extrair_inst_prev_sub(texto: str):
    """
    Extrai cidade + subinstituto em casos como:
    INST PREV FORMIGA - PREVIFOR - 2,25%
    """
    m = re.search(
        r"INST\s+PREV\s+([A-Z\s]+?)\s*-\s*([A-Z0-9]+)\s*-",
        texto
    )
    if not m:
        return None

    cidade = m.group(1).strip()
    sub = m.group(2).strip()

    return cidade, sub


def extrair_inst_prev_gen(texto: str) -> str:
    """
    INST PREV GUARAPUAVA - 2.15%
    """
    t = ascii_upper(texto)
    m = _RE_INST_PREV_GEN.search(t)
    return normalizar_cidade_prefeitura(m.group(1).strip()) if m else ""


def extrair_tj_uf(texto: str) -> Optional[str]:
    """
    TJ - MG
    """
    t = ascii_upper(texto)
    m = _RE_TJ_UF.search(t)
    return m.group(1).strip() if m else None


def extrair_tj_estado(texto: str) -> str:
    """
    TJ - MINAS GERAIS
    """
    t = ascii_upper(texto)
    m = _RE_TJ_ESTADO.search(t)
    if not m:
        return ""
    estado = m.group(1).strip()
    estado = estado.split(" - ")[0].strip()
    return estado
