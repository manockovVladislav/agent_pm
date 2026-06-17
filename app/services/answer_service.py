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


def _format_strategy(strategy: dict) -> list[str]:
    lines = []
    number = strategy.get("number")
    recommended = " - рекомендую" if strategy.get("recommended") else ""

    lines.append(
        f"[{number}] {strategy.get('title')} "
        f"(confidence={strategy.get('confidence')}){recommended}"
    )

    if strategy.get("strategy_id") == "event_tables_concat":
        lines.append(f"- таблиц-событий: {len(strategy.get('event_sources') or [])}")
        lines.append(f"- общий case_id: {_fmt(strategy.get('case_id'))}")
        lines.append("- activity: имя таблицы")
    else:
        lines.append(f"- таблица: `{_fmt(strategy.get('base_table') or strategy.get('table'))}`")
        lines.append(f"- case_id: `{_fmt(strategy.get('case_id'))}`")
        lines.append(f"- activity: `{_fmt(strategy.get('activity'))}`")
        lines.append(f"- timestamp: `{_fmt(strategy.get('timestamp'))}`")

    if strategy.get("reason"):
        lines.append(f"- почему: {strategy.get('reason')}")

    risks = strategy.get("risks") or []

    if risks:
        lines.append(f"- риски: {_format_list(risks, limit=3)}")

    return lines


def _format_analysis_summary(
    files: list[dict],
    tables_info: dict,
    relationships: list[dict],
) -> list[str]:
    lines = []
    tables_with_case = 0
    tables_with_activity = 0
    tables_with_time = 0
    error_tables = 0

    for table_info in tables_info.values():
        if "error" in table_info:
            error_tables += 1
            continue

        if table_info.get("candidate_case_id_columns"):
            tables_with_case += 1

        if table_info.get("candidate_activity_columns"):
            tables_with_activity += 1

        if table_info.get("candidate_timestamp_columns"):
            tables_with_time += 1

    lines.append("Я проанализировал папку `data/`.")
    lines.append("")
    lines.append("Кратко по данным:")
    lines.append(f"- найдено файлов: {len(files)}")
    lines.append(f"- успешно прочитано таблиц: {len(tables_info) - error_tables}")
    lines.append(f"- таблиц с возможным case_id: {tables_with_case}")
    lines.append(f"- таблиц с возможным activity/status: {tables_with_activity}")
    lines.append(f"- таблиц с возможным timestamp: {tables_with_time}")
    lines.append(f"- найдено возможных связей: {len(relationships)}")
    lines.append("")

    return lines


