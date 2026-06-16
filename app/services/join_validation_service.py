import pandas as pd

from app.services.table_profiler import read_table


def _key_stats(df: pd.DataFrame, key: str) -> dict:
    if key not in df.columns:
        return {
            "key_exists": False,
            "duplicate_key_rows": None,
            "duplicate_key_values": None,
            "missing_key_rows": None,
        }

    return {
        "key_exists": True,
        "duplicate_key_rows": int(df.duplicated(subset=[key], keep=False).sum()),
        "duplicate_key_values": int(df[key].dropna().duplicated().sum()),
        "missing_key_rows": int(df[key].isna().sum()),
    }


def validate_join_plan(
    join_plan: dict,
    tables_info: dict,
    row_growth_warning_ratio: float = 1.25,
) -> dict:
    """
    Боевые проверки join_plan до сборки event log:
    - разрастание строк после join
    - many-to-many join
    - потеря строк после join
    - дубли ключей
    """

    report = {
        "status": "ok",
        "checks": [],
        "warnings": [],
        "errors": [],
        "total_joins": len(join_plan.get("joins", [])),
    }

    if join_plan.get("status") != "ok":
        report["status"] = "error"
        report["errors"].append(join_plan.get("error", "Некорректный join_plan."))
        return report

    base_table = join_plan["base_table"]

    if base_table not in tables_info:
        report["status"] = "error"
        report["errors"].append(f"Базовая таблица не найдена: {base_table}")
        return report

    current_df = read_table(tables_info[base_table]["path"])
    report["base_table"] = base_table
    report["base_rows"] = int(len(current_df))

    for join in join_plan.get("joins", []):
        right_table = join["right_table"]
        left_key = join["left_key"]
        right_key = join["right_key"]
        how = join.get("how", "left")

        check = {
            "right_table": right_table,
            "left_key": left_key,
            "right_key": right_key,
            "how": how,
            "rows_before": int(len(current_df)),
        }

        if right_table not in tables_info:
            check["status"] = "error"
            check["error"] = f"Правая таблица не найдена: {right_table}"
            report["checks"].append(check)
            report["errors"].append(check["error"])
            continue

        right_df = read_table(tables_info[right_table]["path"])

        left_stats = _key_stats(current_df, left_key)
        right_stats = _key_stats(right_df, right_key)
        check["left_key_stats"] = left_stats
        check["right_key_stats"] = right_stats

        if not left_stats["key_exists"] or not right_stats["key_exists"]:
            check["status"] = "error"
            check["error"] = "Ключ join отсутствует в одной из таблиц."
            report["checks"].append(check)
            report["errors"].append(
                f"{right_table}: ключ join отсутствует в одной из таблиц."
            )
            continue

        left_key_has_duplicates = left_stats["duplicate_key_rows"] > 0
        right_key_has_duplicates = right_stats["duplicate_key_rows"] > 0
        check["many_to_many"] = bool(left_key_has_duplicates and right_key_has_duplicates)

        merged_df = current_df.merge(
            right_df,
            left_on=left_key,
            right_on=right_key,
            how=how,
            suffixes=("", f"__{right_table}"),
        )

        rows_before = len(current_df)
        rows_after = len(merged_df)
        row_growth_ratio = None if rows_before == 0 else round(rows_after / rows_before, 4)

        left_values = set(current_df[left_key].dropna().astype(str))
        right_values = set(right_df[right_key].dropna().astype(str))
        unmatched_left_values = left_values - right_values

        check["rows_after"] = int(rows_after)
        check["row_delta"] = int(rows_after - rows_before)
        check["row_growth_ratio"] = row_growth_ratio
        check["unmatched_left_key_values"] = int(len(unmatched_left_values))
        check["lost_rows_after_join"] = int(max(rows_before - rows_after, 0))
        check["status"] = "ok"

        if check["many_to_many"]:
            message = (
                f"{base_table} -> {right_table}: many-to-many join по "
                f"{left_key} = {right_key}."
            )
            check.setdefault("warnings", []).append(message)
            report["warnings"].append(message)

        if row_growth_ratio is not None and row_growth_ratio > row_growth_warning_ratio:
            message = (
                f"{base_table} -> {right_table}: строки выросли "
                f"в {row_growth_ratio} раза после join."
            )
            check.setdefault("warnings", []).append(message)
            report["warnings"].append(message)

        if check["lost_rows_after_join"] > 0:
            message = (
                f"{base_table} -> {right_table}: потеряно строк после join: "
                f"{check['lost_rows_after_join']}."
            )
            check.setdefault("warnings", []).append(message)
            report["warnings"].append(message)

        if right_key_has_duplicates:
            message = (
                f"{right_table}: дубли ключа {right_key}: "
                f"{right_stats['duplicate_key_rows']} строк."
            )
            check.setdefault("warnings", []).append(message)
            report["warnings"].append(message)

        report["checks"].append(check)
        current_df = merged_df

    report["final_rows_after_joins"] = int(len(current_df))

    if report["errors"]:
        report["status"] = "error"
    elif report["warnings"]:
        report["status"] = "warning"

    return report
