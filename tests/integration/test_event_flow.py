import pytest
#from src.buttons import button_handler, create_event_button

@pytest.mark.asyncio
async def test_full_event_flow(app, db_path, drafts_db_path):
    # 1. Создаем мероприятие
    # 2. Редактируем его
    # 3. Участвуем
    # 4. Проверяем состояние
    pass