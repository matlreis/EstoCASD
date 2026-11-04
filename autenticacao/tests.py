from io import StringIO
from unittest import expectedFailure, mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.forms import PasswordInput
from django.shortcuts import resolve_url
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import LoginForm, SignUpForm
from .middleware import RequestAtualMiddleware, get_request_atual
from .models import Admin, LogAdmin
from .services import AutenticacaoService

SENHA = 'Senha-Teste-8378'
# o hash de senha padrão é lento de propósito; nos testes, um hash simples basta
SENHA_RAPIDA = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


def criar_admin(email='a@test.com', nome='Alice', senha=SENHA):
    return Admin.objects.create_user(email=email, nome=nome, password=senha)


def pagina_inicial():
    return resolve_url(settings.LOGIN_REDIRECT_URL)


@SENHA_RAPIDA
class AdminModelTestCase(TestCase):
    def test_create_user_guarda_hash_e_nao_a_senha(self):
        admin = criar_admin()
        self.assertNotEqual(admin.password, SENHA)

    def test_create_user_permite_conferir_a_senha(self):
        admin = criar_admin()
        self.assertTrue(admin.check_password(SENHA))

    def test_create_user_sem_email_falha(self):
        with self.assertRaises(ValueError):
            criar_admin(email='')

    def test_admin_comum_nao_e_gestor(self):
        admin = criar_admin()
        self.assertFalse(admin.is_superuser)

    def test_create_superuser_cria_gestor(self):
        admin = Admin.objects.create_superuser(email='g@test.com', nome='Gestor', password=SENHA)
        self.assertTrue(admin.is_superuser)

    def test_create_superuser_libera_o_painel(self):
        admin = Admin.objects.create_superuser(email='g@test.com', nome='Gestor', password=SENHA)
        self.assertTrue(admin.is_staff)

    def test_str_mostra_o_nome(self):
        admin = Admin(nome='Alice', email='a@test.com')
        texto = str(admin)
        self.assertEqual(texto, 'Alice')

    def test_admin_comum_nao_acessa_o_painel(self):
        admin = criar_admin()
        self.assertFalse(admin.is_staff)

    def test_create_user_normaliza_o_dominio_do_email(self):
        admin = criar_admin(email='a@TEST.COM')
        self.assertEqual(admin.email, 'a@test.com')

    def test_create_user_sem_senha_fica_com_senha_inutilizavel(self):
        admin = Admin.objects.create_user(email='a@test.com', nome='Alice')
        self.assertFalse(admin.has_usable_password())

    def test_admin_com_log_nao_pode_ser_apagado(self):
        admin = criar_admin()  # a criação da conta já gera um log
        with self.assertRaises(ProtectedError):
            admin.delete()

    def test_comando_createsuperuser_cria_gestor(self):
        with mock.patch.dict('os.environ', {'DJANGO_SUPERUSER_PASSWORD': SENHA}):
            call_command('createsuperuser', interactive=False, email='g@test.com', nome='Gestor', stdout=StringIO())
        admin = Admin.objects.get(email='g@test.com')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(SENHA))


