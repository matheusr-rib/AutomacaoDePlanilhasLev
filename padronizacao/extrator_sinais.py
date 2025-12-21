from __future__ import annotations

import json
from typing import Dict, Any, Optional

from .modelos_padrao import SinaisExtraidos, TipoInstitucional
from .normalizacao import normalizar_texto, normalizar_uf
from .motor_ia import MotorIA


# ==============================
# CONFIGURAÇÕES
# ==============================

TIPOS_PERMITIDOS: set[str] = {"GOV", "PREF", "TJ", "SIAPE", "OUTROS"}
LIMIAR_CONFIANCA_PADRAO = 0.65


# ==============================
# HELPERS DETERMINÍSTICOS
# ==============================

def _inferir_uf_do_nome(nome_base: str) -> Optional[str]:
    """
    Inferência determinística de UF a partir do nome do estado.
    Ex:
      "GOV TOCANTINS" -> "TO"
      "GOV SAO PAULO" -> "SP"

    NÃO usa IA
    NÃO inventa
    """
    if not nome_base:
        return None

    partes = normalizar_texto(nome_base).split()
    for p in partes:
        uf = normalizar_uf(p)
        if uf:
            return uf
    return None


# ==============================
# EXTRATOR PRINCIPAL
# ==============================

class ExtratorSinaisIA:
    """
    Extrai APENAS sinais estruturais do texto bruto.

    GARANTIAS:
    - IA NÃO escreve padrão
    - IA NÃO inventa UF ou subproduto
    - UF pode ser inferida por regra determinística (apenas GOV)
    """

    def __init__(self, motor_ia: Optional[MotorIA] = None):
        self.motor_ia = motor_ia or MotorIA()

    # ==============================
    # API PRINCIPAL
    # ==============================

    def extrair(self, entrada_raw: Dict[str, Any]) -> SinaisExtraidos:
        resposta, confianca = self._chamar_ia(entrada_raw)

        # ----------------------------
        # FALHA OU BAIXA CONFIANÇA
        # ----------------------------
        if not resposta or confianca < LIMIAR_CONFIANCA_PADRAO:
            return self._fallback_seguro(entrada_raw, confianca)

        # ----------------------------
        # VALIDAÇÃO E NORMALIZAÇÃO
        # ----------------------------
        tipo = self._validar_tipo(resposta.get("tipo"))
        nome_base = self._validar_nome_base(resposta.get("nome_base"), entrada_raw)
        uf = self._validar_uf(resposta.get("uf"))
        subproduto = self._validar_subproduto(resposta.get("subproduto"), entrada_raw)

        # ----------------------------
        # REGRA DE DOMÍNIO (CRÍTICA)
        # GOV pode inferir UF pelo nome do estado
        # ----------------------------
        if tipo == "GOV" and not uf:
            uf = _inferir_uf_do_nome(nome_base)

        return SinaisExtraidos(
            tipo=tipo,
            nome_base=nome_base,
            uf=uf,
            subproduto=subproduto,
            confianca=confianca,
        )

    # ==============================
    # CHAMADA IA
    # ==============================

    def _chamar_ia(self, entrada_raw: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], float]:
        system = (
            "Você é um EXTRATOR de informações.\n"
            "Você NÃO cria nomes finais.\n"
            "Você NÃO inventa dados.\n"
            "Se algo não estiver explícito no texto, retorne null.\n"
        )

        user = f"""
TEXTO ORIGINAL:
produto_raw: {entrada_raw.get("produto_raw")}
convenio_raw: {entrada_raw.get("convenio_raw")}

TAREFA:
Extraia APENAS os sinais abaixo.

TIPOS PERMITIDOS:
- GOV (governos estaduais)
- PREF (prefeituras / institutos municipais)
- TJ (tribunais)
- SIAPE (federal)
- OUTROS (autarquias, hospitais, etc.)

REGRAS CRÍTICAS:
- subproduto: SOMENTE se estiver explicitamente escrito.
- uf: SOMENTE se estiver explicitamente escrito.
- NÃO converta estado → UF.
- NÃO padronize texto.
- NÃO adivinhe.

FORMATO (JSON):
{{
  "status": "OK" | "AMBIGUO",
  "tipo": "GOV" | "PREF" | "TJ" | "SIAPE" | "OUTROS",
  "nome_base": "<texto base limpo>" | null,
  "uf": "<UF>" | null,
  "subproduto": "<texto>" | null,
  "confianca": 0.0
}}
"""

        try:
            resposta = self.motor_ia._call_json(system, user, temperature=0.0)
            status = str(resposta.get("status", "AMBIGUO")).upper()
            confianca = float(resposta.get("confianca", 0.0))

            if status != "OK":
                return None, confianca

            return resposta, confianca

        except Exception:
            return None, 0.0

    # ==============================
    # VALIDAÇÕES
    # ==============================

    def _validar_tipo(self, tipo: Any) -> TipoInstitucional:
        t = str(tipo).upper().strip() if tipo else "OUTROS"
        return t if t in TIPOS_PERMITIDOS else "OUTROS"  # type: ignore

    def _validar_nome_base(self, nome_base: Any, entrada_raw: Dict[str, Any]) -> str:
        if nome_base:
            nb = normalizar_texto(nome_base)
            if nb:
                return nb

        bruto = entrada_raw.get("convenio_raw") or entrada_raw.get("produto_raw") or ""
        return normalizar_texto(bruto)

    def _validar_uf(self, uf: Any) -> Optional[str]:
        if not uf:
            return None
        return normalizar_uf(str(uf))

    def _validar_subproduto(self, subproduto: Any, entrada_raw: Dict[str, Any]) -> Optional[str]:
        if not subproduto:
            return None

        sub = normalizar_texto(subproduto)
        if not sub:
            return None

        texto_raw = normalizar_texto(
            f"{entrada_raw.get('produto_raw', '')} {entrada_raw.get('convenio_raw', '')}"
        )

        # subproduto só passa se existir explicitamente no texto original
        if sub not in texto_raw:
            return None

        return sub

    # ==============================
    # FALLBACK SEGURO
    # ==============================

    def _fallback_seguro(self, entrada_raw: Dict[str, Any], confianca: float) -> SinaisExtraidos:
        texto = normalizar_texto(
            entrada_raw.get("convenio_raw") or entrada_raw.get("produto_raw") or ""
        )

        if texto.startswith("PREF"):
            tipo: TipoInstitucional = "PREF"
        elif texto.startswith("GOV"):
            tipo = "GOV"
        elif texto.startswith("TJ"):
            tipo = "TJ"
        elif "SIAPE" in texto:
            tipo = "SIAPE"
        else:
            tipo = "OUTROS"

        nome_base = texto
        uf = _inferir_uf_do_nome(nome_base) if tipo == "GOV" else None

        return SinaisExtraidos(
            tipo=tipo,
            nome_base=nome_base,
            uf=uf,
            subproduto=None,
            confianca=confianca or 0.0,
        )
