from calendar import monthrange
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import F, Sum
from django.http import HttpResponse
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounting.forms import (
    CashOperationForm,
    PurchaseInvoiceForm,
    PurchaseInvoiceLineForm,
    PurchaseInvoiceLineFormSet,
    RegistrationForm,
    SalesInvoiceForm,
    SalesInvoiceLineFormSet,
)
from accounting.models import (
    Account,
    CashOperation,
    JournalEntry,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
)
from accounting.services import posting
from accounting.services import reports as report_svc
from accounting.utils import next_document_number
from inventory.models import Product


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return default


def _month_bounds(today: date) -> tuple[date, date]:
    first = today.replace(day=1)
    last = today.replace(day=monthrange(today.year, today.month)[1])
    return first, last


def _validation_messages(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        parts = []
        for k, v in exc.message_dict.items():
            parts.append(f"{k}: {', '.join(v)}")
        return "; ".join(parts)
    if exc.messages:
        return "; ".join(exc.messages)
    return str(exc)


@login_required
def dashboard(request):
    today = timezone.now().date()
    d_from, d_to = _month_bounds(today)
    _, _, profit = report_svc.profit_and_loss(d_from, d_to)

    key_codes = ["1010", "1030", "1210", "3310", "1330"]
    key_balances = []
    for code in key_codes:
        acc = Account.objects.filter(code=code).first()
        key_balances.append(
            {
                "code": code,
                "name": acc.name if acc else "—",
                "amount": report_svc.account_balance_as_of(acc, today) if acc else None,
            }
        )

    recent_entries = JournalEntry.objects.order_by("-date", "-id")[:15]
    recent_sales = SalesInvoice.objects.order_by("-date", "-id")[:5]
    recent_purchases = PurchaseInvoice.objects.order_by("-date", "-id")[:5]

    inventory_products = Product.objects.all()
    total_inventory_items = inventory_products.count()
    total_inventory_quantity = inventory_products.aggregate(total=Sum('current_quantity'))['total'] or 0
    total_inventory_value = inventory_products.aggregate(total=Sum(F('price') * F('current_quantity')))['total'] or 0
    low_stock_products_count = inventory_products.filter(current_quantity__lt=F('min_threshold')).count()

    return render(
        request,
        "accounting/dashboard.html",
        {
            "today": today,
            "month_from": d_from,
            "month_to": d_to,
            "profit_month": profit,
            "key_balances": key_balances,
            "recent_entries": recent_entries,
            "recent_sales": recent_sales,
            "recent_purchases": recent_purchases,
            "total_inventory_items": total_inventory_items,
            "total_inventory_quantity": total_inventory_quantity,
            "total_inventory_value": total_inventory_value,
            "low_stock_products_count": low_stock_products_count,
        },
    )


@login_required
def account_list(request):
    accounts = Account.objects.filter(is_active=True).order_by("code")
    return render(request, "accounting/account_list.html", {"accounts": accounts})


@login_required
def journal_list(request):
    entries = JournalEntry.objects.order_by("-date", "-id")[:200]
    return render(request, "accounting/journal_list.html", {"entries": entries})


@login_required
def journal_detail(request, pk):
    entry = get_object_or_404(JournalEntry.objects.prefetch_related("lines__account"), pk=pk)
    return render(request, "accounting/journal_detail.html", {"entry": entry})


@login_required
def sales_list(request):
    invoices = SalesInvoice.objects.select_related("counterparty").order_by("-date", "-id")
    return render(request, "accounting/sales_list.html", {"invoices": invoices})


@login_required
def sales_create(request):
    today = timezone.now().date()
    initial = {
        "number": next_document_number("SI", SalesInvoice),
        "date": today,
    }
    if request.method == "POST":
        form = SalesInvoiceForm(request.POST)
        formset = SalesInvoiceLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            inv = form.save(commit=False)
            inv.created_by = request.user
            inv.save()
            formset.instance = inv
            formset.save()
            if "save_post" in request.POST:
                try:
                    posting.post_sales_invoice(inv, request.user)
                    messages.success(request, "Документ сохранён и проведён.")
                except ValidationError as e:
                    messages.error(request, _validation_messages(e))
            else:
                messages.success(request, "Черновик сохранён. Проведите документ на странице просмотра.")
            return redirect("accounting:sales_detail", pk=inv.pk)
    else:
        form = SalesInvoiceForm(initial=initial)
        formset = SalesInvoiceLineFormSet()
    return render(
        request,
        "accounting/sales_form.html",
        {"form": form, "formset": formset, "title": "Новая реализация"},
    )


@login_required
def sales_detail(request, pk):
    inv = get_object_or_404(SalesInvoice.objects.select_related("counterparty", "journal_entry"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "post":
                posting.post_sales_invoice(inv, request.user)
                messages.success(request, "Проведено.")
            elif action == "unpost":
                posting.unpost_sales_invoice(inv, request.user)
                messages.success(request, "Проведение снято.")
        except ValidationError as e:
            messages.error(request, _validation_messages(e))
        return redirect("accounting:sales_detail", pk=pk)
    lines = inv.lines.select_related("product")
    return render(
        request,
        "accounting/sales_detail.html",
        {"invoice": inv, "lines": lines},
    )


@login_required
def purchase_list(request):
    invoices = PurchaseInvoice.objects.select_related("counterparty").order_by("-date", "-id")
    return render(request, "accounting/purchase_list.html", {"invoices": invoices})


@login_required
def purchase_create(request):
    today = timezone.now().date()
    initial = {
        "number": next_document_number("PI", PurchaseInvoice),
        "date": today,
    }
    if request.method == "POST":
        form = PurchaseInvoiceForm(request.POST)
        if form.is_valid():
            inv = form.save(commit=False)
            inv.created_by = request.user
            inv.save()
            messages.success(request, "Черновик сохранён. Добавьте товары.")
            return redirect("accounting:purchase_detail", pk=inv.pk)
    else:
        form = PurchaseInvoiceForm(initial=initial)
    return render(
        request,
        "accounting/purchase_form.html",
        {"form": form, "title": "Новая закупка", "invoice": None},
    )


@login_required
def purchase_add_line(request, pk):
    """HTMX view для добавления строки в закупку"""
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    
    if request.method == "POST":
        form = PurchaseInvoiceLineForm(request.POST)
        if form.is_valid():
            line = form.save(commit=False)
            line.invoice = invoice
            line.save()
            # Возвращаем обновленный список строк
            lines = invoice.lines.select_related("product")
            return render(request, "accounting/purchase_lines.html", {"lines": lines})
    else:
        form = PurchaseInvoiceLineForm()
    
    return render(request, "accounting/purchase_line_form.html", {"form": form, "invoice": invoice})


@login_required
def purchase_remove_line(request, pk, line_pk):
    """HTMX view для удаления строки из закупки"""
    invoice = get_object_or_404(PurchaseInvoice, pk=pk)
    line = get_object_or_404(PurchaseInvoiceLine, pk=line_pk, invoice=invoice)
    
    if request.method == "DELETE":
        line.delete()
        lines = invoice.lines.select_related("product")
        return render(request, "accounting/purchase_lines.html", {"lines": lines})
    
    return HttpResponse(status=405)


@login_required
def cash_list(request):
    ops = CashOperation.objects.order_by("-date", "-id")
    return render(request, "accounting/cash_list.html", {"operations": ops})


@login_required
def cash_create(request):
    today = timezone.now().date()
    initial = {"number": next_document_number("CO", CashOperation), "date": today}
    if request.method == "POST":
        form = CashOperationForm(request.POST)
        if form.is_valid():
            op = form.save(commit=False)
            op.created_by = request.user
            op.save()
            if "save_post" in request.POST:
                try:
                    posting.post_cash_operation(op, request.user)
                    messages.success(request, "Операция сохранена и проведена.")
                except ValidationError as e:
                    messages.error(request, _validation_messages(e))
            else:
                messages.success(request, "Черновик сохранён.")
            return redirect("accounting:cash_detail", pk=op.pk)
    else:
        form = CashOperationForm(initial=initial)
    return render(request, "accounting/cash_form.html", {"form": form, "title": "Касса / банк"})


@login_required
def cash_detail(request, pk):
    op = get_object_or_404(CashOperation.objects.select_related("journal_entry", "counterparty"), pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "post":
                posting.post_cash_operation(op, request.user)
                messages.success(request, "Проведено.")
            elif action == "unpost":
                posting.unpost_cash_operation(op)
                messages.success(request, "Проведение снято.")
        except ValidationError as e:
            messages.error(request, _validation_messages(e))
        return redirect("accounting:cash_detail", pk=pk)
    return render(request, "accounting/cash_detail.html", {"operation": op})


@login_required
def report_trial_balance(request):
    today = timezone.now().date()
    d_from = _parse_date(request.GET.get("date_from"), today.replace(day=1))
    d_to = _parse_date(request.GET.get("date_to"), today)
    rows = report_svc.trial_balance(d_from, d_to)
    return render(
        request,
        "accounting/report_trial_balance.html",
        {"rows": rows, "date_from": d_from, "date_to": d_to},
    )


@login_required
def report_general_ledger(request):
    today = timezone.now().date()
    d_from = _parse_date(request.GET.get("date_from"), today.replace(day=1))
    d_to = _parse_date(request.GET.get("date_to"), today)
    account_id = request.GET.get("account")
    account = None
    ledger_rows = []
    if account_id:
        account = get_object_or_404(Account, pk=account_id)
        ledger_rows = report_svc.general_ledger(account, d_from, d_to)
    accounts = Account.objects.filter(is_active=True).order_by("code")
    return render(
        request,
        "accounting/report_general_ledger.html",
        {
            "accounts": accounts,
            "account": account,
            "ledger_rows": ledger_rows,
            "date_from": d_from,
            "date_to": d_to,
        },
    )


@login_required
def report_pnl(request):
    today = timezone.now().date()
    d_from = _parse_date(request.GET.get("date_from"), today.replace(day=1))
    d_to = _parse_date(request.GET.get("date_to"), today)
    income, expense, profit = report_svc.profit_and_loss(d_from, d_to)
    return render(
        request,
        "accounting/report_pnl.html",
        {
            "income": income,
            "expense": expense,
            "profit": profit,
            "date_from": d_from,
            "date_to": d_to,
        },
    )


@login_required
def report_balance_sheet(request):
    today = timezone.now().date()
    as_of = _parse_date(request.GET.get("as_of"), today)
    data = report_svc.balance_sheet(as_of)
    return render(
        request,
        "accounting/report_balance_sheet.html",
        {"data": data, "as_of": as_of},
    )


def register(request):
    """Страница регистрации"""
    if request.user.is_authenticated:
        return redirect("accounting:dashboard")
    
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Регистрация успешна! Теперь вы можете войти.")
            return redirect("login")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = RegistrationForm()
    
    return render(request, "accounting/register.html", {"form": form})


@login_required
def users_list(request):
    """Список пользователей"""
    users = User.objects.all().order_by("date_joined")
    context = {
        "users": users,
        "total_users": users.count(),
    }
    return render(request, "accounting/users_list.html", context)


@login_required
def calculator(request):
    """Встроенный бухгалтерский калькулятор"""
    return render(request, "accounting/calculator.html")
