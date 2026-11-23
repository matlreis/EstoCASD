from django.shortcuts import render
from .services import DashboardZeladoriaService, DashboardEmprestimoService
import json

def dashboard_view(request):
    vendas = DashboardZeladoriaService.listar_vendas()[:10]
    atrasos = DashboardEmprestimoService.listar_devolvidos_atrasos()[:10]

    itens_vendidos = [venda['id_item__nome'] for venda in vendas]
    valores_totais = [venda['total_vendido'] for venda in vendas]

    itens_atrasados = [atraso['id_item__nome'] for atraso in atrasos]
    atrasos_totais = [atraso['total_atrasos'] for atraso in atrasos]

    contexto = {
        'itens_vendidos_json': json.dumps(itens_vendidos),
        'valores_totais_json': json.dumps(valores_totais),
        'itens_atrasados_json': json.dumps(itens_atrasados),
        'atrasos_totais_json': json.dumps(atrasos_totais)
    }
    return render(request, 'dashboard/dashboard.html', contexto)

