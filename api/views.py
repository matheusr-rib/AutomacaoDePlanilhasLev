# api/views.py
from __future__ import annotations

from pathlib import Path
import uuid
import json

from django.conf import settings
from django.http import JsonResponse, HttpRequest, FileResponse, Http404
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from api.controllers.atualizar_planilha import processar_atualizacao
from api.controllers.background import executar_em_background


def _write_status(status_path: Path, status: str, erro: str | None = None, resultado: dict | None = None) -> None:
    payload = {
        "status": status,
        "erro": erro,
    }
    if resultado is not None:
        payload["resultado"] = resultado

    status_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _processar_async(
    exec_dir: Path,
    banco: str,
    caminho_banco: Path,
    caminho_interno: Path,
    caminho_saida: Path,
) -> None:
    """
    Roda o processamento em background e atualiza status.json.
    """
    status_path = exec_dir / "status.json"

    try:
        resultado = processar_atualizacao(
            banco=banco,
            caminho_banco=caminho_banco,
            caminho_interno=caminho_interno,
            caminho_saida=caminho_saida,
        )

        _write_status(status_path, "DONE", erro=None, resultado=resultado)

    except Exception as e:
        _write_status(status_path, "ERROR", erro=str(e), resultado=None)


@method_decorator(csrf_exempt, name="dispatch")
class ExecucaoAtualizacaoView(View):
    """
    POST /api/execucoes/atualizacao
    - salva arquivos
    - cria status.json (PROCESSING)
    - dispara processamento em background
    - retorna 202 com execucao_id
    """

    def post(self, request: HttpRequest):
        banco = request.POST.get("banco")
        arquivo_banco = request.FILES.get("arquivo_banco")
        arquivo_interno = request.FILES.get("arquivo_interno")

        if not banco or not arquivo_banco or not arquivo_interno:
            return JsonResponse(
                {"status": "error", "erro": "Campos obrigatórios: banco, arquivo_banco, arquivo_interno"},
                status=400,
            )

        exec_id = uuid.uuid4().hex
        exec_dir = Path(settings.MEDIA_ROOT) / "execucoes" / exec_id
        exec_dir.mkdir(parents=True, exist_ok=True)

        caminho_banco = exec_dir / "banco.xlsx"
        caminho_interno = exec_dir / "interno.xlsx"
        caminho_saida = exec_dir / "delta.xlsx"
        status_path = exec_dir / "status.json"

        # 1) salvar uploads
        for file, path in [
            (arquivo_banco, caminho_banco),
            (arquivo_interno, caminho_interno),
        ]:
            with path.open("wb") as f:
                for chunk in file.chunks():
                    f.write(chunk)

        # 2) status inicial
        _write_status(status_path, "PROCESSING")

        # 3) dispara background
        executar_em_background(
            _processar_async,
            exec_dir,
            banco,
            caminho_banco,
            caminho_interno,
            caminho_saida,
        )

        # 4) responde rápido (202 Accepted)
        return JsonResponse(
            {
                "status": "success",
                "execucao_id": exec_id,
                "status_url": f"/api/execucoes/{exec_id}/status",
                "download_url": f"/api/execucoes/{exec_id}/download",
            },
            status=202,
        )


class ExecucaoStatusView(View):
    """
    GET /api/execucoes/<execucao_id>/status
    """

    def get(self, request: HttpRequest, execucao_id: str):
        exec_dir = Path(settings.MEDIA_ROOT) / "execucoes" / execucao_id
        status_path = exec_dir / "status.json"

        if not status_path.exists():
            raise Http404("Execução não encontrada")

        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            # se corromper por algum motivo, devolve algo seguro
            data = {"status": "ERROR", "erro": "status.json inválido"}

        return JsonResponse(data, status=200)


class DownloadDeltaView(View):
    """
    GET /api/execucoes/<execucao_id>/download
    Força download da planilha DELTA
    """

    def get(self, request: HttpRequest, execucao_id: str):
        caminho = Path(settings.MEDIA_ROOT) / "execucoes" / execucao_id / "delta.xlsx"

        if not caminho.exists():
            # Se ainda está processando, devolve 404 mesmo (front vai esperar pelo status DONE)
            raise Http404("Arquivo ainda não está pronto")

        return FileResponse(
            open(caminho, "rb"),
            as_attachment=True,
            filename="planilha_atualizacao.xlsx",
        )
