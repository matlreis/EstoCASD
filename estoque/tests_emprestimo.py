from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .forms import EmprestimoForm
from .models import Emprestimo, ItemCASD, LogEmprestimo, Morador
from .services import EmprestimoService
from .helpers_tests import HOJE, PRAZO_LIMITE, SABADO, DOMINGO, SEGUNDA, FIXAR_HOJE, AT, DS, DE, criar_emprestimo, criar_admin, status_atual


def dados_emprestimo(**alteracoes):
    dados = {
        'nome': 'Pedro/Sonic',
        'ap_vaga': '101J Vaga A',
        'email': 'pedro@test.com',
        'telefone': '12999999999',
        'quant': 1,
        'limit_date': HOJE + timedelta(days=1),  # sexta-feira
    }
    dados.update(alteracoes)
    return dados


@FIXAR_HOJE
class CreateEmprestimoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)

    def test_retorna_o_emprestimo_criado(self):
        emprestimo = EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=2))
        self.assertEqual(Emprestimo.objects.get(), emprestimo)

    def test_emprestimo_guarda_quantidade_e_data(self):
        emprestimo = EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=2))
        self.assertEqual((emprestimo.quant, emprestimo.limit_date), (2, HOJE + timedelta(days=1)))

    def test_emprestimo_comeca_ativo(self):
        emprestimo = EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())
        self.assertEqual(emprestimo.status, Emprestimo.StatusEmprestimo.AT)

    def test_aumenta_a_quantidade_emprestada(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=2))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 2)

    def test_emprestimos_seguidos_acumulam_a_quantidade_emprestada(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=1))
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=2))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 3)

    def test_emprestimo_agendado_comeca_ativo(self):
        dados = dados_emprestimo(start_date=HOJE + timedelta(days=1), limit_date=SEGUNDA)
        emprestimo = EmprestimoService.criar_emprestimo(self.item, dados)
        self.assertEqual(emprestimo.status, Emprestimo.StatusEmprestimo.AT)

    def test_emprestimo_agendado_ja_reserva_a_quantidade(self):
        dados = dados_emprestimo(quant=2, start_date=HOJE + timedelta(days=1), limit_date=SEGUNDA)
        EmprestimoService.criar_emprestimo(self.item, dados)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 2)


@FIXAR_HOJE
class QuantidadeEmprestimoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3, quant_emprestada=1)

    def test_aceita_exatamente_o_disponivel(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=2))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_disponivel, 0)

    def test_recusa_mais_que_o_disponivel(self):
        with self.assertRaisesMessage(ValidationError, 'Disponível: 2'):
            EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=3))

    def test_recusa_quantidade_zero(self):
        with self.assertRaises(ValidationError):
            EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=0))

    def test_recusa_item_sem_unidades_disponiveis(self):
        esgotado = ItemCASD.objects.create(nome='Extensão', quant_total=1, quant_emprestada=1)
        with self.assertRaises(ValidationError):
            EmprestimoService.criar_emprestimo(esgotado, dados_emprestimo(quant=1))

    def test_usa_a_quantidade_do_banco_e_nao_a_da_instancia_recebida(self):
        # simula outro empréstimo feito depois que a view leu o item
        ItemCASD.objects.filter(pk=self.item.pk).update(quant_emprestada=3)
        with self.assertRaises(ValidationError):
            EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=1))

    def test_recusa_item_removido(self):
        # o item foi removido depois que a view o leu: a instância ainda diz is_active=True
        ItemCASD.objects.filter(pk=self.item.pk).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, 'não está mais disponível'):
            EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())


@FIXAR_HOJE
class DataDevolucaoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)

    def criar_com_data(self, dias_a_partir_de_hoje):
        limit_date = HOJE + timedelta(days=dias_a_partir_de_hoje)
        return EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(limit_date=limit_date))

    def test_aceita_devolucao_hoje(self):
        emprestimo = self.criar_com_data(0)
        self.assertEqual(emprestimo.limit_date, HOJE)

    def test_aceita_devolucao_na_sexta(self):
        emprestimo = self.criar_com_data(1)
        self.assertEqual(emprestimo.limit_date.weekday(), 4)

    def test_recusa_data_no_passado(self):
        with self.assertRaises(ValidationError):
            self.criar_com_data(-1)

    def test_recusa_sabado(self):
        with self.assertRaisesMessage(ValidationError, 'fim de semana'):
            self.criar_com_data(2)

    def test_recusa_domingo(self):
        with self.assertRaisesMessage(ValidationError, 'fim de semana'):
            self.criar_com_data(3)

    def test_aceita_o_ultimo_dia_do_prazo_maximo(self):
        emprestimo = self.criar_com_data(7)
        self.assertEqual(emprestimo.limit_date, PRAZO_LIMITE)

    def test_recusa_um_dia_alem_do_prazo_maximo(self):
        with self.assertRaisesMessage(ValidationError, '5 dias úteis'):
            self.criar_com_data(8)

    def test_data_no_passado_tem_mensagem_propria(self):
        with self.assertRaisesMessage(ValidationError, 'passado'):
            self.criar_com_data(-1)


