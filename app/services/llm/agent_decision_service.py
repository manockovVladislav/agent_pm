import json
import re
from typing import Any

from app.config import LLM_BACKEND, LLM_DECISION_MAX_NEW_TOKENS
from app.services.llm.llm_factory import create_llm_service


ALLOWED_ACTIONS = {
    "accept",
    "rebuild_join_plan",
    "ask_user",
}

ALLOWED_REQUIREMENT_KEYS = {
    "plan_mode",
    "activity_source",
    "base_table",
    "case_id",
    "activity",
    "timestamp",
    "start_time",
    "stop_time",
}


def _compact_dict(data: dict | None, keys: list[str]) -> dict:
    if not data:
        return {}

    return {
        key: data.get(key)
        for key in keys
        if key in data
    }


def _table_summary(tables_info: dict) -> dict:
    summary = {}

    for table_name, info in tables_info.items():
        if "error" in info:
            summary[table_name] = {
                "error": info["error"],
            }
            continue

        summary[table_name] = {
            "rows": info.get("rows"),
            "columns": info.get("columns"),
            "candidate_case_id_columns": info.get("candidate_case_id_columns"),
            "candidate_activity_columns": info.get("candidate_activity_columns"),
            "candidate_timestamp_columns": info.get("candidate_timestamp_columns"),
        }

    return summary


