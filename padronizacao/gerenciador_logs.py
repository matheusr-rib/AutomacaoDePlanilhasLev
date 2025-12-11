import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class GerenciadorLogs:
    """
    Registra as sugestões da IA em um CSV para revisão manual posterior.
    """

    def __init__(self, caminho_csv: Path | None = None):
        self.caminho_csv = caminho_csv or Path("logs") / "sugestoes_padronizacao.csv"
        self.caminho_csv.parent.mkdir(parents=True, exist_ok=True)

    def registrar_sugestao(self, entrada: Dict[str, Any], saida: Dict[str, Any], confianca: float) -> None:
        cabecalho = [
            "data_hora",
            "entrada_id_raw",
            "entrada_prazo_raw",
            "entrada_taxa_raw",
            "entrada_produto_raw",
            "entrada_convenio_raw",
            "saida_produto",
            "saida_convenio",
            "saida_familia",
            "saida_grupo",
            "confianca",
            "aprovado",
            "corrigido_para",
        ]

        linha = {
            "data_hora": datetime.now().isoformat(),
            "entrada_id_raw": entrada.get("id_raw", ""),
            "entrada_prazo_raw": entrada.get("prazo_raw", ""),
            "entrada_taxa_raw": entrada.get("taxa_raw", ""),
            "entrada_produto_raw": entrada.get("produto_raw", ""),
            "entrada_convenio_raw": entrada.get("convenio_raw", ""),
            "saida_produto": saida.get("produto_padronizado", ""),
            "saida_convenio": saida.get("convenio_padronizado", ""),
            "saida_familia": saida.get("familia_produto", ""),
            "saida_grupo": saida.get("grupo_convenio", ""),
            "confianca": str(confianca),
            "aprovado": "",
            "corrigido_para": "",
        }

        arquivo_existe = self.caminho_csv.exists()

        with self.caminho_csv.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cabecalho)
            if not arquivo_existe:
                writer.writeheader()
            writer.writerow(linha)
