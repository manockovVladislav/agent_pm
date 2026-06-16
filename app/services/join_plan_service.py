def _normalize_column_name(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _resolve_column(column_name: str | None, available_columns: list[str]) -> str | None:
    if not column_name:
        return None

    normalized_target = _normalize_column_name(column_name)

    for column in available_columns:
        if _normalize_column_name(column) == normalized_target:
            return column

    return column_name


def _pick_column(
    values: list[str],
    preferred_names: list[str],
    used_columns: set[str] | None = None,
) -> str | None:
    if not values:
        return None

    used_columns = used_columns or set()

    available = [
        value for value in values
        if value not in used_columns
    ]

    if not available:
        return None

    normalized_to_original = {
        _normalize_column_name(value): value
        for value in available
    }

    for preferred_name in preferred_names:
        normalized_name = _normalize_column_name(preferred_name)

        if normalized_name in normalized_to_original:
            return normalized_to_original[normalized_name]

    for value in available:
        normalized_value = _normalize_column_name(value)

        if any(token in normalized_value for token in preferred_names):
            return value

    return available[0]


def _score_base_table(table_info: dict) -> int:
    score = 0

    if table_info.get("candidate_case_id_columns"):
        score += 3

    if table_info.get("candidate_activity_columns"):
        score += 4

    if table_info.get("candidate_timestamp_columns"):
        score += 4

    score += min(table_info.get("rows", 0) // 1000, 5)

    return score


def choose_base_table(tables_info: dict) -> str | None:
    """
    Выбирает базовую таблицу для event log.

    Идеально, если в таблице есть:
    - case_id
    - activity
    - timestamp
    """

    candidates = []

    for table_name, info in tables_info.items():
        if "error" in info:
            continue

        score = _score_base_table(info)

        candidates.append(
            {
                "table_name": table_name,
                "score": score,
            }
        )

    if not candidates:
        return None

    candidates = sorted(
        candidates,
        key=lambda item: item["score"],
        reverse=True,
    )

    return candidates[0]["table_name"]


def build_join_plan(
    tables_info: dict,
    relationships: list[dict],
    user_requirements: dict | None = None,
) -> dict:
    """
    Строит предварительный join_plan.

    Пока это эвристика без Qwen:
    - выбирает базовую таблицу
    - выбирает case_id/activity/timestamp
    - добавляет возможные left join по найденным связям
    """

    user_requirements = user_requirements or {}
    base_table = user_requirements.get("base_table") or choose_base_table(tables_info)

    if base_table is None:
        return {
            "status": "error",
            "error": "Не удалось выбрать базовую таблицу для event log.",
        }

    if base_table not in tables_info:
        return {
            "status": "error",
            "error": f"Базовая таблица не найдена: {base_table}",
            "base_table": base_table,
        }

    base_info = tables_info[base_table]
    base_columns = base_info.get("columns", [])

    used_columns = set()

    case_id_col = (
        _resolve_column(user_requirements.get("case_id"), base_columns)
        or _pick_column(
            base_info.get("candidate_case_id_columns", []),
            preferred_names=["case_id", "caseid", "request_id", "application_id", "id"],
            used_columns=used_columns,
        )
    )

    if case_id_col:
        used_columns.add(case_id_col)

    activity_col = (
        _resolve_column(user_requirements.get("activity"), base_columns)
        or _pick_column(
            base_info.get("candidate_activity_columns", []),
            preferred_names=["activity", "event", "event_name", "status", "operation"],
            used_columns=used_columns,
        )
    )

    if activity_col:
        used_columns.add(activity_col)

    timestamp_col = (
        _resolve_column(user_requirements.get("timestamp"), base_columns)
        or _pick_column(
            base_info.get("candidate_timestamp_columns", []),
            preferred_names=["timestamp", "event_time", "created_at", "updated_at", "date"],
            used_columns=used_columns,
        )
    )

    requested_columns = {
        "case_id": case_id_col if user_requirements.get("case_id") else None,
        "activity": activity_col if user_requirements.get("activity") else None,
        "timestamp": timestamp_col if user_requirements.get("timestamp") else None,
    }

    missing_requested_columns = [
        f"{role}={column}"
        for role, column in requested_columns.items()
        if column and column not in base_columns
    ]

    if missing_requested_columns:
        return {
            "status": "error",
            "error": (
                "В базовой таблице нет колонок, указанных пользователем: "
                f"{missing_requested_columns}"
            ),
            "base_table": base_table,
            "available_columns": base_columns,
        }

    if not case_id_col or not activity_col or not timestamp_col:
        return {
            "status": "error",
            "error": (
                "Не удалось автоматически определить обязательные поля "
                "case_id/activity/timestamp."
            ),
            "base_table": base_table,
            "case_id": case_id_col,
            "activity": activity_col,
            "timestamp": timestamp_col,
        }

    joins = []
    used_right_tables = set()

    for rel in relationships:
        left_table = rel["left_table"]
        right_table = rel["right_table"]

        if left_table == base_table and right_table not in used_right_tables:
            joins.append(
                {
                    "right_table": right_table,
                    "left_key": rel["left_column"],
                    "right_key": rel["right_column"],
                    "how": "left",
                    "relationship_score": rel["score"],
                }
            )
            used_right_tables.add(right_table)

        elif right_table == base_table and left_table not in used_right_tables:
            joins.append(
                {
                    "right_table": left_table,
                    "left_key": rel["right_column"],
                    "right_key": rel["left_column"],
                    "how": "left",
                    "relationship_score": rel["score"],
                }
            )
            used_right_tables.add(left_table)

    join_plan = {
        "status": "ok",
        "base_table": base_table,
        "event_log_columns": {
            "case_id": case_id_col,
            "activity": activity_col,
            "timestamp": timestamp_col,
        },
        "joins": joins,
        "output_columns": {
            "case_id": case_id_col,
            "activity": activity_col,
            "timestamp": timestamp_col,
        },
    }

    return join_plan
