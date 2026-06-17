from pathlib import Path

from app.config import DATA_DIR
from app.graph.graph import build_event_log_graph
from app.services.session_service import reset_session_state


class ProcessMiningDataAgent:
    """
    Главный класс агента для Jupyter-чата.

    Логика:
    - общение идет через app/ui/chat_widget.py;
    - управление состояниями идет через LangGraph;
    - агент сам анализирует data/ и строит preview;
    - финальный event_log собирается только после подтверждения.
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
            "user_intent": None,
            "dialog_phase": None,
            "parsed_requirements": None,
            "user_requirements": None,
            "session_warnings": None,
            "files": None,
            "tables_info": None,
            "table_classifications": None,
            "relationships": None,
            "proposed_strategies": None,
            "selected_strategy": None,
            "join_plan": None,
            "join_validation_report": None,
            "preview_event_log": None,
            "preview_validation_report": None,
            "preview_output_paths": None,
            "event_log": None,
            "validation_report": None,
            "output_paths": None,
            "session_path": None,
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
