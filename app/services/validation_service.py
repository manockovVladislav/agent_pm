import pandas as pd


def _route_for_group(group: pd.DataFrame) -> tuple[str, ...]:
    ordered = group.sort_values("timestamp", na_position="last")

    return tuple(
        ordered["activity"]
        .dropna()
        .astype(str)
        .tolist()
    )


def _has_repeated_return(activities: list[str]) -> bool:
    seen_positions = {}

    for index, activity in enumerate(activities):
        if activity in seen_positions and index - seen_positions[activity] > 1:
            return True

        seen_positions[activity] = index

    return False


def validate_event_log(event_log: pd.DataFrame) -> dict:
    """
    Проверяет качество event log.
    """

    report = {}

    required_columns = [
        "case_id",
        "activity",
        "timestamp",
    ]

    missing_required_columns = [
        col for col in required_columns
        if col not in event_log.columns
    ]

    report["missing_required_columns"] = missing_required_columns

    if missing_required_columns:
        report["status"] = "error"
        report["error"] = "В event log отсутствуют обязательные колонки."
        return report

    total_rows = len(event_log)

    report["status"] = "ok"
    report["total_events"] = int(total_rows)
    report["total_cases"] = int(event_log["case_id"].nunique(dropna=True))
    report["unique_activities"] = int(event_log["activity"].nunique(dropna=True))

    report["missing_case_id"] = int(event_log["case_id"].isna().sum())
    report["missing_activity"] = int(event_log["activity"].isna().sum())
    report["missing_timestamp"] = int(event_log["timestamp"].isna().sum())
    report["invalid_timestamp"] = int(
        pd.to_datetime(event_log["timestamp"], errors="coerce").isna().sum()
    )

    report["missing_case_id_percent"] = round(
        event_log["case_id"].isna().mean() * 100,
        2,
    )

    report["missing_activity_percent"] = round(
        event_log["activity"].isna().mean() * 100,
        2,
    )

    report["missing_timestamp_percent"] = round(
        event_log["timestamp"].isna().mean() * 100,
        2,
    )

    report["duplicate_events"] = int(
        event_log.duplicated(
            subset=[
                "case_id",
                "activity",
                "timestamp",
            ]
        ).sum()
    )

    case_sizes = (
        event_log
        .dropna(subset=["case_id"])
        .groupby("case_id")
        .size()
    )

    report["cases_with_one_event"] = int((case_sizes == 1).sum())

    if "start_time" in event_log.columns and "stop_time" in event_log.columns:
        start_time = pd.to_datetime(event_log["start_time"], errors="coerce")
        stop_time = pd.to_datetime(event_log["stop_time"], errors="coerce")
        durations_seconds = (stop_time - start_time).dt.total_seconds()

        report["invalid_start_time"] = int(start_time.isna().sum())
        report["invalid_stop_time"] = int(stop_time.isna().sum())
        report["negative_duration_events"] = int((durations_seconds < 0).sum())
    else:
        report["invalid_start_time"] = None
        report["invalid_stop_time"] = None
        report["negative_duration_events"] = None

    clean_log = event_log.dropna(
        subset=[
            "case_id",
            "timestamp",
        ]
    ).copy()

    if clean_log.empty:
        report["min_case_duration_hours"] = None
        report["avg_case_duration_hours"] = None
        report["median_case_duration_hours"] = None
        report["max_case_duration_hours"] = None
    else:
        durations = (
            clean_log
            .groupby("case_id")["timestamp"]
            .agg(["min", "max"])
        )

        durations["duration_hours"] = (
            durations["max"] - durations["min"]
        ).dt.total_seconds() / 3600

        report["min_case_duration_hours"] = round(
            float(durations["duration_hours"].min()),
            2,
        )

        report["avg_case_duration_hours"] = round(
            float(durations["duration_hours"].mean()),
            2,
        )

        report["median_case_duration_hours"] = round(
            float(durations["duration_hours"].median()),
            2,
        )

        report["max_case_duration_hours"] = round(
            float(durations["duration_hours"].max()),
            2,
        )

    activity_counts = (
        event_log["activity"]
        .fillna("NULL")
        .astype(str)
        .value_counts()
        .head(20)
        .to_dict()
    )

    report["top_activities"] = {
        str(key): int(value)
        for key, value in activity_counts.items()
    }

    clean_routes_log = event_log.dropna(
        subset=[
            "case_id",
            "activity",
        ]
    ).copy()

    if clean_routes_log.empty:
        report["unique_routes"] = 0
        report["rare_routes"] = 0
        report["rare_route_cases"] = 0
        report["cases_with_missing_common_stages"] = 0
        report["cases_with_repeated_returns"] = 0
    else:
        routes = pd.Series(
            {
                case_id: _route_for_group(group)
                for case_id, group in clean_routes_log.groupby("case_id")
            }
        )

        route_counts = routes.value_counts()
        total_cases_with_routes = int(len(routes))

        report["unique_routes"] = int(len(route_counts))
        report["top_routes"] = {
            " -> ".join(route): int(count)
            for route, count in route_counts.head(10).items()
        }

        rare_route_counts = route_counts[route_counts == 1]
        report["rare_routes"] = int(len(rare_route_counts))
        report["rare_route_cases"] = int(rare_route_counts.sum())
        report["rare_route_cases_percent"] = round(
            (report["rare_route_cases"] / total_cases_with_routes) * 100,
            2,
        ) if total_cases_with_routes else 0

        most_common_route = route_counts.index[0] if len(route_counts) else tuple()
        most_common_stages = set(most_common_route)

        missing_common_stage_cases = 0
        repeated_return_cases = 0

        for route in routes:
            route_stages = set(route)

            if most_common_stages and not most_common_stages.issubset(route_stages):
                missing_common_stage_cases += 1

            if _has_repeated_return(list(route)):
                repeated_return_cases += 1

        report["cases_with_missing_common_stages"] = int(missing_common_stage_cases)
        report["cases_with_repeated_returns"] = int(repeated_return_cases)

    clean_time_activity_log = event_log.dropna(
        subset=[
            "case_id",
            "activity",
            "timestamp",
        ]
    ).copy()

    if clean_time_activity_log.empty:
        report["cases_with_same_timestamp_multi_activity"] = 0
        report["same_timestamp_multi_activity_events"] = 0
    else:
        same_timestamp_cases = 0
        same_timestamp_events = 0

        for _, case_group in clean_time_activity_log.groupby("case_id"):
            timestamp_activity_counts = (
                case_group
                .groupby("timestamp")["activity"]
                .nunique(dropna=True)
            )
            problematic_timestamps = timestamp_activity_counts[
                timestamp_activity_counts > 1
            ]

            if not problematic_timestamps.empty:
                same_timestamp_cases += 1
                same_timestamp_events += int(
                    case_group[
                        case_group["timestamp"].isin(problematic_timestamps.index)
                    ].shape[0]
                )

        report["cases_with_same_timestamp_multi_activity"] = int(same_timestamp_cases)
        report["same_timestamp_multi_activity_events"] = int(same_timestamp_events)

    if clean_log.empty:
        report["outlier_case_duration_count"] = 0
        report["outlier_case_duration_threshold_hours"] = None
    else:
        durations_for_outliers = (
            clean_log
            .groupby("case_id")["timestamp"]
            .agg(["min", "max"])
        )

        durations_for_outliers["duration_hours"] = (
            durations_for_outliers["max"] - durations_for_outliers["min"]
        ).dt.total_seconds() / 3600

        q1 = durations_for_outliers["duration_hours"].quantile(0.25)
        q3 = durations_for_outliers["duration_hours"].quantile(0.75)
        iqr = q3 - q1
        threshold = q3 + 1.5 * iqr

        report["outlier_case_duration_threshold_hours"] = round(float(threshold), 2)
        report["outlier_case_duration_count"] = int(
            (durations_for_outliers["duration_hours"] > threshold).sum()
        )

    return report
