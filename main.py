from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.gms.moontontech.com/api/gms/source/2669606/2756567"
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://www.mobilelegends.com",
    "Referer": "https://www.mobilelegends.com/rank",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
    "x-appid": "2669606",
    "x-actid": "2669607",
    "x-lang": "en",
}

RANK_OPTIONS = {
    "all": "101",
    "epic": "5",
    "legend": "6",
    "mythic": "7",
    "mythical_honor": "8",
    "mythical_glory_plus": "9",
}

WINDOW_OPTIONS = {
    # The mobilelegends.com UI labels these as "Past X days", but the backend parameter
    # observed in-browser for "Past 7 days" is still `match_type = 0`.
    # Keep a legacy alias for older runs/configs.
    "past_7_days": 0,
    "past_1_day": 0,  # alias
    # These may be valid in the future, but currently can return empty datasets.
    "past_3_days": 1,
    "past_15_days": 3,
    "past_30_days": 4,
}

FIELDS = [
    "main_hero",
    "main_hero_appearance_rate",
    "main_hero_ban_rate",
    "main_hero_channel",
    "main_hero_win_rate",
    "main_heroid",
    "data.sub_hero.hero",
    "data.sub_hero.hero_channel",
    "data.sub_hero.increase_win_rate",
    "data.sub_hero.heroid",
]

SORT_FIELDS = {
    "win_rate": "main_hero_win_rate",
    "pick_rate": "main_hero_appearance_rate",
    "ban_rate": "main_hero_ban_rate",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Mobile Legends hero ranking/tierlist stats for AI or NotebookLM."
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run an interactive prompt to choose export options.",
    )
    parser.add_argument(
        "--rank",
        action="append",
        choices=list(RANK_OPTIONS.keys()),
        help="Rank bucket(s) to export. Repeat flag for multiple values.",
    )
    parser.add_argument(
        "--window",
        action="append",
        choices=list(WINDOW_OPTIONS.keys()),
        help="Time window(s) to export. Repeat flag for multiple values.",
    )
    parser.add_argument(
        "--sort-by",
        default="win_rate",
        choices=list(SORT_FIELDS.keys()),
        help="Sort mode to request from API.",
    )
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Include rank/window combos even when API returns no rows.",
    )
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args()

def _is_tty() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _prompt_choice(title: str, options: list[tuple[str, str]], default_key: str) -> str:
    index_by_key = {k: i + 1 for i, (k, _) in enumerate(options)}
    default_index = index_by_key[default_key]
    while True:
        print()
        print(title)
        for i, (key, label) in enumerate(options, start=1):
            suffix = " (default)" if i == default_index else ""
            print(f"  {i}) {label}{suffix}")
        raw = input(f"Select 1-{len(options)} [{default_index}]: ").strip()
        if raw == "":
            return default_key
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
        print("Invalid choice. Try again.")


def _prompt_multiselect(title: str, options: list[tuple[str, str]], default_keys: list[str]) -> list[str]:
    key_by_index = {i + 1: k for i, (k, _) in enumerate(options)}
    label_by_key = {k: label for k, label in options}
    default_indices = [i + 1 for i, (k, _) in enumerate(options) if k in set(default_keys)]

    while True:
        print()
        print(title)
        for i, (key, label) in enumerate(options, start=1):
            default_mark = " (default)" if key in set(default_keys) else ""
            print(f"  {i}) {label}{default_mark}")
        print("  a) All of the above")
        raw = input(
            f"Select numbers (comma-separated) or 'a' [{','.join(map(str, default_indices)) or 'a'}]: "
        ).strip().lower()

        if raw == "":
            return default_keys
        if raw == "a":
            return [k for k, _ in options]

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if not parts:
            print("Invalid choice. Try again.")
            continue

        selected: list[str] = []
        ok = True
        for part in parts:
            if not part.isdigit():
                ok = False
                break
            idx = int(part)
            if idx not in key_by_index:
                ok = False
                break
            selected.append(key_by_index[idx])

        if ok and selected:
            # de-dup while preserving order
            seen: set[str] = set()
            deduped = []
            for k in selected:
                if k not in seen:
                    deduped.append(k)
                    seen.add(k)
            return deduped

        valid_labels = ", ".join(label_by_key[k] for k in default_keys) if default_keys else "All"
        print(f"Invalid choice. Try again. Default is: {valid_labels}.")


