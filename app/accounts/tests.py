from django.contrib.auth.models import Group
from django.test import TestCase


class DefaultGroupsTests(TestCase):
    def test_baseline_role_groups_exist(self):
        expected = {
            "Owner/Admin",
            "Manager",
            "Front Desk",
            "Estimator",
            "Technician",
            "Read-only",
        }
        actual = set(Group.objects.values_list("name", flat=True))
        self.assertTrue(
            expected.issubset(actual),
            msg=f"Missing baseline groups: {expected - actual}",
        )
