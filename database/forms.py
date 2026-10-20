from django import forms
from .models import Item, Morador

class CreateItem(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['nome', 'tipo_estoque', 'quant_total']

class UpdateItem(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['nome', 'tipo_estoque', 'quant_total']

class CreateMorador(forms.ModelForm):
    class Meta:
        model = Morador
        fields = ['nome', 'ap', 'email']