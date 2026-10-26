from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from estoque.models import Transacao, Emprestimo, Item, Morador
from .services import emprestimos_atrasados


class EmprestimosAtrasadosTestCase(TestCase):
    def setUp(self):
        self.item = Item.objects.create(nome='TesteCASD', tipo_estoque='CASD', quant_total=3)
        self.morador = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
        self.ontem = timezone.now() - timedelta(days=1)
        self.amanha = timezone.now() + timedelta(days=1)

    def test_emprestimo_vencido_aparece(self):
        emprestimo = Emprestimo.objects.create(id_item=self.item, id_morador=self.morador, limit_date=self.ontem)
        self.assertIn(emprestimo, emprestimos_atrasados())

    def test_emprestimo_no_prazo_nao_aparece(self):
        emprestimo = Emprestimo.objects.create(id_item=self.item, id_morador=self.morador, limit_date=self.amanha)
        self.assertNotIn(emprestimo, emprestimos_atrasados())

    def test_emprestimo_devolvido_nao_aparece(self):
        emprestimo = Emprestimo.objects.create(id_item=self.item, id_morador=self.morador, limit_date=self.ontem, status=Transacao.StatusTransacao.DE)
        self.assertNotIn(emprestimo, emprestimos_atrasados())