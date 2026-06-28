from django.contrib import admin
from django.test import TestCase

from customers.models import Customer
from repair_orders.models import RepairOrder
from vehicles.admin import VehicleAdmin
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def make_customer(**kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": "Test",
        "last_name": "Customer",
    }
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_vehicle(customer, vin=VALID_VIN, **kwargs):
    return Vehicle.objects.create(
        customer=customer, vin=vin, make="Honda", model="Civic", year=2021, **kwargs
    )


def make_repair_order(customer, vehicle, number="RO-0001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


class VehicleAdminDisplayTests(TestCase):
    def setUp(self):
        self.admin_instance = VehicleAdmin(Vehicle, admin.site)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_repair_order_count_is_correct(self):
        make_repair_order(self.customer, self.vehicle)
        self.assertEqual(self.admin_instance.repair_order_count(self.vehicle), 1)
