from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional, List, Tuple

from openai import OpenAI


class MotorIA:
    """
    Motor de IA em modo SEGURO.

    Regras:
    - A IA NÃO escreve textos finais padronizados
    - A IA NÃO inventa convenções
    - A IA NÃO altera cache
    - A IA apenas:
        (A) extrai sinais estruturais
        (B) escolhe UMA opção dentre convênios oficiais do cache
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: int = 30,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.timeout = timeout

    # ==========================================================
    # CHAMADA BASE (JSON PURO)
    # ==========================================================
    def _call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Chamada base da IA.
        Sempre espera JSON válido.
        """
        resposta = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=self.timeout,
        )

        conteudo = resposta.choices[0].message.content or ""
        return json.loads(conteudo)

    # ==========================================================
    # MODO A — SELEÇÃO GUIADA
    # ==========================================================
    def sugerir_selecao_guiada(
        self,
        entrada: Dict[str, Any],
        opcoes_convenio: List[str],
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], float]:
        """
        A IA escolhe UMA opção da lista de convênios oficiais.
        Não pode inventar texto.
        """

        contexto = contexto or {}
        opcoes = opcoes_convenio[:15]

        opcoes_txt = "\n".join(
            [f"{i+1}) {op}" for i, op in enumerate(opcoes)]
        )

        system = (
            "Você é um classificador extremamente rigoroso.\n"
            "Você NÃO cria texto.\n"
            "Você NÃO inventa nomes.\n"
            "Você APENAS escolhe uma opção existente.\n"
            "Se não tiver certeza, responda AMBIGUO."
        )

        user = f"""
DADOS DE ENTRADA:
produto_raw: {entrada.get("produto_raw")}
convenio_raw: {entrada.get("convenio_raw")}

CONTEXTO ESTRUTURAL:
{json.dumps(contexto, ensure_ascii=False)}

OPÇÕES OFICIAIS (escolha exatamente UMA):
{opcoes_txt}

REGRAS CRÍTICAS:
- opcao_escolhida deve ser IDÊNTICA a uma das opções.
- NÃO invente UF.
- NÃO invente subproduto.
- subproduto só pode existir se estiver explicitamente no texto original.

FORMATO (JSON):
{{
  "status": "OK" | "AMBIGUO",
  "opcao_escolhida": "<uma das opções>" | null,
  "subproduto": "<texto>" | null,
  "confianca": 0.0
}}
"""

        try:
            resposta = self._call_json(system, user, temperature=0.0)

            status = str(resposta.get("status", "AMBIGUO")).upper()
            opcao = resposta.get("opcao_escolhida")
            opcao = str(opcao).strip() if opcao else None
            sub = resposta.get("subproduto")
            sub = str(sub).strip() if sub else None
            confianca = float(resposta.get("confianca", 0.0))

            if status != "OK":
                return {"status": "AMBIGUO"}, 0.0

            if opcao not in opcoes:
                return {"status": "AMBIGUO"}, 0.0

            confianca = max(0.0, min(1.0, confianca))

            return {
                "status": "OK",
                "opcao_escolhida": opcao,
                "subproduto": sub,
            }, confianca

        except Exception:
            # IA nunca pode quebrar pipeline
            return {"status": "AMBIGUO"}, 0.0

    # ==========================================================
    # MODO B — EXTRAÇÃO ESTRUTURAL
    # ==========================================================
    def sugerir_estrutura(
        self,
        entrada: Dict[str, Any],
        contexto: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], float]:
        """
        A IA extrai APENAS estrutura.
        Não escreve padrão.
        """

        contexto = contexto or {}

        system = (
            "Você é um extrator de informações.\n"
            "Você NÃO cria texto final.\n"
            "Você NÃO inventa valores.\n"
            "Se algo não estiver explícito, retorne null."
        )

        user = f"""
TEXTO ORIGINAL:
produto_raw: {entrada.get("produto_raw")}
convenio_raw: {entrada.get("convenio_raw")}

CONTEXTO PRÉ-EXTRAÍDO:
{json.dumps(contexto, ensure_ascii=False)}

TIPOS PERMITIDOS:
- GOV
- PREF
- TJ
- SIAPE
- OUTROS

REGRAS CRÍTICAS:
- subproduto SOMENTE se estiver explicitamente escrito.
- uf SOMENTE se estiver explicitamente escrito.
- NÃO invente siglas.
- NÃO padronize texto.

FORMATO (JSON):
{{
  "status": "OK" | "AMBIGUO",
  "tipo": "GOV" | "PREF" | "TJ" | "SIAPE" | "OUTROS",
  "nome_base": "<texto base>" | null,
  "uf": "<UF>" | null,
  "subproduto": "<texto>" | null,
  "confianca": 0.0
}}
"""

        try:
            resposta = self._call_json(system, user, temperature=0.0)

            status = str(resposta.get("status", "AMBIGUO")).upper()
            confianca = float(resposta.get("confianca", 0.0))

            if status != "OK":
                return {}, 0.0

            return {
                "tipo": resposta.get("tipo"),
                "nome_base": resposta.get("nome_base"),
                "uf": resposta.get("uf"),
                "subproduto": resposta.get("subproduto"),
            }, max(0.0, min(1.0, confianca))

        except Exception:
            return {}, 0.0
