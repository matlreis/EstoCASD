from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, F, Q

from estoque.models import (
    ItemCASD,
    Morador,
    Emprestimo,
    LogEmprestimo,
    ItemZeladoria,
    LogItemZeladoria,
    Venda
)

class DashboardEmprestimoService:

    @staticmethod
    def listar_devolvidos_atrasos():
        devolvidos_atrasados = Q(
            logemprestimo__event_type='DEVOLUCAO_CONFIRMADA',
            logemprestimo__event_date__gt=F('limit_date')
        )

        solicitados_atrasados = Q(
            logemprestimo__event_type='DEVOLUCAO_SINALIZADA',
            logemprestimo__event_date__gt=F('limit_date')
        )

        ativos_atrasados = Q(
            status='ATIVO',
            limit_date__lt=timezone.localdate()
        )

        return (
            Emprestimo.objects
            .filter(devolvidos_atrasados | solicitados_atrasados | ativos_atrasados)
            .values('id_item', 'id_item__nome')
            .annotate(total_atrasos=Count('id', distinct=True))
            .order_by('-total_atrasos')
        )

class DashboardZeladoriaService:

    @staticmethod
    def listar_vendas():
        return (
            Venda.objects
            .values('id_item', 'id_item__nome')
            .annotate(total_vendido=Sum('quant'))
            .order_by('-total_vendido')
        )