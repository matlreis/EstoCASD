from django.conf import settings
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
    quant_uso = models.PositiveIntegerField('quantidade em uso', default=0)
    preco_unitario = models.DecimalField(
        'preço unitário', max_digits=8, decimal_places=2, null=True, blank=True, 
    )

    class Meta(Item.Meta):
        verbose_name = 'item da zeladoria'
        verbose_name_plural = 'itens da zeladoria'

    @property
    def quant_disponivel(self) -> int:
        return self.quant_total - self.quant_uso

    @property
    def em_uso(self) -> bool:
        return self.quant_uso > 0


class LogItemZeladoria(LogEvento):
    id_item = models.ForeignKey(ItemZeladoria, on_delete=models.CASCADE, db_column='id_item')
    id_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='id_admin')

    quant_anterior = models.PositiveIntegerField(null=True, blank=True)
    quant_nova = models.PositiveIntegerField(null=True, blank=True)

    class Evento(models.TextChoices):
        CRIADO = 'CRIADO', 'Criado'
        QUANT_ALTERADA = 'QUANTIDADE_ALTERADA', 'Quantidade total alterada'
        USO_ALTERADO = 'USO_ALTERADO', 'Quantidade em uso alterada'
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