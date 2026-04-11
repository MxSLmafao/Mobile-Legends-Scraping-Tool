# MLBB Hero Tierlist Exporter

This project exports hero ranking/tierlist statistics from the Mobile Legends rank data API used by:

- `https://www.mobilelegends.com/rank`

It creates files you can directly ingest into your own AI pipeline or upload to NotebookLM.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

Default export (`ALL` rank, `past_1_day`, sorted by win rate):

```bash
python3 extract_mlbb_tierlist.py
```

Interactive mode (prompts you to pick window/ranks/sort/output):

```bash
python3 extract_mlbb_tierlist.py --interactive
```

Export multiple rank buckets and windows:

```bash
python3 extract_mlbb_tierlist.py \
  --rank all --rank epic --rank legend --rank mythic --rank mythical_honor --rank mythical_glory_plus \
  --window past_7_days \
  --sort-by win_rate
```

Include windows/ranks even when API returns no rows:

```bash
python3 extract_mlbb_tierlist.py --include-empty
```

## Output Files

By default, files are written to `output/`:

- `output/mlbb_tierlist.json` → full structured dataset.
- `output/mlbb_tierlist.jsonl` → one JSON record per line (good for RAG ingestion).
- `output/mlbb_tierlist.csv` → flat spreadsheet-friendly export.
- `output/mlbb_tierlist_notebooklm.md` → NotebookLM-friendly markdown summary with tables.
- `output/notebooklm_ranks/mlbb_tierlist_notebooklm_<rank>.md` → one NotebookLM markdown file per rank bucket.
- `output/mlbb_tierlist_summary.json` → metadata and combo-level extraction summary.

## Suggested Ingestion

- **Custom AI / RAG**: use `mlbb_tierlist.jsonl`.
- **NotebookLM**: upload `mlbb_tierlist_notebooklm.md` (+ optionally CSV for raw table data).
- **NotebookLM (per rank)**: upload the files in `output/notebooklm_ranks/`.

## Notes

- This exporter uses the same rank endpoint the website calls from the browser.
- In the exports, `counter_heroes` refers to heroes the listed hero counters (favorable matchups), matching the site's "COUNTER HERO" column.
- Some window/rank combinations can return zero rows depending on currently available official data.
