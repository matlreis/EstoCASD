from estoque.models import Emprestimo


def emprestimos_atrasados():
    return (
        Emprestimo.objects.atrasados()
        .select_related('id_item', 'id_morador')
        .order_by('limit_date')
    )
