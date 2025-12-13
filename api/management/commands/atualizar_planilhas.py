from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.controllers.atualizar_planilha import processar_atualizacao


class Command(BaseCommand):
    help = "Atualiza planilhas de comissionamento com cache, IA e validação humana"

    def add_arguments(self, parser):
        parser.add_argument(
            "--banco",
            type=str,
            required=True,
            help="Nome do banco (ex: HOPE)",
        )

        parser.add_argument(
            "--arquivo_banco",
            type=str,
            required=True,
            help="Caminho do arquivo do banco (ex: HOPE.xlsx)",
        )

        parser.add_argument(
            "--arquivo_interno",
            type=str,
            required=True,
            help="Caminho do arquivo interno (ex: tabela interna hope.xlsx)",
        )

        parser.add_argument(
            "--arquivo_validacao",
            type=str,
            required=False,
            help="CSV de validação humana para atualizar o cache antes da execução",
        )

        parser.add_argument(
            "--saida",
            type=str,
            required=True,
            help="Caminho do arquivo Excel de saída",
        )

    def handle(self, *args, **options):
        banco = options["banco"]
        caminho_banco = Path(options["arquivo_banco"])
        caminho_interno = Path(options["arquivo_interno"])
        caminho_saida = Path(options["saida"])

        caminho_validacao = None
        if options.get("arquivo_validacao"):
            caminho_validacao = Path(options["arquivo_validacao"])

        if not caminho_banco.exists():
            raise CommandError(f"Arquivo banco não encontrado: {caminho_banco}")

        if not caminho_interno.exists():
            raise CommandError(f"Arquivo interno não encontrado: {caminho_interno}")

        if caminho_validacao and not caminho_validacao.exists():
            raise CommandError(
                f"Arquivo de validação não encontrado: {caminho_validacao}"
            )

        self.stdout.write(self.style.NOTICE("Processando banco HOPE..."))
        self.stdout.write(f"Arquivo banco: {caminho_banco}")
        self.stdout.write(f"Arquivo interno: {caminho_interno}")

        if caminho_validacao:
            self.stdout.write(f"Arquivo validação: {caminho_validacao}")

        self.stdout.write(f"Saída: {caminho_saida}")

        processar_atualizacao(
            banco=banco,
            caminho_banco=caminho_banco,
            caminho_interno=caminho_interno,
            caminho_saida=caminho_saida,
            caminho_validacao=caminho_validacao,
        )

        self.stdout.write(self.style.SUCCESS("Atualização concluída com sucesso."))
