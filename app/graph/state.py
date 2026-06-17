from typing import Any, TypedDict


class EventLogBuildState(TypedDict):
    user_question: str
    data_dir: str

    session_state: dict[str, Any] | None

    user_intent: str | None
    dialog_phase: str | None

    parsed_requirements: dict[str, Any] | None
    user_requirements: dict[str, Any] | None

    files: list[dict[str, Any]] | None
    tables_info: dict[str, Any] | None
    relationships: list[dict[str, Any]] | None

    proposed_strategies: list[dict[str, Any]] | None
    selected_strategy: dict[str, Any] | None

    join_plan: dict[str, Any] | None
    join_validation_report: dict[str, Any] | None

    preview_event_log: Any | None
    preview_validation_report: dict[str, Any] | None
    preview_output_paths: dict[str, str] | None

    event_log: Any | None
    validation_report: dict[str, Any] | None
    output_paths: dict[str, str] | None

    session_path: str | None
    answer: str | None
