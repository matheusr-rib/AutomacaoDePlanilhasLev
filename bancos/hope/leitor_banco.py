# bancos/hope/leitor_banco.py

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


def ler_excel_banco(caminho: Path) -> List[Dict[str, Any]]:
    """
    Lê o arquivo do banco (RelatorioProdutos.xlsx)
    e devolve uma lista de dicts (linhas).
    """
    df = pd.read_excel(caminho, dtype=str).fillna("")

    return df.to_dict(orient="records")
