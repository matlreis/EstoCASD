from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.utils import proximo_dia_util, somar_dias_uteis
from .models import (
    ItemCASD,
    Morador,
    Emprestimo,
    LogEmprestimo,
    ItemZeladoria,
    LogItemZeladoria,
    Venda
)


# Prazo máximo de devolução do item do CASD, em dias úteis a partir da retirada
PRAZO_MAX_DIAS_UTEIS = 5
# Antecedência máxima para agendar a retirada, em dias úteis a partir de hoje
ANTECEDENCIA_MAX_DIAS_UTEIS = 5

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
    def criar_emprestimo(item, dados, ip=None):
        item = ItemCASD.objects.select_for_update().get(pk=item.pk)
        if not item.is_active:
            raise ValidationError("Este item não está mais disponível.")

        quant = dados['quant']
        if not 1 <= quant <= item.quant_disponivel:
            raise ValidationError(f"Quantidade indisponível. Disponível: {item.quant_disponivel}.")

        hoje = timezone.localdate()
        # sem data de retirada, vale a de hoje (ou a segunda-feira, se hoje for fim de semana)
        start_date = dados.get('start_date') or proximo_dia_util(hoje)
        if start_date < hoje:
            raise ValidationError("A data de retirada não pode estar no passado.")
        if start_date > somar_dias_uteis(hoje, ANTECEDENCIA_MAX_DIAS_UTEIS):
            raise ValidationError(
                f"A retirada só pode ser agendada com até {ANTECEDENCIA_MAX_DIAS_UTEIS} dias úteis de antecedência."
            )
        if start_date.weekday() >= 5:
            raise ValidationError("A data de retirada não pode cair no fim de semana.")

        limit_date = dados['limit_date']
        if limit_date < hoje:
            raise ValidationError("A data de devolução não pode estar no passado.")
        if limit_date < start_date:
            raise ValidationError("A data de devolução não pode ser anterior à data de retirada.")
        if limit_date > somar_dias_uteis(start_date, PRAZO_MAX_DIAS_UTEIS):
            raise ValidationError(
                f"A data de devolução não pode passar de {PRAZO_MAX_DIAS_UTEIS} dias úteis depois da retirada."
            )
        # proibir prazo de entrega no final de semana (5 = sábado, 6 = domingo)
        if limit_date.weekday() >= 5:
            raise ValidationError("A data de devolução não pode cair no fim de semana.")

        morador, _ = Morador.objects.update_or_create(
            email=dados['email'].lower(),
            defaults={'nome': dados['nome'], 'ap_vaga': dados['ap_vaga']},
        )

        item.quant_emprestada += quant
        item.save(update_fields=['quant_emprestada'])

        emprestimo = Emprestimo.objects.create(
            id_item=item, id_morador=morador, quant=quant, start_date=start_date, limit_date=limit_date,
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
            start_date__lte=timezone.localdate(),
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

    @staticmethod
    @transaction.atomic
    def confirmar_devolucao(emprestimo, admin, ip=None):
        emprestimo = Emprestimo.objects.select_for_update().get(pk=emprestimo.pk)
        if emprestimo.status == Emprestimo.StatusEmprestimo.DE:
            raise ValidationError('Este empréstimo já foi devolvido.')

        item = ItemCASD.objects.select_for_update().get(pk=emprestimo.id_item_id)
        item.quant_emprestada -= emprestimo.quant
        item.save(update_fields=['quant_emprestada'])

        emprestimo.status = Emprestimo.StatusEmprestimo.DE
        emprestimo.save(update_fields=['status'])
        LogEmprestimo.objects.create(
            id_emprestimo=emprestimo, id_admin=admin, ip_aparelho=ip,
            event_type=LogEmprestimo.Evento.DEVOLUCAO_CONFIRMADA,
        )

    @staticmethod
    def listar_ativos():
        return (
            Emprestimo.objects.ativos()
            .select_related('id_item', 'id_morador')
            .order_by('limit_date')
        )


class ZeladoriaService:

    @staticmethod
    def list_items():
        return ItemZeladoria.objects.filter(is_active=True).order_by('nome')

    @staticmethod
    @transaction.atomic
    def create_item(dados, admin, ip=None):
        item = ItemZeladoria.objects.create(**dados)
        LogItemZeladoria.objects.create(
            id_item=item, id_admin=admin, ip_aparelho=ip,
            event_type=LogItemZeladoria.Evento.CRIADO, quant_nova=item.quant_total,
        )
        return item

    @staticmethod
    @transaction.atomic
    def update_item(item, dados, admin, ip=None):
        item = ItemZeladoria.objects.select_for_update().get(pk=item.pk)
        quant_anterior = item.quant_total
        for campo, valor in dados.items():
            setattr(item, campo, valor)
        item.save()

        # alterar só nome ou preço não entra no histórico do item
        if item.quant_total != quant_anterior:
            LogItemZeladoria.objects.create(
                id_item=item, id_admin=admin, ip_aparelho=ip,
                event_type=LogItemZeladoria.Evento.QUANT_ALTERADA,
                quant_anterior=quant_anterior, quant_nova=item.quant_total,
            )
        return item

    @staticmethod
    @transaction.atomic
    def delete_item(item, admin, ip=None):
        item = ItemZeladoria.objects.select_for_update().get(pk=item.pk)
        item.is_active = False
        item.save(update_fields=['is_active'])
        LogItemZeladoria.objects.create(
            id_item=item, id_admin=admin, ip_aparelho=ip,
            event_type=LogItemZeladoria.Evento.REMOVIDO,
        )

    @staticmethod
    @transaction.atomic
    def registrar_venda(item, dados, admin, ip=None):
        item = ItemZeladoria.objects.select_for_update().get(pk=item.pk)
        if not item.is_active:
            raise ValidationError('Este item foi removido.')
        if item.preco_unitario is None:
            raise ValidationError('Este item não está à venda.')
        if not 1 <= dados['quant'] <= item.quant_total:
            raise ValidationError(f'Quantidade indisponível. Em estoque: {item.quant_total}.')

        quant_anterior = item.quant_total
        item.quant_total -= dados['quant']
        item.save(update_fields=['quant_total'])
        LogItemZeladoria.objects.create(
            id_item=item, id_admin=admin, ip_aparelho=ip,
            event_type=LogItemZeladoria.Evento.VENDA,
            quant_anterior=quant_anterior, quant_nova=item.quant_total
        )
        return Venda.objects.create(
            id_item=item, id_admin=admin, preco_unitario=item.preco_unitario, **dados,
        )

    @staticmethod
    def listar_vendas():
        return (
            Venda.objects.select_related('id_item', 'id_admin')
            .order_by('-data', '-pk')
        )

    @staticmethod
    def historico(item):
        return (
            item.logitemzeladoria_set
            .select_related('id_admin')
            .order_by('-event_date', '-pk')
        )
