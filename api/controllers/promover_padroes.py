# api/controllers/promover_padroes.py

from pathlib import Path
import csv
import json

from padronizacao.servico_padronizacao import ServicoPadronizacao


def promover_padroes(caminho_csv_corrigido: Path) -> None:
    """
    Lê o CSV corrigido (aprovado/corrigido_para preenchidos)
    e atualiza o dicionario_manual.json com os novos padrões.

    Chave usada: id_raw | taxa_raw | prazo_raw
    """
    servico = ServicoPadronizacao()
    dic = servico.dic_manual

    with caminho_csv_corrigido.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            aprovado_raw = (row.get("aprovado") or "").strip().lower()
            corrigido = (row.get("corrigido_para") or "").strip()

            aprovado = aprovado_raw in {"sim", "true", "1", "ok", "x"}

            if not aprovado and not corrigido:
                continue

            id_raw = (row.get("entrada_id_raw") or "").strip()
            taxa_raw = (row.get("entrada_taxa_raw") or "").strip()
            prazo_raw = (row.get("entrada_prazo_raw") or "").strip()

            chave = f"{id_raw.strip().upper()}|{taxa_raw.strip().upper()}|{prazo_raw.strip().upper()}"

            if corrigido:
                produto_final = corrigido
            else:
                produto_final = row.get("saida_produto") or row.get("entrada_produto_raw") or ""

            convenio_final = row.get("saida_convenio") or row.get("entrada_convenio_raw") or ""

            dic[chave] = {
                "produto_padronizado": produto_final,
                "convenio_padronizado": convenio_final,
                "familia_produto": row.get("saida_familia") or "",
                "grupo_convenio": row.get("saida_grupo") or "",
            }

    caminho_dic = servico.caminho_dic_manual
    with caminho_dic.open("w", encoding="utf-8") as f:
        json.dump(dic, f, ensure_ascii=False, indent=2)
