# Recorded validation

Validated on 2026-09-18 using Windows, Python 3.13 and MuseScore Studio 4.6.3 (official portable build). Core tools and tests require only Python's standard library. PyMuPDF is optional for PDF review; it was supplied through a local dependency directory in the PDF integration check. Other operating systems and MuseScore versions have not been integration-tested here.

## Executed checks

- **32 original unit and mutation tests passed in the first release.** Run `python -m unittest discover -s tests -v`. Wrong pitch, octave, rhythm, missing notes, key/meter/tempo, wrong voice assignment, barlines, ties and slur anchors are detected. Beam/accidental mutations fail in display scope. Unsupported notation cannot produce a full automatic PASS. Tests also cover MXL, namespaces, rational divisions, pickups, exact condensation, invalid input, stale hashes and incomplete review.
- **Ode full workflow:** compact JSON -> MusicXML -> actual MSCZ -> separate-process reopen -> PDF/PNG/MusicXML -> independent publisher-note reference: PASS, 245/245 events. Five slurs are compared by endpoints. Original source/map annotations still require the review ledger.
- **Greensleeves:** source parser reads 266 four-voice events. Generic strict roundtrip audit passes 266/266. A newly reopened condensed MSCZ passes 240/240 unique printed events with explicit merge mode. Merge mode does not certify voice assignment.
- **Synthetic pickup example:** actual MSCZ import/reopen/export audit passes for the three-bar 6/8 example with 1/8 pickup, chord, slur and shortened final bar. This is a conversion-fidelity test, not proof against an independent historical score.
- **PDF review:** real source/output PDF pages, overlapping strips and HTML comparison generated successfully.
- **Network source helper:** downloaded the Mutopia Ode PDF and matched pinned SHA-256 `b11e9f934de259ad3b9231e03000e8676cc5e5b85ea917cb387de06a10fe7864`.
- **Acceptance rejection:** attempting to finalize an unreviewed real Ode job correctly returned NOT ACCEPTED. Unit fixtures also verify stale-artifact rejection. Actual demonstration ledgers remain pending; no script marks them reviewed.
- **Portability:** copied the entire skill to an isolated directory and ran its one-command demo from another working directory. It generated a real MSCZ and passed independent-reference comparison without reading the original project's transcription helpers. The final ZIP is also extracted and smoke-tested before delivery.
- **Skill packaging:** the skill-creator quick validator passed. ZIP packaging excludes Python caches and the MuseScore executable.

## What these results mean

These checks demonstrate repeatable construction, conversion and comparison for the supplied cases, including deliberate failure detection. They do not prove arbitrary scanned scores can be read automatically without mistakes. A PASS only certifies equality within the JSON report's supported scope. Final source review must cover all visible musical content and any unsupported constructs.

The supplied demo is immediately runnable with Python and a MuseScore executable. A new score still needs a correct source reading and an independently established reference. Typography and decorative layout are outside the default acceptance target.


## New-PDF workflow validation (2026-09-18)

The expanded suite contains **61 tests**, all passing with PyMuPDF available. It adds guarded pitch/XML edits, stale patch rejection, ambiguous targets, all-movement retention, engine timeout/no-output behavior, conversion recovery from cached exports, invalidation of old successful revisions, every-source-page coverage, missing-staff acceptance blocking, OMR coordinate extraction, and actual two-page PDF preparation. Without PyMuPDF, two page-preparation tests are explicitly skipped; all core tests remain runnable with the standard library.

`setup_omr.py` was run for real into a fresh project folder. It downloaded and verified the fixed hashes, extracted Audiveris 5.11.0 without a system installation, and supplied full English Tesseract data. A subsequent run using the generated engine-config.json processed a previously unseen Mutopia Menuet PDF into MSCZ and a review workbench. The earlier LSTM-only language package failed Audiveris's legacy OCR initialization; setup now deliberately uses the full tessdata 4.1.0 package.

A second holdout used a BWV 269 four-part source, rendered and flattened into a two-page, image-only PDF before recognition. The pipeline was given only this PDF. A withheld MusicXML was used *afterwards* for independent evaluation and correction localization:

- First OMR: 9 staff instances recognized; source-pixel detection found 12 and identified 3 unmatched staves.
- Explicit 190-threshold binarization retry: all 12 staff instances recovered, 228 note events recognized.
- One localized missing Alto B3 quarter was added with a hash-guarded patch and the score rebuilt without rerunning OMR. All 229 note events then matched the withheld reference, with no missing or extra note events.
- Full-score accuracy was NOT established: expression marks, ties/barlines, key-mode metadata and lyrics still need work/review. The independent full-scope audit remained FAIL, and the pipeline kept review pending. This failure is preserved rather than mislabeled as perfect transcription.

The public repository's verification/new-pdf-validation.json records source URLs/hashes, timing, coverage counts and scope-limited results. These inputs are integration cases, not a lookup table: recognition code has no known-title, filename or source-hash branch. Ordinary printed music is the tested OMR case; handwriting, tablature, percussion, severe skew/blur and every complex notation style have not been comprehensively verified. The skill instructs the executing agent to use source images and full MuseScore/MusicXML editing for unsupported regions and to continue correcting, not return an unreviewed draft as complete.
