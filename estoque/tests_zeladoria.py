from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ItemZeladoriaForm
from .models import ItemCASD, ItemZeladoria, LogItemZeladoria
from .services import ZeladoriaService
from .helpers_tests import criar_admin


EVENTO = LogItemZeladoria.Evento


def dados_zeladoria(**alteracoes):
    dados = {'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': None}
    dados.update(alteracoes)
    return dados


def criar_item_zeladoria(nome='Extensão', quant_total=5, preco_unitario=None):
    # cria direto no banco, sem passar pelo service: não gera log
    return ItemZeladoria.objects.create(nome=nome, quant_total=quant_total,
                                        preco_unitario=preco_unitario)


class ListItemsZeladoriaTestCase(TestCase):
    def test_nao_inclui_itens_removidos(self):
        removido = ItemZeladoria.objects.create(nome='Rodo', is_active=False)
        self.assertNotIn(removido, ZeladoriaService.list_items())

    def test_ordena_por_nome(self):
        criar_item_zeladoria(nome='Vassoura')
        criar_item_zeladoria(nome='Balde')
        nomes = [item.nome for item in ZeladoriaService.list_items()]
        self.assertEqual(nomes, ['Balde', 'Vassoura'])

    def test_nao_inclui_itens_do_casd(self):
        criar_item_zeladoria(nome='Vassoura')
        ItemCASD.objects.create(nome='Caixa de som')
        nomes = [item.nome for item in ZeladoriaService.list_items()]
        self.assertEqual(nomes, ['Vassoura'])


class CreateItemZeladoriaTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()

    def test_retorna_o_item_criado(self):
        item = ZeladoriaService.create_item(dados_zeladoria(), self.admin)
        self.assertEqual(ItemZeladoria.objects.get(), item)

    def test_grava_os_dados(self):
        item = ZeladoriaService.create_item(dados_zeladoria(preco_unitario=Decimal('2.50')), self.admin)
        item.refresh_from_db()
        self.assertEqual((item.nome, item.quant_total, item.preco_unitario),
                         ('Extensão', 5, Decimal('2.50')))

    def test_registra_um_log_criado(self):
        item = ZeladoriaService.create_item(dados_zeladoria(), self.admin)
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.id_item, log.event_type), (item, EVENTO.CRIADO))

    def test_log_guarda_a_quantidade_inicial_como_nova(self):
        ZeladoriaService.create_item(dados_zeladoria(quant_total=7), self.admin)
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.quant_anterior, log.quant_nova), (None, 7))

    def test_log_guarda_o_admin(self):
        ZeladoriaService.create_item(dados_zeladoria(), self.admin)
        self.assertEqual(LogItemZeladoria.objects.get().id_admin, self.admin)

    def test_log_guarda_o_ip(self):
        ZeladoriaService.create_item(dados_zeladoria(), self.admin, ip='10.0.0.1')
        self.assertEqual(LogItemZeladoria.objects.get().ip_aparelho, '10.0.0.1')

    def test_log_sem_ip_fica_nulo(self):
        ZeladoriaService.create_item(dados_zeladoria(), self.admin)
        self.assertIsNone(LogItemZeladoria.objects.get().ip_aparelho)


class UpdateItemZeladoriaTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = criar_item_zeladoria(quant_total=5, preco_unitario=Decimal('12.50'))

    def atualizar(self, ip=None, **alteracoes):
        dados = dados_zeladoria(**{'preco_unitario': Decimal('12.50'), **alteracoes})
        return ZeladoriaService.update_item(self.item, dados, self.admin, ip)

    def test_grava_o_nome(self):
        self.atualizar(nome='Extensão 3m')
        self.item.refresh_from_db()
        self.assertEqual(self.item.nome, 'Extensão 3m')

    def test_grava_o_preco(self):
        self.atualizar(preco_unitario=Decimal('15.00'))
        self.item.refresh_from_db()
        self.assertEqual(self.item.preco_unitario, Decimal('15.00'))

    def test_permite_remover_o_preco(self):
        self.atualizar(preco_unitario=None)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.preco_unitario)

    def test_reduzir_o_total_registra_log_com_anterior_e_nova(self):
        self.atualizar(quant_total=3)
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.event_type, log.quant_anterior, log.quant_nova),
                         (EVENTO.QUANT_ALTERADA, 5, 3))

    def test_aumentar_o_total_registra_log(self):
        self.atualizar(quant_total=8)
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.quant_anterior, log.quant_nova), (5, 8))

    def test_log_guarda_admin_e_ip(self):
        self.atualizar(quant_total=8, ip='10.0.0.1')
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.id_admin, log.ip_aparelho), (self.admin, '10.0.0.1'))

    def test_alterar_so_nome_e_preco_nao_gera_log(self):
        self.atualizar(nome='Extensão 3m', preco_unitario=Decimal('15.00'))
        self.assertFalse(LogItemZeladoria.objects.exists())

class DeleteItemZeladoriaTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = criar_item_zeladoria(quant_total=3)

    def test_faz_soft_delete(self):
        ZeladoriaService.delete_item(self.item, self.admin)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_item_sai_da_lista(self):
        ZeladoriaService.delete_item(self.item, self.admin)
        self.assertNotIn(self.item, ZeladoriaService.list_items())

    def test_registra_log_removido_sem_quantidades(self):
        ZeladoriaService.delete_item(self.item, self.admin)
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.event_type, log.quant_anterior, log.quant_nova),
                         (EVENTO.REMOVIDO, None, None))

    def test_log_guarda_admin_e_ip(self):
        ZeladoriaService.delete_item(self.item, self.admin, ip='10.0.0.1')
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.id_admin, log.ip_aparelho), (self.admin, '10.0.0.1'))


class HistoricoZeladoriaTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = ZeladoriaService.create_item(dados_zeladoria(quant_total=5), self.admin)

    def eventos(self):
        return [log.event_type for log in ZeladoriaService.historico(self.item)]

    def test_item_sem_logs_tem_historico_vazio(self):
        sem_logs = criar_item_zeladoria(nome='Balde')
        self.assertFalse(ZeladoriaService.historico(sem_logs).exists())

    def test_mais_recente_vem_primeiro(self):
        ZeladoriaService.update_item(self.item, dados_zeladoria(quant_total=4), self.admin)
        ZeladoriaService.update_item(self.item, dados_zeladoria(quant_total=6), self.admin)
        quantidades = [log.quant_nova for log in ZeladoriaService.historico(self.item)]
        self.assertEqual(quantidades, [6, 4, 5])

    def test_inclui_a_remocao(self):
        ZeladoriaService.delete_item(self.item, self.admin)
        self.assertEqual(self.eventos()[0], EVENTO.REMOVIDO)

    def test_mesmo_horario_desempata_pela_ordem_de_criacao(self):
        ZeladoriaService.update_item(self.item, dados_zeladoria(quant_total=4), self.admin)
        LogItemZeladoria.objects.update(event_date=timezone.now())
        self.assertEqual(self.eventos(), [EVENTO.QUANT_ALTERADA, EVENTO.CRIADO])

    def test_ler_o_admin_nao_gera_consultas_extras(self):
        for quant_total in (4, 3, 2):
            ZeladoriaService.update_item(self.item, dados_zeladoria(quant_total=quant_total), self.admin)
        with self.assertNumQueries(1):
            for log in ZeladoriaService.historico(self.item):
                log.id_admin.nome

    def test_nao_inclui_logs_de_outro_item(self):
        outro = ZeladoriaService.create_item(dados_zeladoria(nome='Balde'), self.admin)
        self.assertNotIn(outro, [log.id_item for log in ZeladoriaService.historico(self.item)])


class ItemZeladoriaFormTestCase(TestCase):
    def test_aceita_dados_validos(self):
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': '12.50'})
        self.assertTrue(form.is_valid())

    def test_preco_e_opcional(self):
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': ''})
        self.assertTrue(form.is_valid())

    def test_preco_vazio_vira_nulo(self):
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': ''})
        form.is_valid()
        self.assertIsNone(form.cleaned_data['preco_unitario'])

    def test_aceita_preco_zero(self):
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': '0'})
        self.assertTrue(form.is_valid())

    def test_recusa_preco_negativo(self):
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': '-0.01'})
        self.assertIn('preco_unitario', form.errors)

    def test_recusa_preco_com_mais_de_dois_decimais(self):
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': '1.234'})
        self.assertIn('preco_unitario', form.errors)

    def test_recusa_preco_acima_do_limite_do_campo(self):
        # max_digits=8 com 2 decimais: o maior valor é 999999.99
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': '1000000.00'})
        self.assertIn('preco_unitario', form.errors)

    def test_recusa_total_negativo(self):
        form = ItemZeladoriaForm({'nome': 'Extensão', 'quant_total': -1, 'preco_unitario': ''})
        self.assertIn('quant_total', form.errors)

    def test_nome_e_total_sao_obrigatorios(self):
        form = ItemZeladoriaForm({})
        self.assertEqual(set(form.errors), {'nome', 'quant_total'})

    def test_preco_tem_texto_de_ajuda(self):
        self.assertIn('Opcional', ItemZeladoriaForm().fields['preco_unitario'].help_text)


