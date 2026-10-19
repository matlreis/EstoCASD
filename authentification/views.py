from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import SignUpForm, LoginForm
from database.models import LogAdmin

def fazer_sign_up(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():

            senha = form.cleaned_data['senha']

            novo_admin = form.save(commit=False)
            novo_admin.set_password(senha)

            novo_admin.save()

            ip = request.META.get('REMOTE_ADDR')
            LogAdmin.objects.create(id_admin = novo_admin, ip_aparelho=ip, event_type='CONTA_CRIADA')

            return redirect('')
    
    else:
        form = SignUpForm()


    contexto = {
        'form': form,
    }
    return render(request, 'signup.html', contexto)

def fazer_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            senha = form.cleaned_data['senha']

            usuario = authenticate(request, email=email, password=senha)

            if usuario is not None:
                login(request, usuario)
                return redirect('')
            else:
                form.add_error(None, "Email ou senha incorretos")

    else:
        form = LoginForm()

    contexto = {
        'form': form,
    }
    return render(request, 'login.html', contexto)