def _format_preview_answer(
    files: list[dict],
    tables_info: dict,
    relationships: list[dict],
    proposed_strategies: list[dict],
    selected_strategy: dict | None,
    join_plan: dict | None,
    join_validation_report: dict | None,
    preview_validation_report: dict | None,
    preview_output_paths: dict | None,
    session_path: str | None,
) -> str:
    lines = []
    lines.extend(
        _format_analysis_summary(
            files=files,
            tables_info=tables_info,
            relationships=relationships,
        )
    )

    lines.append("Лучшие стратегии сборки event log:")

    if proposed_strategies:
        for strategy in proposed_strategies:
            lines.extend(_format_strategy(strategy))
            lines.append("")
    else:
        lines.append("- стратегии не найдены")
        lines.append("")

    if selected_strategy:
        lines.append(
            f"Выбранная стратегия: [{selected_strategy.get('number')}] "
            f"{selected_strategy.get('title')}"
        )
        lines.append("")

    lines.append("Предварительный план:")

    if not join_plan:
        lines.append("- план не построен")
    elif join_plan.get("status") != "ok":
        lines.append("- статус: error")
        lines.append(f"- ошибка: {join_plan.get('error')}")

        if join_plan.get("available_columns"):
            lines.append(f"- доступные колонки: {_format_list(join_plan.get('available_columns'), 30)}")
    else:
        lines.append(f"- режим: `{join_plan.get('mode')}`")

        if join_plan.get("mode") == "event_tables_concat":
            sources = join_plan.get("event_sources") or []
            lines.append(f"- источников событий: {len(sources)}")
            lines.append("- activity берется из имени таблицы")

            for source in sources[:10]:
                lines.append(
                    f"- `{source.get('file')}` -> "
                    f"activity=`{source.get('activity')}`, "
                    f"case_id=`{source.get('case_id')}`, "
                    f"timestamp=`{source.get('timestamp')}`"
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
            lines.append("Предупреждения:")
            for warning in warnings[:8]:
                lines.append(f"- {warning}")

    lines.append("")
    lines.append("Preview:")

    if preview_validation_report:
        lines.append(_quality_line("статус", preview_validation_report.get("status")))
        lines.append(_quality_line("событий", preview_validation_report.get("total_events")))
        lines.append(_quality_line("case_id", preview_validation_report.get("total_cases")))
        lines.append(_quality_line("уникальных activity", preview_validation_report.get("unique_activities")))
        lines.append(_quality_line("пропусков case_id", preview_validation_report.get("missing_case_id")))
        lines.append(_quality_line("пропусков activity", preview_validation_report.get("missing_activity")))
        lines.append(_quality_line("пропусков timestamp", preview_validation_report.get("missing_timestamp")))
        lines.append(_quality_line("невалидных timestamp", preview_validation_report.get("invalid_timestamp")))
        lines.append(_quality_line("дублей событий", preview_validation_report.get("duplicate_events")))
        lines.append(_quality_line("case_id с одним событием", preview_validation_report.get("cases_with_one_event")))

        suggestions = preview_validation_report.get("suggestions") or []

        if suggestions:
            lines.append("")
            lines.append("Что можно улучшить:")
            for suggestion in suggestions[:5]:
                lines.append(f"- {suggestion}")
    else:
        lines.append("- preview не собран")

    lines.append("")
    lines.append("Файлы preview:")

    if preview_output_paths:
        for name, path in preview_output_paths.items():
            lines.append(f"- `{name}`: `{path}`")
    else:
        lines.append("- файлы preview не сохранены")

    if session_path:
        lines.append(f"- `session_state`: `{session_path}`")

    lines.append("")
    lines.append("Если preview выглядит корректно - напиши `подтверждаю`.")
    lines.append("Если нет - уточни, например:")
    lines.append("`case_id=deal_id timestamp=created_at`")
    lines.append("или")
    lines.append("`выбери вариант 2`")
    lines.append("или")
    lines.append("`join table1.xlsx.id = table2.xlsx.id`")

    return "\n".join(lines)


def _format_final_answer(
    validation_report: dict | None,
    output_paths: dict | None,
    session_path: str | None,
) -> str:
    lines = []
    lines.append("Финальный event log собран после подтверждения пользователя.")
    lines.append("")

    if validation_report:
        lines.append("Качество финального event log:")
        lines.append(_quality_line("статус", validation_report.get("status")))
        lines.append(_quality_line("событий", validation_report.get("total_events")))
        lines.append(_quality_line("case_id", validation_report.get("total_cases")))
        lines.append(_quality_line("уникальных activity", validation_report.get("unique_activities")))
        lines.append(_quality_line("пропусков case_id", validation_report.get("missing_case_id")))
        lines.append(_quality_line("пропусков activity", validation_report.get("missing_activity")))
        lines.append(_quality_line("пропусков timestamp", validation_report.get("missing_timestamp")))
        lines.append(_quality_line("невалидных timestamp", validation_report.get("invalid_timestamp")))
        lines.append(_quality_line("дублей событий", validation_report.get("duplicate_events")))
        lines.append(_quality_line("case_id с одним событием", validation_report.get("cases_with_one_event")))
        lines.append(_quality_line("редких маршрутов", validation_report.get("rare_routes")))
        lines.append(_quality_line("средняя длительность case, часов", validation_report.get("avg_case_duration_hours")))

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

    lines.append("")
    lines.append("Можно продолжить доработку: изменить поля, выбрать другую стратегию или добавить join.")

    return "\n".join(lines)


def _format_unknown_answer(dialog_phase: str | None) -> str:
    lines = []
    lines.append("Я не стал ничего собирать автоматически.")
    lines.append("")

    if dialog_phase == "preview_ready":
        lines.append("Сейчас уже есть preview. Можно подтвердить финальную сборку или исправить план.")
    elif dialog_phase == "result_ready":
        lines.append("Финальный результат уже собран. Можно доработать правила.")
    else:
        lines.append("Можно начать с команды:")

    lines.append("")
    lines.append("- `помоги собрать лог`")
    lines.append("- `выбери вариант 1`")
    lines.append("- `case_id=application_id timestamp=created_at`")
    lines.append("- `join table1.xlsx.id = table2.xlsx.id`")
    lines.append("- `подтверждаю`")
    lines.append("- `сбросить`")

    return "\n".join(lines)


def build_final_answer(
    user_question: str,
    user_intent: str | None,
    dialog_phase: str | None,
    parsed_requirements: dict | None,
    user_requirements: dict | None,
    files: list[dict],
    tables_info: dict,
    relationships: list[dict],
    proposed_strategies: list[dict],
    selected_strategy: dict | None,
    join_plan: dict | None,
    join_validation_report: dict | None,
    preview_validation_report: dict | None,
    preview_output_paths: dict | None,
    validation_report: dict | None,
    output_paths: dict | None,
    session_path: str | None = None,
) -> str:
    if user_intent == "execute_final":
        return _format_final_answer(
            validation_report=validation_report,
            output_paths=output_paths,
            session_path=session_path,
        )

    if user_intent in {"start", "select_strategy", "correct_plan", "preview"}:
        return _format_preview_answer(
            files=files,
            tables_info=tables_info,
            relationships=relationships,
            proposed_strategies=proposed_strategies,
            selected_strategy=selected_strategy,
            join_plan=join_plan,
            join_validation_report=join_validation_report,
            preview_validation_report=preview_validation_report,
            preview_output_paths=preview_output_paths,
            session_path=session_path,
        )

    return _format_unknown_answer(dialog_phase=dialog_phase)
