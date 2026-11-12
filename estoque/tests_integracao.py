"""
Testes de integração do app estoque.
Cada classe é um cenário: o setUp executa os passos pelo site, como um usuário faria.
"""
from datetime import timedelta

from django.contrib.messages import get_messages
from django.db.models import Sum
from django.test import Client, TestCase
from django.urls import reverse

from .helpers_tests import AT, DE, DS, FIXAR_HOJE, HOJE, criar_admin
from .models import Emprestimo, ItemCASD, ItemZeladoria, LogEmprestimo, Morador
from .services import PRAZO_MAX_DIAS, ZeladoriaService


class FluxoTestCase(TestCase):
    """Base dos cenários: monta o ambiente e reúne os passos que alguém daria pelo site."""

    def setUp(self):
        # o FIXAR_HOJE aplicado na classe só vale para os métodos test_*, e não para o setUp
        self.enterContext(FIXAR_HOJE)
        self.anonimo = Client()
        self.admin = criar_admin()
        self.cliente_admin = Client()
        self.cliente_admin.force_login(self.admin)

    # passos de quem cuida do estoque (admin logado)
    def cadastrar_item(self, nome='Caixa de som', quant_total=3):
        self.cliente_admin.post(reverse('estoque:item_create'), {'nome': nome, 'quant_total': quant_total})
        return ItemCASD.objects.get(nome=nome, is_active=True)

    def editar_item(self, item, quant_total):
        url = reverse('estoque:item_update', args=[item.pk])
        return self.cliente_admin.post(url, {'nome': item.nome, 'quant_total': quant_total})

    def remover_item(self, item):
        return self.cliente_admin.post(reverse('estoque:item_delete', args=[item.pk]))

    def confirmar_devolucao(self, emprestimo):
        return self.cliente_admin.post(reverse('estoque:devolucao_confirmar', args=[emprestimo.pk]))

    # passos de quem pega o item emprestado (sem login)
    def emprestar(self, item, quant=1, nome='Pedro', email='pedro@test.com', dias=1):
        dados = {'nome': nome, 'ap': '101J', 'email': email, 'quant': quant,
                 'limit_date': (HOJE + timedelta(days=dias)).isoformat()}
        return self.anonimo.post(reverse('estoque:emprestimo_create', args=[item.pk]), dados)

    def sinalizar_devolucao(self, item, email='pedro@test.com'):
        return self.anonimo.post(reverse('estoque:devolucao_sinalizar', args=[item.pk]), {'email': email})

    # leituras do estado
    def item_atual(self, item):
        return ItemCASD.objects.get(pk=item.pk)

    def itens_da_listagem(self):
        return list(self.anonimo.get(reverse('estoque:item_list')).context['itens'])

    def emprestimos_na_lista_do_admin(self):
        return list(self.cliente_admin.get(reverse('estoque:emprestimo_list')).context['emprestimos'])

    def eventos_do_emprestimo(self, emprestimo):
        logs = LogEmprestimo.objects.filter(id_emprestimo=emprestimo).order_by('pk')
        return list(logs.values_list('event_type', flat=True))

    def mensagens(self, resposta):
        return [str(m) for m in get_messages(resposta.wsgi_request)]


class CadastroPeloAdminTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)

    def test_item_aparece_na_listagem_publica(self):
        self.assertEqual(self.itens_da_listagem(), [self.item])

    def test_item_novo_esta_totalmente_disponivel(self):
        self.assertEqual(self.itens_da_listagem()[0].quant_disponivel, 3)

    def test_item_novo_pode_ser_emprestado_por_inteiro(self):
        self.emprestar(self.item, quant=3)
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 0)


class EmprestimoPeloSiteTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=2)
        self.emprestimo = Emprestimo.objects.get()

    def test_item_perde_as_unidades_emprestadas(self):
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 1)

    def test_listagem_publica_mostra_a_nova_disponibilidade(self):
        self.assertEqual(self.itens_da_listagem()[0].quant_disponivel, 1)

    def test_emprestimo_nasce_ativo(self):
        self.assertEqual(self.emprestimo.status, AT)

    def test_emprestimo_aparece_na_lista_do_admin(self):
        self.assertEqual(self.emprestimos_na_lista_do_admin(), [self.emprestimo])

    def test_log_registra_a_criacao(self):
        self.assertEqual(self.eventos_do_emprestimo(self.emprestimo), [LogEmprestimo.Evento.CRIADO])


class DevolucaoSinalizadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=2)
        self.emprestimo = Emprestimo.objects.get()
        self.sinalizar_devolucao(self.item)

    def test_status_vira_devolucao_sinalizada(self):
        self.emprestimo.refresh_from_db()
        self.assertEqual(self.emprestimo.status, DS)

    def test_unidades_continuam_emprestadas_ate_o_admin_confirmar(self):
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 1)

    def test_emprestimo_continua_na_lista_do_admin(self):
        self.assertEqual(self.emprestimos_na_lista_do_admin(), [self.emprestimo])

    def test_log_registra_criacao_e_sinalizacao_em_ordem(self):
        eventos = [LogEmprestimo.Evento.CRIADO, LogEmprestimo.Evento.DEVOLUCAO_SINALIZADA]
        self.assertEqual(self.eventos_do_emprestimo(self.emprestimo), eventos)


class DevolucaoConfirmadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=2)
        self.emprestimo = Emprestimo.objects.get()
        self.sinalizar_devolucao(self.item)
        self.confirmar_devolucao(self.emprestimo)

    def test_unidades_voltam_ao_estoque(self):
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 3)

    def test_status_vira_devolvido(self):
        self.emprestimo.refresh_from_db()
        self.assertEqual(self.emprestimo.status, DE)

    def test_emprestimo_sai_da_lista_do_admin(self):
        self.assertEqual(self.emprestimos_na_lista_do_admin(), [])

    def test_log_registra_o_ciclo_inteiro_em_ordem(self):
        evento = LogEmprestimo.Evento
        eventos = [evento.CRIADO, evento.DEVOLUCAO_SINALIZADA, evento.DEVOLUCAO_CONFIRMADA]
        self.assertEqual(self.eventos_do_emprestimo(self.emprestimo), eventos)

    def test_log_da_confirmacao_guarda_o_admin(self):
        ultimo_log = LogEmprestimo.objects.order_by('pk').last()
        self.assertEqual(ultimo_log.id_admin, self.admin)

    def test_item_volta_a_poder_ser_emprestado_por_inteiro(self):
        self.emprestar(self.item, quant=3)
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 0)


class ConfirmarSemSinalizarTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=2)
        self.emprestimo = Emprestimo.objects.get()
        self.confirmar_devolucao(self.emprestimo)

    def test_unidades_voltam_ao_estoque(self):
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 3)

    def test_log_registra_so_criacao_e_confirmacao(self):
        evento = LogEmprestimo.Evento
        self.assertEqual(self.eventos_do_emprestimo(self.emprestimo),
                         [evento.CRIADO, evento.DEVOLUCAO_CONFIRMADA])


class EstoqueEsgotadoTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=2)
        self.emprestar(self.item, quant=1, nome='Pedro', email='pedro@test.com')
        self.emprestar(self.item, quant=1, nome='Ana', email='ana@test.com')
        self.do_pedro = Emprestimo.objects.get(id_morador__email='pedro@test.com')

    def test_item_esgotado_continua_na_listagem(self):
        self.assertEqual(self.itens_da_listagem(), [self.item])

    def test_listagem_mostra_zero_unidades_disponiveis(self):
        self.assertEqual(self.itens_da_listagem()[0].quant_disponivel, 0)

    def test_novo_emprestimo_e_recusado(self):
        self.emprestar(self.item, quant=1, nome='Bia', email='bia@test.com')
        self.assertEqual(Emprestimo.objects.count(), 2)

    def test_recusa_informa_que_nao_ha_unidades(self):
        resposta = self.emprestar(self.item, quant=1, nome='Bia', email='bia@test.com')
        self.assertIn('Quantidade indisponível. Disponível: 0.', resposta.context['form'].non_field_errors())

    def test_recusa_nao_cadastra_o_morador(self):
        self.emprestar(self.item, quant=1, nome='Bia', email='bia@test.com')
        self.assertFalse(Morador.objects.filter(email='bia@test.com').exists())

    def test_depois_de_uma_devolucao_o_emprestimo_volta_a_ser_aceito(self):
        self.confirmar_devolucao(self.do_pedro)
        self.emprestar(self.item, quant=1, nome='Bia', email='bia@test.com')
        self.assertEqual(Emprestimo.objects.ativos().count(), 2)


class ItemRemovidoTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.remover_item(self.item)

    def test_item_sai_da_listagem_publica(self):
        self.assertEqual(self.itens_da_listagem(), [])

    def test_pagina_de_emprestimo_deixa_de_existir(self):
        resposta = self.anonimo.get(reverse('estoque:emprestimo_create', args=[self.item.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_pagina_de_devolucao_deixa_de_existir(self):
        resposta = self.anonimo.get(reverse('estoque:devolucao_sinalizar', args=[self.item.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_envio_do_formulario_de_emprestimo_nao_cria_emprestimo(self):
        self.emprestar(self.item)
        self.assertFalse(Emprestimo.objects.exists())

    def test_item_nao_pode_mais_ser_editado(self):
        resposta = self.cliente_admin.get(reverse('estoque:item_update', args=[self.item.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_registro_continua_no_banco(self):
        self.assertTrue(ItemCASD.objects.filter(pk=self.item.pk).exists())

    def test_permite_cadastrar_outro_item_com_o_mesmo_nome(self):
        novo = self.cadastrar_item(quant_total=1)
        self.assertEqual(self.itens_da_listagem(), [novo])


class RemocaoBloqueadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=1)
        self.resposta = self.remover_item(self.item)

    def test_item_continua_ativo(self):
        self.assertTrue(self.item_atual(self.item).is_active)

    def test_item_continua_na_listagem(self):
        self.assertEqual(self.itens_da_listagem(), [self.item])

    def test_admin_recebe_a_mensagem_de_erro(self):
        self.assertIn('Há empréstimos em andamento com este item.', self.mensagens(self.resposta))


class RemocaoComDevolucaoSinalizadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=1)
        self.sinalizar_devolucao(self.item)
        self.remover_item(self.item)

    def test_item_continua_ativo(self):
        self.assertTrue(self.item_atual(self.item).is_active)


class RemocaoLiberadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=1)
        self.emprestimo = Emprestimo.objects.get()
        self.sinalizar_devolucao(self.item)
        self.confirmar_devolucao(self.emprestimo)
        self.remover_item(self.item)

    def test_item_sai_da_listagem(self):
        self.assertEqual(self.itens_da_listagem(), [])

    def test_historico_do_emprestimo_e_preservado(self):
        self.assertTrue(Emprestimo.objects.filter(pk=self.emprestimo.pk).exists())


class EdicaoDeItemEmprestadoTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=2)

    def test_reduzir_abaixo_do_emprestado_e_recusado(self):
        self.editar_item(self.item, quant_total=1)
        self.assertEqual(self.item_atual(self.item).quant_total, 3)

    def test_recusa_informa_a_quantidade_emprestada(self):
        resposta = self.editar_item(self.item, quant_total=1)
        mensagem = 'A quantidade total não pode ser menor que a quantidade emprestada (2).'
        self.assertIn(mensagem, resposta.context['form'].non_field_errors())

    def test_reduzir_ate_o_emprestado_e_aceito(self):
        self.editar_item(self.item, quant_total=2)
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 0)

    def test_aumentar_o_total_libera_novas_unidades(self):
        self.editar_item(self.item, quant_total=5)
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 3)

    def test_edicao_nao_altera_as_unidades_emprestadas(self):
        self.editar_item(self.item, quant_total=5)
        self.assertEqual(self.item_atual(self.item).quant_emprestada, 2)

    def test_novo_emprestimo_respeita_o_total_ampliado(self):
        self.editar_item(self.item, quant_total=5)
        self.emprestar(self.item, quant=3, nome='Ana', email='ana@test.com')
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 0)


class MesmoMoradorComDoisEmprestimosTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=5)
        self.emprestar(self.item, quant=1, email='pedro@test.com')
        self.emprestar(self.item, quant=2, email='PEDRO@Test.com')
        self.primeiro, self.segundo = Emprestimo.objects.order_by('pk')

    def test_morador_e_reaproveitado(self):
        self.assertEqual(Morador.objects.count(), 1)

    def test_email_fica_guardado_em_minusculas(self):
        self.assertEqual(Morador.objects.get().email, 'pedro@test.com')

    def test_os_dois_emprestimos_ficam_ativos(self):
        self.assertEqual(Emprestimo.objects.ativos().count(), 2)

    def test_sinalizar_pega_os_dois_emprestimos(self):
        self.sinalizar_devolucao(self.item)
        self.assertEqual(list(Emprestimo.objects.order_by('pk').values_list('status', flat=True)), [DS, DS])

    def test_confirmar_um_devolve_so_a_quantidade_dele(self):
        self.confirmar_devolucao(self.primeiro)
        self.assertEqual(self.item_atual(self.item).quant_emprestada, 2)

    def test_confirmar_um_nao_altera_o_outro(self):
        self.confirmar_devolucao(self.primeiro)
        self.segundo.refresh_from_db()
        self.assertEqual(self.segundo.status, AT)


class QuantidadeEmprestadaCoerenteTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=6)
        self.emprestar(self.item, quant=1, nome='Ana', email='ana@test.com')
        self.emprestar(self.item, quant=2, nome='Pedro', email='pedro@test.com')
        self.sinalizar_devolucao(self.item, email='pedro@test.com')
        self.confirmar_devolucao(Emprestimo.objects.get(id_morador__email='pedro@test.com'))
        self.editar_item(self.item, quant_total=8)
        self.emprestar(self.item, quant=3, nome='Bia', email='bia@test.com')

    def test_contador_do_item_e_a_soma_dos_emprestimos_em_andamento(self):
        em_andamento = Emprestimo.objects.ativos().filter(id_item=self.item).aggregate(total=Sum('quant'))
        self.assertEqual(self.item_atual(self.item).quant_emprestada, em_andamento['total'])

    def test_disponivel_e_o_total_menos_o_que_esta_emprestado(self):
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 4)


class DataDeDevolucaoInvalidaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)

    def test_data_no_passado_nao_cria_emprestimo(self):
        self.emprestar(self.item, dias=-1)
        self.assertFalse(Emprestimo.objects.exists())

    def test_data_no_passado_informa_o_motivo(self):
        resposta = self.emprestar(self.item, dias=-1)
        self.assertIn('A data de devolução não pode estar no passado.', resposta.context['form'].non_field_errors())

    def test_fim_de_semana_nao_cria_emprestimo(self):
        self.emprestar(self.item, dias=2)
        self.assertFalse(Emprestimo.objects.exists())

    def test_fim_de_semana_informa_o_motivo(self):
        resposta = self.emprestar(self.item, dias=2)
        self.assertIn('A data de devolução não pode cair no fim de semana.', resposta.context['form'].non_field_errors())

    def test_alem_do_prazo_maximo_nao_cria_emprestimo(self):
        self.emprestar(self.item, dias=PRAZO_MAX_DIAS + 1)
        self.assertFalse(Emprestimo.objects.exists())

    def test_alem_do_prazo_maximo_informa_o_motivo(self):
        resposta = self.emprestar(self.item, dias=PRAZO_MAX_DIAS + 1)
        self.assertIn(f'A data de devolução não pode passar de {PRAZO_MAX_DIAS} dias.', resposta.context['form'].non_field_errors())

    def test_ultimo_dia_do_prazo_maximo_e_aceito(self):
        self.emprestar(self.item, dias=PRAZO_MAX_DIAS)
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_recusa_nao_cadastra_o_morador(self):
        self.emprestar(self.item, dias=2)
        self.assertFalse(Morador.objects.exists())

    def test_recusa_nao_gera_log(self):
        self.emprestar(self.item, dias=2)
        self.assertFalse(LogEmprestimo.objects.exists())

    def test_recusa_nao_altera_a_disponibilidade(self):
        self.emprestar(self.item, dias=2)
        self.assertEqual(self.item_atual(self.item).quant_disponivel, 3)


class SinalizarComEmailSemEmprestimoTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=2, email='pedro@test.com')
        self.emprestimo = Emprestimo.objects.get()
        self.resposta = self.sinalizar_devolucao(self.item, email='ana@test.com')

    def test_informa_que_nao_ha_emprestimo_para_o_email(self):
        mensagem = 'Nenhum empréstimo ativo deste item para este e-mail.'
        self.assertIn(mensagem, self.resposta.context['form'].non_field_errors())

    def test_emprestimo_de_outro_morador_continua_ativo(self):
        self.emprestimo.refresh_from_db()
        self.assertEqual(self.emprestimo.status, AT)

    def test_nao_gera_log_de_sinalizacao(self):
        self.assertEqual(self.eventos_do_emprestimo(self.emprestimo), [LogEmprestimo.Evento.CRIADO])

    def test_o_morador_certo_ainda_consegue_sinalizar(self):
        self.sinalizar_devolucao(self.item, email='pedro@test.com')
        self.emprestimo.refresh_from_db()
        self.assertEqual(self.emprestimo.status, DS)


class ConfirmacaoDuplicadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.cadastrar_item(quant_total=3)
        self.emprestar(self.item, quant=2)
        self.emprestimo = Emprestimo.objects.get()
        self.sinalizar_devolucao(self.item)
        self.confirmar_devolucao(self.emprestimo)
        self.segunda_resposta = self.confirmar_devolucao(self.emprestimo)

    def test_unidades_sao_devolvidas_uma_unica_vez(self):
        self.assertEqual(self.item_atual(self.item).quant_emprestada, 0)

    def test_segunda_confirmacao_mostra_o_aviso(self):
        self.assertIn('Este empréstimo já foi devolvido.', self.mensagens(self.segunda_resposta))

    def test_log_registra_a_confirmacao_uma_unica_vez(self):
        evento = LogEmprestimo.Evento
        eventos = [evento.CRIADO, evento.DEVOLUCAO_SINALIZADA, evento.DEVOLUCAO_CONFIRMADA]
        self.assertEqual(self.eventos_do_emprestimo(self.emprestimo), eventos)

    def test_emprestimo_continua_devolvido(self):
        self.emprestimo.refresh_from_db()
        self.assertEqual(self.emprestimo.status, DE)


class ZeladoriaCriadaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        dados = {'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': '12.50'}
        self.cliente_admin.post(reverse('estoque:zeladoria_create'), dados)
        self.item = ItemZeladoria.objects.get()

    def eventos(self):
        return [log.event_type for log in ZeladoriaService.historico(self.item)]

    def test_item_aparece_na_lista_da_zeladoria(self):
        resposta = self.cliente_admin.get(reverse('estoque:zeladoria_list'))
        self.assertEqual(list(resposta.context['itens']), [self.item])

    def test_item_nao_aparece_no_estoque_do_casd(self):
        self.assertEqual(self.itens_da_listagem(), [])

    def test_anonimo_nao_acessa_a_lista_da_zeladoria(self):
        resposta = self.anonimo.get(reverse('estoque:zeladoria_list'))
        self.assertEqual(resposta.status_code, 302)

    def test_historico_comeca_com_o_evento_criado(self):
        self.assertEqual(self.eventos(), ['CRIADO'])


class ZeladoriaQuantidadeAlteradaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.cliente_admin.post(reverse('estoque:zeladoria_create'),
                                {'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': ''})
        self.item = ItemZeladoria.objects.get()
        self.url = reverse('estoque:zeladoria_update', args=[self.item.pk])
        self.cliente_admin.post(self.url, {'nome': 'Extensão', 'quant_total': 8, 'preco_unitario': ''})

    def eventos(self):
        return [log.event_type for log in ZeladoriaService.historico(self.item)]

    def test_quantidade_nova_e_gravada(self):
        self.item.refresh_from_db()
        self.assertEqual(self.item.quant_total, 8)

    def test_evento_mais_recente_guarda_quantidade_anterior_e_nova(self):
        mais_recente = ZeladoriaService.historico(self.item).first()
        self.assertEqual((mais_recente.quant_anterior, mais_recente.quant_nova), (5, 8))

    def test_historico_vai_do_mais_novo_ao_mais_antigo(self):
        self.assertEqual(self.eventos(), ['QUANTIDADE_ALTERADA', 'CRIADO'])

    def test_alterar_so_o_nome_nao_gera_evento(self):
        self.cliente_admin.post(self.url, {'nome': 'Extensão 3m', 'quant_total': 8, 'preco_unitario': ''})
        self.assertEqual(self.eventos(), ['QUANTIDADE_ALTERADA', 'CRIADO'])


class ZeladoriaRemovidaTestCase(FluxoTestCase):
    def setUp(self):
        super().setUp()
        self.cliente_admin.post(reverse('estoque:zeladoria_create'),
                                {'nome': 'Extensão', 'quant_total': 5, 'preco_unitario': ''})
        self.item = ItemZeladoria.objects.get()
        self.cliente_admin.post(reverse('estoque:zeladoria_delete', args=[self.item.pk]))

    def test_item_sai_da_lista_da_zeladoria(self):
        resposta = self.cliente_admin.get(reverse('estoque:zeladoria_list'))
        self.assertEqual(list(resposta.context['itens']), [])

    def test_historico_termina_com_o_evento_removido(self):
        self.assertEqual(ZeladoriaService.historico(self.item).first().event_type, 'REMOVIDO')

    def test_registro_continua_no_banco(self):
        self.assertTrue(ItemZeladoria.objects.filter(pk=self.item.pk).exists())

    def test_item_nao_pode_mais_ser_editado(self):
        resposta = self.cliente_admin.get(reverse('estoque:zeladoria_update', args=[self.item.pk]))
        self.assertEqual(resposta.status_code, 404)