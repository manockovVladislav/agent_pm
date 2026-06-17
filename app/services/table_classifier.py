def _safe_div(a: float, b: float) -> float:
    if not b:
        return 0.0

    return a / b


def _best_profile(table_info: dict, columns: list[str]) -> tuple[str | None, dict]:
    profiles = table_info.get("column_profiles") or {}

    for column in columns:
        if column in profiles:
            return column, profiles[column]

    return None, {}


def classify_tables(tables_info: dict) -> dict:
    classifications = {}

    for table_name, table_info in tables_info.items():
        if "error" in table_info:
            classifications[table_name] = {
                "role": "noise_table",
                "confidence": 0.0,
                "reason": "таблица не прочитана",
                "signals": {},
            }
            continue

        rows = int(table_info.get("rows") or 0)
        columns = table_info.get("columns") or []
        case_candidates = table_info.get("candidate_case_id_columns") or []
        activity_candidates = table_info.get("candidate_activity_columns") or []
        time_candidates = table_info.get("candidate_timestamp_columns") or []

        case_column, case_profile = _best_profile(table_info, case_candidates)
        case_unique = int(case_profile.get("unique_count") or 0)
        events_per_case = round(_safe_div(rows, case_unique), 2)

        score_event = 0
        score_lifecycle = 0
        score_attribute = 0
        score_bridge = 0

        if case_candidates:
            score_event += 25
            score_lifecycle += 25
            score_attribute += 20
            score_bridge += 20

        if activity_candidates:
            score_event += 30

        if time_candidates:
            score_event += 25
            score_lifecycle += min(len(time_candidates) * 12, 35)

        if len(case_candidates) >= 2:
            score_bridge += 25

        if rows > 0 and case_unique > 0:
            if events_per_case >= 2:
                score_event += 20
            elif 0.8 <= events_per_case <= 1.2:
                score_attribute += 25

        if activity_candidates and time_candidates and events_per_case >= 1.5:
            role = "event_table"
            score = score_event
            reason = "есть case_id, activity/status, timestamp и несколько событий на case"
        elif case_candidates and len(time_candidates) >= 2 and not activity_candidates:
            role = "lifecycle_table"
            score = score_lifecycle
            reason = "есть case_id и несколько дат, но нет явного activity"
        elif case_candidates and len(case_candidates) >= 2 and not time_candidates:
            role = "bridge_table"
            score = score_bridge
            reason = "похожа на таблицу связей между идентификаторами"
        elif case_candidates and events_per_case <= 1.2:
            role = "attribute_table"
            score = score_attribute
            reason = "похожа на таблицу атрибутов: примерно одна строка на case"
        else:
            role = "noise_table"
            score = max(score_event, score_lifecycle, score_attribute, score_bridge)
            reason = "недостаточно признаков event log или справочника"

        classifications[table_name] = {
            "role": role,
            "confidence": round(min(score / 100, 1.0), 2),
            "reason": reason,
            "signals": {
                "rows": rows,
                "columns": len(columns),
                "case_column": case_column,
                "case_unique": case_unique,
                "events_per_case": events_per_case,
                "case_candidates": case_candidates[:5],
                "activity_candidates": activity_candidates[:5],
                "timestamp_candidates": time_candidates[:5],
            },
        }

    return classifications
