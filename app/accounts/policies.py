from django.core.exceptions import PermissionDenied

from .authorization import (
    PERM_BILLING_MANAGE,
    PERM_BILLING_RECORD_PAYMENT,
    PERM_BILLING_VIEW,
    PERM_REPAIR_ORDERS_CHANGE_STATUS,
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_OWNER_ADMIN,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
    user_has_app_permission,
    user_role_names,
)


def require_policy(policy_result):
    if not policy_result:
        raise PermissionDenied


def _is_active_user(user):
    return bool(getattr(user, "is_authenticated", False) and user.is_active)


def _is_superuser(user):
    return bool(_is_active_user(user) and user.is_superuser)


def _role_names(user):
    return user_role_names(user)


def is_owner_admin_or_manager(user):
    if _is_superuser(user):
        return True
    roles = _role_names(user)
    return ROLE_OWNER_ADMIN in roles or ROLE_MANAGER in roles


def is_technician(user):
    return ROLE_TECHNICIAN in _role_names(user)


def is_read_only(user):
    return ROLE_READ_ONLY in _role_names(user)


def _has_broad_repair_order_role(user):
    if _is_superuser(user):
        return True
    roles = _role_names(user)
    return bool(
        {
            ROLE_OWNER_ADMIN,
            ROLE_MANAGER,
            ROLE_FRONT_DESK,
            ROLE_ESTIMATOR,
            ROLE_READ_ONLY,
        }
        & roles
    )


def _is_technician_only(user):
    return is_technician(user) and not _has_broad_repair_order_role(user)


def is_assigned_technician(user, repair_order):
    return bool(
        _is_active_user(user) and is_technician(user) and repair_order.assigned_to_id == user.id
    )


def can_access_assigned_repair_order(user, repair_order):
    return is_assigned_technician(user, repair_order)


def can_view_repair_order(user, repair_order):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_REPAIR_ORDERS_VIEW):
        return False
    if _is_technician_only(user):
        return is_assigned_technician(user, repair_order)
    return True


def can_edit_repair_order(user, repair_order):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE):
        return False
    if _is_technician_only(user):
        return False
    return can_view_repair_order(user, repair_order)


def can_change_repair_order_status(user, repair_order):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_REPAIR_ORDERS_CHANGE_STATUS):
        return False
    if _is_technician_only(user):
        return False
    return can_view_repair_order(user, repair_order)


def filter_repair_orders_for_user(user, queryset):
    if _is_superuser(user):
        return queryset
    if not user_has_app_permission(user, PERM_REPAIR_ORDERS_VIEW):
        return queryset.none()
    if _is_technician_only(user):
        return queryset.filter(assigned_to=user)
    return queryset


def can_view_estimate(user, estimate):
    return can_view_repair_order(user, estimate.repair_order)


def can_manage_estimate(user, estimate):
    # Estimates currently reuse repair-order manage permission; there is no
    # separate estimates.manage permission yet.
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE):
        return False
    return can_view_repair_order(user, estimate.repair_order)


def can_manage_estimate_for_repair_order(user, repair_order):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE):
        return False
    return can_view_repair_order(user, repair_order)


def can_convert_estimate_to_invoice(user, estimate):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_BILLING_MANAGE):
        return False
    return can_view_repair_order(user, estimate.repair_order)


def can_view_invoice(user, invoice):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_BILLING_VIEW):
        return False
    return can_view_repair_order(user, invoice.repair_order)


def can_view_invoice_for_repair_order(user, repair_order):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_BILLING_VIEW):
        return False
    return can_view_repair_order(user, repair_order)


def can_manage_invoice(user, invoice):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_BILLING_MANAGE):
        return False
    return can_view_repair_order(user, invoice.repair_order)


def can_manage_invoice_for_repair_order(user, repair_order):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_BILLING_MANAGE):
        return False
    return can_view_repair_order(user, repair_order)


def can_record_payment(user, invoice):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_BILLING_RECORD_PAYMENT):
        return False
    return can_view_repair_order(user, invoice.repair_order)


def can_manage_invoice_line_items(user, invoice):
    return can_manage_invoice(user, invoice)


def can_view_attachment(user, attachment):
    return can_view_repair_order(user, attachment.repair_order)


def can_upload_attachment_for_repair_order(user, repair_order):
    if _is_superuser(user):
        return True
    if not user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE):
        return False
    return can_view_repair_order(user, repair_order)


def can_delete_attachment(user, attachment):
    # Deleting evidence/photos/documents is restricted to Owner/Admin and Manager.
    # Front Desk can upload but not delete, since removal of records is more sensitive.
    if _is_superuser(user):
        return True
    return is_owner_admin_or_manager(user)
