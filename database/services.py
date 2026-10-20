from django.utils import timezone
from .models import Emprestimo, Uso

_RELATED = {
    Emprestimo: ('id_item', 'id_morador'),
    Uso: ('id_item', 'id_admin')
}

def _atrasados(model):
    return (
        model.objects
        .filter(is_active=True, limit_date__lt=timezone.now())
        .select_related(*_RELATED[model])
        .order_by('limit_date')
    )

def emprestimos_atrasados():
    return _atrasados(Emprestimo)

def usos_atrasados():
    return _atrasados(Uso)