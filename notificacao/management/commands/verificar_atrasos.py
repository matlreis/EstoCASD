from django.core.management.base import BaseCommand
from django.utils import timezone
from notificacao.services import emprestimos_atrasados

def _formatar_atraso(limit_date):
    dias = (timezone.localdate() - limit_date).days
    return f'{dias}d de atraso'

class Command(BaseCommand):
    help = 'Lista empréstimos ativos que passaram do prazo previsto.'

    def handle(self, *args, **options):
        emprestimos = list(emprestimos_atrasados())

        if not emprestimos:
            self.stdout.write('Nenhum atraso encontrado.')
            return

        self.stdout.write(f'Empréstimos atrasados ({len(emprestimos)}):')
        for e in emprestimos:
            self.stdout.write(
                f'  {e.id_item.nome} x{e.quant} | '
                f'{e.id_morador.nome} ({e.id_morador.ap}, {e.id_morador.email}) | '
                f'{_formatar_atraso(e.limit_date)}'
            )
