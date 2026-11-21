from django.core.management.base import BaseCommand
from notificacao.services import NotificacaoService


class Command(BaseCommand):
    help = 'Notifica empréstimos atrasados por e-mail.'

    def handle(self, *args, **options):
        emprestimos = list(NotificacaoService.emprestimos_a_notificar())

        if not emprestimos:
            self.stdout.write('Nenhum atraso a notificar.')
            return

        alertas_enviados = 0
        for e in emprestimos:
            try:
                NotificacaoService.enviar_alerta_atraso(e)
            except OSError as err:
                self.stderr.write(f'Não foi possível enviar o alerta para {e.id_morador.email}. Erro: {err}')
            else:
                self.stdout.write(f'Alerta enviado para {e.id_morador.email} ({e.id_item.nome}).')
                alertas_enviados += 1

        self.stdout.write(f'Alertas enviados: {alertas_enviados} de {len(emprestimos)}.')
