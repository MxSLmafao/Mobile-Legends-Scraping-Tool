# MLBB Data Extraction Tool

This project exports Mobile Legends data from:

- `https://www.mobilelegends.com/rank`
- `https://www.mobilelegends.com/hero` (rendered page scraping with Playwright)

It creates files you can directly ingest into your own AI pipeline to train it or upload to services like NotebookLM.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
```

## Quick Start

Tierlist default export (`ALL` rank, `past_1_day`, sorted by win rate):

```bash
python3 extract_mlbb_tierlist.py
```

Tierlist interactive mode (prompts you to pick window/ranks/sort/output):

```bash
python3 extract_mlbb_tierlist.py --interactive
```

Hero detail export (all heroes in `herolist.md`):

```bash
python3 extract_mlbb_heroes.py
```

Hero exporter interactive mode (prompts for output formats/options):

```bash
python3 extract_mlbb_heroes.py --interactive
```

Hero detail exporter with selected formats only:

```bash
python3 extract_mlbb_heroes.py \
  --format json --format jsonl --format md --format per_hero_md --format summary \
  --limit 10
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

By default, files are written to `output/`.

Tierlist files:

- `output/mlbb_tierlist.json` → full structured dataset.
- `output/mlbb_tierlist.jsonl` → one JSON record per line (good for RAG ingestion).
- `output/mlbb_tierlist.csv` → flat spreadsheet-friendly export.
- `output/mlbb_tierlist_notebooklm.md` → NotebookLM-friendly markdown summary with tables.
- `output/notebooklm_ranks/mlbb_tierlist_notebooklm_<rank>.md` → one NotebookLM markdown file per rank bucket.
- `output/mlbb_tierlist_summary.json` → metadata and combo-level extraction summary.

Hero detail files (default output dir: `output/hero_details`):

- `output/hero_details/mlbb_hero_details.json` → all heroes in one structured JSON.
- `output/hero_details/mlbb_hero_details.jsonl` → one hero record per line.
- `output/hero_details/mlbb_hero_details_notebooklm.md` → one combined markdown document.
- `output/hero_details/heroes/hero_<id>_<name>.md` → one markdown file per hero.
- `output/hero_details/mlbb_hero_details_summary.json` → run summary + failed heroes.

## Suggested Ingestion

- **Tierlist for custom AI / RAG**: use `mlbb_tierlist.jsonl`.
- **Tierlist for NotebookLM**: upload `mlbb_tierlist_notebooklm.md` (+ optional per-rank files in `output/notebooklm_ranks/`).
- **Hero detail for custom AI / RAG**: use `output/hero_details/mlbb_hero_details.jsonl`.
- **Hero detail for NotebookLM**: upload `output/hero_details/mlbb_hero_details_notebooklm.md` or per-hero files in `output/hero_details/heroes/`.

## Notes

- `extract_mlbb_tierlist.py` uses website rank API calls.
- `extract_mlbb_heroes.py` uses Playwright and clicks each skill icon to extract the rendered skill text and combos.
- In the exports, `counter_heroes` refers to heroes the listed hero counters (favorable matchups), matching the site's "COUNTER HERO" column.
- Some window/rank combinations can return zero rows depending on currently available official data.
