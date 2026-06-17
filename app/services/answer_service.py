def _fmt(value, default="не найдено"):
    if value is None or value == "":
        return default

    return str(value)


def _format_list(values, limit: int = 10) -> str:
    if not values:
        return "не найдено"

    return ", ".join(map(str, list(values)[:limit]))


def _quality_line(name: str, value) -> str:
    return f"- {name}: {_fmt(value, '0')}"


def _format_preview_sample(sample_rows: list[dict], limit: int = 8) -> list[str]:
    if not sample_rows:
        return ["- нет строк для показа"]

    columns = list(sample_rows[0].keys())
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]

    for row in sample_rows[:limit]:
        values = [
            str(row.get(column, "")).replace("\n", " ")[:80]
            for column in columns
        ]
        lines.append("| " + " | ".join(values) + " |")

    return lines


def _join_kind(rel: dict, table_classifications: dict) -> str:
    left_role = (table_classifications.get(rel.get("left_table")) or {}).get("role")
    right_role = (table_classifications.get(rel.get("right_table")) or {}).get("role")

    roles = {left_role, right_role}

    if "event_table" in roles and "attribute_table" in roles:
        return "enrichment join"

    if left_role == "event_table" and right_role == "event_table":
        return "event-event join, риск смешать разные источники событий"

    if "bridge_table" in roles:
        return "bridge join"

    if roles == {"attribute_table"}:
        return "attribute join"

    return "join"


def _format_join_commands(
    relationships: list[dict],
    table_classifications: dict,
    limit: int = 5,
) -> list[str]:
    if not relationships:
        return ["- связи не найдены"]

    lines = []

    for rel in relationships[:limit]:
        join_kind = _join_kind(rel, table_classifications)
        command = (
            f"join {rel.get('left_table')}.{rel.get('left_column')} = "
            f"{rel.get('right_table')}.{rel.get('right_column')}"
        )
        lines.append(f"- `{command}` (score={rel.get('score')}, {join_kind})")

    return lines


def _format_strategy(strategy: dict) -> list[str]:
    number = strategy.get("number")
    recommended = " - рекомендую" if strategy.get("recommended") else ""
    lines = [
        f"[{number}] {strategy.get('title')} "
        f"(preview_score={_fmt(strategy.get('preview_score'), 'n/a')}, "
        f"confidence={strategy.get('confidence')}){recommended}"
    ]

    if strategy.get("strategy_id") == "event_tables_concat":
        lines.append(
            f"- {len(strategy.get('event_sources') or [])} таблиц-событий, "
            f"case_id=`{_fmt(strategy.get('case_id'))}`, activity=имя таблицы"
        )
    else:
        lines.append(
            f"- `{_fmt(strategy.get('base_table') or strategy.get('table'))}`: "
            f"case_id=`{_fmt(strategy.get('case_id'))}`, "
            f"activity=`{_fmt(strategy.get('activity'))}`, "
            f"timestamp=`{_fmt(strategy.get('timestamp'))}`"
        )

    risks = strategy.get("risks") or []

    if risks:
        lines.append(f"- риски: {_format_list(risks, limit=2)}")

    return lines


def _format_table_classifications(table_classifications: dict, limit: int = 8) -> list[str]:
    if not table_classifications:
        return ["- классификация таблиц отсутствует"]

    lines = []

    for table_name, item in list(table_classifications.items())[:limit]:
        signals = item.get("signals") or {}
        lines.append(
            f"- `{table_name}`: {item.get('role')} "
            f"(confidence={item.get('confidence')}, "
            f"events/case={signals.get('events_per_case')})"
        )

    return lines


