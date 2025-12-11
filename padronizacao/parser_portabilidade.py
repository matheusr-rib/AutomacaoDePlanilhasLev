import re

def extrair_port_e_refin(nomenclatura: str):
    """
    Extrai os percentuais de PORT e REFIN da nomenclatura do produto.
    Exemplo:
        "COMBO - GOV ACRE - PORT 1.49% A 2.50% - REFIN 1.90%"
    Retorna:
        ("1,49% A 2,50%", "1,90%")
    """
    if not nomenclatura:
        return None, None

    regex_port = r"PORT\s+([\d.,]+%\s*A\s*[\d.,]+%)"
    regex_refin = r"REFIN\s+([\d.,]+%)"

    match_port = re.search(regex_port, nomenclatura, flags=re.IGNORECASE)
    match_refin = re.search(regex_refin, nomenclatura, flags=re.IGNORECASE)

    porcent_port = match_port.group(1) if match_port else None
    porcent_refin = match_refin.group(1) if match_refin else None

    if porcent_port:
        porcent_port = porcent_port.replace(".", ",")
    if porcent_refin:
        porcent_refin = porcent_refin.replace(".", ",")

    return porcent_port, porcent_refin


def montar_complemento(id_origem: str, operacao: str, nomenclatura: str) -> str:
    """
    Gera o campo COMPLEMENTO.
    Para PORTABILIDADE:
        "{IdOrigem} | TX {PORT} | OBRIGATORIO O REFIN"
    Para outras operações:
        retorna apenas o IdOrigem.
    """
    if not operacao or operacao.upper() != "PORTABILIDADE":
        return id_origem

    port, _ = extrair_port_e_refin(nomenclatura)

    if not port:
        return id_origem

    return f"{id_origem} | TX {port} | OBRIGATORIO O REFIN"
