from django import template

from accounts.authorization import user_has_app_permission

register = template.Library()


@register.filter
def has_app_permission(user, permission):
    return user_has_app_permission(user, permission)
