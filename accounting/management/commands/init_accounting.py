"""Инициализация плана счетов (демо, стиль РК) и опционально демо-данных."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounting.models import (
    Account,
    AccountType,
    CashAccountChoice,
    CashOperation,
    CashOperationKind,
    Counterparty,
    CounterpartyKind,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from accounting.services import posting
from inventory.models import Product, Supplier


ACCOUNTS = [
    ("1010", "Касса", AccountType.ASSET),
    ("1030", "Расчётный счёт в банке", AccountType.ASSET),
    ("1210", "Дебиторская задолженность покупателей", AccountType.ASSET),
    ("1330", "Запасы (товары)", AccountType.ASSET),
    ("3310", "Кредиторская задолженность поставщикам", AccountType.LIABILITY),
    ("4010", "Обязательства по НДС (демо)", AccountType.LIABILITY),
    ("5010", "Уставный капитал", AccountType.EQUITY),
    ("5410", "Нераспределённая прибыль отчётного года", AccountType.EQUITY),
    ("6010", "Доход от реализации товаров", AccountType.INCOME),
    ("6110", "Прочие доходы", AccountType.INCOME),
    ("7010", "Себестоимость реализованных товаров", AccountType.EXPENSE),
    ("7210", "Административные расходы", AccountType.EXPENSE),
]


class Command(BaseCommand):
    help = "Создаёт демо-план счетов; опционально — контрагентов и примеры документов."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-demo",
            action="store_true",
            help="Создать контрагентов и провести пример закупки/продажи (нужен товар и пользователь).",
        )

    def handle(self, *args, **options):
        created = 0
        for code, name, atype in ACCOUNTS:
            obj, was_created = Account.objects.get_or_create(
                code=code,
                defaults={"name": name, "account_type": atype, "is_active": True},
            )
            if was_created:
                created += 1
            else:
                obj.name = name
                obj.account_type = atype
                obj.is_active = True
                obj.save(update_fields=["name", "account_type", "is_active"])

        self.stdout.write(self.style.SUCCESS(f"План счетов: учтено счетов {len(ACCOUNTS)}, новых: {created}"))

        if options["with_demo"]:
            self._demo_documents()

    def _demo_documents(self):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("Нет пользователя в БД — создайте superuser."))
            return

        product = Product.objects.order_by("pk").first()
        if not product:
            self.stdout.write(
                self.style.WARNING("Нет товаров — добавьте товар в админке или через склад, затем повторите.")
            )
            return

        cust, _ = Counterparty.objects.get_or_create(
            name="ТОО ДемоКлиент",
            defaults={"kind": CounterpartyKind.CUSTOMER, "bin_optional": "123456789012"},
        )

        sup_inv = Supplier.objects.order_by("pk").first()
        sup_cp = None
        if sup_inv:
            sup_cp, _ = Counterparty.objects.get_or_create(
                name=sup_inv.name,
                defaults={
                    "kind": CounterpartyKind.SUPPLIER,
                    "inventory_supplier": sup_inv,
                },
            )
            if sup_cp.inventory_supplier_id != sup_inv.id:
                sup_cp.inventory_supplier = sup_inv
                sup_cp.kind = CounterpartyKind.SUPPLIER
                sup_cp.save(update_fields=["inventory_supplier", "kind"])

        if not sup_cp:
            sup_cp, _ = Counterparty.objects.get_or_create(
                name="ТОО ДемоПоставщик",
                defaults={"kind": CounterpartyKind.SUPPLIER, "bin_optional": "987654321098"},
            )

        # Закупка + продажа (если номера свободны)
        if not PurchaseInvoice.objects.filter(number="DEMO-PI-1").exists():
            pi = PurchaseInvoice.objects.create(
                number="DEMO-PI-1",
                date=date(2026, 1, 10),
                counterparty=sup_cp,
                note="Демо закупка",
                created_by=user,
            )
            PurchaseInvoiceLine.objects.create(
                invoice=pi,
                product=product,
                quantity=10,
                unit_cost=Decimal("5000.00"),
            )
            posting.post_purchase_invoice(pi, user)
            self.stdout.write(self.style.SUCCESS("Проведена демо-закупка DEMO-PI-1"))

        if not SalesInvoice.objects.filter(number="DEMO-SI-1").exists():
            si = SalesInvoice.objects.create(
                number="DEMO-SI-1",
                date=date(2026, 1, 15),
                counterparty=cust,
                note="Демо реализация",
                created_by=user,
            )
            SalesInvoiceLine.objects.create(
                invoice=si,
                product=product,
                quantity=3,
                unit_price=Decimal("9000.00"),
                unit_cost=Decimal("5000.00"),
            )
            posting.post_sales_invoice(si, user)
            self.stdout.write(self.style.SUCCESS("Проведена демо-реализация DEMO-SI-1"))

        if not CashOperation.objects.filter(number="DEMO-CO-1").exists():
            co = CashOperation.objects.create(
                number="DEMO-CO-1",
                date=date(2026, 1, 16),
                kind=CashOperationKind.CUSTOMER_RECEIPT,
                cash_account=CashAccountChoice.CASH,
                amount=Decimal("27000.00"),
                counterparty=cust,
                description="Частичная оплата от клиента (демо)",
                created_by=user,
            )
            posting.post_cash_operation(co, user)
            self.stdout.write(self.style.SUCCESS("Проведено демо-поступление DEMO-CO-1"))
