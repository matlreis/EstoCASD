from django import forms
from .models import Item

class CreateItem(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['nome', 'tipo_estoque', 'quant_total']

class UpdateItem(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['nome', 'tipo_estoque', 'quant_total']