from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError


class SignUpForm(forms.ModelForm):
    senha = forms.CharField(
        widget=forms.PasswordInput, 
        label="Senha",
        help_text=password_validation.password_validators_help_text_html(),
    )
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
        elif senha:
            admin = self._meta.model(nome=cleaned_data.get('nome'), 
                                     email=cleaned_data.get('email'))
            try:
                password_validation.validate_password(senha, user=admin)
            except ValidationError as e:
                self.add_error('senha', e)

        return cleaned_data

class LoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    senha = forms.CharField(widget=forms.PasswordInput, label="Senha")
