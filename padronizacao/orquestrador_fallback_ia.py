# padronizacao/orquestrador_fallback_ia.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Literal

from .resolvedor_por_regras import EstruturaExtraida
from .indice_cache_base import IndiceCacheBase

ModoOrquestrador = Literal["SEM_IA", "IA_SELECAO_GUIADA", "IA_ESTRUTURAL"]
LIMIAR_SELECAO = 0.75


@dataclass
class DecisaoOrquestrador:
    modo: ModoOrquestrador
    candidatos: Optional[List[str]] = None
    motivo: str = ""


class OrquestradorFallbackIA:
    def decidir(self, estrutura: EstruturaExtraida, indice: IndiceCacheBase) -> DecisaoOrquestrador:
        assinatura = estrutura.assinatura or ""
        tipo = estrutura.tipo

        direto = indice.convenio_oficial_por_assinatura(assinatura)
        if direto:
            return DecisaoOrquestrador(modo="SEM_IA", motivo="MATCH_DIRETO_ASSINATURA")

        cand_scored = indice.buscar_candidatos(assinatura, tipo=tipo, max_candidatos=10, limiar=0.45)
        if cand_scored:
            top_score = cand_scored[0][1]
            if top_score >= LIMIAR_SELECAO and len(cand_scored) == 1:
                return DecisaoOrquestrador(modo="SEM_IA", motivo=f"CANDIDATO_UNICO_SCORE_{top_score:.2f}")

            candidatos = [c.convenio_oficial for c, _ in cand_scored]
            return DecisaoOrquestrador(modo="IA_SELECAO_GUIADA", candidatos=candidatos, motivo=f"{len(candidatos)}_CANDIDATOS")

        return DecisaoOrquestrador(modo="IA_ESTRUTURAL", motivo="SEM_BASE_NO_CACHE")
