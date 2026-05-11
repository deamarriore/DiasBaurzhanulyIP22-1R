from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

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
        # Ограничить контрагентов покупателями
        self.fields['counterparty'].queryset = self.fields['counterparty'].queryset.filter(
            kind__in=['customer', 'both']
        )
        self.fields['counterparty'].empty_label = 'Выберите покупателя'
        if not self.fields['counterparty'].queryset.exists():
            self.fields['counterparty'].help_text = 'Сначала добавьте контрагента с типом Клиент или Клиент и поставщик.'


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
        # Ограничить контрагентов поставщиками
        self.fields['counterparty'].queryset = self.fields['counterparty'].queryset.filter(
            kind__in=['supplier', 'both']
        )
        self.fields['counterparty'].empty_label = 'Выберите поставщика'
        if not self.fields['counterparty'].queryset.exists():
            self.fields['counterparty'].help_text = 'Сначала добавьте контрагента с типом Поставщик или Клиент и поставщик.'


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
        # Сделать counterparty обязательным для определенных типов
        if self.instance and self.instance.kind in ['customer_receipt', 'supplier_payment']:
            self.fields['counterparty'].required = True
            if self.instance.kind == 'customer_receipt':
                self.fields['counterparty'].queryset = self.fields['counterparty'].queryset.filter(
                    kind__in=['customer', 'both']
                )
            elif self.instance.kind == 'supplier_payment':
                self.fields['counterparty'].queryset = self.fields['counterparty'].queryset.filter(
                    kind__in=['supplier', 'both']
                )
        else:
            self.fields['counterparty'].required = False


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(max_length=30, required=False, label="Имя")
    last_name = forms.CharField(max_length=150, required=False, label="Фамилия")

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")


class PurchaseInvoiceLineForm(forms.ModelForm):
    """Форма для одной строки закупки с HTMX"""
    class Meta:
        model = PurchaseInvoiceLine
        fields = ["product", "quantity", "unit_cost"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "unit_cost": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap_form_controls(self)

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует")
        return email
