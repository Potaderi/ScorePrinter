"""New PDF -> local OMR -> ALL score candidates -> MSCZ -> source review/correction."""
import argparse
import html
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from scorelib import dump, load, sha, xml_root
from score_pipeline import convert, executable, finalize as finalize_score, run_ms
from omr_engine import find_engine, run_engine, project_diagnostics
from staff_inventory import staff_hints, coverage_findings


def pdf_module(deps=None):
    if deps:
        sys.path.insert(0, str(Path(deps).resolve()))
    try:
        import pymupdf
        return pymupdf
    except ImportError as error:
        raise ValueError('PyMuPDF needed: python -m pip install --target <project>/deps pymupdf; '
                         'then pass --deps <project>/deps') from error


def relative(job, path):
    return Path(path).resolve().relative_to(job.resolve()).as_posix()


def contained(job, name):
    path = (job / name).resolve()
    if not path.is_relative_to(job.resolve()):
        raise ValueError('Job path escapes its directory')
    return path


def read_job(job):
    job = Path(job).resolve()
    state = load(job/'job.json')
    if state['source_sha256'] != sha(job/'source.pdf'):
        raise ValueError('Source PDF changed; create a new job')
    return job, state


def prepare(pdf, job, deps=None, dpi=180):
    module = pdf_module(deps)
    pdf, job = Path(pdf).resolve(), Path(job).resolve()
    if job.exists():
        raise ValueError('Output exists. Use resume/rebuild rather than overwriting a job.')
    if not 100 <= dpi <= 400:
        raise ValueError('Review DPI must be 100..400')
    with module.open(pdf) as doc:
        if not doc.is_pdf or doc.needs_pass or not doc.page_count:
            raise ValueError('Input must be a nonempty unlocked PDF')
        job.mkdir(parents=True)
        shutil.copy2(pdf, job/'source.pdf')
        pages = []
        (job/'source-pages').mkdir()
        for index, page in enumerate(doc, 1):
            # Review files preserve full page coverage, even if OMR misses every staff.
            name = f'source-pages/page-{index:04d}.png'
            page.get_pixmap(dpi=dpi, alpha=False).save(job/name)
            bands = []
            for band in range(4):
                box = module.Rect(0, max(0, (band/4-.025)*page.rect.height), page.rect.width,
                                  min(page.rect.height, ((band+1)/4+.025)*page.rect.height))
                strip = f'source-pages/page-{index:04d}-band-{band+1}.png'
                page.get_pixmap(dpi=min(400, max(240,dpi)), clip=box, alpha=False).save(job/strip)
                bands.append(strip)
            gray = page.get_pixmap(dpi=150, colorspace=module.csGRAY, alpha=False)
            hints = staff_hints(gray.samples, gray.width, gray.height)
            pages.append({'page': index, 'image': name, 'bands': bands, 'staff_hints': hints,
                          'width': page.rect.width, 'height': page.rect.height,
                          'embedded_images': len(page.get_images()),
                          'text_characters': len(page.get_text()), 'rotation': page.rotation})
    state = {'schema': 1, 'source_sha256': sha(job/'source.pdf'), 'pages': pages,
             'scores': [], 'attempts': [], 'status': 'PREPARED', 'errors': []}
    dump(job/'job.json', state)
    dump(job/'source-review.json', {'source_sha256': state['source_sha256'],
          'reviewer': '', 'method': '', 'pages': [
              {'page': p['page'], 'classification': 'pending', 'status': 'pending',
               'source_inventory': '', 'score_ids': [], 'evidence': ''} for p in pages],
          'score_revisions': {}, 'coverage_resolutions': [], 'note': 'Inventory EVERY system, staff, measure and musical text on '
          'every page, including regions OMR missed. Use classification music or non-music. '
          'Non-music exclusions require evidence. Fill score_revisions after reviewing current MSCZ hashes.'})
    write_index(job, state)
    return state


