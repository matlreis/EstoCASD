from django import forms
from django.utils import timezone

from core.utils import proximo_dia_util, somar_dias_uteis
from .models import ItemCASD, ItemZeladoria, Venda
from .services import ANTECEDENCIA_MAX_DIAS_UTEIS, PRAZO_MAX_DIAS_UTEIS


class ItemCASDForm(forms.ModelForm):
    class Meta:
        model = ItemCASD
        fields = ['nome', 'quant_total']

class ItemZeladoriaForm(forms.ModelForm):
    class Meta:
        model = ItemZeladoria
        fields = ['nome', 'quant_total', 'preco_unitario']
        help_texts = {
            'preco_unitario': 'Opcional. Preencha apenas para itens vendidos.'
        }

class EmprestimoForm(forms.Form):
    # Limitar as datas de retirada e de devolução do item
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate()
        ultima_retirada = somar_dias_uteis(hoje, ANTECEDENCIA_MAX_DIAS_UTEIS)
        self.fields['start_date'].initial = proximo_dia_util(hoje)
        self.fields['start_date'].widget.attrs.update({
            'min': hoje.isoformat(),
            'max': ultima_retirada.isoformat(),
        })
        self.fields['limit_date'].widget.attrs.update({
            'min': hoje.isoformat(),
            'max': somar_dias_uteis(ultima_retirada, PRAZO_MAX_DIAS_UTEIS).isoformat(),
            'data-prazo-dias-uteis': PRAZO_MAX_DIAS_UTEIS,
        })

    nome = forms.CharField(max_length=255)
    ap_vaga = forms.CharField(label='AP e vaga', max_length=50, help_text='Ex.: 105D Vaga A')
    email = forms.EmailField()
    quant = forms.IntegerField(min_value=1, initial=1)
    start_date = forms.DateField(  # vazio vale o próximo dia útil
        label='Retirada prevista',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    limit_date = forms.DateField(
        label='Devolução prevista',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

class DevolucaoForm(forms.Form):
    email = forms.EmailField()

class VendaForm(forms.ModelForm):
    quant = forms.IntegerField(label='Quantidade', min_value=1, initial=1)
    
    class Meta:
        model = Venda
        fields = ['nome_comprador', 'ap_vaga', 'quant', 'notas']
        help_texts = {
            'ap_vaga': 'Ex.: 105D Vaga A',
            'notas': 'Opcional. Observações da venda.'
        }