@FIXAR_HOJE
class DataRetiradaTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)

    def agendar(self, retirada_em, devolucao_em):
        retirada = HOJE + timedelta(days=retirada_em)
        devolucao = HOJE + timedelta(days=devolucao_em)
        return EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(start_date=retirada, limit_date=devolucao))

    def test_sem_retirada_vale_hoje(self):
        emprestimo = EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())
        self.assertEqual(emprestimo.start_date, HOJE)

    def test_sem_retirada_em_fim_de_semana_vale_a_segunda(self):
        with mock.patch('django.utils.timezone.localdate', new=lambda: SABADO):
            emprestimo = EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(limit_date=SEGUNDA))
        self.assertEqual(emprestimo.start_date, SEGUNDA)

    def test_guarda_a_data_de_retirada_informada(self):
        emprestimo = self.agendar(1, 4)
        self.assertEqual(emprestimo.start_date, HOJE + timedelta(days=1))

    def test_aceita_retirada_hoje(self):
        emprestimo = self.agendar(0, 1)
        self.assertEqual(emprestimo.start_date, HOJE)

    def test_aceita_retirada_na_segunda(self):
        emprestimo = self.agendar(4, 5)
        self.assertEqual(emprestimo.start_date, SEGUNDA)

    def test_aceita_o_ultimo_dia_de_antecedencia(self):
        emprestimo = self.agendar(7, 7)
        self.assertEqual(emprestimo.start_date, PRAZO_LIMITE)

    def test_recusa_um_dia_alem_da_antecedencia(self):
        with self.assertRaisesMessage(ValidationError, '5 dias úteis de antecedência'):
            self.agendar(8, 8)

    def test_recusa_retirada_no_passado(self):
        with self.assertRaisesMessage(ValidationError, 'retirada não pode estar no passado'):
            self.agendar(-1, 1)

    def test_recusa_retirada_no_sabado(self):
        with self.assertRaisesMessage(ValidationError, 'retirada não pode cair no fim de semana'):
            self.agendar(2, 4)

    def test_recusa_retirada_no_domingo(self):
        with self.assertRaisesMessage(ValidationError, 'retirada não pode cair no fim de semana'):
            self.agendar(3, 4)

    def test_aceita_devolucao_no_mesmo_dia_da_retirada(self):
        emprestimo = self.agendar(1, 1)
        self.assertEqual(emprestimo.limit_date, HOJE + timedelta(days=1))

    def test_recusa_devolucao_antes_da_retirada(self):
        with self.assertRaisesMessage(ValidationError, 'anterior à data de retirada'):
            self.agendar(4, 1)

    def test_prazo_pula_o_fim_de_semana_depois_da_retirada(self):
        # retirada na sexta: o 5º dia útil é a sexta seguinte
        emprestimo = self.agendar(1, 8)
        self.assertEqual(emprestimo.limit_date, HOJE + timedelta(days=8))

    def test_aceita_o_ultimo_dia_do_prazo_contado_da_retirada(self):
        # retirada na última quinta possível: o prazo vai até a quinta seguinte
        emprestimo = self.agendar(7, 14)
        self.assertEqual(emprestimo.limit_date, HOJE + timedelta(days=14))

    def test_recusa_um_dia_alem_do_prazo_contado_da_retirada(self):
        with self.assertRaisesMessage(ValidationError, '5 dias úteis depois da retirada'):
            self.agendar(7, 15)


@FIXAR_HOJE
class EmprestimoRecusadoTestCase(TestCase):
    """Uma solicitação recusada não pode deixar nenhum rastro no banco."""

    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=1)
        with self.assertRaises(ValidationError):
            EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(quant=2))

    def test_nao_altera_a_quantidade_emprestada(self):
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 0)

    def test_nao_cria_emprestimo(self):
        self.assertFalse(Emprestimo.objects.exists())

    def test_nao_cria_morador(self):
        self.assertFalse(Morador.objects.exists())

    def test_nao_cria_log(self):
        self.assertFalse(LogEmprestimo.objects.exists())


@FIXAR_HOJE
class MoradorEmprestimoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)

    def test_cria_o_morador_novo(self):
        emprestimo = EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())
        self.assertEqual(emprestimo.id_morador, Morador.objects.get(email='pedro@test.com'))

    def test_guarda_o_email_em_minusculas(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(email='Pedro@Test.COM'))
        self.assertEqual(Morador.objects.get().email, 'pedro@test.com')

    def test_reaproveita_o_morador_existente(self):
        Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())
        self.assertEqual(Morador.objects.count(), 1)

    def test_reaproveita_o_morador_mesmo_com_maiusculas_no_email(self):
        Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(email='PEDRO@test.com'))
        self.assertEqual(Morador.objects.count(), 1)

    def test_atualiza_nome_e_ap_vaga_do_morador_existente(self):
        Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(nome='Pedro Souza/Sonic', ap_vaga='202J Vaga B'))
        morador = Morador.objects.get()
        self.assertEqual((morador.nome, morador.ap_vaga), ('Pedro Souza/Sonic', '202J Vaga B'))

    def test_guarda_o_telefone_do_morador_novo(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())
        self.assertEqual(Morador.objects.get().telefone, '12999999999')

    def test_atualiza_o_telefone_do_morador_existente(self):
        Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(telefone='1234567890'))
        self.assertEqual(Morador.objects.get().telefone, '1234567890')