def build_agent_decision_prompt(
    user_question: str,
    parsed_requirements: dict | None,
    user_requirements: dict | None,
    tables_info: dict,
    relationships: list[dict],
    join_plan: dict,
    join_validation_report: dict,
    validation_report: dict,
    agent_iteration: int,
    max_agent_iterations: int,
) -> str:
    payload = {
        "user_question": user_question,
        "parsed_requirements": parsed_requirements or {},
        "active_user_requirements": user_requirements or {},
        "agent_iteration": agent_iteration,
        "max_agent_iterations": max_agent_iterations,
        "tables": _table_summary(tables_info),
        "relationships_top": relationships[:10],
        "join_plan": join_plan,
        "join_quality": _compact_dict(
            join_validation_report,
            [
                "status",
                "warnings",
                "errors",
                "total_joins",
                "base_rows",
                "final_rows_after_joins",
            ],
        ),
        "event_log_quality": _compact_dict(
            validation_report,
            [
                "status",
                "error",
                "total_events",
                "total_cases",
                "unique_activities",
                "missing_case_id",
                "missing_activity",
                "missing_timestamp",
                "duplicate_events",
                "negative_duration_events",
                "rare_routes",
                "outlier_case_duration_count",
            ],
        ),
    }

    return "\n".join(
        [
            "Ты управляющий агент сборки event log для process mining.",
            "LangGraph уже посчитал профили таблиц, связи, join_plan и проверки качества.",
            "Твоя задача — выбрать следующий шаг процесса.",
            "",
            "Разрешенные action:",
            "- accept: принять текущий event log и сохранить артефакты.",
            "- rebuild_join_plan: исправить требования к join_plan и пересобрать event log.",
            "- ask_user: остановиться и попросить пользователя уточнить данные.",
            "",
            "Правила:",
            "- Не выдумывай названия таблиц и колонок. Используй только columns из tables.",
            "- Если каждый файл является отдельным событием/этапом, используй requirements: "
            "plan_mode=event_tables_concat, activity_source=table_name.",
            "- Если предлагаешь rebuild_join_plan, заполни requirements только разрешенными ключами: "
            "plan_mode, activity_source, base_table, case_id, activity, timestamp, start_time, stop_time.",
            "- Если не уверен, используй ask_user.",
            "- Если достигнут max_agent_iterations, используй accept или ask_user.",
            "- Верни только JSON без markdown.",
            "",
            "Формат JSON:",
            '{ "action": "accept|rebuild_join_plan|ask_user", '
            '"requirements": {}, "reason": "...", "user_message": "..." }',
            "",
            "Данные:",
            json.dumps(payload, ensure_ascii=False, default=str),
        ]
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    text = str(text or "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        raise ValueError("LLM не вернула JSON-объект.")

    return json.loads(match.group(0))


def _normalize_decision(raw_decision: dict[str, Any]) -> dict[str, Any]:
    action = str(raw_decision.get("action", "ask_user")).strip().lower()

    if action not in ALLOWED_ACTIONS:
        action = "ask_user"

    requirements = raw_decision.get("requirements") or {}

    if not isinstance(requirements, dict):
        requirements = {}

    requirements = {
        str(key): str(value)
        for key, value in requirements.items()
        if key in ALLOWED_REQUIREMENT_KEYS and value not in [None, ""]
    }

    if action == "rebuild_join_plan" and not requirements:
        action = "ask_user"

    return {
        "action": action,
        "requirements": requirements,
        "reason": str(raw_decision.get("reason", "")).strip(),
        "user_message": str(raw_decision.get("user_message", "")).strip(),
    }


def _fallback_decision(
    join_plan: dict,
    join_validation_report: dict,
    validation_report: dict,
) -> dict:
    if join_plan.get("status") != "ok":
        return {
            "backend": "rules",
            "status": "ok",
            "action": "ask_user",
            "requirements": {},
            "reason": join_plan.get("error", "join_plan не построен."),
            "user_message": (
                "Не удалось надежно построить join_plan. "
                "Укажите base_table, case_id, activity и timestamp."
            ),
            "raw_text": "",
            "error": None,
        }

    if validation_report.get("status") == "error":
        return {
            "backend": "rules",
            "status": "ok",
            "action": "ask_user",
            "requirements": {},
            "reason": validation_report.get("error", "event log не прошел проверку."),
            "user_message": (
                "Event log не прошел критическую проверку. "
                "Уточните колонки case_id, activity и timestamp."
            ),
            "raw_text": "",
            "error": None,
        }

    return {
        "backend": "rules",
        "status": "ok",
        "action": "accept",
        "requirements": {},
        "reason": (
            "Критических ошибок нет. "
            f"Статус join_plan: {join_validation_report.get('status')}. "
            f"Статус event_log: {validation_report.get('status')}."
        ),
        "user_message": "Event log собран и проверен.",
        "raw_text": "",
        "error": None,
    }


def decide_next_action(
    user_question: str,
    parsed_requirements: dict | None,
    user_requirements: dict | None,
    tables_info: dict,
    relationships: list[dict],
    join_plan: dict,
    join_validation_report: dict,
    validation_report: dict,
    agent_iteration: int,
    max_agent_iterations: int,
    backend: str | None = None,
) -> dict:
    backend = backend or LLM_BACKEND
    normalized_backend = str(backend).strip().lower().replace("-", "_")

    if normalized_backend in {"", "none", "off", "disabled", "false"}:
        return _fallback_decision(
            join_plan=join_plan,
            join_validation_report=join_validation_report,
            validation_report=validation_report,
        )

    if agent_iteration >= max_agent_iterations:
        fallback = _fallback_decision(
            join_plan=join_plan,
            join_validation_report=join_validation_report,
            validation_report=validation_report,
        )
        fallback["reason"] = (
            f"Достигнут лимит итераций агента: {max_agent_iterations}. "
            f"{fallback['reason']}"
        )
        return fallback

    prompt = build_agent_decision_prompt(
        user_question=user_question,
        parsed_requirements=parsed_requirements,
        user_requirements=user_requirements,
        tables_info=tables_info,
        relationships=relationships,
        join_plan=join_plan,
        join_validation_report=join_validation_report,
        validation_report=validation_report,
        agent_iteration=agent_iteration,
        max_agent_iterations=max_agent_iterations,
    )

    try:
        llm = create_llm_service(backend=backend)
        raw_text = llm.generate(
            prompt,
            max_new_tokens=LLM_DECISION_MAX_NEW_TOKENS,
        )
        raw_decision = _extract_json_object(raw_text)
        decision = _normalize_decision(raw_decision)
    except Exception as error:
        fallback = _fallback_decision(
            join_plan=join_plan,
            join_validation_report=join_validation_report,
            validation_report=validation_report,
        )
        fallback["backend"] = backend
        fallback["status"] = "fallback"
        fallback["error"] = str(error)
        return fallback

    return {
        "backend": backend,
        "status": "ok",
        "raw_text": raw_text,
        "error": None,
        **decision,
    }
