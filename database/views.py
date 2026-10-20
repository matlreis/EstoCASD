from django.shortcuts import render, redirect
from .models import Item, Admin, LogAdmin
from .forms import CreateItem, UpdateItem, CreateMorador

def gerenciar_estoque(request):
    if request.method == 'POST':
        acao = request.POST.get('acao')

        if acao == 'criar':  
            create_form = CreateItem(request.POST)
            if create_form.is_valid():
                create_form.save()

        else:
            id = request.POST.get('item_id')
            if acao == 'atualizar':
                item = Item.objects.get(id=id)
                item.nome = request.POST.get('nome')
                item.tipo_estoque = request.POST.get('tipo_estoque')
                item.quant_total = request.POST.get('quant_total')
                item.save()

                
                #update_form = UpdateItem(request.POST)
                #update_form.save()

            elif acao == 'deletar':
                Item.objects.filter(id=id).delete()
            
            elif acao == 'emprestar':
                return redirect('emprestimo')

        return redirect('')
    
    else:
        create_form = CreateItem()

    itens = Item.objects.all()
    usuarios = Admin.objects.all()
    log_admin = LogAdmin.objects.all()

    contexto = {
        'create_form': create_form,
        'itens': itens,
        'usuarios': usuarios,
        'log_admin': log_admin
    }
    return render(request, 'estoque.html', contexto)

def pegar_emprestimo(request):
    if request.method == 'POST':
        morador_form = CreateMorador(request.POST)
        if morador_form.is_valid():
            morador_form.save()

        redirect('emprestimo')

    else:
        morador_form = CreateMorador()

    contexto = {
        'morador_form': morador_form
    }
    return render(request, 'emprestimo.html', contexto)