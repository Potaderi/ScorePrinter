# Recorded validation

Validated on 2026-09-18 using Windows, Python 3.13 and MuseScore Studio 4.6.3 (official portable build). Core tools and tests require only Python's standard library. PyMuPDF is optional for PDF review; it was supplied through a local dependency directory in the PDF integration check. Other operating systems and MuseScore versions have not been integration-tested here.

## Executed checks

- **32 unit and mutation tests passed.** Run `python -m unittest discover -s tests -v`. Wrong pitch, octave, rhythm, missing notes, key/meter/tempo, wrong voice assignment, barlines, ties and slur anchors are detected. Beam/accidental mutations fail in display scope. Unsupported notation cannot produce a full automatic PASS. Tests also cover MXL, namespaces, rational divisions, pickups, exact condensation, invalid input, stale hashes and incomplete review.
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
