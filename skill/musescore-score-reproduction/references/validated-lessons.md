# Lessons backed by the completed scores

1. **Use an independent reference.** Candidate-to-roundtrip comparisons detect conversion loss, not misreading. The publisher LilyPond note bodies caught errors in the original manual entry. Header fields in a reference map still require source-PDF inspection.
2. **Compare spelling, duration and anchors.** Equal MIDI pitches or equal slur counts are insufficient. The auditor uses rational onsets, spelled pitches, voice/staff identity and exact span endpoints. Displayed accidentals and beams need display comparison or visual inspection.
3. **Separate voice preservation from print condensation.** Greensleeves has 266 four-voice events but 240 unique printed events. Equal pitch/onset/duration duplicates may collapse only for the explicitly condensed edition. Different durations cannot collapse. Keep the strict voice-preserving file.
4. **Treat pickups and short final bars as real durations.** The Greensleeves pickup is 1/8 and its last measure is 5/8. MuseScore may export the last bar as X1. Match ordinal positions without coercing displayed labels to integers.
5. **Beam appearance needs its own review.** Default 6/8 beaming can differ from the source, including backward hooks in dotted groups. Equal notes and timing alone cannot certify it. Identical stem directions on simultaneous voices can also create doubled flags or beams.
6. **Reopen the delivered archive.** Always export checks from the saved MSCZ in a separate process. Close Python ZIP handles before MuseScore writes a file. In the tested Windows portable build, qwindows.dll exists but offscreen does not; use the Windows Qt platform.
7. **Do not score whitespace as accuracy.** LilyPond and MuseScore produce different glyph shapes and spacing. Musical content and legibility are the acceptance target unless the user requests typography matching.
8. **Validate inputs before engraving.** The builder rejects underfilled bars, unknown fields, invalid numeric meters, unknown break values and nonconsecutive ties. Symbol-only time-signature changes must be encoded even when the numeric meter is unchanged.
9. **Unknown notation is unresolved work.** The source parser deliberately rejects syntax it cannot interpret. The auditor emits review issues for unsupported notation. Do not delete source features to get a green report.

## Official handbook sections applied

Read the relevant section when extending beyond the bundled examples. These are the official pages used for this workflow, not an assertion that every feature in them is automated.

- [Note and rest entry](https://handbook.musescore.org/basics/entering-notes-and-rests): duration selection, chords and explicit accidental entry.
- [Multiple voices](https://handbook.musescore.org/basics/working-with-multiple-voices): voice completeness and independent rhythms on a staff.
- [Slurs and ties](https://handbook.musescore.org/notation/expressive-markings/slurs-and-ties): distinguish phrasing spans from sustained pitches.
- [Beams](https://handbook.musescore.org/notation/rhythm-meter-and-measures/beams): grouping and beam overrides.
- [Measure properties](https://handbook.musescore.org/notation/rhythm-meter-and-measures/measure-properties): actual duration for pickups and incomplete bars.
- [MusicXML](https://handbook.musescore.org/file-management/working-with-musicxml-files): interchange does not preserve all engraving choices.
- [Export](https://handbook.musescore.org/file-management/file-export): use PDF/PNG for visible content and MusicXML for structured comparison.

The installed executable's --help takes precedence when older CLI documentation differs. Arbitrary LilyPond, OMR accuracy, complex ornaments/repeats, cross-staff notation and audio equivalence were not established by these examples.


## Lessons from previously unseen PDFs

- A successful OMR process can omit whole staves. The two-page scan lost three staff instances without warning. Independently inspecting original page coverage is essential; input/output roundtrip equality cannot catch this.
- Binarizing a low-resolution scan into a separate 300 DPI engine input recovered those three staves. This is a demonstrated fallback, not a default operation to apply blindly to all images.
- OMR note accuracy and symbol accuracy differ. Even after 229 note events matched, fermatas misread as staccatos and missing ties still needed correction. Check expression, lyrics and repeat structure explicitly.
- Audiveris 5.11.0's default legacy OCR needs the full Tesseract model; tessdata_fast lacks legacy components. Engine logs exposed this; setup includes the compatible full model.
- Fix a single omitted note with a guarded patch/rebuild, not an entire new OMR pass. The scan repair was checked against a withheld source and rendered original, with an explicit source-reading reason recorded.