class MoradorTelefoneTestCase(TestCase):
    """O model guarda só os dígitos; a máscara é retirada antes, pelo formulário."""

    def morador(self, telefone):
        return Morador(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone=telefone)

    def test_aceita_telefone_so_com_digitos(self):
        self.morador('12999999999').full_clean()  # não lança ValidationError

    def test_recusa_telefone_com_mascara(self):
        with self.assertRaises(ValidationError) as erro:
            self.morador('(12) 99999-9999').full_clean()
        self.assertIn('telefone', erro.exception.message_dict)

    def test_recusa_telefone_sem_ddd(self):
        with self.assertRaises(ValidationError) as erro:
            self.morador('999999999').full_clean()
        self.assertIn('telefone', erro.exception.message_dict)

    def test_formata_celular(self):
        self.assertEqual(self.morador('12999999999').telefone_formatado, '(12) 99999-9999')

    def test_formata_fixo(self):
        self.assertEqual(self.morador('1234567890').telefone_formatado, '(12) 3456-7890')


@FIXAR_HOJE
class LogEmprestimoCriadoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)

    def test_registra_um_log_criado(self):
        emprestimo = EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(), ip='10.0.0.1')
        log = LogEmprestimo.objects.get()
        self.assertEqual((log.id_emprestimo, log.event_type), (emprestimo, LogEmprestimo.Evento.CRIADO))

    def test_log_guarda_o_ip(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(), ip='10.0.0.1')
        self.assertEqual(LogEmprestimo.objects.get().ip_aparelho, '10.0.0.1')

    def test_log_sem_ip_fica_nulo(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())
        self.assertIsNone(LogEmprestimo.objects.get().ip_aparelho)

    def test_log_do_morador_nao_tem_admin(self):
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(), ip='10.0.0.1')
        self.assertIsNone(LogEmprestimo.objects.get().id_admin)


def dados_post(**alteracoes):
    # o formulário chega como texto: a data vai no formato do <input type="date">
    dados = dados_emprestimo(**alteracoes)
    for campo in ('start_date', 'limit_date'):
        if isinstance(dados.get(campo), date):
            dados[campo] = dados[campo].isoformat()
    return dados


