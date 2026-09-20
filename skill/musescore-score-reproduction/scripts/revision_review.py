"""Locate measures needing renewed review after any MusicXML/MXL revision."""
import argparse
import sys
from pathlib import Path
from scorelib import audit, dump, parse, sha


def revision_changes(before, after):
    report = audit(before, after, display=True)
    old, new = parse(before), parse(after)
    universe = {(m['part'], m['measure']) for s in (old, new) for m in s['measures']}
    targets = {}

    def add(part, measure, reason):
        if (part, measure) in universe:
            targets.setdefault((part, measure), set()).add(reason)

    def locate(item, reason, downstream=False):
        if 'start' in item and 'end' in item:
            start, end = item['start'], item['end']
            for part, measure in universe:
                if start.get('part') == end.get('part') == part and start['measure'] <= measure <= end['measure']:
                    add(part, measure, reason + ': spanning notation')
        elif 'part' in item and 'measure' in item:
            add(item['part'], item['measure'], reason)
            if downstream:
                for part, measure in universe:
                    if part == item['part'] and measure >= item['measure']:
                        add(part, measure, reason + ': downstream context')

    for category, difference in report['differences'].items():
        for side in ('missing', 'extra'):
            for item in difference[side]:
                if category == 'labels':
                    for part, measure in universe:
                        if part == item['part']:add(part,measure,'part label changed')
                locate(item, category + '/' + side,
                       category in ('attributes', 'measures') or item.get('kind') in ('repeat', 'ending'))
    # A changed endpoint or interior note can change the meaning of an unchanged span.
    changed = set(targets)
    for score in (old, new):
        for mark in score['marks']:
            if 'start' not in mark or 'end' not in mark:
                continue
            start, end = mark['start'], mark['end']
            if any(p == start.get('part') == end.get('part') and start['measure'] <= m <= end['measure'] for p, m in changed):
                locate(mark, 'changed music inside ' + mark['kind'])
    if report['issues']:
        for part, measure in universe:
            add(part, measure, 'unsupported semantics: full source review needed')
    return {'schema': 1, 'before_sha256': sha(before), 'after_sha256': sha(after),
            'review_targets': [dict(part=p, measure=m, reasons=sorted(reasons))
                               for (p, m), reasons in sorted(targets.items())],
            'differences': report['differences'], 'issues': report['issues'],
            'approval_transferred': False,
            'note': 'Prioritize these measures and their source regions. This does not approve other measures or certify the PDF.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--after', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output must be new')
    try:
        result = revision_changes(args.before, args.after)
        dump(args.out, result)
        print('Measures requiring renewed review:', len(result['review_targets']))
        return 0
    except Exception as error:
        print('REVISION ERROR:', error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
