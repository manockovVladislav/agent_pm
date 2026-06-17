import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import SESSION_STATE_PATH


DEFAULT_SESSION_STATE = {
    "version": 3,
    "phase": "empty",
    "dialog_step": 0,
    "max_dialog_steps": 30,
    "user_requirements": {},
    "files": [],
    "tables_info": {},
    "relationships": [],
    "proposed_strategies": [],
    "selected_strategy": None,
    "last_join_plan": None,
    "last_join_validation_report": None,
    "last_preview_validation_report": None,
    "last_preview_output_paths": None,
    "last_validation_report": None,
    "last_output_paths": None,
    "history": [],
}


def _empty_session_state() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_SESSION_STATE)


def load_session_state(path: str | Path = SESSION_STATE_PATH) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        return _empty_session_state()

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_session_state()

    session_state = _empty_session_state()
    session_state.update(loaded)

    for key, default_value in DEFAULT_SESSION_STATE.items():
        if key not in session_state:
            session_state[key] = copy.deepcopy(default_value)

    return session_state


def save_session_state(
    session_state: dict[str, Any],
    path: str | Path = SESSION_STATE_PATH,
) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            session_state,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return str(path)


def reset_session_state(path: str | Path = SESSION_STATE_PATH) -> str:
    return save_session_state(_empty_session_state(), path)


def merge_user_requirements(
    session_state: dict[str, Any],
    parsed_requirements: dict[str, Any] | None,
) -> dict[str, Any]:
    updated = copy.deepcopy(session_state)
    parsed_requirements = parsed_requirements or {}

    user_requirements = updated.get("user_requirements") or {}

    if "selected_joins" in parsed_requirements:
        old_joins = user_requirements.get("selected_joins") or []
        new_joins = parsed_requirements.get("selected_joins") or []

        parsed_requirements = dict(parsed_requirements)
        parsed_requirements["selected_joins"] = old_joins + new_joins

    user_requirements.update(parsed_requirements)
    updated["user_requirements"] = user_requirements

    return updated


def update_session_after_run(
    session_state: dict[str, Any],
    user_question: str,
    user_intent: str | None,
    parsed_requirements: dict[str, Any] | None,
    files: list[dict[str, Any]] | None,
    tables_info: dict[str, Any] | None,
    relationships: list[dict[str, Any]] | None,
    proposed_strategies: list[dict[str, Any]] | None,
    selected_strategy: dict[str, Any] | None,
    join_plan: dict[str, Any] | None,
    join_validation_report: dict[str, Any] | None,
    preview_validation_report: dict[str, Any] | None,
    preview_output_paths: dict[str, str] | None,
    validation_report: dict[str, Any] | None,
    output_paths: dict[str, str] | None,
) -> dict[str, Any]:
    updated = copy.deepcopy(session_state)

    if files is not None:
        updated["files"] = files

    if tables_info is not None:
        updated["tables_info"] = tables_info

    if relationships is not None:
        updated["relationships"] = relationships

    if proposed_strategies is not None:
        updated["proposed_strategies"] = proposed_strategies

    if selected_strategy is not None:
        updated["selected_strategy"] = selected_strategy

    if join_plan is not None:
        updated["last_join_plan"] = join_plan

    if join_validation_report is not None:
        updated["last_join_validation_report"] = join_validation_report

    if preview_validation_report is not None:
        updated["last_preview_validation_report"] = preview_validation_report

    if preview_output_paths is not None:
        updated["last_preview_output_paths"] = preview_output_paths

    if validation_report is not None:
        updated["last_validation_report"] = validation_report

    if output_paths is not None:
        updated["last_output_paths"] = output_paths

    if user_intent in {"start", "select_strategy", "correct_plan", "preview"}:
        updated["phase"] = "preview_ready"
    elif user_intent == "execute_final":
        updated["phase"] = "result_ready"
    elif user_intent == "reset":
        updated["phase"] = "empty"

    history = updated.get("history") or []
    history.append(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "user_question": user_question,
            "user_intent": user_intent,
            "parsed_requirements": parsed_requirements or {},
            "phase_after": updated.get("phase"),
            "selected_strategy_id": (
                None if not selected_strategy else selected_strategy.get("strategy_id")
            ),
            "join_plan_status": None if not join_plan else join_plan.get("status"),
            "preview_status": (
                None
                if not preview_validation_report
                else preview_validation_report.get("status")
            ),
            "final_status": (
                None if not validation_report else validation_report.get("status")
            ),
        }
    )

    updated["history"] = history[-30:]

    return updated
