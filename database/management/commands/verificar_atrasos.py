from django.core.management.base import BaseCommand
from django.utils import timezone
from database.services import emprestimos_atrasados, usos_atrasados

def _formatar_atraso(limit_date):
    delta = timezone.now() - limit_date
    horas = int(delta.total_seconds() // 3600)
    dias, horas = divmod(horas, 24)
    return f'{dias}d {horas}h de atraso'

class Command(BaseCommand):
    help = 'Lista empréstimos e usos ativos que passaram do prazo previsto.'

    def handle(self, *args, **options):
        emprestimos = list(emprestimos_atrasados())
        usos = list(usos_atrasados())

        if not emprestimos and not usos:
            self.stdout.write('Nenhum atraso encontrado.')
            return

        if emprestimos:
            self.stdout.write(f'Empréstimos atrasados ({len(emprestimos)}):')
            for e in emprestimos:
                self.stdout.write(
                    f'  {e.id_item.nome} x{e.quant} | '
                    f'{e.id_morador.nome} ({e.id_morador.ap}, {e.id_morador.email}) | '
                    f'{_formatar_atraso(e.limit_date)}'
                )

        if usos:
            self.stdout.write(f'Usos atrasados ({len(usos)}):')
            for u in usos:
                self.stdout.write(
                    f'  {u.id_item.nome} x{u.quant} | '
                    f'{u.id_admin.nome} | '
                    f'{_formatar_atraso(u.limit_date)}'
                )