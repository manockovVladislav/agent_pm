from app.services.file_service import scan_data_directory
from app.services.table_profiler import profile_tables
from app.services.relationship_service import infer_relationships
from app.services.join_plan_service import build_join_plan
from app.services.join_validation_service import validate_join_plan
from app.services.requirements_parser import parse_user_requirements
from app.services.session_service import (
    load_session_state,
    merge_user_requirements,
    save_session_state,
    update_session_after_run,
)
from app.services.event_log_builder import (
    execute_join_plan,
    build_event_log_from_joined_df,
    execute_event_tables_concat_plan,
)
from app.services.validation_service import validate_event_log
from app.services.output_service import save_outputs
from app.services.answer_service import build_final_answer
from app.services.llm.agent_decision_service import decide_next_action


def load_session_node(state):
    session_state = load_session_state()

    return {
        "session_state": session_state,
        "user_requirements": session_state.get("user_requirements") or {},
    }


def parse_requirements_node(state):
    parsed_requirements = parse_user_requirements(state["user_question"])
    session_state = merge_user_requirements(
        session_state=state["session_state"],
        parsed_requirements=parsed_requirements,
    )

    return {
        "session_state": session_state,
        "parsed_requirements": parsed_requirements,
        "user_requirements": session_state.get("user_requirements") or {},
    }


def scan_data_node(state):
    files = scan_data_directory(state["data_dir"])

    return {
        "files": files,
    }


def profile_tables_node(state):
    tables_info = profile_tables(state["files"])

    return {
        "tables_info": tables_info,
    }


def infer_relationships_node(state):
    relationships = infer_relationships(
        tables_info=state["tables_info"],
    )

    return {
        "relationships": relationships,
    }


def build_join_plan_node(state):
    join_plan = build_join_plan(
        tables_info=state["tables_info"],
        relationships=state["relationships"],
        user_requirements=state.get("user_requirements"),
    )

    return {
        "join_plan": join_plan,
    }


def validate_join_plan_node(state):
    join_validation_report = validate_join_plan(
        join_plan=state["join_plan"],
        tables_info=state["tables_info"],
    )

    return {
        "join_validation_report": join_validation_report,
    }


def execute_join_plan_node(state):
    join_plan = state["join_plan"]

    if join_plan.get("status") != "ok":
        return {
            "event_log": None,
        }

    try:
        if join_plan.get("mode") == "event_tables_concat":
            event_log = execute_event_tables_concat_plan(
                join_plan=join_plan,
                tables_info=state["tables_info"],
            )
        else:
            joined_df = execute_join_plan(
                join_plan=join_plan,
                tables_info=state["tables_info"],
            )

            event_log = build_event_log_from_joined_df(
                joined_df=joined_df,
                join_plan=join_plan,
            )
    except Exception as error:
        return {
            "event_log": None,
            "validation_report": {
                "status": "error",
                "error": str(error),
            },
        }

    return {
        "event_log": event_log,
    }


def validate_event_log_node(state):
    event_log = state["event_log"]

    if event_log is None:
        validation_report = state.get("validation_report")

        if validation_report:
            return {
                "validation_report": validation_report,
            }

        return {
            "validation_report": {
                "status": "error",
                "error": "Event log не был собран.",
            }
        }

    validation_report = validate_event_log(event_log)

    return {
        "validation_report": validation_report,
    }


def decide_next_action_node(state):
    agent_decision = decide_next_action(
        user_question=state["user_question"],
        parsed_requirements=state["parsed_requirements"],
        user_requirements=state["user_requirements"],
        tables_info=state["tables_info"],
        relationships=state["relationships"],
        join_plan=state["join_plan"],
        join_validation_report=state["join_validation_report"],
        validation_report=state["validation_report"],
        agent_iteration=state["agent_iteration"],
        max_agent_iterations=state["max_agent_iterations"],
    )

    history = list(state.get("agent_decision_history") or [])
    history.append(agent_decision)

    return {
        "agent_decision": agent_decision,
        "agent_decision_history": history,
    }


def apply_agent_decision_node(state):
    agent_decision = state["agent_decision"] or {}
    decision_requirements = agent_decision.get("requirements") or {}
    user_requirements = dict(state.get("user_requirements") or {})
    user_requirements.update(decision_requirements)

    session_state = merge_user_requirements(
        session_state=state["session_state"],
        parsed_requirements=decision_requirements,
    )

    return {
        "session_state": session_state,
        "user_requirements": user_requirements,
        "agent_iteration": state["agent_iteration"] + 1,
        "event_log": None,
        "validation_report": None,
        "output_paths": None,
        "join_validation_report": None,
    }


def route_after_agent_decision(state):
    agent_decision = state.get("agent_decision") or {}
    action = agent_decision.get("action")
    requirements = agent_decision.get("requirements") or {}
    current_requirements = state.get("user_requirements") or {}
    requirements_changed = any(
        current_requirements.get(key) != value
        for key, value in requirements.items()
    )

    if (
        action == "rebuild_join_plan"
        and requirements
        and requirements_changed
        and state["agent_iteration"] < state["max_agent_iterations"]
    ):
        return "apply_agent_decision"

    return "save_outputs"


def save_outputs_node(state):
    output_paths = save_outputs(
        event_log=state["event_log"],
        join_plan=state["join_plan"],
        join_validation_report=state["join_validation_report"],
        validation_report=state["validation_report"],
        relationships=state["relationships"],
    )

    return {
        "output_paths": output_paths,
    }


def save_session_node(state):
    session_state = update_session_after_run(
        session_state=state["session_state"],
        user_question=state["user_question"],
        parsed_requirements=state["parsed_requirements"] or {},
        agent_decision_history=state["agent_decision_history"] or [],
        join_plan=state["join_plan"],
        join_validation_report=state["join_validation_report"],
        validation_report=state["validation_report"],
        output_paths=state["output_paths"],
    )

    session_path = save_session_state(session_state)

    return {
        "session_state": session_state,
        "session_path": session_path,
    }


def generate_answer_node(state):
    answer = build_final_answer(
        user_question=state["user_question"],
        parsed_requirements=state["parsed_requirements"],
        user_requirements=state["user_requirements"],
        agent_decision=state["agent_decision"],
        agent_decision_history=state["agent_decision_history"],
        files=state["files"],
        tables_info=state["tables_info"],
        relationships=state["relationships"],
        join_plan=state["join_plan"],
        join_validation_report=state["join_validation_report"],
        validation_report=state["validation_report"],
        output_paths=state["output_paths"],
        session_path=state["session_path"],
    )

    return {
        "answer": answer,
    }
