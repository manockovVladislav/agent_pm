from pathlib import Path

import pandas as pd

from app.config import OUTPUTS_DIR
from app.services.output_service import save_json
from app.services.validation_service import validate_event_log


def build_preview_event_log(
    event_log: pd.DataFrame | None,
    max_rows: int = 1000,
    max_cases: int = 100,
) -> pd.DataFrame | None:
    if event_log is None:
        return None

    if event_log.empty:
        return event_log.copy()

    if "case_id" not in event_log.columns:
        return event_log.head(max_rows).copy()

    case_ids = (
        event_log["case_id"]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .head(max_cases)
        .tolist()
    )

    if not case_ids:
        return event_log.head(max_rows).copy()

    preview = event_log[
        event_log["case_id"].astype(str).isin(case_ids)
    ].copy()

    return preview.head(max_rows).reset_index(drop=True)


def save_preview_outputs(
    preview_event_log: pd.DataFrame | None,
    preview_validation_report: dict,
    output_dir: str | Path = OUTPUTS_DIR,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {}

    preview_quality_path = output_dir / "preview_quality_report.json"
    save_json(preview_validation_report, preview_quality_path)
    paths["preview_quality_report_json"] = str(preview_quality_path)

    if preview_event_log is not None:
        preview_path = output_dir / "preview_event_log.xlsx"
        preview_event_log.to_excel(preview_path, index=False)
        paths["preview_event_log"] = str(preview_path)

    return paths


def validate_preview_event_log(preview_event_log: pd.DataFrame | None) -> dict:
    if preview_event_log is None:
        return {
            "status": "error",
            "error": "Preview event log не был собран.",
        }

    report = validate_event_log(preview_event_log)
    suggestions = []

    if report.get("missing_timestamp", 0) > 0:
        suggestions.append("удалить или исправить строки без timestamp")

    if report.get("missing_case_id", 0) > 0:
        suggestions.append("проверить поле case_id, есть пропуски")

    if report.get("duplicate_events", 0) > 0:
        suggestions.append("удалить полные дубли по case_id + activity + timestamp")

    if report.get("cases_with_one_event", 0) > 0:
        suggestions.append("проверить, почему часть case_id содержит только одно событие")

    if report.get("invalid_timestamp", 0) > 0:
        suggestions.append("проверить формат даты в timestamp")

    report["suggestions"] = suggestions

    return report
