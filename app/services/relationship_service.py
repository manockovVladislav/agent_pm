from difflib import SequenceMatcher

import pandas as pd

from app.services.table_profiler import read_table


def _normalize_name(name: str) -> str:
    return (
        str(name)
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".", "")
    )


def _name_similarity(left_name: str, right_name: str) -> float:
    left_norm = _normalize_name(left_name)
    right_norm = _normalize_name(right_name)

    if left_norm == right_norm:
        return 1.0

    if left_norm in right_norm or right_norm in left_norm:
        return 0.85

    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _safe_unique_values(df: pd.DataFrame, column: str, limit: int = 5000) -> set:
    if column not in df.columns:
        return set()

    values = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = values[values != ""]

    return set(values.head(limit).tolist())


def _value_overlap_score(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_col: str,
    right_col: str,
) -> float:
    left_values = _safe_unique_values(left_df, left_col)
    right_values = _safe_unique_values(right_df, right_col)

    if not left_values or not right_values:
        return 0.0

    intersection = left_values.intersection(right_values)
    smaller_size = min(len(left_values), len(right_values))

    if smaller_size == 0:
        return 0.0

    return len(intersection) / smaller_size


def infer_relationships(
    tables_info: dict,
    max_rows: int = 5000,
    min_score: float = 0.45,
) -> list[dict]:
    """
    Ищет возможные связи между таблицами.

    Логика:
    1. Сравнивает названия колонок.
    2. Сравнивает пересечение значений.
    3. Возвращает список вероятных связей.
    """

    table_names = [
        table_name
        for table_name, info in tables_info.items()
        if "error" not in info
    ]

    loaded_tables = {}

    for table_name in table_names:
        path = tables_info[table_name]["path"]

        try:
            loaded_tables[table_name] = read_table(path, max_rows=max_rows)
        except Exception:
            loaded_tables[table_name] = None

    relationships = []

    for i, left_table in enumerate(table_names):
        for right_table in table_names[i + 1:]:
            left_df = loaded_tables.get(left_table)
            right_df = loaded_tables.get(right_table)

            if left_df is None or right_df is None:
                continue

            left_columns = list(left_df.columns)
            right_columns = list(right_df.columns)

            for left_col in left_columns:
                for right_col in right_columns:
                    name_score = _name_similarity(left_col, right_col)

                    if name_score < 0.55:
                        continue

                    overlap_score = _value_overlap_score(
                        left_df=left_df,
                        right_df=right_df,
                        left_col=left_col,
                        right_col=right_col,
                    )

                    final_score = round(
                        0.55 * name_score + 0.45 * overlap_score,
                        4,
                    )

                    if final_score >= min_score:
                        relationships.append(
                            {
                                "left_table": left_table,
                                "left_column": left_col,
                                "right_table": right_table,
                                "right_column": right_col,
                                "name_score": round(name_score, 4),
                                "overlap_score": round(overlap_score, 4),
                                "score": final_score,
                            }
                        )

    relationships = sorted(
        relationships,
        key=lambda item: item["score"],
        reverse=True,
    )

    return relationships
