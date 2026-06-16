from pathlib import Path

from app.config import DATA_DIR
from app.graph.graph import build_event_log_graph
from app.services.session_service import reset_session_state


class ProcessMiningDataAgent:
    """
    Главный класс агента для Jupyter-чата.
    """

    def __init__(self, data_dir: str | Path = DATA_DIR):
        self.data_dir = str(data_dir)
        self.graph = build_event_log_graph()
        self.last_state = None

    def run(self, user_question: str) -> str:
        initial_state = {
            "user_question": user_question,
            "data_dir": self.data_dir,

            "session_state": None,
            "parsed_requirements": None,
            "user_requirements": None,
            "agent_iteration": 0,
            "max_agent_iterations": 2,
            "agent_decision": None,
            "agent_decision_history": [],

            "files": None,
            "tables_info": None,

            "relationships": None,
            "join_plan": None,
            "join_validation_report": None,

            "event_log": None,
            "validation_report": None,
            "output_paths": None,
            "session_path": None,
            "llm_response": None,

            "answer": None,
        }

        result = self.graph.invoke(initial_state)

        self.last_state = result

        return result["answer"]

    def get_last_state(self):
        return self.last_state

    def reset_session(self) -> str:
        self.last_state = None
        return reset_session_state()
