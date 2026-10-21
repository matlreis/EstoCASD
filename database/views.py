from django.shortcuts import get_object_or_404, render, redirect
from .models import Item
from .forms import ItemForm


def item_list(request):
    itens = Item.objects.all().filter(is_active=True)
    context = {'itens': itens}
    return render(request, 'estoque/item_list.html', context)

def item_create(request):
    if request.method == "POST":
        item_form = ItemForm(request.POST)
        if item_form.is_valid():
            item_form.save()
            return redirect('estoque:item_list')

    else:
        item_form = ItemForm()

    context = {'form': item_form}
    return render(request, 'estoque/item_form.html', context)

def item_update(request, pk):
    return redirect('estoque:item_list')

def item_delete(request, pk):
    return redirect('estoque:item_list')

def emprestimo_create(request, pk):
    return redirect('estoque:item_list')