"""Tests for the shared tax utility and the SHOP_SALES_TAX_RATE setting."""

from decimal import Decimal

from config.settings import env_decimal_rate
from core.tax import (
    calculate_tax,
    default_sales_tax_rate,
    default_taxable_for_item_type,
    quantize_money,
)
from django.conf import settings
from django.test import TestCase


class TaxUtilityTests(TestCase):
    def test_calculate_tax_basic(self):
        self.assertEqual(calculate_tax(Decimal("100.00"), Decimal("0.0825")), Decimal("8.25"))

    def test_calculate_tax_rounds_half_up(self):
        # 33.33 * 0.0825 = 2.749725 -> 2.75
        self.assertEqual(calculate_tax(Decimal("33.33"), Decimal("0.0825")), Decimal("2.75"))

    def test_calculate_tax_zero_rate(self):
        self.assertEqual(calculate_tax(Decimal("500.00"), Decimal("0")), Decimal("0.00"))

    def test_quantize_money_rounds_half_up(self):
        self.assertEqual(quantize_money(Decimal("1.005")), Decimal("1.01"))

    def test_default_taxability_by_item_type(self):
        self.assertFalse(default_taxable_for_item_type("labor"))
        self.assertTrue(default_taxable_for_item_type("parts"))
        self.assertTrue(default_taxable_for_item_type("materials"))
        self.assertFalse(default_taxable_for_item_type("sublet"))
        self.assertFalse(default_taxable_for_item_type("misc"))

    def test_default_taxability_unknown_type_is_false(self):
        self.assertFalse(default_taxable_for_item_type("unknown"))


class SalesTaxRateSettingTests(TestCase):
    def test_default_rate_is_decimal_0825(self):
        self.assertEqual(settings.SHOP_SALES_TAX_RATE, Decimal("0.0825"))
        self.assertEqual(default_sales_tax_rate(), Decimal("0.0825"))

    def test_blank_env_falls_back_to_default(self):
        self.assertEqual(
            env_decimal_rate("SHOP_SALES_TAX_RATE_MISSING", "0.0825"), Decimal("0.0825")
        )

    def test_valid_env_is_parsed_and_stripped(self):
        import os

        os.environ["_TEST_TAX_RATE"] = "  0.0625  "
        try:
            self.assertEqual(env_decimal_rate("_TEST_TAX_RATE", "0.0825"), Decimal("0.0625"))
        finally:
            del os.environ["_TEST_TAX_RATE"]

    def test_invalid_env_fails_loudly(self):
        import os

        os.environ["_TEST_TAX_RATE"] = "not-a-number"
        try:
            with self.assertRaises(RuntimeError):
                env_decimal_rate("_TEST_TAX_RATE", "0.0825")
        finally:
            del os.environ["_TEST_TAX_RATE"]

    def test_out_of_range_env_fails_loudly(self):
        import os

        os.environ["_TEST_TAX_RATE"] = "1.5"
        try:
            with self.assertRaises(RuntimeError):
                env_decimal_rate("_TEST_TAX_RATE", "0.0825")
        finally:
            del os.environ["_TEST_TAX_RATE"]

    def test_negative_env_fails_loudly(self):
        import os

        os.environ["_TEST_TAX_RATE"] = "-0.01"
        try:
            with self.assertRaises(RuntimeError):
                env_decimal_rate("_TEST_TAX_RATE", "0.0825")
        finally:
            del os.environ["_TEST_TAX_RATE"]
