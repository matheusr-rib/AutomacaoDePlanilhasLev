# bancos/hope/leitor_interno.py

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


def ler_excel_interno(caminho: Path) -> List[Dict[str, Any]]:
    """
    Lê a tabela interna HOPE mantendo todas as colunas e valores.
    """
    df = pd.read_excel(caminho, dtype=str).fillna("")

    return df.to_dict(orient="records")
