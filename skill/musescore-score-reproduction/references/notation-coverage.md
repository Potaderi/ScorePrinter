# Notation coverage and efficient correction

The checker compares MusicXML/MXL semantics, not PDF pixels. A source inventory is still necessary to catch features omitted by both files. Unknown notation elements/attributes produce review issues.

| Content | Compared information |
| --- | --- |
| Lyrics | Note association, verse, syllabic boundaries, exact text, elision and extension tags |
| Ornaments and technique | Type, auxiliary accidentals, fermata shape, fingering and supported technical children |
| Grace notes | Sequence at the same onset, pitch/type and encoded grace properties |
| Tuplets | Rational duration ratio and explicit start/end anchors |
| Wedges, octave lines, pedals | Start/end anchors, size/type, endpoint attributes and pedal changes |
| Harmony | Root, kind, inversion, bass, degrees and supported chord-frame content |
| Repeats and endings | Direction/count, ending number/type/text and barline side |
| Parts | Visible names and abbreviations |

Numeric span IDs are pairing labels. Standard fermata/mordent/wedge/octave defaults normalize. A numeric lyric name identical to its verse number is redundant; named verse/chorus types remain distinct. Ornament accidental above/below remains significant. The conventional thick/thin style of a repeat is normalized; other barline changes remain differences. Adjacent font-only lyric text runs merge without losing syllable text.

Use `--display` for explicitly encoded accidental signs, stems and beams. Formatting and margins are excluded. This parser is not a full MusicXML schema validator: arbitrary extensions, every parent attribute, header metadata, instrument playback, repeat traversal and graphical equivalence are not certified. Percussion mapping, nontraditional signatures/meters and cross-staff/voice spans may require manual review. Inspect titles, grouping, custom symbols and collisions in the rendered pages.

## Recheck changes without rerunning recognition

Every successful `pdf_to_mscz.py rebuild` with a preceding revision writes `changes.json`. It lists affected part/measure ordinals, expands changes through intersecting spans, and includes downstream signature/repeat context. Unknown semantics require full review. No approvals transfer.

```text
python scripts/revision_review.py --before old.musicxml --after corrected.musicxml --out changes.json
```

The workbench displays all output PNG pages in numeric order. OMR diagnostics cache by project/parser hashes; source crops cache by source hash, page, rectangle and DPI. Editing a project invalidates its cache. Score edits do not rerun unchanged OMR or source cropping.

## Optional independent-reference repairs

Use only a separately obtained MusicXML of the exact PDF edition. This is optional: new-PDF tasks never require the user to find a reference.

```text
python scripts/reference_patch.py candidate.musicxml --reference same-edition.mxl --evidence "Publisher source URL/version and source-page confirmation" --out proposed.json
python scripts/musicxml_patch.py candidate.musicxml --patch proposed.json --out corrected.musicxml
```

The proposal refuses unequal note/rest events or measure extents, unpitched instruments and ambiguous duplicate anchors. It matches part/measure/staff/voice/onset/duration/pitch/grace events and replaces only ties, note notations and lyrics within matched notes. Add `--barlines` only when reference barlines are independently confirmed. Notes, signatures, directions and harmony are retained. Inspect the proposal, apply its SHA-guarded operations, rebuild and inspect the source/output. A zero-operation proposal needs no application.

To repair titles or part names, a patch may use `"scope": "document"` and a unique selector such as `part-list/score-part[4]/part-name`; omit part/measure for this scope. Source hash, old text and source-reading reason remain required.

## References and actual validation

- [MuseScore MusicXML](https://handbook.musescore.org/file-management/working-with-musicxml-files) and [slurs/ties](https://handbook.musescore.org/notation/expressive-markings/slurs-and-ties).
- MusicXML 4.0: [lyrics](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/lyric/), [tuplets](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/tuplet/), [wedges](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/wedge/), [octave shifts](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/octave-shift/), [pedal](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/pedal/).

MuseScore 4.6.3 import/save/reopen passed a new combined lyric/mordent/fingering/fermata/harmony/wedge fixture. Generic patches corrected the BWV269 scan: 229 events, 52 lyric records, 24 fermatas, four ties, repeats, part labels and explicit display fields match the withheld source. Both final PDF pages were viewed. These are bounded tests, not a universal automatic transcription guarantee.
