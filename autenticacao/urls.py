from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'autenticacao'
urlpatterns = [
    path('login/', views.fazer_login, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('cadastro/', views.fazer_sign_up, name='cadastro')
]