@FIXAR_HOJE
class EmprestimoFormTestCase(TestCase):
    def test_campo_de_data_usa_input_date(self):
        widget = EmprestimoForm().fields['limit_date'].widget
        self.assertEqual(widget.input_type, 'date')  # o Django tira o 'type' de attrs

    def test_data_minima_e_hoje(self):
        widget = EmprestimoForm().fields['limit_date'].widget
        self.assertEqual(widget.attrs['min'], HOJE.isoformat())

    def test_data_maxima_de_devolucao_conta_da_ultima_retirada(self):
        widget = EmprestimoForm().fields['limit_date'].widget
        # quinta-feira: 5º dia útil depois da última retirada possível (HOJE + 7)
        self.assertEqual(widget.attrs['max'], (HOJE + timedelta(days=14)).isoformat())

    def test_limites_sao_calculados_a_cada_formulario(self):
        # se fossem calculados no corpo da classe, ficariam presos ao dia em que o servidor subiu
        amanha = HOJE + timedelta(days=1)
        with mock.patch('django.utils.timezone.localdate', new=lambda: amanha):
            widget = EmprestimoForm().fields['limit_date'].widget
        self.assertEqual(widget.attrs['min'], amanha.isoformat())

    def test_formularios_nao_compartilham_os_limites(self):
        primeiro = EmprestimoForm()
        with mock.patch('django.utils.timezone.localdate', new=lambda: HOJE + timedelta(days=1)):
            EmprestimoForm()
        self.assertEqual(primeiro.fields['limit_date'].widget.attrs['min'], HOJE.isoformat())

    def test_quantidade_comeca_em_um(self):
        self.assertEqual(EmprestimoForm().fields['quant'].initial, 1)

    def test_aceita_dados_validos(self):
        form = EmprestimoForm(dados_post())
        self.assertTrue(form.is_valid())

    def test_converte_a_data_para_date(self):
        form = EmprestimoForm(dados_post())
        form.is_valid()
        self.assertEqual(form.cleaned_data['limit_date'], HOJE + timedelta(days=1))

    def test_recusa_quantidade_zero(self):
        form = EmprestimoForm(dados_post(quant=0))
        self.assertIn('quant', form.errors)

    def test_recusa_email_invalido(self):
        form = EmprestimoForm(dados_post(email='pedro'))
        self.assertIn('email', form.errors)

    def test_aceita_ap_e_vaga(self):
        form = EmprestimoForm(dados_post(ap_vaga='105D Vaga A'))
        self.assertTrue(form.is_valid())

    def test_recusa_ap_vaga_com_mais_de_50_caracteres(self):
        form = EmprestimoForm(dados_post(ap_vaga='A' * 51))
        self.assertIn('ap_vaga', form.errors)

    def test_ap_vaga_tem_texto_de_ajuda(self):
        self.assertIn('Ex.:', EmprestimoForm().fields['ap_vaga'].help_text)

    def test_nome_tem_texto_de_ajuda(self):
        self.assertIn('Ex.:', EmprestimoForm().fields['nome'].help_text)

    def test_recusa_data_em_formato_invalido(self):
        form = EmprestimoForm({**dados_post(), 'limit_date': '31/02/2026'})
        self.assertIn('limit_date', form.errors)

    def test_todos_os_campos_sao_obrigatorios_menos_a_retirada(self):
        form = EmprestimoForm({})
        self.assertEqual(set(form.errors), {'nome', 'ap_vaga', 'email', 'telefone', 'quant', 'limit_date'})

    def test_nao_valida_o_intervalo_de_datas(self):
        # min/max só limitam o navegador; a regra de negócio fica no EmprestimoService
        form = EmprestimoForm(dados_post(limit_date=HOJE - timedelta(days=1)))
        self.assertTrue(form.is_valid())

    def test_campo_de_retirada_usa_input_date(self):
        widget = EmprestimoForm().fields['start_date'].widget
        self.assertEqual(widget.input_type, 'date')

    def test_retirada_padrao_e_hoje_em_dia_util(self):
        form = EmprestimoForm()
        self.assertEqual(form.fields['start_date'].initial, HOJE)

    def test_retirada_padrao_no_sabado_e_a_segunda(self):
        with mock.patch('django.utils.timezone.localdate', new=lambda: SABADO):
            form = EmprestimoForm()
        self.assertEqual(form.fields['start_date'].initial, SEGUNDA)

    def test_retirada_padrao_no_domingo_e_a_segunda(self):
        with mock.patch('django.utils.timezone.localdate', new=lambda: DOMINGO):
            form = EmprestimoForm()
        self.assertEqual(form.fields['start_date'].initial, SEGUNDA)

    def test_retirada_minima_e_hoje(self):
        widget = EmprestimoForm().fields['start_date'].widget
        self.assertEqual(widget.attrs['min'], HOJE.isoformat())

    def test_retirada_maxima_e_cinco_dias_uteis_a_frente(self):
        widget = EmprestimoForm().fields['start_date'].widget
        self.assertEqual(widget.attrs['max'], PRAZO_LIMITE.isoformat())

    def test_devolucao_informa_o_prazo_em_dias_uteis_ao_navegador(self):
        widget = EmprestimoForm().fields['limit_date'].widget
        self.assertEqual(widget.attrs['data-prazo-dias-uteis'], 5)

    def test_retirada_e_opcional(self):
        form = EmprestimoForm(dados_post())
        self.assertNotIn('start_date', form.errors)

    def test_retirada_vazia_fica_sem_valor(self):
        form = EmprestimoForm(dados_post(start_date=''))
        form.is_valid()
        self.assertIsNone(form.cleaned_data['start_date'])

    def test_converte_a_retirada_para_date(self):
        form = EmprestimoForm(dados_post(start_date=SEGUNDA))
        form.is_valid()
        self.assertEqual(form.cleaned_data['start_date'], SEGUNDA)

    def test_recusa_retirada_em_formato_invalido(self):
        form = EmprestimoForm({**dados_post(), 'start_date': '31/02/2026'})
        self.assertIn('start_date', form.errors)

    def test_nao_valida_o_intervalo_da_retirada(self):
        # min/max só limitam o navegador; a regra de negócio fica no EmprestimoService
        form = EmprestimoForm(dados_post(start_date=HOJE - timedelta(days=1)))
        self.assertTrue(form.is_valid())


class TelefoneEmprestimoFormTestCase(TestCase):
    """A máscara é livre e o zero antes do DDD é descartado; o formulário entrega só os dígitos."""

    def telefone_limpo(self, telefone):
        form = EmprestimoForm(dados_post(telefone=telefone))
        form.is_valid()
        return form.cleaned_data.get('telefone')

    def erros(self, telefone):
        return EmprestimoForm(dados_post(telefone=telefone)).errors

    def test_aceita_celular_com_mascara(self):
        self.assertEqual(self.telefone_limpo('(12) 99999-9999'), '12999999999')

    def test_aceita_celular_so_com_digitos(self):
        self.assertEqual(self.telefone_limpo('12999999999'), '12999999999')

    def test_aceita_celular_sem_parenteses(self):
        self.assertEqual(self.telefone_limpo('12 99999-9999'), '12999999999')

    def test_aceita_telefone_fixo(self):
        self.assertEqual(self.telefone_limpo('(12) 3456-7890'), '1234567890')

    def test_descarta_o_zero_antes_do_ddd(self):
        self.assertEqual(self.telefone_limpo('012999999999'), '12999999999')

    def test_descarta_o_zero_antes_do_ddd_com_mascara(self):
        self.assertEqual(self.telefone_limpo('(012) 99999-9999'), '12999999999')

    def test_recusa_telefone_sem_ddd(self):
        self.assertIn('telefone', self.erros('99999-9999'))

    def test_recusa_ddd_com_zero(self):
        self.assertIn('telefone', self.erros('(10) 99999-9999'))

    def test_recusa_dois_zeros_antes_do_ddd(self):
        self.assertIn('telefone', self.erros('0012999999999'))

    def test_recusa_celular_sem_o_nove(self):
        self.assertIn('telefone', self.erros('(12) 89999-9999'))

    def test_recusa_fixo_comecando_com_nove(self):
        self.assertIn('telefone', self.erros('(12) 9999-9999'))

    def test_recusa_letras(self):
        self.assertIn('telefone', self.erros('(12) 9999a-9999'))

    def test_recusa_codigo_do_pais(self):
        self.assertIn('telefone', self.erros('+55 12 99999-9999'))

    def test_erro_explica_o_formato(self):
        self.assertIn('Informe um telefone com DDD.', self.erros('99999-9999')['telefone'][0])

    def test_telefone_tem_texto_de_ajuda(self):
        self.assertIn('(12) 99999-9999', EmprestimoForm().fields['telefone'].help_text)

    def test_campo_de_telefone_usa_input_tel(self):
        self.assertEqual(EmprestimoForm().fields['telefone'].widget.input_type, 'tel')


