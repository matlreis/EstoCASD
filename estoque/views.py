from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST

from core.utils import get_client_ip
from .models import ItemCASD, Emprestimo, ItemZeladoria
from .forms import ItemCASDForm, EmprestimoForm, DevolucaoForm, ItemZeladoriaForm
from .services import EstoqueService, EmprestimoService, ZeladoriaService


@login_not_required
def item_list(request):
    itens = EstoqueService.list_items()
    context = {'itens': itens}
    return render(request, 'estoque/item_list.html', context)

def item_create(request):
    if request.method == "POST":
        item_form = ItemCASDForm(request.POST)
        if item_form.is_valid():
            EstoqueService.create_item(item_form.cleaned_data)
            messages.success(request, 'Item cadastrado.')
            return redirect('estoque:item_list')

    else:
        item_form = ItemCASDForm()

    context = {'form': item_form}
    return render(request, 'estoque/item_form.html', context)

def item_update(request, pk):
    item = get_object_or_404(ItemCASD, pk=pk, is_active=True)

    if request.method == "POST":
        item_form = ItemCASDForm(request.POST, instance=item)
        if item_form.is_valid():
            try:
                EstoqueService.update_item(item, item_form.cleaned_data)
            except ValidationError as e:
                item_form.add_error(None, e)
            else:
                messages.success(request, 'Item atualizado.')
                return redirect('estoque:item_list')

    else:
        item_form = ItemCASDForm(instance=item)

    context = {'form': item_form, 'item': item}
    return render(request, 'estoque/item_form.html', context)

@require_POST
def item_delete(request, pk):
    item = get_object_or_404(ItemCASD, pk=pk, is_active=True)
    try:
        EstoqueService.delete_item(item)
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        messages.success(request, 'Item removido.')
    return redirect('estoque:item_list')

@login_not_required
def emprestimo_create(request, pk):
    item = get_object_or_404(ItemCASD, pk=pk, is_active=True)

    if request.method == 'POST':
        form = EmprestimoForm(request.POST)
        if form.is_valid():
            try:
                ip = get_client_ip(request)
                EmprestimoService.criar_emprestimo(item, form.cleaned_data, ip)
            except ValidationError as e:
                form.add_error(None, e)
            else:
                messages.success(request, "Empréstimo registrado.")
                return redirect('estoque:item_list')

    else:
        form = EmprestimoForm()

    context = {'form': form, 'item': item}
    return render(request, 'estoque/emprestimo_form.html', context)

@login_not_required
def devolucao_sinalizar(request, pk):
    item = get_object_or_404(ItemCASD, pk=pk, is_active=True)

    if request.method == 'POST':
        form = DevolucaoForm(request.POST)
        if form.is_valid():
            try:
                email = form.cleaned_data['email']
                ip = get_client_ip(request)
                EmprestimoService.sinalizar_devolucao(item, email, ip)
            except ValidationError as e:
                form.add_error(None, e)
            else:
                messages.success(request, "Devolução sinalizada.")
                return redirect('estoque:item_list')

    else:
        form = DevolucaoForm()

    context = {'form': form, 'item': item}
    return render(request, 'estoque/devolucao_form.html', context)

def emprestimo_list(request):
    emprestimos = EmprestimoService.listar_ativos()
    context = {'emprestimos': emprestimos}
    return render(request, 'estoque/emprestimo_list.html', context)

@require_POST
def devolucao_confirmar(request, pk):
    emprestimo = get_object_or_404(Emprestimo, pk=pk)
    try:
        ip = get_client_ip(request)
        # o LoginRequiredMiddleware garante que há um admin logado
        EmprestimoService.confirmar_devolucao(emprestimo, request.user, ip)
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        messages.success(request, 'Devolução confirmada.')
    return redirect('estoque:emprestimo_list')

def zeladoria_list(request):
    itens = ZeladoriaService.list_items()
    context = {'itens': itens}
    return render(request, 'estoque/zeladoria_list.html', context)

def zeladoria_create(request):
    if request.method == 'POST':
        form = ItemZeladoriaForm(request.POST)
        if form.is_valid():
            ip = get_client_ip(request)
            ZeladoriaService.create_item(form.cleaned_data, request.user, ip)
            messages.success(request, 'Item cadastrado.')
            return redirect('estoque:zeladoria_list')

    else:
        form = ItemZeladoriaForm()

    context = {'form': form}
    return render(request, 'estoque/zeladoria_form.html', context)

def zeladoria_update(request, pk):
    item = get_object_or_404(ItemZeladoria, pk=pk, is_active=True)

    if request.method == 'POST':
        form = ItemZeladoriaForm(request.POST, instance=item)
        if form.is_valid():
            try:
                ip = get_client_ip(request)
                ZeladoriaService.update_item(item, form.cleaned_data, request.user, ip)
            except ValidationError as e:
                form.add_error(None, e)
            else:
                messages.success(request, 'Item atualizado.')
                return redirect('estoque:zeladoria_list')

    else:
        form = ItemZeladoriaForm(instance=item)

    context = {'form': form, 'item': item}
    return render(request, 'estoque/zeladoria_form.html', context)

@require_POST
def zeladoria_delete(request, pk):
    item = get_object_or_404(ItemZeladoria, pk=pk, is_active=True)
    ip = get_client_ip(request)
    ZeladoriaService.delete_item(item, request.user, ip)
    messages.success(request, 'Item removido.')
    return redirect('estoque:zeladoria_list')
