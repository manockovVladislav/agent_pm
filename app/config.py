from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"
MEMORY_DIR = BASE_DIR / "app" / "memory"
SESSION_STATE_PATH = MEMORY_DIR / "session_state.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# LLM settings.
# Use "qwen" in production and "cobolt_cpp"/"kobold_cpp" for local tests.
LLM_BACKEND = "cobolt_cpp"
QWEN_MODEL_PATH = str(BASE_DIR / "models" / "qwen3")
KOBOLD_CPP_URL = "http://127.0.0.1:5001/api/v1/generate"
LLM_MAX_NEW_TOKENS = 300
LLM_DECISION_MAX_NEW_TOKENS = 300
KOBOLD_CPP_TIMEOUT_SECONDS = 60

SUPPORTED_TABLE_EXTENSIONS = [
    ".csv",
    ".xlsx",
]
