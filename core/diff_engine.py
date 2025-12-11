from typing import List, Dict, Tuple
from .modelos import CanonicalItem, DiffAction, TipoAcao
from .chave_identidade import chave_hope


class DiffEngine:
    """
    Compara itens internos x itens do banco e gera ações:
    - ABRIR (novo)
    - FECHAR (obsoleto)
    - FECHAR+ABRIR (alterou campos relevantes)
    """

    def diff(self, itens_internos: List[CanonicalItem], itens_banco: List[CanonicalItem]) -> List[DiffAction]:
        mapa_interno: Dict[Tuple, CanonicalItem] = {chave_hope(i): i for i in itens_internos}
        mapa_banco: Dict[Tuple, CanonicalItem] = {chave_hope(i): i for i in itens_banco}

        acoes: List[DiffAction] = []

        chaves_todas = set(mapa_interno.keys()) | set(mapa_banco.keys())

        for chave in chaves_todas:
            interno = mapa_interno.get(chave)
            banco = mapa_banco.get(chave)

            # existe só no interno → FECHAR
            if interno and not banco:
                acoes.append(
                    DiffAction(
                        tipo=TipoAcao.FECHAR,
                        item_interno=interno,
                        item_banco=None,
                        motivo="Registro presente apenas na planilha interna.",
                    )
                )
                continue

            # existe só no banco → ABRIR
            if banco and not interno:
                acoes.append(
                    DiffAction(
                        tipo=TipoAcao.ABRIR,
                        item_interno=None,
                        item_banco=banco,
                        motivo="Registro novo presente apenas no banco.",
                    )
                )
                continue

            # existe nos dois → checar alterações
            if interno and banco and self._houve_alteracao_relevante(interno, banco):
                acoes.append(
                    DiffAction(
                        tipo=TipoAcao.FECHAR_ABRIR,
                        item_interno=interno,
                        item_banco=banco,
                        motivo="Campos relevantes alterados (id tabela banco, comissão ou parc. atual).",
                    )
                )

        return acoes

    def _houve_alteracao_relevante(self, interno: CanonicalItem, banco: CanonicalItem) -> bool:
        """
        Regras HOPE: se mudou algum desses -> FECHAR+ABRIR:
        - id_tabela_banco
        - comissao_pct
        - parc_atual
        """
        if (interno.id_tabela_banco or "") != (banco.id_tabela_banco or ""):
            return True

        if round(interno.comissao_pct or 0.0, 4) != round(banco.comissao_pct or 0.0, 4):
            return True

        if (interno.parc_atual or "") != (banco.parc_atual or ""):
            return True

        return False
