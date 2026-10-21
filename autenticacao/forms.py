from django import forms
from django.contrib.auth import get_user_model

class SignUpForm(forms.ModelForm):
    senha = forms.CharField(widget=forms.PasswordInput, label="Senha")
    confirmar_senha = forms.CharField(widget=forms.PasswordInput, label="Confirmar Senha")

    class Meta:
        model = get_user_model()
        fields = ['nome', 'email']

    def clean(self):
        cleaned_data = super().clean()
        senha = cleaned_data.get("senha")
        confirmar_senha = cleaned_data.get("confirmar_senha")

        if senha and confirmar_senha and senha != confirmar_senha:
            self.add_error('confirmar_senha', "As senhas não coincidem.")

        return cleaned_data

class LoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    senha = forms.CharField(widget=forms.PasswordInput, label="Senha")
