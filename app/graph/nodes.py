from app.services.answer_service import build_final_answer
from app.services.event_log_builder import (
    build_event_log_from_joined_df,
    execute_event_tables_concat_plan,
    execute_join_plan,
)
from app.services.file_service import scan_data_directory
from app.services.join_plan_service import build_join_plan
from app.services.join_validation_service import validate_join_plan
from app.services.output_service import save_outputs
from app.services.preview_service import (
    build_preview_event_log,
    save_preview_outputs,
    validate_preview_event_log,
)
from app.services.relationship_service import infer_relationships
from app.services.requirements_parser import parse_user_requirements
from app.services.session_service import (
    build_data_fingerprint,
    load_session_state,
    merge_user_requirements,
    reset_session_state,
    save_session_state,
    update_session_after_run,
)
from app.services.strategy_detector import (
    detect_strategies,
    strategy_to_user_requirements,
)
from app.services.table_classifier import classify_tables
from app.services.table_profiler import profile_tables
from app.services.validation_service import validate_event_log


START_WORDS = [
    "помоги собрать лог",
    "собрать лог",
    "собери лог",
    "лог событий",
    "event log",
    "посмотри data",
    "проанализируй data",
    "начать",
]

RESET_WORDS = [
    "reset",
    "сброс",
    "сбросить",
    "начать заново",
    "очистить сессию",
]

CONFIRM_WORDS = [
    "подтверждаю",
    "выполни",
    "запускай",
    "собирай финально",
    "собрать финально",
    "финально",
    "результат корректен",
    "да, корректно",
    "да корректно",
    "ок",
    "ok",
    "да",
]

PREVIEW_WORDS = [
    "preview",
    "превью",
    "предпросмотр",
    "покажи пример",
    "сделай preview",
]

WHY_WORDS = [
    "почему",
    "объясни",
    "поясни",
    "why",
]

COMPARE_WORDS = [
    "сравни стратегии",
    "сравнить стратегии",
    "compare strategies",
    "compare",
]

CORRECTION_WORDS = [
    "case_id",
    "activity",
    "timestamp",
    "base_table",
    "mode",
    "join",
    "джойн",
    "приджойн",
    "не используй",
    "исправь",
    "замени",
]


def _has_any(text: str, words: list[str]) -> bool:
    text = str(text).strip().lower()

    return any(word in text for word in words)


def _classify_intent(
    user_question: str,
    parsed_requirements: dict,
    session_state: dict,
) -> str:
    text = str(user_question).strip().lower()
    phase = session_state.get("phase", "empty")

    if _has_any(text, RESET_WORDS):
        return "reset"

    if _has_any(text, START_WORDS):
        return "start"

    if parsed_requirements.get("selected_strategy_number"):
        return "select_strategy"

    if parsed_requirements:
        return "correct_plan"

    if _has_any(text, PREVIEW_WORDS):
        return "preview"

    if _has_any(text, COMPARE_WORDS):
        return "compare_strategies"

    if _has_any(text, WHY_WORDS):
        return "explain_choice"

    if _has_any(text, CONFIRM_WORDS):
        if phase == "preview_ready":
            return "execute_final"

        return "preview"

    if _has_any(text, CORRECTION_WORDS):
        return "correct_plan"

    if phase in {None, "empty"}:
        return "start"

    return "unknown"


def load_session_node(state):
    session_state = load_session_state()

    return {
        "session_state": session_state,
        "dialog_phase": session_state.get("phase", "empty"),
        "user_requirements": session_state.get("user_requirements") or {},
        "proposed_strategies": session_state.get("proposed_strategies") or [],
        "selected_strategy": session_state.get("selected_strategy"),
        "table_classifications": session_state.get("table_classifications") or {},
        "join_plan": session_state.get("last_join_plan"),
        "join_validation_report": session_state.get("last_join_validation_report"),
        "preview_validation_report": session_state.get("last_preview_validation_report"),
        "preview_output_paths": session_state.get("last_preview_output_paths"),
        "validation_report": session_state.get("last_validation_report"),
        "output_paths": session_state.get("last_output_paths"),
    }