class ZeladoriaAnonimoTestCase(TestCase):
    """Todas as páginas da zeladoria são restritas aos admins."""

    def setUp(self):
        self.item = criar_item_zeladoria()
        self.login = reverse('autenticacao:login')

    def assertRedirecionaParaLogin(self, resposta, url):
        self.assertRedirects(resposta, f'{self.login}?next={url}', fetch_redirect_response=False)

    def test_lista_redireciona(self):
        url = reverse('estoque:zeladoria_list')
        self.assertRedirecionaParaLogin(self.client.get(url), url)

    def test_cadastro_redireciona(self):
        url = reverse('estoque:zeladoria_create')
        self.assertRedirecionaParaLogin(self.client.get(url), url)

    def test_edicao_redireciona(self):
        url = reverse('estoque:zeladoria_update', args=[self.item.pk])
        self.assertRedirecionaParaLogin(self.client.get(url), url)

    def test_remocao_redireciona(self):
        url = reverse('estoque:zeladoria_delete', args=[self.item.pk])
        self.assertRedirecionaParaLogin(self.client.post(url), url)

    def test_post_de_cadastro_nao_cria_item(self):
        self.client.post(reverse('estoque:zeladoria_create'), dados_zeladoria(nome='Balde', preco_unitario=''))
        self.assertFalse(ItemZeladoria.objects.filter(nome='Balde').exists())

    def test_post_de_remocao_nao_remove(self):
        self.client.post(reverse('estoque:zeladoria_delete', args=[self.item.pk]))
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_cabecalho_nao_tem_link_para_a_zeladoria(self):
        resposta = self.client.get(reverse('estoque:item_list'))
        self.assertNotContains(resposta, f'href="{reverse("estoque:zeladoria_list")}"')


