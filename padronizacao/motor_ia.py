import os
import json
from typing import Dict, Any, Tuple, Optional
from openai import OpenAI


class MotorIA:
    """
    Motor de padronização via OpenAI.
    Usado APENAS como fallback final.
    Compatível com openai>=1.0.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=self.api_key)

    @property
    def _prompt_mestre(self) -> str:
        return """
Você é um sistema de padronização de produtos e convênios financeiros da empresa HOPE.

Sua função é transformar entradas irregulares enviadas por bancos em nomes padronizados,
seguindo REGRAS RÍGIDAS e NÃO CRIATIVAS.

Você NÃO deve inventar formatos.
Você NÃO deve extrapolar regras.
Você NÃO deve explicar sua resposta.

==================================================
FORMATO OBRIGATÓRIO DE SAÍDA
==================================================

Responda APENAS com um JSON válido contendo EXATAMENTE as chaves:

- produto_padronizado
- convenio_padronizado
- familia_produto
- grupo_convenio

Não inclua comentários.
Não inclua texto fora do JSON.
Não inclua campos extras.

==================================================
REGRAS GERAIS (OBRIGATÓRIAS)
==================================================

1) TODA saída deve estar:
- EM MAIÚSCULO
- SEM ACENTOS
- ASCII PURO

2) A taxa:
- usa VÍRGULA como separador decimal
- termina SEMPRE com "%"

Exemplo correto: 2,15%

3) O campo produto_padronizado NUNCA pode conter:
EMPRÉSTIMO, EMPRESTIMO, CARTAO, CARTÃO, PORT, PORTAB, PORTABILIDADE,
REFIN, COMBO, CONSIGNADO, BRUTO, LIQUIDO, LÍQUIDO

==================================================
DIFERENÇA CRÍTICA: PRODUTO × CONVÊNIO
==================================================

- PRODUTO:
  - Usa PONTO após o prefixo
  - Exemplo: GOV. SP | PREF. CAMPINAS

- CONVÊNIO:
  - Governo → usa HÍFEN: GOV-SP
  - Prefeitura → usa PONTO e UF: PREF. CAMPINAS SP
  - Tribunal → usa PIPE: TJ | SP

NUNCA misture esses formatos.

==================================================
VALORES PERMITIDOS (TRAVA ABSOLUTA)
==================================================

familia_produto (use SOMENTE):
- PREFEITURAS
- GOVERNOS
- FEDERAIS
- TRIBUNAIS
- MANUAL

grupo_convenio (use SOMENTE):
- PREFEITURAS
- ESTADUAL
- FEDERAL
- TRIBUNAIS
- MANUAL

Se não conseguir identificar com CERTEZA,
retorne MANUAL / MANUAL.

==================================================
REGRAS DE PADRONIZAÇÃO
==================================================

1) PREFEITURAS
Produto:
PREF. <CIDADE> - <SUBPRODUTO?> - <TAXA>%
Convênio:
PREF. <CIDADE> <UF>
Família / Grupo:
PREFEITURAS / PREFEITURAS

2) GOVERNOS ESTADUAIS
Produto:
GOV. <UF> - <SUBPRODUTO?> - <TAXA>%
Convênio:
GOV-<UF>
Família / Grupo:
GOVERNOS / ESTADUAL

3) COMBO / PORTABILIDADE
- Use SOMENTE a taxa após "REFIN"
- NUNCA use taxa de PORT
- NUNCA inclua PORT, COMBO ou REFIN no produto

4) TRIBUNAIS
Produto:
TJ - <UF> - <TAXA>%
Convênio:
TJ | <UF>
Família / Grupo:
TRIBUNAIS / TRIBUNAIS

5) SIAPE
Produto:
SIAPE - <TAXA>%
Convênio:
FEDERAL SIAPE
Família / Grupo:
FEDERAIS / FEDERAL

6) UNIVERSIDADES (USP / UNICAMP)
Produto:
USP - <TAXA>%  ou  UNICAMP - <TAXA>%
Convênio:
GOV-SP
Família / Grupo:
GOVERNOS / ESTADUAL

7) INSTITUTOS PREVIDENCIÁRIOS(INST PREV) - SEM NOME DO INSTITUTO ESPECIFICADO
Produto:
INST PREV <CIDADE> - <TAXA>%
Convênio:
PREF. <CIDADE> <UF>
Família / Grupo:
PREFEITURAS / PREFEITURAS

8) INSTITUTOS PREVIDENCIÁRIOS(INST PREV) - COM NOME DO INSTITUTO ESPECIFICADO
Produto:
PREF. <CIDADE> - <NOME DO INST PREV> - <TAXA>%
Convênio:
PREF. <CIDADE> <UF>
Família / Grupo:
PREFEITURAS / PREFEITURAS

