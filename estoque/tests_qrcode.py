from unittest import mock

import segno
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .helpers_tests import criar_admin
from .models import ItemCASD, ItemZeladoria
from .qr import qr_code_png, montar_qr_code

ASSINATURA_PNG = b'\x89PNG\r\n\x1a\n'
URL = 'https://estocasd.example/itens/1/'


def largura_do_png(png):
    return int.from_bytes(png[16:20], 'big')


class ItemDetailViewTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3, quant_emprestada=1)
        self.url = reverse('estoque:item_detail', args=[self.item.pk])

    def test_responde_sem_login(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)

    def test_contexto_traz_o_item(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context['item'], self.item)

    def test_mostra_o_nome_do_item(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<h1>Caixa de som</h1>', html=True)

    def test_mostra_a_quantidade_disponivel(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<p>Disponível: 2 de 3</p>', html=True)

    def test_botao_emprestar_leva_ao_formulario_de_emprestimo(self):
        resposta = self.client.get(self.url)
        link = reverse('estoque:emprestimo_create', args=[self.item.pk])
        self.assertContains(resposta, f'<a class="btn btn-primario" href="{link}">Emprestar</a>', html=True)

    def test_botao_devolver_leva_ao_formulario_de_devolucao(self):
        resposta = self.client.get(self.url)
        link = reverse('estoque:devolucao_sinalizar', args=[self.item.pk])
        self.assertContains(resposta, f'<a class="btn" href="{link}">Devolver</a>', html=True)

    def test_item_esgotado_continua_acessivel(self):
        ItemCASD.objects.filter(pk=self.item.pk).update(quant_emprestada=3)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<p>Disponível: 0 de 3</p>', html=True)

    def test_item_removido_retorna_404(self):
        ItemCASD.objects.filter(pk=self.item.pk).update(is_active=False)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)

    def test_item_inexistente_retorna_404(self):
        resposta = self.client.get(reverse('estoque:item_detail', args=[self.item.pk + 1]))
        self.assertEqual(resposta.status_code, 404)


class ItemDetailItemDaZeladoriaTestCase(TestCase):
    def test_item_da_zeladoria_retorna_404(self):
        zeladoria = ItemZeladoria.objects.create(nome='Detergente', quant_total=5)
        resposta = self.client.get(reverse('estoque:item_detail', args=[zeladoria.pk]))
        self.assertEqual(resposta.status_code, 404)


class QrCodeTestCase(SimpleTestCase):
    def test_usa_correcao_de_erros_de_nivel_q_no_minimo(self):
        # o segno sobe para H quando sobra espaço na mesma versão do código
        qr = montar_qr_code(URL)
        self.assertIn(qr.error, ('Q', 'H'))

    def test_gera_qr_code_padrao_e_nao_micro_qr(self):
        qr = montar_qr_code('abc')
        self.assertFalse(qr.is_micro)

    def test_codifica_a_url_informada(self):
        qr = montar_qr_code(URL)
        self.assertEqual(qr.matrix, segno.make_qr(URL, error='q').matrix)

    def test_urls_diferentes_geram_codigos_diferentes(self):
        qr = montar_qr_code('https://estocasd.example/itens/2/')
        self.assertNotEqual(qr.matrix, montar_qr_code(URL).matrix)

    def test_png_comeca_com_a_assinatura_png(self):
        png = qr_code_png(URL)
        self.assertEqual(png[:8], ASSINATURA_PNG)

    def test_png_tem_resolucao_suficiente_para_imprimir(self):
        png = qr_code_png(URL)
        self.assertGreaterEqual(largura_do_png(png), 600)

    def test_png_tem_zona_de_silencio_de_quatro_modulos(self):
        png = qr_code_png(URL)
        self.assertEqual(largura_do_png(png) % (len(montar_qr_code(URL).matrix) + 8), 0)


class ItemQrViewTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)
        self.url = reverse('estoque:item_qr', args=[self.item.pk])
        self.endereco = 'http://testserver' + reverse('estoque:item_detail', args=[self.item.pk])
        self.client.force_login(criar_admin())

    def test_admin_acessa_a_pagina(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)

    def test_contexto_traz_o_item(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context['item'], self.item)

    def test_contexto_traz_o_endereco_da_pagina_do_item(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.context['url'], self.endereco)

    @override_settings(ALLOWED_HOSTS=['estocasd.example'])
    def test_endereco_usa_o_host_e_o_esquema_da_requisicao(self):
        resposta = self.client.get(self.url, secure=True, HTTP_HOST='estocasd.example')
        self.assertEqual(resposta.context['url'], 'https://estocasd.example' + reverse('estoque:item_detail', args=[self.item.pk]))

    def test_mostra_o_nome_do_item(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<h1>Caixa de som</h1>', html=True)

    def test_mostra_o_endereco_codificado(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, f'<p class="qr-endereco">{self.endereco}</p>', html=True)

    def test_mostra_a_imagem_do_qr_code(self):
        resposta = self.client.get(self.url)
        png = reverse('estoque:item_qr_png', args=[self.item.pk])
        self.assertContains(resposta, f'<img class="qr-code" src="{png}" alt="QR code de Caixa de som">', html=True)

    def test_oferece_o_download_do_png(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'download="qr-caixa-de-som.png"')

    def test_item_removido_retorna_404(self):
        ItemCASD.objects.filter(pk=self.item.pk).update(is_active=False)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)


