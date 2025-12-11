# bancos/hope/writer.py

from pathlib import Path
from typing import List, Dict, Any

from core.writer_saida import escrever_excel
from bancos.hope.regras import COLUNAS_HOPE_SAIDA


def escrever_planilha_hope(linhas: List[Dict[str, Any]], caminho_saida: Path) -> None:
    """
    Escreve o Excel final da HOPE, garantindo todas as colunas
    na ordem correta.
    """
    escrever_excel(linhas, COLUNAS_HOPE_SAIDA, caminho_saida)
