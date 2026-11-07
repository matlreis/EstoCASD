from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import ItemCASD, Morador, Emprestimo, LogEmprestimo


# Prazo máximo de devolução do item do CASD
PRAZO_MAX_DIAS = 60

class EstoqueService:

    @staticmethod
    def list_items():
        return ItemCASD.objects.filter(is_active=True).order_by('nome')

    @staticmethod
    def create_item(dados):
        return ItemCASD.objects.create(**dados)

    @staticmethod
    @transaction.atomic
    def update_item(item, dados):
        item = ItemCASD.objects.select_for_update().get(pk=item.pk)
        if dados['quant_total'] < item.quant_emprestada:
            raise ValidationError(
                f'A quantidade total não pode ser menor que a quantidade emprestada ({item.quant_emprestada}).'
            )

        for campo, valor in dados.items():
            setattr(item, campo, valor)
        item.save()
        return item

    @staticmethod
    @transaction.atomic
    def delete_item(item):
        item = ItemCASD.objects.select_for_update().get(pk=item.pk)
        if item.emprestimo_set.ativos().exists():
            raise ValidationError('Há empréstimos em andamento com este item.')

        item.is_active = False
        item.save(update_fields=['is_active'])


class EmprestimoService:

    @staticmethod
    @transaction.atomic
    def create_emprestimo(item, dados, ip=None):
        item = ItemCASD.objects.select_for_update().get(pk=item.pk)
        if not item.is_active:
            raise ValidationError("Este item não está mais disponível.")

        quant = dados['quant']
        if not 1 <= quant <= item.quant_disponivel:
            raise ValidationError(f"Quantidade indisponível. Disponível: {item.quant_disponivel}.")

        limit_date = dados['limit_date']
        if limit_date < timezone.localdate():
            raise ValidationError("A data de devolução não pode estar no passado.")
        if limit_date > timezone.localdate() + timedelta(days=PRAZO_MAX_DIAS):
            raise ValidationError(f"A data de devolução não pode passar de {PRAZO_MAX_DIAS} dias.")
        # proibir prazo de entrega no final de semana (5 = sábado, 6 = domingo)
        if limit_date.weekday() >= 5:
            raise ValidationError("A data de devolução não pode cair no fim de semana.")

        morador, _ = Morador.objects.update_or_create(
            email=dados['email'].lower(),
            defaults={'nome': dados['nome'], 'ap': dados['ap']},
        )

        item.quant_emprestada += quant
        item.save(update_fields=['quant_emprestada'])

        emprestimo = Emprestimo.objects.create(
            id_item=item, id_morador=morador, quant=quant, limit_date=limit_date,
        )
        LogEmprestimo.objects.create(
            id_emprestimo=emprestimo, ip_aparelho=ip, event_type=LogEmprestimo.Evento.CRIADO,
        )

        return emprestimo

    @staticmethod
    @transaction.atomic
    def sinalizar_devolucao(item, email, ip=None):
        emprestimos = list(Emprestimo.objects.select_for_update().filter(
            id_item=item,
            id_morador__email=email.lower(),
            status=Emprestimo.StatusEmprestimo.AT,
        ))
        if not emprestimos:
            raise ValidationError("Nenhum empréstimo ativo deste item para este e-mail.")

        for emprestimo in emprestimos:
            emprestimo.status = Emprestimo.StatusEmprestimo.DS
            emprestimo.save(update_fields=['status'])
            LogEmprestimo.objects.create(
                id_emprestimo=emprestimo, ip_aparelho=ip,
                event_type=LogEmprestimo.Evento.DEVOLUCAO_SINALIZADA,
            )
