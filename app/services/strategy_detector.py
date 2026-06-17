from pathlib import Path


CASE_ID_PREFERRED = [
    "case_id",
    "caseid",
    "application_id",
    "request_id",
    "deal_id",
    "doc_id",
    "document_id",
    "claim_id",
    "process_id",
    "id",
]

ACTIVITY_PREFERRED = [
    "activity",
    "event",
    "event_name",
    "status",
    "status_name",
    "operation",
    "operation_name",
    "opname",
    "stage",
    "step",
    "action",
]

TIME_PREFERRED = [
    "timestamp",
    "event_time",
    "created_at",
    "updated_at",
    "operation_date",
    "date",
    "time",
    "start_time",
    "created",
]


def _norm(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _pick_best_column(
    columns: list[str],
    candidates: list[str],
    preferred: list[str],
    used: set[str] | None = None,
) -> str | None:
    used = used or set()

    available_candidates = [
        col for col in candidates
        if col in columns and col not in used
    ]

    if not available_candidates:
        return None

    normalized_map = {
        _norm(col): col
        for col in available_candidates
    }

    for name in preferred:
        if _norm(name) in normalized_map:
            return normalized_map[_norm(name)]

    for col in available_candidates:
        col_norm = _norm(col)

        if any(token in col_norm for token in preferred):
            return col

    return available_candidates[0]


def _column_profile(table_info: dict, column: str | None) -> dict:
    if not column:
        return {}

    return (table_info.get("column_profiles") or {}).get(column) or {}


def _safe_div(a: float, b: float) -> float:
    if not b:
        return 0.0

    return a / b


def _missing_percent(table_info: dict, column: str | None) -> float:
    if not column:
        return 100.0

    return float(_column_profile(table_info, column).get("missing_percent") or 0.0)


def _unique_count(table_info: dict, column: str | None) -> int:
    if not column:
        return 0

    return int(_column_profile(table_info, column).get("unique_count") or 0)


def _format_bad_sources(values: list[str], limit: int = 3) -> str:
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f" и еще {len(values) - limit}"

    return ", ".join(shown) + suffix


def _score_single_event_table(
    table_name: str,
    table_info: dict,
    table_classification: dict | None = None,
) -> dict | None:
    if "error" in table_info:
        return None

    rows = int(table_info.get("rows") or 0)
    columns = table_info.get("columns") or []
    used = set()

    case_id = _pick_best_column(
        columns=columns,
        candidates=table_info.get("candidate_case_id_columns") or [],
        preferred=CASE_ID_PREFERRED,
        used=used,
    )

    if case_id:
        used.add(case_id)

    activity = _pick_best_column(
        columns=columns,
        candidates=table_info.get("candidate_activity_columns") or [],
        preferred=ACTIVITY_PREFERRED,
        used=used,
    )

    if activity:
        used.add(activity)

    timestamp = _pick_best_column(
        columns=columns,
        candidates=table_info.get("candidate_timestamp_columns") or [],
        preferred=TIME_PREFERRED,
        used=used,
    )

    case_unique = _unique_count(table_info, case_id)
    activity_unique = _unique_count(table_info, activity)
    case_missing_percent = _missing_percent(table_info, case_id)
    activity_missing_percent = _missing_percent(table_info, activity)
    timestamp_missing_percent = _missing_percent(table_info, timestamp)
    avg_events_per_case = round(_safe_div(rows, case_unique), 2)

    score = 0
    reasons = []
    risks = []
    table_classification = table_classification or {}
    table_role = table_classification.get("role")

    if table_role == "event_table":
        score += 18
        reasons.append("таблица классифицирована как event_table")
    elif table_role == "lifecycle_table":
        score -= 10
        risks.append("таблица похожа на lifecycle table, activity может быть неявной")
    elif table_role == "attribute_table":
        score -= 30
        risks.append("таблица похожа на справочник/атрибуты, а не на события")
    elif table_role == "bridge_table":
        score -= 35
        risks.append("таблица похожа на bridge table")
    elif table_role == "noise_table":
        score -= 25

    if case_id:
        score += 25
        reasons.append(f"найден case_id `{case_id}`")

        if case_missing_percent == 0:
            score += 8
            reasons.append("case_id без пропусков")
        elif case_missing_percent <= 5:
            score += 3
            risks.append(f"case_id содержит пропуски: {case_missing_percent}%")
        else:
            score -= 12
            risks.append(f"много пропусков case_id: {case_missing_percent}%")
    else:
        risks.append("не найден надежный case_id")

    if activity:
        score += 30
        reasons.append(f"найден activity `{activity}`")

        if activity_missing_percent == 0:
            score += 5
        elif activity_missing_percent > 10:
            score -= 10
            risks.append(f"много пропусков activity: {activity_missing_percent}%")
    else:
        risks.append("не найдено поле activity/status/operation")

    if timestamp:
        score += 30
        reasons.append(f"найден timestamp `{timestamp}`")

        if timestamp_missing_percent == 0:
            score += 10
            reasons.append("timestamp без пропусков")
        elif timestamp_missing_percent <= 5:
            score += 4
            risks.append(f"timestamp содержит пропуски: {timestamp_missing_percent}%")
        else:
            score -= 18
            risks.append(f"много пропусков timestamp: {timestamp_missing_percent}%")
    else:
        risks.append("не найден timestamp")

    if rows > 0 and case_unique > 0:
        if 2 <= avg_events_per_case <= 100:
            score += 15
            reasons.append(f"в среднем {avg_events_per_case} событий на case_id")
        elif avg_events_per_case > 100:
            score -= 10
            risks.append("слишком много событий на case_id, возможен неверный ключ")
        else:
            score -= 10
            risks.append("case_id почти уникален, возможно это event_id")

    if activity_unique > 0:
        activity_unique_ratio = _safe_div(activity_unique, rows)

        if 2 <= activity_unique <= 100 and activity_unique_ratio <= 0.5:
            score += 10
            reasons.append(f"разумное число activity: {activity_unique}")
        elif activity_unique_ratio > 0.8:
            score -= 25
            risks.append("activity почти уникальна, возможно выбрано не то поле")
        elif activity_unique > 500:
            score -= 15
            risks.append("слишком много разных activity")

    if rows < 2:
        score -= 20
        risks.append("слишком мало строк")

    confidence = max(0.0, min(score / 151, 1.0))

    if not case_id or not activity or not timestamp:
        confidence = min(confidence, 0.45)

    return {
        "strategy_id": "single_event_table",
        "strategy_key": f"single_event_table:{table_name}",
        "title": "Одна таблица уже похожа на event log",
        "confidence": round(confidence, 2),
        "table": table_name,
        "base_table": table_name,
        "case_id": case_id,
        "activity": activity,
        "timestamp": timestamp,
        "rows": rows,
        "avg_events_per_case": avg_events_per_case,
        "activity_unique_count": activity_unique,
        "table_role": table_role,
        "quality_signals": {
            "case_missing_percent": case_missing_percent,
            "activity_missing_percent": activity_missing_percent,
            "timestamp_missing_percent": timestamp_missing_percent,
        },
        "plan_mode": "joined_table",
        "joins": [],
        "reason": "; ".join(reasons) if reasons else "эвристика не нашла сильных признаков",
        "risks": risks,
    }


def _common_candidate(columns_by_table: list[list[str]], preferred: list[str]) -> str | None:
    if not columns_by_table:
        return None

    normalized_common = None
    normalized_to_original = {}

    for columns in columns_by_table:
        current = {_norm(col) for col in columns}

        for col in columns:
            normalized_to_original.setdefault(_norm(col), col)

        if normalized_common is None:
            normalized_common = current
        else:
            normalized_common = normalized_common.intersection(current)

    if not normalized_common:
        return None

    for name in preferred:
        n = _norm(name)

        if n in normalized_common:
            return normalized_to_original[n]

    for n in normalized_common:
        if any(token in n for token in preferred):
            return normalized_to_original[n]

    return normalized_to_original[sorted(normalized_common)[0]]


def _score_concat_strategy(tables_info: dict) -> dict | None:
    event_sources = []
    case_columns = []
    total_rows = 0
    valid_tables = 0
    risks = []
    reasons = []

    for table_name, table_info in tables_info.items():
        if "error" in table_info:
            continue

        valid_tables += 1

        columns = table_info.get("columns") or []
        case_id = _pick_best_column(
            columns=columns,
            candidates=table_info.get("candidate_case_id_columns") or [],
            preferred=CASE_ID_PREFERRED,
        )
        timestamp = _pick_best_column(
            columns=columns,
            candidates=table_info.get("candidate_timestamp_columns") or [],
            preferred=TIME_PREFERRED,
        )

        if case_id and timestamp:
            case_missing_percent = _missing_percent(table_info, case_id)
            timestamp_missing_percent = _missing_percent(table_info, timestamp)
            event_sources.append(
                {
                    "file": table_name,
                    "activity": Path(table_name).stem,
                    "case_id": case_id,
                    "timestamp": timestamp,
                    "rows": table_info.get("rows"),
                    "case_missing_percent": case_missing_percent,
                    "timestamp_missing_percent": timestamp_missing_percent,
                }
            )
            case_columns.append(columns)
            total_rows += int(table_info.get("rows") or 0)

    if not event_sources:
        return None

    common_case_id = _common_candidate(case_columns, CASE_ID_PREFERRED)
    score = 0

    if len(event_sources) >= 2:
        score += 35
        reasons.append(f"найдено {len(event_sources)} таблиц, похожих на события")
    else:
        score += 10
        risks.append("только одна таблица подходит для concat")

    if common_case_id:
        score += 30
        reasons.append(f"есть общий возможный case_id `{common_case_id}`")
    else:
        score -= 10
        risks.append("у таблиц могут быть разные case_id")

    if total_rows > 0:
        score += 15

    coverage = _safe_div(len(event_sources), valid_tables)

    if coverage >= 0.8:
        score += 15
        reasons.append(f"подходит {round(coverage * 100)}% таблиц")
    elif coverage < 0.5:
        score -= 15
        risks.append(f"для concat подходит только {round(coverage * 100)}% таблиц")

    bad_sources = [
        source["file"]
        for source in event_sources
        if source["case_missing_percent"] > 10
        or source["timestamp_missing_percent"] > 10
    ]

    if bad_sources:
        score -= min(len(bad_sources) * 10, 25)
        risks.append(f"есть таблицы с пропусками ключевых полей: {_format_bad_sources(bad_sources)}")

    confidence = max(0.0, min(score / 95, 1.0))

    return {
        "strategy_id": "event_tables_concat",
        "strategy_key": "event_tables_concat",
        "title": "Несколько таблиц как отдельные события",
        "confidence": round(confidence, 2),
        "plan_mode": "event_tables_concat",
        "activity_source": "table_name",
        "case_id": common_case_id,
        "timestamp": None,
        "event_sources": event_sources,
        "rows": total_rows,
        "reason": "; ".join(reasons) if reasons else "несколько таблиц имеют case_id и timestamp",
        "risks": risks,
    }


def _score_base_with_joins_strategy(
    tables_info: dict,
    relationships: list[dict],
    best_single: dict | None,
) -> dict | None:
    if not best_single:
        return None

    base_table = best_single.get("base_table")

    if not base_table:
        return None

    joins = []

    for rel in relationships:
        left_table = rel.get("left_table")
        right_table = rel.get("right_table")

        if left_table == base_table:
            joins.append(
                {
                    "right_table": right_table,
                    "left_key": rel.get("left_column"),
                    "right_key": rel.get("right_column"),
                    "how": "left",
                    "relationship_score": rel.get("score"),
                    "source": "suggested",
                }
            )
        elif right_table == base_table:
            joins.append(
                {
                    "right_table": left_table,
                    "left_key": rel.get("right_column"),
                    "right_key": rel.get("left_column"),
                    "how": "left",
                    "relationship_score": rel.get("score"),
                    "source": "suggested",
                }
            )

    confidence = 0.35

    if joins:
        confidence += min(len(joins) * 0.07, 0.25)

    return {
        "strategy_id": "base_table_with_joins",
        "strategy_key": f"base_table_with_joins:{base_table}",
        "title": "Основная таблица событий + справочники через left join",
        "confidence": round(min(confidence, 0.75), 2),
        "plan_mode": "joined_table",
        "base_table": base_table,
        "case_id": best_single.get("case_id"),
        "activity": best_single.get("activity"),
        "timestamp": best_single.get("timestamp"),
        "suggested_joins": joins[:10],
        "reason": (
            "есть таблица, похожая на event log, и найдены возможные связи "
            "для обогащения атрибутами"
        ),
        "risks": [
            "join может размножить строки",
            "по умолчанию suggested join не применяются без явного подтверждения",
        ],
    }


def detect_strategies(
    tables_info: dict,
    relationships: list[dict],
    table_classifications: dict | None = None,
) -> list[dict]:
    strategies = []
    single_candidates = []
    table_classifications = table_classifications or {}

    for table_name, table_info in tables_info.items():
        strategy = _score_single_event_table(
            table_name=table_name,
            table_info=table_info,
            table_classification=table_classifications.get(table_name),
        )

        if strategy:
            single_candidates.append(strategy)

    single_candidates = sorted(
        single_candidates,
        key=lambda item: item.get("confidence", 0),
        reverse=True,
    )

    if single_candidates:
        strategies.extend(single_candidates[:2])

    concat_strategy = _score_concat_strategy(tables_info)

    if concat_strategy:
        strategies.append(concat_strategy)

    base_join_strategy = _score_base_with_joins_strategy(
        tables_info=tables_info,
        relationships=relationships,
        best_single=single_candidates[0] if single_candidates else None,
    )

    if base_join_strategy:
        strategies.append(base_join_strategy)

    strategies = sorted(
        strategies,
        key=lambda item: item.get("confidence", 0),
        reverse=True,
    )

    for index, strategy in enumerate(strategies, start=1):
        strategy["number"] = index
        strategy["recommended"] = index == 1

    return strategies[:5]


def strategy_to_user_requirements(strategy: dict) -> dict:
    strategy_id = strategy.get("strategy_id")

    if strategy_id == "event_tables_concat":
        requirements = {
            "plan_mode": "event_tables_concat",
            "activity_source": "table_name",
        }

        if strategy.get("case_id"):
            requirements["case_id"] = strategy.get("case_id")

        if strategy.get("timestamp"):
            requirements["timestamp"] = strategy.get("timestamp")

        return requirements

    requirements = {
        "plan_mode": "joined_table",
        "base_table": strategy.get("base_table"),
        "case_id": strategy.get("case_id"),
        "activity": strategy.get("activity"),
        "timestamp": strategy.get("timestamp"),
    }

    return {
        key: value
        for key, value in requirements.items()
        if value
    }
