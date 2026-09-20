---
name: musescore-score-reproduction
description: Turn a new sheet-music PDF into editable MuseScore MSCZ using local OMR, complete-page inspection, targeted correction and source verification. Use for unfamiliar scores, multipage scans and notation beyond the bundled examples; continue correcting the actual source instead of merely running a demo.
metadata:
  short-description: New PDF recognition, correction and MSCZ verification
---

# New PDF to verified MuseScore score

The task is the user's NEW PDF, not reproducing the bundled examples. Start with that PDF. Do not require the user to supply a note JSON, LilyPond, or independent MusicXML. The executing agent is responsible for source reading, correcting recognition errors, checking every original page and delivering the editable score. OMR output is a draft, not completion.

Read [references/new-pdf.md](references/new-pdf.md) first: it contains runnable setup, PDF entry, resume, preprocessing, patching, rebuilding and acceptance commands. Read [references/verification.md](references/verification.md) for comparison boundaries; use [references/input-format.md](references/input-format.md) only when simpler regions need manual JSON entry.

## Default entry

From this skill folder:

```text
python scripts/pdf_to_mscz.py run USER.pdf --out NEW_JOB --engine-config ENGINE/engine-config.json --musescore /path/to/MuseScore --deps PROJECT/deps
```

Python 3.10+, MuseScore, Audiveris and PyMuPDF are required for this path. If Audiveris is not present, `setup_omr.py --out PROJECT/tools/audiveris` explicitly downloads hash-pinned Windows packages and extracts them inside the project, including compatible English OCR data. It does not register a system installation. Other OS packages are available from the official Audiveris releases. Preserve the user's files and use portable MuseScore when existing settings must not change.

If OMR is unavailable, use `run ... --prepare-only` for the source-page workbench, read its images and enter the music with MuseScore/MusicXML. This is a fallback for the actual PDF, never an excuse to substitute Ode or another example.

## Work until the actual source is handled

1. **Read the source inventory before trusting recognition.** Inspect every page, record systems, staves, parts, measure ranges, clefs, signatures, pickup/last-bar lengths and non-note musical content. Include lyrics, chord symbols, tuplets, ornaments, repeats, endings, transpositions, percussion or tablature where present. Empty OMR output does not mean a source page is empty. Encrypted PDFs must first be legitimately unlocked; ambiguous/missing pixels cannot be reconstructed with certainty.
2. **Run the generic pipeline.** It preserves the PDF, renders all pages and overlapping strips, runs local Audiveris, retains every exported work/movement and OMR project, creates real MSCZ files, reopens them, exports PDF/PNG/MusicXML and records structured differences. Nothing in this path selects notes by title, filename or known score hash.
3. **Fix missing coverage first.** Inspect `index.html`, `triage.json` and all source pages. Independent five-line pixel hints help detect omitted staves, but are conservative and cannot cover every notation style. Complete pages/systems omitted by OMR must be transcribed. Check candidate part names/counts against the source. For a scan with broken gray lines, a targeted retry with `--binarize 190 --omr-dpi 300` can help. A second evidence-based retry may be useful; otherwise correct the failed region rather than repeatedly rescanning the whole book.
4. **Correct only what needs changing.** Use Audiveris's saved `.omr` editor for system/staff structure; use MuseScore, explicit MusicXML, or guarded `musicxml_patch.py` for symbols, notes and measures. `pdf_to_mscz.py rebuild` creates a new revision without rerunning OMR; `resume` reuses cached exports after interrupted conversions. A patch checks its input hash, exact target, old value and source-reading reason. For omissions outside the simple JSON builder, retain full MusicXML: do not flatten tuplets, grace notes, cross-staff chords, lyrics, complex repeats or instrumental notation to fit a convenience schema.
5. **Independently reread the original.** Compare each rendered output measure to source pixels. A publisher MusicXML of the same edition is useful if available, but is not a prerequisite. A self-roundtrip only tests conversion. OMR grades, pixel similarity, equal MIDI pitches and a green exit code do not prove source fidelity. Source inventory must catch omissions from both the candidate and its reference. Use high-resolution bands/crops rather than repeatedly scanning whole-page thumbnails.
6. **Verify the complete PDF and final revision.** Fill each current score's `review.json` and whole-job `source-review.json` with actual reviewed evidence. Resolve coverage findings and unsupported symbols explicitly, and include every work/movement. Then run `pdf_to_mscz.py finalize JOB`. A new PDF must use this outer acceptance gate; the lower-level score gate alone misses whole-source omissions. Changed/failed revisions invalidate previous completion. Never fill all review rows automatically.
7. **Deliver the current MSCZ(s) and evidence.** Do not stop at a pending ledger when source images are readable and you can continue editing. If some source information is genuinely unreadable, give its exact page/system/crop and complete the rest; request only the missing musical information. Do not claim arbitrary PDF/handwriting recognition is guaranteed or mark uncertainty as 100% correct.

The user normally wants exact musical content, not identical fonts/margins. Musical text, accidental meaning, beams and collisions that conceal content are relevant. Read the [official handbook](https://handbook.musescore.org/) sections needed for the source's notation; [validated lessons](references/validated-lessons.md) links the specific sections and observed failures.

Read [notation coverage and incremental correction](references/notation-coverage.md) for expanded symbol comparison, changed-measure review and optional independent-reference repair. Rebuild prioritizes affected measures without transferring approval. The workbench displays output pages and caches unchanged diagnostics/crops.

## Tool routing

| Tool | Purpose |
|---|---|
| `pdf_to_mscz.py` | Main new-PDF job: run, resume, rebuild, status, whole-PDF finalize |
| `setup_omr.py` | Explicit hash-pinned project-local Windows OMR setup with full English OCR data |
| `omr_engine.py` | Audiveris batch execution, saved project and symbol/system diagnostics |
| `staff_inventory.py` | Independent five-line pixel hints to flag possible omitted staves |
| `revision_review.py` | Changed measures, span context and downstream review targets |
| `reference_patch.py` | Optional same-edition notation repair with exact note anchors |
| `notation.py` | Lyrics, ornaments, technical notation, harmony and span semantics |
| `musicxml_patch.py` | Guarded targeted XML corrections retaining other notation |
| `score_pipeline.py` | Lower-level MSCZ creation/reopening/audit and per-score review |
| `musicxml_audit.py`, `scorelib.py` | Rational-time events, voice/staff, span and supported notation comparison |
| `build_score.py` | Fast rhythm-checked JSON entry for supported simple regions |
| `lilypond_reference.py` | Optional independent publisher-reference parser for a narrow absolute-pitch subset |
| `source_project.py` | Download provenance and protected-file hash snapshots |
| `pdf_review.py` | Standalone source/render page comparison |
| `demo.py` | Environment self-test only, never the user's transcription task |

Scripts are in `scripts/`. Keep the whole skill folder together. Core comparison and patch scripts use the standard library; PDF jobs need PyMuPDF. Run `python -m unittest discover -s tests -v`; with PyMuPDF importable the suite includes real PDF page preparation. [Validation evidence](references/validation.md) separates old fixtures, unseen PDF integration, deliberate errors, and remaining unsupported verification. The older [quickstart](references/quickstart.md) documents manual entry/demo tools; it is not the default new-PDF path.