def write_index(job, state):
    parts = ['<!doctype html><meta charset="utf-8"><title>PDF transcription review</title>',
             '<style>body{font:16px system-ui;max-width:1300px;margin:auto}img{max-width:100%}'
             '.row{display:flex;gap:1em}.row>*{width:49%}li{margin:8px}</style>',
             '<h1>Source PDF → MSCZ review</h1>',
             '<p>Review all source pages and all output scores. Page layout may differ. '
             'OMR confidence is not accuracy. Unknown or missing symbols require correction.</p>',
             '<p><a href="source-review.json">Whole-source coverage</a> · '
             '<a href="triage.json">Prioritized findings</a> · <a href="job.json">Job state</a></p>',
             '<h2>Output scores / movements</h2><ul>']
    for item in state['scores']:
        rev = item.get('current')
        if not rev:
            parts.append(f'<li>{html.escape(item["id"])}: needs transcription</li>')
            continue
        parts.append(f'<li>{html.escape(item["id"])}: '
                     f'<a href="{rev}/score.mscz">MSCZ</a> · <a href="{rev}/score.pdf">PDF</a> · '
                     f'<a href="{rev}/audit.json">audit</a> · <a href="{rev}/review.json">review</a></li>')
    parts.append('</ul><h2>Every original page</h2>')
    for page in state['pages']:
        parts.append(f'<details open><summary>Page {page["page"]}</summary>'
                     f'<img loading="lazy" src="{page["image"]}"><p>High resolution bands: ')
        parts.extend(f'<a href="{band}">{i}</a> ' for i,band in enumerate(page['bands'],1))
        parts.append('</p></details>')
    triage = load(job/'triage.json') if (job/'triage.json').exists() else {'items': []}
    parts.append('<h2>Located OMR / notation findings</h2>')
    for item in triage['items']:
        label = html.escape(str(item.get('reason', item.get('kind','review'))))
        parts.append(f'<details><summary>{html.escape(str(item.get("page","?")))}: {label}</summary>')
        parts.append('<pre>'+html.escape(str(item))+'</pre>')
        if item.get('crop'):
            parts.append(f'<img loading="lazy" src="{item["crop"]}">')
        parts.append('</details>')
    (job/'index.html').write_text('\n'.join(parts), encoding='utf-8')


def make_triage(job, state, deps=None):
    module = pdf_module(deps)
    with module.open(job/'source.pdf') as source:
        for record in state['pages']:
            if 'staff_hints' not in record:
                gray = source[record['page']-1].get_pixmap(dpi=150, colorspace=module.csGRAY, alpha=False)
                record['staff_hints'] = staff_hints(gray.samples, gray.width, gray.height)
    items = []
    recognized_staves = []
    latest_diagnostics = False
    for attempt in state['attempts']:
        folder = contained(job, attempt)
        if not (folder/'engine.json').is_file():
            items.append({'reason': 'Interrupted OMR attempt', 'attempt': attempt})
            continue
        report = load(folder/'engine.json')
        for warning in report['warnings']:
            items.append({'reason': 'engine warning', 'details': warning, 'attempt': attempt})
        for project in sorted((folder/'export').rglob('*.omr')):
            try:
                diagnostics = project_diagnostics(project)
                dump(project.with_suffix('.diagnostics.json'), diagnostics)
                if report.get('preprocessing',{}).get('rotate',0):
                    for item in diagnostics['findings']+diagnostics['systems']:
                        item.pop('bbox',None)
                    items.append({'reason': 'Rotated OMR geometry requires direct source-page review', 'attempt': attempt})
                if attempt == state['attempts'][-1] and not report.get('preprocessing',{}).get('rotate',0):
                    latest_diagnostics = True
                    recognized_staves.extend(diagnostics['staves'])
                items.extend(dict(item, project=relative(job, project)) for item in diagnostics['findings'])
                # Every recognized system is available as a crop, including high-grade symbols.
                items.extend(dict(item, reason='inspect complete source system', project=relative(job, project))
                             for item in diagnostics['systems'])
                for sheet in diagnostics['sheets']:
                    if not sheet['completed'] or sheet['invalid']:
                        items.append(dict(sheet, reason='OMR did not complete this source page'))
            except Exception as error:
                items.append({'reason': 'OMR diagnostics unavailable', 'details': str(error)})
    if latest_diagnostics:
        hints = [dict(hint,page=page['page']) for page in state['pages'] for hint in page.get('staff_hints',[])]
        items.extend(coverage_findings(hints, recognized_staves))
    for score in state['scores']:
        if not score.get('current'):
            continue
        current = contained(job, score['current'])
        if not (current/'audit.json').exists():
            items.append({'reason': 'Audit unavailable for converted file', 'score': score['id']})
            continue
        report = load(current/'audit.json')
        for issue in report['issues']:
            items.append(dict(issue, score=score['id']))
        for category, difference in report['differences'].items():
            for side in ('missing','extra'):
                for event in difference[side]:
                    items.append({'reason': 'conversion difference', 'score': score['id'],
                                  'kind': category, 'side': side, 'location': event})
    module = pdf_module(deps)
    dump(job/'job.json', state)
    (job/'crops').mkdir(exist_ok=True)
    with module.open(job/'source.pdf') as doc:
        for index, item in enumerate(items):
            box, number = item.get('bbox'), item.get('page')
            if box and number and 1 <= number <= len(doc):
                page = doc[number-1]
                clip = module.Rect(box[0]*page.rect.width, box[1]*page.rect.height,
                                   box[2]*page.rect.width, box[3]*page.rect.height)
                if clip.is_empty:
                    continue
                name = f'crops/item-{index:05d}.png'
                page.get_pixmap(dpi=240, clip=clip, alpha=False).save(job/name)
                item['crop'] = name
    for item in items:
        if item.get('kind') == 'coverage':
            item['id'] = f'coverage-page-{item["page"]}-y-{item["center"]:.6f}'
    dump(job/'triage.json', {'items': items, 'accuracy_claim': False,
                            'note': 'Triage is a priority queue, not exhaustive source verification.'})
    write_index(job, state)


