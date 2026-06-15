"""Rich event ETL for Milestone 2 (clustering on low-level data).

Unlike notebooks/00_etl.ipynb (which filtered to business start/complete events and
kept only result/ct from the YAML `data` payload), this script keeps the RAW CPEE
engine events and extracts the full low-level `data` payload per event:

  - the *signature* of process variables touched by the event (e.g. an
    `activity/calling` event for "Match patient data" carries {pid, sampleid}),
  - physical/positional scalars: position (plate slot 1-96), plateid, slotid, pid, sampleid,
  - the cpee:lifecycle micro-state (activity/calling, activity/receiving, activity/done,
    dataelements/change, gateway/join, ...).

These are the genuinely LOW-LEVEL features we cluster on in M2 -- NOT endpoints, NOT the
PCR outcome (result/ct), NOT durations/timestamps. The activity label (concept:name) is kept
ONLY as ground truth for the 1:1 comparison, never as a clustering feature.

Output: data/processed/pcr_events_rich.parquet (one row per raw event).

Run once:  python scripts/build_rich_events.py
"""
from pathlib import Path
import sys
from multiprocessing import Pool, cpu_count
import yaml
import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "pcr_events_rich.parquet"

# Variables that are NOT low-level signal: service endpoints / config and ground truth.
# Recorded here for documentation; the notebook also excludes them when building features.
ENDPOINT_VARS = {"timeout", "timeout2", "subprocess", "receive", "send", "correlator",
                 "notify", "url", "endpoints", "behavior", "customization", "init"}
GROUND_TRUTH_VARS = {"result", "state", "ct"}
# Model/bookkeeping attributes emitted on attributes/change events (setup noise).
META_VARS = {"info", "creator", "author", "modeltype", "theme", "design_dir",
             "design_stage", "modeluuid", "guarded", "guarded_id"}


def extract_payload(data_list):
    """Return (var_names list, scalars dict) from an event's `data` payload."""
    names, scal = [], {}
    if not isinstance(data_list, list):
        return names, scal
    for item in data_list:
        if not isinstance(item, dict):
            continue
        nm = item.get("name")
        if nm is None:
            continue
        names.append(str(nm))
        v = item.get("value")
        if nm == "sample" and isinstance(v, dict):
            for k in ("position", "plateid", "sampleid"):
                if v.get(k) is not None:
                    scal.setdefault(k, v.get(k))
        elif nm in ("position", "plateid", "slotid", "pid", "sampleid") and not isinstance(v, (dict, list)):
            scal[nm] = v
    return names, scal


def parse_file(filepath):
    rows = []
    try:
        docs = list(yaml.safe_load_all(open(filepath, "r", encoding="utf-8")))
    except Exception:
        return rows
    instance_uuid = filepath.stem.replace(".xes", "")
    header = docs[0] if docs else {}
    trace = header.get("log", {}).get("trace", {}) if isinstance(header, dict) else {}
    case_name = trace.get("cpee:name", "") if isinstance(trace, dict) else ""

    for doc in docs[1:]:
        if not isinstance(doc, dict) or "event" not in doc:
            continue
        ev = doc["event"]
        ts = ev.get("time:timestamp")
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        elif not isinstance(ts, str):
            ts = None
        names, scal = extract_payload(ev.get("data"))
        rows.append({
            "instance_uuid": instance_uuid,
            "case_id": ev.get("concept:instance"),
            "case_name": case_name,
            "activity": ev.get("concept:name"),           # ground truth label (not a feature)
            "endpoint": ev.get("concept:endpoint", ""),    # excluded from features
            "lifecycle": ev.get("lifecycle:transition"),
            "cpee_lifecycle": ev.get("cpee:lifecycle:transition"),
            "cpee_activity_id": ev.get("id:id", ""),
            "data_vars": ",".join(names),                  # low-level signature (sorted-free)
            "n_vars": len(names),
            "position": scal.get("position"),
            "plateid": scal.get("plateid"),
            "slotid": scal.get("slotid"),
            "pid": scal.get("pid"),
            "sampleid": scal.get("sampleid"),
            "timestamp": ts,                                # ordering only, never a feature
        })
    return rows


def main():
    yaml_files = sorted(
        p for p in RAW_DIR.rglob("*.xes.yaml")
        if "__MACOSX" not in p.parts and not p.name.startswith("._")
    )
    print(f"YAML files: {len(yaml_files)}")
    if not yaml_files:
        sys.exit("No raw YAML found under data/raw/. Run the ETL download first.")

    all_rows = []
    n_proc = max(1, cpu_count() - 1)
    with Pool(n_proc) as pool:
        for rows in tqdm(pool.imap_unordered(parse_file, yaml_files, chunksize=16),
                         total=len(yaml_files), desc=f"Parsing ({n_proc} proc)"):
            all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["position"] = pd.to_numeric(df["position"], errors="coerce")
    df["pid"] = pd.to_numeric(df["pid"], errors="coerce")
    # id-like fields can be int or str in the raw YAML -> normalise to string
    for c in ["plateid", "slotid", "sampleid"]:
        df[c] = df[c].astype("string")
    df = df.sort_values(["instance_uuid", "timestamp"]).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"\nSaved {len(df):,} events -> {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size / 1024:.1f} KB)")
    print(f"cases: {df['instance_uuid'].nunique():,}")
    print("\ncpee_lifecycle counts:")
    print(df["cpee_lifecycle"].value_counts().to_string())
    print(f"\nactivity/calling events (clustering candidates): "
          f"{(df['cpee_lifecycle'] == 'activity/calling').sum():,}")


if __name__ == "__main__":
    main()
