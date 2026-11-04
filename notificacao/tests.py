from datetime import timedelta
from io import StringIO

from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone

from estoque.models import Emprestimo, ItemCASD, Morador
from .services import emprestimos_atrasados


def criar_emprestimo(item, morador, limit_date, status=Emprestimo.StatusEmprestimo.AT, quant=1):
    return Emprestimo.objects.create(id_item=item, id_morador=morador, limit_date=limit_date, status=status, quant=quant)


class EmprestimosAtrasadosTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Escada', quant_total=3)
        self.morador = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
        self.ontem = timezone.localdate() - timedelta(days=1)
        self.amanha = timezone.localdate() + timedelta(days=1)

    def test_emprestimo_vencido_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem)
        atrasados = emprestimos_atrasados()
        self.assertIn(emprestimo, atrasados)

    def test_emprestimo_no_prazo_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.amanha)
        atrasados = emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_emprestimo_devolvido_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem, Emprestimo.StatusEmprestimo.DE)
        atrasados = emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_mais_atrasado_vem_primeiro(self):
        recente = criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=1))
        antigo = criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=3))
        atrasados = list(emprestimos_atrasados())
        self.assertEqual(atrasados, [antigo, recente])

    def test_devolucao_sinalizada_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem, Emprestimo.StatusEmprestimo.DS)
        atrasados = emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_ler_item_e_morador_nao_gera_consultas_extras(self):
        for _ in range(3):
            criar_emprestimo(self.item, self.morador, self.ontem)
        with self.assertNumQueries(1):
            for emprestimo in emprestimos_atrasados():
                emprestimo.id_item.nome
                emprestimo.id_morador.nome


class VerificarAtrasosCommandTestCase(TestCase):
    def setUp(self):
        self.saida = StringIO()
        self.item = ItemCASD.objects.create(nome='Furadeira', quant_total=2)
        self.morador = Morador.objects.create(nome='Ana', ap='102J', email='ana@test.com')

    def test_sem_atrasos_informa_que_nao_ha_nenhum(self):
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Nenhum atraso encontrado.', self.saida.getvalue())

    def test_lista_o_item_do_emprestimo_atrasado(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Furadeira', self.saida.getvalue())

    def test_lista_o_email_do_morador_atrasado(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('ana@test.com', self.saida.getvalue())

    def test_lista_o_nome_do_morador_atrasado(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Ana', self.saida.getvalue())

    def test_lista_o_apartamento_do_morador_atrasado(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('102J', self.saida.getvalue())

    def test_lista_a_quantidade_emprestada(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2), quant=4)
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Furadeira x4', self.saida.getvalue())

    def test_mostra_os_dias_de_atraso(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('| 2d', self.saida.getvalue())

    def test_cabecalho_mostra_o_total_de_atrasos(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=3))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Empréstimos atrasados (2):', self.saida.getvalue())

    def test_com_atrasos_nao_informa_que_nao_ha_nenhum(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertNotIn('Nenhum atraso encontrado.', self.saida.getvalue())

    def test_emprestimo_devolvido_nao_e_listado(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2), Emprestimo.StatusEmprestimo.DE)
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('Nenhum atraso encontrado.', self.saida.getvalue())

    def test_mais_atrasado_e_listado_primeiro(self):
        antigo = ItemCASD.objects.create(nome='Escada', quant_total=1)
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=1))
        criar_emprestimo(antigo, self.morador, timezone.localdate() - timedelta(days=3))
        call_command('verificar_atrasos', stdout=self.saida)
        saida = self.saida.getvalue()
        self.assertLess(saida.index('Escada'), saida.index('Furadeira'))
