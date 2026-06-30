from accounts.authorization import (
    ALL_APP_PERMISSIONS,
    PERM_BILLING_MANAGE,
    PERM_BILLING_RECORD_PAYMENT,
    PERM_BILLING_VIEW,
    PERM_CUSTOMERS_MANAGE,
    PERM_CUSTOMERS_VIEW,
    PERM_DASHBOARD_VIEW,
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
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.test import TestCase


def make_user(username="auth-user", **kwargs):
    return get_user_model().objects.create_user(
        username=username,
        password="pw-test-12345",
        **kwargs,
    )


def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


class AuthorizationHelperTests(TestCase):
    def test_anonymous_user_has_no_app_permissions(self):
        user = AnonymousUser()

        self.assertEqual(user_role_names(user), set())
        self.assertFalse(user_has_app_permission(user, PERM_DASHBOARD_VIEW))

    def test_inactive_user_has_no_app_permissions(self):
        user = assign_role(make_user(is_active=False), ROLE_MANAGER)

        self.assertEqual(user_role_names(user), set())
        self.assertFalse(user_has_app_permission(user, PERM_DASHBOARD_VIEW))

    def test_user_with_no_role_group_has_no_app_permissions(self):
        user = make_user()

        self.assertEqual(user_role_names(user), set())
        self.assertFalse(user_has_app_permission(user, PERM_DASHBOARD_VIEW))

    def test_superuser_has_all_app_permissions(self):
        user = get_user_model().objects.create_superuser(
            username="super",
            password="pw-test-12345",
        )

        for permission in ALL_APP_PERMISSIONS:
            with self.subTest(permission=permission):
                self.assertTrue(user_has_app_permission(user, permission))

    def test_owner_admin_has_all_app_permissions(self):
        user = assign_role(make_user(), ROLE_OWNER_ADMIN)

        for permission in ALL_APP_PERMISSIONS:
            with self.subTest(permission=permission):
                self.assertTrue(user_has_app_permission(user, permission))

    def test_manager_has_operational_permissions(self):
        user = assign_role(make_user(), ROLE_MANAGER)

        for permission in ALL_APP_PERMISSIONS:
            with self.subTest(permission=permission):
                self.assertTrue(user_has_app_permission(user, permission))

    def test_front_desk_can_intake_and_record_payments_but_not_manage_billing(self):
        user = assign_role(make_user(), ROLE_FRONT_DESK)

        self.assertTrue(user_has_app_permission(user, PERM_CUSTOMERS_MANAGE))
        self.assertTrue(user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE))
        self.assertTrue(user_has_app_permission(user, PERM_BILLING_RECORD_PAYMENT))
        self.assertFalse(user_has_app_permission(user, PERM_BILLING_MANAGE))
        self.assertFalse(user_has_app_permission(user, PERM_REPAIR_ORDERS_CHANGE_STATUS))

    def test_estimator_can_view_and_change_repair_order_status(self):
        user = assign_role(make_user(), ROLE_ESTIMATOR)

        self.assertTrue(user_has_app_permission(user, PERM_CUSTOMERS_VIEW))
        self.assertTrue(user_has_app_permission(user, PERM_REPAIR_ORDERS_VIEW))
        self.assertTrue(user_has_app_permission(user, PERM_REPAIR_ORDERS_CHANGE_STATUS))
        self.assertTrue(user_has_app_permission(user, PERM_BILLING_VIEW))
        self.assertFalse(user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE))
        self.assertFalse(user_has_app_permission(user, PERM_BILLING_MANAGE))

    def test_technician_can_view_repair_orders_but_cannot_mutate(self):
        user = assign_role(make_user(), ROLE_TECHNICIAN)

        self.assertTrue(user_has_app_permission(user, PERM_DASHBOARD_VIEW))
        self.assertTrue(user_has_app_permission(user, PERM_REPAIR_ORDERS_VIEW))
        self.assertFalse(user_has_app_permission(user, PERM_CUSTOMERS_VIEW))
        self.assertFalse(user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE))
        self.assertFalse(user_has_app_permission(user, PERM_REPAIR_ORDERS_CHANGE_STATUS))

    def test_read_only_can_view_but_cannot_mutate(self):
        user = assign_role(make_user(), ROLE_READ_ONLY)

        self.assertTrue(user_has_app_permission(user, PERM_DASHBOARD_VIEW))
        self.assertTrue(user_has_app_permission(user, PERM_CUSTOMERS_VIEW))
        self.assertTrue(user_has_app_permission(user, PERM_REPAIR_ORDERS_VIEW))
        self.assertTrue(user_has_app_permission(user, PERM_BILLING_VIEW))
        self.assertFalse(user_has_app_permission(user, PERM_CUSTOMERS_MANAGE))
        self.assertFalse(user_has_app_permission(user, PERM_REPAIR_ORDERS_MANAGE))
        self.assertFalse(user_has_app_permission(user, PERM_BILLING_MANAGE))
        self.assertFalse(user_has_app_permission(user, PERM_BILLING_RECORD_PAYMENT))
