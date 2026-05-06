"""Вспомогательные функции UI/номеров документов (демо)."""


def next_document_number(prefix: str, model) -> str:
    """Номер вида SI-5 по числу записей (упрощённо)."""
    return f"{prefix}-{model.objects.count() + 1}"
