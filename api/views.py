# api/views.py

from pathlib import Path
from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.views import View

from .controllers.atualizar_planilha import processar_atualizacao
from .controllers.promover_padroes import promover_padroes


class AtualizarPlanilhaView(View):
    """
    POST /api/atualizar/

    Campos esperados:
    - banco (ex: "HOPE")
    - arquivo_banco (file)
    - arquivo_interno (file)
    """

    def post(self, request: HttpRequest):
        banco = request.POST.get("banco", "HOPE")
        arquivo_banco = request.FILES.get("arquivo_banco")
        arquivo_interno = request.FILES.get("arquivo_interno")

        if not arquivo_banco or not arquivo_interno:
            return JsonResponse(
                {"erro": "Parâmetros obrigatórios: arquivo_banco e arquivo_interno."},
                status=400,
            )

        # Diretório onde vamos salvar a saída
        saidas_dir = Path(settings.MEDIA_ROOT) / "saidas"
        saidas_dir.mkdir(parents=True, exist_ok=True)

        caminho_banco = saidas_dir / "tmp_banco.xlsx"
        caminho_interno = saidas_dir / "tmp_interno.xlsx"
        caminho_saida = saidas_dir / "saida_atualizada.xlsx"

        # Salvar uploads em disco
        with caminho_banco.open("wb") as f:
            for chunk in arquivo_banco.chunks():
                f.write(chunk)

        with caminho_interno.open("wb") as f:
            for chunk in arquivo_interno.chunks():
                f.write(chunk)

        # Processar atualização
        try:
            processar_atualizacao(banco, caminho_banco, caminho_interno, caminho_saida)
        except Exception as e:
            return JsonResponse({"erro": str(e)}, status=500)

        # Para integração futura com Next.js, retornamos o caminho relativo
        caminho_relativo = f"{settings.MEDIA_URL}saidas/saida_atualizada.xlsx"

        return JsonResponse(
            {
                "mensagem": "Processamento concluído com sucesso.",
                "arquivo_saida": caminho_relativo,
            }
        )


class PromoverPadroesView(View):
    """
    POST /api/promover/

    Campos esperados:
    - arquivo_corrigido (file CSV com colunas aprovado/corrigido_para)
    """

    def post(self, request: HttpRequest):
        arquivo_corrigido = request.FILES.get("arquivo_corrigido")

        if not arquivo_corrigido:
            return JsonResponse({"erro": "arquivo_corrigido é obrigatório."}, status=400)

        tmp_dir = Path(settings.MEDIA_ROOT) / "promocoes"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        caminho_corrigido = tmp_dir / "sugestoes_corrigidas.csv"

        with caminho_corrigido.open("wb") as f:
            for chunk in arquivo_corrigido.chunks():
                f.write(chunk)

        try:
            promover_padroes(caminho_corrigido)
        except Exception as e:
            return JsonResponse({"erro": str(e)}, status=500)

        return JsonResponse({"mensagem": "Padrões promovidos com sucesso."})