def parse_requirements_node(state):
    parsed_requirements = parse_user_requirements(state["user_question"])
    session_state = state["session_state"]
    user_intent = _classify_intent(
        user_question=state["user_question"],
        parsed_requirements=parsed_requirements,
        session_state=session_state,
    )

    if user_intent == "reset":
        return {
            "parsed_requirements": parsed_requirements,
            "user_intent": user_intent,
        }

    dialog_step = int(session_state.get("dialog_step") or 0) + 1
    session_state["dialog_step"] = dialog_step

    if dialog_step > int(session_state.get("max_dialog_steps") or 30):
        session_state["phase"] = "stopped"
        return {
            "session_state": session_state,
            "parsed_requirements": parsed_requirements,
            "user_intent": "unknown",
            "answer": (
                "Достигнут лимит 30 шагов диалога. "
                "Чтобы начать заново, напиши `сбросить`."
            ),
        }

    if user_intent in {"correct_plan", "select_strategy"}:
        session_state = merge_user_requirements(
            session_state=session_state,
            parsed_requirements=parsed_requirements,
        )

    return {
        "session_state": session_state,
        "parsed_requirements": parsed_requirements,
        "user_requirements": session_state.get("user_requirements") or {},
        "user_intent": user_intent,
        "dialog_phase": session_state.get("phase", "empty"),
    }


def route_after_parse(state):
    if state.get("answer"):
        return "generate_answer"

    if state.get("user_intent") == "reset":
        return "reset_session"

    if state.get("user_intent") in {"unknown", "compare_strategies", "explain_choice"}:
        return "generate_answer"

    return "scan_data"


def reset_session_node(state):
    session_path = reset_session_state()

    return {
        "answer": (
            "Сессия сброшена. Можно начать заново: "
            "`помоги собрать лог`."
        ),
        "session_path": session_path,
    }


def scan_data_node(state):
    files = scan_data_directory(state["data_dir"])
    session_state = dict(state.get("session_state") or {})
    current_fingerprint = build_data_fingerprint(files)
    previous_fingerprint = session_state.get("data_fingerprint")
    session_warnings = list(state.get("session_warnings") or [])

    if previous_fingerprint and previous_fingerprint != current_fingerprint:
        session_state["user_requirements"] = {}
        session_state["selected_strategy"] = None
        session_state["last_join_plan"] = None
        session_state["last_join_validation_report"] = None
        session_state["last_preview_validation_report"] = None
        session_state["last_preview_output_paths"] = None
        session_state["last_validation_report"] = None
        session_state["last_output_paths"] = None
        session_state["phase"] = "empty"

        warning = (
            "Файлы в `data/` изменились, поэтому старые требования сессии "
            "сброшены перед новым анализом."
        )
        session_state["data_warning"] = warning
        session_warnings.append(warning)
    else:
        session_state["data_warning"] = None

    session_state["data_fingerprint"] = current_fingerprint

    return {
        "files": files,
        "session_state": session_state,
        "user_requirements": session_state.get("user_requirements") or {},
        "session_warnings": session_warnings,
    }


def profile_tables_node(state):
    tables_info = profile_tables(state["files"])

    return {
        "tables_info": tables_info,
    }


def classify_tables_node(state):
    table_classifications = classify_tables(state["tables_info"])

    return {
        "table_classifications": table_classifications,
    }


def infer_relationships_node(state):
    relationships = infer_relationships(
        tables_info=state["tables_info"],
    )

    return {
        "relationships": relationships,
    }


def detect_strategies_node(state):
    strategies = detect_strategies(
        tables_info=state["tables_info"],
        relationships=state["relationships"],
        table_classifications=state.get("table_classifications") or {},
    )

    return {
        "proposed_strategies": strategies,
    }