def make_revision(job, state, score, candidate, musescore, reference=None, timeout=180):
    exe = executable(musescore)
    revisions = score.setdefault('revisions', [])
    index = len(revisions)+1
    folder = job/'scores'/score['id']/f'rev-{index:03d}'
    inputs = job/'inputs'
    inputs.mkdir(exist_ok=True)
    candidate = Path(candidate).resolve()
    local = inputs/(score['id']+f'-{index:03d}'+candidate.suffix.lower())
    if local.exists() or folder.exists():
        raise ValueError('Revision destination already exists; do not overwrite failed work')
    shutil.copy2(candidate, local)
    if reference:
        expected = inputs/(score['id']+f'-{index:03d}-reference'+Path(reference).suffix.lower())
        shutil.copy2(reference, expected)
    elif local.suffix.lower() == '.mscz':
        baseline = inputs/(score['id']+f'-{index:03d}-baseline')
        baseline.mkdir()
        expected = baseline/'input.musicxml'
        run_ms(exe, ['-o', expected, local], baseline, 'export-baseline', timeout)
    else:
        expected = local
    entry = {'path': relative(job, folder), 'candidate_sha256': sha(local),
             'reference_role': 'independent-reference' if reference else 'transcription-roundtrip'}
    revisions.append(entry)
    # Save before starting a tool: an interrupted operation remains visible/recoverable.
    dump(job/'job.json', state)
    try:
        convert(SimpleNamespace(input=local, expected=expected, source=job/'source.pdf',
                                out=folder, musescore=str(exe), timeout=timeout,
                                expected_role=entry['reference_role'], display=False,
                                layout=False, merge_voices=False))
        score['current'] = relative(job, folder)
        score['mscz_sha256'] = sha(folder/'score.mscz')
        entry['state'] = 'REVIEW_REQUIRED'
        entry['audit_status'] = load(folder/'audit.json')['status']
        # Successful conversion never certifies a PDF reading.
        state['status'] = 'REVIEW_REQUIRED'
        review = load(job/'source-review.json')
        review['score_revisions'].pop(score['id'], None)
        dump(job/'source-review.json', review)
    except Exception as error:
        score.pop('current', None)
        score.pop('mscz_sha256', None)
        entry['state'] = 'CONVERSION_FAILED'
        entry['error'] = str(error)
        state['errors'].append({'score': score['id'], 'revision': entry['path'], 'error': str(error)})
        state['status'] = 'NEEDS_CORRECTION'
    state['status'] = 'REVIEW_REQUIRED' if all(s.get('current') and s['revisions'][-1].get('audit_status') != 'FAIL' for s in state['scores']) else 'NEEDS_CORRECTION'
    dump(job/'job.json', state)


def prepared_engine_pdf(job, folder, args):
    if args.binarize is None and args.rotate == 0:
        return job/'source.pdf'
    module = pdf_module(args.deps)
    folder.parent.mkdir(parents=True, exist_ok=True)
    output = folder.parent/(folder.name+'-preprocessed.pdf')
    if output.exists():
        raise ValueError('Prepared attempt PDF already exists')
    with module.open(job/'source.pdf') as source, module.open() as target:
        for page in source:
            pix = page.get_pixmap(dpi=args.omr_dpi, colorspace=module.csGRAY, alpha=False)
            if args.binarize is not None:
                table = bytes(0 if x < args.binarize else 255 for x in range(256))
                pix = module.Pixmap(module.csGRAY, pix.width, pix.height, pix.samples.translate(table), False)
            # Only explicit right-angle rotation; no speculative automatic alteration of notation.
            rotation = args.rotate % 360
            width,height = page.rect.width,page.rect.height
            if rotation in (90,270):
                width,height = height,width
            dest = target.new_page(width=width,height=height)
            dest.insert_image(dest.rect,stream=pix.tobytes('png'),rotate=rotation)
        target.save(output)
    return output


