# api/management/commands/atualizar_planilhas.py

from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from api.controllers.atualizar_planilha import processar_atualizacao


class Command(BaseCommand):
    help = "Atualiza planilhas de comissionamento para um banco específico (ex: HOPE)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--banco", type=str, required=True, help="Nome do banco (ex: HOPE)")
        parser.add_argument(
            "--arquivo_banco",
            type=str,
            required=True,
            help="Caminho para o arquivo XLSX do banco (RelatorioProdutos.xlsx).",
        )
        parser.add_argument(
            "--arquivo_interno",
            type=str,
            required=True,
            help="Caminho para a tabela interna (tabela interna hope.xlsx).",
        )
        parser.add_argument(
            "--saida",
            type=str,
            required=True,
            help="Caminho para salvar o arquivo XLSX atualizado.",
        )

    def handle(self, *args, **options):
        banco = options["banco"]
        caminho_banco = Path(options["arquivo_banco"])
        caminho_interno = Path(options["arquivo_interno"])
        caminho_saida = Path(options["saida"])

        self.stdout.write(f"Processando banco {banco}...")
        self.stdout.write(f"Arquivo banco: {caminho_banco}")
        self.stdout.write(f"Arquivo interno: {caminho_interno}")
        self.stdout.write(f"Saída: {caminho_saida}")

        processar_atualizacao(banco, caminho_banco, caminho_interno, caminho_saida)

        self.stdout.write(self.style.SUCCESS("Atualização concluída com sucesso!"))
