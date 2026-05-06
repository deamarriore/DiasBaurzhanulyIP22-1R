"""Отчёты: ОСВ, главная книга, P&L, баланс."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from accounting.models import Account, AccountType, JournalLine


def _lines_qs():
    return JournalLine.objects.filter(entry__is_posted=True).select_related(
        "entry", "account"
    )


def _signed_amount(account: Account, debit: Decimal, credit: Decimal) -> Decimal:
    """Вклад строки в «сальдо» счёта (активы/расходы: Дт−Кт; остальные: Кт−Дт)."""
    if account.is_debit_normal:
        return debit - credit
    return credit - debit


def account_balance_as_of(account: Account, as_of) -> Decimal:
    """Сальдо на конец даты as_of (включительно)."""
    agg = (
        _lines_qs()
        .filter(account=account, entry__date__lte=as_of)
        .aggregate(dr=Sum("debit"), cr=Sum("credit"))
    )
    dr = agg["dr"] or Decimal("0")
    cr = agg["cr"] or Decimal("0")
    return _signed_amount(account, dr, cr)


def account_movement(account: Account, date_from, date_to) -> tuple[Decimal, Decimal]:
    """Обороты за период: (дебет, кредит)."""
    agg = (
        _lines_qs()
        .filter(account=account, entry__date__gte=date_from, entry__date__lte=date_to)
        .aggregate(dr=Sum("debit"), cr=Sum("credit"))
    )
    dr = agg["dr"] or Decimal("0")
    cr = agg["cr"] or Decimal("0")
    return dr, cr


def opening_balance(account: Account, date_from) -> Decimal:
    """Сальдо на начало date_from (строго до даты)."""
    agg = (
        _lines_qs()
        .filter(account=account, entry__date__lt=date_from)
        .aggregate(dr=Sum("debit"), cr=Sum("credit"))
    )
    dr = agg["dr"] or Decimal("0")
    cr = agg["cr"] or Decimal("0")
    return _signed_amount(account, dr, cr)


@dataclass
class TrialBalanceRow:
    account: Account
    opening: Decimal
    debit: Decimal
    credit: Decimal
    closing: Decimal


def trial_balance(date_from, date_to) -> list[TrialBalanceRow]:
    rows: list[TrialBalanceRow] = []
    for acc in Account.objects.filter(is_active=True):
        ob = opening_balance(acc, date_from)
        dr, cr = account_movement(acc, date_from, date_to)
        closing = ob + _signed_amount(acc, dr, cr)
        if ob == 0 and dr == 0 and cr == 0:
            continue
        rows.append(TrialBalanceRow(account=acc, opening=ob, debit=dr, credit=cr, closing=closing))
    return rows


@dataclass
class LedgerRow:
    row_date: date
    entry_number: str
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


def general_ledger(account: Account, date_from, date_to) -> list[LedgerRow]:
    lines = (
        _lines_qs()
        .filter(account=account, entry__date__gte=date_from, entry__date__lte=date_to)
        .select_related("entry")
        .order_by("entry__date", "entry_id", "sort_order", "id")
    )
    balance = opening_balance(account, date_from)
    out: list[LedgerRow] = []
    for ln in lines:
        balance = balance + _signed_amount(account, ln.debit, ln.credit)
        out.append(
            LedgerRow(
                row_date=ln.entry.date,
                entry_number=ln.entry.number,
                description=ln.description or ln.entry.description,
                debit=ln.debit,
                credit=ln.credit,
                balance=balance,
            )
        )
    return out


def profit_and_loss(date_from, date_to) -> tuple[Decimal, Decimal, Decimal]:
    """(доходы, расходы, прибыль) за период по типам счетов."""
    income_total = Decimal("0")
    expense_total = Decimal("0")
    for acc in Account.objects.filter(is_active=True):
        dr, cr = account_movement(acc, date_from, date_to)
        if acc.account_type == AccountType.INCOME:
            income_total += cr - dr
        elif acc.account_type == AccountType.EXPENSE:
            expense_total += dr - cr
    profit = income_total - expense_total
    return income_total, expense_total, profit


def balance_sheet(as_of):
    """
    Упрощённый баланс на дату: активы, обязательства, капитал.
    Активы / Обязательства / Капитал считаются как сальдо соответствующих типов счетов.
    """
    assets = Decimal("0")
    liabilities = Decimal("0")
    equity = Decimal("0")
    for acc in Account.objects.filter(is_active=True):
        bal = account_balance_as_of(acc, as_of)
        if acc.account_type == AccountType.ASSET:
            assets += bal
        elif acc.account_type == AccountType.LIABILITY:
            liabilities += bal
        elif acc.account_type == AccountType.EQUITY:
            equity += bal
    # Нераспределённая прибыль: накопленный финрез до as_of по доходам/расходам
    income_bal = Decimal("0")
    expense_bal = Decimal("0")
    for acc in Account.objects.filter(is_active=True):
        bal = account_balance_as_of(acc, as_of)
        if acc.account_type == AccountType.INCOME:
            income_bal += bal
        elif acc.account_type == AccountType.EXPENSE:
            expense_bal += bal
    retained = income_bal - expense_bal
    equity_total = equity + retained
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity_plain": equity,
        "retained_earnings": retained,
        "equity_total": equity_total,
        "check": assets - (liabilities + equity_total),
    }
