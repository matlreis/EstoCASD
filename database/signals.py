from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import LogAdmin, LogEmprestimo, Emprestimo

@receiver(user_logged_in)
def log_admin_login(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    LogAdmin.objects.create(id_admin=user, ip_aparelho=ip, event_type="LOGIN")

@receiver(user_logged_out)
def log_admin_logout(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    LogAdmin.objects.create(id_admin=user, ip_aparelho=ip, event_type="LOGOUT")