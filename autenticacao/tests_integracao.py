"""Testes de integração do app autenticacao.
Cada classe é um cenário: o setUp executa os passos pelo site (cadastro, login, logout).
"""
from django.contrib.messages import get_messages
from django.shortcuts import resolve_url
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Admin, LogAdmin

SENHA = 'Senha-Teste-8378'
# o hash de senha padrão é lento de propósito; nos testes, um hash simples basta
SENHA_RAPIDA = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
IP_DO_CADASTRO = '203.0.113.5'
IP_DO_LOGIN = '198.51.100.7'
IP_DO_LOGOUT = '198.51.100.8'


@SENHA_RAPIDA
class FluxoTestCase(TestCase):
    """Base dos cenários: reúne os passos que alguém daria pelo site."""

    def setUp(self):
        self.gestor = self.criar_conta('gestor@test.com', 'Gestor')
        self.cliente_gestor = Client()
        self.cliente_gestor.force_login(self.gestor)

    def criar_conta(self, email, nome):
        return Admin.objects.create_user(email=email, nome=nome, password=SENHA)

    # passos pelo site
    def cadastrar(self, cliente, nome, email, senha=SENHA, ip=IP_DO_CADASTRO):
        dados = {'nome': nome, 'email': email, 'senha': senha, 'confirmar_senha': senha}
        return cliente.post(reverse('autenticacao:cadastro'), dados, REMOTE_ADDR=ip)

    def entrar(self, cliente, email, senha=SENHA, ip=IP_DO_LOGIN):
        dados = {'email': email, 'senha': senha}
        return cliente.post(reverse('autenticacao:login'), dados, REMOTE_ADDR=ip)

    def sair(self, cliente, ip=IP_DO_LOGOUT):
        return cliente.post(reverse('autenticacao:logout'), REMOTE_ADDR=ip)

    def abrir_pagina_protegida(self, cliente):
        return cliente.get(reverse('autenticacao:cadastro'))

    # leituras do estado
    def sessao_de(self, cliente):
        return cliente.session.get('_auth_user_id') and int(cliente.session['_auth_user_id'])

    def eventos_de(self, admin):
        logs = LogAdmin.objects.filter(id_admin=admin).order_by('pk')
        return list(logs.values_list('event_type', flat=True))

    def ultimo_log_de(self, admin):
        return LogAdmin.objects.filter(id_admin=admin).order_by('pk').last()

    def mensagens(self, resposta):
        return [str(m) for m in get_messages(resposta.wsgi_request)]

    def url_de_login_para(self, destino):
        return f"{reverse('autenticacao:login')}?next={destino}"


class CadastroDeNovoAdminTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.resposta = self.cadastrar(self.cliente_gestor, 'Bia', 'bia@test.com')
        self.bia = Admin.objects.get(email='bia@test.com')

    def test_nova_conta_nasce_ativa_e_sem_poderes_de_gestor(self):
        self.assertEqual((self.bia.is_active, self.bia.is_staff, self.bia.is_superuser), (True, False, False))

    def test_senha_digitada_permite_entrar(self):
        self.assertTrue(self.bia.check_password(SENHA))

    def test_cadastro_volta_para_a_pagina_inicial(self):
        self.assertRedirects(self.resposta, resolve_url('estoque:item_list'), fetch_redirect_response=False)

    def test_cadastro_mostra_a_mensagem_de_sucesso(self):
        self.assertIn('Administrador cadastrado.', self.mensagens(self.resposta))

    def test_sessao_do_gestor_continua_a_mesma(self):
        self.assertEqual(self.sessao_de(self.cliente_gestor), self.gestor.pk)

    def test_log_de_criacao_aponta_para_a_conta_nova(self):
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA'])

    def test_log_de_criacao_guarda_o_ip_de_quem_cadastrou(self):
        self.assertEqual(self.ultimo_log_de(self.bia).ip_aparelho, IP_DO_CADASTRO)


class NovoAdminEntraTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar(self.cliente_gestor, 'Bia', 'bia@test.com')
        self.bia = Admin.objects.get(email='bia@test.com')
        self.cliente_bia = Client()
        self.resposta = self.entrar(self.cliente_bia, 'bia@test.com')

    def test_sessao_pertence_a_bia(self):
        self.assertEqual(self.sessao_de(self.cliente_bia), self.bia.pk)

    def test_login_leva_a_pagina_inicial(self):
        self.assertRedirects(self.resposta, resolve_url('estoque:item_list'), fetch_redirect_response=False)

    def test_rota_protegida_abre_para_bia(self):
        self.assertEqual(self.abrir_pagina_protegida(self.cliente_bia).status_code, 200)

    def test_bia_tambem_consegue_cadastrar_outro_admin(self):
        self.cadastrar(self.cliente_bia, 'Caio', 'caio@test.com')
        self.assertTrue(Admin.objects.filter(email='caio@test.com').exists())

    def test_log_tem_criacao_e_login_em_ordem(self):
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN'])

    def test_log_do_login_guarda_o_ip_do_login(self):
        self.assertEqual(self.ultimo_log_de(self.bia).ip_aparelho, IP_DO_LOGIN)


class NovoAdminSaiTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar(self.cliente_gestor, 'Bia', 'bia@test.com')
        self.bia = Admin.objects.get(email='bia@test.com')
        self.cliente_bia = Client()
        self.entrar(self.cliente_bia, 'bia@test.com')
        self.abrir_pagina_protegida(self.cliente_bia)
        self.resposta = self.sair(self.cliente_bia)

    def test_sessao_e_encerrada(self):
        self.assertIsNone(self.sessao_de(self.cliente_bia))

    def test_logout_leva_a_pagina_inicial(self):
        self.assertRedirects(self.resposta, resolve_url('estoque:item_list'), fetch_redirect_response=False)

    def test_rota_protegida_volta_a_exigir_login(self):
        resposta = self.abrir_pagina_protegida(self.cliente_bia)
        url = reverse('autenticacao:cadastro')
        self.assertRedirects(resposta, self.url_de_login_para(url), fetch_redirect_response=False)

    def test_log_registra_o_ciclo_inteiro_em_ordem(self):
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN', 'LOGOUT'])

    def test_log_do_logout_guarda_o_ip_do_logout(self):
        self.assertEqual(self.ultimo_log_de(self.bia).ip_aparelho, IP_DO_LOGOUT)

    def test_sair_de_novo_nao_gera_outro_log(self):
        self.sair(self.cliente_bia)
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN', 'LOGOUT'])

    def test_entrar_de_novo_gera_um_novo_login(self):
        self.entrar(self.cliente_bia, 'bia@test.com')
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN', 'LOGOUT', 'LOGIN'])


class DoisAdminsLogadosTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.ana = self.criar_conta('ana@test.com', 'Ana')
        self.bia = self.criar_conta('bia@test.com', 'Bia')
        self.cliente_ana = Client()
        self.cliente_bia = Client()
        self.entrar(self.cliente_ana, 'ana@test.com')
        self.entrar(self.cliente_bia, 'bia@test.com')

    def test_cada_navegador_tem_a_sua_sessao(self):
        sessoes = (self.sessao_de(self.cliente_ana), self.sessao_de(self.cliente_bia))
        self.assertEqual(sessoes, (self.ana.pk, self.bia.pk))

    def test_sair_de_um_nao_derruba_o_outro(self):
        self.sair(self.cliente_bia)
        self.assertEqual(self.sessao_de(self.cliente_ana), self.ana.pk)

    def test_logout_de_bia_nao_aparece_no_log_da_ana(self):
        self.sair(self.cliente_bia)
        self.assertEqual(self.eventos_de(self.ana), ['CONTA_CRIADA', 'LOGIN'])

    def test_logout_de_bia_aparece_no_log_dela(self):
        self.sair(self.cliente_bia)
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN', 'LOGOUT'])


class LoginComFalhasDepoisCorretoTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.bia = self.criar_conta('bia@test.com', 'Bia')
        self.cliente_bia = Client()
        self.resposta_errada = self.entrar(self.cliente_bia, 'bia@test.com', senha='senha-errada')
        self.entrar(self.cliente_bia, 'bia@test.com', senha='outra-errada')

    def test_falhas_nao_abrem_sessao(self):
        self.assertIsNone(self.sessao_de(self.cliente_bia))

    def test_falhas_mostram_o_erro_na_pagina_de_login(self):
        erros = self.resposta_errada.context['form'].non_field_errors()
        self.assertIn('Email ou senha incorretos.', erros)

    def test_falhas_nao_deixam_rastro_no_log(self):
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA'])

    def test_login_correto_depois_das_falhas_abre_a_sessao(self):
        self.entrar(self.cliente_bia, 'bia@test.com')
        self.assertEqual(self.sessao_de(self.cliente_bia), self.bia.pk)

    def test_login_correto_depois_das_falhas_gera_um_unico_login(self):
        self.entrar(self.cliente_bia, 'bia@test.com')
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN'])


class ContaDesativadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.bia = self.criar_conta('bia@test.com', 'Bia')
        self.cliente_bia = Client()
        self.entrar(self.cliente_bia, 'bia@test.com')
        Admin.objects.filter(pk=self.bia.pk).update(is_active=False)

    def test_sessao_aberta_perde_o_acesso(self):
        resposta = self.abrir_pagina_protegida(self.cliente_bia)
        url = reverse('autenticacao:cadastro')
        self.assertRedirects(resposta, self.url_de_login_para(url), fetch_redirect_response=False)

    def test_novo_login_e_recusado(self):
        novo_navegador = Client()
        self.entrar(novo_navegador, 'bia@test.com')
        self.assertIsNone(self.sessao_de(novo_navegador))

    def test_recusa_mostra_a_mesma_mensagem_de_senha_errada(self):
        resposta = self.entrar(Client(), 'bia@test.com')
        self.assertIn('Email ou senha incorretos.', resposta.context['form'].non_field_errors())

    def test_recusa_nao_gera_log_de_login(self):
        self.entrar(Client(), 'bia@test.com')
        self.assertEqual(self.eventos_de(self.bia), ['CONTA_CRIADA', 'LOGIN'])

    def test_conta_reativada_volta_a_entrar(self):
        Admin.objects.filter(pk=self.bia.pk).update(is_active=True)
        novo_navegador = Client()
        self.entrar(novo_navegador, 'bia@test.com')
        self.assertEqual(self.sessao_de(novo_navegador), self.bia.pk)


class CadastroRecusadoTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.logs_antes = LogAdmin.objects.count()
        self.resposta = self.cadastrar(self.cliente_gestor, 'Bia', 'bia@test.com', senha='12345678')

    def test_nao_cria_a_conta(self):
        self.assertFalse(Admin.objects.filter(email='bia@test.com').exists())

    def test_nao_gera_nenhum_log(self):
        self.assertEqual(LogAdmin.objects.count(), self.logs_antes)

    def test_erro_aparece_no_campo_da_senha(self):
        self.assertIn('senha', self.resposta.context['form'].errors)

    def test_formulario_mantem_o_email_digitado(self):
        self.assertEqual(self.resposta.context['form']['email'].value(), 'bia@test.com')

    def test_senha_digitada_nao_volta_na_pagina(self):
        self.assertNotContains(self.resposta, '12345678')

    def test_sessao_do_gestor_continua_a_mesma(self):
        self.assertEqual(self.sessao_de(self.cliente_gestor), self.gestor.pk)


class EmailRepetidoEmOutraCaixaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.cadastrar(self.cliente_gestor, 'Bia', 'Bia@Test.com')
        self.bia = Admin.objects.get(nome='Bia')
        self.resposta = self.cadastrar(self.cliente_gestor, 'Outra Bia', 'BIA@test.COM')

    def test_segundo_cadastro_nao_cria_conta(self):
        self.assertEqual(Admin.objects.count(), 2)

    def test_erro_aparece_no_campo_do_email(self):
        self.assertIn('email', self.resposta.context['form'].errors)

    def test_segundo_cadastro_nao_gera_log_de_criacao(self):
        self.assertEqual(LogAdmin.objects.filter(event_type='CONTA_CRIADA').count(), 2)

    def test_login_em_outra_caixa_abre_a_sessao_da_conta_original(self):
        cliente = Client()
        self.entrar(cliente, 'bia@TEST.com')
        self.assertEqual(self.sessao_de(cliente), self.bia.pk)


class LoginPeloSiteEPainelTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.su = Admin.objects.create_superuser(email='su@test.com', nome='Superuser', password=SENHA)
        self.cliente_su = Client()
        self.entrar(self.cliente_su, 'su@test.com')
        self.bia = self.criar_conta('bia@test.com', 'Bia')
        self.cliente_bia = Client()
        self.entrar(self.cliente_bia, 'bia@test.com')

    def test_gestor_abre_o_painel(self):
        self.assertEqual(self.cliente_su.get(reverse('admin:index')).status_code, 200)

    def test_admin_comum_nao_abre_o_painel(self):
        self.assertEqual(self.cliente_bia.get(reverse('admin:index')).status_code, 302)

    def test_gestor_ve_no_painel_todos_os_logs_do_ciclo(self):
        self.sair(self.cliente_bia)
        resposta = self.cliente_su.get(reverse('admin:autenticacao_logadmin_changelist'))
        self.assertEqual(resposta.context['cl'].result_count, LogAdmin.objects.count())