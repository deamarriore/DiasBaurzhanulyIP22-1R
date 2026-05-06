from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from accounting.models import (
    Account,
    CashOperation,
    Counterparty,
    FiscalPeriod,
    JournalEntry,
    JournalLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from accounting.services import posting


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2
    fields = ("account", "debit", "credit", "counterparty", "description", "sort_order")
    ordering = ("sort_order", "id")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "description", "is_posted", "created_by", "balanced_display")
    list_filter = ("is_posted", "date")
    search_fields = ("number", "description")
    readonly_fields = ("created_at",)
    inlines = [JournalLineInline]

    def balanced_display(self, obj):
        if not obj.pk:
            return "—"
        ok = obj.is_balanced()
        return format_html('<span style="color:{};">{}</span>', "green" if ok else "red", "Да" if ok else "Нет")

    balanced_display.short_description = "Баланс"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        obj.refresh_from_db()
        if obj.lines.exists() and not obj.is_balanced():
            messages.warning(request, "Проводка не сбалансирована (дебет ≠ кредит).")

    actions = ["action_unpost_delete_lines"]

    @admin.action(description="Снять проведение (удалить строки проводки)")
    def action_unpost_delete_lines(self, request, queryset):
        deleted = 0
        for entry in queryset:
            if SalesInvoice.objects.filter(journal_entry=entry).exists():
                messages.error(request, f"{entry.number}: сначала отмените документ реализации.")
                continue
            if PurchaseInvoice.objects.filter(journal_entry=entry).exists():
                messages.error(request, f"{entry.number}: сначала отмените документ закупки.")
                continue
            if CashOperation.objects.filter(journal_entry=entry).exists():
                messages.error(request, f"{entry.number}: сначала отмените кассовый документ.")
                continue
            entry.lines.all().delete()
            entry.delete()
            deleted += 1
        if deleted:
            messages.success(request, f"Удалено ручных проводок: {deleted}.")


class SalesLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 1
    autocomplete_fields = ("product",)


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "counterparty", "is_posted", "created_by")
    list_filter = ("is_posted", "date")
    search_fields = ("number", "counterparty__name")
    readonly_fields = ("journal_entry", "is_posted", "created_at", "created_by")
    inlines = [SalesLineInline]
    autocomplete_fields = ("counterparty",)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_posted:
            ro.extend(["number", "date", "counterparty", "note"])
        return ro

    def get_inline_instances(self, request, obj=None):
        if obj and obj.is_posted:
            return []
        return super().get_inline_instances(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    actions = ["action_post", "action_unpost"]

    @admin.action(description="Провести (проводки + склад)")
    def action_post(self, request, queryset):
        for inv in queryset:
            try:
                posting.post_sales_invoice(inv, request.user)
                messages.success(request, f"{inv.number}: проведено.")
            except ValidationError as e:
                messages.error(request, f"{inv.number}: {e}")

    @admin.action(description="Отменить проведение")
    def action_unpost(self, request, queryset):
        for inv in queryset:
            try:
                posting.unpost_sales_invoice(inv, request.user)
                messages.success(request, f"{inv.number}: снято.")
            except ValidationError as e:
                messages.error(request, f"{inv.number}: {e}")


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseInvoiceLine
    extra = 1
    autocomplete_fields = ("product",)


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "counterparty", "is_posted", "created_by")
    list_filter = ("is_posted", "date")
    search_fields = ("number", "counterparty__name")
    readonly_fields = ("journal_entry", "is_posted", "created_at", "created_by")
    inlines = [PurchaseLineInline]
    autocomplete_fields = ("counterparty",)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_posted:
            ro.extend(["number", "date", "counterparty", "note"])
        return ro

    def get_inline_instances(self, request, obj=None):
        if obj and obj.is_posted:
            return []
        return super().get_inline_instances(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    actions = ["action_post", "action_unpost"]

    @admin.action(description="Провести (проводки + склад)")
    def action_post(self, request, queryset):
        for inv in queryset:
            try:
                posting.post_purchase_invoice(inv, request.user)
                messages.success(request, f"{inv.number}: проведено.")
            except ValidationError as e:
                messages.error(request, f"{inv.number}: {e}")

    @admin.action(description="Отменить проведение")
    def action_unpost(self, request, queryset):
        for inv in queryset:
            try:
                posting.unpost_purchase_invoice(inv, request.user)
                messages.success(request, f"{inv.number}: снято.")
            except ValidationError as e:
                messages.error(request, f"{inv.number}: {e}")


@admin.register(CashOperation)
class CashOperationAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "kind", "cash_account", "amount", "is_posted")
    list_filter = ("is_posted", "kind", "cash_account")
    search_fields = ("number", "description")
    readonly_fields = ("journal_entry", "is_posted", "created_at", "created_by")
    autocomplete_fields = ("counterparty",)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_posted:
            ro.extend(
                [
                    "number",
                    "date",
                    "kind",
                    "cash_account",
                    "amount",
                    "counterparty",
                    "description",
                ]
            )
        return ro

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    actions = ["action_post", "action_unpost"]

    @admin.action(description="Провести")
    def action_post(self, request, queryset):
        for op in queryset:
            try:
                posting.post_cash_operation(op, request.user)
                messages.success(request, f"{op.number}: проведено.")
            except ValidationError as e:
                messages.error(request, f"{op.number}: {e}")

    @admin.action(description="Отменить проведение")
    def action_unpost(self, request, queryset):
        for op in queryset:
            try:
                posting.unpost_cash_operation(op)
                messages.success(request, f"{op.number}: снято.")
            except ValidationError as e:
                messages.error(request, f"{op.number}: {e}")


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "is_active")
    list_filter = ("account_type", "is_active")
    search_fields = ("code", "name")


@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "bin_optional", "phone")
    list_filter = ("kind",)
    search_fields = ("name", "bin_optional")


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "is_closed")
