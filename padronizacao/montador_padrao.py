from __future__ import annotations

from typing import Dict, Any, Optional

from .modelos_padrao import SinaisExtraidos
from .indexador_cache import IndexadorCache
from .normalizacao import normalizar_texto, formatar_taxa


# ==============================
# MAPA OFICIAL DE FAMÍLIA / GRUPO
# ==============================

FAMILIA_GRUPO_POR_TIPO = {
    "GOV": ("GOVERNOS", "ESTADUAL"),
    "PREF": ("PREFEITURAS", "PREFEITURAS"),
    "TJ": ("TRIBUNAIS", "TRIBUNAIS"),
    "SIAPE": ("FEDERAL", "FEDERAL"),
    "OUTROS": ("OUTROS", "OUTROS"),
}


class MontadorPadrao:
    """
    Responsável por escrever o padrão FINAL.
    Nenhuma IA escreve texto aqui.
    """

    # ----------------------------
    # API PRINCIPAL
    # ----------------------------
    def montar(
        self,
        sinais: SinaisExtraidos,
        taxa: float,
        indexador: IndexadorCache,
        convenio_oficial: Optional[str],
        texto_raw: str,
    ) -> Dict[str, Any]:
        """
        Monta a saída padronizada final.
        """

        taxa_fmt = formatar_taxa(taxa)
        tipo = sinais.tipo

        # 1) Define convênio final
        convenio_final = self._definir_convenio(
            sinais=sinais,
            indexador=indexador,
            convenio_oficial=convenio_oficial,
        )

        # 2) Define prefixo de produto (sem taxa)
        prefixo_produto = self._definir_prefixo_produto(
            sinais=sinais,
            convenio=convenio_final,
            indexador=indexador,
            texto_raw=texto_raw,
        )

        # 3) Monta produto final
        produto_final = f"{prefixo_produto} - {taxa_fmt}"

        # 4) Define família / grupo
        familia, grupo = self._definir_familia_grupo(
            tipo=tipo,
            convenio=convenio_final,
            indexador=indexador,
        )

        return {
            "produto_padronizado": produto_final,
            "convenio_padronizado": convenio_final,
            "familia_produto": familia,
            "grupo_convenio": grupo,
        }

    # ----------------------------
    # CONVÊNIO
    # ----------------------------
    def _definir_convenio(
        self,
        sinais: SinaisExtraidos,
        indexador: IndexadorCache,
        convenio_oficial: Optional[str],
    ) -> str:
        """
        Define o convênio final:
        - se houver convênio oficial do cache → usa
        - senão → cria convênio organizado por regra
        """

        if convenio_oficial:
            return convenio_oficial

        tipo = sinais.tipo
        uf = sinais.uf
        base = sinais.nome_base

        if tipo == "GOV" and uf:
            return f"GOV-{uf}"

        if tipo == "PREF":
            # PREFEITURAS SEMPRE TÊM CIDADE
            cidade = base.replace("PREF", "").strip()
            if uf:
                return f"PREF. {cidade} {uf}"
            return f"PREF. {cidade}"

        if tipo == "TJ" and uf:
            return f"TJ | {uf}"

        if tipo == "SIAPE":
            return "SIAPE"

        # OUTROS
        if uf:
            return f"{base} - {uf}"
        return base

    # ----------------------------
    # PREFIXO DO PRODUTO
    # ----------------------------
    def _definir_prefixo_produto(
        self,
        sinais: SinaisExtraidos,
        convenio: str,
        indexador: IndexadorCache,
        texto_raw: str,
    ) -> str:
        """
        Define o prefixo do produto (SEM taxa).
        """
        # 1) Tenta usar prefixo existente do cache
        prefixo_cache = indexador.melhor_prefixo_produto(
            convenio=convenio,
            texto_raw=texto_raw,
            subproduto=sinais.subproduto,
        )

        if prefixo_cache:
            return prefixo_cache

        # 2) Montagem determinística por regra
        tipo = sinais.tipo
        uf = sinais.uf
        base = sinais.nome_base
        sub = sinais.subproduto

        if tipo == "GOV":
            if sub:
                return f"GOV. {uf} - {sub}"
            return f"GOV. {uf}"

        if tipo == "PREF":
            cidade = base.replace("PREF", "").strip()
            if sub:
                return f"PREF {cidade} - {sub}"
            return f"PREF {cidade}"

        if tipo == "TJ":
            return f"TJ - {uf}"

        if tipo == "SIAPE":
            return "SIAPE"

        # OUTROS
        if uf:
            return f"{base} - {uf}"
        return base

    # ----------------------------
    # FAMÍLIA / GRUPO
    # ----------------------------
    def _definir_familia_grupo(
        self,
        tipo: str,
        convenio: str,
        indexador: IndexadorCache,
    ) -> tuple[str, str]:
        """
        Família / grupo:
        - se existir no cache → força
        - senão → usa regra por tipo
        """
        familia, grupo = indexador.metadados(convenio)

        if familia and grupo:
            return familia, grupo

        return FAMILIA_GRUPO_POR_TIPO.get(tipo, ("OUTROS", "OUTROS"))
