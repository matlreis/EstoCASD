from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import LogEvento


class Item(models.Model):
    nome = models.CharField(max_length=255)
    quant_total = models.PositiveIntegerField('quantidade total', default=1)

    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.nome


class ItemCASD(Item):
    quant_emprestada = models.PositiveIntegerField('quantidade emprestada', default=0)

    class Meta(Item.Meta):
        verbose_name = 'item do CASD'
        verbose_name_plural = 'itens do CASD'

    @property
    def quant_disponivel(self) -> int:
        return self.quant_total - self.quant_emprestada


class ItemZeladoria(Item):
    preco_unitario = models.DecimalField(
        'preço unitário', max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )

    class Meta(Item.Meta):
        verbose_name = 'item da zeladoria'
        verbose_name_plural = 'itens da zeladoria'


class LogItemZeladoria(LogEvento):
    id_item = models.ForeignKey(ItemZeladoria, on_delete=models.CASCADE, db_column='id_item')
    id_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='id_admin')

    quant_anterior = models.PositiveIntegerField(null=True, blank=True)
    quant_nova = models.PositiveIntegerField(null=True, blank=True)

    class Evento(models.TextChoices):
        CRIADO = 'CRIADO', 'Criado'
        VENDA = 'VENDA', 'Venda'
        QUANT_ALTERADA = 'QUANTIDADE_ALTERADA', 'Quantidade total alterada'
        REMOVIDO = 'REMOVIDO', 'Removido'

    event_type = models.CharField(max_length=20, choices=Evento.choices)

    class Meta(LogEvento.Meta):
        verbose_name = 'log de item da zeladoria'
        verbose_name_plural = 'logs de itens da zeladoria'


class Morador(models.Model):
    nome = models.CharField(max_length=255)
    ap = models.CharField(max_length=4)
    email = models.EmailField(unique=True)

    class Meta:
        verbose_name = 'morador'
        verbose_name_plural = 'moradores'

    def __str__(self):
        return f'{self.nome} ({self.ap})'


class EmprestimoQuerySet(models.QuerySet):
    def ativos(self):
        return self.exclude(status=Emprestimo.StatusEmprestimo.DE)

    def atrasados(self):
        return self.filter(status=Emprestimo.StatusEmprestimo.AT,
                           limit_date__lt=timezone.localdate())

    def devolvidos(self):
        return self.filter(status=Emprestimo.StatusEmprestimo)


class Emprestimo(models.Model):
    id_item = models.ForeignKey(ItemCASD, on_delete=models.PROTECT, db_column='id_item')
    id_morador = models.ForeignKey(Morador, on_delete=models.PROTECT, db_column='id_morador')

    class StatusEmprestimo(models.TextChoices):
        AT = 'ATIVO', 'Ativo'
        DS = 'DEVOLUCAO_SINALIZADA', 'Devolução sinalizada'
        DE = 'DEVOLVIDO', 'Devolvido'

    status = models.CharField(max_length=20, choices=StatusEmprestimo.choices, default=StatusEmprestimo.AT)

    limit_date = models.DateField('devolução prevista')
    quant = models.PositiveIntegerField('quantidade', default=1)

    objects = EmprestimoQuerySet.as_manager()

    class Meta:
        verbose_name = 'empréstimo'
        verbose_name_plural = 'empréstimos'

    def __str__(self):
        return f'{self.id_item} x{self.quant} para {self.id_morador}'


class LogEmprestimo(LogEvento):
    id_emprestimo = models.ForeignKey(Emprestimo, on_delete=models.CASCADE, db_column='id_emprestimo')
    id_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                        db_column='id_admin', null=True, blank=True)

    class Evento(models.TextChoices):
        CRIADO = 'CRIADO', 'Criado'
        DEVOLUCAO_SINALIZADA = 'DEVOLUCAO_SINALIZADA', 'Devolução sinalizada'
        DEVOLUCAO_CONFIRMADA = 'DEVOLUCAO_CONFIRMADA', 'Devolução confirmada'

    event_type = models.CharField(max_length=20, choices=Evento.choices)


class Venda(models.Model):
    id_item = models.ForeignKey(ItemZeladoria, on_delete=models.PROTECT, db_column='id_item')
    id_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='id_admin')

    nome_comprador = models.CharField('nome do comprador', max_length=255)
    ap_vaga = models.CharField('AP e vaga', max_length=50)

    quant = models.PositiveIntegerField('quantidade', validators=[MinValueValidator(1)])
    # copiado do item no momento da venda: o preço do item pode mudar depois
    preco_unitario = models.DecimalField('preço unitário', max_digits=8, decimal_places=2)
    notas = models.TextField(blank=True)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'venda'
        verbose_name_plural = 'vendas'

    @property
    def total(self):
        return self.quant * self.preco_unitario
