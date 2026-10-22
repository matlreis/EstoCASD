from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from core.models import LogEvento

class AdminManager(BaseUserManager):
    def create_user(self, email, nome, password=None):
        if not email:
            raise ValueError('O email é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, nome=nome)
        
        user.set_password(password) 
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nome, password=None):
        user = self.create_user(email, nome, password)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user
    

class Admin(AbstractBaseUser, PermissionsMixin):
    nome = models.CharField('nome', max_length=255)
    email = models.EmailField('e-mail', unique=True)

    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    is_active = models.BooleanField(
        'ativo', default=True,
        help_text='Desmarque para bloquear o acesso.',
    )
    is_staff = models.BooleanField('acesso ao painel', default=False)
    is_superuser = models.BooleanField(
        'gestor', default=False,
        help_text='Gerencia contas e consulta logs no painel de admin.', 
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome']

    objects = AdminManager()

    class Meta:
        db_table = 'admin'
        verbose_name = 'administrador'
        verbose_name_plural = 'administradores'

    def __str__(self):
        return self.nome


class LogAdmin(LogEvento):
    id_admin = models.ForeignKey(settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, db_column='id_admin')

    class Meta(LogEvento.Meta):
        verbose_name = 'log de administrador'
        verbose_name_plural = 'logs de administradores'