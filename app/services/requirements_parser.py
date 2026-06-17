import re


FIELD_ALIASES = {
    "plan_mode": [
        "plan_mode",
        "mode",
        "режим",
    ],
    "base_table": [
        "base_table",
        "base table",
        "базовая таблица",
        "основная таблица",
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
        "статус",
    ],
    "timestamp": [
        "timestamp",
        "event_time",
        "datetime",
        "дата события",
        "время события",
        "дата",
    ],
    "start_time": [
        "start_time",
        "начало",
        "дата начала",
    ],
    "stop_time": [
        "stop_time",
        "конец",
        "окончание",
        "дата окончания",
    ],
}


VALUE_PATTERN = r"([A-Za-zА-Яа-я0-9_.\-]+)"


def _find_value_for_alias(text: str, alias: str) -> str | None:
    patterns = [
        rf"(?<!\w){re.escape(alias)}(?!\w)\s*=\s*{VALUE_PATTERN}",
        rf"(?<!\w){re.escape(alias)}(?!\w)\s*:\s*{VALUE_PATTERN}",
        (
            rf"(?<!\w){re.escape(alias)}(?!\w)\s+"
            rf"(?:из|from|как|as|бери из|возьми из|используй)\s+"
            rf"{VALUE_PATTERN}"
        ),
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            return match.group(1).strip(" .,;:")

    return None


def _parse_selected_joins(text: str) -> list[dict]:
    joins = []

    pattern = re.compile(
        r"(?:left\s+join|join|джойн|приджойн)\s+"
        r"([A-Za-zА-Яа-я0-9_.\-]+)\.([A-Za-zА-Яа-я0-9_\-]+)"
        r"\s*=\s*"
        r"([A-Za-zА-Яа-я0-9_.\-]+)\.([A-Za-zА-Яа-я0-9_\-]+)",
        flags=re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        joins.append(
            {
                "left_table": match.group(1).strip(),
                "left_key": match.group(2).strip(),
                "right_table": match.group(3).strip(),
                "right_key": match.group(4).strip(),
                "how": "left",
                "source": "user",
            }
        )

    return joins


def _parse_strategy_number(text: str) -> int | None:
    normalized = str(text).strip().lower()

    direct = {
        "1": 1,
        "2": 2,
        "3": 3,
        "первый": 1,
        "первая": 1,
        "вариант 1": 1,
        "первый вариант": 1,
        "второй": 2,
        "вторая": 2,
        "вариант 2": 2,
        "второй вариант": 2,
        "третий": 3,
        "третья": 3,
        "вариант 3": 3,
        "третий вариант": 3,
    }

    if normalized in direct:
        return direct[normalized]

    match = re.search(r"(?:вариант|стратеги[яю])\s*(\d+)", normalized)

    if match:
        return int(match.group(1))

    return None


def parse_user_requirements(user_question: str) -> dict:
    parsed = {}
    text = str(user_question)
    low = text.lower()

    strategy_number = _parse_strategy_number(text)

    if strategy_number is not None:
        parsed["selected_strategy_number"] = strategy_number

    if any(word in low for word in ["concat", "конкат", "сконкат", "каждая таблица", "каждый файл"]):
        parsed["plan_mode"] = "event_tables_concat"
        parsed["activity_source"] = "table_name"

    if any(word in low for word in ["joined", "join", "джойн", "приджойн", "базовая таблица", "основная таблица"]):
        if "plan_mode" not in parsed:
            parsed["plan_mode"] = "joined_table"

    if any(word in low for word in ["activity из имени", "activity из названия", "событие из имени", "событие из названия"]):
        parsed["activity_source"] = "table_name"
        parsed["plan_mode"] = "event_tables_concat"

    for field_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            value = _find_value_for_alias(text, alias)

            if value:
                if field_name == "plan_mode":
                    value_low = value.lower()

                    if value_low in {"concat", "event_tables_concat", "конкат"}:
                        parsed["plan_mode"] = "event_tables_concat"
                        parsed["activity_source"] = "table_name"
                    elif value_low in {"join", "joined", "joined_table", "джойн"}:
                        parsed["plan_mode"] = "joined_table"
                    else:
                        parsed[field_name] = value
                else:
                    parsed[field_name] = value

                break

    selected_joins = _parse_selected_joins(text)

    if selected_joins:
        parsed["selected_joins"] = selected_joins
        parsed.setdefault("plan_mode", "joined_table")

    return parsed
