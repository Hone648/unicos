from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ROLE_OWNER_ADMIN = "Owner/Admin"
ROLE_MANAGER = "Manager"
ROLE_FRONT_DESK = "Front Desk"
ROLE_ESTIMATOR = "Estimator"
ROLE_TECHNICIAN = "Technician"
ROLE_READ_ONLY = "Read-only"

PERM_DASHBOARD_VIEW = "dashboard.view"
PERM_REPORTS_VIEW = "reports.view"

PERM_CUSTOMERS_VIEW = "customers.view"
PERM_CUSTOMERS_MANAGE = "customers.manage"

PERM_REPAIR_ORDERS_VIEW = "repair_orders.view"
PERM_REPAIR_ORDERS_MANAGE = "repair_orders.manage"
PERM_REPAIR_ORDERS_CHANGE_STATUS = "repair_orders.change_status"

PERM_BILLING_VIEW = "billing.view"
PERM_BILLING_MANAGE = "billing.manage"
PERM_BILLING_RECORD_PAYMENT = "billing.record_payment"

ALL_APP_PERMISSIONS = frozenset(
    {
        PERM_DASHBOARD_VIEW,
        PERM_REPORTS_VIEW,
        PERM_CUSTOMERS_VIEW,
        PERM_CUSTOMERS_MANAGE,
        PERM_REPAIR_ORDERS_VIEW,
        PERM_REPAIR_ORDERS_MANAGE,
        PERM_REPAIR_ORDERS_CHANGE_STATUS,
        PERM_BILLING_VIEW,
        PERM_BILLING_MANAGE,
        PERM_BILLING_RECORD_PAYMENT,
    }
)

ROLE_PERMISSION_MATRIX = {
    ROLE_OWNER_ADMIN: ALL_APP_PERMISSIONS,
    ROLE_MANAGER: ALL_APP_PERMISSIONS,
    ROLE_FRONT_DESK: frozenset(
        {
            PERM_DASHBOARD_VIEW,
            PERM_CUSTOMERS_VIEW,
            PERM_CUSTOMERS_MANAGE,
            PERM_REPAIR_ORDERS_VIEW,
            PERM_REPAIR_ORDERS_MANAGE,
            PERM_BILLING_VIEW,
            PERM_BILLING_RECORD_PAYMENT,
        }
    ),
    ROLE_ESTIMATOR: frozenset(
        {
            PERM_DASHBOARD_VIEW,
            PERM_CUSTOMERS_VIEW,
            PERM_REPAIR_ORDERS_VIEW,
            PERM_REPAIR_ORDERS_CHANGE_STATUS,
            PERM_BILLING_VIEW,
        }
    ),
    ROLE_TECHNICIAN: frozenset(
        {
            PERM_DASHBOARD_VIEW,
            PERM_REPAIR_ORDERS_VIEW,
        }
    ),
    ROLE_READ_ONLY: frozenset(
        {
            PERM_DASHBOARD_VIEW,
            PERM_REPORTS_VIEW,
            PERM_CUSTOMERS_VIEW,
            PERM_REPAIR_ORDERS_VIEW,
            PERM_BILLING_VIEW,
        }
    ),
}


def user_role_names(user):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return set()
    return set(user.groups.values_list("name", flat=True))


def user_app_permissions(user):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return set()
    if user.is_superuser:
        return set(ALL_APP_PERMISSIONS)

    role_names = user_role_names(user)
    if ROLE_OWNER_ADMIN in role_names:
        return set(ALL_APP_PERMISSIONS)

    permissions = set()
    for role_name in role_names:
        permissions.update(ROLE_PERMISSION_MATRIX.get(role_name, frozenset()))
    return permissions


def user_has_app_permission(user, permission):
    return permission in user_app_permissions(user)


def app_permission_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not user_has_app_permission(request.user, permission):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
