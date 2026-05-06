from django.urls import path

from accounting import views

app_name = "accounting"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/", views.account_list, name="account_list"),
    path("journal/", views.journal_list, name="journal_list"),
    path("journal/<int:pk>/", views.journal_detail, name="journal_detail"),
    path("sales/", views.sales_list, name="sales_list"),
    path("sales/new/", views.sales_create, name="sales_create"),
    path("sales/<int:pk>/", views.sales_detail, name="sales_detail"),
    path("purchases/", views.purchase_list, name="purchase_list"),
    path("purchases/new/", views.purchase_create, name="purchase_create"),
    path("purchases/<int:pk>/", views.purchase_detail, name="purchase_detail"),
    path("cash/", views.cash_list, name="cash_list"),
    path("cash/new/", views.cash_create, name="cash_create"),
    path("cash/<int:pk>/", views.cash_detail, name="cash_detail"),
    path("reports/trial-balance/", views.report_trial_balance, name="report_trial_balance"),
    path("reports/general-ledger/", views.report_general_ledger, name="report_general_ledger"),
    path("reports/pnl/", views.report_pnl, name="report_pnl"),
    path("reports/balance-sheet/", views.report_balance_sheet, name="report_balance_sheet"),
]
