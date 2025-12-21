# padronizacao/indice_cache_base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple, Set, Iterable, DefaultDict
from collections import defaultdict

from .dicionario_cache import DicionarioCache
from .normalizacao import normalizar_texto, tokens as tokset, jaccard


@dataclass(frozen=True)
class CandidatoConvenio:
    convenio_oficial: str
    assinatura: str
    tipo: str
    familia: str
    grupo: str


class IndiceCacheBase:
    """
    Índices derivados do cache manual (interno).
    - NÃO altera o cache
    - Serve pra: achar convênio oficial por similaridade e puxar familia/grupo oficiais
    """

    def __init__(self):
        self._convenio_por_assinatura: Dict[str, str] = {}
        self._metadados_por_convenio: Dict[str, Dict[str, str]] = {}
        self._candidatos_por_tipo: DefaultDict[str, List[CandidatoConvenio]] = defaultdict(list)
        self._subprodutos_por_convenio: DefaultDict[str, Set[str]] = defaultdict(set)

    @classmethod
    def construir(cls, cache: DicionarioCache) -> "IndiceCacheBase":
        idx = cls()

        for _chave, item in cache._cache.items():  # leitura apenas
            if not isinstance(item, dict):
                continue

            convenio = (item.get("convenio_padronizado") or "").strip()
            familia = (item.get("familia_produto") or "").strip()
            grupo = (item.get("grupo_convenio") or "").strip()
            produto = (item.get("produto_padronizado") or "").strip()

            if not convenio:
                continue

            assinatura = cls.assinatura_convenio(convenio)
            idx._convenio_por_assinatura.setdefault(assinatura, convenio)

            if familia and grupo:
                idx._metadados_por_convenio.setdefault(convenio, {"familia": familia, "grupo": grupo})

            tipo = cls.tipo_convenio(convenio, familia, grupo, produto)
            idx._candidatos_por_tipo[tipo].append(
                CandidatoConvenio(convenio_oficial=convenio, assinatura=assinatura, tipo=tipo, familia=familia, grupo=grupo)
            )

            sub = cls._extrair_subproduto_de_produto(produto, tipo)
            if sub:
                idx._subprodutos_por_convenio[convenio].add(sub)

        return idx

    def convenio_oficial_por_assinatura(self, assinatura: str) -> Optional[str]:
        return self._convenio_por_assinatura.get(normalizar_texto(assinatura))

    def metadados(self, convenio_oficial: str) -> Optional[Dict[str, str]]:
        return self._metadados_por_convenio.get(convenio_oficial)

    def subprodutos_conhecidos(self, convenio_oficial: str) -> Set[str]:
        return set(self._subprodutos_por_convenio.get(convenio_oficial, set()))

    def buscar_candidatos(
        self,
        assinatura_alvo: str,
        tipo: Optional[str] = None,
        max_candidatos: int = 10,
        limiar: float = 0.45,
    ) -> List[Tuple[CandidatoConvenio, float]]:
        assinatura_alvo = normalizar_texto(assinatura_alvo)
        alvo_tokens = tokset(assinatura_alvo)

        if tipo:
            candidatos: Iterable[CandidatoConvenio] = self._candidatos_por_tipo.get(tipo, [])
        else:
            candidatos = [c for lst in self._candidatos_por_tipo.values() for c in lst]

        scored: List[Tuple[CandidatoConvenio, float]] = []
        for c in candidatos:
            score = jaccard(alvo_tokens, tokset(c.assinatura))
            if score >= limiar:
                scored.append((c, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_candidatos]

    @staticmethod
    def assinatura_convenio(convenio_oficial: str) -> str:
        t = normalizar_texto(convenio_oficial)
        t = t.replace("GOV-", "GOV ")
        t = t.replace("|", " ")
        t = " ".join(t.split())
        return t

    @staticmethod
    def tipo_convenio(convenio: str, familia: str, grupo: str, produto: str) -> str:
        c = normalizar_texto(convenio)
        f = normalizar_texto(familia)
        g = normalizar_texto(grupo)

        if c == "SIAPE" or "SIAPE" in c:
            return "SIAPE"
        if c.startswith("TJ"):
            return "TJ"
        if c.startswith("GOV"):
            return "GOV"
        if c.startswith("PREF"):
            return "PREF"

        if f == "PREFEITURAS" or g == "PREFEITURAS":
            return "PREF"
        if f == "GOVERNOS" or g == "ESTADUAL":
            return "GOV"
        if f == "TRIBUNAIS" or g == "TRIBUNAIS":
            return "TJ"
        if f == "FEDERAL" or g == "FEDERAL":
            return "SIAPE"

        return "OUTROS"

    @staticmethod
    def _extrair_subproduto_de_produto(produto_padronizado: str, tipo: str) -> Optional[str]:
        if not produto_padronizado:
            return None

        if tipo == "GOV":
            # GOV. SP - SPPREV - 2,50%
            if " - " in produto_padronizado:
                partes = [p.strip() for p in produto_padronizado.split("-") if p.strip()]
                if len(partes) >= 3:
                    return normalizar_texto(partes[-2]) or None
        return None
