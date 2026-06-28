from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from customers.models import Customer
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def make_customer(**kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": "Test",
        "last_name": "User",
    }
    defaults.update(kwargs)
    c = Customer(**defaults)
    c.save()
    return c


def make_vehicle(customer, **kwargs):
    defaults = {
        "vin": VALID_VIN,
        "year": 2021,
        "make": "Honda",
        "model": "Civic",
    }
    defaults.update(kwargs)
    return Vehicle(customer=customer, **defaults)


class VehicleRelationshipTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_vehicle_belongs_to_customer(self):
        v = make_vehicle(self.customer)
        v.save()
        self.assertEqual(v.customer, self.customer)

    def test_customer_can_have_multiple_vehicles(self):
        make_vehicle(self.customer, vin="1HGBH41JXMN109186").save()
        make_vehicle(self.customer, vin="2T1BURHE0JC043821").save()
        self.assertEqual(self.customer.vehicles.count(), 2)


class VehicleVinTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_vin_normalized_to_uppercase_on_save(self):
        v = make_vehicle(self.customer, vin="1hgbh41jxmn109186")
        v.save()
        self.assertEqual(v.vin, "1HGBH41JXMN109186")

    def test_vin_whitespace_stripped_on_save(self):
        v = make_vehicle(self.customer, vin="  1HGBH41JXMN109186  ")
        v.save()
        self.assertEqual(v.vin, "1HGBH41JXMN109186")

    def test_invalid_vin_too_short_fails(self):
        v = make_vehicle(self.customer, vin="TOOSHORT")
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_invalid_vin_with_forbidden_char_I_fails(self):
        v = make_vehicle(self.customer, vin="1HGBH41JXMN10918I")
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_invalid_vin_with_forbidden_char_O_fails(self):
        v = make_vehicle(self.customer, vin="1HGBH41JXMN10918O")
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_invalid_vin_with_forbidden_char_Q_fails(self):
        v = make_vehicle(self.customer, vin="1HGBH41JXMN10918Q")
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_full_clean_normalizes_lowercase_vin(self):
        v = make_vehicle(self.customer, vin="1hgbh41jxmn109186")
        v.full_clean()
        self.assertEqual(v.vin, "1HGBH41JXMN109186")

    def test_full_clean_strips_vin_whitespace(self):
        v = make_vehicle(self.customer, vin="  1HGBH41JXMN109186  ")
        v.full_clean()
        self.assertEqual(v.vin, "1HGBH41JXMN109186")

    def test_duplicate_vin_fails(self):
        make_vehicle(self.customer, vin=VALID_VIN).save()
        with self.assertRaises(IntegrityError):
            make_vehicle(self.customer, vin=VALID_VIN).save()


class VehicleRequiredFieldTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_make_is_required(self):
        v = make_vehicle(self.customer, make="")
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_model_is_required(self):
        v = make_vehicle(self.customer, model="")
        with self.assertRaises(ValidationError):
            v.full_clean()


class VehicleStrTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_str_includes_year_make_model_and_vin(self):
        v = make_vehicle(self.customer, year=2021, make="Honda", model="Civic")
        v.save()
        s = str(v)
        self.assertIn("2021", s)
        self.assertIn("Honda", s)
        self.assertIn("Civic", s)
        self.assertIn(VALID_VIN, s)

    def test_str_without_year_still_useful(self):
        v = make_vehicle(self.customer, year=None)
        v.save()
        s = str(v)
        self.assertIn("Honda", s)
        self.assertIn(VALID_VIN, s)


class CustomerProtectionTests(TestCase):
    def test_customer_deletion_blocked_when_vehicles_exist(self):
        customer = make_customer()
        make_vehicle(customer).save()
        with self.assertRaises(ProtectedError):
            customer.delete()
