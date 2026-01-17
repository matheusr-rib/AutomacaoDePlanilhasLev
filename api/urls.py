from django.urls import path
from api.views import ExecucaoAtualizacaoView, DownloadDeltaView, ExecucaoStatusView

urlpatterns = [
    path("execucoes/atualizacao", ExecucaoAtualizacaoView.as_view(), name="execucao-atualizacao"),
    path("execucoes/<str:execucao_id>/status", ExecucaoStatusView.as_view(), name="execucao-status"),
    path("execucoes/<str:execucao_id>/download", DownloadDeltaView.as_view(), name="execucao-download"),
]
