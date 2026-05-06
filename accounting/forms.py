from django import forms
from django.forms import inlineformset_factory

from accounting.models import CashOperation, PurchaseInvoice, PurchaseInvoiceLine, SalesInvoice, SalesInvoiceLine


def _bootstrap_form_controls(form: forms.ModelForm) -> None:
    for name, field in form.fields.items():
        w = field.widget
        if isinstance(w, (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.DateInput)):
            w.attrs.setdefault("class", "form-control")
        elif isinstance(w, forms.Select):
            w.attrs.setdefault("class", "form-select")
        elif isinstance(w, forms.Textarea):
            w.attrs.setdefault("class", "form-control")


class SalesInvoiceForm(forms.ModelForm):
    class Meta:
        model = SalesInvoice
        fields = ["number", "date", "counterparty", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap_form_controls(self)


SalesInvoiceLineFormSet = inlineformset_factory(
    SalesInvoice,
    SalesInvoiceLine,
    fields=["product", "quantity", "unit_price", "unit_cost"],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    widgets={
        "product": forms.Select(attrs={"class": "form-select"}),
        "quantity": forms.NumberInput(attrs={"class": "form-control"}),
        "unit_price": forms.NumberInput(attrs={"class": "form-control"}),
        "unit_cost": forms.NumberInput(attrs={"class": "form-control"}),
    },
)


class PurchaseInvoiceForm(forms.ModelForm):
    class Meta:
        model = PurchaseInvoice
        fields = ["number", "date", "counterparty", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap_form_controls(self)


PurchaseInvoiceLineFormSet = inlineformset_factory(
    PurchaseInvoice,
    PurchaseInvoiceLine,
    fields=["product", "quantity", "unit_cost"],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    widgets={
        "product": forms.Select(attrs={"class": "form-select"}),
        "quantity": forms.NumberInput(attrs={"class": "form-control"}),
        "unit_cost": forms.NumberInput(attrs={"class": "form-control"}),
    },
)


class CashOperationForm(forms.ModelForm):
    class Meta:
        model = CashOperation
        fields = [
            "number",
            "date",
            "kind",
            "cash_account",
            "amount",
            "counterparty",
            "description",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 2, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap_form_controls(self)