def recognize(job, state, args):
    if state['attempts'] and not args.retry_omr:
        print('Cached OMR retained; retrying only unfinished conversions.')
        # Discover exports after an interrupted conversion without running OMR again.
        for attempt in state['attempts']:
            folder = contained(job, attempt)
            if not (folder/'engine.json').exists():
                continue
            for candidate in load(folder/'engine.json')['candidates']:
                origin = relative(job, contained(folder, candidate))
                if any(s.get('origin') == origin for s in state['scores']+state.get('superseded_scores', [])):
                    continue
                used = state['scores']+state.get('superseded_scores', [])
                state['scores'].append({'id': f'{max([int(s["id"]) for s in used]+[0])+1:03d}',
                                        'origin': origin, 'revisions': []})
        for score in state['scores']:
            if not score.get('current') and score.get('origin', '').startswith('omr/'):
                make_revision(job, state, score, contained(job, score['origin']), args.musescore,
                              timeout=args.convert_timeout)
        if state['scores']:
            state['status'] = 'REVIEW_REQUIRED' if all(s.get('current') and s['revisions'][-1].get('audit_status') != 'FAIL' for s in state['scores']) else 'NEEDS_CORRECTION'
        dump(job/'job.json', state)
        return
    exe = find_engine(args.audiveris)
    folder = job/'omr'/f'attempt-{len(state["attempts"])+1:03d}'
    state['attempts'].append(relative(job, folder))
    dump(job/'job.json', state)
    engine_pdf = prepared_engine_pdf(job, folder, args)
    report = run_engine(engine_pdf, folder, exe, args.timeout, args.tessdata)
    report['preprocessing'] = {'binarize': args.binarize, 'dpi': args.omr_dpi, 'rotate': args.rotate}
    dump(folder/'engine.json', report)
    if report['timed_out'] or report['returncode']:
        state['errors'].append({'attempt': relative(job, folder), 'error': 'Engine failed or timed out; inspect log'})
    # An explicit retry creates a fresh candidate set; old revisions stay on disk.
    if args.retry_omr and state['scores']:
        state.setdefault('superseded_scores', []).extend(state['scores'])
        state['scores'] = []
    for candidate in report['candidates']:
        identifier = f'{len(state.get("superseded_scores",[]))+len(state["scores"])+1:03d}'
        score = {'id': identifier, 'origin': relative(job, contained(folder, candidate)), 'revisions': []}
        state['scores'].append(score)
        make_revision(job, state, score, contained(folder, candidate), args.musescore, timeout=args.convert_timeout)
    if not report['candidates']:
        state['status'] = 'NEEDS_TRANSCRIPTION'
    dump(job/'job.json', state)


