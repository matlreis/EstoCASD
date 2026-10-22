from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Admin, LogAdmin
from .middleware import get_request_atual

@receiver(post_save, sender=Admin)
def log_admin_criado(sender, instance, created, raw, **kwargs):
    if created and not raw:
        request = get_request_atual()
        ip = request.META.get('REMOTE_ADDR') if request else None
        LogAdmin.objects.create(id_admin=instance, ip_aparelho=ip, event_type='CONTA_CRIADA')

@receiver(user_logged_in)
def log_admin_login(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    LogAdmin.objects.create(id_admin=user, ip_aparelho=ip, event_type="LOGIN")

@receiver(user_logged_out)
def log_admin_logout(sender, request, user, **kwargs):
    # logout sem sessão ativa
    if user is None:
        return
    ip = request.META.get('REMOTE_ADDR')
    LogAdmin.objects.create(id_admin=user, ip_aparelho=ip, event_type="LOGOUT")