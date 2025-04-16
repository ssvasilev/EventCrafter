from src.event.edit.update_event_field import update_event_field
from src.utils.show_input_error import show_input_error


async def update_participant_limit(update, context, draft, value):
    """Обновляет лимит участников с унифицированным выводом ошибок"""
    try:
        limit = int(value)
        if limit < 0:
            raise ValueError
        await update_event_field(
            context, draft,
            "participant_limit",
            limit if limit != 0 else None
        )
    except ValueError:
        await show_input_error(
            update, context,
            "❌ Лимит должен быть целым числом ≥ 0 (0 - без лимита)"
        )