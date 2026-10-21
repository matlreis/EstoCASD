from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Emprestimo, Item, Transacao, Uso


class EstoqueService:

    @staticmethod
    def list_items(tipo_estoque=None):
        itens = Item.objects.filter(is_active=True).order_by('nome')
        if tipo_estoque:
            itens = itens.filter(tipo_estoque=tipo_estoque)
        return itens

    @staticmethod
    def create_item(dados):
        return Item.objects.create(**dados)

    @staticmethod
    @transaction.atomic
    def update_item(item, dados):
        item = Item.objects.select_for_update().get(pk=item.pk)
        if dados['quant_total'] < item.quant_uso:
            raise ValidationError(
                f'A quantidade total não pode ser menor que a quantidade em uso ({item.quant_uso}).'
            )

        for campo, valor in dados.items():
            setattr(item, campo, valor)
        item.save()
        return item

    @staticmethod
    @transaction.atomic
    def delete_item(item):
        item = Item.objects.select_for_update().get(pk=item.pk)
        devolvido = Transacao.StatusTransacao.DE
        em_andamento = (
            item.emprestimo_set.exclude(status=devolvido).exists()
            or item.uso_set.exclude(status=devolvido).exists()
        )
        if em_andamento:
            raise ValidationError('Há transações em andamento com este item.')

        item.is_active = False
        item.save(update_fields=['is_active'])


_RELATED = {
    Emprestimo: ('id_item', 'id_morador'),
    Uso: ('id_item', 'id_admin')
}

def _atrasados(model):
    return (
        model.objects
        .filter(status=Transacao.StatusTransacao.AT, limit_date__lt=timezone.now())
        .select_related(*_RELATED[model])
        .order_by('limit_date')
    )

def emprestimos_atrasados():
    return _atrasados(Emprestimo)

def usos_atrasados():
    return _atrasados(Uso)
