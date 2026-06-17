from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    build_join_plan_node,
    build_preview_node,
    classify_tables_node,
    detect_strategies_node,
    evaluate_strategies_node,
    execute_final_node,
    generate_answer_node,
    infer_relationships_node,
    load_session_node,
    parse_requirements_node,
    profile_tables_node,
    reset_session_node,
    route_after_parse,
    route_after_plan_validation,
    save_session_node,
    scan_data_node,
    select_strategy_node,
    validate_join_plan_node,
)
from app.graph.state import EventLogBuildState


def build_event_log_graph():
    graph = StateGraph(EventLogBuildState)

    graph.add_node("load_session", load_session_node)
    graph.add_node("parse_requirements", parse_requirements_node)
    graph.add_node("reset_session", reset_session_node)
    graph.add_node("scan_data", scan_data_node)
    graph.add_node("profile_tables", profile_tables_node)
    graph.add_node("classify_tables", classify_tables_node)
    graph.add_node("infer_relationships", infer_relationships_node)
    graph.add_node("detect_strategies", detect_strategies_node)
    graph.add_node("evaluate_strategies", evaluate_strategies_node)
    graph.add_node("select_strategy", select_strategy_node)
    graph.add_node("build_join_plan", build_join_plan_node)
    graph.add_node("validate_join_plan", validate_join_plan_node)
    graph.add_node("build_preview", build_preview_node)
    graph.add_node("execute_final", execute_final_node)
    graph.add_node("save_session", save_session_node)
    graph.add_node("generate_answer", generate_answer_node)

    graph.add_edge(START, "load_session")
    graph.add_edge("load_session", "parse_requirements")

    graph.add_conditional_edges(
        "parse_requirements",
        route_after_parse,
        {
            "reset_session": "reset_session",
            "scan_data": "scan_data",
            "generate_answer": "generate_answer",
        },
    )

    graph.add_edge("reset_session", "generate_answer")
    graph.add_edge("scan_data", "profile_tables")
    graph.add_edge("profile_tables", "classify_tables")
    graph.add_edge("classify_tables", "infer_relationships")
    graph.add_edge("infer_relationships", "detect_strategies")
    graph.add_edge("detect_strategies", "evaluate_strategies")
    graph.add_edge("evaluate_strategies", "select_strategy")
    graph.add_edge("select_strategy", "build_join_plan")
    graph.add_edge("build_join_plan", "validate_join_plan")

    graph.add_conditional_edges(
        "validate_join_plan",
        route_after_plan_validation,
        {
            "build_preview": "build_preview",
            "execute_final": "execute_final",
        },
    )

    graph.add_edge("build_preview", "save_session")
    graph.add_edge("execute_final", "save_session")
    graph.add_edge("save_session", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()
