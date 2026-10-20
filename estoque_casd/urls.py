"""
URL configuration for estoque_casd project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from database.views import gerenciar_estoque, pegar_emprestimo
from authentification.views import fazer_login, fazer_sign_up

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', gerenciar_estoque, name=''),
    path('login/', fazer_login, name='login'),
    path('cadastro/', fazer_sign_up, name='cadastro'),
    path('emprestimo/', pegar_emprestimo, name='emprestimo')
]
