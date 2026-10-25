# AI Assignment Checker

Automated lab/assignment marking for professors. Point it at a OneDrive subject
folder (`MCA_LABS`, `PYTHON_ASSIGNMENTS`, a shared `MCA-TEST` folder — any name).
It **reads each submitted file's contents** to find the roll number and
experiment number (filenames can be anything), AI-grades the work against your
rubric, applies the attendance rule, and writes a marks Excel + a reasoning
`.txt` **back into the same folder**. Re-runs update those same two files in
place — no new files pile up.

```
┌─ subject folder ─────────────────────────────────────────────┐
│  24108A0005_Manmit_Samal_MCA_Expt-1.pdf   ─┐                 │
│  gaadi mca.pdf                             ├─ read contents → │ rollno + expt no.
│  Mca_lab1_AJ14.pdf                         ─┘                 │
│  MCA-TEST-ATTENDANCE.xlsx                   ── P/A or 2/0     │
│                                                            │
│  → marks_output.xlsx   (rollno × Assign1..11 + Total)       │
│  → marks_output.txt    (why every mark was given)           │
└──────────────────────────────────────────────────────────────┘
```

---

## Prerequisites (what you actually need)

| Need | Detail |
|---|---|
| **Python 3.11** | `python3.11 --version`. (3.12/3.13 usually fine; avoid 3.14 — some deps lag) |
| **pip packages** | `pip install -r requirements.txt` — pandas, openpyxl, pymupdf, python-docx, httpx, … |
| **Ollama Cloud free-tier key** | From <https://ollama.com> (Settings → API keys). **No local model, no Ollama app, no GPU, no `ollama pull`** — grading happens in the cloud on the free plan. |
| **OneDrive desktop app** | Syncing the professor's subject folder to this machine (any folder path works — it doesn't have to be OneDrive). |

You do **not** need: a local LLM, poppler/`pdftotext`, `docx2txt`, LibreOffice,
or Microsoft Graph API access. PDF and DOCX are parsed natively.

---

## Setup (once)

```bash
git clone https://github.com/Aditya232-rtx/ai_assignment_checker.git
cd ai_assignment_checker
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env and paste your key
```

