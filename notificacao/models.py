from django.db import models

from core.models import LogEvento
from estoque.models import Emprestimo


class LogNotificacao(LogEvento):
    id_emprestimo = models.ForeignKey(Emprestimo, on_delete=models.CASCADE, db_column='id_emprestimo')

    class Evento(models.TextChoices):
        ALERTA_ATRASO = 'ALERTA_ATRASO', 'Alerta de atraso'

    event_type = models.CharField(max_length=20, choices=Evento.choices)

    class Meta(LogEvento.Meta):
        verbose_name = 'log de notificação'
        verbose_name_plural = 'logs de notificações'
