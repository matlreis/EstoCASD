from datetime import UTC, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ItemZeladoriaForm, VendaForm
from .models import ItemCASD, ItemZeladoria, LogItemZeladoria, Venda
from .services import ZeladoriaService
from .helpers_tests import criar_admin


EVENTO = LogItemZeladoria.Evento


def dados_zeladoria(**alteracoes):
    dados = {'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': None}
    dados.update(alteracoes)
    return dados


def dados_venda(**alteracoes):
    # mesmo formato do cleaned_data do VendaForm
    dados = {'nome_comprador': 'Pedro', 'ap_vaga': '101D Vaga A', 'quant': 1, 'notas': ''}
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


class RegistrarVendaTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = criar_item_zeladoria(nome='Água 500ml', quant_total=10, preco_unitario=Decimal('2.50'))

    def vender(self, ip=None, item=None, **alteracoes):
        return ZeladoriaService.registrar_venda(item or self.item, dados_venda(**alteracoes), self.admin, ip)

    def estoque(self):
        return ItemZeladoria.objects.get(pk=self.item.pk).quant_total

    def test_retorna_a_venda_criada(self):
        venda = self.vender()
        self.assertEqual(Venda.objects.get(), venda)

    def test_grava_os_dados_da_venda(self):
        venda = self.vender(nome_comprador='Pedro', ap_vaga='101D Vaga A', quant=3, notas='evento da Atlética')
        venda.refresh_from_db()
        self.assertEqual((venda.id_item, venda.nome_comprador, venda.ap_vaga, venda.quant, venda.notas),
                         (self.item, 'Pedro', '101D Vaga A', 3, 'evento da Atlética'))

    def test_venda_guarda_o_admin(self):
        venda = self.vender()
        self.assertEqual(venda.id_admin, self.admin)

    def test_copia_o_preco_do_item(self):
        venda = self.vender()
        venda.refresh_from_db()
        self.assertEqual(venda.preco_unitario, Decimal('2.50'))

    def test_reduz_o_estoque(self):
        self.vender(quant=3)
        self.assertEqual(self.estoque(), 7)

    def test_registra_log_venda_com_anterior_e_nova(self):
        self.vender(quant=3)
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.id_item, log.event_type, log.quant_anterior, log.quant_nova),
                         (self.item, EVENTO.VENDA, 10, 7))

    def test_log_guarda_admin_e_ip(self):
        self.vender(ip='10.0.0.1')
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.id_admin, log.ip_aparelho), (self.admin, '10.0.0.1'))

    def test_log_sem_ip_fica_nulo(self):
        self.vender()
        self.assertIsNone(LogItemZeladoria.objects.get().ip_aparelho)

    def test_vendas_seguidas_acumulam(self):
        self.vender(quant=3)
        self.vender(quant=4)
        logs = LogItemZeladoria.objects.order_by('pk')
        self.assertEqual([(log.quant_anterior, log.quant_nova) for log in logs], [(10, 7), (7, 3)])

    def test_aceita_vender_exatamente_o_estoque(self):
        self.vender(quant=10)
        self.assertEqual(self.estoque(), 0)

    def test_recusa_item_removido(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, 'Este item foi removido.'):
            self.vender(quant=3)

    def test_recusa_vender_um_a_mais_que_o_estoque(self):
        with self.assertRaisesMessage(ValidationError, 'Quantidade indisponível. Em estoque: 10.'):
            self.vender(quant=11)

    def test_recusa_quantidade_zero(self):
        with self.assertRaisesMessage(ValidationError, 'Quantidade indisponível.'):
            self.vender(quant=0)

    def test_recusa_item_com_estoque_zerado(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(quant_total=0)
        with self.assertRaisesMessage(ValidationError, 'Em estoque: 0.'):
            self.vender(quant=1)

    def test_recusa_item_sem_preco(self):
        sem_preco = criar_item_zeladoria(nome='Vassoura', quant_total=3)
        with self.assertRaisesMessage(ValidationError, 'Este item não está à venda.'):
            self.vender(item=sem_preco)

    def test_aceita_item_com_preco_zero(self):
        # "is None" no service: preço 0 é um preço, o item está à venda
        gratis = criar_item_zeladoria(nome='Panfleto', quant_total=5, preco_unitario=Decimal('0'))
        venda = self.vender(item=gratis, quant=2)
        self.assertEqual(venda.total, Decimal('0'))

    def test_venda_recusada_nao_deixa_rastro(self):
        sem_preco = criar_item_zeladoria(nome='Vassoura', quant_total=3)
        casos = [('acima do estoque', self.item, 11), ('quantidade zero', self.item, 0),
                 ('item sem preço', sem_preco, 1)]
        for caso, item, quant in casos:
            with self.subTest(caso):
                with self.assertRaises(ValidationError):
                    self.vender(item=item, quant=quant)
                item.refresh_from_db()
                self.assertEqual(item.quant_total, 10 if item == self.item else 3)
                self.assertFalse(Venda.objects.exists())
                self.assertFalse(LogItemZeladoria.objects.exists())

    def test_mudar_o_preco_depois_nao_altera_a_venda(self):
        venda = self.vender(quant=2)
        ZeladoriaService.update_item(self.item, dados_zeladoria(nome='Água 500ml', quant_total=8,
                                                                preco_unitario=Decimal('3.00')), self.admin)
        venda.refresh_from_db()
        self.assertEqual((venda.preco_unitario, venda.total), (Decimal('2.50'), Decimal('5.00')))

    # Instância desatualizada: o self.item foi lido com 10 unidades a R$ 2,50, e outro
    # admin mudou o banco depois. O service deve trabalhar com o que está no banco.

    def test_instancia_desatualizada_usa_o_estoque_do_banco(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(quant_total=2)
        self.vender(quant=1)
        self.assertEqual(self.estoque(), 1)

    def test_instancia_desatualizada_nao_vende_alem_do_banco(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(quant_total=2)
        with self.assertRaisesMessage(ValidationError, 'Em estoque: 2.'):
            self.vender(quant=3)

    def test_instancia_desatualizada_usa_o_preco_do_banco(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(preco_unitario=Decimal('3.00'))
        venda = self.vender()
        self.assertEqual(venda.preco_unitario, Decimal('3.00'))

    def test_preco_apagado_no_banco_recusa_a_venda(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(preco_unitario=None)
        with self.assertRaisesMessage(ValidationError, 'Este item não está à venda.'):
            self.vender()


class VendaModelTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = criar_item_zeladoria(quant_total=10, preco_unitario=Decimal('2.50'))

    def test_total_e_quantidade_vezes_preco(self):
        venda = ZeladoriaService.registrar_venda(self.item, dados_venda(quant=3), self.admin)
        self.assertEqual(venda.total, Decimal('7.50'))

    def test_item_com_vendas_nao_pode_ser_apagado_de_fato(self):
        # PROTECT: a remoção da zeladoria é sempre soft delete
        ZeladoriaService.registrar_venda(self.item, dados_venda(), self.admin)
        with self.assertRaises(ProtectedError):
            self.item.delete()


class ListarVendasTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.item = criar_item_zeladoria(quant_total=10, preco_unitario=Decimal('2.50'))

    def vender(self, quant, item=None):
        return ZeladoriaService.registrar_venda(item or self.item, dados_venda(quant=quant), self.admin)

    def quantidades(self):
        return [venda.quant for venda in ZeladoriaService.listar_vendas()]

    def test_sem_vendas_retorna_vazio(self):
        self.assertFalse(ZeladoriaService.listar_vendas().exists())

    def test_mais_recente_vem_primeiro(self):
        for quant in (1, 2, 3):
            self.vender(quant)
        self.assertEqual(self.quantidades(), [3, 2, 1])

    def test_mesmo_horario_desempata_pela_ordem_de_criacao(self):
        self.vender(1)
        self.vender(2)
        Venda.objects.update(data=timezone.now())
        self.assertEqual(self.quantidades(), [2, 1])

    def test_inclui_vendas_de_todos_os_itens(self):
        balde = criar_item_zeladoria(nome='Balde', quant_total=5, preco_unitario=Decimal('4.90'))
        self.vender(1)
        self.vender(2, item=balde)
        self.assertEqual(Venda.objects.count(), ZeladoriaService.listar_vendas().count())

    def test_inclui_venda_de_item_removido(self):
        venda = self.vender(1)
        ZeladoriaService.delete_item(self.item, self.admin)
        self.assertIn(venda, ZeladoriaService.listar_vendas())

    def test_ler_item_e_admin_nao_gera_consultas_extras(self):
        for quant in (1, 2, 3):
            self.vender(quant)
        with self.assertNumQueries(1):
            for venda in ZeladoriaService.listar_vendas():
                venda.id_item.nome
                venda.id_admin.nome


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


class VendaFormTestCase(TestCase):
    def test_aceita_dados_validos(self):
        form = VendaForm(dados_venda(notas='evento da Atlética'))
        self.assertTrue(form.is_valid())

    def test_nome_local_e_quantidade_sao_obrigatorios(self):
        form = VendaForm({})
        self.assertEqual(set(form.errors), {'nome_comprador', 'ap_vaga', 'quant'})

    def test_notas_sao_opcionais(self):
        form = VendaForm(dados_venda(notas=''))
        self.assertTrue(form.is_valid())

    def test_local_aceita_texto_livre(self):
        # sem validação de formato: só ajuda os gestores a identificar o morador
        form = VendaForm(dados_venda(ap_vaga='quarto do fundo, 2º andar'))
        self.assertTrue(form.is_valid())

    def test_recusa_local_acima_do_limite_do_campo(self):
        form = VendaForm(dados_venda(ap_vaga='x' * 51))
        self.assertIn('ap_vaga', form.errors)

    def test_recusa_quantidade_zero(self):
        form = VendaForm(dados_venda(quant=0))
        self.assertIn('quant', form.errors)

    def test_recusa_quantidade_negativa(self):
        form = VendaForm(dados_venda(quant=-1))
        self.assertIn('quant', form.errors)

    def test_recusa_quantidade_nao_numerica(self):
        form = VendaForm(dados_venda(quant='dez'))
        self.assertIn('quant', form.errors)

    def test_campo_de_quantidade_tem_minimo_1_no_navegador(self):
        self.assertIn('min="1"', str(VendaForm()['quant']))

    def test_quantidade_comeca_em_1(self):
        self.assertEqual(VendaForm().fields['quant'].initial, 1)

    def test_preco_nao_e_campo_do_formulario(self):
        # o preço é sempre copiado do item pelo service
        self.assertNotIn('preco_unitario', VendaForm().fields)

    def test_local_tem_texto_de_ajuda(self):
        self.assertIn('Ex.:', VendaForm().fields['ap_vaga'].help_text)

    def test_notas_tem_texto_de_ajuda(self):
        self.assertIn('Opcional', VendaForm().fields['notas'].help_text)


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

    def test_historico_redireciona(self):
        url = reverse('estoque:zeladoria_historico', args=[self.item.pk])
        self.assertRedirecionaParaLogin(self.client.get(url), url)

    def test_venda_redireciona(self):
        url = reverse('estoque:zeladoria_venda', args=[self.item.pk])
        self.assertRedirecionaParaLogin(self.client.get(url), url)

    def test_historico_de_vendas_redireciona(self):
        url = reverse('estoque:venda_list')
        self.assertRedirecionaParaLogin(self.client.get(url), url)

    def test_post_de_cadastro_nao_cria_item(self):
        self.client.post(reverse('estoque:zeladoria_create'), dados_zeladoria(nome='Balde', preco_unitario=''))
        self.assertFalse(ItemZeladoria.objects.filter(nome='Balde').exists())

    def test_post_de_venda_nao_vende(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(preco_unitario=Decimal('2.50'))
        self.client.post(reverse('estoque:zeladoria_venda', args=[self.item.pk]), dados_venda())
        self.item.refresh_from_db()
        self.assertEqual((Venda.objects.count(), self.item.quant_total), (0, 5))

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

    def test_tem_link_de_historico(self):
        item = criar_item_zeladoria()
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'href="{reverse("estoque:zeladoria_historico", args=[item.pk])}">Histórico')

    def test_item_com_preco_tem_botao_de_venda(self):
        item = criar_item_zeladoria(preco_unitario=Decimal('2.50'))
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'href="{reverse("estoque:zeladoria_venda", args=[item.pk])}">Registrar venda')

    def test_item_sem_preco_nao_tem_botao_de_venda(self):
        item = criar_item_zeladoria()
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, reverse('estoque:zeladoria_venda', args=[item.pk]))

    def test_item_com_preco_zero_tem_botao_de_venda(self):
        # "is not None" no template: preço 0 é um preço, o item está à venda
        item = criar_item_zeladoria(preco_unitario=Decimal('0'))
        resposta = self.client.get(self.url)
        self.assertContains(resposta, reverse('estoque:zeladoria_venda', args=[item.pk]))

    def test_tem_link_para_o_historico_de_vendas(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'href="{reverse("estoque:venda_list")}">Histórico de vendas')

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


class ZeladoriaHistoricoViewTestCase(TestCase):
    # 17:30 em UTC: a página deve mostrar 14:30, no fuso de São Paulo (UTC-3)
    DATA_LOG = datetime(2026, 11, 5, 17, 30, tzinfo=UTC)

    def setUp(self):
        self.admin = criar_admin()
        self.client.force_login(self.admin)
        self.item = ZeladoriaService.create_item(dados_zeladoria(quant_total=5), self.admin)
        self.url = reverse('estoque:zeladoria_historico', args=[self.item.pk])

    def abrir(self):
        # fixa a data de todos os logs para que as linhas esperadas sejam exatas
        LogItemZeladoria.objects.update(event_date=self.DATA_LOG)
        return self.client.get(self.url)

    def alterar_total(self, quant_total, admin=None):
        ZeladoriaService.update_item(self.item, dados_zeladoria(quant_total=quant_total), admin or self.admin)

    def test_usa_o_template_de_historico(self):
        resposta = self.abrir()
        self.assertTemplateUsed(resposta, 'estoque/zeladoria_historico.html')

    def test_titulo_mostra_o_nome_do_item(self):
        resposta = self.abrir()
        self.assertContains(resposta, '<h1>Histórico: Extensão</h1>', html=True)

    def test_voltar_leva_para_a_zeladoria(self):
        resposta = self.abrir()
        self.assertContains(resposta, f'href="{reverse("estoque:zeladoria_list")}">Voltar')

    def test_item_inexistente_retorna_404(self):
        resposta = self.client.get(reverse('estoque:zeladoria_historico', args=[self.item.pk + 1]))
        self.assertEqual(resposta.status_code, 404)

    def test_item_removido_retorna_404(self):
        ZeladoriaService.delete_item(self.item, self.admin)
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 404)

    def test_data_no_formato_e_fuso_local(self):
        resposta = self.abrir()
        self.assertContains(resposta, '<td>05/11/2026 14:30</td>', html=True)

    def test_criacao_mostra_traco_antes(self):
        resposta = self.abrir()
        self.assertContains(resposta, '<tr><td>05/11/2026 14:30</td><td>Criado</td>'
                                      '<td>—</td><td>5</td><td>Alice</td></tr>', html=True)

    def test_alteracao_mostra_antes_e_depois(self):
        self.alterar_total(3)
        resposta = self.abrir()
        self.assertContains(resposta, '<tr><td>05/11/2026 14:30</td><td>Quantidade total alterada</td>'
                                      '<td>5</td><td>3</td><td>Alice</td></tr>', html=True)

    def test_quantidade_zero_nao_vira_traco(self):
        # default_if_none no template: só None vira "—", o 0 continua aparecendo
        self.alterar_total(0)
        resposta = self.abrir()
        self.assertContains(resposta, '<tr><td>05/11/2026 14:30</td><td>Quantidade total alterada</td>'
                                      '<td>5</td><td>0</td><td>Alice</td></tr>', html=True)

    def test_cada_linha_mostra_o_admin_do_evento(self):
        self.alterar_total(3, admin=criar_admin(email='bruno@test.com', nome='Bruno'))
        resposta = self.abrir()
        self.assertContains(resposta, '<td>Bruno</td>', count=1, html=True)
        self.assertContains(resposta, '<td>Alice</td>', count=1, html=True)

    def test_mais_recente_vem_primeiro(self):
        self.alterar_total(3)
        conteudo = self.abrir().content.decode()
        self.assertLess(conteudo.index('Quantidade total alterada'), conteudo.index('<td>Criado</td>'))

    def test_nao_mostra_logs_de_outro_item(self):
        ZeladoriaService.create_item(dados_zeladoria(nome='Balde'), self.admin)
        resposta = self.abrir()
        self.assertContains(resposta, '<td>Criado</td>', count=1, html=True)

    def test_com_registros_nao_mostra_aviso(self):
        resposta = self.abrir()
        self.assertNotContains(resposta, 'Nenhum registro.')

    def test_sem_registros_mostra_aviso(self):
        sem_logs = criar_item_zeladoria(nome='Balde')
        resposta = self.client.get(reverse('estoque:zeladoria_historico', args=[sem_logs.pk]))
        self.assertContains(resposta, 'Nenhum registro.')

class ZeladoriaVendaViewTestCase(TestCase):
    def setUp(self):
        self.admin = criar_admin()
        self.client.force_login(self.admin)
        self.item = criar_item_zeladoria(nome='Água 500ml', quant_total=10, preco_unitario=Decimal('2.50'))
        self.url = reverse('estoque:zeladoria_venda', args=[self.item.pk])

    def post(self, url=None, **alteracoes):
        return self.client.post(url or self.url, dados_venda(**alteracoes), REMOTE_ADDR='10.0.0.1')

    def estoque(self):
        return ItemZeladoria.objects.get(pk=self.item.pk).quant_total

    def assertNaoVendeu(self):
        self.assertFalse(Venda.objects.exists())
        self.assertFalse(LogItemZeladoria.objects.exists())
        self.assertEqual(self.estoque(), 10)

    def test_usa_o_template_de_venda(self):
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, 'estoque/zeladoria_venda_form.html')

    def test_titulo_mostra_o_nome_do_item(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<h1>Registrar venda de Água 500ml</h1>', html=True)

    def test_mostra_o_preco_em_reais(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Preço unitário: R$ 2,50')

    def test_mostra_o_estoque_atual(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Estoque atual: 10')

    def test_mostra_o_texto_de_ajuda_do_local(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Ex.: 105D Vaga A')

    def test_notas_aparecem_como_caixa_de_texto(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<textarea name="notas"')

    def test_cancelar_volta_para_a_zeladoria(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'href="{reverse("estoque:zeladoria_list")}">Cancelar')

    def test_item_inexistente_retorna_404(self):
        resposta = self.client.get(reverse('estoque:zeladoria_venda', args=[self.item.pk + 1]))
        self.assertEqual(resposta.status_code, 404)

    def test_item_removido_retorna_404(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(is_active=False)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)

    def test_post_em_item_removido_retorna_404_e_nao_vende(self):
        ItemZeladoria.objects.filter(pk=self.item.pk).update(is_active=False)
        resposta = self.post()
        self.assertEqual(resposta.status_code, 404)
        self.assertNaoVendeu()

    def test_item_sem_preco_retorna_404(self):
        # o botão some na lista, mas a URL ainda pode ser aberta direto
        ItemZeladoria.objects.filter(pk=self.item.pk).update(preco_unitario=None)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)

    def test_post_em_item_sem_preco_retorna_404_e_nao_vende(self):
        # o preço pode ter sido apagado entre o GET e o POST
        ItemZeladoria.objects.filter(pk=self.item.pk).update(preco_unitario=None)
        resposta = self.post()
        self.assertEqual(resposta.status_code, 404)
        self.assertNaoVendeu()

    def test_cria_a_venda(self):
        self.post(nome_comprador='Pedro', ap_vaga='101D Vaga A', quant=3, notas='evento da Atlética')
        venda = Venda.objects.get()
        self.assertEqual((venda.id_item, venda.nome_comprador, venda.ap_vaga, venda.quant, venda.notas),
                         (self.item, 'Pedro', '101D Vaga A', 3, 'evento da Atlética'))

    def test_reduz_o_estoque(self):
        self.post(quant=3)
        self.assertEqual(self.estoque(), 7)

    def test_aceita_vender_todo_o_estoque(self):
        resposta = self.post(quant=10)
        self.assertRedirects(resposta, reverse('estoque:zeladoria_list'))
        self.assertEqual(self.estoque(), 0)

    def test_venda_guarda_o_admin_logado(self):
        self.post()
        self.assertEqual(Venda.objects.get().id_admin, self.admin)

    def test_log_guarda_admin_logado_e_ip(self):
        self.post()
        log = LogItemZeladoria.objects.get()
        self.assertEqual((log.event_type, log.id_admin, log.ip_aparelho), (EVENTO.VENDA, self.admin, '10.0.0.1'))

    def test_preco_vem_do_item_e_nao_do_post(self):
        # um preço enviado à mão no POST é ignorado: não é campo do formulário
        self.post(preco_unitario='0.01')
        self.assertEqual(Venda.objects.get().preco_unitario, Decimal('2.50'))

    def test_sucesso_redireciona_para_a_zeladoria(self):
        resposta = self.post()
        self.assertRedirects(resposta, reverse('estoque:zeladoria_list'))

    def test_sucesso_mostra_mensagem(self):
        resposta = self.client.post(self.url, dados_venda(), follow=True)
        self.assertContains(resposta, 'Venda registrada.')

    def test_quantidade_acima_do_estoque_mostra_erro(self):
        resposta = self.post(quant=11)
        self.assertContains(resposta, 'Quantidade indisponível. Em estoque: 10.')

    def test_quantidade_acima_do_estoque_nao_vende(self):
        self.post(quant=11)
        self.assertNaoVendeu()

    def test_erro_mantem_os_dados_digitados(self):
        resposta = self.post(nome_comprador='Pedro', quant=11)
        self.assertContains(resposta, 'value="Pedro"')

    def test_quantidade_zero_mostra_erro_no_campo(self):
        resposta = self.post(quant=0)
        self.assertContains(resposta, 'maior ou igual a 1')

    def test_formulario_invalido_nao_vende(self):
        self.post(nome_comprador='')
        self.assertNaoVendeu()


class VendaListViewTestCase(TestCase):
    # 17:30 em UTC: a página deve mostrar 14:30, no fuso de São Paulo (UTC-3)
    DATA_VENDA = datetime(2026, 11, 5, 17, 30, tzinfo=UTC)

    def setUp(self):
        self.admin = criar_admin()
        self.client.force_login(self.admin)
        self.item = criar_item_zeladoria(nome='Água 500ml', quant_total=40, preco_unitario=Decimal('2.50'))
        self.url = reverse('estoque:venda_list')

    def vender(self, item=None, admin=None, **alteracoes):
        return ZeladoriaService.registrar_venda(item or self.item, dados_venda(**alteracoes), admin or self.admin)

    def abrir(self):
        # fixa a data de todas as vendas para que as linhas esperadas sejam exatas
        Venda.objects.update(data=self.DATA_VENDA)
        return self.client.get(self.url)

    def test_usa_o_template_de_vendas(self):
        resposta = self.abrir()
        self.assertTemplateUsed(resposta, 'estoque/venda_list.html')

    def test_titulo_da_pagina(self):
        resposta = self.abrir()
        self.assertContains(resposta, '<h1>Histórico de Vendas</h1>', html=True)

    def test_voltar_leva_para_a_zeladoria(self):
        resposta = self.abrir()
        self.assertContains(resposta, f'href="{reverse("estoque:zeladoria_list")}">Voltar')

    def test_mostra_a_venda_completa(self):
        self.vender(nome_comprador='Pedro', ap_vaga='101D Vaga A', quant=10, notas='evento da Atlética')
        resposta = self.abrir()
        self.assertContains(resposta, '<tr><td>05/11/2026 14:30</td><td>Água 500ml</td><td>10</td>'
                                      '<td>R$ 25,00</td><td>Pedro - 101D Vaga A</td>'
                                      '<td>evento da Atlética</td><td>Alice</td></tr>', html=True)

    def test_total_mostra_os_centavos(self):
        self.vender(quant=3)
        resposta = self.abrir()
        self.assertContains(resposta, '<td>R$ 7,50</td>', html=True)

    def test_total_usa_o_preco_da_venda_e_nao_o_atual(self):
        self.vender(quant=10)
        ItemZeladoria.objects.filter(pk=self.item.pk).update(preco_unitario=Decimal('3.00'))
        resposta = self.abrir()
        self.assertContains(resposta, '<td>R$ 25,00</td>', html=True)

    def test_item_com_preco_zero_mostra_total_zero(self):
        gratis = criar_item_zeladoria(nome='Panfleto', quant_total=5, preco_unitario=Decimal('0'))
        self.vender(item=gratis, quant=2)
        resposta = self.abrir()
        self.assertContains(resposta, '<td>R$ 0,00</td>', html=True)

    def test_comprador_aparece_como_foi_digitado(self):
        # sem ajuste de maiúsculas nem de formato no local
        self.vender(nome_comprador='pedro', ap_vaga='101d vaga a')
        resposta = self.abrir()
        self.assertContains(resposta, '<td>pedro - 101d vaga a</td>', html=True)

    def test_venda_sem_notas_mostra_traco(self):
        self.vender(notas='')
        resposta = self.abrir()
        self.assertContains(resposta, '<td>—</td>', html=True)

    def test_notas_sao_escapadas(self):
        # notas são texto livre: um HTML digitado aparece como texto, não é interpretado
        self.vender(notas='<script>alert(1)</script>')
        resposta = self.abrir()
        self.assertContains(resposta, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(resposta, '<script>alert(1)</script>')

    def test_registrada_por_mostra_quem_vendeu_e_nao_o_admin_logado(self):
        self.vender(admin=criar_admin(email='bruno@test.com', nome='Bruno'))
        resposta = self.abrir()
        self.assertContains(resposta, '<td>Bruno</td>', html=True)
        self.assertNotContains(resposta, '<td>Alice</td>', html=True)

    def test_mais_recente_vem_primeiro(self):
        self.vender(nome_comprador='Pedro')
        self.vender(nome_comprador='Ana')
        conteudo = self.abrir().content.decode()
        self.assertLess(conteudo.index('Ana -'), conteudo.index('Pedro -'))

    def test_mostra_vendas_de_todos_os_itens(self):
        balde = criar_item_zeladoria(nome='Balde', quant_total=5, preco_unitario=Decimal('4.90'))
        self.vender()
        self.vender(item=balde)
        resposta = self.abrir()
        self.assertContains(resposta, '<td>Água 500ml</td>', html=True)
        self.assertContains(resposta, '<td>Balde</td>', html=True)

    def test_venda_de_item_removido_continua_aparecendo(self):
        self.vender()
        ZeladoriaService.delete_item(self.item, self.admin)
        resposta = self.abrir()
        self.assertContains(resposta, '<td>Água 500ml</td>', html=True)

    def test_com_vendas_nao_mostra_aviso(self):
        self.vender()
        resposta = self.abrir()
        self.assertNotContains(resposta, 'Nenhuma venda registrada.')

    def test_sem_vendas_mostra_aviso(self):
        resposta = self.abrir()
        self.assertContains(resposta, 'Nenhuma venda registrada.')
