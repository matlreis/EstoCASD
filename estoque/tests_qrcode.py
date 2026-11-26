from django.test import TestCase
from django.urls import reverse

from .models import ItemCASD, ItemZeladoria


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