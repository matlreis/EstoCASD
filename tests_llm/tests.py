"""
Teste cego por LLM.
Cada teste preenche o banco de teste, roda o site em um servidor ao vivo e entrega uma ação ao
agente, que usa o site pelo navegador. Os achados vão para um relatório em tests_llm/reports/ e
não reprovam o teste, porque a saída do modelo não é determinística: o teste só falha se o agente
não concluir a ação. Bugs confirmados viram testes determinísticos com @expectedFailure.

Execute com: RUN_LLM_TEST=1 uv run manage.py test tests_llm
Para acompanhar o navegador, defina LLM_HEADED=1; para que as ações sejam executada de forma mais
lenta, defina LLM_SLOW_MO=1.
"""
import os
from datetime import timedelta
from pathlib import Path
from unittest import mock, skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from playwright.sync_api import sync_playwright

from autenticacao.models import Admin
from estoque.models import Emprestimo, ItemCASD, ItemZeladoria, Morador

from . import actions
from .agent import executar_acao
from .browser import Navegador

PASTA_RELATORIOS = Path(__file__).resolve().parent / 'reports'


@skipUnless(os.environ.get('RUN_LLM_TEST'), 'teste por LLM: defina RUN_LLM_TEST=1')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TesteCegoLLM(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        # a API síncrona do Playwright mantém um event loop na thread do teste, e o Django
        # bloqueia o ORM dentro de um event loop; o patch é desfeito no fim da classe
        cls.enterClassContext(mock.patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'}))
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.chromium = cls.playwright.chromium.launch(
            headless=not os.environ.get('LLM_HEADED'),
            slow_mo=500 if os.environ.get('LLM_SLOW_MO') else None
        )
        cls.addClassCleanup(cls.chromium.close)

    def setUp(self):
        # contexto novo por teste: cookies e sessão não passam de uma ação para outra
        contexto = self.chromium.new_context()
        self.addCleanup(contexto.close)
        self.navegador = Navegador(contexto.new_page(), self.live_server_url)
        self.preencher()

    def preencher(self):
        """Dados fictícios. As datas são relativas ao dia real, que é o dia que o navegador vê."""
        hoje = timezone.localdate()
        Admin.objects.create_superuser(email=actions.EMAIL_ADMIN, nome='Gestor', password=actions.SENHA_ADMIN)

        ItemCASD.objects.create(nome='Escada', quant_total=3)
        caixa = ItemCASD.objects.create(nome='Caixa de som', quant_total=1, quant_emprestada=1)
        extensao = ItemCASD.objects.create(nome='Extensão', quant_total=4, quant_emprestada=2)

        joana = Morador.objects.create(nome='Joana/Mafalda', ap_vaga='104J Vaga A', email='joana@casd.test',
                                       telefone='12999990104')
        lucas = Morador.objects.create(nome='Lucas/Tintim', ap_vaga='305J Vaga B', email='lucas@casd.test',
                                       telefone='12999990305')
        Emprestimo.objects.create(id_item=caixa, id_morador=joana, limit_date=hoje + timedelta(days=7))
        Emprestimo.objects.create(id_item=extensao, id_morador=lucas, limit_date=hoje - timedelta(days=5))
        Emprestimo.objects.create(id_item=extensao, id_morador=joana, limit_date=hoje + timedelta(days=3),
                                  status=Emprestimo.StatusEmprestimo.DS)

        ItemZeladoria.objects.create(nome='Papel higiênico', quant_total=20, preco_unitario='2.00')
        ItemZeladoria.objects.create(nome='Vassoura', quant_total=2)

    def executar(self, acao):
        resultado = executar_acao(self.navegador, acao, actions.CONTEXTO_CLIENTE)
        print(f'Relatório: {self.escrever_relatorio(acao, resultado)}')
        self.assertTrue(resultado.concluiu, f'o agente não concluiu a ação em {resultado.passos} passos')

    def escrever_relatorio(self, acao, resultado):
        nome = self._testMethodName.removeprefix('test_')
        agora = timezone.localtime()
        linhas = [
            f'# Teste cego por LLM: {nome}', '',
            f'- Modelo: `{os.environ["LLM_MODEL"]}`',
            f'- Data: {agora:%d/%m/%Y %H:%M}',
            f'- Passos: {resultado.passos}',
            f'- Concluiu: {"sim" if resultado.concluiu else "não"}', '',
            '## Ação', '', acao, '',
            f'## Achados ({len(resultado.achados)})', '',
        ]
        for achado in resultado.achados:
            linhas += [
                f'### [{achado.get("gravidade")}] {achado.get("titulo")}', '',
                f'- **Passos:** {achado.get("passos")}',
                f'- **Esperado:** {achado.get("esperado")}',
                f'- **Obtido:** {achado.get("obtido")}', '',
            ]
        linhas += ['## Resumo do agente', '', resultado.resumo or '(sem resumo)', '', '## Passos executados', '']
        linhas += [f'- [{passo}] `{ferramenta}` {argumentos}' for passo, ferramenta, argumentos in resultado.acoes]

        PASTA_RELATORIOS.mkdir(exist_ok=True)
        caminho = PASTA_RELATORIOS / f'{agora:%Y-%m-%d_%H%M}_{nome}.md'
        caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
        return caminho

    def test_ferramentas(self):
        # sem LLM: confere que o navegador enxerga o site semeado
        pagina = self.navegador.navegar('/')
        self.assertIn('Escada', pagina)

    def test_morador_emprestimo(self):
        self.executar(actions.ACAO_MORADOR_EMPRESTIMO)

    def test_morador_limites(self):
        self.executar(actions.ACAO_MORADOR_LIMITES)

    def test_admin_estoque(self):
        self.executar(actions.ACAO_ADMIN_ESTOQUE)

    def test_admin_zeladoria(self):
        self.executar(actions.ACAO_ADMIN_ZELADORIA)

    def test_gestor_contas(self):
        self.executar(actions.ACAO_GESTOR_CONTAS)
