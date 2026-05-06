"""Проведение документов и формирование проводок."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from inventory.models import StockOperation

from accounting.models import (
    Account,
    CashOperation,
    CashOperationKind,
    JournalEntry,
    JournalLine,
    PurchaseInvoice,
    SalesInvoice,
    next_journal_number,
)


def _account(code: str) -> Account:
    try:
        return Account.objects.get(code=code)
    except Account.DoesNotExist as exc:
        raise ValidationError(f"Счёт с кодом {code} не найден. Запустите init_accounting.") from exc


def _require_balanced(entry: JournalEntry) -> None:
    entry.refresh_from_db()
    if not entry.is_balanced():
        raise ValidationError("Проводка не сбалансирована.")


@transaction.atomic
def post_sales_invoice(invoice: SalesInvoice, user=None) -> JournalEntry:
    """Дт 1210 / Кт 6010 (выручка); Дт 7010 / Кт 1330 (себестоимость); склад — расход."""
    if invoice.is_posted:
        raise ValidationError("Документ уже проведён.")
    lines = list(invoice.lines.select_related("product"))
    if not lines:
        raise ValidationError("Добавьте хотя бы одну строку.")

    revenue = invoice.line_total_revenue()
    cogs = invoice.line_total_cogs()
    if revenue <= 0:
        raise ValidationError("Сумма реализации должна быть больше нуля.")

    for ln in lines:
        if ln.quantity <= 0:
            raise ValidationError("Количество в строке должно быть больше нуля.")
        if ln.product.current_quantity < ln.quantity:
            raise ValidationError(
                f"Недостаточно товара «{ln.product.name}»: "
                f"есть {ln.product.current_quantity}, нужно {ln.quantity}."
            )

    author = user or invoice.created_by
    entry = JournalEntry.objects.create(
        number=next_journal_number(),
        date=invoice.date,
        description=f"Реализация {invoice.number}",
        is_posted=True,
        created_by=author,
    )

    ar = _account("1210")
    rev = _account("6010")
    cogs_acc = _account("7010")
    inv = _account("1330")

    cp = invoice.counterparty
    JournalLine.objects.create(
        entry=entry,
        account=ar,
        debit=revenue,
        credit=Decimal("0"),
        counterparty=cp,
        description="Дебиторская задолженность",
        sort_order=1,
    )
    JournalLine.objects.create(
        entry=entry,
        account=rev,
        debit=Decimal("0"),
        credit=revenue,
        counterparty=cp,
        description="Выручка",
        sort_order=2,
    )
    if cogs > 0:
        JournalLine.objects.create(
            entry=entry,
            account=cogs_acc,
            debit=cogs,
            credit=Decimal("0"),
            description="Себестоимость",
            sort_order=3,
        )
        JournalLine.objects.create(
            entry=entry,
            account=inv,
            debit=Decimal("0"),
            credit=cogs,
            description="Списание запасов",
            sort_order=4,
        )

    _require_balanced(entry)

    for ln in lines:
        StockOperation.objects.create(
            product=ln.product,
            operation_type="out",
            quantity=ln.quantity,
            reason=f"Реализация {invoice.number}",
            created_by=author,
        )

    invoice.journal_entry = entry
    invoice.is_posted = True
    invoice.save(update_fields=["journal_entry", "is_posted"])
    return entry


@transaction.atomic
def unpost_sales_invoice(invoice: SalesInvoice, user=None) -> None:
    """Отмена проведения: возврат на склад проводками прихода и удаление проводки."""
    if not invoice.is_posted or not invoice.journal_entry_id:
        raise ValidationError("Документ не проведён.")

    author = user or invoice.created_by
    entry = invoice.journal_entry

    for ln in invoice.lines.select_related("product"):
        StockOperation.objects.create(
            product=ln.product,
            operation_type="in",
            quantity=ln.quantity,
            reason=f"Сторно реализации {invoice.number}",
            created_by=author,
        )

    JournalLine.objects.filter(entry=entry).delete()
    entry.delete()

    invoice.journal_entry = None
    invoice.is_posted = False
    invoice.save(update_fields=["journal_entry", "is_posted"])


@transaction.atomic
def post_purchase_invoice(invoice: PurchaseInvoice, user=None) -> JournalEntry:
    """Дт 1330 / Кт 3310; склад — приход."""
    if invoice.is_posted:
        raise ValidationError("Документ уже проведён.")
    lines = list(invoice.lines.select_related("product"))
    if not lines:
        raise ValidationError("Добавьте хотя бы одну строку.")

    total = invoice.line_total()
    if total <= 0:
        raise ValidationError("Сумма закупки должна быть больше нуля.")

    author = user or invoice.created_by
    entry = JournalEntry.objects.create(
        number=next_journal_number(),
        date=invoice.date,
        description=f"Закупка {invoice.number}",
        is_posted=True,
        created_by=author,
    )

    inv = _account("1330")
    ap = _account("3310")
    cp = invoice.counterparty

    JournalLine.objects.create(
        entry=entry,
        account=inv,
        debit=total,
        credit=Decimal("0"),
        description="Поступление запасов",
        sort_order=1,
    )
    JournalLine.objects.create(
        entry=entry,
        account=ap,
        debit=Decimal("0"),
        credit=total,
        counterparty=cp,
        description="Кредиторская задолженность",
        sort_order=2,
    )

    _require_balanced(entry)

    for ln in lines:
        StockOperation.objects.create(
            product=ln.product,
            operation_type="in",
            quantity=ln.quantity,
            reason=f"Закупка {invoice.number}",
            created_by=author,
        )

    invoice.journal_entry = entry
    invoice.is_posted = True
    invoice.save(update_fields=["journal_entry", "is_posted"])
    return entry


@transaction.atomic
def unpost_purchase_invoice(invoice: PurchaseInvoice, user=None) -> None:
    """Сторно закупки: расход со склада и удаление проводки."""
    if not invoice.is_posted or not invoice.journal_entry_id:
        raise ValidationError("Документ не проведён.")

    author = user or invoice.created_by
    entry = invoice.journal_entry

    for ln in invoice.lines.select_related("product"):
        StockOperation.objects.create(
            product=ln.product,
            operation_type="out",
            quantity=ln.quantity,
            reason=f"Сторно закупки {invoice.number}",
            created_by=author,
        )

    JournalLine.objects.filter(entry=entry).delete()
    entry.delete()

    invoice.journal_entry = None
    invoice.is_posted = False
    invoice.save(update_fields=["journal_entry", "is_posted"])


@transaction.atomic
def post_cash_operation(op: CashOperation, user=None) -> JournalEntry:
    if op.is_posted:
        raise ValidationError("Документ уже проведён.")
    if op.amount <= 0:
        raise ValidationError("Сумма должна быть больше нуля.")

    cash_code = op.cash_account  # "1010" or "1030"
    cash_acc = _account(cash_code)
    author = user or op.created_by

    entry = JournalEntry.objects.create(
        number=next_journal_number(),
        date=op.date,
        description=f"{op.number} {op.get_kind_display()}",
        is_posted=True,
        created_by=author,
    )

    amt = op.amount
    cp = op.counterparty

    if op.kind == CashOperationKind.CUSTOMER_RECEIPT:
        ar = _account("1210")
        JournalLine.objects.create(
            entry=entry,
            account=cash_acc,
            debit=amt,
            credit=Decimal("0"),
            description=op.description or "Поступление от клиента",
            sort_order=1,
        )
        JournalLine.objects.create(
            entry=entry,
            account=ar,
            debit=Decimal("0"),
            credit=amt,
            counterparty=cp,
            description=op.description or "Погашение дебиторки",
            sort_order=2,
        )
    elif op.kind == CashOperationKind.SUPPLIER_PAYMENT:
        ap = _account("3310")
        JournalLine.objects.create(
            entry=entry,
            account=ap,
            debit=amt,
            credit=Decimal("0"),
            counterparty=cp,
            description=op.description or "Оплата поставщику",
            sort_order=1,
        )
        JournalLine.objects.create(
            entry=entry,
            account=cash_acc,
            debit=Decimal("0"),
            credit=amt,
            description=op.description or "Списание денег",
            sort_order=2,
        )
    elif op.kind == CashOperationKind.MISC_INCOME:
        inc = _account("6110")
        JournalLine.objects.create(
            entry=entry,
            account=cash_acc,
            debit=amt,
            credit=Decimal("0"),
            description=op.description or "Прочий приход",
            sort_order=1,
        )
        JournalLine.objects.create(
            entry=entry,
            account=inc,
            debit=Decimal("0"),
            credit=amt,
            description=op.description or "Прочие доходы",
            sort_order=2,
        )
    elif op.kind == CashOperationKind.MISC_EXPENSE:
        exp = _account("7210")
        JournalLine.objects.create(
            entry=entry,
            account=exp,
            debit=amt,
            credit=Decimal("0"),
            description=op.description or "Прочий расход",
            sort_order=1,
        )
        JournalLine.objects.create(
            entry=entry,
            account=cash_acc,
            debit=Decimal("0"),
            credit=amt,
            description=op.description or "Оплата из кассы/банка",
            sort_order=2,
        )
    else:
        raise ValidationError("Неизвестный тип операции.")

    _require_balanced(entry)

    op.journal_entry = entry
    op.is_posted = True
    op.save(update_fields=["journal_entry", "is_posted"])
    return entry


@transaction.atomic
def unpost_cash_operation(op: CashOperation) -> None:
    if not op.is_posted or not op.journal_entry_id:
        raise ValidationError("Документ не проведён.")
    entry = op.journal_entry
    JournalLine.objects.filter(entry=entry).delete()
    entry.delete()
    op.journal_entry = None
    op.is_posted = False
    op.save(update_fields=["journal_entry", "is_posted"])
