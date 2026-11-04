from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from .models import ItemCASD
from .forms import ItemCASDForm
from .services import EstoqueService


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
    return redirect('estoque:item_list')
