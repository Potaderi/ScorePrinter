"""Apply guarded, score-independent MusicXML corrections without flattening notation."""
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from scorelib import dump, load, sha, xml_root


def apply_patch(source, specification):
    if specification.get('input_sha256') != sha(source):
        raise ValueError('Patch was prepared for another revision; inspect the current score first')
    root = xml_root(source)
    operations = specification.get('operations', [])
    if not operations:
        raise ValueError('No correction operations')
    for operation in operations:
        if not operation.get('reason', '').strip():
            raise ValueError('Every correction needs a source-reading reason')
        scope = operation.get('scope','measure')
        if scope == 'document':
            measure = root
        elif scope == 'measure':
            if int(operation['part']) < 1 or int(operation['measure']) < 1:
                raise ValueError('Part/measure addresses are 1-based ordinals')
            part = root.findall('part')[int(operation['part'])-1]
            measure = part.findall('measure')[int(operation['measure'])-1]
        else:
            raise ValueError('Unknown correction scope: '+str(scope))
        selector = operation.get('select', '.')
        targets = [measure] if selector == '.' else measure.findall(selector)
        if len(targets) != 1:
            raise ValueError(f'Correction selector must match exactly once: {selector} ({len(targets)})')
        node = targets[0]
        mode = operation['op']
        if mode == 'text':
            if 'before' not in operation or (node.text or '') != operation['before']:
                raise ValueError('Text precondition failed')
            node.text = str(operation['after'])
        elif mode == 'attribute':
            key = operation['name']
            if 'before' not in operation or node.get(key) != operation['before']:
                raise ValueError('Attribute precondition failed')
            node.set(key, str(operation['after']))
        elif mode in ('remove', 'replace'):
            parent = next((p for p in root.iter() if node in list(p)), None)
            if parent is None:
                raise ValueError('Cannot replace root')
            index = list(parent).index(node)
            parent.remove(node)
            if mode == 'replace':
                parent.insert(index, ET.fromstring(operation['xml']))
        elif mode == 'insert':
            index = int(operation.get('index', len(node)))
            if not 0 <= index <= len(node):
                raise ValueError('Insert index outside parent')
            node.insert(index, ET.fromstring(operation['xml']))
        else:
            raise ValueError('Unknown correction operation: ' + str(mode))
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--patch', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError('Correction output must be new')
        spec = load(args.patch)
        root = apply_patch(args.source, spec)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(root).write(args.out, encoding='utf-8', xml_declaration=True)
        dump(args.out.with_suffix(args.out.suffix+'.corrections.json'),
             {'input_sha256': sha(args.source), 'output_sha256': sha(args.out), 'patch': spec})
        print('Corrected:', args.out)
        return 0
    except Exception as error:
        print('CORRECTION ERROR:', error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
