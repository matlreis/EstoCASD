from django.test import RequestFactory, SimpleTestCase
from .utils import get_client_ip


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