def _score_preview_report(report: dict | None) -> int:
    if not report or report.get("status") == "error":
        return 0

    total_events = int(report.get("total_events") or 0)
    total_cases = int(report.get("total_cases") or 0)
    unique_activities = int(report.get("unique_activities") or 0)
    missing_case_id = int(report.get("missing_case_id") or 0)
    missing_activity = int(report.get("missing_activity") or 0)
    missing_timestamp = int(report.get("missing_timestamp") or 0)
    invalid_timestamp = int(report.get("invalid_timestamp") or 0)
    duplicate_events = int(report.get("duplicate_events") or 0)
    one_event_cases = int(report.get("cases_with_one_event") or 0)
    same_timestamp_cases = int(report.get("cases_with_same_timestamp_multi_activity") or 0)

    score = 0

    if total_events > 0:
        score += 20

    if total_cases > 0:
        score += 20

    if unique_activities >= 2:
        score += 20
    elif unique_activities == 1:
        score -= 10

    if total_cases:
        avg_events_per_case = total_events / total_cases

        if 2 <= avg_events_per_case <= 100:
            score += 20
        elif avg_events_per_case < 2:
            score -= 10
        else:
            score -= 15

        one_event_ratio = one_event_cases / total_cases

        if one_event_ratio > 0.5:
            score -= 15
        elif one_event_ratio > 0.25:
            score -= 7

    error_count = (
        missing_case_id
        + missing_activity
        + missing_timestamp
        + invalid_timestamp
        + duplicate_events
    )

    if error_count == 0:
        score += 25
    else:
        score -= min(error_count * 4, 45)

    if same_timestamp_cases:
        score -= min(same_timestamp_cases * 6, 30)

    if report.get("status") == "warning":
        score -= 5

    return max(0, min(score, 100))


def _strategy_assumptions(strategy: dict, join_plan: dict | None) -> list[str]:
    assumptions = []

    if strategy.get("strategy_id") == "event_tables_concat":
        assumptions.append("каждая выбранная таблица является отдельным типом события")
        assumptions.append("activity берется из имени таблицы")
        assumptions.append("case_id должен связывать события между таблицами")
    else:
        base_table = strategy.get("base_table") or strategy.get("table")
        assumptions.append(f"`{base_table}` считается основной таблицей событий")
        assumptions.append(f"`{strategy.get('case_id')}` считается case_id")
        assumptions.append(f"`{strategy.get('activity')}` считается activity")
        assumptions.append(f"`{strategy.get('timestamp')}` считается timestamp")

    if join_plan and not join_plan.get("joins"):
        assumptions.append("найденные связи не применены автоматически, они только подсказки")

    return assumptions


def _execute_event_log_from_plan(
    join_plan: dict,
    join_validation_report: dict,
    tables_info: dict,
):
    if not join_plan:
        raise ValueError("join_plan отсутствует")

    if join_plan.get("status") != "ok":
        raise ValueError(f"join_plan некорректен: {join_plan.get('error')}")

    if join_validation_report.get("status") == "error":
        raise ValueError(
            "join_plan содержит ошибки: "
            f"{join_validation_report.get('errors')}"
        )

    if join_plan.get("mode") == "event_tables_concat":
        return execute_event_tables_concat_plan(
            join_plan=join_plan,
            tables_info=tables_info,
        )

    joined_df = execute_join_plan(
        join_plan=join_plan,
        tables_info=tables_info,
    )

    return build_event_log_from_joined_df(
        joined_df=joined_df,
        join_plan=join_plan,
    )


