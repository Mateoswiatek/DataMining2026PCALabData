from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"

EVENTS_PATH = PROCESSED_DIR / "pcr_events_biz.parquet"
CASES_PATH = PROCESSED_DIR / "pcr_cases.parquet"


def main() -> None:
    df_events = pd.read_parquet(EVENTS_PATH)
    df_cases = pd.read_parquet(CASES_PATH)

    df_cases_sample = df_cases[df_cases["process_type"] == "sample"].copy()
    sample_ids = set(df_cases_sample["instance_uuid"])
    df_ev_sample = df_events[df_events["instance_uuid"].isin(sample_ids)].copy()

    df_events["endpoint"] = df_events["endpoint"].fillna("").astype(str)
    df_ev_sample["endpoint"] = df_ev_sample["endpoint"].fillna("").astype(str)

    unique_all = df_events.loc[df_events["endpoint"] != "", "endpoint"].nunique()
    unique_sample = df_ev_sample.loc[df_ev_sample["endpoint"] != "", "endpoint"].nunique()
    unique_sample_start = df_ev_sample.loc[
        (df_ev_sample["endpoint"] != "") & (df_ev_sample["lifecycle"] == "start"),
        "endpoint",
    ].nunique()

    missing_pcr = df_cases_sample["pcr_result"].isna().sum()
    total_sample_cases = len(df_cases_sample)
    missing_pct = (missing_pcr / total_sample_cases * 100) if total_sample_cases else 0.0

    print("--- Sample cases ---")
    print(f"Cases: {total_sample_cases}")
    print(f"Missing PCR result: {missing_pcr} ({missing_pct:.1f}%)")
    print()
    print("--- Unique endpoints ---")
    print(f"All events: {unique_all}")
    print(f"Sample events: {unique_sample}")
    print(f"Sample start events: {unique_sample_start}")
    print()

    event_cols = ["instance_uuid", "activity", "timestamp", "lifecycle", "endpoint"]
    case_cols = ["instance_uuid", "pcr_result", "ct"]

    print("--- Event dtypes ---")
    print(df_events[event_cols].dtypes)
    print()
    print("--- Case dtypes ---")
    print(df_cases[case_cols].dtypes)
    print()

    top10 = df_ev_sample["endpoint"].value_counts().head(10)
    print("--- Top 10 endpoints (sample events) ---")
    print(top10.to_string())


if __name__ == "__main__":
    main()
