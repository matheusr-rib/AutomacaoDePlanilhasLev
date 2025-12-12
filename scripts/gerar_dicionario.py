import pandas as pd
import json

df = pd.read_excel(r"C:\Users\reisr\Downloads\exemplosjson.xlsx")

dicionario = {}

for _, row in df.iterrows():
    chave = f"{row['Id Tabela Banco']}|{row['TAXA']}|{row['Parc. Atual']}"
    
    dicionario[chave] = {
        "produto_padronizado": row["Produto"],
        "convenio_padronizado": row["Convênio"],
        "familia_produto": row["Família Produto"],
        "grupo_convenio": row["Grupo Convênio"]
    }

with open("dicionario_manual.json", "w", encoding="utf-8") as f:
    json.dump(dicionario, f, ensure_ascii=False, indent=2)

print("Dicionário gerado com sucesso!")
