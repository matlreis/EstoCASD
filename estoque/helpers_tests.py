from datetime import date, timedelta
from unittest import mock

from autenticacao.models import Admin
from .models import Emprestimo


# "Hoje" fixo, para os testes não dependerem do dia em que rodam. Uma quinta-feira
# foi escolhida porque o último dia do prazo máximo (5 dias úteis) cai em outra quinta,
# e o dia seguinte é uma sexta, então os testes do prazo máximo não esbarram na regra
# do fim de semana.
HOJE = date(2026, 11, 5)  # quinta-feira
PRAZO_LIMITE = HOJE + timedelta(days=7)  # quinta-feira, 5º dia útil depois de HOJE
SABADO = HOJE + timedelta(days=2)
DOMINGO = HOJE + timedelta(days=3)
SEGUNDA = HOJE + timedelta(days=4)
FIXAR_HOJE = mock.patch('django.utils.timezone.localdate', new=lambda: HOJE)


AT = Emprestimo.StatusEmprestimo.AT
DS = Emprestimo.StatusEmprestimo.DS
DE = Emprestimo.StatusEmprestimo.DE


def criar_emprestimo(item, morador, status=AT, quant=1, limit_date=HOJE, start_date=HOJE):
    # cria direto no banco: quem chama ajusta quant_emprestada do item
    return Emprestimo.objects.create(id_item=item, id_morador=morador, status=status,
                                     quant=quant, start_date=start_date, limit_date=limit_date)


def criar_admin(email='admin@test.com', nome='Alice'):
    # sem senha: os testes usam force_login, que não precisa dela
    return Admin.objects.create_user(email=email, nome=nome)


def status_atual(emprestimo):
    emprestimo.refresh_from_db()
    return emprestimo.status