@FIXAR_HOJE
class EmprestimoCreateViewTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)
        self.url = reverse('estoque:emprestimo_create', args=[self.item.pk])

    def test_anonimo_acessa_o_formulario(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)

    def test_usa_o_template_de_emprestimo(self):
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, 'estoque/emprestimo_form.html')

    def test_pagina_mostra_o_item(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Emprestar: Caixa de som')

    def test_pagina_limita_as_datas_no_navegador(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'min="{HOJE.isoformat()}"')

    def test_item_inexistente_retorna_404(self):
        resposta = self.client.get(reverse('estoque:emprestimo_create', args=[self.item.pk + 1]))
        self.assertEqual(resposta.status_code, 404)

    def test_item_removido_retorna_404(self):
        self.item.is_active = False
        self.item.save()
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)

    def test_anonimo_registra_emprestimo(self):
        self.client.post(self.url, dados_post())
        self.assertTrue(Emprestimo.objects.exists())

    def test_sucesso_redireciona_para_a_lista(self):
        resposta = self.client.post(self.url, dados_post())
        self.assertRedirects(resposta, reverse('estoque:item_list'))

    def test_sucesso_mostra_mensagem(self):
        resposta = self.client.post(self.url, dados_post(), follow=True)
        self.assertContains(resposta, 'Empréstimo registrado.')

    def test_log_guarda_o_ip_do_cliente(self):
        self.client.post(self.url, dados_post(), REMOTE_ADDR='10.0.0.1')
        self.assertEqual(LogEmprestimo.objects.get().ip_aparelho, '10.0.0.1')

    def test_log_usa_o_ip_original_atras_do_proxy(self):
        self.client.post(self.url, dados_post(), HTTP_X_FORWARDED_FOR='10.0.0.2, 10.0.0.3')
        self.assertEqual(LogEmprestimo.objects.get().ip_aparelho, '10.0.0.2')

    def test_formulario_invalido_nao_registra_emprestimo(self):
        self.client.post(self.url, dados_post(quant=0))
        self.assertFalse(Emprestimo.objects.exists())

    def test_erro_do_service_reexibe_o_formulario(self):
        resposta = self.client.post(self.url, dados_post(quant=4))
        self.assertEqual(resposta.status_code, 200)

    def test_erro_do_service_aparece_na_pagina(self):
        resposta = self.client.post(self.url, dados_post(quant=4))
        self.assertContains(resposta, 'Quantidade indisponível. Disponível: 3.')

    def test_erro_do_service_nao_registra_emprestimo(self):
        self.client.post(self.url, dados_post(limit_date=HOJE - timedelta(days=1)))
        self.assertFalse(Emprestimo.objects.exists())

    def test_erro_mantem_os_dados_digitados(self):
        resposta = self.client.post(self.url, dados_post(nome='Pedro Souza/Sonic', quant=4))
        self.assertContains(resposta, 'value="Pedro Souza/Sonic"')

    def test_formulario_mostra_a_retirada_padrao_preenchida(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context['form']['start_date'].value(), HOJE)

    def test_pagina_carrega_o_script_das_datas(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'js/emprestimo_datas.js')

    def test_pagina_informa_o_prazo_ao_script(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'data-prazo-dias-uteis="5"')

    def test_anonimo_agenda_emprestimo(self):
        self.client.post(self.url, dados_post(start_date=HOJE + timedelta(days=1), limit_date=SEGUNDA))
        self.assertEqual(Emprestimo.objects.get().start_date, HOJE + timedelta(days=1))

    def test_retirada_vazia_usa_o_padrao(self):
        self.client.post(self.url, dados_post(start_date=''))
        self.assertEqual(Emprestimo.objects.get().start_date, HOJE)

    def test_retirada_no_sabado_nao_registra_emprestimo(self):
        self.client.post(self.url, dados_post(start_date=SABADO, limit_date=SEGUNDA))
        self.assertFalse(Emprestimo.objects.exists())

    def test_retirada_no_sabado_aparece_na_pagina(self):
        resposta = self.client.post(self.url, dados_post(start_date=SABADO, limit_date=SEGUNDA))
        self.assertContains(resposta, 'A data de retirada não pode cair no fim de semana.')


class SinalizarDevolucaoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=2)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.emprestimo = criar_emprestimo(self.item, self.pedro, quant=2)

    def test_muda_o_status_para_devolucao_sinalizada(self):
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertEqual(status_atual(self.emprestimo), DS)

    def test_aceita_email_com_maiusculas(self):
        EmprestimoService.sinalizar_devolucao(self.item, 'Pedro@TEST.com')
        self.assertEqual(status_atual(self.emprestimo), DS)

    def test_nao_altera_a_quantidade_emprestada(self):
        # o item só volta ao estoque quando o admin confirma
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 2)

    def test_sinaliza_todos_os_emprestimos_ativos_do_morador_no_item(self):
        outro = criar_emprestimo(self.item, self.pedro)
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertEqual([status_atual(self.emprestimo), status_atual(outro)], [DS, DS])

    def test_nao_sinaliza_emprestimo_de_outro_morador(self):
        ana = Morador.objects.create(nome='Ana/Calvin', ap_vaga='102J Vaga B', email='ana@test.com', telefone='12988888888')
        da_ana = criar_emprestimo(self.item, ana)
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertEqual(status_atual(da_ana), AT)

    def test_nao_sinaliza_emprestimo_de_outro_item(self):
        escada = ItemCASD.objects.create(nome='Escada', quant_total=1, quant_emprestada=1)
        da_escada = criar_emprestimo(escada, self.pedro)
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertEqual(status_atual(da_escada), AT)

    def test_nao_altera_emprestimo_ja_devolvido(self):
        devolvido = criar_emprestimo(self.item, self.pedro, status=DE)
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertEqual(status_atual(devolvido), DE)

    def test_recusa_email_sem_emprestimo(self):
        with self.assertRaisesMessage(ValidationError, 'Nenhum empréstimo ativo'):
            EmprestimoService.sinalizar_devolucao(self.item, 'ninguem@test.com')

    def test_recusa_sinalizar_duas_vezes(self):
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        with self.assertRaises(ValidationError):
            EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')

    def test_cria_um_log_por_emprestimo_sinalizado(self):
        criar_emprestimo(self.item, self.pedro)
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        logs = LogEmprestimo.objects.filter(event_type=LogEmprestimo.Evento.DEVOLUCAO_SINALIZADA)
        self.assertEqual(logs.count(), 2)

    def test_log_guarda_o_ip(self):
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com', ip='10.0.0.1')
        self.assertEqual(LogEmprestimo.objects.get().ip_aparelho, '10.0.0.1')

    def test_log_do_morador_nao_tem_admin(self):
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertIsNone(LogEmprestimo.objects.get().id_admin)

    def test_recusa_nao_cria_log(self):
        with self.assertRaises(ValidationError):
            EmprestimoService.sinalizar_devolucao(self.item, 'ninguem@test.com')
        self.assertFalse(LogEmprestimo.objects.exists())


@FIXAR_HOJE
class SinalizarEmprestimoAgendadoTestCase(TestCase):
    """Enquanto a retirada não chega, o morador não pode sinalizar a devolução."""

    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=2)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.agendado = criar_emprestimo(self.item, self.pedro, quant=2, start_date=HOJE + timedelta(days=1))

    def test_recusa_informando_que_nao_ha_emprestimo_ativo(self):
        with self.assertRaisesMessage(ValidationError, 'Nenhum empréstimo ativo'):
            EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')

    def test_recusa_nao_muda_o_status(self):
        with self.assertRaises(ValidationError):
            EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertEqual(status_atual(self.agendado), AT)

    def test_recusa_nao_cria_log(self):
        with self.assertRaises(ValidationError):
            EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertFalse(LogEmprestimo.objects.exists())


class SinalizarComUmEmprestimoAgendadoTestCase(TestCase):
    def setUp(self):
        self.enterContext(FIXAR_HOJE)
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=2)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.iniciado = criar_emprestimo(self.item, self.pedro)
        self.agendado = criar_emprestimo(self.item, self.pedro, start_date=HOJE + timedelta(days=1))
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')

    def test_sinaliza_o_emprestimo_que_ja_comecou(self):
        self.assertEqual(status_atual(self.iniciado), DS)

    def test_nao_sinaliza_o_agendado(self):
        self.assertEqual(status_atual(self.agendado), AT)


@FIXAR_HOJE
class SinalizarNoDiaDaRetiradaTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=1)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.emprestimo = criar_emprestimo(self.item, self.pedro, start_date=HOJE)

    def test_no_dia_da_retirada_ja_pode_sinalizar(self):
        EmprestimoService.sinalizar_devolucao(self.item, 'pedro@test.com')
        self.assertEqual(status_atual(self.emprestimo), DS)


class ConfirmarDevolucaoTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=3)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.emprestimo = criar_emprestimo(self.item, self.pedro, status=DS, quant=2)

    def test_muda_o_status_para_devolvido(self):
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)
        self.assertEqual(status_atual(self.emprestimo), DE)

    def test_devolve_a_quantidade_do_emprestimo_ao_estoque(self):
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 1)

    def test_confirma_emprestimo_ativo_sem_sinalizacao(self):
        # o morador pode devolver o item sem sinalizar no site
        ativo = criar_emprestimo(self.item, self.pedro, status=AT)
        EmprestimoService.confirmar_devolucao(ativo, self.admin)
        self.assertEqual(status_atual(ativo), DE)

    def test_nao_altera_outros_emprestimos_do_item(self):
        outro = criar_emprestimo(self.item, self.pedro, status=DS)
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)
        self.assertEqual(status_atual(outro), DS)

    def test_recusa_confirmar_duas_vezes(self):
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)
        with self.assertRaisesMessage(ValidationError, 'já foi devolvido'):
            EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)

    def test_segunda_confirmacao_nao_devolve_a_quantidade_de_novo(self):
        # simula o clique duplo: a segunda chamada recebe a instância antiga, ainda com status DS
        copia_antiga = Emprestimo.objects.get(pk=self.emprestimo.pk)
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)
        with self.assertRaises(ValidationError):
            EmprestimoService.confirmar_devolucao(copia_antiga, self.admin)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 1)

    def test_registra_um_log_de_confirmacao(self):
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)
        log = LogEmprestimo.objects.get()
        self.assertEqual((log.id_emprestimo, log.event_type),
                         (self.emprestimo, LogEmprestimo.Evento.DEVOLUCAO_CONFIRMADA))

    def test_log_guarda_o_admin(self):
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin)
        self.assertEqual(LogEmprestimo.objects.get().id_admin, self.admin)

    def test_log_guarda_o_ip(self):
        EmprestimoService.confirmar_devolucao(self.emprestimo, self.admin, ip='10.0.0.1')
        self.assertEqual(LogEmprestimo.objects.get().ip_aparelho, '10.0.0.1')

    def test_recusa_nao_cria_log(self):
        devolvido = criar_emprestimo(self.item, self.pedro, status=DE)
        with self.assertRaises(ValidationError):
            EmprestimoService.confirmar_devolucao(devolvido, self.admin)
        self.assertFalse(LogEmprestimo.objects.exists())


@FIXAR_HOJE
class EmprestimoAgendadoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')

    def test_e_agendado_quando_a_retirada_ainda_nao_chegou(self):
        emprestimo = criar_emprestimo(self.item, self.pedro, start_date=HOJE + timedelta(days=1))
        self.assertTrue(emprestimo.agendado)

    def test_nao_e_agendado_quando_a_retirada_e_hoje(self):
        emprestimo = criar_emprestimo(self.item, self.pedro, start_date=HOJE)
        self.assertFalse(emprestimo.agendado)

    def test_nao_e_agendado_quando_a_retirada_ja_passou(self):
        emprestimo = criar_emprestimo(self.item, self.pedro, start_date=HOJE - timedelta(days=1))
        self.assertFalse(emprestimo.agendado)

    def test_nao_e_agendado_quando_ja_foi_devolvido(self):
        emprestimo = criar_emprestimo(self.item, self.pedro, status=DE, start_date=HOJE + timedelta(days=1))
        self.assertFalse(emprestimo.agendado)


class ListarAtivosTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')

    def test_inclui_ativos_e_com_devolucao_sinalizada(self):
        ativo = criar_emprestimo(self.item, self.pedro, status=AT)
        sinalizado = criar_emprestimo(self.item, self.pedro, status=DS)
        self.assertCountEqual(EmprestimoService.listar_ativos(), [ativo, sinalizado])

    def test_nao_inclui_devolvidos(self):
        devolvido = criar_emprestimo(self.item, self.pedro, status=DE)
        self.assertNotIn(devolvido, EmprestimoService.listar_ativos())

    def test_prazo_mais_proximo_vem_primeiro(self):
        depois = criar_emprestimo(self.item, self.pedro, limit_date=HOJE + timedelta(days=5))
        antes = criar_emprestimo(self.item, self.pedro, limit_date=HOJE + timedelta(days=1))
        self.assertEqual(list(EmprestimoService.listar_ativos()), [antes, depois])

    def test_ler_item_e_morador_nao_gera_consultas_extras(self):
        for _ in range(3):
            criar_emprestimo(self.item, self.pedro)
        with self.assertNumQueries(1):
            for emprestimo in EmprestimoService.listar_ativos():
                emprestimo.id_item.nome
                emprestimo.id_morador.nome


class EmprestimoListAgendadoViewTestCase(TestCase):
    def setUp(self):
        self.enterContext(FIXAR_HOJE)
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.ana = Morador.objects.create(nome='Ana/Calvin', ap_vaga='102J Vaga B', email='ana@test.com', telefone='12988888888')
        criar_emprestimo(self.item, self.pedro, start_date=HOJE + timedelta(days=1))
        criar_emprestimo(self.item, self.ana)
        self.client.force_login(criar_admin())
        self.resposta = self.client.get(reverse('estoque:emprestimo_list'))

    def test_agendado_mostra_a_data_de_retirada(self):
        self.assertContains(self.resposta, 'Agendado para 06/11', count=1)

    def test_emprestimo_que_ja_comecou_continua_ativo(self):
        self.assertContains(self.resposta, '<td>Ativo</td>', count=1, html=True)


class DevolucaoSinalizarViewTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3, quant_emprestada=1)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.emprestimo = criar_emprestimo(self.item, self.pedro)
        self.url = reverse('estoque:devolucao_sinalizar', args=[self.item.pk])

    def test_anonimo_acessa_o_formulario(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)

    def test_usa_o_template_de_devolucao(self):
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, 'estoque/devolucao_form.html')

    def test_item_removido_retorna_404(self):
        self.item.is_active = False
        self.item.save()
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)

    def test_lista_de_itens_tem_o_botao_devolver(self):
        resposta = self.client.get(reverse('estoque:item_list'))
        self.assertContains(resposta, self.url)

    def test_anonimo_sinaliza_a_devolucao(self):
        self.client.post(self.url, {'email': 'pedro@test.com'})
        self.assertEqual(status_atual(self.emprestimo), DS)

    def test_sucesso_redireciona_para_a_lista(self):
        resposta = self.client.post(self.url, {'email': 'pedro@test.com'})
        self.assertRedirects(resposta, reverse('estoque:item_list'))

    def test_sucesso_mostra_mensagem(self):
        resposta = self.client.post(self.url, {'email': 'pedro@test.com'}, follow=True)
        self.assertContains(resposta, 'Devolução sinalizada.')

    def test_log_guarda_o_ip_do_cliente(self):
        self.client.post(self.url, {'email': 'pedro@test.com'}, REMOTE_ADDR='10.0.0.1')
        self.assertEqual(LogEmprestimo.objects.get().ip_aparelho, '10.0.0.1')

    def test_email_invalido_nao_sinaliza(self):
        self.client.post(self.url, {'email': 'pedro'})
        self.assertEqual(status_atual(self.emprestimo), AT)

    def test_erro_do_service_aparece_na_pagina(self):
        resposta = self.client.post(self.url, {'email': 'ninguem@test.com'})
        self.assertContains(resposta, 'Nenhum empréstimo ativo deste item para este e-mail.')


class EmprestimoListViewTestCase(TestCase):
    def setUp(self):
        self.url = reverse('estoque:emprestimo_list')
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')

    def test_anonimo_e_redirecionado_para_o_login(self):
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, f"{reverse('autenticacao:login')}?next={self.url}")

    def test_admin_acessa_a_lista(self):
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, 'estoque/emprestimo_list.html')

    def test_mostra_morador_com_apartamento(self):
        criar_emprestimo(self.item, self.pedro)
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Pedro/Sonic (101J Vaga A)')

    def test_mostra_a_data_no_formato_brasileiro(self):
        criar_emprestimo(self.item, self.pedro, limit_date=date(2026, 11, 20))
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '20/11/2026')

    def test_mostra_o_rotulo_do_status(self):
        criar_emprestimo(self.item, self.pedro, status=DS)
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Devolução sinalizada')

    def test_tem_o_botao_de_confirmar(self):
        emprestimo = criar_emprestimo(self.item, self.pedro)
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, reverse('estoque:devolucao_confirmar', args=[emprestimo.pk]))

    def test_sem_emprestimos_mostra_aviso(self):
        criar_emprestimo(self.item, self.pedro, status=DE)
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Nenhum empréstimo ativo.')

    def test_cabecalho_tem_link_para_o_admin(self):
        self.client.force_login(criar_admin())
        resposta = self.client.get(reverse('estoque:item_list'))
        self.assertContains(resposta, f'href="{self.url}"')

    def test_cabecalho_nao_tem_link_para_o_anonimo(self):
        resposta = self.client.get(reverse('estoque:item_list'))
        self.assertNotContains(resposta, f'href="{self.url}"')

    def test_mostra_o_telefone_formatado(self):
        criar_emprestimo(self.item, self.pedro)
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '(12) 99999-9999')


class DevolucaoConfirmarViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3, quant_emprestada=1)
        self.pedro = Morador.objects.create(nome='Pedro/Sonic', ap_vaga='101J Vaga A', email='pedro@test.com', telefone='12999999999')
        self.emprestimo = criar_emprestimo(self.item, self.pedro, status=DS)
        self.url = reverse('estoque:devolucao_confirmar', args=[self.emprestimo.pk])

    def test_anonimo_e_redirecionado_para_o_login(self):
        resposta = self.client.post(self.url)
        self.assertRedirects(resposta, f"{reverse('autenticacao:login')}?next={self.url}",
                             fetch_redirect_response=False)

    def test_anonimo_nao_confirma(self):
        self.client.post(self.url)
        self.assertEqual(status_atual(self.emprestimo), DS)

    def test_get_nao_e_permitido(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 405)

    def test_emprestimo_inexistente_retorna_404(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(reverse('estoque:devolucao_confirmar', args=[self.emprestimo.pk + 1]))
        self.assertEqual(resposta.status_code, 404)

    def test_admin_confirma_a_devolucao(self):
        self.client.force_login(self.admin)
        self.client.post(self.url)
        self.assertEqual(status_atual(self.emprestimo), DE)

    def test_log_guarda_o_admin_logado(self):
        self.client.force_login(self.admin)
        self.client.post(self.url)
        self.assertEqual(LogEmprestimo.objects.get().id_admin, self.admin)

    def test_sucesso_volta_para_a_lista_de_emprestimos(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(self.url)
        self.assertRedirects(resposta, reverse('estoque:emprestimo_list'))

    def test_sucesso_mostra_mensagem(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(self.url, follow=True)
        self.assertContains(resposta, 'Devolução confirmada.')

    def test_confirmar_de_novo_mostra_erro(self):
        self.client.force_login(self.admin)
        self.client.post(self.url)
        resposta = self.client.post(self.url, follow=True)
        self.assertContains(resposta, 'Este empréstimo já foi devolvido.')