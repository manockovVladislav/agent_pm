import json
from pathlib import Path

import pandas as pd

from app.config import OUTPUTS_DIR


def save_json(data: dict, path: str | Path):
    path = Path(path)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


def save_outputs(
    event_log: pd.DataFrame | None,
    join_plan: dict,
    join_validation_report: dict,
    validation_report: dict,
    relationships: list[dict],
    output_dir: str | Path = OUTPUTS_DIR,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {}

    join_plan_path = output_dir / "join_plan.json"
    save_json(join_plan, join_plan_path)
    paths["join_plan"] = str(join_plan_path)

    join_validation_report_path = output_dir / "join_quality_report.json"
    save_json(join_validation_report, join_validation_report_path)
    paths["join_quality_report_json"] = str(join_validation_report_path)

    relationships_path = output_dir / "relationships.json"
    save_json({"relationships": relationships}, relationships_path)
    paths["relationships"] = str(relationships_path)

    validation_report_path = output_dir / "quality_report.json"
    save_json(validation_report, validation_report_path)
    paths["quality_report_json"] = str(validation_report_path)

    if event_log is not None:
        event_log_path = output_dir / "event_log.xlsx"
        event_log.to_excel(event_log_path, index=False)
        paths["event_log"] = str(event_log_path)

        preview_path = output_dir / "event_log_preview.xlsx"
        event_log.head(1000).to_excel(preview_path, index=False)
        paths["event_log_preview"] = str(preview_path)

        quality_excel_path = output_dir / "quality_report.xlsx"

        quality_df = pd.DataFrame(
            [
                {
                    "metric": key,
                    "value": str(value),
                }
                for key, value in validation_report.items()
            ]
        )

        quality_df.to_excel(quality_excel_path, index=False)
        paths["quality_report_excel"] = str(quality_excel_path)

        join_quality_excel_path = output_dir / "join_quality_report.xlsx"

        join_quality_df = pd.DataFrame(
            [
                {
                    "metric": key,
                    "value": str(value),
                }
                for key, value in join_validation_report.items()
                if key != "checks"
            ]
        )

        join_quality_df.to_excel(join_quality_excel_path, index=False)
        paths["join_quality_report_excel"] = str(join_quality_excel_path)

    return paths
