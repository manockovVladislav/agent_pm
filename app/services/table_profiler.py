from pathlib import Path

import pandas as pd


ID_KEYWORDS = [
    "id",
    "case",
    "case_id",
    "request",
    "application",
    "deal",
    "doc",
    "num",
    "number",
    "номер",
    "заяв",
    "сдел",
    "док",
]

ACTIVITY_KEYWORDS = [
    "activity",
    "event",
    "status",
    "operation",
    "opname",
    "stage",
    "step",
    "action",
    "статус",
    "операц",
    "этап",
    "событ",
    "действ",
]

TIME_KEYWORDS = [
    "date",
    "time",
    "timestamp",
    "created",
    "updated",
    "start",
    "stop",
    "end",
    "дата",
    "время",
    "начал",
    "оконч",
]


def read_table(path: str | Path, max_rows: int | None = None) -> pd.DataFrame:
    """
    Универсальное чтение CSV/XLSX.
    """

    path = Path(path)

    if path.suffix.lower() == ".csv":
        try:
            return pd.read_csv(path, nrows=max_rows)
        except UnicodeDecodeError:
            return pd.read_csv(path, nrows=max_rows, encoding="utf-8-sig")

    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, nrows=max_rows)

    raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")


def _contains_keyword(column_name: str, keywords: list[str]) -> bool:
    name = str(column_name).lower()

    return any(keyword in name for keyword in keywords)


def _safe_examples(series: pd.Series, limit: int = 5) -> list:
    values = (
        series
        .dropna()
        .astype(str)
        .drop_duplicates()
        .head(limit)
        .tolist()
    )

    return values


def profile_table(path: str | Path) -> dict:
    """
    Делает профиль одной таблицы:
    - строки
    - колонки
    - типы
    - пропуски
    - дубли
    - примеры значений
    - кандидаты на case_id/activity/timestamp
    """

    path = Path(path)
    df_full = read_table(path, max_rows=None)

    rows_count = len(df_full)
    columns = list(df_full.columns)

    missing_by_column = (
        df_full
        .isna()
        .sum()
        .sort_values(ascending=False)
        .to_dict()
    )

    missing_percent_by_column = {}

    for col in columns:
        if rows_count == 0:
            missing_percent_by_column[col] = 0
        else:
            missing_percent_by_column[col] = round(
                df_full[col].isna().mean() * 100,
                2,
            )

    duplicate_rows = int(df_full.duplicated().sum())

    column_profiles = {}

    for col in columns:
        series = df_full[col]

        column_profiles[col] = {
            "dtype": str(series.dtype),
            "missing_count": int(series.isna().sum()),
            "missing_percent": missing_percent_by_column[col],
            "unique_count": int(series.nunique(dropna=True)),
            "examples": _safe_examples(series),
        }

    candidate_case_id_columns = [
        col for col in columns
        if _contains_keyword(col, ID_KEYWORDS)
    ]

    candidate_activity_columns = [
        col for col in columns
        if _contains_keyword(col, ACTIVITY_KEYWORDS)
    ]

    candidate_timestamp_columns = [
        col for col in columns
        if _contains_keyword(col, TIME_KEYWORDS)
    ]

    return {
        "file_name": path.name,
        "path": str(path),
        "rows": rows_count,
        "columns_count": len(columns),
        "columns": columns,
        "duplicate_rows": duplicate_rows,
        "missing_by_column": missing_by_column,
        "column_profiles": column_profiles,
        "candidate_case_id_columns": candidate_case_id_columns,
        "candidate_activity_columns": candidate_activity_columns,
        "candidate_timestamp_columns": candidate_timestamp_columns,
    }


def profile_tables(files: list[dict]) -> dict:
    """
    Делает профиль всех найденных таблиц.
    """

    result = {}

    for file_info in files:
        path = file_info["path"]
        file_name = file_info["file_name"]

        try:
            result[file_name] = profile_table(path)
        except Exception as error:
            result[file_name] = {
                "file_name": file_name,
                "path": path,
                "error": str(error),
            }

    return result
