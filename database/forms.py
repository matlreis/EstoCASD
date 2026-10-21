from django import forms
from .models import Item

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['nome', 'tipo_estoque', 'quant_total']

class EmprestimoForm(forms.Form):
    nome = forms.CharField(max_length=255)
    ap = forms.CharField(max_length=4)
    email = forms.EmailField()
    quant = forms.IntegerField(min_value=1, initial=1)
    limit_date = forms.DateTimeField(
        label='Devolução prevista',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )