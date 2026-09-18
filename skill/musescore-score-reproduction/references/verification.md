# Verification contract

`musicxml_audit.py` returns 0 for equality in supported scope, 1 for differences or unresolved review features, and 2 for malformed input/usage. JSON reports always contain `passed` and `status`. Inspect `scope`, `issues`, and `differences`; do not equate an exit 0 with original-PDF reading accuracy.

Default comparison includes events (part, ordinal measure, staff, normalized voice, rational onset, pitch spelling/octave/alteration, duration/type/dots and tuplet ratio), effective key/time/clef/staff/transpose changes, actual bar extent, slur and tie endpoints, basic articulations/fermata/arpeggiation, metronomes, tempo, dynamics, words/rehearsal text, wedge endpoints and barline/repeat/ending records.

- `--display` additionally compares explicitly encoded accidentals, stems and beams. MusicXML may omit automatically inferred beams or accidentals; a difference needs investigation, not blind suppression. A roundtrip-only input usually lacks MuseScore-generated display fields. Therefore content mode plus a documented original-PDF visual review is the recommended default.
- `--layout` compares explicit system/page breaks. It is optional because layout is excluded by default.
- `--merge-voices` compares unique events/marks without voice identity. Keep a separate strict voice version. This is not a generic equivalence relation for arrangements.
- Equivalent `divisions`, numeric voice renumbering and nonnumeric bar labels are normalized. Repeated identical key/clef declarations at system starts do not become fake changes.
- Chord tones share onset. Backup/forward affects cursor. Whole-measure rests use actual duration. Hidden alignment rests are noted and excluded; hidden pitched notes require review.
- Unmatched spans, overlapping sequential events, overfull bars and duration/type inconsistencies are issues. Structural gaps can be legal forward spacing, so underfill is enforced by the entry builder, not guessed from every XML voice.

REVIEW_REQUIRED examples: tuplets, grace notes, lyrics, ornaments, technical notation, unpitched notes, nontraditional signatures, complex meter, staff-details, unsupported directives and unsupported measure children. The tool records these instead of silently certifying them. Cross-voice/staff slurs may need manual resolution.

Not certified: graphical placement, the meaning of arbitrary text, printed accidental inference when not explicitly encoded, timbre, audio playback, repeat traversal correctness, MIDI instruments, part names, arbitrary metadata, pixels, or source-to-reference transcription accuracy. The reviewer must inventory features in the source so omissions from BOTH expected and candidate are not missed.

`score_pipeline.py convert` deliberately leaves `review.json` pending. The reviewer compares original source to exported PDF, fills every part/measure/staff row with `source_content: pass`, `notation_and_beams: pass`, and concrete evidence (page/system, marks inspected, any corrected discrepancy). Set reviewer/method and `reference_independently_checked` truthfully. Unsupported issue resolutions must quote each exact issue, status and evidence. `finalize` checks complete coverage and hashes; it does not claim to verify the truth of these assertions.

Do not provide a script that fills all review rows with pass automatically. Do not promote `transcription-roundtrip` to `independent-reference` simply because both files look alike. A changed MSCZ, PDF, reference or audit invalidates acceptance and requires fresh review.