`.env` (never commit this file — it's gitignored):

```ini
USE_OLLAMA_CLOUD=true
OLLAMA_CLOUD_URL=https://ollama.com/v1
OLLAMA_CLOUD_KEY=<your-free-tier-key>
MODEL_NAME=gemma4:31b-cloud        # any model your plan includes
```

---

## Usage (every grading run)

```bash
python -m checker.cli map-marks <FOLDER_NAME> --rubric rubrics/example_rubric.yaml
```

`<FOLDER_NAME>` is the professor's subject folder — any name, any subject:

```bash
python -m checker.cli map-marks MCA_LABS           --rubric rubrics/example_rubric.yaml
python -m checker.cli map-marks PYTHON_ASSIGNMENTS --rubric rubrics/example_rubric.yaml
python -m checker.cli map-marks MCA-TEST           --rubric rubrics/example_rubric.yaml
```

### Browser frontend

For a simple local control panel, run this from the project root:

```bash
python3 -m checker.cli serve --open
```

It prints the frontend URL (normally `http://127.0.0.1:8765`) and opens it in
your default browser. The panel uses the same `map-marks` pipeline: inspect a
folder, choose deterministic or AI grading, run the marksheet, and open the
reasoning report. Stop the server with `Ctrl+C`.

If `python3` is not on your PATH but the virtual environment is active, use
`python -m checker.cli serve --open` instead.

The easiest repeatable startup command is:

```bash
bash start.sh
```

It creates `.venv` when needed, installs the requirements into that project
environment, and starts the browser frontend.

- **Name matching is forgiving** — case, spaces, underscores and hyphens are
  equivalent: `MCA_LABS` = `mca labs` = `MCA-LABS`.
- **Shared folders work** — OneDrive prefixes shared folders with the sharer
  (`Manoj Suryawanshi's files - MCA-TEST`); passing `MCA-TEST` finds it.
- Searched under `~/Library/CloudStorage/OneDrive*`, `~/OneDrive*`, home and
  `~/Downloads`. Prefer an explicit path? `python -m checker.cli map-marks /full/path/to/folder ...`
- Omit the name entirely to fall back to auto-discovery (`MCA-TEST` → `mca_labs`).

Useful flags:

| Flag | Purpose |
|---|---|
| `--interval 60` | Re-run every 60 s hands-free (new uploads picked up automatically) |
| `--rubric <yaml>` | Rubric file (required unless `--no-grade`) — see `rubrics/example_rubric.yaml` |
| `--no-grade` | No AI: Present+submitted = 10, Absent+submitted = 5 (dry run) |
| `--attendance <file>` | Override auto-detected `*attendance*.xlsx` |
| `--assignments 11` | Number of experiments (default 11) |
| `--output <file>` | Override output path (default: `<folder>/marks_output.xlsx`) |

### What the professor maintains (only two things)

1. **Attendance** — an `attendance*.xlsx` inside the folder:
   `Roll No` column + one column per experiment (`lab1`, `EX-1`, `Experiment 2`, …).
   Cells: `P`/`2`/`1` = present, `A`/`0` = absent.
2. **Student files** — dropped into the same folder, any file names, any nesting.

Everything else (marks sheet, reasoning report, re-grade bookkeeping) is the
tool's job.

---

## How marks are decided

Per student × experiment cell:

| Situation | Mark |
|---|---|
| No submission file | **0** |
| Present + submitted | **AI score / 10** (rubric total, scaled to 10) |
| Absent + submitted | **min(AI score, 5)** — at most 5 |

Roll number and experiment number are extracted from **inside the document**
(body text and DOCX tables), so all of these work equally well:

```
24108A0005_Manmit_Samal_MCA_Expt-1.pdf      → roll 24108A0005, Expt 1
gaadi mca.pdf                               → roll & expt found in the PDF text
Mca_lab1_AJ14.pdf                           → lab number from filename, roll from content
L3_24108A0021.pdf / A5_... / Exp6_...       → terse filename forms
```

Files whose rollno/expt can't be determined are listed under `SKIPPED FILES` in
the report instead of being guessed.

---

## Incremental runs — same two files, updated in place

Run it once for Expt 1, again when Expt 2 submissions arrive, again after
fixing attendance — **the same `marks_output.xlsx` and `marks_output.txt` are
updated every time. No new files are ever created.**

| Change since last run | What happens |
|---|---|
| New submission file | Graded (AI call for that file only) |
| File edited / re-uploaded | Detected via content hash → re-graded |
| Unchanged file | **Reused from cache** — no AI call, runs in seconds |
| Attendance edited | 10/5/0 rule re-applied immediately, without re-grading |
| Rubric or model changed | All files re-graded (cache invalidated on purpose) |

A first AI run costs one AI call per submitted file (19 files ≈ 90 s). A re-run
with nothing new takes **under a second** (`[CACHE] reused 19, newly graded 0`).

The cache lives in a hidden `AI_Grades` sheet inside `marks_output.xlsx` —
don't delete that workbook if you want to keep avoiding re-grade cost (deleting
it is safe, it just re-grades everything).

---

## Output files

**`marks_output.xlsx`** — the `Marks` sheet:

| rollno | Assign1 | Assign2 | … | Assign11 | Total |
|---|---|---|---|---|---|
| 24108A0004 | 10.0 | 0 | | 0 | 10.0 |
| 24108A0005 | 8.0 | 5.0 | | 0 | 13.0 |

**`marks_output.txt`** — human-readable reasoning for every cell: which file was
used, whether the student was present, the per-criterion AI justification with
evidence, which attendance rule applied, and the final mark. Anything the tool
couldn't read (scanned-image PDFs, missing identifiers) is listed with the
reason.

If AI grading fails for a file, the mark falls back to **10** and the report
says so explicitly — failures are never silent.

---

## Tests

```bash
pytest tests/
```

Covers content-based roll/expt extraction, the 10/5/0 rule, attendance code
decoding, incremental cache reuse, folder-name discovery and the CLI
end-to-end flow (offline, using the deterministic fallback grader).

---

## Architecture (for developers)

```
checker/
├── cli.py             map-marks / grade-all / watch / eval commands
├── config.py          .env, Ollama endpoint, find_folder() discovery
├── marks_mapper.py    scan → attendance join → 10/5/0 → xlsx + txt (+ cache)
├── agents/
│   ├── llm.py         shared httpx call to Ollama Cloud (or local)
│   ├── grader.py      rubric → per-criterion scores + justifications
│   └── verifier.py    sanity-checks the grading JSON
├── parser.py          PDF/DOCX/TXT/code → text (pymupdf, python-docx)
├── rubric.py          YAML rubric loader
├── prechecks.py       empty-file / format / duplicate checks
├── db.py, local_ingestor.py, exporter.py   legacy CSV pipeline
rubrics/example_rubric.yaml
```

The legacy `grade-all` / `watch` CSV+SQLite pipeline still exists for
experimentation; the professor flow is `map-marks` only.

## Security notes

- API key lives only in `.env` (gitignored; `.env.example` has placeholders).
- Nothing leaves the machine except anonymised submission text sent to your
  own Ollama Cloud account for grading.
