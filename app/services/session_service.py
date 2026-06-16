import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import SESSION_STATE_PATH


DEFAULT_SESSION_STATE = {
    "version": 1,
    "user_requirements": {},
    "last_join_plan": None,
    "last_join_validation_report": None,
    "last_validation_report": None,
    "last_output_paths": None,
    "last_agent_decision_history": [],
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
    except json.JSONDecodeError:
        return _empty_session_state()

    session_state = _empty_session_state()
    session_state.update(loaded)
    session_state["user_requirements"] = loaded.get("user_requirements") or {}
    session_state["history"] = loaded.get("history") or []

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
    parsed_requirements: dict[str, str],
) -> dict[str, Any]:
    updated = copy.deepcopy(session_state)
    user_requirements = updated.get("user_requirements") or {}
    user_requirements.update(parsed_requirements)
    updated["user_requirements"] = user_requirements

    return updated


def update_session_after_run(
    session_state: dict[str, Any],
    user_question: str,
    parsed_requirements: dict[str, str],
    agent_decision_history: list[dict[str, Any]],
    join_plan: dict | None,
    join_validation_report: dict | None,
    validation_report: dict | None,
    output_paths: dict | None,
) -> dict[str, Any]:
    updated = copy.deepcopy(session_state)

    updated["last_join_plan"] = join_plan
    updated["last_join_validation_report"] = join_validation_report
    updated["last_validation_report"] = validation_report
    updated["last_output_paths"] = output_paths
    updated["last_agent_decision_history"] = agent_decision_history

    history = updated.get("history") or []
    history.append(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "user_question": user_question,
            "parsed_requirements": parsed_requirements,
            "agent_actions": [
                decision.get("action")
                for decision in agent_decision_history
            ],
            "join_plan_status": None if join_plan is None else join_plan.get("status"),
            "join_validation_status": (
                None if join_validation_report is None
                else join_validation_report.get("status")
            ),
            "validation_status": (
                None if validation_report is None
                else validation_report.get("status")
            ),
        }
    )

    updated["history"] = history[-20:]

    return updated
