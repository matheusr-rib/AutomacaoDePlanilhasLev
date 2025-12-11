# api/management/commands/promover_padroes.py

from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from api.controllers.promover_padroes import promover_padroes


class Command(BaseCommand):
    help = "Promove padrões corrigidos/validados para o dicionario_manual.json."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--arquivo_corrigido",
            type=str,
            required=True,
            help="Caminho para o CSV de sugestões corrigidas (com colunas 'aprovado', 'corrigido_para').",
        )

    def handle(self, *args, **options):
        caminho_csv = Path(options["arquivo_corrigido"])

        self.stdout.write(f"Promovendo padrões a partir de: {caminho_csv}")

        promover_padroes(caminho_csv)

        self.stdout.write(self.style.SUCCESS("Padrões promovidos com sucesso!"))
