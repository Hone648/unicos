from customers.models import Customer
from django.core.exceptions import ValidationError
from django.test import TestCase


def make_individual(**kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": "Jane",
        "last_name": "Smith",
    }
    defaults.update(kwargs)
    return Customer(**defaults)


def make_business(**kwargs):
    defaults = {"customer_type": Customer.CustomerType.BUSINESS, "business_name": "Quick Lube LLC"}
    defaults.update(kwargs)
    return Customer(**defaults)


class CustomerValidationTests(TestCase):
    def test_individual_with_first_and_last_name_is_valid(self):
        c = make_individual()
        c.full_clean()  # should not raise

    def test_individual_with_only_first_name_is_valid(self):
        c = make_individual(last_name="")
        c.full_clean()

    def test_individual_with_only_last_name_is_valid(self):
        c = make_individual(first_name="")
        c.full_clean()

    def test_individual_without_any_name_fails(self):
        c = make_individual(first_name="", last_name="")
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_business_with_business_name_is_valid(self):
        c = make_business()
        c.full_clean()

    def test_business_without_business_name_fails(self):
        c = make_business(business_name="")
        with self.assertRaises(ValidationError):
            c.full_clean()


class CustomerDisplayNameTests(TestCase):
    def test_individual_display_name_is_full_name(self):
        c = make_individual(first_name="Jane", last_name="Smith")
        self.assertEqual(c.display_name, "Jane Smith")

    def test_individual_display_name_with_only_first_name(self):
        c = make_individual(first_name="Jane", last_name="")
        self.assertEqual(c.display_name, "Jane")

    def test_business_display_name_is_business_name(self):
        c = make_business(business_name="Quick Lube LLC")
        self.assertEqual(c.display_name, "Quick Lube LLC")

    def test_str_matches_display_name(self):
        c = make_individual(first_name="Bob", last_name="Jones")
        self.assertEqual(str(c), c.display_name)
