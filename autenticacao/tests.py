from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import LoginForm, SignUpForm
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


class LoginFormTestCase(TestCase):
    def test_dados_validos_sao_aceitos(self):
        form = LoginForm({'email': 'a@test.com', 'senha': SENHA})
        self.assertTrue(form.is_valid())

    def test_email_invalido_e_recusado(self):
        form = LoginForm({'email': 'email-invalido', 'senha': SENHA})
        self.assertIn('email', form.errors)

    def test_senha_em_branco_e_recusada(self):
        form = LoginForm({'email': 'a@test.com', 'senha': ''})
        self.assertIn('senha', form.errors)


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
        self.assertEqual(resposta.status_code, 200)


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