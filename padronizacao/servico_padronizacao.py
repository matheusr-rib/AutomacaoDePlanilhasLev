from typing import Dict, Any, Tuple
from pathlib import Path
import json

from .motor_ia import MotorIA
from .gerenciador_logs import GerenciadorLogs


class ServicoPadronizacao:
    """
    Pipeline:
    1) tenta dicionário manual (cache_manual.json) com chave: id + taxa + prazo
    2) (futuro) tenta heurísticas usando a base interna
    3) chama IA
    4) loga sugestão para revisão
    """

    def __init__(self, caminho_dic_manual: Path | None = None):
        self.caminho_dic_manual = caminho_dic_manual or Path("padronizacao") / "dicionario_manual.json"
        self.dic_manual = self._carregar_dicionario()
        self.ia = MotorIA()
        self.logger = GerenciadorLogs()

    def _carregar_dicionario(self) -> Dict[str, Any]:
        if self.caminho_dic_manual.exists():
            with self.caminho_dic_manual.open(encoding="utf-8") as f:
                return json.load(f)
        return {}

    def padronizar(self, entrada: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """
        entrada deve conter:
        - id_raw: Id do Produto na Origem
        - taxa_raw: Taxa a.m
        - prazo_raw: parc_atual ou Prazo Inicial/Prazo Final compactado
        - produto_raw, convenio_raw (para contexto da IA)
        """
        chave = self._gerar_chave_manual(entrada)

        # 1) dicionário manual (aprendizado validado)
        if chave in self.dic_manual:
            return self.dic_manual[chave], 1.0

        # 2) heurísticas com base interna (pode ser implementado depois)

        # 3) IA
        sugestao, confianca = self.ia.sugerir_padrao(entrada)

        # 4) log para revisão manual
        self.logger.registrar_sugestao(entrada, sugestao, confianca)

        return sugestao, confianca

    def _gerar_chave_manual(self, entrada: Dict[str, Any]) -> str:
        """
        Gera uma chave única textual para lookup no dicionário manual:
        id_raw | taxa_raw | prazo_raw
        """
        id_raw = (entrada.get("id_raw") or "").strip().upper()
        taxa_raw = (entrada.get("taxa_raw") or "").strip().upper()
        prazo_raw = (entrada.get("prazo_raw") or "").strip().upper()

        return f"{id_raw}|{taxa_raw}|{prazo_raw}"
