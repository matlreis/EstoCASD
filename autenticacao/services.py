from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Admin


class AutenticacaoService:
    @staticmethod
    @transaction.atomic
    def cadastrar(nome, email, senha):
        admin = Admin.objects.create_user(email=email, nome=nome, 
                                          password=senha)
        return admin

    @staticmethod
    def autenticar(email, senha):
        admin = authenticate(email=email, password=senha)
        if admin is None:
            raise ValidationError('Email ou senha incorretos.')
        return admin