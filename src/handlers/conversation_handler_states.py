from enum import Enum

class States(Enum):
    """
    Перечисление состояний ConversationHandler для создания мероприятий.
    Каждое состояние соответствует этапу ввода данных.
    """
    SET_DESCRIPTION = 1  # Ожидание ввода описания мероприятия
    SET_DATE = 2         # Ожидание ввода даты
    SET_TIME = 3         # Ожидание ввода времени
    SET_LIMIT = 4        # Ожидание ввода лимита участников

class EditStates(Enum):
    """
    Перечисление состояний ConversationHandler для редактирования мероприятий.
    """
    EDIT_EVENT = 10       # Меню выбора параметра для редактирования
    EDIT_DESCRIPTION = 11 # Ожидание ввода нового описания
    EDIT_DATE = 12        # Ожидание ввода новой даты
    EDIT_TIME = 13        # Ожидание ввода нового времени
    EDIT_LIMIT = 14       # Ожидание ввода нового лимита участников

# Алиасы для удобства использования
(
    SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT,
    EDIT_EVENT, EDIT_DESCRIPTION, EDIT_DATE, EDIT_TIME, EDIT_LIMIT
) = (
    States.SET_DESCRIPTION, States.SET_DATE, States.SET_TIME, States.SET_LIMIT,
    EditStates.EDIT_EVENT, EditStates.EDIT_DESCRIPTION, 
    EditStates.EDIT_DATE, EditStates.EDIT_TIME, EditStates.EDIT_LIMIT
)