from django import forms
from .models import ItemCASD

class ItemCASDForm(forms.ModelForm):
    class Meta:
        model = ItemCASD
        fields = ['nome', 'quant_total']

class EmprestimoForm(forms.Form):
    nome = forms.CharField(max_length=255)
    ap = forms.CharField(max_length=4)
    email = forms.EmailField()
    quant = forms.IntegerField(min_value=1, initial=1)
    limit_date = forms.DateField(
        label='Devolução prevista',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
