# Scan correction evidence

The OMR input was a two-page image-only PDF generated from a separately withheld BWV269 MusicXML. After PDF-only recognition, the reference was used to localize errors and prepare guarded repairs. This fixture tests correction and verification; it is not a claim that independent reference data exists for every user PDF.

Reference: https://raw.githubusercontent.com/cuthbertLab/music21/master/music21/corpus/bach/bwv269.mxl

SHA-256: 9676f11a2b26488bcf30db90c15576caa1ea2a616b909e376d44b8b804e9d138

`before.musicxml` is the reopened OMR result after one missing Alto note had already been repaired. Apply these in order from the repository root, with new output paths:

```text
python skill/musescore-score-reproduction/scripts/musicxml_patch.py verification/bwv269-correction/before.musicxml --patch verification/bwv269-correction/notation-fix.json --out notation-corrected.musicxml
python skill/musescore-score-reproduction/scripts/musicxml_patch.py notation-corrected.musicxml --patch verification/bwv269-correction/key-mode-fix.json --out complete-corrected.musicxml
python skill/musescore-score-reproduction/scripts/musicxml_patch.py complete-corrected.musicxml --patch verification/bwv269-correction/labels-fix.json --out labels-corrected.musicxml
```

The first patch corrects 75 note/barline targets; the next restores key-mode metadata; the last repairs part names/abbreviations. Source reading and exact-edition evidence are embedded in each patch. No runtime script recognizes this piece by name or hash.

`score.mscz` was imported from the corrected candidate, then reopened in a separate MuseScore 4.6.3 process to produce `roundtrip.musicxml` and `score.pdf`. `independent-audit.json` compares the withheld source against that export, including explicitly encoded accidentals/stems/beams. There are zero differences/issues in that scope. Both PDF pages were visually inspected. The whole-job per-measure attestation ledger was not automatically marked accepted. Fonts, spacing, page numbering and auxiliary credits are not the content equality claim.
