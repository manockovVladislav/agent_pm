import re


FIELD_ALIASES = {
    "base_table": [
        "base_table",
        "base table",
        "базовая таблица",
        "основная таблица",
        "таблица",
    ],
    "case_id": [
        "case_id",
        "case id",
        "кейс",
        "id кейса",
        "идентификатор процесса",
    ],
    "activity": [
        "activity",
        "активность",
        "событие",
        "операция",
        "действие",
    ],
    "timestamp": [
        "timestamp",
        "time",
        "datetime",
        "дата",
        "время",
        "дата события",
        "время события",
    ],
}

CONNECTOR_PATTERN = (
    r"(?:\s*(?:=|:|из|from|бери\s+из|возьми\s+из|используй|использовать|"
    r"брать\s+из|колонка|поле|как|as)\s*)+"
)

VALUE_PATTERN = r"([A-Za-zА-Яа-я0-9_.\-]+)"


def _find_value_for_alias(text: str, alias: str) -> str | None:
    pattern = rf"(?<!\w){re.escape(alias)}(?!\w){CONNECTOR_PATTERN}{VALUE_PATTERN}"
    match = re.search(pattern, text, flags=re.IGNORECASE)

    if not match:
        return None

    return match.group(1).strip(" .,;:")


def parse_user_requirements(user_question: str) -> dict[str, str]:
    """
    Достает из текста явные правки пользователя для join_plan.

    Примеры:
    - case_id бери из application_id
    - activity из operation_name
    - timestamp = created_at
    - base_table customer_events.csv
    """

    parsed = {}
    text = str(user_question)

    for field_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            value = _find_value_for_alias(text, alias)

            if value:
                parsed[field_name] = value
                break

    return parsed
