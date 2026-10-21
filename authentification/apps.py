from django.apps import AppConfig


class AutentificationConfig(AppConfig):
    name = 'authentification'

    def ready(self):
        import database.signals