def accept(job):
    job, state = read_job(job)
    review = load(job/'source-review.json')
    errors = []
    if review.get('source_sha256') != state['source_sha256']:
        errors.append('Source coverage review is stale')
    if not review.get('reviewer','').strip() or not review.get('method','').strip():
        errors.append('Source reviewer and method are required')
    rows = review.get('pages', [])
    expected_pages = {p['page'] for p in state['pages']}
    if len(rows) != len(expected_pages) or {p['page'] for p in rows} != expected_pages:
        errors.append('Every original PDF page must be accounted for exactly once')
    coverage = [i for i in load(job/'triage.json')['items'] if i.get('kind')=='coverage'] if (job/'triage.json').exists() else []
    resolutions = review.get('coverage_resolutions', [])
    for issue in coverage:
        matches = [r for r in resolutions if r.get('id') == issue['id'] and r.get('status') == 'pass' and r.get('evidence','').strip()]
        if len(matches) != 1:
            errors.append('Unresolved source coverage finding: '+issue['id'])
    ids = {s['id'] for s in state['scores']}
    linked = set()
    if not ids:
        errors.append('No completed score; transcribe missing music')
    for row in rows:
        if row.get('status') != 'pass' or not row.get('evidence','').strip():
            errors.append(f'Unreviewed original page {row.get("page")}')
        if row.get('classification') == 'music':
            links = set(row.get('score_ids', []))
            if not row.get('source_inventory','').strip() or not links or not links <= ids:
                errors.append(f'Missing source inventory/output mapping on page {row.get("page")}')
            linked |= links
        elif row.get('classification') != 'non-music':
            errors.append(f'Unclassified original page {row.get("page")}')
    if linked != ids:
        errors.append('Source-to-score mapping does not cover every output')
    if state['attempts']:
        latest = contained(job,state['attempts'][-1])
        if (latest/'engine.json').exists():
            registered = {s.get('origin') for s in state['scores']}
            for export in load(latest/'engine.json')['candidates']:
                if relative(job,contained(latest,export)) not in registered:
                    errors.append('OMR export not represented by a score: '+export)
    for score in state['scores']:
        if (not score.get('current') or not score.get('revisions')
                or score['revisions'][-1].get('state') != 'REVIEW_REQUIRED'
                or score['revisions'][-1].get('path') != score.get('current')):
            errors.append('No successful latest revision: '+score['id'])
            continue
        folder = contained(job, score['current'])
        if review.get('score_revisions',{}).get(score['id']) != sha(folder/'score.mscz'):
            errors.append('Source review does not cover current MSCZ: '+score['id'])
        if finalize_score(folder):
            errors.append('Score review/audit not accepted: '+score['id'])
    result = {'accepted': not errors, 'errors': errors,
              'source_sha256': state['source_sha256'], 'review_sha256': sha(job/'source-review.json'),
              'scope': 'Documented content checks plus attested complete-source review; not a universal accuracy proof.'}
    dump(job/'acceptance.json', result)
    state['status'] = 'ACCEPTED' if not errors else 'REVIEW_REQUIRED'
    dump(job/'job.json', state)
    print('ACCEPTED' if not errors else 'NOT ACCEPTED')
    for error in errors[:12]:
        print(error)
    return 0 if not errors else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    start = sub.add_parser('run')
    start.add_argument('pdf', type=Path)
    start.add_argument('--out', type=Path, required=True)
    start.add_argument('--prepare-only', action='store_true')
    start.add_argument('--dpi', type=int, default=180)
    resume = sub.add_parser('resume')
    resume.add_argument('job', type=Path)
    for command in (start, resume):
        command.add_argument('--audiveris')
        command.add_argument('--engine-config', type=Path)
        command.add_argument('--tessdata', type=Path)
        command.add_argument('--musescore')
        command.add_argument('--deps', type=Path)
        command.add_argument('--timeout', type=int, default=900)
        command.add_argument('--convert-timeout', type=int, default=180)
        command.add_argument('--retry-omr', action='store_true')
        command.add_argument('--binarize', type=int, choices=range(1,256), metavar='1..255')
        command.add_argument('--omr-dpi', type=int, choices=range(150,601), default=300, metavar='150..600')
        command.add_argument('--rotate', type=int, choices=(0,90,180,270), default=0)
    rebuild = sub.add_parser('rebuild')
    rebuild.add_argument('job', type=Path)
    rebuild.add_argument('--score', help='Existing score ID; omit to add a missing score/movement')
    rebuild.add_argument('--candidate', required=True, type=Path)
    rebuild.add_argument('--reference', type=Path)
    rebuild.add_argument('--musescore')
    rebuild.add_argument('--deps', type=Path)
    rebuild.add_argument('--timeout', type=int, default=180)
    for name in ('status','finalize'):
        command = sub.add_parser(name)
        command.add_argument('job', type=Path)
    args = parser.parse_args()
    try:
        if getattr(args, 'engine_config', None):
            config = load(args.engine_config)
            args.audiveris = args.audiveris or config.get('audiveris')
            args.tessdata = args.tessdata or config.get('tessdata')
        if args.command == 'run':
            job = args.out.resolve()
            state = prepare(args.pdf, job, args.deps, args.dpi)
            if not args.prepare_only:
                recognize(job, state, args)
            make_triage(job, state, args.deps)
        elif args.command == 'resume':
            job, state = read_job(args.job)
            recognize(job, state, args)
            make_triage(job, state, args.deps)
        elif args.command == 'rebuild':
            job, state = read_job(args.job)
            if args.score:
                score = next(s for s in state['scores'] if s['id'] == args.score)
            else:
                used = state['scores'] + state.get('superseded_scores', [])
                score = {'id': f'{max([int(s["id"]) for s in used]+[0])+1:03d}', 'revisions': [],
                         'origin': 'independent transcription / missing movement'}
                state['scores'].append(score)
            make_revision(job, state, score, args.candidate, args.musescore, args.reference, args.timeout)
            make_triage(job, state, args.deps)
        elif args.command == 'finalize':
            return accept(args.job)
        else:
            job, state = read_job(args.job)
        print('Job:', job)
        print('State:', state['status'], '| PDF pages:', len(state['pages']), '| scores:', len(state['scores']))
        print('Review:', job/'index.html')
        print('Next: inspect source, correct candidates, rebuild, review every page/measure, then finalize.')
        return 0 if state['scores'] and all(s.get('current') for s in state['scores']) else 1
    except Exception as error:
        print('PDF WORKFLOW ERROR:', error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
