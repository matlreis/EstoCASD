from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from .models import Item
from .forms import ItemForm
from .services import EstoqueService


def item_list(request):
    itens = EstoqueService.list_items()
    context = {'itens': itens}
    return render(request, 'estoque/item_list.html', context)

def item_create(request):
    if request.method == "POST":
        item_form = ItemForm(request.POST)
        if item_form.is_valid():
            EstoqueService.create_item(item_form.cleaned_data)
            messages.success(request, 'Item cadastrado.')
            return redirect('estoque:item_list')

    else:
        item_form = ItemForm()

    context = {'form': item_form}
    return render(request, 'estoque/item_form.html', context)

def item_update(request, pk):
    item = get_object_or_404(Item, pk=pk, is_active=True)

    if request.method == "POST":
        item_form = ItemForm(request.POST, instance=item)
        if item_form.is_valid():
            try:
                EstoqueService.update_item(item, item_form.cleaned_data)
            except ValidationError as e:
                item_form.add_error(None, e)
            else:
                messages.success(request, 'Item atualizado.')
                return redirect('estoque:item_list')

    else:
        item_form = ItemForm(instance=item)

    context = {'form': item_form, 'item': item}
    return render(request, 'estoque/item_form.html', context)

@require_POST
def item_delete(request, pk):
    item = get_object_or_404(Item, pk=pk, is_active=True)
    try:
        EstoqueService.delete_item(item)
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        messages.success(request, 'Item removido.')
    return redirect('estoque:item_list')

def emprestimo_create(request, pk):
    return redirect('estoque:item_list')
