from datetime import date, timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .forms import EmprestimoForm
from .models import Emprestimo, ItemCASD, LogEmprestimo, Morador
from .services import PRAZO_MAX_DIAS, EmprestimoService
from .helpers_tests import HOJE, FIXAR_HOJE, AT, DS, DE, criar_emprestimo, criar_admin, status_atual


def dados_emprestimo(**alteracoes):
    dados = {
        'nome': 'Pedro',
        'ap': '101J',
        'email': 'pedro@test.com',
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
        emprestimo = self.criar_com_data(PRAZO_MAX_DIAS)
        self.assertEqual(emprestimo.limit_date, HOJE + timedelta(days=PRAZO_MAX_DIAS))

    def test_recusa_um_dia_alem_do_prazo_maximo(self):
        with self.assertRaisesMessage(ValidationError, f'{PRAZO_MAX_DIAS} dias'):
            self.criar_com_data(PRAZO_MAX_DIAS + 1)

    def test_data_no_passado_tem_mensagem_propria(self):
        with self.assertRaisesMessage(ValidationError, 'passado'):
            self.criar_com_data(-1)


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
        Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo())
        self.assertEqual(Morador.objects.count(), 1)

    def test_reaproveita_o_morador_mesmo_com_maiusculas_no_email(self):
        Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(email='PEDRO@test.com'))
        self.assertEqual(Morador.objects.count(), 1)

    def test_atualiza_nome_e_ap_do_morador_existente(self):
        Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
        EmprestimoService.criar_emprestimo(self.item, dados_emprestimo(nome='Pedro Souza', ap='202J'))
        morador = Morador.objects.get()
        self.assertEqual((morador.nome, morador.ap), ('Pedro Souza', '202J'))


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
    dados['limit_date'] = dados['limit_date'].isoformat()
    return dados


@FIXAR_HOJE
class EmprestimoFormTestCase(TestCase):
    def test_campo_de_data_usa_input_date(self):
        widget = EmprestimoForm().fields['limit_date'].widget
        self.assertEqual(widget.input_type, 'date')  # o Django tira o 'type' de attrs

    def test_data_minima_e_hoje(self):
        widget = EmprestimoForm().fields['limit_date'].widget
        self.assertEqual(widget.attrs['min'], HOJE.isoformat())

    def test_data_maxima_e_o_fim_do_prazo(self):
        widget = EmprestimoForm().fields['limit_date'].widget
        self.assertEqual(widget.attrs['max'], (HOJE + timedelta(days=PRAZO_MAX_DIAS)).isoformat())

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

    def test_recusa_ap_com_mais_de_quatro_caracteres(self):
        form = EmprestimoForm(dados_post(ap='1010J'))
        self.assertIn('ap', form.errors)

    def test_recusa_data_em_formato_invalido(self):
        form = EmprestimoForm({**dados_post(), 'limit_date': '31/02/2026'})
        self.assertIn('limit_date', form.errors)

    def test_todos_os_campos_sao_obrigatorios(self):
        form = EmprestimoForm({})
        self.assertEqual(set(form.errors), {'nome', 'ap', 'email', 'quant', 'limit_date'})

    def test_nao_valida_o_intervalo_de_datas(self):
        # min/max só limitam o navegador; a regra de negócio fica no EmprestimoService
        form = EmprestimoForm(dados_post(limit_date=HOJE - timedelta(days=1)))
        self.assertTrue(form.is_valid())


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
        resposta = self.client.post(self.url, dados_post(nome='Pedro Souza', quant=4))
        self.assertContains(resposta, 'value="Pedro Souza"')


class SinalizarDevolucaoTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=2)
        self.pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
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
        ana = Morador.objects.create(nome='Ana', ap='102J', email='ana@test.com')
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


class ConfirmarDevolucaoTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=3)
        self.pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
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


class ListarAtivosTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5)
        self.pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')

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


class DevolucaoSinalizarViewTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3, quant_emprestada=1)
        self.pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
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
        self.pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')

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
        self.assertContains(resposta, 'Pedro (101J)')

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


class DevolucaoConfirmarViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3, quant_emprestada=1)
        self.pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
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