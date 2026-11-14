"""
Testes de sistema.
Tudo é feito pela interface do sistema (as páginas do site e o comando verificar_atrasos),
sem chamar services nem models diretamente. Cada classe é um cenário: o setUp executa os
passos e cada teste confere um único resultado.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from autenticacao.models import Admin, LogAdmin
from estoque.helpers_tests import FIXAR_HOJE, HOJE
from estoque.models import Emprestimo, ItemCASD, ItemZeladoria, LogEmprestimo
from estoque.services import ZeladoriaService

SENHA = 'Senha-Teste-8378'
IP_DO_PROXY = '10.0.0.1'
IP_DO_USUARIO = '203.0.113.9'
ATRAS_PROXY = {'REMOTE_ADDR': IP_DO_PROXY, 'HTTP_X_FORWARDED_FOR': IP_DO_USUARIO}


# o hash de senha padrão é lento de propósito; nos testes, um hash simples basta
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SistemaTestCase(TestCase):
    """Base dos cenários: reúne os passos que alguém daria pelo site."""

    def setUp(self):
        # o FIXAR_HOJE aplicado na classe só vale para os métodos test_*, e não para o setUp
        self.enterContext(FIXAR_HOJE)
        self.visitante = Client()
        self.gestor = Admin.objects.create_user(email='gestor@test.com', nome='Gestor', password=SENHA)
        self.cliente_gestor = Client()
        self.entrar(self.cliente_gestor, 'gestor@test.com')

    # autenticacao
    def cadastrar_admin(self, cliente, nome, email, **extra):
        dados = {'nome': nome, 'email': email, 'senha': SENHA, 'confirmar_senha': SENHA}
        return cliente.post(reverse('autenticacao:cadastro'), dados, **extra)

    def entrar(self, cliente, email, **extra):
        return cliente.post(reverse('autenticacao:login'), {'email': email, 'senha': SENHA}, **extra)

    def sair(self, cliente, **extra):
        return cliente.post(reverse('autenticacao:logout'), **extra)

    def novo_admin_logado(self, nome='Bia', email='bia@test.com'):
        """O gestor cadastra uma conta, e a pessoa entra pelo próprio navegador."""
        self.cadastrar_admin(self.cliente_gestor, nome, email)
        cliente = Client()
        self.entrar(cliente, email)
        return Admin.objects.get(email=email), cliente

    # estoque (CASD)
    def cadastrar_item(self, cliente, nome='Caixa de som', quant_total=3):
        cliente.post(reverse('estoque:item_create'), {'nome': nome, 'quant_total': quant_total})
        return ItemCASD.objects.get(nome=nome, is_active=True)

    def emprestar(self, item, quant=1, nome='Pedro', email='pedro@test.com', dias=1):
        dados = {'nome': nome, 'ap': '101J', 'email': email, 'quant': quant,
                 'limit_date': (HOJE + timedelta(days=dias)).isoformat()}
        return self.visitante.post(reverse('estoque:emprestimo_create', args=[item.pk]), dados)

    def sinalizar_devolucao(self, item, email='pedro@test.com'):
        return self.visitante.post(reverse('estoque:devolucao_sinalizar', args=[item.pk]), {'email': email})

    def confirmar_devolucao(self, cliente, emprestimo, **extra):
        return cliente.post(reverse('estoque:devolucao_confirmar', args=[emprestimo.pk]), **extra)

    # estoque (zeladoria)
    def cadastrar_item_zeladoria(self, cliente, nome='Extensão', quant_total=5, **extra):
        dados = {'nome': nome, 'quant_total': quant_total, 'preco_unitario': ''}
        cliente.post(reverse('estoque:zeladoria_create'), dados, **extra)
        return ItemZeladoria.objects.get(nome=nome, is_active=True)

    # notificacao
    def rodar_verificador(self, dias_apos_hoje):
        """Executa o comando como se hoje fosse HOJE + dias_apos_hoje e devolve o que ele imprimiu."""
        saida = StringIO()
        dia = HOJE + timedelta(days=dias_apos_hoje)
        with mock.patch('django.utils.timezone.localdate', new=lambda: dia):
            call_command('verificar_atrasos', stdout=saida)
        return saida.getvalue()

    # leituras do estado
    def itens_da_listagem(self):
        return list(self.visitante.get(reverse('estoque:item_list')).context['itens'])

    def eventos_de(self, admin):
        logs = LogAdmin.objects.filter(id_admin=admin).order_by('pk')
        return list(logs.values_list('event_type', flat=True))

    def item_atual(self, item):
        return ItemCASD.objects.get(pk=item.pk)

    def url_de_login_para(self, destino):
        return f"{reverse('autenticacao:login')}?next={destino}"


class NovoAdminCadastraItemTestCase(SistemaTestCase):
    """O gestor cadastra um admin, o novo admin entra e cadastra um item para o estoque."""

    def setUp(self):
        super().setUp()
        self.bia, self.cliente_bia = self.novo_admin_logado()
        self.item = self.cadastrar_item(self.cliente_bia, quant_total=3)

    def test_item_aparece_na_listagem_publica(self):
        self.assertEqual(self.itens_da_listagem(), [self.item])

    def test_item_nasce_totalmente_disponivel(self):
        self.assertEqual(self.item.quant_disponivel, 3)

    def test_item_cadastrado_pode_ser_emprestado_por_um_visitante(self):
        self.emprestar(self.item, quant=1)
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_log_da_conta_tem_criacao_e_login(self):
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN'])

    def test_sessao_do_gestor_nao_foi_afetada(self):
        resposta = self.cliente_gestor.get(reverse('estoque:zeladoria_list'))
        self.assertEqual(resposta.status_code, 200)


class AdminIdentificadoNosLogsDoEstoqueTestCase(SistemaTestCase):
    """Quem entrou pelo autenticacao é quem aparece nos logs do estoque."""

    def setUp(self):
        super().setUp()
        self.bia, self.cliente_bia = self.novo_admin_logado()
        self.item_zeladoria = self.cadastrar_item_zeladoria(self.cliente_bia)
        self.item = self.cadastrar_item(self.cliente_bia, quant_total=3)
        self.emprestar(self.item, quant=2)
        self.emprestimo = Emprestimo.objects.get()
        self.confirmar_devolucao(self.cliente_bia, self.emprestimo)

    def test_historico_da_zeladoria_guarda_o_admin(self):
        self.assertEqual(ZeladoriaService.historico(self.item_zeladoria).first().id_admin, self.bia)

    def test_log_da_confirmacao_guarda_o_admin(self):
        confirmacao = LogEmprestimo.objects.filter(id_emprestimo=self.emprestimo).order_by('pk').last()
        self.assertEqual(confirmacao.id_admin, self.bia)

    def test_log_do_pedido_do_morador_nao_tem_admin(self):
        pedido = LogEmprestimo.objects.filter(id_emprestimo=self.emprestimo).order_by('pk').first()
        self.assertIsNone(pedido.id_admin)

    def test_devolucao_confirmada_devolve_as_unidades_ao_estoque(self):
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 3)


class LogoutBloqueiaAsTelasDeAdminTestCase(SistemaTestCase):
    """Depois de sair, o antigo admin só enxerga o que qualquer visitante enxerga."""

    def setUp(self):
        super().setUp()
        self.bia, self.cliente_bia = self.novo_admin_logado()
        self.item = self.cadastrar_item(self.cliente_bia, quant_total=3)
        self.emprestar(self.item, quant=1)
        self.emprestimo = Emprestimo.objects.get()
        self.sinalizar_devolucao(self.item)
        self.sair(self.cliente_bia)

    def assertExigeLogin(self, resposta, url):
        self.assertRedirects(resposta, self.url_de_login_para(url), fetch_redirect_response=False)

    def test_cadastro_de_item_exige_login(self):
        url = reverse('estoque:item_create')
        self.assertExigeLogin(self.cliente_bia.get(url), url)

    def test_edicao_de_item_exige_login(self):
        url = reverse('estoque:item_update', args=[self.item.pk])
        self.assertExigeLogin(self.cliente_bia.get(url), url)

    def test_lista_de_emprestimos_exige_login(self):
        url = reverse('estoque:emprestimo_list')
        self.assertExigeLogin(self.cliente_bia.get(url), url)

    def test_lista_da_zeladoria_exige_login(self):
        url = reverse('estoque:zeladoria_list')
        self.assertExigeLogin(self.cliente_bia.get(url), url)

    def test_cadastro_de_outro_admin_exige_login(self):
        url = reverse('autenticacao:cadastro')
        self.assertExigeLogin(self.cliente_bia.get(url), url)

    def test_confirmar_devolucao_nao_tem_efeito(self):
        self.confirmar_devolucao(self.cliente_bia, self.emprestimo)
        self.emprestimo.refresh_from_db()
        self.assertEqual(self.emprestimo.status, Emprestimo.StatusEmprestimo.DS)

    def test_remover_item_nao_tem_efeito(self):
        self.cliente_bia.post(reverse('estoque:item_delete', args=[self.item.pk]))
        self.assertTrue(self.item_atual(self.item).is_active)

    def test_listagem_publica_continua_acessivel(self):
        resposta = self.cliente_bia.get(reverse('estoque:item_list'))
        self.assertEqual(resposta.status_code, 200)


class ContaDesativadaNoMeioDoFluxoTestCase(SistemaTestCase):
    """O admin é desativado depois de ter cadastrado um item e de ter uma devolução pendente."""

    def setUp(self):
        super().setUp()
        self.bia, self.cliente_bia = self.novo_admin_logado()
        self.item = self.cadastrar_item(self.cliente_bia, quant_total=3)
        self.emprestar(self.item, quant=1)
        self.emprestimo = Emprestimo.objects.get()
        self.sinalizar_devolucao(self.item)
        Admin.objects.filter(pk=self.bia.pk).update(is_active=False)

    def test_novo_item_nao_e_cadastrado(self):
        self.cliente_bia.post(reverse('estoque:item_create'), {'nome': 'Escada', 'quant_total': 2})
        self.assertEqual(ItemCASD.objects.count(), 1)

    def test_pedido_de_novo_item_vai_para_o_login(self):
        url = reverse('estoque:item_create')
        resposta = self.cliente_bia.post(url, {'nome': 'Escada', 'quant_total': 2})
        self.assertRedirects(resposta, self.url_de_login_para(url), fetch_redirect_response=False)

    def test_confirmacao_de_devolucao_nao_tem_efeito(self):
        self.confirmar_devolucao(self.cliente_bia, self.emprestimo)
        self.emprestimo.refresh_from_db()
        self.assertEqual(self.emprestimo.status, Emprestimo.StatusEmprestimo.DS)

    def test_item_ja_cadastrado_continua_na_listagem_publica(self):
        self.assertEqual(self.itens_da_listagem(), [self.item])

    def test_historico_da_conta_continua_no_banco(self):
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN'])


class MesmoIpEmTodosOsLogsTestCase(SistemaTestCase):
    """Atrás do proxy, o IP do usuário é o mesmo nos logs do autenticacao e do estoque."""

    def setUp(self):
        super().setUp()
        self.cadastrar_admin(self.cliente_gestor, 'Bia', 'bia@test.com')
        self.bia = Admin.objects.get(email='bia@test.com')
        self.cliente_bia = Client()
        self.entrar(self.cliente_bia, 'bia@test.com', **ATRAS_PROXY)
        self.item_zeladoria = self.cadastrar_item_zeladoria(self.cliente_bia, **ATRAS_PROXY)
        item = self.cadastrar_item(self.cliente_bia, quant_total=3)
        self.emprestar(item, quant=1)
        self.emprestimo = Emprestimo.objects.get()
        self.confirmar_devolucao(self.cliente_bia, self.emprestimo, **ATRAS_PROXY)

    def test_login_registra_o_ip_do_usuario_e_nao_o_do_proxy(self):
        log_do_login = LogAdmin.objects.get(id_admin=self.bia, event_type='LOGIN')
        self.assertEqual(log_do_login.ip_aparelho, IP_DO_USUARIO)

    def test_historico_da_zeladoria_registra_o_mesmo_ip(self):
        self.assertEqual(ZeladoriaService.historico(self.item_zeladoria).first().ip_aparelho, IP_DO_USUARIO)

    def test_confirmacao_da_devolucao_registra_o_mesmo_ip(self):
        confirmacao = LogEmprestimo.objects.filter(id_emprestimo=self.emprestimo).order_by('pk').last()
        self.assertEqual(confirmacao.ip_aparelho, IP_DO_USUARIO)


class EmprestimoVencidoNoVerificadorTestCase(SistemaTestCase):
    """O morador empresta pelo site, o prazo passa e o comando verificar_atrasos o lista. O prazo é HOJE + 1 dia."""

    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(self.cliente_gestor, 'Caixa de som', quant_total=3)
        self.emprestar(self.item, quant=2, dias=1)

    def test_no_dia_do_prazo_ainda_nao_ha_atraso(self):
        self.assertIn('Nenhum atraso encontrado.', self.rodar_verificador(1))

    def test_um_dia_depois_do_prazo_ja_e_atraso(self):
        self.assertIn('1d de atraso', self.rodar_verificador(2))

    def test_lista_o_item_emprestado(self):
        self.assertIn('Caixa de som x2', self.rodar_verificador(3))

    def test_lista_o_e_mail_do_morador(self):
        self.assertIn('pedro@test.com', self.rodar_verificador(3))

    def test_mostra_os_dias_de_atraso(self):
        self.assertIn('2d de atraso', self.rodar_verificador(3))


class DevolucaoSinalizadaDepoisDoPrazoTestCase(SistemaTestCase):
    def setUp(self):
        super().setUp()
        item = self.cadastrar_item(self.cliente_gestor, quant_total=3)
        self.emprestar(item, quant=2, dias=1)
        self.sinalizar_devolucao(item)

    def test_emprestimo_com_devolucao_sinalizada_sai_dos_atrasos(self):
        self.assertIn('Nenhum atraso encontrado.', self.rodar_verificador(3))


class DevolucaoConfirmadaDepoisDoPrazoTestCase(SistemaTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(self.cliente_gestor, quant_total=3)
        self.emprestar(self.item, quant=2, dias=1)
        self.confirmar_devolucao(self.cliente_gestor, Emprestimo.objects.get())

    def test_emprestimo_devolvido_sai_dos_atrasos(self):
        self.assertIn('Nenhum atraso encontrado.', self.rodar_verificador(3))

    def test_item_volta_a_ficar_totalmente_disponivel(self):
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 3)


class VariosAtrasosTestCase(SistemaTestCase):
    """Pedro tem prazo em HOJE + 1 dia (sexta) e Ana em HOJE + 4 dias (segunda)."""

    def setUp(self):
        super().setUp()
        item = self.cadastrar_item(self.cliente_gestor, quant_total=5)
        self.emprestar(item, quant=1, nome='Pedro', email='pedro@test.com', dias=1)
        self.emprestar(item, quant=1, nome='Ana', email='ana@test.com', dias=4)
        self.emprestimo_do_pedro = Emprestimo.objects.get(id_morador__email='pedro@test.com')

    def test_cabecalho_mostra_o_total_de_atrasos(self):
        self.assertIn('Empréstimos atrasados (2):', self.rodar_verificador(6))

    def test_o_mais_atrasado_vem_primeiro(self):
        saida = self.rodar_verificador(6)
        self.assertLess(saida.index('Pedro'), saida.index('Ana'))

    def test_so_o_prazo_vencido_aparece(self):
        self.assertNotIn('Ana', self.rodar_verificador(3))

    def test_depois_da_devolucao_de_um_so_resta_o_outro(self):
        self.confirmar_devolucao(self.cliente_gestor, self.emprestimo_do_pedro)
        self.assertIn('Empréstimos atrasados (1):', self.rodar_verificador(6))

    def test_quem_devolveu_deixa_de_ser_listado(self):
        self.confirmar_devolucao(self.cliente_gestor, self.emprestimo_do_pedro)
        self.assertNotIn('Pedro', self.rodar_verificador(6))


class CabecalhoAcompanhaOLoginTestCase(SistemaTestCase):
    """Os links de admin no cabeçalho do estoque aparecem e somem conforme a sessão do autenticacao."""

    def setUp(self):
        super().setUp()
        self.admin = Admin.objects.create_user(email='bia@test.com', nome='Bia', password=SENHA)
        self.cliente = Client()
        self.url_zeladoria = reverse('estoque:zeladoria_list')
        self.url_emprestimos = reverse('estoque:emprestimo_list')

    def abrir_listagem(self):
        return self.cliente.get(reverse('estoque:item_list'))

    def test_visitante_nao_ve_o_link_da_zeladoria(self):
        self.assertNotContains(self.abrir_listagem(), f'href="{self.url_zeladoria}"')

    def test_visitante_nao_ve_o_link_dos_emprestimos(self):
        self.assertNotContains(self.abrir_listagem(), f'href="{self.url_emprestimos}"')

    def test_depois_do_login_aparece_o_link_da_zeladoria(self):
        self.entrar(self.cliente, 'bia@test.com')
        self.assertContains(self.abrir_listagem(), f'href="{self.url_zeladoria}"')

    def test_depois_do_login_aparece_o_link_dos_emprestimos(self):
        self.entrar(self.cliente, 'bia@test.com')
        self.assertContains(self.abrir_listagem(), f'href="{self.url_emprestimos}"')

    def test_depois_do_logout_some_o_link_da_zeladoria(self):
        self.entrar(self.cliente, 'bia@test.com')
        self.sair(self.cliente)
        self.assertNotContains(self.abrir_listagem(), f'href="{self.url_zeladoria}"')

    def test_depois_do_logout_some_o_link_dos_emprestimos(self):
        self.entrar(self.cliente, 'bia@test.com')
        self.sair(self.cliente)
        self.assertNotContains(self.abrir_listagem(), f'href="{self.url_emprestimos}"')