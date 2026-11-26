from django.urls import path

from . import views

app_name = 'estoque'
urlpatterns = [
    path('', views.item_list, name='item_list'),
    path('itens/novo/', views.item_create, name='item_create'),
    path('itens/<int:pk>/', views.item_detail, name='item_detail'),
    path('itens/<int:pk>/editar/', views.item_update, name='item_update'),
    path('itens/<int:pk>/remover/', views.item_delete, name='item_delete'),
    path('itens/<int:pk>/emprestar/', views.emprestimo_create, name='emprestimo_create'),
    path('itens/<int:pk>/devolver/', views.devolucao_sinalizar, name='devolucao_sinalizar'),
    path('emprestimos/', views.emprestimo_list, name='emprestimo_list'),
    path('emprestimos/<int:pk>/confirmar/', views.devolucao_confirmar, name='devolucao_confirmar'),
    path('zeladoria/', views.zeladoria_list, name='zeladoria_list'),
    path('zeladoria/novo/', views.zeladoria_create, name='zeladoria_create'),
    path('zeladoria/vendas/', views.venda_list, name='venda_list'),
    path('zeladoria/<int:pk>/editar/', views.zeladoria_update, name='zeladoria_update'),
    path('zeladoria/<int:pk>/remover/', views.zeladoria_delete, name='zeladoria_delete'),
    path('zeladoria/<int:pk>/historico/', views.zeladoria_historico, name='zeladoria_historico'),
    path('zeladoria/<int:pk>/venda/', views.zeladoria_venda, name='zeladoria_venda'),
]
