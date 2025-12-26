from pathlib import Path
import uuid

from django.conf import settings
from django.http import JsonResponse, HttpRequest, FileResponse, Http404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from api.controllers.atualizar_planilha import processar_atualizacao


@method_decorator(csrf_exempt, name="dispatch")
class ExecucaoAtualizacaoView(View):
    """
    POST /api/execucoes/atualizacao
    """

    def post(self, request: HttpRequest):
        banco = request.POST.get("banco")
        arquivo_banco = request.FILES.get("arquivo_banco")
        arquivo_interno = request.FILES.get("arquivo_interno")

        if not banco or not arquivo_banco or not arquivo_interno:
            return JsonResponse(
                {"erro": "Campos obrigatórios: banco, arquivo_banco, arquivo_interno"},
                status=400,
            )

        exec_id = uuid.uuid4().hex
        exec_dir = Path(settings.MEDIA_ROOT) / "execucoes" / exec_id
        exec_dir.mkdir(parents=True, exist_ok=True)

        caminho_banco = exec_dir / "banco.xlsx"
        caminho_interno = exec_dir / "interno.xlsx"
        caminho_saida = exec_dir / "delta.xlsx"

        for file, path in [
            (arquivo_banco, caminho_banco),
            (arquivo_interno, caminho_interno),
        ]:
            with path.open("wb") as f:
                for chunk in file.chunks():
                    f.write(chunk)

        try:
            resultado = processar_atualizacao(
                banco=banco,
                caminho_banco=caminho_banco,
                caminho_interno=caminho_interno,
                caminho_saida=caminho_saida,
            )
        except Exception as e:
            return JsonResponse(
                {"status": "error", "erro": str(e)},
                status=500,
            )

        return JsonResponse(
            {
                "status": "success",
                "execucao_id": exec_id,
                "download_url": f"http://localhost:8000/api/execucoes/{exec_id}/download",
                "resumo": {
                    "linhas_banco": resultado["linhas_banco"],
                    "linhas_interno": resultado["linhas_interno"],
                    "linhas_saida": resultado["linhas_saida"],
                },
                "acoes": resultado["acoes"],
                "cache": resultado["cache"],
                "padronizacao": resultado["padronizacao"],
            }
        )


class DownloadDeltaView(View):
    """
    GET /api/execucoes/<execucao_id>/download
    Força download da planilha DELTA
    """

    def get(self, request: HttpRequest, execucao_id: str):
        caminho = Path(settings.MEDIA_ROOT) / "execucoes" / execucao_id / "delta.xlsx"

        if not caminho.exists():
            raise Http404("Arquivo não encontrado")

        return FileResponse(
            open(caminho, "rb"),
            as_attachment=True,
            filename="planilha_atualizacao.xlsx",
        )
