# api/urls.py

from django.urls import path
from .views import AtualizarPlanilhaView, PromoverPadroesView

urlpatterns = [
    path("atualizar/", AtualizarPlanilhaView.as_view(), name="api-atualizar"),
    path("promover/", PromoverPadroesView.as_view(), name="api-promover"),
]
