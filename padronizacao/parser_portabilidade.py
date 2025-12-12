# padronizacao/parser_portabilidade.py
# ------------------------------------
# Responsável por extrair taxas de PORT e REFIN da nomenclatura original
# e gerar o COMPLEMENTO final quando a operação é PORTABILIDADE.

import re


def extrair_port_e_refin(nomenclatura: str):
    """
    Extrai as faixas de PORT e REFIN a partir do nome original
    enviado pelo banco.
    
    Exemplo de entrada:
        "COMBO - GOV ACRE - PORT 1.49% A 2.50% - REFIN 1.90%"

    Retorno:
        ("1,49% A 2,50%", "1,90%")
    """
    if not nomenclatura:
        return None, None

    # Extrai a faixa da PORTABILIDADE (ex.: 1.49% A 2.50%)
    regex_port = r"PORT\s+([\d.,]+%\s*A\s*[\d.,]+%)"

    # Extrai a taxa REFIN (ex.: 1.90%)
    regex_refin = r"REFIN\s+([\d.,]+%)"

    match_port = re.search(regex_port, nomenclatura, flags=re.IGNORECASE)
    match_refin = re.search(regex_refin, nomenclatura, flags=re.IGNORECASE)

    port = match_port.group(1) if match_port else None
    refin = match_refin.group(1) if match_refin else None

    # Converte decimal para vírgula (padrão brasileiro HOPE)
    if port:
        port = port.replace(".", ",")
    if refin:
        refin = refin.replace(".", ",")

    return port, refin


def montar_complemento(id_origem: str, operacao: str, nomenclatura: str) -> str:
    """
    Gera o campo COMPLEMENTO atualizado.

    ➤ Regras HOPE:
        - Apenas PORTABILIDADE monta complemento especial:
              "{ID} | TX ENTRADA {PORT} | OBRIGATORIO O REFIN"

        - Todas as outras operações retornam APENAS o ID.

    Exemplo:
        Entrada:
            id_origem = "2360"
            operacao  = "PORTABILIDADE"
            nomenclatura = "COMBO - GOV ACRE - PORT 1.49% A 2.50% - REFIN 1.90%"

        Saída:
            "2360 | TX ENTRADA 1,49% A 2,50% | OBRIGATORIO O REFIN"
    """

    if not operacao or operacao.upper() != "PORTABILIDADE":
        return id_origem

    port, refin = extrair_port_e_refin(nomenclatura)

    # Se não achar PORT, usa fallback seguro (apenas ID)
    if not port:
        return id_origem

    # NOVO FORMATO OFICIAL:
    return f"{id_origem} | TX ENTRADA {port} | OBRIGATORIO O REFIN"
