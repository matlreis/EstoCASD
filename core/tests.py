from datetime import date
from django.test import RequestFactory, SimpleTestCase
from .utils import get_client_ip, proximo_dia_util, somar_dias_uteis


class GetClientIpTestCase(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_sem_proxy_usa_remote_addr(self):
        request = self.factory.get('/', REMOTE_ADDR='203.0.113.5')
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.5')

    def test_atras_de_proxy_usa_x_forwarded_for(self):
        request = self.factory.get('/', REMOTE_ADDR='10.0.0.1', HTTP_X_FORWARDED_FOR='203.0.113.5')
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.5')

    def test_x_forwarded_for_com_varios_ips_usa_o_primeiro(self):
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='203.0.113.5, 10.0.0.1')
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.5')

    def test_sem_request_retorna_none(self):
        ip = get_client_ip(None)
        self.assertIsNone(ip)

    def test_x_forwarded_for_vazio_usa_remote_addr(self):
        request = self.factory.get('/', REMOTE_ADDR='203.0.113.5', HTTP_X_FORWARDED_FOR='')
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.5')

    def test_x_forwarded_for_com_espacos_retorna_o_ip_limpo(self):
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='  203.0.113.5  , 10.0.0.1')
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.5')

    def test_x_forwarded_for_aceita_ipv6(self):
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='2001:db8::1, 10.0.0.1')
        ip = get_client_ip(request)
        self.assertEqual(ip, '2001:db8::1')

    def test_sem_x_forwarded_for_e_sem_remote_addr_retorna_none(self):
        request = self.factory.get('/')
        del request.META['REMOTE_ADDR']
        ip = get_client_ip(request)
        self.assertIsNone(ip)


class ProximoDiaUtilTestCase(SimpleTestCase):
    def test_dia_util_devolve_a_mesma_data(self):
        resultado = proximo_dia_util(date(2026, 11, 5))
        self.assertEqual(resultado, date(2026, 11, 5))

    def test_sexta_devolve_a_mesma_data(self):
        resultado = proximo_dia_util(date(2026, 11, 6))
        self.assertEqual(resultado, date(2026, 11, 6))

    def test_sabado_devolve_a_segunda(self):
        resultado = proximo_dia_util(date(2026, 11, 7))
        self.assertEqual(resultado, date(2026, 11, 9))

    def test_domingo_devolve_a_segunda(self):
        resultado = proximo_dia_util(date(2026, 11, 8))
        self.assertEqual(resultado, date(2026, 11, 9))


class SomarDiasUteisTestCase(SimpleTestCase):
    def test_de_segunda_soma_um_dia_util_e_vai_para_terca(self):
        resultado = somar_dias_uteis(date(2026, 11, 2), 1)
        self.assertEqual(resultado, date(2026, 11, 3))

    def test_de_sexta_soma_um_dia_util_e_vai_para_segunda(self):
        resultado = somar_dias_uteis(date(2026, 11, 6), 1)
        self.assertEqual(resultado, date(2026, 11, 9))

    def test_de_sabado_soma_um_dia_util_e_vai_para_segunda(self):
        resultado = somar_dias_uteis(date(2026, 11, 7), 1)
        self.assertEqual(resultado, date(2026, 11, 9))

    def test_de_domingo_soma_um_dia_util_e_vai_para_segunda(self):
        resultado = somar_dias_uteis(date(2026, 11, 8), 1)
        self.assertEqual(resultado, date(2026, 11, 9))

    def test_cinco_dias_uteis_a_partir_de_quinta_caem_na_quinta_seguinte(self):
        resultado = somar_dias_uteis(date(2026, 11, 5), 5)
        self.assertEqual(resultado, date(2026, 11, 12))

    def test_cinco_dias_uteis_a_partir_de_sabado_caem_na_sexta_seguinte(self):
        resultado = somar_dias_uteis(date(2026, 11, 7), 5)
        self.assertEqual(resultado, date(2026, 11, 13))

    def test_zero_dias_uteis_devolve_a_mesma_data(self):
        resultado = somar_dias_uteis(date(2026, 11, 7), 0)
        self.assertEqual(resultado, date(2026, 11, 7))