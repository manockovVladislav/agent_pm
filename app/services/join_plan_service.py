from pathlib import Path


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
    candidates = []

    for table_name, info in tables_info.items():
        if "error" in info:
            continue

        candidates.append(
            {
                "table_name": table_name,
                "score": _score_base_table(info),
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


def _table_name_to_activity(table_name: str) -> str:
    return Path(table_name).stem


def _is_event_tables_concat_mode(user_requirements: dict) -> bool:
    plan_mode = str(user_requirements.get("plan_mode", "")).strip().lower()
    activity_source = str(user_requirements.get("activity_source", "")).strip().lower()

    return (
        plan_mode in {"event_tables_concat", "events_concat", "concat"}
        or activity_source in {"table_name", "file_name", "filename"}
    )


def _pick_event_source_column(
    table_info: dict,
    role: str,
    requested_column: str | None,
    preferred_names: list[str],
    used_columns: set[str] | None = None,
) -> tuple[str | None, str | None]:
    columns = table_info.get("columns", [])

    if requested_column:
        resolved_column = _resolve_column(requested_column, columns)

        if resolved_column in columns:
            return resolved_column, None

        warning = (
            f"{table_info.get('file_name')}: колонка {role}={requested_column} "
            "не найдена, использован автоматический подбор."
        )
    else:
        warning = None

    candidate_key = {
        "case_id": "candidate_case_id_columns",
        "timestamp": "candidate_timestamp_columns",
        "start_time": "candidate_timestamp_columns",
        "stop_time": "candidate_timestamp_columns",
    }[role]

    return (
        _pick_column(
            table_info.get(candidate_key, []),
            preferred_names=preferred_names,
            used_columns=used_columns,
        ),
        warning,
    )


def build_event_tables_concat_plan(
    tables_info: dict,
    user_requirements: dict | None = None,
) -> dict:
    user_requirements = user_requirements or {}
    event_sources = []
    warnings = []
    errors = []
    requested_tables = user_requirements.get("selected_tables")

    if requested_tables:
        requested_tables = set(requested_tables)

    for table_name, table_info in tables_info.items():
        if requested_tables and table_name not in requested_tables:
            continue

        if "error" in table_info:
            warnings.append(f"{table_name}: таблица пропущена, ошибка чтения.")
            continue

        used_columns = set()

        case_id_col, warning = _pick_event_source_column(
            table_info=table_info,
            role="case_id",
            requested_column=user_requirements.get("case_id"),
            preferred_names=[
                "case_id",
                "caseid",
                "request_id",
                "application_id",
                "app_id",
                "deal_id",
                "doc_id",
                "id",
            ],
            used_columns=used_columns,
        )

        if warning:
            warnings.append(warning)

        if case_id_col:
            used_columns.add(case_id_col)

        timestamp_col, warning = _pick_event_source_column(
            table_info=table_info,
            role="timestamp",
            requested_column=user_requirements.get("timestamp"),
            preferred_names=[
                "timestamp",
                "event_time",
                "created_at",
                "updated_at",
                "operation_date",
                "date",
                "time",
                "start_time",
                "stop_time",
            ],
            used_columns=used_columns,
        )

        if warning:
            warnings.append(warning)

        if timestamp_col:
            used_columns.add(timestamp_col)

        start_time_col, _ = _pick_event_source_column(
            table_info=table_info,
            role="start_time",
            requested_column=user_requirements.get("start_time"),
            preferred_names=[
                "start_time",
                "started_at",
                "created_at",
                "timestamp",
                "date",
            ],
            used_columns=None,
        )

        stop_time_col, _ = _pick_event_source_column(
            table_info=table_info,
            role="stop_time",
            requested_column=user_requirements.get("stop_time"),
            preferred_names=[
                "stop_time",
                "finished_at",
                "ended_at",
                "updated_at",
                "timestamp",
                "date",
            ],
            used_columns=None,
        )

        if case_id_col and timestamp_col:
            event_sources.append(
                {
                    "file": table_name,
                    "activity": _table_name_to_activity(table_name),
                    "activity_source": "table_name",
                    "case_id": case_id_col,
                    "timestamp": timestamp_col,
                    "start_time": start_time_col,
                    "stop_time": stop_time_col,
                    "rows": table_info.get("rows"),
                }
            )
        else:
            warnings.append(
                f"{table_name}: пропущена для concat, "
                f"case_id={case_id_col}, timestamp={timestamp_col}"
            )

    if not event_sources:
        return {
            "status": "error",
            "mode": "event_tables_concat",
            "error": "Не найдено таблиц для concat с case_id и timestamp.",
            "event_sources": [],
            "warnings": warnings,
            "errors": errors,
            "joins": [],
        }

    return {
        "status": "ok",
        "mode": "event_tables_concat",
        "activity_source": "table_name",
        "base_table": None,
        "event_sources": event_sources,
        "event_log_columns": {
            "case_id": "case_id",
            "activity": "activity",
            "activity_id": "activity_id",
            "timestamp": "timestamp",
            "start_time": "start_time",
            "stop_time": "stop_time",
        },
        "joins": [],
        "warnings": warnings,
        "errors": errors,
        "output_columns": {
            "case_id": "case_id",
            "activity": "activity",
            "activity_id": "activity_id",
            "timestamp": "timestamp",
            "start_time": "start_time",
            "stop_time": "stop_time",
            "source_table": "source_table",
        },
    }


def _build_user_selected_joins(
    base_table: str,
    user_requirements: dict,
) -> tuple[list[dict], list[str]]:
    joins = []
    warnings = []
    selected_joins = user_requirements.get("selected_joins") or []

    for selected_join in selected_joins:
        left_table = selected_join.get("left_table")
        right_table = selected_join.get("right_table")
        left_key = selected_join.get("left_key")
        right_key = selected_join.get("right_key")

        if left_table == base_table:
            joins.append(
                {
                    "right_table": right_table,
                    "left_key": left_key,
                    "right_key": right_key,
                    "how": selected_join.get("how", "left"),
                    "source": "user",
                }
            )
        elif right_table == base_table:
            joins.append(
                {
                    "right_table": left_table,
                    "left_key": right_key,
                    "right_key": left_key,
                    "how": selected_join.get("how", "left"),
                    "source": "user",
                }
            )
        else:
            warnings.append(
                "Join пропущен, потому что ни одна из таблиц не является "
                f"базовой: {left_table} <-> {right_table}"
            )

    if not joins:
        warnings.append(
            "Автоматические join не применены. "
            "Найденные связи используются только как подсказки. "
            "Чтобы добавить join, напиши явно: "
            "`join table1.xlsx.id = table2.xlsx.id`."
        )

    return joins, warnings


def build_join_plan(
    tables_info: dict,
    relationships: list[dict],
    user_requirements: dict | None = None,
) -> dict:
    user_requirements = user_requirements or {}

    if _is_event_tables_concat_mode(user_requirements):
        return build_event_tables_concat_plan(
            tables_info=tables_info,
            user_requirements=user_requirements,
        )

    base_table = user_requirements.get("base_table") or choose_base_table(tables_info)

    if base_table is None:
        return {
            "status": "error",
            "mode": "joined_table",
            "error": "Не удалось выбрать базовую таблицу для event log.",
        }

    if base_table not in tables_info:
        return {
            "status": "error",
            "mode": "joined_table",
            "error": f"Базовая таблица не найдена: {base_table}",
            "base_table": base_table,
            "available_tables": list(tables_info.keys()),
        }

    base_info = tables_info[base_table]

    if "error" in base_info:
        return {
            "status": "error",
            "mode": "joined_table",
            "error": f"Ошибка чтения базовой таблицы {base_table}: {base_info['error']}",
            "base_table": base_table,
        }

    base_columns = base_info.get("columns", [])
    used_columns = set()

    case_id_col = (
        _resolve_column(user_requirements.get("case_id"), base_columns)
        or _pick_column(
            base_info.get("candidate_case_id_columns", []),
            preferred_names=[
                "case_id",
                "caseid",
                "request_id",
                "application_id",
                "deal_id",
                "doc_id",
                "id",
            ],
            used_columns=used_columns,
        )
    )

    if case_id_col:
        used_columns.add(case_id_col)

    activity_col = (
        _resolve_column(user_requirements.get("activity"), base_columns)
        or _pick_column(
            base_info.get("candidate_activity_columns", []),
            preferred_names=[
                "activity",
                "event",
                "event_name",
                "status",
                "status_name",
                "operation",
                "operation_name",
                "opname",
                "stage",
            ],
            used_columns=used_columns,
        )
    )

    if activity_col:
        used_columns.add(activity_col)

    timestamp_col = (
        _resolve_column(user_requirements.get("timestamp"), base_columns)
        or _pick_column(
            base_info.get("candidate_timestamp_columns", []),
            preferred_names=[
                "timestamp",
                "event_time",
                "created_at",
                "updated_at",
                "operation_date",
                "date",
                "time",
            ],
            used_columns=used_columns,
        )
    )

    requested_columns = {
        "case_id": user_requirements.get("case_id"),
        "activity": user_requirements.get("activity"),
        "timestamp": user_requirements.get("timestamp"),
    }
    missing_requested_columns = []

    for role, requested in requested_columns.items():
        if not requested:
            continue

        resolved = _resolve_column(requested, base_columns)

        if resolved not in base_columns:
            missing_requested_columns.append(f"{role}={requested}")

    if missing_requested_columns:
        return {
            "status": "error",
            "mode": "joined_table",
            "error": (
                "В базовой таблице нет колонок, указанных пользователем: "
                f"{missing_requested_columns}"
            ),
            "base_table": base_table,
            "available_columns": base_columns,
        }

    missing_roles = []

    if not case_id_col:
        missing_roles.append("case_id")

    if not activity_col:
        missing_roles.append("activity")

    if not timestamp_col:
        missing_roles.append("timestamp")

    if missing_roles:
        return {
            "status": "error",
            "mode": "joined_table",
            "error": (
                "Не удалось определить обязательные поля: "
                f"{missing_roles}"
            ),
            "base_table": base_table,
            "case_id": case_id_col,
            "activity": activity_col,
            "timestamp": timestamp_col,
            "available_columns": base_columns,
        }

    joins, warnings = _build_user_selected_joins(
        base_table=base_table,
        user_requirements=user_requirements,
    )

    return {
        "status": "ok",
        "mode": "joined_table",
        "base_table": base_table,
        "event_log_columns": {
            "case_id": case_id_col,
            "activity": activity_col,
            "timestamp": timestamp_col,
        },
        "joins": joins,
        "warnings": warnings,
        "errors": [],
        "output_columns": {
            "case_id": case_id_col,
            "activity": activity_col,
            "timestamp": timestamp_col,
        },
    }
