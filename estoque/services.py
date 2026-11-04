from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ItemCASD


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
