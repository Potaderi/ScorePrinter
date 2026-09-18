---
name: musescore-score-reproduction
description: Transcribe a PDF or image score into editable MuseScore MSCZ using bundled entry, conversion, reference-audit and visual-review scripts. Use for source-faithful musical content, including multi-voice scores and pickup measures. Scripts do not replace independent reading of the reference.
metadata:
  short-description: Scripted transcription and source-based verification
---

# MuseScore transcription toolkit

This folder is self-contained: copy the entire folder, not just SKILL.md. Python 3.10+ and an installed MuseScore executable are needed. Core scripts use only the standard library. PDF previews optionally use PyMuPDF. No script installs a skill, changes global configuration, or downloads an executable.

Read [references/quickstart.md](references/quickstart.md) for executable commands and the new-task workflow. Read [references/input-format.md](references/input-format.md) before entering a JSON score. For exact coverage, exit codes and manual review requirements, read [references/verification.md](references/verification.md).

## Fast path

From the skill folder, run:

```text
python scripts/demo.py --musescore /absolute/path/to/MuseScore4.exe --out /new/project/demo
```

This builds the bundled 16-measure Ode from compact entry data, independently parses the publisher's LilyPond notes, creates a real MSCZ, reopens it, exports PDF/PNG/MusicXML, and reports differences. The output contains `result/score.mscz`, `audit.json`, `review.json`, provenance hashes and logs. This is a tested example, not a command that transcribes an arbitrary PDF automatically.

## New score workflow

1. Create an isolated project. Preserve source PDF, URL, license and SHA-256 using `source_project.py`. Use a portable MuseScore build when existing application settings must be preserved: environment variables alone do not isolate all Windows/macOS preferences. Do not silently install software or modify files outside the requested project.
2. Read the relevant [official handbook](https://handbook.musescore.org/): note/rest entry, multiple voices, slurs/ties, beams, measure properties, MusicXML and export. Check executable `--help` because the handbook's CLI page includes older options.
3. Crop the source with `pdf_review.py`. Record every staff and voice, pickup/last-bar durations, pitch spelling, dots, rests, notation and structure. With JSON entry, `build_score.py` catches underfilled measures, unknown fields and invalid ties before MuseScore import. For notation beyond the entry schema, use MuseScore GUI or explicit MusicXML; never approximate it to fit the schema.
4. Use a reference independent of the candidate. Prefer publisher MusicXML; the bundled `lilypond_reference.py` accepts only its documented absolute-pitch subset and rejects unknown syntax. When only a PDF exists, independently reread or second-enter the reference. Comparing a candidate to its own input proves conversion fidelity, not reading accuracy. Do not fabricate a source reference by exporting the candidate.
5. Run `score_pipeline.py convert`. It produces a fresh output directory, checks the MSCZ archive, reopens the saved file in another process, renders it, and runs `musicxml_audit.py`. Fix every reported mismatch at its part/measure/staff/onset and rerun into a new directory.
6. Review the original source against the actual output PDF per measure. Explicit accidental display, stems and beams need `--display` with a compatible independent reference or direct visual review. Check all text, expressive notation, repeats and unsupported constructs present in the source. An automated PASS covers only the report's listed fields.
7. Fill `review.json` with actual evidence, never automatic pass flags. Run `score_pipeline.py finalize`. It rejects missing review rows, mismatches, unresolved unsupported features and changed file hashes. It validates the review record; it cannot prove the honesty or correctness of a review assertion.

## Invariants that prevent common mistakes

- Pitch tokens are absolute and literal: `F4` is F natural even under a G-major key signature; write `F#4` when intended. Do not conflate enharmonic spelling.
- Keep voice identities for the audit version. Use `--merge-voices` only for intentional print condensation and retain the voice-preserving MSCZ. It drops voice identity and exact duplicate events by design; that mode cannot certify the independent voice allocation.
- Slurs and ties must have correct start/end note anchors, not just the correct count. Backup/forward and chords affect onset calculations. Short final bars may export as `X1`; compare ordinal measure positions separately from displayed labels.
- A new unknown notation produces REVIEW_REQUIRED, not a success. Annotating a note with an unsupported feature is not permission to omit it.
- Fine typography, page margins and decorative credit layout are excluded unless the user requests them. Missing musical text, ambiguous accidental display, incorrect beams and collisions that hide content are not cosmetic differences.
- Preserve original output files. The pipeline and entry tools refuse existing output destinations. Close ZIP handles before MuseScore writes an archive. Windows portable MuseScore may have `qwindows.dll` without an offscreen plugin.

## Tool index

| Tool | Use |
|---|---|
| `scripts/build_score.py` | Compact JSON -> rhythm-checked MusicXML |
| `scripts/lilypond_reference.py` | Independent narrow source parser; rejects unsupported syntax |
| `scripts/musicxml_audit.py` | Detailed source/candidate event, structure and notation differences |
| `scripts/score_pipeline.py` | Doctor, MSCZ import/reopen/export/audit, final review gate |
| `scripts/source_project.py` | Source download/hash and protected-file snapshots |
| `scripts/pdf_review.py` | Original/render PNG pages, strips and side-by-side HTML |
| `scripts/demo.py` | One-command complete reproducible example |
| `scripts/scorelib.py` | Shared rational-time parser and comparison core |

Run `python -m unittest discover -s tests -v` to verify mutation detection before trusting a changed toolkit. Read [references/validation.md](references/validation.md) for recorded real-score integration results. [references/validated-lessons.md](references/validated-lessons.md) records the specific observed pitfalls.