def _interactive_fill(args: argparse.Namespace) -> argparse.Namespace:
    print("MLBB Tierlist Exporter (interactive)")

    window = _prompt_choice(
        "Choose time window:",
        [
            ("past_7_days", "Past 7 days (matches site request: match_type=0)"),
            ("past_3_days", "Past 3 days (may be empty depending on official data)"),
            ("past_15_days", "Past 15 days (may be empty depending on official data)"),
            ("past_30_days", "Past 30 days (may be empty depending on official data)"),
        ],
        default_key="past_7_days",
    )

    ranks = _prompt_multiselect(
        "Choose rank buckets:",
        [
            ("all", "ALL"),
            ("epic", "Epic"),
            ("legend", "Legend"),
            ("mythic", "Mythic"),
            ("mythical_honor", "Mythical Honor"),
            ("mythical_glory_plus", "Mythical Glory+"),
        ],
        default_keys=["all", "epic", "legend", "mythic", "mythical_honor", "mythical_glory_plus"],
    )

    sort_by = _prompt_choice(
        "Sort ranking by:",
        [("win_rate", "Win rate"), ("pick_rate", "Pick rate"), ("ban_rate", "Ban rate")],
        default_key="win_rate",
    )

    print()
    out_dir = input(f"Output directory [{args.output_dir}]: ").strip() or args.output_dir
    include_empty_raw = input("Include empty rank/window combos? [y/N]: ").strip().lower()
    include_empty = include_empty_raw in {"y", "yes"}

    args.window = [window]
    args.rank = ranks
    args.sort_by = sort_by
    args.output_dir = out_dir
    args.include_empty = include_empty
    return args


def build_payload(
    rank_value: str, window_value: int, page_index: int, page_size: int, sort_field: str
) -> dict[str, Any]:
    return {
        "pageSize": page_size,
        "pageIndex": page_index,
        "filters": [
            {"field": "bigrank", "operator": "eq", "value": rank_value},
            {"field": "match_type", "operator": "eq", "value": window_value},
        ],
        "sorts": [
            {"data": {"field": sort_field, "order": "desc"}, "type": "sequence"},
            {"data": {"field": "main_heroid", "order": "desc"}, "type": "sequence"},
        ],
        "fields": FIELDS,
    }