def _format_strategy_compare(proposed_strategies: list[dict]) -> str:
    if not proposed_strategies:
        return "Нет сохраненных стратегий для сравнения. Сначала напиши `помоги собрать лог`."

    lines = [
        "Сравнение стратегий:",
        "",
        "| # | strategy | preview_score | events | cases | activity | missing_ts | invalid_ts | same_ts_cases |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for strategy in proposed_strategies[:5]:
        metrics = strategy.get("preview_metrics") or {}
        lines.append(
            "| "
            f"{strategy.get('number')} | "
            f"{strategy.get('title')} | "
            f"{_fmt(strategy.get('preview_score'), 'n/a')} | "
            f"{_fmt(metrics.get('events'), 'n/a')} | "
            f"{_fmt(metrics.get('cases'), 'n/a')} | "
            f"{_fmt(metrics.get('activities'), 'n/a')} | "
            f"{_fmt(metrics.get('missing_timestamp'), 'n/a')} | "
            f"{_fmt(metrics.get('invalid_timestamp'), 'n/a')} | "
            f"{_fmt(metrics.get('same_timestamp_cases'), 'n/a')} |"
        )

    lines.append("")
    lines.append("Рекомендована стратегия с максимальным `preview_score`; при равенстве учитывается confidence.")

    return "\n".join(lines)


def _format_explain_choice(
    selected_strategy: dict | None,
    proposed_strategies: list[dict],
    table_classifications: dict,
    join_plan: dict | None,
) -> str:
    if not selected_strategy:
        return "Нет выбранной стратегии. Сначала напиши `помоги собрать лог`."

    lines = [
        f"Почему выбрана стратегия [{selected_strategy.get('number')}]:",
        f"- {selected_strategy.get('title')}",
        f"- preview_score: {_fmt(selected_strategy.get('preview_score'), 'n/a')}",
        f"- confidence до preview: {_fmt(selected_strategy.get('confidence'), 'n/a')}",
    ]

    metrics = selected_strategy.get("preview_metrics") or {}

    if metrics:
        lines.append(
            "- preview: "
            f"events={_fmt(metrics.get('events'), 'n/a')}, "
            f"cases={_fmt(metrics.get('cases'), 'n/a')}, "
            f"activity={_fmt(metrics.get('activities'), 'n/a')}, "
            f"missing_ts={_fmt(metrics.get('missing_timestamp'), 'n/a')}, "
            f"invalid_ts={_fmt(metrics.get('invalid_timestamp'), 'n/a')}"
        )

    assumptions = selected_strategy.get("assumptions") or []

    if assumptions:
        lines.append("")
        lines.append("Допущения:")
        for assumption in assumptions[:8]:
            lines.append(f"- {assumption}")

    risks = selected_strategy.get("risks") or []

    if risks:
        lines.append("")
        lines.append("Риски:")
        for risk in risks[:5]:
            lines.append(f"- {risk}")

    if join_plan:
        lines.append("")
        lines.append("Join:")
        lines.append(f"- применено join-операций: {len(join_plan.get('joins') or [])}")
        if not join_plan.get("joins"):
            lines.append("- найденные связи не применялись автоматически")

    lines.append("")
    lines.append("Классификация таблиц:")
    lines.extend(_format_table_classifications(table_classifications))

    if proposed_strategies:
        lines.append("")
        lines.append("Альтернативы:")
        for strategy in proposed_strategies[:5]:
            if strategy.get("number") == selected_strategy.get("number"):
                continue
            lines.append(
                f"- [{strategy.get('number')}] {strategy.get('title')}: "
                f"preview_score={_fmt(strategy.get('preview_score'), 'n/a')}"
            )

    return "\n".join(lines)


def _format_analysis_summary(
    files: list[dict],
    tables_info: dict,
    table_classifications: dict,
    relationships: list[dict],
) -> list[str]:
    error_tables = sum(1 for table_info in tables_info.values() if "error" in table_info)
    roles = {}

    for item in table_classifications.values():
        role = item.get("role")
        roles[role] = roles.get(role, 0) + 1

    return [
        "Я проанализировал `data/`.",
        "",
        "Данные:",
        f"- файлов: {len(files)}",
        f"- прочитано таблиц: {len(tables_info) - error_tables}",
        f"- event tables: {roles.get('event_table', 0)}",
        f"- attribute/lifecycle/bridge: "
        f"{roles.get('attribute_table', 0)}/"
        f"{roles.get('lifecycle_table', 0)}/"
        f"{roles.get('bridge_table', 0)}",
        f"- найдено возможных связей: {len(relationships)}",
        "",
    ]


def _format_plan(join_plan: dict | None, join_validation_report: dict | None) -> list[str]:
    lines = ["План:"]

    if not join_plan:
        return lines + ["- план не построен"]

    if join_plan.get("status") != "ok":
        lines.append("- статус: error")
        lines.append(f"- ошибка: {join_plan.get('error')}")

        if join_plan.get("available_columns"):
            lines.append(f"- доступные колонки: {_format_list(join_plan.get('available_columns'), 30)}")

        return lines

    lines.append(f"- режим: `{join_plan.get('mode')}`")

    if join_plan.get("mode") == "event_tables_concat":
        sources = join_plan.get("event_sources") or []
        lines.append(f"- источников событий: {len(sources)}")

        for source in sources[:5]:
            lines.append(
                f"- `{source.get('file')}`: activity=`{source.get('activity')}`, "
                f"case_id=`{source.get('case_id')}`, timestamp=`{source.get('timestamp')}`"
            )
    else:
        event_cols = join_plan.get("event_log_columns") or {}
        lines.append(f"- базовая таблица: `{join_plan.get('base_table')}`")
        lines.append(f"- case_id: `{event_cols.get('case_id')}`")
        lines.append(f"- activity: `{event_cols.get('activity')}`")
        lines.append(f"- timestamp: `{event_cols.get('timestamp')}`")
        lines.append(f"- join-операций: {len(join_plan.get('joins') or [])}")

    warnings = list(join_plan.get("warnings") or [])

    if join_validation_report:
        warnings.extend(join_validation_report.get("warnings") or [])

    if warnings:
        lines.append("")
        lines.append("Важные предупреждения:")
        for warning in warnings[:4]:
            lines.append(f"- {warning}")

    return lines


def _format_preview_answer(
    files: list[dict],
    tables_info: dict,
    table_classifications: dict,
    relationships: list[dict],
    proposed_strategies: list[dict],
    selected_strategy: dict | None,
    join_plan: dict | None,
    join_validation_report: dict | None,
    preview_validation_report: dict | None,
    preview_output_paths: dict | None,
    session_warnings: list[str] | None,
    session_path: str | None,
) -> str:
    lines = []
    session_warnings = session_warnings or []

    if session_warnings:
        lines.append("Предупреждение:")
        for warning in session_warnings[:2]:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend(_format_analysis_summary(files, tables_info, table_classifications, relationships))
    lines.append("Стратегии:")

    if proposed_strategies:
        for strategy in proposed_strategies[:3]:
            lines.extend(_format_strategy(strategy))
    else:
        lines.append("- стратегии не найдены")

    if selected_strategy:
        lines.append("")
        lines.append(
            f"Выбрано: [{selected_strategy.get('number')}] "
            f"{selected_strategy.get('title')}"
        )

    lines.append("")
    lines.extend(_format_plan(join_plan, join_validation_report))
    lines.append("")
    lines.append("Качество preview:")

    if preview_validation_report:
        lines.append(_quality_line("статус", preview_validation_report.get("status")))
        lines.append(_quality_line("событий", preview_validation_report.get("total_events")))
        lines.append(_quality_line("case_id", preview_validation_report.get("total_cases")))
        lines.append(_quality_line("activity", preview_validation_report.get("unique_activities")))
        lines.append(_quality_line("пропусков timestamp", preview_validation_report.get("missing_timestamp")))
        lines.append(_quality_line("невалидных timestamp", preview_validation_report.get("invalid_timestamp")))
        lines.append(_quality_line("дублей событий", preview_validation_report.get("duplicate_events")))

        suggestions = preview_validation_report.get("suggestions") or []

        if suggestions:
            lines.append("")
            lines.append("Что проверить:")
            for suggestion in suggestions[:3]:
                lines.append(f"- {suggestion}")

        lines.append("")
        lines.append("Первые строки preview:")
        lines.extend(_format_preview_sample(preview_validation_report.get("sample_rows") or []))
    else:
        lines.append("- preview не собран")

    lines.append("")
    lines.append("Join-подсказки:")
    lines.extend(_format_join_commands(relationships, table_classifications))
    lines.append("")
    lines.append("Файлы:")

    if preview_output_paths:
        for name, path in preview_output_paths.items():
            lines.append(f"- `{name}`: `{path}`")
    else:
        lines.append("- preview-файлы не сохранены")

    if session_path:
        lines.append(f"- `session_state`: `{session_path}`")

    lines.append("")
    lines.append("Дальше: `подтверждаю`, `выбери вариант 2`, `case_id=... timestamp=...` или join-команда выше.")

    return "\n".join(lines)


def _format_final_answer(
    validation_report: dict | None,
    output_paths: dict | None,
    session_warnings: list[str] | None,
    session_path: str | None,
) -> str:
    lines = ["Финальный event log собран после подтверждения пользователя.", ""]

    if session_warnings:
        lines.append("Предупреждение:")
        for warning in session_warnings[:2]:
            lines.append(f"- {warning}")
        lines.append("")

    if validation_report:
        lines.append("Качество:")
        lines.append(_quality_line("статус", validation_report.get("status")))
        lines.append(_quality_line("событий", validation_report.get("total_events")))
        lines.append(_quality_line("case_id", validation_report.get("total_cases")))
        lines.append(_quality_line("activity", validation_report.get("unique_activities")))
        lines.append(_quality_line("пропусков timestamp", validation_report.get("missing_timestamp")))
        lines.append(_quality_line("невалидных timestamp", validation_report.get("invalid_timestamp")))
        lines.append(_quality_line(
            "case с одинаковым timestamp для разных activity",
            validation_report.get("cases_with_same_timestamp_multi_activity"),
        ))

        if validation_report.get("error"):
            lines.append(f"- ошибка: {validation_report.get('error')}")
    else:
        lines.append("Отчет качества отсутствует.")

    lines.append("")
    lines.append("Файлы:")

    if output_paths:
        for name, path in output_paths.items():
            lines.append(f"- `{name}`: `{path}`")
    else:
        lines.append("- файлы не сохранены")

    if session_path:
        lines.append(f"- `session_state`: `{session_path}`")

    return "\n".join(lines)


def _format_unknown_answer(dialog_phase: str | None) -> str:
    lines = ["Я не стал ничего собирать автоматически.", ""]

    if dialog_phase == "preview_ready":
        lines.append("Сейчас есть preview. Можно подтвердить финальную сборку или исправить план.")
    elif dialog_phase == "result_ready":
        lines.append("Финальный результат уже собран. Можно доработать правила.")
    else:
        lines.append("Начни с `помоги собрать лог`.")

    lines.append("")
    lines.append("Команды: `выбери вариант 1`, `case_id=... timestamp=...`, `join table1.id = table2.id`, `подтверждаю`, `сбросить`.")

    return "\n".join(lines)


def build_final_answer(
    user_question: str,
    user_intent: str | None,
    dialog_phase: str | None,
    parsed_requirements: dict | None,
    user_requirements: dict | None,
    files: list[dict],
    tables_info: dict,
    table_classifications: dict,
    relationships: list[dict],
    proposed_strategies: list[dict],
    selected_strategy: dict | None,
    join_plan: dict | None,
    join_validation_report: dict | None,
    preview_validation_report: dict | None,
    preview_output_paths: dict | None,
    validation_report: dict | None,
    output_paths: dict | None,
    session_warnings: list[str] | None = None,
    session_path: str | None = None,
) -> str:
    if user_intent == "compare_strategies":
        return _format_strategy_compare(proposed_strategies)

    if user_intent == "explain_choice":
        return _format_explain_choice(
            selected_strategy=selected_strategy,
            proposed_strategies=proposed_strategies,
            table_classifications=table_classifications,
            join_plan=join_plan,
        )

    if user_intent == "execute_final":
        return _format_final_answer(
            validation_report=validation_report,
            output_paths=output_paths,
            session_warnings=session_warnings,
            session_path=session_path,
        )

    if user_intent in {"start", "select_strategy", "correct_plan", "preview"}:
        return _format_preview_answer(
            files=files,
            tables_info=tables_info,
            table_classifications=table_classifications,
            relationships=relationships,
            proposed_strategies=proposed_strategies,
            selected_strategy=selected_strategy,
            join_plan=join_plan,
            join_validation_report=join_validation_report,
            preview_validation_report=preview_validation_report,
            preview_output_paths=preview_output_paths,
            session_warnings=session_warnings,
            session_path=session_path,
        )

    return _format_unknown_answer(dialog_phase=dialog_phase)
