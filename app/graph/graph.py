from langgraph.graph import StateGraph, START, END

from app.graph.state import EventLogBuildState
from app.graph.nodes import (
    apply_agent_decision_node,
    build_join_plan_node,
    decide_next_action_node,
    execute_join_plan_node,
    generate_answer_node,
    infer_relationships_node,
    load_session_node,
    parse_requirements_node,
    profile_tables_node,
    validate_event_log_node,
    save_outputs_node,
    save_session_node,
    scan_data_node,
    route_after_agent_decision,
    validate_join_plan_node,
)


def build_event_log_graph():
    graph = StateGraph(EventLogBuildState)

    graph.add_node("load_session", load_session_node)
    graph.add_node("parse_requirements", parse_requirements_node)
    graph.add_node("scan_data", scan_data_node)
    graph.add_node("profile_tables", profile_tables_node)
    graph.add_node("infer_relationships", infer_relationships_node)
    graph.add_node("build_join_plan", build_join_plan_node)
    graph.add_node("validate_join_plan", validate_join_plan_node)
    graph.add_node("execute_join_plan", execute_join_plan_node)
    graph.add_node("validate_event_log", validate_event_log_node)
    graph.add_node("decide_next_action", decide_next_action_node)
    graph.add_node("apply_agent_decision", apply_agent_decision_node)
    graph.add_node("save_outputs", save_outputs_node)
    graph.add_node("save_session", save_session_node)
    graph.add_node("generate_answer", generate_answer_node)

    graph.add_edge(START, "load_session")
    graph.add_edge("load_session", "parse_requirements")
    graph.add_edge("parse_requirements", "scan_data")
    graph.add_edge("scan_data", "profile_tables")
    graph.add_edge("profile_tables", "infer_relationships")
    graph.add_edge("infer_relationships", "build_join_plan")
    graph.add_edge("build_join_plan", "validate_join_plan")
    graph.add_edge("validate_join_plan", "execute_join_plan")
    graph.add_edge("execute_join_plan", "validate_event_log")
    graph.add_edge("validate_event_log", "decide_next_action")
    graph.add_conditional_edges(
        "decide_next_action",
        route_after_agent_decision,
        {
            "apply_agent_decision": "apply_agent_decision",
            "save_outputs": "save_outputs",
        },
    )
    graph.add_edge("apply_agent_decision", "build_join_plan")
    graph.add_edge("save_outputs", "save_session")
    graph.add_edge("save_session", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()
