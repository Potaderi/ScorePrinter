"""Propose note-bound notation repairs from an independently verified same-edition reference.

Optional accelerator, never a prerequisite for PDF transcription. Refuses event
mismatches or ambiguous anchors. Outputs guarded operations; does not approve them.
"""
import argparse
import copy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from notation import VISUAL
from scorelib import audit, dump, parse, sha, token, xml_root

GROUPS = {'tie', 'notations', 'lyric'}
ORDER = {tag: index for index, tag in enumerate(
    'grace cue chord pitch unpitched rest duration tie instrument footnote level voice type dot accidental time-modification stem notehead notehead-text staff beam notations lyric play listen'.split())}


def clean(node):
    node = copy.deepcopy(node)
    for item in node.iter():
        for key in list(item.attrib):
            if key in VISUAL and not (key == 'placement' and item.tag == 'accidental-mark'):
                del item.attrib[key]
        if item.tag not in ('text','elision') and item.text is not None and not item.text.strip():
            item.text = None
        item.tail = None
    return node


def note_map(path):
    root = xml_root(path)
    normalized = iter(parse(path)['events'])
    mapped = {}
    # Parser emits one event per visible pitched/rest note in XML encounter order.
    for pi, part in enumerate(root.findall('part'), 1):
        for mi, measure in enumerate(part.findall('measure'), 1):
            for ni, note in enumerate(measure.findall('note'), 1):
                if note.get('print-object') == 'no' and note.find('rest') is not None:
                    continue
                if note.find('unpitched') is not None:
                    raise ValueError('Unpitched instrument anchors require direct review')
                if note.find('pitch') is None and note.find('rest') is None:
                    raise ValueError('Unrecognized note anchor')
                event = next(normalized)
                if event['part'] != pi or event['measure'] != mi:
                    raise ValueError('Event/raw-note correspondence failed')
                key = token(event)
                if key in mapped:
                    raise ValueError('Ambiguous duplicate note anchor; use a targeted manual patch')
                mapped[key] = (pi, mi, ni, note)
    if next(normalized, None) is not None:
        raise ValueError('Unmapped note events')
    return root, mapped


def proposal(candidate, reference, evidence, barlines=False):
    if not evidence.strip():
        raise ValueError('Explain independent reference provenance and same-edition verification')
    report = audit(reference, candidate)
    if any(report['differences']['events'].values()) or any(report['differences']['measures'].values()):
        raise ValueError('Align all note/rest events and measures against the PDF before using reference notation repair')
    root, actual = note_map(candidate)
    expected_root, expected = note_map(reference)
    if actual.keys() != expected.keys():
        raise ValueError('Reference note anchors do not match')
    operations = []
    for key, (pi, mi, ni, node) in actual.items():
        ref = expected[key][3]
        ordered = lambda n: sorted((c for c in n if c.tag in GROUPS),key=lambda c: ORDER[c.tag])
        old = [ET.tostring(clean(c), encoding='unicode') for c in ordered(node)]
        new = [ET.tostring(clean(c), encoding='unicode') for c in ordered(ref)]
        if old == new:
            continue
        replacement = copy.deepcopy(node)
        for child in list(replacement):
            if child.tag in GROUPS:
                replacement.remove(child)
        for child in ref:
            if child.tag not in GROUPS:
                continue
            rank = ORDER[child.tag]
            index = next((i for i, c in enumerate(replacement) if ORDER.get(c.tag, 999) > rank), len(replacement))
            replacement.insert(index, clean(child))
        operations.append({'part': pi, 'measure': mi, 'select': f'note[{ni}]', 'op': 'replace',
                           'xml': ET.tostring(replacement, encoding='unicode'),
                           'reason': evidence + '; matched note anchor ' + key})
    if barlines:
        for pi, (part, ref_part) in enumerate(zip(root.findall('part'), expected_root.findall('part')), 1):
            for mi, (measure, ref_measure) in enumerate(zip(part.findall('measure'), ref_part.findall('measure')), 1):
                old, new = measure.findall('barline'), ref_measure.findall('barline')
                if [ET.tostring(clean(n)) for n in old] == [ET.tostring(clean(n)) for n in new]:
                    continue
                for index in range(len(old), 0, -1):
                    operations.append({'part': pi, 'measure': mi, 'select': f'barline[{index}]',
                                       'op': 'remove', 'reason': evidence + '; independently checked barline'})
                for node in new:
                    # Barline location carries semantics; XML child order does not set its time.
                    operations.append({'part': pi, 'measure': mi, 'select': '.', 'op': 'insert',
                                       'xml': ET.tostring(clean(node), encoding='unicode'),
                                       'reason': evidence + '; independently checked barline'})
    return {'schema': 1, 'input_sha256': sha(candidate), 'reference_sha256': sha(reference),
            'reference_evidence': evidence, 'operations': operations,
            'unresolved_audit_issues': report['issues'], 'requires_source_review': True,
            'scope': 'Only ties, note notations, lyrics' + (' and barlines' if barlines else '') +
                     '; notes, directions, signatures, harmony and other score data are retained.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--barlines', action='store_true')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output must be new')
    try:
        result = proposal(args.candidate, args.reference, args.evidence, args.barlines)
        dump(args.out, result)
        print('Proposed operations:', len(result['operations']))
        return 0
    except Exception as error:
        print('REFERENCE PATCH ERROR:', error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
