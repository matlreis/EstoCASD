from django.urls import path

from . import views

app_name = 'estoque'
urlpatterns = [
    path('', views.item_list, name='item_list'),
    path('itens/novo/', views.item_create, name='item_create'),
    path('itens/<int:pk>/editar/', views.item_update, name='item_update'),
    path('itens/<int:pk>/remover/', views.item_delete, name='item_delete'),
    path('itens/<int:pk>/emprestar/', views.emprestimo_create, name='emprestimo_create'),
]