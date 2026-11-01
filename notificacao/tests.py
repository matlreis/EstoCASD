from datetime import timedelta
from io import StringIO

from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone

from estoque.models import Transacao, Emprestimo, Item, Morador
from .services import emprestimos_atrasados


def criar_emprestimo(item, morador, limit_date, status=Transacao.StatusTransacao.AT):
    return Emprestimo.objects.create(id_item=item, id_morador=morador, limit_date=limit_date, status=status)


class EmprestimosAtrasadosTestCase(TestCase):
    def setUp(self):
        self.item = Item.objects.create(nome='Escada', tipo_estoque='CASD', quant_total=3)
        self.morador = Morador.objects.create(nome='João Pedro', ap='101J', email='jp@test.com')
        self.ontem = timezone.now() - timedelta(days=1)
        self.amanha = timezone.now() + timedelta(days=1)

    def test_emprestimo_vencido_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem)
        atrasados = emprestimos_atrasados()
        self.assertIn(emprestimo, atrasados)

    def test_emprestimo_no_prazo_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.amanha)
        atrasados = emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_emprestimo_devolvido_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem, Transacao.StatusTransacao.DE)
        atrasados = emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_mais_atrasado_vem_primeiro(self):
        recente = criar_emprestimo(self.item, self.morador, timezone.now() - timedelta(hours=1))
        antigo = criar_emprestimo(self.item, self.morador, timezone.now() - timedelta(days=3))
        atrasados = list(emprestimos_atrasados())
        self.assertEqual(atrasados, [antigo, recente])


class VerificarAtrasosCommandTestCase(TestCase):
    def setUp(self):
        self.saida = StringIO()
        self.item = Item.objects.create(nome='Furadeira', tipo_estoque='CASD', quant_total=2)
        self.morador = Morador.objects.create(nome='Ana', ap='102J', email='ana@test.com')

    def test_sem_atrasos_informa_que_nao_ha_nenhum(self):
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Nenhum atraso encontrado.', self.saida.getvalue())

    def test_lista_o_item_do_emprestimo_atrasado(self):
        criar_emprestimo(self.item, self.morador, timezone.now() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Furadeira', self.saida.getvalue())

    def test_lista_o_email_do_morador_atrasado(self):
        criar_emprestimo(self.item, self.morador, timezone.now() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('ana@test.com', self.saida.getvalue())