class ZeladoriaListViewTestCase(TestCase):
    def setUp(self):
        self.url = reverse('estoque:zeladoria_list')
        self.client.force_login(criar_admin())

    def test_usa_o_template_da_zeladoria(self):
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, 'estoque/zeladoria_list.html')

    def test_mostra_os_itens_ativos(self):
        criar_item_zeladoria(nome='Vassoura')
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Vassoura')

    def test_nao_mostra_itens_removidos(self):
        ItemZeladoria.objects.create(nome='Rodo velho', is_active=False)
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, 'Rodo velho')

    def test_nao_mostra_itens_do_casd(self):
        ItemCASD.objects.create(nome='Caixa de som')
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, 'Caixa de som')

    def test_mostra_o_preco_em_reais(self):
        criar_item_zeladoria(preco_unitario=Decimal('12.50'))
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'R$ 12,50')

    def test_preco_zero_e_mostrado(self):
        # "is not None" no template: um preço 0 não pode virar "—"
        criar_item_zeladoria(preco_unitario=Decimal('0'))
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'R$ 0,00')

    def test_item_sem_preco_mostra_traco(self):
        criar_item_zeladoria()
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<td>—</td>', html=True)

    def test_tem_botao_de_adicionar(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, reverse('estoque:zeladoria_create'))

    def test_tem_link_de_edicao(self):
        item = criar_item_zeladoria()
        resposta = self.client.get(self.url)
        self.assertContains(resposta, reverse('estoque:zeladoria_update', args=[item.pk]))

    def test_tem_botao_de_remocao_com_confirmacao(self):
        criar_item_zeladoria(nome='Vassoura')
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'data-confirm="Remover Vassoura da zeladoria?"')

    def test_sem_itens_mostra_aviso(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Nenhum item cadastrado na zeladoria.')

    def test_cabecalho_tem_link_para_a_zeladoria(self):
        resposta = self.client.get(reverse('estoque:item_list'))
        self.assertContains(resposta, f'href="{self.url}"')


class ZeladoriaCreateViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.client.force_login(self.admin)
        self.url = reverse('estoque:zeladoria_create')

    def post(self, **alteracoes):
        dados = dados_zeladoria(**{'preco_unitario': '', **alteracoes})
        return self.client.post(self.url, dados, REMOTE_ADDR='10.0.0.1')

    def test_usa_o_template_de_formulario(self):
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, 'estoque/zeladoria_form.html')

    def test_titulo_indica_cadastro(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<h1>Novo item da zeladoria</h1>', html=True)

    def test_mostra_o_texto_de_ajuda_do_preco(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Opcional. Preencha apenas para itens vendidos.')

    def test_cancelar_volta_para_a_zeladoria(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'href="{reverse("estoque:zeladoria_list")}">Cancelar')

    def test_cria_o_item(self):
        self.post(nome='Balde', quant_total=3, preco_unitario='4.90')
        item = ItemZeladoria.objects.get()
        self.assertEqual((item.nome, item.quant_total, item.preco_unitario), ('Balde', 3, Decimal('4.90')))

    def test_log_guarda_o_admin_logado(self):
        self.post()
        self.assertEqual(LogItemZeladoria.objects.get().id_admin, self.admin)

    def test_log_guarda_o_ip(self):
        self.post()
        self.assertEqual(LogItemZeladoria.objects.get().ip_aparelho, '10.0.0.1')

    def test_sucesso_redireciona_para_a_zeladoria(self):
        resposta = self.post()
        self.assertRedirects(resposta, reverse('estoque:zeladoria_list'))

    def test_sucesso_mostra_mensagem(self):
        resposta = self.client.post(self.url, dados_zeladoria(preco_unitario=''), follow=True)
        self.assertContains(resposta, 'Item cadastrado.')

    def test_formulario_invalido_nao_cria_item(self):
        self.post(nome='')
        self.assertFalse(ItemZeladoria.objects.exists())

    def test_formulario_invalido_nao_cria_log(self):
        self.post(nome='')
        self.assertFalse(LogItemZeladoria.objects.exists())

    def test_preco_negativo_mostra_erro_no_campo(self):
        resposta = self.post(preco_unitario='-1')
        self.assertContains(resposta, 'maior ou igual a 0')


class ZeladoriaUpdateViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.client.force_login(self.admin)
        self.item = criar_item_zeladoria(nome='Extensão', quant_total=5)
        self.url = reverse('estoque:zeladoria_update', args=[self.item.pk])

    def post(self, **alteracoes):
        dados = dados_zeladoria(**{'preco_unitario': '', **alteracoes})
        return self.client.post(self.url, dados)

    def test_formulario_vem_preenchido(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'value="Extensão"')

    def test_titulo_indica_edicao(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<h1>Editar item da zeladoria</h1>', html=True)

    def test_item_inexistente_retorna_404(self):
        resposta = self.client.get(reverse('estoque:zeladoria_update', args=[self.item.pk + 1]))
        self.assertEqual(resposta.status_code, 404)

    def test_item_removido_retorna_404(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(is_active=False)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)

    def test_atualiza_o_item(self):
        self.post(nome='Extensão 3m', quant_total=6)
        self.item.refresh_from_db()
        self.assertEqual((self.item.nome, self.item.quant_total), ('Extensão 3m', 6))

    def test_log_guarda_o_admin_logado(self):
        self.post(quant_total=6)
        self.assertEqual(LogItemZeladoria.objects.get().id_admin, self.admin)

    def test_sucesso_redireciona_para_a_zeladoria(self):
        resposta = self.post(quant_total=6)
        self.assertRedirects(resposta, reverse('estoque:zeladoria_list'))

    def test_sucesso_mostra_mensagem(self):
        resposta = self.client.post(self.url, dados_zeladoria(preco_unitario=''), follow=True)
        self.assertContains(resposta, 'Item atualizado.')


class ZeladoriaDeleteViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.client.force_login(self.admin)
        self.item = criar_item_zeladoria()
        self.url = reverse('estoque:zeladoria_delete', args=[self.item.pk])

    def test_get_nao_e_permitido(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 405)

    def test_item_removido_retorna_404(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(is_active=False)
        resposta = self.client.post(self.url)
        self.assertEqual(resposta.status_code, 404)

    def test_remove_o_item(self):
        self.client.post(self.url)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_log_guarda_o_admin_logado(self):
        self.client.post(self.url)
        self.assertEqual(LogItemZeladoria.objects.get().id_admin, self.admin)

    def test_redireciona_para_a_zeladoria(self):
        resposta = self.client.post(self.url)
        self.assertRedirects(resposta, reverse('estoque:zeladoria_list'))

    def test_sucesso_mostra_mensagem(self):
        resposta = self.client.post(self.url, follow=True)
        self.assertContains(resposta, 'Item removido.')