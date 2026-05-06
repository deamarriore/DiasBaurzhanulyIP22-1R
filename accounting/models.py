"""
Демо-модели бухгалтерского учёта (двойная запись). Упрощённый план счетов в стиле РК.
Не предназначено для строгого соответствия налоговому законодательству.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from inventory.models import Product


class AccountType(models.TextChoices):
    ASSET = "asset", "Актив"
    LIABILITY = "liability", "Обязательство"
    EQUITY = "equity", "Капитал"
    INCOME = "income", "Доход"
    EXPENSE = "expense", "Расход"


class Account(models.Model):
    """Счёт плана счетов."""

    code = models.CharField(max_length=20, unique=True, verbose_name="Код")
    name = models.CharField(max_length=255, verbose_name="Наименование")
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        verbose_name="Тип счёта",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Счёт"
        verbose_name_plural = "План счетов"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def is_debit_normal(self) -> bool:
        """Нормальное сальдо по дебету для активов и расходов."""
        return self.account_type in (AccountType.ASSET, AccountType.EXPENSE)


class CounterpartyKind(models.TextChoices):
    CUSTOMER = "customer", "Клиент"
    SUPPLIER = "supplier", "Поставщик"
    BOTH = "both", "Клиент и поставщик"


class Counterparty(models.Model):
    """Контрагент для документов и субконто."""

    kind = models.CharField(
        max_length=20,
        choices=CounterpartyKind.choices,
        default=CounterpartyKind.BOTH,
        verbose_name="Тип",
    )
    name = models.CharField(max_length=255, verbose_name="Наименование")
    bin_optional = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="БИН/ИИН (демо)",
    )
    phone = models.CharField(max_length=40, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    inventory_supplier = models.OneToOneField(
        "inventory.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_counterparty",
        verbose_name="Связь с поставщиком склада",
    )

    class Meta:
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"
        ordering = ["name"]

    def __str__(self):
        return self.name


class JournalEntry(models.Model):
    """Шапка проводки (журнала)."""

    number = models.CharField(max_length=40, unique=True, verbose_name="Номер")
    date = models.DateField(verbose_name="Дата")
    description = models.CharField(max_length=500, blank=True, verbose_name="Описание")
    is_posted = models.BooleanField(default=True, verbose_name="Проведена")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Автор",
    )

    class Meta:
        verbose_name = "Проводка"
        verbose_name_plural = "Журнал проводок"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.number} от {self.date}"

    def is_balanced(self) -> bool:
        lines = list(self.lines.all())
        if not lines:
            return False
        total_dr = sum((ln.debit for ln in lines), Decimal("0"))
        total_cr = sum((ln.credit for ln in lines), Decimal("0"))
        return total_dr == total_cr


class JournalLine(models.Model):
    """Строка проводки."""

    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Проводка",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        verbose_name="Счёт",
    )
    debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Дебет",
    )
    credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Кредит",
    )
    counterparty = models.ForeignKey(
        Counterparty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Контрагент",
    )
    description = models.CharField(max_length=255, blank=True, verbose_name="Примечание")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        verbose_name = "Строка проводки"
        verbose_name_plural = "Строки проводок"
        ordering = ["sort_order", "id"]

    def clean(self):
        dr_positive = self.debit > 0
        cr_positive = self.credit > 0
        if dr_positive and cr_positive:
            raise ValidationError("Укажите либо дебет, либо кредит, не оба.")
        if not dr_positive and not cr_positive:
            raise ValidationError("Сумма дебета или кредита должна быть больше нуля.")
        if self.debit < 0 or self.credit < 0:
            raise ValidationError("Суммы не могут быть отрицательными.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class FiscalPeriod(models.Model):
    """Закрытие периода (демо)."""

    year = models.PositiveIntegerField(verbose_name="Год")
    month = models.PositiveSmallIntegerField(verbose_name="Месяц")
    is_closed = models.BooleanField(default=False, verbose_name="Закрыт")

    class Meta:
        verbose_name = "Фискальный период"
        verbose_name_plural = "Фискальные периоды"
        constraints = [
            models.UniqueConstraint(fields=["year", "month"], name="unique_fiscal_period"),
        ]

    def __str__(self):
        return f"{self.year}-{self.month:02d}"


class SalesInvoice(models.Model):
    """Реализация (счёт-фактура продажи, демо)."""

    number = models.CharField(max_length=40, unique=True, verbose_name="Номер")
    date = models.DateField(verbose_name="Дата")
    counterparty = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        verbose_name="Покупатель",
    )
    is_posted = models.BooleanField(default=False, verbose_name="Проведён")
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_invoice",
        verbose_name="Проводка",
    )
    note = models.TextField(blank=True, verbose_name="Примечание")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Создал",
    )

    class Meta:
        verbose_name = "Реализация"
        verbose_name_plural = "Реализации"
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number

    def line_total_revenue(self) -> Decimal:
        return sum((ln.line_revenue() for ln in self.lines.all()), Decimal("0"))

    def line_total_cogs(self) -> Decimal:
        return sum((ln.line_cogs() for ln in self.lines.all()), Decimal("0"))


class SalesInvoiceLine(models.Model):
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Документ",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="Товар",
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Цена продажи за ед.",
    )
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Себестоимость за ед.",
        help_text="Для демо; можно отличать от цены продажи.",
    )

    class Meta:
        verbose_name = "Строка реализации"
        verbose_name_plural = "Строки реализации"

    def line_revenue(self) -> Decimal:
        return Decimal(self.quantity) * self.unit_price

    def line_cogs(self) -> Decimal:
        return Decimal(self.quantity) * self.unit_cost


class PurchaseInvoice(models.Model):
    """Закупка у поставщика (демо)."""

    number = models.CharField(max_length=40, unique=True, verbose_name="Номер")
    date = models.DateField(verbose_name="Дата")
    counterparty = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        verbose_name="Поставщик",
    )
    is_posted = models.BooleanField(default=False, verbose_name="Проведён")
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_invoice",
        verbose_name="Проводка",
    )
    note = models.TextField(blank=True, verbose_name="Примечание")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Создал",
    )

    class Meta:
        verbose_name = "Закупка"
        verbose_name_plural = "Закупки"
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number

    def line_total(self) -> Decimal:
        return sum((ln.line_amount() for ln in self.lines.all()), Decimal("0"))


class PurchaseInvoiceLine(models.Model):
    invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Документ",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="Товар",
    )
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Цена закупки за ед.",
    )

    class Meta:
        verbose_name = "Строка закупки"
        verbose_name_plural = "Строки закупки"

    def line_amount(self) -> Decimal:
        return Decimal(self.quantity) * self.unit_cost


class CashAccountChoice(models.TextChoices):
    CASH = "1010", "Касса (1010)"
    BANK = "1030", "Расчётный счёт (1030)"


class CashOperationKind(models.TextChoices):
    CUSTOMER_RECEIPT = "customer_receipt", "Поступление от клиента"
    SUPPLIER_PAYMENT = "supplier_payment", "Оплата поставщику"
    MISC_INCOME = "misc_income", "Прочий приход"
    MISC_EXPENSE = "misc_expense", "Прочий расход"


class CashOperation(models.Model):
    """Касса / банк."""

    number = models.CharField(max_length=40, unique=True, verbose_name="Номер")
    date = models.DateField(verbose_name="Дата")
    kind = models.CharField(
        max_length=30,
        choices=CashOperationKind.choices,
        verbose_name="Тип операции",
    )
    cash_account = models.CharField(
        max_length=10,
        choices=CashAccountChoice.choices,
        default=CashAccountChoice.CASH,
        verbose_name="Деньги",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Сумма")
    counterparty = models.ForeignKey(
        Counterparty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_operations",
        verbose_name="Контрагент",
    )
    description = models.CharField(max_length=500, blank=True, verbose_name="Описание")
    is_posted = models.BooleanField(default=False, verbose_name="Проведён")
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_operation",
        verbose_name="Проводка",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Создал",
    )

    class Meta:
        verbose_name = "Касса/банк"
        verbose_name_plural = "Касса и банк"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.number} ({self.get_kind_display()})"


def next_journal_number(prefix: str = "JE") -> str:
    """Генерация номера проводки (демо, по счётчику записей)."""
    return f"{prefix}-{JournalEntry.objects.count() + 1}"
