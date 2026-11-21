from datetime import datetime, time, timedelta
from io import StringIO
from smtplib import SMTPException
from unittest import mock

from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone

from estoque.helpers_tests import status_atual
from estoque.models import Emprestimo, ItemCASD, Morador
from .models import LogNotificacao
from .services import NotificacaoService


def criar_emprestimo(item, morador, limit_date, status=Emprestimo.StatusEmprestimo.AT, quant=1):
    return Emprestimo.objects.create(id_item=item, id_morador=morador, limit_date=limit_date, status=status, quant=quant)


def registrar_alerta(emprestimo, quando=None):
    # event_date é auto_now_add: para simular um alerta em outro momento, o valor é ajustado com update()
    log = LogNotificacao.objects.create(id_emprestimo=emprestimo, event_type=LogNotificacao.Evento.ALERTA_ATRASO)
    if quando is not None:
        LogNotificacao.objects.filter(pk=log.pk).update(event_date=quando)
    return log


def horario_local(dia, hora, minuto=0):
    # data e hora no fuso do projeto (America/Sao_Paulo)
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class EmprestimosAtrasadosTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Escada', quant_total=3)
        self.morador = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.ontem = timezone.localdate() - timedelta(days=1)
        self.amanha = timezone.localdate() + timedelta(days=1)

    def test_emprestimo_vencido_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem)
        atrasados = NotificacaoService.emprestimos_atrasados()
        self.assertIn(emprestimo, atrasados)

    def test_emprestimo_no_prazo_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.amanha)
        atrasados = NotificacaoService.emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_emprestimo_devolvido_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem, Emprestimo.StatusEmprestimo.DE)
        atrasados = NotificacaoService.emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_mais_atrasado_vem_primeiro(self):
        recente = criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=1))
        antigo = criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=3))
        atrasados = list(NotificacaoService.emprestimos_atrasados())
        self.assertEqual(atrasados, [antigo, recente])

    def test_devolucao_sinalizada_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem, Emprestimo.StatusEmprestimo.DS)
        atrasados = NotificacaoService.emprestimos_atrasados()
        self.assertNotIn(emprestimo, atrasados)

    def test_ler_item_e_morador_nao_gera_consultas_extras(self):
        for _ in range(3):
            criar_emprestimo(self.item, self.morador, self.ontem)
        with self.assertNumQueries(1):
            for emprestimo in NotificacaoService.emprestimos_atrasados():
                emprestimo.id_item.nome
                emprestimo.id_morador.nome


class EmprestimosANotificarTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Escada', quant_total=3)
        self.morador = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.hoje = timezone.localdate()
        self.ontem = self.hoje - timedelta(days=1)

    def test_atrasado_sem_alerta_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem)
        self.assertIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_atrasado_alertado_hoje_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem)
        registrar_alerta(emprestimo)
        self.assertNotIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_atrasado_alertado_ontem_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem - timedelta(days=1))
        registrar_alerta(emprestimo, horario_local(self.ontem, 12))
        self.assertIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_alerta_de_ontem_a_noite_nao_conta_como_de_hoje(self):
        # 23h30 em São Paulo já é o dia seguinte em UTC: a comparação tem que usar a data local
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem - timedelta(days=1))
        registrar_alerta(emprestimo, horario_local(self.ontem, 23, 30))
        self.assertIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_alerta_de_outro_emprestimo_nao_impede_o_aviso(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem)
        registrar_alerta(criar_emprestimo(self.item, self.morador, self.ontem))
        self.assertIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_emprestimo_que_vence_hoje_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.hoje)
        self.assertNotIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_devolucao_sinalizada_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem, Emprestimo.StatusEmprestimo.DS)
        self.assertNotIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_emprestimo_devolvido_nao_aparece(self):
        emprestimo = criar_emprestimo(self.item, self.morador, self.ontem, Emprestimo.StatusEmprestimo.DE)
        self.assertNotIn(emprestimo, NotificacaoService.emprestimos_a_notificar())

    def test_mais_atrasado_vem_primeiro(self):
        recente = criar_emprestimo(self.item, self.morador, self.ontem)
        antigo = criar_emprestimo(self.item, self.morador, self.hoje - timedelta(days=3))
        self.assertEqual(list(NotificacaoService.emprestimos_a_notificar()), [antigo, recente])

    def test_ler_item_e_morador_nao_gera_consultas_extras(self):
        # a busca pelos alertas de hoje entra como subconsulta, sem consulta separada
        for _ in range(3):
            registrar_alerta(criar_emprestimo(self.item, self.morador, self.ontem), horario_local(self.ontem, 12))
        with self.assertNumQueries(1):
            for emprestimo in NotificacaoService.emprestimos_a_notificar():
                emprestimo.id_item.nome
                emprestimo.id_morador.nome


class EnviarAlertaAtrasoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Furadeira', quant_total=3)
        self.morador = Morador.objects.create(nome='Ana/Calvin', ap_vaga='102J Vaga B', email='ana@test.com', telefone='12988888888')
        self.limit_date = timezone.localdate() - timedelta(days=2)
        self.emprestimo = criar_emprestimo(self.item, self.morador, self.limit_date, quant=2)

    def enviar(self, emprestimo=None):
        NotificacaoService.enviar_alerta_atraso(emprestimo or self.emprestimo)
        return mail.outbox[-1]

    def test_envia_um_email(self):
        self.enviar()
        self.assertEqual(len(mail.outbox), 1)

    def test_destinatario_e_o_email_do_morador(self):
        email = self.enviar()
        self.assertEqual(email.to, ['ana@test.com'])

    def test_remetente_e_o_padrao_do_projeto(self):
        email = self.enviar()
        self.assertEqual(email.from_email, settings.DEFAULT_FROM_EMAIL)

    def test_assunto_tem_o_nome_do_item(self):
        email = self.enviar()
        self.assertIn('Furadeira', email.subject)

    def test_corpo_tem_o_nome_do_morador(self):
        email = self.enviar()
        self.assertIn('Ana/Calvin', email.body)

    def test_corpo_tem_o_nome_do_item(self):
        email = self.enviar()
        self.assertIn('Item: Furadeira', email.body)

    def test_corpo_tem_a_quantidade(self):
        email = self.enviar()
        self.assertIn('Quantidade: 2', email.body)

    def test_corpo_tem_a_data_prevista_formatada(self):
        email = self.enviar()
        self.assertIn(self.limit_date.strftime('%d/%m/%Y'), email.body)

    def test_corpo_tem_os_dias_de_atraso(self):
        email = self.enviar()
        self.assertIn('Atraso: 2 dias', email.body)

    def test_um_dia_de_atraso_fica_no_singular(self):
        ontem = timezone.localdate() - timedelta(days=1)
        email = self.enviar(criar_emprestimo(self.item, self.morador, ontem))
        self.assertIn('Atraso: 1 dia\n', email.body)

    def test_nome_com_apostrofo_nao_e_escapado(self):
        # o template é texto puro: sem autoescape off, o apóstrofo viraria &#x27;
        morador = Morador.objects.create(nome="Ana D'Ávila", ap_vaga='103J Vaga A', email='davila@test.com', telefone='12977777777')
        email = self.enviar(criar_emprestimo(self.item, morador, self.limit_date))
        self.assertIn("Ana D'Ávila", email.body)

    def test_registra_um_alerta_de_atraso(self):
        self.enviar()
        log = LogNotificacao.objects.get()
        self.assertEqual((log.id_emprestimo, log.event_type), (self.emprestimo, LogNotificacao.Evento.ALERTA_ATRASO))

    def test_alerta_fica_sem_ip(self):
        self.enviar()
        self.assertIsNone(LogNotificacao.objects.get().ip_aparelho)

    def test_emprestimo_continua_ativo(self):
        self.enviar()
        self.assertEqual(status_atual(self.emprestimo), Emprestimo.StatusEmprestimo.AT)

    def test_emprestimo_alertado_sai_da_lista_a_notificar(self):
        self.enviar()
        self.assertNotIn(self.emprestimo, NotificacaoService.emprestimos_a_notificar())


class FalhaNoEnvioDoAlertaTestCase(TestCase):
    """Se o e-mail não sair, nada é registrado e o empréstimo é avisado na próxima execução."""

    def setUp(self):
        item = ItemCASD.objects.create(nome='Furadeira', quant_total=3)
        morador = Morador.objects.create(nome='Ana/Calvin', ap_vaga='102J Vaga B', email='ana@test.com', telefone='12988888888')
        self.emprestimo = criar_emprestimo(item, morador, timezone.localdate() - timedelta(days=2))
        with mock.patch('notificacao.services.send_mail', side_effect=SMTPException('servidor indisponível')):
            with self.assertRaises(SMTPException):
                NotificacaoService.enviar_alerta_atraso(self.emprestimo)

    def test_nao_registra_alerta(self):
        self.assertFalse(LogNotificacao.objects.exists())

    def test_emprestimo_continua_a_notificar(self):
        self.assertIn(self.emprestimo, NotificacaoService.emprestimos_a_notificar())


class VerificarAtrasosCommandTestCase(TestCase):
    def setUp(self):
        self.saida = StringIO()
        self.item = ItemCASD.objects.create(nome='Furadeira', quant_total=2)
        self.morador = Morador.objects.create(nome='Ana/Calvin', ap_vaga='102J Vaga B', email='ana@test.com', telefone='12988888888')

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
        self.assertIn('Ana/Calvin', self.saida.getvalue())

    def test_lista_o_apartamento_do_morador_atrasado(self):
        criar_emprestimo(self.item, self.morador, timezone.localdate() - timedelta(days=2))
        call_command('verificar_atrasos', stdout=self.saida)
        self.assertIn('102J Vaga B', self.saida.getvalue())

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
