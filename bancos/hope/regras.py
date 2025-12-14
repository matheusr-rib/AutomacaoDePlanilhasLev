# bancos/hope/regras.py

from datetime import date, timedelta
from typing import Dict, Any, Tuple

from core.modelos import CanonicalItem
from bancos.hope.colunas_extras import COLUNAS_EXTRAS_HOPE


COLUNAS_COMUNS = [
    "ID",
    "Instituição",
    "Produto",
    "Família Produto",
    "Grupo Convênio",
    "Convênio",
    "Operação",
    "Parc. Atual",
    "Parc. Refin.",
    "% PMT Pagas",
    "% Taxa",
    "Idade",
    "% Comissão",
    "-",
    "Base Comissão",
    "% Mínima",
    "% Intermediária",
    "% Máxima",
    "% Fator",
    "% TAC",
    "Val. Teto TAC",
    "Faixa Val. Contrato",
    "Faixa Val. Seguro",
    "Vigência",
    "Término",
    "Complemento",
    "Venda Digital",
    "Visualização Restrita",
    "Val. Base Produção",
    "Id Tabela Banco",
]

COLUNAS_HOPE_SAIDA = COLUNAS_COMUNS + COLUNAS_EXTRAS_HOPE


# ==========================================================
# CALCULADORA (% Mínima / % Intermediária / % Máxima)
# ==========================================================

def _fmt_pct(valor: float) -> str:
    """Formata 2 casas com vírgula (padrão do seu arquivo HOPE)."""
    return f"{valor:.2f}".replace(".", ",")


def calcular_faixas_comissao(operacao: str, comissao_base: float) -> Tuple[str, str, str]:
    """
    Implementa as 3 fórmulas do Excel:
    - % Mínima        = ARRED(K*0,7;2)
    - % Intermediária = NOVO/CARTÃO/SAQUE COMPL. -> ARRED(K*0,95;2) | demais -> ARRED(K*0,85;2)
    - % Máxima        = NOVO/CARTÃO/SAQUE COMPL. -> ARRED(K*1;2)    | demais -> ARRED(K*0,95;2)

    Se operação não for reconhecida, retorna "VERIFICAR OP" para os 3 campos.
    """
    if not operacao:
        return ("VERIFICAR OP", "VERIFICAR OP", "VERIFICAR OP")

    try:
        base = float(comissao_base)
    except Exception:
        return ("VERIFICAR OP", "VERIFICAR OP", "VERIFICAR OP")

    op = operacao.strip().upper()

    # mínima sempre 0,7
    minima = round(base * 0.7, 2)

    if op in {"NOVO", "CARTÃO", "SAQUE COMPL."}:
        intermediaria = round(base * 0.95, 2)
        maxima = round(base * 1.0, 2)

    elif op in {"REFIN", "PORTAB/REFIN", "PORTABILIDADE", "COMPRA DE DIVIDA"}:
        intermediaria = round(base * 0.85, 2)
        maxima = round(base * 0.95, 2)

    else:
        return ("VERIFICAR OP", "VERIFICAR OP", "VERIFICAR OP")

    return (_fmt_pct(minima), _fmt_pct(intermediaria), _fmt_pct(maxima))


# ==========================================================
# REGRAS DE SAÍDA
# ==========================================================

def linha_fechar(item: CanonicalItem) -> Dict[str, Any]:
    """
    FECHAR → copiar linha original 100% igual e adicionar Término = ontem.
    """
    ontem = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")

    base = {col: "" for col in COLUNAS_HOPE_SAIDA}

    linha_original = item.extras.get("linha_original", {})

    for col in COLUNAS_HOPE_SAIDA:
        if col in linha_original:
            base[col] = linha_original[col]

    base["Término"] = ontem

    return base


def linha_abrir(item: CanonicalItem) -> Dict[str, Any]:
    """
    ABRIR → cria linha nova seguindo padrões HOPE.
    Agora também preenche:
      % Mínima / % Intermediária / % Máxima
    com base em:
      Operação + % Comissão (base)
    """
    hoje = date.today().strftime("%d/%m/%Y")

    base = {col: "" for col in COLUNAS_HOPE_SAIDA}

    # Campos principais
    base["Instituição"] = item.instituicao
    base["Produto"] = item.produto_nome
    base["Convênio"] = item.convenio
    base["Operação"] = item.operacao
    base["Parc. Atual"] = item.parc_atual
    base["% Comissão"] = _fmt_pct(float(item.comissao_pct))
    base["Id Tabela Banco"] = item.id_tabela_banco or ""
    base["Complemento"] = item.extras.get("Complemento", "")
    base["Família Produto"] = item.extras.get("Família Produto", "")
    base["Grupo Convênio"] = item.extras.get("Grupo Convênio", "")

    # Defaults HOPE
    base["Parc. Refin."] = "0"
    base["% PMT Pagas"] = "0"
    base["% Taxa"] = "0"
    base["Idade"] = "0-80"
    base["-"] = "%"

    # Base Comissão: regra PORTABILIDADE (mantida como era)
    if (item.operacao or "").upper() == "PORTABILIDADE":
        base["Base Comissão"] = "BRUTO"
    else:
        base["Base Comissão"] = "LÍQUIDO"

    # ✅ Aplicar calculadora nas linhas ABRIR
    pmin, pint, pmax = calcular_faixas_comissao(item.operacao, float(item.comissao_pct))
    base["% Mínima"] = pmin
    base["% Intermediária"] = pint
    base["% Máxima"] = pmax

    base["% Fator"] = "0"
    base["% TAC"] = "0"
    base["Val. Teto TAC"] = "0"
    base["Faixa Val. Contrato"] = "0,00-100.000,00-LÍQUIDO"
    base["Faixa Val. Seguro"] = "0"
    base["Vigência"] = hoje
    base["Término"] = ""

    base["Venda Digital"] = "SIM"
    base["Visualização Restrita"] = "NÃO"
    base["Val. Base Produção"] = ""

    # Colunas extras HOPE (mantém contrato de sempre)
    for col in COLUNAS_EXTRAS_HOPE:
        base[col] = ""

    return base
