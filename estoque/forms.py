from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import ItemCASD
from .services import PRAZO_MAX_DIAS


class ItemCASDForm(forms.ModelForm):
    class Meta:
        model = ItemCASD
        fields = ['nome', 'quant_total']

class EmprestimoForm(forms.Form):
    # Limitar a data limite de devolução do item
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate()
        self.fields['limit_date'].widget.attrs.update({
            'min': hoje.isoformat(),
            'max': (hoje + timedelta(days=PRAZO_MAX_DIAS)).isoformat(),
        })

    nome = forms.CharField(max_length=255)
    ap = forms.CharField(max_length=4)
    email = forms.EmailField()
    quant = forms.IntegerField(min_value=1, initial=1)
    limit_date = forms.DateField(
        label='Devolução prevista',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

class DevolucaoForm(forms.Form):
    email = forms.EmailField()
