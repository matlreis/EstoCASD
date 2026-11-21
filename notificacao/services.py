from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string

from estoque.models import Emprestimo
from .models import LogNotificacao


class NotificacaoService:

    @staticmethod
    def emprestimos_atrasados():
        return (
            Emprestimo.objects.atrasados()
            .select_related('id_item', 'id_morador')
            .order_by('limit_date')
        )

    @staticmethod
    def emprestimos_a_notificar():
        """Filtra empréstimos atrasados que não foram notificados hoje."""
        avisados_hoje = LogNotificacao.objects.filter(
            event_type=LogNotificacao.Evento.ALERTA_ATRASO,
            event_date__date=timezone.localdate(),
        ).values('id_emprestimo')
        return NotificacaoService.emprestimos_atrasados().exclude(pk__in=avisados_hoje)

    @staticmethod
    def enviar_alerta_atraso(emprestimo):
        morador = emprestimo.id_morador
        dias = (timezone.localdate() - emprestimo.limit_date).days
        subject = f'[EstoCASD] Empréstimo atrasado — {emprestimo.id_item.nome}'
        context = {'emprestimo': emprestimo, 'dias': dias}
        message = render_to_string('notificacao/email_atraso.txt', context)
        send_mail(subject, message, None, [morador.email])
        LogNotificacao.objects.create(
            id_emprestimo=emprestimo, 
            event_type=LogNotificacao.Evento.ALERTA_ATRASO
        )
