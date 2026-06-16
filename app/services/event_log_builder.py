import pandas as pd

from app.services.table_profiler import read_table


def _rename_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Убирает технические дубли колонок после merge.
    """

    new_columns = []
    seen = {}

    for col in df.columns:
        if col not in seen:
            seen[col] = 0
            new_columns.append(col)
        else:
            seen[col] += 1
            new_columns.append(f"{col}__dup_{seen[col]}")

    df.columns = new_columns

    return df


def _preserve_reserved_columns(
    df: pd.DataFrame,
    reserved_columns: list[str],
    source_columns: list[str],
) -> pd.DataFrame:
    rename_map = {}
    source_columns = set(source_columns)

    for column in reserved_columns:
        if column in df.columns and column not in source_columns:
            rename_map[column] = f"{column}_source_attr"

    if rename_map:
        return df.rename(columns=rename_map)

    return df


def execute_join_plan(
    join_plan: dict,
    tables_info: dict,
) -> pd.DataFrame:
    """
    Выполняет join_plan через pandas и возвращает сырой объединенный DataFrame.
    """

    if join_plan.get("status") != "ok":
        raise ValueError(f"Некорректный join_plan: {join_plan}")

    base_table = join_plan["base_table"]
    base_path = tables_info[base_table]["path"]

    result_df = read_table(base_path)

    for join in join_plan.get("joins", []):
        right_table = join["right_table"]
        right_path = tables_info[right_table]["path"]

        right_df = read_table(right_path)

        left_key = join["left_key"]
        right_key = join["right_key"]
        how = join.get("how", "left")

        if left_key not in result_df.columns:
            continue

        if right_key not in right_df.columns:
            continue

        result_df = result_df.merge(
            right_df,
            left_on=left_key,
            right_on=right_key,
            how=how,
            suffixes=("", f"__{right_table}"),
        )

    result_df = _rename_duplicate_columns(result_df)

    return result_df


def execute_event_tables_concat_plan(
    join_plan: dict,
    tables_info: dict,
) -> pd.DataFrame:
    """
    Собирает event log из набора event-таблиц.

    Каждая таблица является отдельным типом активности, а activity берется
    из имени файла.
    """

    if join_plan.get("status") != "ok":
        raise ValueError(f"Некорректный join_plan: {join_plan}")

    event_frames = []

    for source in join_plan.get("event_sources", []):
        table_name = source["file"]
        table_path = tables_info[table_name]["path"]
        source_df = read_table(table_path)

        case_id_col = source["case_id"]
        timestamp_col = source["timestamp"]
        start_time_col = source.get("start_time")
        stop_time_col = source.get("stop_time")
        activity = source["activity"]

        required_columns = [
            case_id_col,
            timestamp_col,
        ]
        missing_columns = [
            column for column in required_columns
            if column not in source_df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"{table_name}: нет обязательных колонок: {missing_columns}"
            )

        source_columns = [
            case_id_col,
            timestamp_col,
            start_time_col,
            stop_time_col,
        ]
        source_columns = [column for column in source_columns if column]

        event_df = _preserve_reserved_columns(
            source_df.copy(),
            reserved_columns=[
                "case_id",
                "activity",
                "activity_id",
                "timestamp",
                "start_time",
                "stop_time",
                "source_table",
                "source_row_number",
            ],
            source_columns=source_columns,
        )

        event_df["case_id"] = source_df[case_id_col]
        event_df["activity"] = activity
        event_df["activity_id"] = activity
        event_df["timestamp"] = pd.to_datetime(
            source_df[timestamp_col],
            errors="coerce",
        )

        if start_time_col and start_time_col in source_df.columns:
            event_df["start_time"] = pd.to_datetime(
                source_df[start_time_col],
                errors="coerce",
            )
        else:
            event_df["start_time"] = event_df["timestamp"]

        if stop_time_col and stop_time_col in source_df.columns:
            event_df["stop_time"] = pd.to_datetime(
                source_df[stop_time_col],
                errors="coerce",
            )
        else:
            event_df["stop_time"] = event_df["timestamp"]

        event_df["source_table"] = table_name
        event_df["source_row_number"] = range(1, len(event_df) + 1)

        event_frames.append(event_df)

    if not event_frames:
        return pd.DataFrame(
            columns=[
                "case_id",
                "activity",
                "activity_id",
                "timestamp",
                "start_time",
                "stop_time",
                "source_table",
                "source_row_number",
            ]
        )

    event_log = pd.concat(event_frames, ignore_index=True, sort=False)

    event_log = event_log.sort_values(
        by=[
            "case_id",
            "timestamp",
            "source_table",
            "source_row_number",
        ],
        na_position="last",
    ).reset_index(drop=True)

    return event_log


def build_event_log_from_joined_df(
    joined_df: pd.DataFrame,
    join_plan: dict,
) -> pd.DataFrame:
    """
    Собирает минимальный event log:
    - case_id
    - activity
    - timestamp

    Остальные колонки пока оставляем как атрибуты.
    """

    columns = join_plan["event_log_columns"]

    case_id_col = columns["case_id"]
    activity_col = columns["activity"]
    timestamp_col = columns["timestamp"]

    required = [
        case_id_col,
        activity_col,
        timestamp_col,
    ]

    missing = [
        col for col in required
        if col not in joined_df.columns
    ]

    if missing:
        raise ValueError(f"В объединенной таблице нет колонок: {missing}")

    event_log = joined_df.copy()

    canonical_mapping = {
        case_id_col: "case_id",
        activity_col: "activity",
        timestamp_col: "timestamp",
    }

    reserved_names = set(canonical_mapping.values())
    technical_renames = {}

    for col in event_log.columns:
        if col in reserved_names and canonical_mapping.get(col) != col:
            technical_renames[col] = f"{col}_source_attr"

    if technical_renames:
        event_log = event_log.rename(columns=technical_renames)

    event_log = event_log.rename(
        columns=canonical_mapping
    )

    event_log["timestamp"] = pd.to_datetime(
        event_log["timestamp"],
        errors="coerce",
    )

    if "start_time" not in event_log.columns:
        event_log["start_time"] = event_log["timestamp"]

    if "stop_time" not in event_log.columns:
        event_log["stop_time"] = event_log["timestamp"]

    event_log["start_time"] = pd.to_datetime(
        event_log["start_time"],
        errors="coerce",
    )

    event_log["stop_time"] = pd.to_datetime(
        event_log["stop_time"],
        errors="coerce",
    )

    event_log = event_log.sort_values(
        by=[
            "case_id",
            "timestamp",
        ],
        na_position="last",
    )

    return event_log
