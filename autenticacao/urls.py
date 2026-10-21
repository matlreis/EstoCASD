from django.urls import path

from . import views

app_name = 'autenticacao'
urlpatterns = [
    path('login/', views.fazer_login, name='login'),
    path('cadastro/', views.fazer_sign_up, name='cadastro')
]