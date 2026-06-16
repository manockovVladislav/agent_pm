def _format_list(values, limit: int = 10) -> str:
    if not values:
        return "не найдено"

    values = list(values)[:limit]

    return ", ".join(map(str, values))


def build_final_answer(
    user_question: str,
    parsed_requirements: dict | None,
    user_requirements: dict | None,
    agent_decision: dict | None,
    agent_decision_history: list[dict] | None,
    files: list[dict],
    tables_info: dict,
    relationships: list[dict],
    join_plan: dict,
    join_validation_report: dict,
    validation_report: dict,
    output_paths: dict,
    session_path: str | None = None,
) -> str:
    lines = []

    lines.append("Я проанализировал таблицы в папке data.")
    lines.append("")
    lines.append(f"Запрос: {user_question}")
    lines.append("")

    if parsed_requirements:
        lines.append("Распознанные правки в текущем запросе:")
        for key, value in parsed_requirements.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    if user_requirements:
        lines.append("Активные требования с учетом памяти сессии:")
        for key, value in user_requirements.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    if agent_decision:
        lines.append("Решение агента:")
        lines.append(f"- action: {agent_decision.get('action')}")
        lines.append(f"- backend: {agent_decision.get('backend')}")
        lines.append(f"- статус решения: {agent_decision.get('status')}")

        if agent_decision.get("requirements"):
            lines.append(f"- примененные требования: {agent_decision.get('requirements')}")

        if agent_decision.get("reason"):
            lines.append(f"- причина: {agent_decision.get('reason')}")

        if agent_decision.get("user_message"):
            lines.append(f"- сообщение: {agent_decision.get('user_message')}")

        if agent_decision.get("error"):
            lines.append(f"- ошибка LLM: {agent_decision.get('error')}")

        lines.append("")

    if agent_decision_history:
        lines.append("Итерации агента:")
        for index, decision in enumerate(agent_decision_history, start=1):
            lines.append(
                f"- {index}: action={decision.get('action')}, "
                f"status={decision.get('status')}"
            )
        lines.append("")

    lines.append(f"Найдено таблиц: {len(files)}")
    lines.append("")

    for file_info in files:
        file_name = file_info["file_name"]
        table_info = tables_info.get(file_name, {})

        lines.append(f"Таблица: {file_name}")

        if "error" in table_info:
            lines.append(f"- ошибка чтения: {table_info['error']}")
            lines.append("")
            continue

        lines.append(f"- строк: {table_info['rows']}")
        lines.append(f"- колонок: {table_info['columns_count']}")
        lines.append(f"- дублей строк: {table_info['duplicate_rows']}")

        lines.append(
            "- кандидаты на case_id: "
            f"{_format_list(table_info['candidate_case_id_columns'])}"
        )

        lines.append(
            "- кандидаты на activity: "
            f"{_format_list(table_info['candidate_activity_columns'])}"
        )

        lines.append(
            "- кандидаты на timestamp: "
            f"{_format_list(table_info['candidate_timestamp_columns'])}"
        )

        lines.append("")

    lines.append("Найденные возможные связи между таблицами:")
    if relationships:
        for rel in relationships[:10]:
            lines.append(
                f"- {rel['left_table']}.{rel['left_column']} = "
                f"{rel['right_table']}.{rel['right_column']} "
                f"(score={rel['score']})"
            )
    else:
        lines.append("- связи автоматически не найдены")

    lines.append("")

    lines.append("Предварительный join_plan:")

    if join_plan.get("status") == "ok":
        mode = join_plan.get("mode", "joined_table")
        lines.append(f"- режим: {mode}")

        if mode == "event_tables_concat":
            lines.append("- activity: имя файла")
            lines.append(f"- источников событий: {len(join_plan.get('event_sources', []))}")

            for source in join_plan.get("event_sources", [])[:10]:
                lines.append(
                    f"- {source['file']}: activity={source['activity']}, "
                    f"case_id={source.get('case_id')}, "
                    f"timestamp={source.get('timestamp')}"
                )
        else:
            lines.append(f"- базовая таблица: {join_plan['base_table']}")
            lines.append(f"- case_id: {join_plan['event_log_columns']['case_id']}")
            lines.append(f"- activity: {join_plan['event_log_columns']['activity']}")
            lines.append(f"- timestamp: {join_plan['event_log_columns']['timestamp']}")
            lines.append(f"- join-операций: {len(join_plan.get('joins', []))}")
    else:
        if join_plan.get("mode"):
            lines.append(f"- режим: {join_plan.get('mode')}")
        lines.append(f"- ошибка: {join_plan.get('error')}")

        for error in join_plan.get("errors", [])[:5]:
            lines.append(f"- error: {error}")

    lines.append("")

    lines.append("Проверка join_plan:")
    if join_validation_report:
        lines.append(f"- статус: {join_validation_report.get('status')}")
        lines.append(f"- join-операций: {join_validation_report.get('total_joins')}")

        if join_validation_report.get("mode") == "event_tables_concat":
            lines.append(
                "- источников событий: "
                f"{join_validation_report.get('total_event_sources')}"
            )

        lines.append(f"- предупреждений: {len(join_validation_report.get('warnings', []))}")
        lines.append(f"- ошибок: {len(join_validation_report.get('errors', []))}")

        for warning in join_validation_report.get("warnings", [])[:5]:
            lines.append(f"- warning: {warning}")

        for error in join_validation_report.get("errors", [])[:5]:
            lines.append(f"- error: {error}")
    else:
        lines.append("- join_plan пока не проверен")

    lines.append("")

    lines.append("Проверка event log:")

    if validation_report:
        lines.append(f"- статус: {validation_report.get('status')}")
        lines.append(f"- событий: {validation_report.get('total_events')}")
        lines.append(f"- case_id: {validation_report.get('total_cases')}")
        lines.append(f"- уникальных activity: {validation_report.get('unique_activities')}")
        lines.append(f"- пропусков case_id: {validation_report.get('missing_case_id')}")
        lines.append(f"- пропусков activity: {validation_report.get('missing_activity')}")
        lines.append(f"- пропусков timestamp: {validation_report.get('missing_timestamp')}")
        lines.append(f"- дублей событий: {validation_report.get('duplicate_events')}")
        lines.append(f"- case_id с одним событием: {validation_report.get('cases_with_one_event')}")
        lines.append(f"- невалидных дат timestamp: {validation_report.get('invalid_timestamp')}")
        lines.append(
            "- отрицательных длительностей: "
            f"{validation_report.get('negative_duration_events')}"
        )
        lines.append(f"- редких маршрутов: {validation_report.get('rare_routes')}")
        lines.append(
            "- case_id с повторными возвратами: "
            f"{validation_report.get('cases_with_repeated_returns')}"
        )
        lines.append(
            "- outlier-длительностей case: "
            f"{validation_report.get('outlier_case_duration_count')}"
        )
        lines.append(
            "- средняя длительность case, часов: "
            f"{validation_report.get('avg_case_duration_hours')}"
        )
    else:
        lines.append("- event log пока не собран")

    lines.append("")

    lines.append("Файлы сохранены:")

    if output_paths:
        for name, path in output_paths.items():
            lines.append(f"- {name}: {path}")
    else:
        lines.append("- файлы не сохранены")

    if session_path:
        lines.append(f"- session_state: {session_path}")

    return "\n".join(lines)
