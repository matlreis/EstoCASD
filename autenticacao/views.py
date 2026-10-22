from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import SignUpForm, LoginForm
from .services import AutenticacaoService


def fazer_sign_up(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            AutenticacaoService.cadastrar(dados['nome'], dados['email'], 
                dados['senha'])
            messages.success(request, 'Administrador cadastrado.')
            return redirect('estoque:item_list')
    else:
        form = SignUpForm()

    context = { 'form': form }
    return render(request, 'autenticacao/signup.html', context)

@login_not_required
def fazer_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                admin = AutenticacaoService.autenticar(
                    form.cleaned_data['email'], form.cleaned_data['senha']
                )
            except ValidationError as e:
                form.add_error(None, e)
            else:
                login(request, admin)
                return redirect(_destino_pos_login(request))
    else:
        form = LoginForm()

    context = { 'form': form }
    return render(request, 'autenticacao/login.html', context)

def _destino_pos_login(request):
    destino = request.GET.get('next')
    # evita redirecionar para outro site
    if url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return destino
    return settings.LOGIN_REDIRECT_URL