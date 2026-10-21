from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


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
    nome = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects:AdminManager = AdminManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome']

    class Meta:
        db_table = 'admin'

    def __str__(self):
        return self.nome


class Item(models.Model):
    nome = models.CharField(max_length=255)

    class TipoEstoque(models.TextChoices):
            CASD = 'CASD'
            ZELA = 'ZELADORIA'

    tipo_estoque = models.CharField(max_length=20, choices=TipoEstoque.choices)

    quant_total = models.PositiveIntegerField()
    quant_uso = models.PositiveIntegerField(default=0)

    @property
    def quant_disponivel(self) -> int:
        return self.quant_total - self.quant_uso


class Morador(models.Model):
    nome = models.CharField(max_length=255)
    ap = models.CharField(max_length=4)
    email = models.EmailField(unique=True)


class Transacao(models.Model):
    id_item = models.ForeignKey(Item, on_delete=models.PROTECT, db_column='id_item')

    class StatusTransacao(models.TextChoices):
        AT = 'ATIVO'
        DS = 'DEVOLUCAO_SINALIZADA'
        DE = 'DEVOLVIDO'

    status = models.CharField(max_length=20, choices=StatusTransacao.choices)

    limit_date = models.DateTimeField()
    quant = models.PositiveIntegerField(default=1)

    @property
    def atrasado(self) -> bool:
        return timezone.now() > self.limit_date

    class Meta:
        abstract = True


class Emprestimo(Transacao):
    id_morador = models.ForeignKey(Morador, on_delete=models.PROTECT, db_column='id_morador')


class Uso(Transacao):
    id_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='id_admin')
    

class LogEvento(models.Model):
    ip_aparelho = models.GenericIPAddressField()
    
    event_date = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20)

    class Meta:
        abstract = True


class LogAdmin(LogEvento):
    id_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='id_admin')


class LogUso(LogEvento):
    id_uso = models.ForeignKey(Uso, on_delete=models.CASCADE, db_column='id_uso')


class LogEmprestimo(LogEvento):
    id_emprestimo = models.ForeignKey(Emprestimo, on_delete=models.CASCADE, db_column='id_emprestimo')