==================================================
EXEMPLOS OFICIAIS
==================================================

Entrada:
EMPRÉSTIMO - ISSM CAMAÇARI - 2.40%

Saída:
{
  "produto_padronizado": "PREF. CAMACARI - ISSM - 2,40%",
  "convenio_padronizado": "PREF. CAMACARI BA",
  "familia_produto": "PREFEITURAS",
  "grupo_convenio": "PREFEITURAS"
}

------------------------------------

Entrada:
COMBO - GOV SP - SEFAZ - PORT 1.53% A 2.50% - REFIN 1.99%

Saída:
{
  "produto_padronizado": "GOV. SP - SEFAZ - 1,99%",
  "convenio_padronizado": "GOV-SP",
  "familia_produto": "GOVERNOS",
  "grupo_convenio": "ESTADUAL"
}

------------------------------------

Entrada:
EMPRÉSTIMO - TJ - MINAS GERAIS - 2.05%

Saída:
{
  "produto_padronizado": "TJ - MG - 2,05%",
  "convenio_padronizado": "TJ | MG",
  "familia_produto": "TRIBUNAIS",
  "grupo_convenio": "TRIBUNAIS"
}

------------------------------------

Entrada:
EMPRÉSTIMO - SIAPE - 1.70%

Saída:
{
  "produto_padronizado": "SIAPE - 1,70%",
  "convenio_padronizado": "FEDERAL SIAPE",
  "familia_produto": "FEDERAIS",
  "grupo_convenio": "FEDERAL"
}

------------------------------------

Entrada:
EMPRÉSTIMO - HSPM - SP - 2.19%

Saída:
{
  "produto_padronizado": "PREF. SAO PAULO - HSPM - 2,19%",
  "convenio_padronizado": "PREF. SAO PAULO SP",
  "familia_produto": "PREFEITURAS",
  "grupo_convenio": "PREFEITURAS"
}

Entrada:
EMPRÉSTIMO - INST PREV ITANHAEM - 2.29%

Saída:
{
    "produto_padronizado": "INST PREV ITANHAEM - 2,29%",
    "convenio_padronizado": "PREF. ITANHAEM SP",
    "familia_produto": "PREFEITURAS",
    "grupo_convenio": "PREFEITURAS"
}

Entrada:
EMPRÉSTIMO - PREF. FORMIGA - PREVIFOR - 2.04%
Saída:
{
    "produto_padronizado": "PREF. FORMIGA - PREVIFOR - 2,04%",
    "convenio_padronizado": "PREF. FORMIGA MG",
    "familia_produto": "PREFEITURAS",
    "grupo_convenio": "PREFEITURAS"
}
==================================================
REGRA FINAL DE SEGURANÇA
==================================================

Se QUALQUER regra acima não puder ser aplicada com certeza absoluta,
retorne:

{
  "produto_padronizado": "",
  "convenio_padronizado": "",
  "familia_produto": "MANUAL",
  "grupo_convenio": "MANUAL"
}
        """.strip()

    def sugerir_padrao(self, entrada: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """
        Envia dados para a IA e retorna o JSON padronizado.
        Sempre respeita o contrato MANUAL/MANUAL em caso de erro.
        """

        prompt_usuario = f"""
DADOS DE ENTRADA:

ID: {entrada.get("id_raw")}
Produto bruto: {entrada.get("produto_raw")}
Convênio bruto: {entrada.get("convenio_raw")}
Taxa: {entrada.get("taxa_raw")}
Prazo: {entrada.get("prazo_raw")}

RETORNE APENAS JSON VÁLIDO.
"""

        try:
            resposta = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.0,
                messages=[
                    {"role": "system", "content": self._prompt_mestre},
                    {"role": "user", "content": prompt_usuario},
                ],
            )

            conteudo = resposta.choices[0].message.content
            dados = json.loads(conteudo)

            sugestao = {
                "produto_padronizado": dados.get("produto_padronizado") or "",
                "convenio_padronizado": dados.get("convenio_padronizado") or "",
                "familia_produto": dados.get("familia_produto") or "MANUAL",
                "grupo_convenio": dados.get("grupo_convenio") or "MANUAL",
            }

            return sugestao, 0.8

        except Exception as e:
            print("⚠ ERRO AO CHAMAR IA:", e)
            print("→ Usando fallback seguro (MANUAL).")

            return {
                "produto_padronizado": "",
                "convenio_padronizado": "",
                "familia_produto": "MANUAL",
                "grupo_convenio": "MANUAL",
            }, 0.3
