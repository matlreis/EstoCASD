from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Emprestimo, ItemCASD, ItemZeladoria, Morador
from .services import EstoqueService
from .helpers_tests import AT, DE, criar_emprestimo, status_atual


def dados_item(**alteracoes):
    dados = {'nome': 'Caixa de som', 'quant_total': 3}
    dados.update(alteracoes)
    return dados


class ListItemsTestCase(TestCase):
    def test_sem_itens_retorna_lista_vazia(self):
        self.assertEqual(list(EstoqueService.list_items()), [])

    def test_ordena_por_nome(self):
        for nome in ['Tapete', 'Bola', 'Caixa']:
            ItemCASD.objects.create(nome=nome, quant_total=1)
        self.assertEqual([i.nome for i in EstoqueService.list_items()], ['Bola', 'Caixa', 'Tapete'])

    def test_nao_inclui_item_removido(self):
        removido = ItemCASD.objects.create(nome='Bola', quant_total=1, is_active=False)
        self.assertNotIn(removido, EstoqueService.list_items())

    def test_inclui_item_totalmente_emprestado(self):
        esgotado = ItemCASD.objects.create(nome='Bola', quant_total=2, quant_emprestada=2)
        self.assertIn(esgotado, EstoqueService.list_items())

    def test_inclui_item_com_total_zero(self):
        vazio = ItemCASD.objects.create(nome='Bola', quant_total=0)
        self.assertIn(vazio, EstoqueService.list_items())

    def test_nao_inclui_itens_da_zeladoria(self):
        ItemZeladoria.objects.create(nome='Vassoura', quant_total=2)
        self.assertEqual(list(EstoqueService.list_items()), [])

    def test_nomes_repetidos_aparecem_todos(self):
        ItemCASD.objects.create(nome='Bola', quant_total=1)
        ItemCASD.objects.create(nome='Bola', quant_total=1)
        self.assertEqual(len(EstoqueService.list_items()), 2)

    def test_faz_uma_unica_consulta(self):
        for nome in ['Bola', 'Caixa', 'Tapete']:
            ItemCASD.objects.create(nome=nome, quant_total=1)
        with self.assertNumQueries(1):
            list(EstoqueService.list_items())


