from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import (
    Account,
    AccountType,
    Counterparty,
    CounterpartyKind,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from accounting.services import posting
from accounting.services import reports as report_svc
from inventory.models import Category, Product, Supplier


def _seed_accounts():
    data = [
        ("1010", "Касса", AccountType.ASSET),
        ("1030", "Банк", AccountType.ASSET),
        ("1210", "Дебиторка", AccountType.ASSET),
        ("1330", "Запасы", AccountType.ASSET),
        ("3310", "Кредиторка", AccountType.LIABILITY),
        ("6010", "Выручка", AccountType.INCOME),
        ("6110", "Прочие доходы", AccountType.INCOME),
        ("7010", "Себестоимость", AccountType.EXPENSE),
        ("7210", "Расходы", AccountType.EXPENSE),
    ]
    for code, name, atype in data:
        Account.objects.get_or_create(
            code=code,
            defaults={"name": name, "account_type": atype, "is_active": True},
        )


class PostingTests(TestCase):
    def setUp(self):
        _seed_accounts()
        self.user = User.objects.create_user("tester", password="secret")
        self.cat = Category.objects.create(name="КатТест")
        self.supplier = Supplier.objects.create(name="ПостТест", address="Адрес")
        self.product = Product.objects.create(
            name="ТоварТест",
            article="T-001",
            category=self.cat,
            supplier=self.supplier,
            price=Decimal("1000.00"),
            current_quantity=5,
        )
        self.customer = Counterparty.objects.create(
            name="КлиентТест",
            kind=CounterpartyKind.CUSTOMER,
        )
        self.supplier_cp = Counterparty.objects.create(
            name="ПостТест",
            kind=CounterpartyKind.SUPPLIER,
        )

    def test_post_purchase_increases_stock_and_balanced_journal(self):
        pi = PurchaseInvoice.objects.create(
            number="PI-T1",
            date=date(2026, 2, 1),
            counterparty=self.supplier_cp,
            created_by=self.user,
        )
        PurchaseInvoiceLine.objects.create(
            invoice=pi,
            product=self.product,
            quantity=3,
            unit_cost=Decimal("400.00"),
        )
        je = posting.post_purchase_invoice(pi, self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_quantity, 8)
        self.assertTrue(pi.is_posted)
        je.refresh_from_db()
        self.assertTrue(je.is_balanced())

    def test_post_sale_decreases_stock(self):
        si = SalesInvoice.objects.create(
            number="SI-T1",
            date=date(2026, 2, 2),
            counterparty=self.customer,
            created_by=self.user,
        )
        SalesInvoiceLine.objects.create(
            invoice=si,
            product=self.product,
            quantity=2,
            unit_price=Decimal("900.00"),
            unit_cost=Decimal("400.00"),
        )
        posting.post_sales_invoice(si, self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_quantity, 3)

    def test_post_sale_fails_if_not_enough_qty(self):
        si = SalesInvoice.objects.create(
            number="SI-T2",
            date=date(2026, 2, 3),
            counterparty=self.customer,
            created_by=self.user,
        )
        SalesInvoiceLine.objects.create(
            invoice=si,
            product=self.product,
            quantity=100,
            unit_price=Decimal("1.00"),
            unit_cost=Decimal("1.00"),
        )
        with self.assertRaises(ValidationError):
            posting.post_sales_invoice(si, self.user)

    def test_trial_balance_runs_after_posting(self):
        pi = PurchaseInvoice.objects.create(
            number="PI-T2",
            date=date(2026, 3, 1),
            counterparty=self.supplier_cp,
            created_by=self.user,
        )
        PurchaseInvoiceLine.objects.create(
            invoice=pi,
            product=self.product,
            quantity=1,
            unit_cost=Decimal("100.00"),
        )
        posting.post_purchase_invoice(pi, self.user)
        rows = report_svc.trial_balance(date(2026, 3, 1), date(2026, 3, 31))
        self.assertTrue(len(rows) > 0)
