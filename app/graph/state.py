from typing import TypedDict, Optional, Any


class EventLogBuildState(TypedDict):
    user_question: str
    data_dir: str

    session_state: Optional[dict[str, Any]]
    parsed_requirements: Optional[dict[str, str]]
    user_requirements: Optional[dict[str, str]]
    agent_iteration: int
    max_agent_iterations: int
    agent_decision: Optional[dict[str, Any]]
    agent_decision_history: Optional[list[dict[str, Any]]]

    files: Optional[list[dict[str, Any]]]
    tables_info: Optional[dict[str, Any]]

    relationships: Optional[list[dict[str, Any]]]
    join_plan: Optional[dict[str, Any]]
    join_validation_report: Optional[dict[str, Any]]

    event_log: Optional[Any]
    validation_report: Optional[dict[str, Any]]
    output_paths: Optional[dict[str, str]]
    session_path: Optional[str]
    llm_response: Optional[dict[str, Any]]

    answer: Optional[str]
