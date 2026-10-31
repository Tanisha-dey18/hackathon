# SENTINEL Documentation Set

Documentation for **PROJECT SENTINEL**, prepared for the PayPal AI Hackathon 2026. Everything here was written from the actual repository: metrics, test results and screenshots come from the running system.

> Hackathon prototype using PayPal Sandbox and synthetic data. Not an officially deployed PayPal fraud prevention product.

## Which document to use

| File | Pages | Use it for |
|---|---|---|
| `SENTINEL_Complete_Project_Report.pdf` | 72 | The full report (Parts 1–20): hackathon submission, college project documentation, technical evaluation. Parts 1–4 are for non-technical readers. |
| `SENTINEL_Technical_Architecture.pdf` | 31 | PayPal engineers and technical judges: architecture, stack, ML, graph, agent, PayPal integration, database/API, security, testing, limitations. |
| `SENTINEL_Project_Quick_Overview.pdf` | 3 | Recruiters and judges who have two minutes. |
| `SENTINEL_Viva_and_Interview_Guide.pdf` | 18 | Preparing for viva or interviews: 110 questions with short answers, deeper explanations and follow-ups, plus pitches and resume/LinkedIn/GitHub/submission text. |
| `SENTINEL_Project_Documentation.md` | – | Editable source of the complete report (renders on GitHub; diagrams as SVG, screenshots in `assets/`). |

## Folder layout

```
SENTINEL_DOCUMENTATION/
  *.pdf                          generated documents
  SENTINEL_Project_Documentation.md
  assets/                        17 real application screenshots
  assets/diagrams/               7 architecture diagrams (SVG)
  source/
    part_a.md ... part_e.md      report source (Parts 1–20)
    quick_overview.md            source of the quick overview
    diagrams.py                  diagram definitions (ReportLab graphics)
    build_pdfs.py                generator
```

## Regenerating

Edit the Markdown in `source/` (not the exported `.md`), then run from the repository root:

```
backend/.venv/Scripts/python -m pip install reportlab
backend/.venv/Scripts/python SENTINEL_DOCUMENTATION/source/build_pdfs.py
```

The generator embeds Segoe UI and Consolas from `C:\Windows\Fonts` (DejaVu as a fallback).

## Accuracy notes

- Model metrics are from model version v1 on a 500-row hold-out set of **synthetic** data.
- Test results are from the 23-test `pytest` suite (all passing at time of writing).
- Live PayPal Sandbox capture, Groq LLM investigations and Docker/Render runtime were **not executed** during development; the documents say so wherever relevant.
- "Prepared by" uses the repository author name (Tanisha Dey); change `AUTHOR` in `source/build_pdfs.py` if needed.