def evaluate_strategies_node(state):
    evaluated = []
    base_requirements = dict(state.get("user_requirements") or {})

    for strategy in (state.get("proposed_strategies") or [])[:5]:
        candidate = dict(strategy)
        candidate_requirements = strategy_to_user_requirements(candidate)
        candidate_requirements.update(base_requirements)

        join_plan = build_join_plan(
            tables_info=state["tables_info"],
            relationships=state["relationships"],
            user_requirements=candidate_requirements,
        )
        join_validation_report = validate_join_plan(
            join_plan=join_plan,
            tables_info=state["tables_info"],
        )

        preview_report = {
            "status": "error",
            "error": "preview не был построен",
        }

        try:
            event_log = _execute_event_log_from_plan(
                join_plan=join_plan,
                join_validation_report=join_validation_report,
                tables_info=state["tables_info"],
            )
            preview_event_log = build_preview_event_log(
                event_log=event_log,
                max_rows=1000,
                max_cases=100,
            )
            preview_report = validate_preview_event_log(preview_event_log)
        except Exception as error:
            preview_report = {
                "status": "error",
                "error": str(error),
            }

        preview_score = _score_preview_report(preview_report)
        candidate["preview_score"] = preview_score
        candidate["preview_status"] = preview_report.get("status")
        candidate["preview_metrics"] = {
            "events": preview_report.get("total_events"),
            "cases": preview_report.get("total_cases"),
            "activities": preview_report.get("unique_activities"),
            "missing_timestamp": preview_report.get("missing_timestamp"),
            "invalid_timestamp": preview_report.get("invalid_timestamp"),
            "duplicates": preview_report.get("duplicate_events"),
            "one_event_cases": preview_report.get("cases_with_one_event"),
            "same_timestamp_cases": preview_report.get("cases_with_same_timestamp_multi_activity"),
        }
        candidate["preview_error"] = preview_report.get("error")
        candidate["join_plan_status"] = join_plan.get("status")
        candidate["join_validation_status"] = join_validation_report.get("status")
        candidate["assumptions"] = _strategy_assumptions(candidate, join_plan)

        evaluated.append(candidate)

    evaluated = sorted(
        evaluated,
        key=lambda item: (item.get("preview_score") or 0, item.get("confidence") or 0),
        reverse=True,
    )

    for index, strategy in enumerate(evaluated, start=1):
        strategy["number"] = index
        strategy["recommended"] = index == 1

    return {
        "proposed_strategies": evaluated[:5],
    }


def select_strategy_node(state):
    strategies = state.get("proposed_strategies") or []
    session_state = state.get("session_state") or {}
    parsed_requirements = state.get("parsed_requirements") or {}
    user_requirements = dict(state.get("user_requirements") or {})
    selected_strategy = None
    selected_number = parsed_requirements.get("selected_strategy_number")

    if selected_number:
        for strategy in strategies:
            if int(strategy.get("number") or 0) == int(selected_number):
                selected_strategy = strategy
                break

    if selected_strategy is None and session_state.get("selected_strategy"):
        old_strategy = session_state.get("selected_strategy")

        for strategy in strategies:
            if strategy.get("strategy_key") == old_strategy.get("strategy_key"):
                selected_strategy = strategy
                break

    if selected_strategy is None and strategies:
        selected_strategy = strategies[0]

    if selected_strategy:
        strategy_requirements = strategy_to_user_requirements(selected_strategy)
        strategy_requirements.update(user_requirements)
        user_requirements = strategy_requirements

    return {
        "selected_strategy": selected_strategy,
        "user_requirements": user_requirements,
    }


def build_join_plan_node(state):
    join_plan = build_join_plan(
        tables_info=state["tables_info"],
        relationships=state["relationships"],
        user_requirements=state.get("user_requirements") or {},
    )

    return {
        "join_plan": join_plan,
    }


def validate_join_plan_node(state):
    join_plan = state.get("join_plan")

    if not join_plan:
        return {
            "join_validation_report": {
                "status": "error",
                "errors": ["join_plan отсутствует"],
                "warnings": [],
                "checks": [],
            }
        }

    join_validation_report = validate_join_plan(
        join_plan=join_plan,
        tables_info=state["tables_info"],
    )

    return {
        "join_validation_report": join_validation_report,
    }


