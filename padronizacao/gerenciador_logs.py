from pathlib import Path
import csv
from typing import Dict, Any, List, Optional


class GerenciadorLogs:
    def __init__(self, caminho_csv: Optional[Path] = None, habilitado: bool = True):
        self.habilitado = habilitado and (caminho_csv is not None)
        self.caminho_csv = caminho_csv
        self._buffer: List[Dict[str, Any]] = []

        self.colunas = [
            "chave_cache",
            "id_produto_origem",
            "produto_raw",

            "ia_produto_padronizado",
            "ia_convenio_padronizado",
            "ia_familia_produto",
            "ia_grupo_convenio",
            "ia_confianca",

            "aprovado",
            "produto_corrigido",
            "convenio_corrigido",
            "familia_corrigida",
            "grupo_corrigido",
        ]

        if not self.habilitado:
            return

        self.caminho_csv.parent.mkdir(parents=True, exist_ok=True)

        if not self.caminho_csv.exists():
            with self.caminho_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.colunas, delimiter=";")
                writer.writeheader()

    def registrar_sugestao(
        self,
        chave_cache: str,
        entrada: Dict[str, Any],
        sugestao: Dict[str, Any],
        confianca: float,
    ):
        if not self.habilitado:
            return

        self._buffer.append({
            "chave_cache": chave_cache,
            "id_produto_origem": entrada.get("id_raw", ""),
            "produto_raw": entrada.get("produto_raw", ""),

            "ia_produto_padronizado": sugestao.get("produto_padronizado", ""),
            "ia_convenio_padronizado": sugestao.get("convenio_padronizado", ""),
            "ia_familia_produto": sugestao.get("familia_produto", ""),
            "ia_grupo_convenio": sugestao.get("grupo_convenio", ""),
            "ia_confianca": confianca,

            "aprovado": "",
            "produto_corrigido": "",
            "convenio_corrigido": "",
            "familia_corrigida": "",
            "grupo_corrigido": "",
        })

    def flush(self) -> int:
        """Escreve o buffer no CSV em uma tacada só."""
        if not self.habilitado or not self._buffer:
            return 0

        with self.caminho_csv.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.colunas, delimiter=";")
            writer.writerows(self._buffer)

        n = len(self._buffer)
        self._buffer.clear()
        return n