class CreateItemTestCase(TestCase):
    def test_retorna_o_item_criado(self):
        item = EstoqueService.create_item(dados_item())
        self.assertEqual(ItemCASD.objects.get(), item)

    def test_guarda_nome_e_quantidade_total(self):
        item = EstoqueService.create_item(dados_item(nome='Bola', quant_total=7))
        self.assertEqual((item.nome, item.quant_total), ('Bola', 7))

    def test_item_novo_comeca_ativo(self):
        item = EstoqueService.create_item(dados_item())
        self.assertTrue(item.is_active)

    def test_item_novo_comeca_sem_unidades_emprestadas(self):
        item = EstoqueService.create_item(dados_item())
        self.assertEqual(item.quant_emprestada, 0)

    def test_item_novo_aparece_na_listagem(self):
        item = EstoqueService.create_item(dados_item())
        self.assertIn(item, EstoqueService.list_items())

    def test_item_novo_esta_totalmente_disponivel(self):
        item = EstoqueService.create_item(dados_item(quant_total=4))
        self.assertEqual(item.quant_disponivel, 4)

    def test_sem_quantidade_usa_o_padrao_de_uma_unidade(self):
        item = EstoqueService.create_item({'nome': 'Bola'})
        self.assertEqual(item.quant_total, 1)

    def test_quantidade_zero_nasce_sem_disponibilidade(self):
        item = EstoqueService.create_item(dados_item(quant_total=0))
        self.assertEqual(item.quant_disponivel, 0)

    def test_aceita_nomes_repetidos(self):
        EstoqueService.create_item(dados_item())
        EstoqueService.create_item(dados_item())
        self.assertEqual(ItemCASD.objects.count(), 2)

    def test_recusa_quantidade_negativa(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EstoqueService.create_item(dados_item(quant_total=-1))

    def test_quantidade_negativa_nao_cria_item(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EstoqueService.create_item(dados_item(quant_total=-1))
        self.assertFalse(ItemCASD.objects.exists())

    def test_recusa_campo_que_o_item_nao_tem(self):
        with self.assertRaises(TypeError):
            EstoqueService.create_item(dados_item(cor='azul'))


class UpdateItemTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=2)

    def test_retorna_o_item_atualizado(self):
        atualizado = EstoqueService.update_item(self.item, dados_item(nome='Caixa JBL', quant_total=5))
        self.assertEqual((atualizado.pk, atualizado.nome), (self.item.pk, 'Caixa JBL'))

    def test_altera_o_nome(self):
        EstoqueService.update_item(self.item, dados_item(nome='Caixa JBL', quant_total=5))
        self.item.refresh_from_db()
        self.assertEqual(self.item.nome, 'Caixa JBL')

    def test_altera_a_quantidade_total(self):
        EstoqueService.update_item(self.item, dados_item(quant_total=9))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_total, 9)

    def test_aumentar_o_total_aumenta_a_disponibilidade(self):
        EstoqueService.update_item(self.item, dados_item(quant_total=10))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_disponivel, 8)

    def test_nao_altera_a_quantidade_emprestada(self):
        EstoqueService.update_item(self.item, dados_item(quant_total=10))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_emprestada, 2)

    def test_mantem_o_item_ativo(self):
        EstoqueService.update_item(self.item, dados_item(quant_total=10))
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_nao_reativa_item_removido(self):
        ItemCASD.objects.filter(pk=self.item.pk).update(is_active=False)
        EstoqueService.update_item(self.item, dados_item(quant_total=10))
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_nao_altera_outros_itens(self):
        outro = ItemCASD.objects.create(nome='Escada', quant_total=2)
        EstoqueService.update_item(self.item, dados_item(nome='Caixa JBL', quant_total=10))
        outro.refresh_from_db()
        self.assertEqual((outro.nome, outro.quant_total), ('Escada', 2))

    def test_nao_altera_os_emprestimos_do_item(self):
        pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
        emprestimo = criar_emprestimo(self.item, pedro, quant=2)
        EstoqueService.update_item(self.item, dados_item(quant_total=10))
        self.assertEqual((status_atual(emprestimo), emprestimo.quant), (AT, 2))

    def test_item_apagado_do_banco_levanta_does_not_exist(self):
        ItemCASD.objects.filter(pk=self.item.pk).delete()
        with self.assertRaises(ItemCASD.DoesNotExist):
            EstoqueService.update_item(self.item, dados_item(quant_total=10))


class UpdateItemLimiteTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=3)

    def test_aceita_total_igual_ao_emprestado(self):
        item = EstoqueService.update_item(self.item, dados_item(quant_total=3))
        self.assertEqual(item.quant_disponivel, 0)

    def test_recusa_total_um_abaixo_do_emprestado(self):
        with self.assertRaises(ValidationError):
            EstoqueService.update_item(self.item, dados_item(quant_total=2))

    def test_mensagem_informa_a_quantidade_emprestada(self):
        with self.assertRaisesMessage(ValidationError, 'emprestada (3)'):
            EstoqueService.update_item(self.item, dados_item(quant_total=2))

    def test_recusa_total_zero_com_unidades_emprestadas(self):
        with self.assertRaises(ValidationError):
            EstoqueService.update_item(self.item, dados_item(quant_total=0))

    def test_aceita_total_zero_sem_unidades_emprestadas(self):
        livre = ItemCASD.objects.create(nome='Bola', quant_total=4)
        item = EstoqueService.update_item(livre, dados_item(nome='Bola', quant_total=0))
        self.assertEqual(item.quant_total, 0)

    def test_recusa_nao_altera_o_total(self):
        with self.assertRaises(ValidationError):
            EstoqueService.update_item(self.item, dados_item(quant_total=2))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_total, 5)

    def test_recusa_nao_altera_o_nome(self):
        with self.assertRaises(ValidationError):
            EstoqueService.update_item(self.item, dados_item(nome='Caixa JBL', quant_total=2))
        self.item.refresh_from_db()
        self.assertEqual(self.item.nome, 'Caixa de som')

    def test_usa_a_quantidade_emprestada_do_banco_e_nao_a_da_instancia_recebida(self):
        ItemCASD.objects.filter(pk=self.item.pk).update(quant_emprestada=5)
        with self.assertRaises(ValidationError):
            EstoqueService.update_item(self.item, dados_item(quant_total=4))


class DeleteItemTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=3)

    def test_desativa_o_item(self):
        EstoqueService.delete_item(self.item)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_mantem_o_registro_no_banco(self):
        EstoqueService.delete_item(self.item)
        self.assertTrue(ItemCASD.objects.filter(pk=self.item.pk).exists())

    def test_nao_altera_as_quantidades(self):
        EstoqueService.delete_item(self.item)
        self.item.refresh_from_db()
        self.assertEqual((self.item.quant_total, self.item.quant_emprestada), (3, 0))

    def test_item_removido_sai_da_listagem(self):
        EstoqueService.delete_item(self.item)
        self.assertNotIn(self.item, EstoqueService.list_items())

    def test_nao_remove_outros_itens(self):
        outro = ItemCASD.objects.create(nome='Escada', quant_total=2)
        EstoqueService.delete_item(self.item)
        outro.refresh_from_db()
        self.assertTrue(outro.is_active)

    def test_remover_duas_vezes_nao_falha(self):
        EstoqueService.delete_item(self.item)
        EstoqueService.delete_item(self.item)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_permite_cadastrar_outro_item_com_o_mesmo_nome(self):
        EstoqueService.delete_item(self.item)
        novo = EstoqueService.create_item(dados_item())
        self.assertEqual(list(EstoqueService.list_items()), [novo])

    def test_preserva_o_historico_de_emprestimos_devolvidos(self):
        pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')
        criar_emprestimo(self.item, pedro, status=DE)
        EstoqueService.delete_item(self.item)
        self.assertTrue(Emprestimo.objects.filter(id_item=self.item).exists())

    def test_item_apagado_do_banco_levanta_does_not_exist(self):
        ItemCASD.objects.filter(pk=self.item.pk).delete()
        with self.assertRaises(ItemCASD.DoesNotExist):
            EstoqueService.delete_item(self.item)


class DeleteItemEmprestimosTestCase(TestCase):
    def setUp(self):
        self.item = ItemCASD.objects.create(nome='Caixa de som', quant_total=5, quant_emprestada=1)
        self.pedro = Morador.objects.create(nome='Pedro', ap='101J', email='pedro@test.com')

    def test_bloqueia_com_emprestimo_ativo(self):
        criar_emprestimo(self.item, self.pedro, status=AT)
        with self.assertRaises(ValidationError):
            EstoqueService.delete_item(self.item)

    def test_mensagem_explica_o_motivo(self):
        criar_emprestimo(self.item, self.pedro, status=AT)
        with self.assertRaisesMessage(ValidationError, 'empréstimos em andamento'):
            EstoqueService.delete_item(self.item)

    def test_bloqueia_se_so_um_dos_emprestimos_esta_ativo(self):
        criar_emprestimo(self.item, self.pedro, status=DE)
        criar_emprestimo(self.item, self.pedro, status=AT)
        with self.assertRaises(ValidationError):
            EstoqueService.delete_item(self.item)

    def test_libera_com_varios_emprestimos_devolvidos(self):
        criar_emprestimo(self.item, self.pedro, status=DE)
        criar_emprestimo(self.item, self.pedro, status=DE)
        EstoqueService.delete_item(self.item)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_emprestimo_de_outro_item_nao_bloqueia(self):
        escada = ItemCASD.objects.create(nome='Escada', quant_total=1, quant_emprestada=1)
        criar_emprestimo(escada, self.pedro, status=AT)
        EstoqueService.delete_item(self.item)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

    def test_considera_emprestimo_criado_depois_da_leitura_do_item(self):
        item_lido = ItemCASD.objects.get(pk=self.item.pk)
        criar_emprestimo(self.item, self.pedro, status=AT)
        with self.assertRaises(ValidationError):
            EstoqueService.delete_item(item_lido)

    def test_recusa_mantem_o_item_ativo(self):
        criar_emprestimo(self.item, self.pedro, status=AT)
        with self.assertRaises(ValidationError):
            EstoqueService.delete_item(self.item)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_recusa_mantem_o_item_na_listagem(self):
        criar_emprestimo(self.item, self.pedro, status=AT)
        with self.assertRaises(ValidationError):
            EstoqueService.delete_item(self.item)
        self.assertIn(self.item, EstoqueService.list_items())