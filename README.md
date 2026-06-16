# Process Mining Event Log Agent

Jupyter-based agent for building and validating an event log from CSV/XLSX tables.

The main artifact is `outputs/join_plan.json`: it records how the event log was assembled, can be reviewed, corrected, repeated, and explained.

## Project Structure

```text
agent_pm/
├── demo.ipynb
├── data/
├── outputs/
├── app/
│   ├── agent.py
│   ├── config.py
│   ├── graph/
│   ├── memory/
│   ├── services/
│   ├── ui/
│   └── visualization/
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

Put source `.csv` or `.xlsx` files into `data/`.

Run `demo.ipynb` and start the chat:

```python
from app.agent import ProcessMiningDataAgent
from app.ui.chat_widget import AgentChatWidget


agent = ProcessMiningDataAgent(data_dir="data")

chat = AgentChatWidget(
    agent_func=agent.run,
    title="Агент сборки event log",
    description="Положите таблицы в data и задайте требования",
)

chat.show()
```

## LLM Configuration

All LLM settings live in `app/config.py`.

```python
LLM_BACKEND = "cobolt_cpp"
QWEN_MODEL_PATH = str(BASE_DIR / "models" / "qwen3")
KOBOLD_CPP_URL = "http://127.0.0.1:5001/api/v1/generate"
LLM_MAX_NEW_TOKENS = 300
LLM_DECISION_MAX_NEW_TOKENS = 300
KOBOLD_CPP_TIMEOUT_SECONDS = 60
```

Use local Cobolt/KoboldCpp for testing:

```python
LLM_BACKEND = "cobolt_cpp"
```

Use Qwen for production-style local inference:

```python
LLM_BACKEND = "qwen"
QWEN_MODEL_PATH = "/path/to/qwen3"
```

Qwen and Cobolt use the same internal interface:

```python
generate(prompt: str, max_new_tokens: int) -> str
```

## Agent Flow

LangGraph controls the workflow. Pandas does the data work. The LLM makes a structured decision after quality checks.

Current graph:

```text
START
  -> load_session
  -> parse_requirements
  -> scan_data
  -> profile_tables
  -> infer_relationships
  -> build_join_plan
  -> validate_join_plan
  -> execute_join_plan
  -> validate_event_log
  -> decide_next_action
      -> apply_agent_decision -> build_join_plan
      -> save_outputs
  -> save_session
  -> generate_answer
END
```

The loop is bounded by `max_agent_iterations` so the agent cannot rebuild forever.

## Agent Decisions

The LLM is not used for joins or calculations. It is used to choose the next process action.

The decision node asks the model for strict JSON:

```json
{
  "action": "accept",
  "requirements": {},
  "reason": "Критических ошибок нет.",
  "user_message": "Event log собран и проверен."
}
```

Allowed actions:

```text
accept
rebuild_join_plan
ask_user
```

If `action = rebuild_join_plan`, the model may return corrected requirements:

```json
{
  "action": "rebuild_join_plan",
  "requirements": {
    "base_table": "orders.csv",
    "case_id": "case_id",
    "activity": "status",
    "timestamp": "updated_at"
  },
  "reason": "Текущий join_plan дал many-to-many рост строк.",
  "user_message": "Пересобираю event log с другой базовой таблицей."
}
```

Then LangGraph applies these requirements and returns to `build_join_plan`.

If `action = ask_user`, the agent stops the rebuild loop and returns a user-facing clarification request.

If the model is unavailable or returns invalid JSON, the system falls back to deterministic rules.

## State and Memory

The active graph state is defined in `app/graph/state.py`.

Important fields:

```text
user_question              raw user query
session_state              loaded session memory
parsed_requirements        explicit requirements parsed from user text
user_requirements          active requirements after session merge
agent_iteration            current rebuild iteration
max_agent_iterations       rebuild limit
agent_decision             latest structured model/rules decision
agent_decision_history     list of decisions in this run
files                      scanned source files
tables_info                table profiles
relationships              inferred table relationships
join_plan                  current join plan
join_validation_report     join quality checks
event_log                  pandas DataFrame
validation_report          event log quality checks
output_paths               saved artifacts
session_path               memory path
answer                     final chat answer
```

Session memory is stored in:

```text
app/memory/session_state.json
```

It stores the last plan, reports, outputs, active requirements, and decision history.

The session is not reset automatically before every request. This is intentional:
user corrections such as `case_id бери из application_id` must survive into the
next graph run. Reset the session only when starting an independent scenario,
changing the dataset, or preparing a clean demo:

```python
agent.reset_session()
```

`app/memory/session_state.json` is runtime state and is excluded from git.

## How "Reasoning" Is Represented

The system does not store or expose hidden chain-of-thought.

Instead, it stores structured operational reasoning:

```json
{
  "action": "accept",
  "requirements": {},
  "reason": "Критических ошибок нет. Статус join_plan: warning. Статус event_log: ok.",
  "user_message": "Event log собран и проверен."
}
```

This is the agent's auditable decision record:

- what it decided;
- which requirements it changed, if any;
- why it made that decision;
- what message should be shown to the user.

Decision records are available in:

```python
agent.get_last_state()["agent_decision"]
agent.get_last_state()["agent_decision_history"]
```

And persisted in:

```json
app/memory/session_state.json
```

## User Corrections

The user can correct requirements in chat:

```text
Нет, case_id бери из application_id, activity из operation_name, timestamp из created_at.
```

The rule-based parser extracts obvious field assignments. The agent then merges them into session requirements and rebuilds the event log.

Supported requirement keys:

```text
base_table
case_id
activity
timestamp
```

## Outputs

Generated files are saved to `outputs/`.

Important outputs:

```text
join_plan.json
join_quality_report.json
relationships.json
quality_report.json
event_log.xlsx
event_log_preview.xlsx
quality_report.xlsx
join_quality_report.xlsx
process_graph.html
```

`join_plan.json` is the primary artifact for review and correction.

## Quality Checks

Join checks:

- row growth after join;
- many-to-many joins;
- row loss after join;
- duplicate join keys;
- missing join keys.

Event log checks:

- required columns;
- missing `case_id`, `activity`, `timestamp`;
- invalid dates;
- duplicate events;
- negative durations;
- cases with one event;
- missing common stages;
- repeated returns;
- rare routes;
- duration outliers.

## Process Graph

After `event_log.xlsx` is built:

```python
import pandas as pd

from app.visualization.process_graph_viewer import ProcessGraphViewer


df = pd.read_excel("outputs/event_log.xlsx")

viewer = ProcessGraphViewer(
    df=df,
    case_id_col="case_id",
    event_col="activity",
    start_time_col="start_time",
    stop_time_col="stop_time",
    output_dir="outputs",
    filename="process_graph.html",
    layout_mode="hierarchical",
    node_spacing=140,
    level_separation=110,
)

viewer.show()
```

The graph is top-to-bottom and shows operation counts in node labels. Edge labels show transition counts.

## Notes

- `join_plan.json` is more important than a single generated `event_log.xlsx`.
- The LLM should return structured JSON for decisions.
- Pandas remains responsible for all deterministic data operations.
- Jupyter is the operator interface, not the business logic layer.