@SENHA_RAPIDA
class AutenticacaoServiceTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()

    def test_cadastrar_cria_o_admin(self):
        admin = AutenticacaoService.cadastrar('Bob', 'b@test.com', SENHA)
        self.assertTrue(Admin.objects.filter(pk=admin.pk, email='b@test.com').exists())

    def test_cadastrar_com_email_repetido_falha(self):
        with self.assertRaises(IntegrityError):
            AutenticacaoService.cadastrar('Arthur', 'a@test.com', SENHA)

    def test_cadastrar_guarda_a_senha_informada(self):
        admin = AutenticacaoService.cadastrar('Bob', 'b@test.com', SENHA)
        self.assertTrue(admin.check_password(SENHA))

    def test_cadastrar_guarda_o_nome_informado(self):
        admin = AutenticacaoService.cadastrar('Bob', 'b@test.com', SENHA)
        self.assertEqual(admin.nome, 'Bob')

    def test_cadastrar_desfaz_a_conta_se_o_log_falhar(self):
        with mock.patch('autenticacao.signals.get_client_ip', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                AutenticacaoService.cadastrar('Bob', 'b@test.com', SENHA)
        self.assertFalse(Admin.objects.filter(email='b@test.com').exists())

    def test_autenticar_com_dados_corretos_devolve_o_admin(self):
        admin = AutenticacaoService.autenticar('a@test.com', SENHA)
        self.assertEqual(admin, self.admin)

    def test_autenticar_com_senha_errada_falha(self):
        with self.assertRaises(ValidationError):
            AutenticacaoService.autenticar('a@test.com', 'senha-errada')

    def test_autenticar_com_email_inexistente_falha(self):
        with self.assertRaises(ValidationError):
            AutenticacaoService.autenticar('inexistente@test.com', SENHA)

    def test_autenticar_conta_desativada_falha(self):
        self.admin.is_active = False
        self.admin.save()
        with self.assertRaises(ValidationError):
            AutenticacaoService.autenticar('a@test.com', SENHA)


@SENHA_RAPIDA
class SignUpFormTestCase(TestCase):
    def setUp(self):
        self.dados = {'nome': 'Bob', 'email': 'b@test.com', 'senha': SENHA, 'confirmar_senha': SENHA}

    def test_dados_validos_sao_aceitos(self):
        form = SignUpForm(self.dados)
        self.assertTrue(form.is_valid())

    def test_senhas_diferentes_sao_recusadas(self):
        form = SignUpForm({**self.dados, 'confirmar_senha': 'senha-diferente'})
        self.assertIn('confirmar_senha', form.errors)

    def test_senha_curta_e_recusada(self):
        form = SignUpForm({**self.dados, 'senha': 'S3n', 'confirmar_senha': 'S3n'})
        self.assertIn('senha', form.errors)

    def test_senha_so_numerica_e_recusada(self):
        form = SignUpForm({**self.dados, 'senha': '7364283783', 'confirmar_senha': '7364283783'})
        self.assertIn('senha', form.errors)

    def test_email_ja_cadastrado_e_recusado(self):
        criar_admin(email='b@test.com', nome='Bernardo')
        form = SignUpForm(self.dados)
        self.assertIn('email', form.errors)

    def test_email_invalido_e_recusado(self):
        form = SignUpForm({**self.dados, 'email': 'email-invalido'})
        self.assertIn('email', form.errors)

    def test_senha_parecida_com_o_email_e_recusada(self):
        form = SignUpForm({**self.dados, 'email': 'bernardosilveira@test.com',
                           'senha': 'bernardosilveira', 'confirmar_senha': 'bernardosilveira'})
        self.assertIn('senha', form.errors)

    def test_confirmacao_em_branco_e_recusada(self):
        form = SignUpForm({**self.dados, 'confirmar_senha': ''})
        self.assertIn('confirmar_senha', form.errors)

    def test_nome_so_com_espacos_e_recusado(self):
        form = SignUpForm({**self.dados, 'nome': '   '})
        self.assertIn('nome', form.errors)

    def test_nome_longo_demais_e_recusado(self):
        form = SignUpForm({**self.dados, 'nome': 'x' * 256})
        self.assertIn('nome', form.errors)

    def test_campos_de_senha_sao_mascarados(self):
        form = SignUpForm()
        self.assertIsInstance(form.fields['senha'].widget, PasswordInput)
        self.assertIsInstance(form.fields['confirmar_senha'].widget, PasswordInput)


class LoginFormTestCase(SimpleTestCase):
    def test_dados_validos_sao_aceitos(self):
        form = LoginForm({'email': 'a@test.com', 'senha': SENHA})
        self.assertTrue(form.is_valid())

    def test_email_invalido_e_recusado(self):
        form = LoginForm({'email': 'email-invalido', 'senha': SENHA})
        self.assertIn('email', form.errors)

    def test_senha_em_branco_e_recusada(self):
        form = LoginForm({'email': 'a@test.com', 'senha': ''})
        self.assertIn('senha', form.errors)

    def test_campo_de_senha_e_mascarado(self):
        form = LoginForm()
        self.assertIsInstance(form.fields['senha'].widget, PasswordInput)


@SENHA_RAPIDA
class LoginViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.url = reverse('autenticacao:login')
        self.credenciais = {'email': 'a@test.com', 'senha': SENHA}

    def test_pagina_de_login_e_publica(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)

    def test_login_valido_abre_a_sessao(self):
        self.client.post(self.url, self.credenciais)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)

    def test_login_valido_vai_para_a_pagina_inicial(self):
        resposta = self.client.post(self.url, self.credenciais)
        self.assertRedirects(resposta, pagina_inicial(), fetch_redirect_response=False)

    def test_login_com_senha_errada_nao_abre_a_sessao(self):
        self.client.post(self.url, {**self.credenciais, 'senha': 'senha-errada'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_com_senha_errada_mostra_o_erro(self):
        resposta = self.client.post(self.url, {**self.credenciais, 'senha': 'senha-errada'})
        self.assertContains(resposta, 'Email ou senha incorretos.')

    def test_login_com_email_invalido_nao_abre_a_sessao(self):
        self.client.post(self.url, {**self.credenciais, 'email': 'email-invalido'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_respeita_o_next_interno(self):
        destino = reverse('autenticacao:cadastro')
        resposta = self.client.post(f'{self.url}?next={destino}', self.credenciais)
        self.assertRedirects(resposta, destino)

    def test_login_ignora_o_next_para_outro_site(self):
        resposta = self.client.post(f'{self.url}?next=https://outro-site.com/', self.credenciais)
        self.assertRedirects(resposta, pagina_inicial(), fetch_redirect_response=False)

    def test_login_ignora_next_malicioso(self):
        maliciosos = ['//evil.com', 'https:///evil.com', 'http:evil.com', '/\\evil.com',
                      'javascript:alert(1)', 'ftp://evil.com', 'https://testserver.evil.com/']
        for destino in maliciosos:
            with self.subTest(destino=destino):
                resposta = self.client.post(self.url, self.credenciais, query_params={'next': destino})
                self.assertRedirects(resposta, pagina_inicial(), fetch_redirect_response=False)

    def test_login_com_next_vazio_vai_para_a_pagina_inicial(self):
        resposta = self.client.post(self.url, self.credenciais, query_params={'next': ''})
        self.assertRedirects(resposta, pagina_inicial(), fetch_redirect_response=False)

    def test_login_em_https_ignora_next_em_http(self):
        destino = f"http://testserver{reverse('autenticacao:cadastro')}"
        resposta = self.client.post(self.url, self.credenciais, query_params={'next': destino}, secure=True)
        self.assertRedirects(resposta, pagina_inicial(), fetch_redirect_response=False)

    def test_login_com_email_inexistente_mostra_o_mesmo_erro(self):
        resposta = self.client.post(self.url, {**self.credenciais, 'email': 'inexistente@test.com'})
        self.assertContains(resposta, 'Email ou senha incorretos.')

    def test_login_de_conta_desativada_e_recusado(self):
        self.admin.is_active = False
        self.admin.save()
        resposta = self.client.post(self.url, self.credenciais)
        self.assertContains(resposta, 'Email ou senha incorretos.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_conta_desativada_perde_a_sessao_ativa(self):
        self.client.force_login(self.admin)
        self.admin.is_active = False
        self.admin.save()
        cadastro = reverse('autenticacao:cadastro')
        resposta = self.client.get(cadastro)
        self.assertRedirects(resposta, f'{self.url}?next={cadastro}')

    def test_anonimo_volta_a_pagina_pedida_apos_o_login(self):
        cadastro = reverse('autenticacao:cadastro')
        pagina_de_login = self.client.get(cadastro).url
        resposta = self.client.post(pagina_de_login, self.credenciais)
        self.assertRedirects(resposta, cadastro)


@SENHA_RAPIDA
class LogoutViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.url = reverse('autenticacao:logout')

    def test_logout_por_post_encerra_a_sessao(self):
        self.client.force_login(self.admin)
        self.client.post(self.url)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_por_get_nao_e_permitido(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 405)

    def test_logout_por_get_mantem_a_sessao(self):
        self.client.force_login(self.admin)
        self.client.get(self.url)
        self.assertIn('_auth_user_id', self.client.session)

    def test_logout_sem_sessao_apenas_redireciona(self):
        resposta = self.client.post(self.url)
        self.assertRedirects(resposta, resolve_url(settings.LOGOUT_REDIRECT_URL), fetch_redirect_response=False)


@SENHA_RAPIDA
class CadastroViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.url = reverse('autenticacao:cadastro')
        self.dados = {'nome': 'Bob', 'email': 'b@test.com', 'senha': SENHA, 'confirmar_senha': SENHA}

    def test_anonimo_e_redirecionado_ao_login(self):
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, f"{reverse('autenticacao:login')}?next={self.url}")

    def test_anonimo_nao_cadastra_admin(self):
        self.client.post(self.url, self.dados)
        self.assertFalse(Admin.objects.filter(email='b@test.com').exists())

    def test_tela_de_cadastro_abre_para_admin_logado(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)

    def test_admin_logado_cadastra_outro_admin(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.dados)
        self.assertTrue(Admin.objects.filter(email='b@test.com').exists())

    def test_cadastro_valido_vai_para_a_pagina_inicial(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(self.url, self.dados)
        self.assertRedirects(resposta, pagina_inicial(), fetch_redirect_response=False)

    def test_cadastro_invalido_nao_cria_admin(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {**self.dados, 'confirmar_senha': 'outra-senha'})
        self.assertFalse(Admin.objects.filter(email='b@test.com').exists())

    def test_cadastro_invalido_mostra_o_formulario_de_novo(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(self.url, {**self.dados, 'confirmar_senha': 'outra-senha'})
        self.assertFormError(resposta.context['form'], 'confirmar_senha', 'As senhas não coincidem.')

    def test_conta_cadastrada_consegue_fazer_login(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.dados)
        novo_cliente = Client()
        novo_cliente.post(reverse('autenticacao:login'), {'email': 'b@test.com', 'senha': SENHA})
        novo_admin = Admin.objects.get(email='b@test.com')
        self.assertEqual(int(novo_cliente.session['_auth_user_id']), novo_admin.pk)

    def test_cadastro_ignora_permissoes_enviadas_no_post(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {**self.dados, 'is_superuser': 'on', 'is_staff': 'on'})
        novo_admin = Admin.objects.get(email='b@test.com')
        self.assertFalse(novo_admin.is_superuser)
        self.assertFalse(novo_admin.is_staff)

    def test_cadastro_mantem_a_sessao_do_admin_logado(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.dados)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)

    def test_cadastro_valido_mostra_a_mensagem_de_sucesso(self):
        self.client.force_login(self.admin)
        resposta = self.client.post(self.url, self.dados, follow=True)
        self.assertContains(resposta, 'Administrador cadastrado.')


class RotasProtegidasTestCase(TestCase):
    def test_anonimo_e_redirecionado_ao_login_nas_rotas_do_estoque(self):
        rotas = [
            reverse('estoque:item_create'),
            reverse('estoque:item_update', kwargs={'pk': 1}),
            reverse('estoque:item_delete', kwargs={'pk': 1}),
        ]
        for rota in rotas:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertRedirects(resposta, f"{reverse('autenticacao:login')}?next={rota}")


@SENHA_RAPIDA
class CsrfTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.cliente_com_csrf = Client(enforce_csrf_checks=True)

    def test_login_sem_token_e_recusado(self):
        resposta = self.cliente_com_csrf.post(reverse('autenticacao:login'), {'email': 'a@test.com', 'senha': SENHA})
        self.assertEqual(resposta.status_code, 403)

    def test_logout_sem_token_e_recusado(self):
        self.cliente_com_csrf.force_login(self.admin)
        resposta = self.cliente_com_csrf.post(reverse('autenticacao:logout'))
        self.assertEqual(resposta.status_code, 403)

    def test_cadastro_sem_token_e_recusado(self):
        self.cliente_com_csrf.force_login(self.admin)
        dados = {'nome': 'Bob', 'email': 'b@test.com', 'senha': SENHA, 'confirmar_senha': SENHA}
        resposta = self.cliente_com_csrf.post(reverse('autenticacao:cadastro'), dados)
        self.assertEqual(resposta.status_code, 403)

    def test_pagina_de_login_traz_o_token(self):
        resposta = self.client.get(reverse('autenticacao:login'))
        self.assertContains(resposta, 'csrfmiddlewaretoken')

    def test_pagina_de_cadastro_traz_o_token(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(reverse('autenticacao:cadastro'))
        # dois tokens: o do cadastro e o do botão "Sair", no cabeçalho do base.html
        self.assertContains(resposta, 'csrfmiddlewaretoken', count=2)


@SENHA_RAPIDA
class LogAdminSignalsTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        LogAdmin.objects.all().delete()  # descarta o log de criação da conta

    def tipos_de_log(self):
        return list(LogAdmin.objects.values_list('event_type', flat=True))

    def test_criar_conta_gera_log(self):
        criar_admin(email='b@test.com', nome='Bob')
        self.assertEqual(self.tipos_de_log(), ['CONTA_CRIADA'])

    def test_criar_conta_fora_de_uma_requisicao_nao_tem_ip(self):
        criar_admin(email='b@test.com', nome='Bob')
        self.assertIsNone(LogAdmin.objects.get().ip_aparelho)

    def test_criar_conta_pela_view_registra_o_ip(self):
        self.client.force_login(self.admin)
        LogAdmin.objects.all().delete()  # descarta o log do force_login
        dados = {'nome': 'Bob', 'email': 'b@test.com', 'senha': SENHA, 'confirmar_senha': SENHA}
        self.client.post(reverse('autenticacao:cadastro'), dados, REMOTE_ADDR='203.0.113.5')
        log = LogAdmin.objects.get(event_type='CONTA_CRIADA')
        self.assertEqual(log.ip_aparelho, '203.0.113.5')

    def test_login_gera_log(self):
        self.client.post(reverse('autenticacao:login'), {'email': 'a@test.com', 'senha': SENHA})
        self.assertEqual(self.tipos_de_log(), ['LOGIN'])

    def test_login_registra_o_admin(self):
        self.client.post(reverse('autenticacao:login'), {'email': 'a@test.com', 'senha': SENHA})
        self.assertEqual(LogAdmin.objects.get().id_admin, self.admin)

    def test_login_falho_nao_gera_log(self):
        self.client.post(reverse('autenticacao:login'), {'email': 'a@test.com', 'senha': 'errada'})
        self.assertEqual(self.tipos_de_log(), [])

    def test_logout_gera_log(self):
        self.client.force_login(self.admin)
        LogAdmin.objects.all().delete()  # descarta o log do force_login
        self.client.post(reverse('autenticacao:logout'))
        self.assertEqual(self.tipos_de_log(), ['LOGOUT'])

    def test_logout_sem_sessao_nao_gera_log(self):
        self.client.post(reverse('autenticacao:logout'))
        self.assertEqual(self.tipos_de_log(), [])

    def test_salvar_conta_existente_nao_gera_log(self):
        self.admin.nome = 'Alice Silva'
        self.admin.save()
        self.assertEqual(self.tipos_de_log(), [])

    def test_create_superuser_gera_um_unico_log(self):
        Admin.objects.create_superuser(email='g@test.com', nome='Gestor', password=SENHA)
        self.assertEqual(self.tipos_de_log(), ['CONTA_CRIADA'])

    def test_carga_de_fixture_nao_gera_log(self):
        # raw=True é o que o loaddata usa ao salvar cada objeto
        agora = timezone.now()
        Admin(email='f@test.com', nome='Fixture', created_at=agora, updated_at=agora).save_base(raw=True)
        self.assertEqual(self.tipos_de_log(), [])

    def test_login_registra_o_ip(self):
        self.client.post(reverse('autenticacao:login'), {'email': 'a@test.com', 'senha': SENHA}, REMOTE_ADDR='203.0.113.5')
        self.assertEqual(LogAdmin.objects.get().ip_aparelho, '203.0.113.5')

    def test_logout_registra_o_ip(self):
        self.client.force_login(self.admin)
        LogAdmin.objects.all().delete()  # descarta o log do force_login
        self.client.post(reverse('autenticacao:logout'), REMOTE_ADDR='203.0.113.5')
        self.assertEqual(LogAdmin.objects.get().ip_aparelho, '203.0.113.5')

    def test_logout_registra_o_admin(self):
        self.client.force_login(self.admin)
        LogAdmin.objects.all().delete()  # descarta o log do force_login
        self.client.post(reverse('autenticacao:logout'))
        self.assertEqual(LogAdmin.objects.get().id_admin, self.admin)


class RequestAtualMiddlewareTestCase(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/')

    def test_request_fica_disponivel_so_durante_a_chamada(self):
        vistos = []

        def view(request):
            vistos.append(get_request_atual())

        RequestAtualMiddleware(view)(self.request)
        self.assertEqual(vistos, [self.request])
        self.assertIsNone(get_request_atual())

    def test_request_e_limpo_mesmo_com_excecao(self):
        def view(request):
            raise RuntimeError

        with self.assertRaises(RuntimeError):
            RequestAtualMiddleware(view)(self.request)
        self.assertIsNone(get_request_atual())


@SENHA_RAPIDA
class PainelAdminTestCase(TestCase):
    def setUp(self):
        self.gestor = Admin.objects.create_superuser(email='g@test.com', nome='Gestor', password=SENHA)
        self.comum = criar_admin()
        self.log = LogAdmin.objects.filter(id_admin=self.comum).get()
        self.lista_de_contas = reverse('admin:autenticacao_admin_changelist')
        self.nova_conta = {'email': 'n@test.com', 'nome': 'Nova', 'usable_password': 'true',
                           'password1': SENHA, 'password2': SENHA}

    def salvar_conta(self, conta, **campos):
        url = reverse('admin:autenticacao_admin_change', args=[conta.pk])
        return self.client.post(url, {'email': conta.email, 'nome': conta.nome, 'is_active': 'on', **campos})

    def test_anonimo_nao_acessa_o_painel(self):
        resposta = self.client.get(self.lista_de_contas)
        self.assertRedirects(resposta, f"{reverse('autenticacao:login')}?next={self.lista_de_contas}")

    def test_admin_comum_nao_acessa_o_painel(self):
        self.client.force_login(self.comum)
        resposta = self.client.get(self.lista_de_contas)
        self.assertRedirects(resposta, f"{reverse('admin:login')}?next={self.lista_de_contas}",
                             fetch_redirect_response=False)

    def test_gestor_abre_as_telas_do_painel(self):
        self.client.force_login(self.gestor)
        telas = [
            self.lista_de_contas,
            reverse('admin:autenticacao_admin_add'),
            reverse('admin:autenticacao_admin_change', args=[self.comum.pk]),
            reverse('admin:autenticacao_logadmin_changelist'),
            reverse('admin:autenticacao_logadmin_change', args=[self.log.pk]),
        ]
        for tela in telas:
            with self.subTest(tela=tela):
                resposta = self.client.get(tela)
                self.assertEqual(resposta.status_code, 200)

    def test_marcar_gestor_libera_o_painel(self):
        self.client.force_login(self.gestor)
        self.salvar_conta(self.comum, is_superuser='on')
        self.comum.refresh_from_db()
        self.assertTrue(self.comum.is_superuser)
        self.assertTrue(self.comum.is_staff)

    def test_desmarcar_gestor_retira_o_painel(self):
        outro_gestor = Admin.objects.create_superuser(email='o@test.com', nome='Outro', password=SENHA)
        self.client.force_login(self.gestor)
        self.salvar_conta(outro_gestor)
        outro_gestor.refresh_from_db()
        self.assertFalse(outro_gestor.is_superuser)
        self.assertFalse(outro_gestor.is_staff)

    def test_conta_criada_no_painel_guarda_a_senha(self):
        self.client.force_login(self.gestor)
        self.client.post(reverse('admin:autenticacao_admin_add'), self.nova_conta)
        conta = Admin.objects.get(email='n@test.com')
        self.assertTrue(conta.check_password(SENHA))

    def test_conta_criada_no_painel_registra_o_ip(self):
        self.client.force_login(self.gestor)
        self.client.post(reverse('admin:autenticacao_admin_add'), self.nova_conta, REMOTE_ADDR='203.0.113.5')
        log = LogAdmin.objects.get(id_admin__email='n@test.com', event_type='CONTA_CRIADA')
        self.assertEqual(log.ip_aparelho, '203.0.113.5')

    def test_conta_nao_pode_ser_excluida(self):
        self.client.force_login(self.gestor)
        url = reverse('admin:autenticacao_admin_delete', args=[self.comum.pk])
        resposta = self.client.post(url, {'post': 'yes'})
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Admin.objects.filter(pk=self.comum.pk).exists())

    def test_log_nao_pode_ser_criado(self):
        self.client.force_login(self.gestor)
        resposta = self.client.post(reverse('admin:autenticacao_logadmin_add'), {'event_type': 'FALSO'})
        self.assertEqual(resposta.status_code, 403)

    def test_log_nao_pode_ser_editado(self):
        self.client.force_login(self.gestor)
        url = reverse('admin:autenticacao_logadmin_change', args=[self.log.pk])
        resposta = self.client.post(url, {'event_type': 'FALSO'})
        self.assertEqual(resposta.status_code, 403)
        self.log.refresh_from_db()
        self.assertEqual(self.log.event_type, 'CONTA_CRIADA')

    def test_log_nao_pode_ser_apagado(self):
        self.client.force_login(self.gestor)
        url = reverse('admin:autenticacao_logadmin_delete', args=[self.log.pk])
        resposta = self.client.post(url, {'post': 'yes'})
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(LogAdmin.objects.filter(pk=self.log.pk).exists())


# Bugs conhecidos: cada teste descreve o comportamento correto e falha hoje.
# Ao corrigir um bug, o teste vira "unexpected success": basta remover o @expectedFailure.
@SENHA_RAPIDA
class XForwardedForInvalidoTestCase(TestCase):
    # só falha no PostgreSQL: o SQLite aceita qualquer texto no campo de IP
    def setUp(self):
        self.admin = criar_admin()
        self.cliente = Client(raise_request_exception=False)  # devolve o 500 em vez de propagar a exceção

    @expectedFailure
    def test_login_nao_da_erro(self):
        credenciais = {'email': 'a@test.com', 'senha': SENHA}
        resposta = self.cliente.post(reverse('autenticacao:login'), credenciais, HTTP_X_FORWARDED_FOR='unknown')
        self.assertEqual(resposta.status_code, 302)

    @expectedFailure
    def test_logout_nao_da_erro(self):
        self.cliente.force_login(self.admin)
        resposta = self.cliente.post(reverse('autenticacao:logout'), HTTP_X_FORWARDED_FOR='unknown')
        self.assertEqual(resposta.status_code, 302)

    @expectedFailure
    def test_cadastro_nao_da_erro(self):
        self.cliente.force_login(self.admin)
        dados = {'nome': 'Bob', 'email': 'b@test.com', 'senha': SENHA, 'confirmar_senha': SENHA}
        resposta = self.cliente.post(reverse('autenticacao:cadastro'), dados, HTTP_X_FORWARDED_FOR='unknown')
        self.assertEqual(resposta.status_code, 302)


@SENHA_RAPIDA
class EmailSemDiferenciarMaiusculasTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.dados = {'nome': 'Arthur', 'senha': SENHA, 'confirmar_senha': SENHA}

    @expectedFailure
    def test_cadastro_recusa_email_repetido_com_dominio_em_maiusculas(self):
        cliente = Client(raise_request_exception=False)  # hoje a view devolve 500 (IntegrityError)
        cliente.force_login(self.admin)
        resposta = cliente.post(reverse('autenticacao:cadastro'), {**self.dados, 'email': 'a@TEST.COM'})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('email', resposta.context['form'].errors)

    @expectedFailure
    def test_formulario_recusa_email_repetido_com_maiusculas_antes_do_arroba(self):
        form = SignUpForm({**self.dados, 'email': 'A@test.com'})
        self.assertIn('email', form.errors)

    @expectedFailure
    def test_login_aceita_dominio_em_maiusculas(self):
        self.client.post(reverse('autenticacao:login'), {'email': 'a@TEST.COM', 'senha': SENHA})
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)

    @expectedFailure
    def test_login_aceita_maiusculas_antes_do_arroba(self):
        self.client.post(reverse('autenticacao:login'), {'email': 'A@test.com', 'senha': SENHA})
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)


@SENHA_RAPIDA
class SenhaComEspacoTestCase(TestCase):
    @expectedFailure
    def test_senha_criada_no_painel_com_espaco_final_consegue_fazer_login(self):
        gestor = Admin.objects.create_superuser(email='g@test.com', nome='Gestor', password=SENHA)
        self.client.force_login(gestor)
        senha = f'{SENHA} '
        self.client.post(reverse('admin:autenticacao_admin_add'), {
            'email': 'n@test.com', 'nome': 'Nova', 'usable_password': 'true',
            'password1': senha, 'password2': senha,
        })
        conta = Admin.objects.get(email='n@test.com')
        novo_cliente = Client()
        novo_cliente.post(reverse('autenticacao:login'), {'email': 'n@test.com', 'senha': senha})
        self.assertEqual(int(novo_cliente.session['_auth_user_id']), conta.pk)