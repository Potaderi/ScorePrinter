# Input schema

The entry builder handles one part, one or more standard staves, up to four voices per staff, single numeric time signatures, key fifths, clefs, pickup/short bars, chords, rests, dotted values, whole-chord ties, slurs, beam overrides and note articulations. It does not encode arbitrary MusicXML or every MuseScore feature.

Use `examples/pickup-entry.json` as a short starter or `examples/ode-entry.json` as a complete four-voice example.

- `title`, `composer`, `source`: text metadata.
- `key`: signed fifths, e.g. 1 = G major/E minor signature. Written pitches remain literal.
- `time`: `[beats, beat_type]`, e.g. `[6,8]`.
- `time_symbol`: `normal`, `common`, or `cut`.
- `tempo`: quarter-note beats per minute.
- `staves`: ordered `{sign: G/F/C, line: number, octave: optional integer}` records.
- `voices`: ordered `{id: name, staff: 1-based staff index}` records. Voice IDs must be unique.
- `measures`: ordered records. Each contains `voices`, a mapping from every voice ID to space-separated tokens. Optional `number` is a display label; `length` is actual duration in quarter-note units (`1/2` for an eighth pickup, `5/2` for five eighths). Without `length`, duration follows the active meter. Optional `key`, `time`, `time_symbol` change signatures. `break` is `system` or `page` and occurs BEFORE this measure. `barline` is a MusicXML bar-style after it. `repeat` accepts only `backward` at the right barline; use explicit MusicXML for repeat starts/endings.
- `slurs`: `{start:[measure,voice,event],end:[measure,voice,event],placement:optional above/below}`. All indices here are 1-based ORDINALS, including the pickup, regardless of printed measure labels. Events count chords/rests, not chord tones.
- `ties`: same start/end addresses. Endpoints must be consecutive events in the same voice and both whole chords must have the same spelling; partial-chord ties need explicit MusicXML.
- `note_marks`: `{at:[measure,voice,event],stem:optional up/down,beams:optional list,accidental:optional name,parentheses:optional true,articulation:optional MusicXML element name}`. Accidentals apply to every note of the target chord; use explicit MusicXML for per-tone exceptions.

Tokens:

```text
C4q       middle C quarter
F#4e.     F-sharp octave 4 dotted eighth
Bb3s      B-flat octave 3 sixteenth
C##5h     C double-sharp octave 5 half note
Rw        whole rest
Rm        whole-measure rest (actual bar duration)
[E3,G3,B3]q   chord, one quarter-note event
```

Durations: `w h q e s t x` = whole, half, quarter, eighth, sixteenth, 32nd, 64th. One or two dots permitted. Rest is uppercase R. A plain F is NATURAL, not key-relative. Every voice must fill each measure exactly, including rests. Do not invent hidden rests to repair a misread rhythm.

For unsupported tuplets, grace notes, lyrics, hairpins, complex repeats, cross-staff notes, or additional instruments, enter/edit using MuseScore or MusicXML and let the auditor report its supported scope and manual-review needs. Never silently flatten these features into simple notes.

The LilyPond reference map is a different input: it contains voice IDs/staves/publisher variable names, measure `lengths` in quarters, header/structural annotations independently read from PDF, and optional pinned source hash. Its parser reads absolute pitch variables only, octave-only transpose `c` to `c'`, inherited durations, rests and slurs. Relative pitch, repeats, functions, chords, ties, ornaments and unrecognized tokens are rejected. A configured trailing spacer is the only skipped duration. Headers supplied by the map are NOT independently proven by parsing the note bodies.