class ItemQrItemDaZeladoriaTestCase(TestCase):
    def test_item_da_zeladoria_nao_tem_qr_code(self):
        zeladoria = ItemZeladoria.objects.create(nome='Detergente', quant_total=5)
        self.client.force_login(criar_admin())
        resposta = self.client.get(reverse('estoque:item_qr', args=[zeladoria.pk]))
        self.assertEqual(resposta.status_code, 404)


class ItemQrPngViewTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)
        self.url = reverse('estoque:item_qr_png', args=[self.item.pk])
        self.client.force_login(criar_admin())

    def test_responde_com_png(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta['Content-Type'], 'image/png')

    def test_corpo_e_um_png(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.content[:8], ASSINATURA_PNG)

    def test_codifica_a_pagina_publica_do_item(self):
        with mock.patch('estoque.views.qr_code_png', return_value=b'png') as qr:
            self.client.get(self.url)
        qr.assert_called_once_with('http://testserver' + reverse('estoque:item_detail', args=[self.item.pk]))

    @override_settings(ALLOWED_HOSTS=['estocasd.example'])
    def test_codifica_o_host_e_o_esquema_da_requisicao(self):
        with mock.patch('estoque.views.qr_code_png', return_value=b'png') as qr:
            self.client.get(self.url, secure=True, HTTP_HOST='estocasd.example')
        qr.assert_called_once_with('https://estocasd.example' + reverse('estoque:item_detail', args=[self.item.pk]))

    def test_item_removido_retorna_404(self):
        ItemCASD.objects.filter(pk=self.item.pk).update(is_active=False)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 404)


class ItemQrSemLoginTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)
        self.login = reverse('autenticacao:login')

    def test_pagina_redireciona_para_o_login(self):
        url = reverse('estoque:item_qr', args=[self.item.pk])
        resposta = self.client.get(url)
        self.assertRedirects(resposta, f'{self.login}?next={url}', fetch_redirect_response=False)

    def test_png_redireciona_para_o_login(self):
        url = reverse('estoque:item_qr_png', args=[self.item.pk])
        resposta = self.client.get(url)
        self.assertRedirects(resposta, f'{self.login}?next={url}', fetch_redirect_response=False)


class ItemListBotaoQrTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)
        self.url = reverse('estoque:item_list')

    def test_admin_ve_o_botao_qr_code(self):
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        link = reverse('estoque:item_qr', args=[self.item.pk])
        self.assertContains(resposta, f'<a class="btn" href="{link}">QR code</a>', html=True)

    def test_admin_ve_um_botao_por_item(self):
        ItemCASD.objects.create(nome='Escada', quant_total=2)
        self.client.force_login(criar_admin())
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'QR code', count=2)

    def test_visitante_nao_ve_o_botao_qr_code(self):
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, 'QR code')