from __future__ import annotations

import re
from typing import Dict, Any, Optional

from .normalizacao import normalizar_texto, formatar_taxa, extrair_taxa
from .indexador_cache import IndexadorCache
from .modelos_padrao import SinaisExtraidos


_RE_TAXA = re.compile(r"\d{1,2}[.,]\d{2}\s*%?$")


class ValidadorSaida:
    """
    Última linha de defesa antes da escrita.
    Nunca cria padrão novo — apenas valida e corrige.
    """

    def validar(
        self,
        saida: Dict[str, Any],
        sinais: SinaisExtraidos,
        indexador: IndexadorCache,
        texto_raw: str,
    ) -> Dict[str, Any]:
        """
        Retorna a saída validada e segura.
        """

        produto = saida.get("produto_padronizado", "").strip()
        convenio = saida.get("convenio_padronizado", "").strip()

        # ----------------------------
        # 1) GARANTIR TAXA NO FINAL
        # ----------------------------
        taxa = extrair_taxa(produto)
        if taxa is None:
            taxa = extrair_taxa(texto_raw)

        if taxa is not None:
            taxa_fmt = formatar_taxa(taxa)
            if not produto.endswith(taxa_fmt):
                produto = self._forcar_taxa_final(produto, taxa_fmt)

        # ----------------------------
        # 2) REMOVER SUBPRODUTO INDEVIDO
        # ----------------------------
        if not sinais.subproduto:
            produto = self._remover_subproduto(produto)

        # ----------------------------
        # 3) FORÇAR CONVÊNIO OFICIAL (SE EXISTIR)
        # ----------------------------
        assinatura = indexador.convenio_por_assinatura(
            normalizar_texto(convenio)
        )
        if assinatura:
            convenio = assinatura

        # ----------------------------
        # 4) FORÇAR FAMÍLIA / GRUPO
        # ----------------------------
        familia, grupo = indexador.metadados(convenio)
        if familia:
            saida["familia_produto"] = familia
        if grupo:
            saida["grupo_convenio"] = grupo

        # ----------------------------
        # 5) ATUALIZA SAÍDA
        # ----------------------------
        saida["produto_padronizado"] = produto
        saida["convenio_padronizado"] = convenio

        return saida

    # ==============================
    # HELPERS
    # ==============================

    def _forcar_taxa_final(self, produto: str, taxa_fmt: str) -> str:
        """
        Remove qualquer taxa existente e adiciona a correta no final.
        """
        partes = produto.split("-")
        if partes and _RE_TAXA.search(partes[-1]):
            partes = partes[:-1]

        base = "-".join(p.strip() for p in partes if p.strip())
        return f"{base} - {taxa_fmt}"

    def _remover_subproduto(self, produto: str) -> str:
        """
        Remove subproduto quando ele não é explícito.
        Ex:
          "GOV. SP - SPPREV - 2,50%" -> "GOV. SP - 2,50%"
        """
        partes = [p.strip() for p in produto.split("-") if p.strip()]
        if len(partes) < 3:
            return produto

        # mantém primeiro bloco e taxa
        return f"{partes[0]} - {partes[-1]}"
