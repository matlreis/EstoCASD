from django.apps import AppConfig


class AutenticacaoConfig(AppConfig):
    name = 'autenticacao'

    def ready(self):
        from . import signals