def _build_event_log_from_plan(state):
    return _execute_event_log_from_plan(
        join_plan=state.get("join_plan"),
        join_validation_report=state.get("join_validation_report") or {},
        tables_info=state["tables_info"],
    )


def build_preview_node(state):
    try:
        full_event_log = _build_event_log_from_plan(state)
        preview_event_log = build_preview_event_log(
            event_log=full_event_log,
            max_rows=1000,
            max_cases=100,
        )
    except Exception as error:
        return {
            "preview_event_log": None,
            "preview_validation_report": {
                "status": "error",
                "error": str(error),
            },
            "preview_output_paths": None,
        }

    preview_validation_report = validate_preview_event_log(preview_event_log)
    preview_output_paths = save_preview_outputs(
        preview_event_log=preview_event_log,
        preview_validation_report=preview_validation_report,
    )

    return {
        "preview_event_log": preview_event_log,
        "preview_validation_report": preview_validation_report,
        "preview_output_paths": preview_output_paths,
    }


def execute_final_node(state):
    try:
        event_log = _build_event_log_from_plan(state)
    except Exception as error:
        return {
            "event_log": None,
            "validation_report": {
                "status": "error",
                "error": str(error),
            },
            "output_paths": None,
        }

    validation_report = validate_event_log(event_log)
    output_paths = save_outputs(
        event_log=event_log,
        join_plan=state["join_plan"],
        join_validation_report=state["join_validation_report"],
        validation_report=validation_report,
        relationships=state["relationships"],
    )

    return {
        "event_log": event_log,
        "validation_report": validation_report,
        "output_paths": output_paths,
    }


def route_after_plan_validation(state):
    if state.get("user_intent") == "execute_final":
        return "execute_final"

    return "build_preview"


def save_session_node(state):
    session_state = state["session_state"]
    session_state = update_session_after_run(
        session_state=session_state,
        user_question=state["user_question"],
        user_intent=state.get("user_intent"),
        parsed_requirements=state.get("parsed_requirements"),
        files=state.get("files"),
        tables_info=state.get("tables_info"),
        table_classifications=state.get("table_classifications"),
        relationships=state.get("relationships"),
        proposed_strategies=state.get("proposed_strategies"),
        selected_strategy=state.get("selected_strategy"),
        join_plan=state.get("join_plan"),
        join_validation_report=state.get("join_validation_report"),
        preview_validation_report=state.get("preview_validation_report"),
        preview_output_paths=state.get("preview_output_paths"),
        validation_report=state.get("validation_report"),
        output_paths=state.get("output_paths"),
        data_fingerprint=build_data_fingerprint(state.get("files")),
        data_warning=(state.get("session_warnings") or [None])[-1],
    )

    session_path = save_session_state(session_state)

    return {
        "session_state": session_state,
        "session_path": session_path,
        "dialog_phase": session_state.get("phase"),
    }


def generate_answer_node(state):
    if state.get("answer"):
        return {
            "answer": state["answer"],
        }

    answer = build_final_answer(
        user_question=state["user_question"],
        user_intent=state.get("user_intent"),
        dialog_phase=state.get("dialog_phase"),
        parsed_requirements=state.get("parsed_requirements"),
        user_requirements=state.get("user_requirements"),
        files=state.get("files") or [],
        tables_info=state.get("tables_info") or {},
        table_classifications=state.get("table_classifications") or {},
        relationships=state.get("relationships") or [],
        proposed_strategies=state.get("proposed_strategies") or [],
        selected_strategy=state.get("selected_strategy"),
        join_plan=state.get("join_plan"),
        join_validation_report=state.get("join_validation_report"),
        preview_validation_report=state.get("preview_validation_report"),
        preview_output_paths=state.get("preview_output_paths"),
        validation_report=state.get("validation_report"),
        output_paths=state.get("output_paths"),
        session_warnings=state.get("session_warnings") or [],
        session_path=state.get("session_path"),
    )

    return {
        "answer": answer,
    }
