# padronizacao/resolvedor_por_regras.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple

from .normalizacao import normalizar_texto, split_segmentos, normalizar_uf
from .indice_cache_base import IndiceCacheBase


@dataclass
class EstruturaExtraida:
    tipo: str
    taxa: Optional[float]
    uf: Optional[str]
    cidade: Optional[str]
    nome_base: Optional[str]
    subproduto: Optional[str]
    assinatura: str
    produto_raw: str
    convenio_raw: str

    def to_contexto_curto(self) -> Dict[str, Any]:
        return {
            "tipo": self.tipo,
            "taxa": self.taxa,
            "uf": self.uf,
            "cidade": self.cidade,
            "nome_base": self.nome_base,
            "subproduto": self.subproduto,
            "assinatura": self.assinatura,
        }


class ResolvedorPorRegras:
    def extrair(self, entrada: Dict[str, Any]) -> EstruturaExtraida:
        produto_raw = str(entrada.get("produto_raw") or "")
        convenio_raw = str(entrada.get("convenio_raw") or "")

        segs, taxa = split_segmentos(produto_raw)

        if taxa is None:
            try:
                taxa_val = entrada.get("taxa_raw")
                if isinstance(taxa_val, str):
                    taxa = float(taxa_val.replace(",", "."))
                elif isinstance(taxa_val, (int, float)):
                    taxa = float(taxa_val)
            except Exception:
                taxa = None

        tipo = self._detectar_tipo(segs, convenio_raw)
        uf, cidade, nome_base, subproduto = self._extrair_componentes(tipo, segs, convenio_raw)
        assinatura = self._assinatura(tipo, uf=uf, cidade=cidade, nome_base=nome_base, convenio_raw=convenio_raw, segs=segs)

        return EstruturaExtraida(
            tipo=tipo,
            taxa=taxa,
            uf=uf,
            cidade=cidade,
            nome_base=nome_base,
            subproduto=subproduto,
            assinatura=assinatura,
            produto_raw=produto_raw,
            convenio_raw=convenio_raw,
        )

    def tentar_resolver_por_base(self, estrutura: EstruturaExtraida, indice: IndiceCacheBase) -> Optional[str]:
        if estrutura.assinatura:
            direto = indice.convenio_oficial_por_assinatura(estrutura.assinatura)
            if direto:
                return direto

        candidatos = indice.buscar_candidatos(estrutura.assinatura or "", tipo=estrutura.tipo, max_candidatos=1, limiar=0.75)
        if candidatos:
            return candidatos[0][0].convenio_oficial
        return None

    def _detectar_tipo(self, segs: List[str], convenio_raw: str) -> str:
        joined = " ".join(segs)
        c = normalizar_texto(convenio_raw)
        j = normalizar_texto(joined)

        if "SIAPE" in j or "SIAPE" in c:
            return "SIAPE"
        if j.startswith("TJ ") or j == "TJ" or c.startswith("TJ"):
            return "TJ"
        if "GOV" in j.split() or j.startswith("GOV ") or c.startswith("GOV"):
            return "GOV"
        if j.startswith("PREF") or "PREF" in j.split() or c.startswith("PREF"):
            return "PREF"
        return "OUTROS"

    def _extrair_componentes(self, tipo: str, segs: List[str], convenio_raw: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        uf = None
        cidade = None
        nome_base = None
        subproduto = None

        if tipo == "SIAPE":
            return None, None, "SIAPE", None

        if tipo == "TJ":
            uf = self._achar_uf(segs) or self._achar_uf([convenio_raw])
            return uf, None, None, None

        if tipo == "GOV":
            uf = self._achar_uf(segs) or self._achar_uf([convenio_raw])
            subproduto = self._extrair_subproduto(segs, uf)
            return uf, None, None, subproduto

        if tipo == "PREF":
            cidade, uf = self._extrair_cidade_uf_pref(segs, convenio_raw)
            subproduto = self._extrair_subproduto(segs, uf)
            return uf, cidade, None, subproduto

        uf = self._achar_uf(segs) or self._achar_uf([convenio_raw])
        if segs:
            base = segs[0]
            toks = base.split()
            if len(toks) >= 2 and normalizar_uf(toks[-1]):
                uf = uf or normalizar_uf(toks[-1])
                base = " ".join(toks[:-1])
            nome_base = base.strip() or None
        return uf, None, nome_base, None

    def _assinatura(self, tipo: str, uf: Optional[str], cidade: Optional[str], nome_base: Optional[str], convenio_raw: str, segs: List[str]) -> str:
        if tipo == "SIAPE":
            return "SIAPE"
        if tipo == "TJ":
            return f"TJ {uf}" if uf else "TJ"
        if tipo == "GOV":
            return f"GOV {uf}" if uf else "GOV"
        if tipo == "PREF":
            if cidade and uf:
                return f"PREF {cidade} {uf}"
            if cidade:
                return f"PREF {cidade}"
            c = normalizar_texto(convenio_raw)
            return c or "PREF"
        if nome_base and uf:
            return f"{nome_base} {uf}"
        return nome_base or (segs[0] if segs else "")

    def _achar_uf(self, textos: List[str]) -> Optional[str]:
        for t in textos:
            s = normalizar_texto(t)
            toks = s.split()
            if toks:
                uf = normalizar_uf(toks[-1])
                if uf:
                    return uf
            for tok in toks:
                uf = normalizar_uf(tok)
                if uf:
                    return uf
        return None

    def _extrair_subproduto(self, segs: List[str], uf: Optional[str]) -> Optional[str]:
        if len(segs) < 2:
            return None
        cand = " ".join(segs[1:]).strip()
        cand_norm = normalizar_texto(cand)
        if uf and cand_norm == uf:
            return None
        toks = cand_norm.split()
        if not toks:
            return None
        if len(toks) == 1 and len(toks[0]) < 4:
            return None
        return cand_norm

    def _extrair_cidade_uf_pref(self, segs: List[str], convenio_raw: str) -> Tuple[Optional[str], Optional[str]]:
        c = normalizar_texto(convenio_raw)
        if c.startswith("PREF"):
            toks = c.split()
            uf = normalizar_uf(toks[-1]) if toks else None
            if uf:
                cidade = " ".join(toks[1:-1]).strip() or None
                return cidade, uf
            cidade = " ".join(toks[1:]).strip() or None
            return cidade, None

        pref_seg = next((s for s in segs if s.startswith("PREF")), None)
        if pref_seg:
            toks = normalizar_texto(pref_seg).split()
            uf = normalizar_uf(toks[-1]) if toks else None
            if uf:
                cidade = " ".join(toks[1:-1]).strip() or None
                return cidade, uf
            cidade = " ".join(toks[1:]).strip() or None
            return cidade, None

        if segs:
            t = segs[0].split()
            uf = normalizar_uf(t[-1]) if t else None
            if uf:
                cidade = " ".join(t[:-1]).strip() or None
                return cidade, uf
            return normalizar_texto(segs[0]), None

        return None, None
