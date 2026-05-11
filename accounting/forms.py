from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils.text import slugify
from uuid import uuid4

from accounting.models import (
    CashOperation,
    Counterparty,
    CounterpartyKind,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from inventory.models import Category, Product, Supplier


def _bootstrap_form_controls(form: forms.ModelForm) -> None:
    for name, field in form.fields.items():
        w = field.widget
        if isinstance(w, (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.DateInput)):
            w.attrs.setdefault("class", "form-control")
        elif isinstance(w, forms.Select):
            w.attrs.setdefault("class", "form-select")
        elif isinstance(w, forms.Textarea):
            w.attrs.setdefault("class", "form-control")


def _ensure_default_customers() -> None:
    default_customers = [
        "ИП Ернар",
        "ИП АЛИМ",
        "ИП Хусан",
        "ИП",
    ]
    for name in default_customers:
        Counterparty.objects.get_or_create(
            name=name,
            kind=CounterpartyKind.CUSTOMER,
        )


class SalesInvoiceForm(forms.ModelForm):
    counterparty = forms.ModelChoiceField(
        queryset=Counterparty.objects.none(),
        required=False,
        label="Покупатель",
        widget=forms.Select(attrs={"class": "form-select"}),
        empty_label="Выберите покупателя",
        help_text="Или введите нового покупателя вручную.",
    )
    counterparty_name = forms.CharField(
        required=False,
        label="Новый покупатель",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Укажите нового покупателя, если его нет в списке",
            }
        ),
        help_text="Если покупателя нет в списке, введите его имя вручную.",
    )

    class Meta:
        model = SalesInvoice
        fields = ["number", "date", "counterparty", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 2, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        _ensure_default_customers()
        super().__init__(*args, **kwargs)
        _bootstrap_form_controls(self)
        # Ограничить контрагентов покупателями
        self.fields["counterparty"].queryset = Counterparty.objects.filter(
            kind__in=["customer", "both"]
        )
        self.fields["counterparty"].required = False
        self.fields["counterparty"].empty_label = "Выберите покупателя"
        self.fields["counterparty"].help_text = "Или введите нового покупателя вручную."
        if not self.fields["counterparty"].queryset.exists():
            self.fields["counterparty"].help_text = (
                "Сначала добавьте контрагента с типом Клиент или Клиент и поставщик "
                "или введите нового покупателя."
            )

    def clean(self):
        cleaned_data = super().clean()
        counterparty = cleaned_data.get("counterparty")
        counterparty_name = cleaned_data.get("counterparty_name")

        if not counterparty and counterparty_name:
            counterparty, _ = Counterparty.objects.get_or_create(
                name=counterparty_name,
                defaults={"kind": CounterpartyKind.CUSTOMER},
            )
            cleaned_data["counterparty"] = counterparty
            if "counterparty" in self._errors:
                del self._errors["counterparty"]

        if not counterparty and not counterparty_name:
            raise forms.ValidationError(
                "Выберите покупателя из списка или введите его имя."
            )
        return cleaned_data


class SalesInvoiceLineForm(forms.ModelForm):
    product_name = forms.CharField(
        required=False,
        label="Товар (введите вручную)",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Введите наименование товара",
            }
        ),
        help_text="Если товара нет в списке, введите его название вручную.",
    )

    class Meta:
        model = SalesInvoiceLine
        fields = ["product", "quantity", "unit_price", "unit_cost"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control"}),
            "unit_cost": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap_form_controls(self)
        self.fields["product"].required = False
        self.fields["product"].help_text = (
            "Выберите товар из списка или введите название вручную."
        )

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        product_name = cleaned_data.get("product_name")
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")
        unit_cost = cleaned_data.get("unit_cost")

        if not product and not product_name:
            raise forms.ValidationError(
                "Выберите товар из списка или введите его наименование."
            )
        if quantity is None or quantity <= 0:
            raise forms.ValidationError("Количество должно быть больше нуля.")
        if unit_price is None or unit_price <= 0:
            raise forms.ValidationError("Цена продажи должна быть больше нуля.")
        if unit_cost is None or unit_cost < 0:
            raise forms.ValidationError("Себестоимость не должна быть отрицательной.")
        return cleaned_data

    def save(self, commit=True):
        product = self.cleaned_data.get("product")
        product_name = self.cleaned_data.get("product_name")
        if not product and product_name:
            product = self._get_or_create_free_product(
                product_name,
                quantity=self.cleaned_data.get("quantity") or 0,
                price=self.cleaned_data.get("unit_price") or 0,
            )
        self.instance.product = product
        return super().save(commit=commit)

    def _get_or_create_free_product(self, name: str, quantity: int, price):
        category, _ = Category.objects.get_or_create(name="Разное")
        supplier, _ = Supplier.objects.get_or_create(
            name="Неизвестный поставщик",
            defaults={
                "contact_person": "",
                "phone": "",
                "email": "",
                "address": "Не задано",
            },
        )
        article_base = slugify(name) or "product"
        article = article_base
        if Product.objects.filter(article=article).exists():
            article = f"{article_base}-{uuid4().hex[:6]}"
        product, created = Product.objects.get_or_create(
            name=name,
            defaults={
                "article": article,
                "category": category,
                "supplier": supplier,
                "description": "Введено вручную",
                "price": price,
                "current_quantity": quantity,
                "min_threshold": 0,
            },
        )
        if product.current_quantity < quantity:
            product.current_quantity = quantity
            product.save(update_fields=["current_quantity"])
        return product


SalesInvoiceLineFormSet = inlineformset_factory(
    SalesInvoice,
    SalesInvoiceLine,
    form=SalesInvoiceLineForm,
    fields=["product", "quantity", "unit_price", "unit_cost"],
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
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
