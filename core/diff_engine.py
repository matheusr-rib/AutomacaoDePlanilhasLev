from typing import List, Dict, Tuple
from .modelos import CanonicalItem, DiffAction, TipoAcao
from .chave_identidade import chave_hope
from core.utils import normalizar_parc_atual


class DiffEngine:
    def diff(self, itens_internos: List[CanonicalItem], itens_banco: List[CanonicalItem]) -> List[DiffAction]:
        mapa_interno: Dict[Tuple, CanonicalItem] = {chave_hope(i): i for i in itens_internos}
        mapa_banco: Dict[Tuple, CanonicalItem] = {chave_hope(i): i for i in itens_banco}

        acoes: List[DiffAction] = []
        chaves_todas = set(mapa_interno.keys()) | set(mapa_banco.keys())

        for chave in chaves_todas:
            interno = mapa_interno.get(chave)
            banco = mapa_banco.get(chave)

            if interno and not banco:
                acoes.append(DiffAction(TipoAcao.FECHAR, interno, None, "Registro presente apenas na planilha interna."))
                continue

            if banco and not interno:
                acoes.append(DiffAction(TipoAcao.ABRIR, None, banco, "Registro novo presente apenas no banco."))
                continue

            if interno and banco and self._houve_alteracao_relevante(interno, banco):
                acoes.append(DiffAction(TipoAcao.FECHAR_ABRIR, interno, banco,
                                       "Campos relevantes alterados (id tabela banco, comissão ou parc. atual)."))

        return acoes

    def _houve_alteracao_relevante(self, interno: CanonicalItem, banco: CanonicalItem) -> bool:
        if (interno.id_tabela_banco or "") != (banco.id_tabela_banco or ""):
            return True

        if round(interno.comissao_pct or 0.0, 4) != round(banco.comissao_pct or 0.0, 4):
            return True

        # ✅ aqui é o seu bug principal
        parc_i = normalizar_parc_atual(interno.parc_atual)
        parc_b = normalizar_parc_atual(banco.parc_atual)
        if parc_i != parc_b:
            return True

        return False
