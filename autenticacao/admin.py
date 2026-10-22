from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Admin, LogAdmin


# os forms padrão do UserAdmin apontam para o User do Django (campo username)
class AdminCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = Admin
        fields = ('email', 'nome')


class AdminChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Admin
        fields = '__all__'


@admin.register(Admin)
class AdminAdmin(UserAdmin):
    form = AdminChangeForm
    add_form = AdminCreationForm

    list_display = ('nome', 'email', 'is_active', 'is_superuser', 'last_login')
    list_filter = ('is_active', 'is_superuser')
    search_fields = ('nome', 'email')
    ordering = ('nome',)
    filter_horizontal = ()

    readonly_fields = ('last_login', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Dados pessoais', {'fields': ('nome',)}),
        ('Permissões', {'fields': ('is_active', 'is_superuser')}),
        ('Datas', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nome', 'usable_password', 'password1', 'password2'),
        }),
    )

    # o painel exige is_staff
    def save_model(self, request, obj, form, change):
        obj.is_staff = obj.is_superuser
        super().save_model(request, obj, form, change)

    # desativar (is_active=False) em vez de deletar admin
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogAdmin)
class LogAdminAdmin(admin.ModelAdmin):
    list_display = ('event_date', 'event_type', 'id_admin', 'ip_aparelho')
    list_filter = ('event_type',)
    search_fields = ('id_admin__nome', 'id_admin__email', 'ip_aparelho')
    date_hierarchy = 'event_date'
    list_select_related = ('id_admin',)

    # somente leitura dos logs
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
