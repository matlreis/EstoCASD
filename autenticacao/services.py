from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Admin, LogAdmin


class AutenticacaoService:
    @staticmethod
    @transaction.atomic
    def cadastrar(nome, email, senha, ip=None):
        admin = Admin.objects.create_user(email=email, nome=nome, 
                                          password=senha)
        LogAdmin.objects.create(id_admin=admin, ip_aparelho=ip, 
                                event_type='CONTA_CRIADA')
        return admin

    @staticmethod
    def autenticar(email, senha):
        admin = authenticate(email=email, password=senha)
        if admin is None:
            raise ValidationError('Email ou senha incorretos.')
        return admin