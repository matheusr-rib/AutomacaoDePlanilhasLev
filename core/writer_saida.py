from typing import List, Dict, Any
from pathlib import Path

import pandas as pd


def escrever_excel(linhas: List[Dict[str, Any]], colunas: List[str], caminho_saida: Path) -> None:
    """
    Escreve um DataFrame em Excel, garantindo a ordem das colunas.
    """
    df = pd.DataFrame(linhas, columns=colunas)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(caminho_saida, index=False)