def fetch_records(
    session: requests.Session,
    rank_value: str,
    window_value: int,
    page_size: int,
    sort_field: str,
    timeout: float,
) -> tuple[int, list[dict[str, Any]]]:
    all_records: list[dict[str, Any]] = []
    total = 0
    page_index = 1

    while True:
        payload = build_payload(rank_value, window_value, page_index, page_size, sort_field)
        response = session.post(API_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        body = response.json()

        if body.get("code") != 0:
            raise RuntimeError(f"API error for rank={rank_value}, window={window_value}: {body}")

        data = body.get("data") or {}
        total = int(data.get("total") or 0)
        records = data.get("records") or []
        all_records.extend(records)

        if not records:
            break

        if len(all_records) >= total:
            break

        page_index += 1

    return total, all_records


def normalize_rows(
    records: list[dict[str, Any]],
    rank_label: str,
    rank_value: str,
    window_label: str,
    window_value: int,
    fetched_at_utc: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, raw_record in enumerate(records, start=1):
        data = raw_record.get("data") or {}
        main_hero = (data.get("main_hero") or {}).get("data") or {}
        counter_raw = data.get("sub_hero") or []
        counter_heroes = [
            {
                "hero_id": counter.get("heroid"),
                "hero_name": ((counter.get("hero") or {}).get("data") or {}).get("name"),
                "counter_win_rate_lift": counter.get("increase_win_rate"),
            }
            for counter in counter_raw
        ]

        row = {
            "fetched_at_utc": fetched_at_utc,
            "source_page": "https://www.mobilelegends.com/rank",
            "rank_label": rank_label,
            "rank_value": rank_value,
            "window_label": window_label,
            "window_value": window_value,
            "position": idx,
            "hero_id": data.get("main_heroid"),
            "hero_name": main_hero.get("name"),
            "hero_head_url": main_hero.get("head"),
            "pick_rate": data.get("main_hero_appearance_rate"),
            "win_rate": data.get("main_hero_win_rate"),
            "ban_rate": data.get("main_hero_ban_rate"),
            "counter_heroes": counter_heroes,
        }
        rows.append(row)
    return rows


def map_hero_names(rows: list[dict[str, Any]]) -> dict[int, str]:
    hero_name_by_id: dict[int, str] = {}
    for row in rows:
        hero_id = row.get("hero_id")
        hero_name = row.get("hero_name")
        if isinstance(hero_id, int) and hero_name:
            hero_name_by_id[hero_id] = str(hero_name)
    return hero_name_by_id


def enrich_counter_names(rows: list[dict[str, Any]], hero_name_by_id: dict[int, str]) -> None:
    for row in rows:
        counters = row.get("counter_heroes") or []
        for counter in counters:
            hero_id = counter.get("hero_id")
            if counter.get("hero_name") is None and isinstance(hero_id, int):
                counter["hero_name"] = hero_name_by_id.get(hero_id)


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "fetched_at_utc",
        "source_page",
        "rank_label",
        "rank_value",
        "window_label",
        "window_value",
        "position",
        "hero_id",
        "hero_name",
        "hero_head_url",
        "pick_rate",
        "win_rate",
        "ban_rate",
        "counter_heroes",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["counter_heroes"] = json.dumps(csv_row.get("counter_heroes") or [], ensure_ascii=False)
            writer.writerow(csv_row)


def write_notebooklm_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Mobile Legends Hero Tierlist Export",
        "",
        "This file is generated for NotebookLM / LLM ingestion.",
        "",
        "## Data Dictionary",
        "",
        "- `pick_rate`, `win_rate`, `ban_rate` are decimal values (for example, `0.561` = 56.1%).",
        "- `counter_heroes` lists heroes that the row hero is strong against (i.e. heroes it counters).",
        "- `counter_win_rate_lift` is the win-rate lift value associated with that counter matchup in the source data.",
        "",
    ]

    # NotebookLM works best with content grouped in a human-readable way.
    # Group primarily by rank bucket, then by window label.
    by_rank: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_rank[row["rank_label"]].append(row)

    for rank_label in sorted(by_rank.keys()):
        lines.extend([f"## Rank: `{rank_label}`", ""])
        by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in by_rank[rank_label]:
            by_window[row["window_label"]].append(row)

        for window_label in sorted(by_window.keys()):
            window_rows = sorted(by_window[window_label], key=lambda x: x["position"])
            lines.extend(
                [
                    f"### Window: `{window_label}`",
                    "",
                    "| Pos | Hero | Win % | Pick % | Ban % | Top Heroes Countered |",
                    "|---:|---|---:|---:|---:|---|",
                ]
            )
            for row in window_rows:
                counters = row.get("counter_heroes") or []
                top_counter_names = [
                    counter.get("hero_name") or str(counter.get("hero_id")) for counter in counters[:3]
                ]
                lines.append(
                    "| {pos} | {hero} | {win:.2f} | {pick:.2f} | {ban:.2f} | {counters} |".format(
                        pos=row["position"],
                        hero=row.get("hero_name") or "Unknown",
                        win=(row.get("win_rate") or 0) * 100,
                        pick=(row.get("pick_rate") or 0) * 100,
                        ban=(row.get("ban_rate") or 0) * 100,
                        counters=", ".join(top_counter_names) if top_counter_names else "-",
                    )
                )
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_notebooklm_markdown_rank_files(base_dir: Path, rows: list[dict[str, Any]]) -> list[Path]:
    by_rank: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_rank[row["rank_label"]].append(row)

    out_dir = base_dir / "notebooklm_ranks"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for rank_label, rank_rows in sorted(by_rank.items(), key=lambda x: x[0]):
        path = out_dir / f"mlbb_tierlist_notebooklm_{rank_label}.md"
        write_notebooklm_markdown(path, rank_rows)
        written.append(path)

    return written


def main() -> None:
    args = parse_args()
    if args.interactive or (not sys.argv[1:] and _is_tty()):
        args = _interactive_fill(args)
    ranks = args.rank or ["all"]
    windows = args.window or ["past_7_days"]
    sort_field = SORT_FIELDS[args.sort_by]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fetched_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    all_rows: list[dict[str, Any]] = []
    combo_summaries: list[dict[str, Any]] = []

    for window_label in windows:
        window_value = WINDOW_OPTIONS[window_label]
        for rank_label in ranks:
            rank_value = RANK_OPTIONS[rank_label]
            total, records = fetch_records(
                session=session,
                rank_value=rank_value,
                window_value=window_value,
                page_size=args.page_size,
                sort_field=sort_field,
                timeout=args.timeout,
            )

            if total == 0 and not args.include_empty:
                combo_summaries.append(
                    {
                        "window_label": window_label,
                        "window_value": window_value,
                        "rank_label": rank_label,
                        "rank_value": rank_value,
                        "total": total,
                        "skipped": True,
                    }
                )
                continue

            rows = normalize_rows(
                records=records,
                rank_label=rank_label,
                rank_value=rank_value,
                window_label=window_label,
                window_value=window_value,
                fetched_at_utc=fetched_at_utc,
            )
            all_rows.extend(rows)
            combo_summaries.append(
                {
                    "window_label": window_label,
                    "window_value": window_value,
                    "rank_label": rank_label,
                    "rank_value": rank_value,
                    "total": total,
                    "exported_rows": len(rows),
                    "skipped": False,
                }
            )

    hero_name_by_id = map_hero_names(all_rows)
    enrich_counter_names(all_rows, hero_name_by_id)

    json_path = output_dir / "mlbb_tierlist.json"
    jsonl_path = output_dir / "mlbb_tierlist.jsonl"
    csv_path = output_dir / "mlbb_tierlist.csv"
    markdown_path = output_dir / "mlbb_tierlist_notebooklm.md"
    summary_path = output_dir / "mlbb_tierlist_summary.json"

    write_json(json_path, all_rows)
    write_jsonl(jsonl_path, all_rows)
    write_csv(csv_path, all_rows)
    write_notebooklm_markdown(markdown_path, all_rows)
    rank_markdown_paths = write_notebooklm_markdown_rank_files(output_dir, all_rows)
    summary_path.write_text(
        json.dumps(
            {
                "fetched_at_utc": fetched_at_utc,
                "api_url": API_URL,
                "sort_by": args.sort_by,
                "requested_ranks": ranks,
                "requested_windows": windows,
                "combo_summaries": combo_summaries,
                "output_rows": len(all_rows),
                "output_files": {
                    "json": str(json_path),
                    "jsonl": str(jsonl_path),
                    "csv": str(csv_path),
                    "notebooklm_markdown": str(markdown_path),
                    "notebooklm_markdown_by_rank": [str(p) for p in rank_markdown_paths],
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Export complete. Rows: {len(all_rows)}")
    print(f"JSON: {json_path}")
    print(f"JSONL: {jsonl_path}")
    print(f"CSV: {csv_path}")
    print(f"NotebookLM markdown: {markdown_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
