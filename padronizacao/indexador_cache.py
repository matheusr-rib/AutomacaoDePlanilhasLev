from __future__ import annotations

import re
from dataclasses import dataclass
from collections import defaultdict, Counter
from typing import Dict, Any, Optional, List, Tuple

from .normalizacao import normalizar_texto, tokens as tokset, jaccard
from .dicionario_cache import DicionarioCache
from .modelos_padrao import SinaisExtraidos


# Remove taxa final do produto padronizado do cache:
# "ALGUMA COISA - 2,10%" ou "ALGUMA COISA - 2.10%"
_RE_TAXA_FINAL = re.compile(r"\s*-\s*\d{1,2}[.,]\d{2}\s*%?\s*$")


@dataclass(frozen=True)
class CandidatoConvenio:
    convenio_oficial: str
    assinatura: str
    tipo: str
    score: float


class IndexadorCache:
    """
    Indexa o dicionário manual (cache interno) para:

    1) Resolver convênio oficial por similaridade (assinatura)
    2) Resolver o MELHOR prefixo de produto para um convênio (produto sem taxa)
       - evita variação e grafia errada
       - evita vazamento de subproduto
       - respeita padrões já existentes no cache

    IMPORTANTE:
    - somente leitura do cache
    - nada que vier da IA entra no cache
    """

    def __init__(self, cache: DicionarioCache):
        self.cache = cache

        # assinatura (normalizada) -> convenio_oficial
        self._convenio_por_assinatura: Dict[str, str] = {}

        # convenio_oficial -> (familia, grupo)
        self._meta_por_convenio: Dict[str, Tuple[str, str]] = {}

        # convenio_oficial -> Counter(prefixo_produto_sem_taxa)
        self._prefixos_por_convenio: Dict[str, Counter[str]] = {}

        # tipo -> lista de (assinatura, convenio)
        self._assinaturas_por_tipo: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    # ----------------------------
    # BUILD
    # ----------------------------
    @classmethod
    def construir(cls, cache: DicionarioCache) -> "IndexadorCache":
        idx = cls(cache)

        for _, item in cache._cache.items():  # leitura
            if not isinstance(item, dict):
                continue

            convenio = (item.get("convenio_padronizado") or "").strip()
            produto = (item.get("produto_padronizado") or "").strip()
            familia = (item.get("familia_produto") or "").strip()
            grupo = (item.get("grupo_convenio") or "").strip()

            if not convenio:
                continue

            tipo = cls._tipo_por_convenio(convenio)

            assinatura = cls._assinatura_convenio(convenio)
            if assinatura and assinatura not in idx._convenio_por_assinatura:
                idx._convenio_por_assinatura[assinatura] = convenio

            if familia or grupo:
                idx._meta_por_convenio.setdefault(convenio, (familia, grupo))

            idx._assinaturas_por_tipo[tipo].append((assinatura, convenio))

            prefixo = cls._prefixo_produto_sem_taxa(produto)
            if prefixo:
                if convenio not in idx._prefixos_por_convenio:
                    idx._prefixos_por_convenio[convenio] = Counter()
                idx._prefixos_por_convenio[convenio][prefixo] += 1

        return idx

    # ----------------------------
    # MATCH CONVÊNIO
    # ----------------------------
    def match_convenio(
        self,
        sinais: SinaisExtraidos,
        assinatura_alvo: str,
        max_candidatos: int = 10,
        limiar: float = 0.45,
    ) -> List[CandidatoConvenio]:
        """
        Retorna candidatos de convênio por similaridade.
        - não decide sozinho, só ranqueia
        """
        assinatura_alvo = normalizar_texto(assinatura_alvo)
        alvo_tokens = tokset(assinatura_alvo)

        tipo = sinais.tipo
        candidatos_base = self._assinaturas_por_tipo.get(tipo, [])
        if not candidatos_base:
            # fallback: busca em todos os tipos se não houver lista daquele tipo
            candidatos_base = [x for lst in self._assinaturas_por_tipo.values() for x in lst]

        scored: List[CandidatoConvenio] = []
        for assinatura, convenio in candidatos_base:
            score = jaccard(alvo_tokens, tokset(assinatura))
            if score >= limiar:
                scored.append(CandidatoConvenio(convenio, assinatura, tipo, score))

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:max_candidatos]

    def convenio_por_assinatura(self, assinatura: str) -> Optional[str]:
        return self._convenio_por_assinatura.get(normalizar_texto(assinatura))

    # ----------------------------
    # METADADOS
    # ----------------------------
    def metadados(self, convenio: str) -> Tuple[str, str]:
        return self._meta_por_convenio.get(convenio, ("", ""))

    # ----------------------------
    # ESCOLHA DO PREFIXO DO PRODUTO
    # ----------------------------
    def melhor_prefixo_produto(
        self,
        convenio: str,
        texto_raw: str,
        subproduto: Optional[str],
    ) -> Optional[str]:
        """
        Escolhe o melhor prefixo (produto sem taxa) para aquele convênio.

        Estratégia:
        1) pega top prefixos mais comuns no cache (por convênio)
        2) se houver subproduto explícito, só considera prefixos compatíveis com ele
        3) escolhe o prefixo com maior overlap de tokens com texto_raw
           (se empatar: mais frequente)
        """
        prefixos = self._prefixos_por_convenio.get(convenio)
        if not prefixos:
            return None

        raw_norm = normalizar_texto(texto_raw)
        raw_tokens = tokset(raw_norm)

        sub = normalizar_texto(subproduto) if subproduto else None

        # pega top N prefixos mais frequentes (para performance)
        top = prefixos.most_common(20)

        # filtro anti-vazamento de subproduto:
        # - se o prefixo contém algo que parece subproduto (ex.: GOV. SP - SPPREV),
        #   só aceita se o subproduto estiver explícito no raw.
        candidatos_filtrados: List[Tuple[str, int]] = []
        for pref, freq in top:
            pref_norm = normalizar_texto(pref)

            if self._prefixo_contem_subproduto(pref_norm):
                if not sub:
                    continue
                if sub not in pref_norm and sub not in raw_norm:
                    continue

            # se subproduto explícito foi detectado, preferir prefixos que o contenham
            if sub and sub in raw_norm:
                # não obriga, mas deixa passar; a pontuação vai favorecer quem casa mais
                pass

            candidatos_filtrados.append((pref, freq))

        if not candidatos_filtrados:
            # se filtrou tudo, volta pro mais frequente puro (último recurso)
            return top[0][0] if top else None

        # score por overlap (Jaccard) entre tokens do raw e tokens do prefixo
        melhor_pref = None
        melhor_score = -1.0
        melhor_freq = -1

        for pref, freq in candidatos_filtrados:
            pref_tokens = tokset(pref)
            score = jaccard(raw_tokens, pref_tokens)

            if score > melhor_score:
                melhor_score, melhor_freq, melhor_pref = score, freq, pref
            elif score == melhor_score and freq > melhor_freq:
                melhor_freq, melhor_pref = freq, pref

        return melhor_pref

    # ----------------------------
    # HELPERS
    # ----------------------------
    @staticmethod
    def _tipo_por_convenio(convenio: str) -> str:
        c = normalizar_texto(convenio)
        if c == "SIAPE":
            return "SIAPE"
        if c.startswith("TJ"):
            return "TJ"
        if c.startswith("GOV-"):
            return "GOV"
        if c.startswith("PREF."):
            return "PREF"
        return "OUTROS"

    @staticmethod
    def _assinatura_convenio(convenio: str) -> str:
        """
        Normaliza convênio para "assinatura" comparável.
        Ex:
          "GOV-SP" -> "GOV SP"
          "TJ | SP" -> "TJ SP"
          "PREF. SAO PAULO SP" -> "PREF SAO PAULO SP"
        """
        c = normalizar_texto(convenio)
        c = c.replace("GOV-", "GOV ")
        c = c.replace("|", " ")
        c = c.replace(".", " ")
        c = " ".join(c.split())
        return c

    @staticmethod
    def _prefixo_produto_sem_taxa(produto_padronizado: str) -> str:
        """
        Remove taxa do final e normaliza espaços.
        """
        if not produto_padronizado:
            return ""
        p = produto_padronizado.strip()
        p = _RE_TAXA_FINAL.sub("", p).strip()
        p = re.sub(r"\s+", " ", p).strip()
        return p

    @staticmethod
    def _prefixo_contem_subproduto(prefixo_norm: str) -> bool:
        """
        Heurística segura: se tem 2 ou mais blocos separados por '-' no prefixo,
        provavelmente contém subproduto.
        Ex:
          "GOV. SP - SPPREV"
          "PREF UBERLANDIA - DEMAE"
        """
        # normaliza separadores
        p = prefixo_norm.replace("—", "-").replace("–", "-")
        return p.count("-") >= 1 and len(p.split("-")) >= 2
