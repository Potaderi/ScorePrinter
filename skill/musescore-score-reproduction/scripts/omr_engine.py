"""Local Audiveris runner and diagnostic extraction. No score-specific note data."""
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from scorelib import dump, sha, xml_root


def isolated_environment(folder):
    env = os.environ.copy()
    folder = Path(folder).resolve()
    for key in ('APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
                'XDG_CACHE_HOME', 'TEMP', 'TMP'):
        target = folder / key.lower()
        target.mkdir(parents=True, exist_ok=True)
        env[key] = str(target)
    home = folder / 'java-home'
    home.mkdir(exist_ok=True)
    # JVM properties isolate Java caches without changing the process's HOME.
    env['JAVA_TOOL_OPTIONS'] = ' '.join((
        env.get('JAVA_TOOL_OPTIONS', ''),
        f'-Duser.home="{home}"',
        f'-Djava.io.tmpdir="{folder / "temp"}"',
        f'-Djava.util.prefs.userRoot="{folder / "prefs"}"',
    )).strip()
    return env


def find_engine(value):
    value = value or shutil.which('Audiveris.exe') or shutil.which('audiveris')
    if not value:
        raise ValueError('Audiveris not found. Use setup_omr.py or --audiveris PATH.')
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError('Audiveris executable does not exist: ' + str(path))
    if os.name == 'nt' and path.suffix.lower() in ('.bat', '.cmd'):
        raise ValueError('Use the native Audiveris.exe launcher on Windows, not a batch file.')
    return path


def run_engine(pdf, output, engine, timeout=900, tessdata=None):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('OMR attempt directory already exists')
    output.mkdir(parents=True)
    env = isolated_environment(output / 'runtime')
    if tessdata:
        tessdata = Path(tessdata).resolve()
        if not (tessdata / 'eng.traineddata').is_file():
            raise ValueError('Tessdata directory must contain eng.traineddata')
        env['TESSDATA_PREFIX'] = str(tessdata)
    command = [str(find_engine(engine)), '-batch', '-transcribe', '-export',
               '-save', '-swap', '-output', str(output / 'export'), '--', str(Path(pdf).resolve())]
    started = time.monotonic()
    timed_out = False
    with (output / 'engine.log').open('wb') as log:
        try:
            result = subprocess.run(command, cwd=output, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = None
            timed_out = True
    # Export *all* works/movements; never silently pick the first MXL.
    candidates = []
    for path in sorted((output / 'export').rglob('*')):
        if path.suffix.lower() not in ('.mxl', '.musicxml', '.xml'):
            continue
        try:
            xml_root(path)
            candidates.append(str(path.relative_to(output)))
        except (ValueError, ET.ParseError, zipfile.BadZipFile, StopIteration):
            continue
    logtext = (output / 'engine.log').read_text(encoding='utf-8', errors='replace')
    warnings = [line for line in logtext.splitlines()
                if re.search(r'\b(WARN|ERROR)\b|missing support|no score|invalid sheet', line, re.I)]
    report = {'argv': command, 'input_sha256': sha(pdf), 'engine_sha256': sha(engine),
              'returncode': code, 'timed_out': timed_out, 'seconds': round(time.monotonic()-started, 2),
              'candidates': candidates, 'warnings': warnings,
              'status': 'CANDIDATES' if candidates else 'NEEDS_TRANSCRIPTION',
              'accuracy_claim': False}
    dump(output / 'engine.json', report)
    return report


def project_diagnostics(path, threshold=0.45):
    """Read Audiveris 5.x coordinates. Hints are not exhaustive error detection."""
    findings, systems, sheets, staves = [], [], [], []
    with zipfile.ZipFile(path) as archive:
        book = ET.fromstring(archive.read('book.xml'))
        for sheet in book.findall('sheet'):
            number = int(sheet.get('number'))
            page = int(sheet.findtext('input/number', str(number)))
            completed = 'PAGE' in sheet.findtext('steps', '').split()
            sheets.append({'page': page, 'sheet': number, 'completed': completed,
                           'invalid': sheet.get('invalid') == 'true'})
            member = f'sheet#{number}/sheet#{number}.xml'
            if member not in archive.namelist():
                continue
            data = ET.fromstring(archive.read(member))
            picture = data.find('picture')
            if picture is None:
                continue
            width, height = float(picture.get('width')), float(picture.get('height'))
            for staff in data.findall('.//system/part/staff'):
                ys = [float(point.get('y')) for point in staff.findall('lines/line/point')]
                if ys:
                    staves.append({'page': page, 'staff': staff.get('id'),
                                   'center': (min(ys)+max(ys))/2/height})
            for system in data.findall('.//system'):
                points = system.findall('./part/staff/lines/line/point')
                if points:
                    xs, ys = [float(p.get('x')) for p in points], [float(p.get('y')) for p in points]
                    systems.append({'page': page, 'system': system.get('id'),
                                    'bbox': [max(0,min(xs)/width-.015), max(0,min(ys)/height-.035),
                                             min(1,max(xs)/width+.015), min(1,max(ys)/height+.035)],
                                    'measures': [s.get('id') for s in system.findall('stack')]})
                for stack in system.findall('stack'):
                    if stack.get('abnormal') == 'true' or (stack.get('duration') and stack.get('expected')
                                                         and stack.get('duration') != stack.get('expected')):
                        findings.append({'page': page, 'system': system.get('id'),
                                         'measure': stack.get('id'), 'reason': 'OMR rhythm anomaly',
                                         'details': dict(stack.attrib)})
            for node in data.iter():
                if node.tag == 'stack':
                    continue  # Rhythm anomalies already have measure/system addresses.
                abnormal = node.get('abnormal') == 'true'
                grade = node.get('grade')
                if not abnormal and (grade is None or float(grade) >= threshold):
                    continue
                bounds = node.find('bounds')
                item = {'page': page, 'symbol': node.tag, 'id': node.get('id'),
                        'reason': 'abnormal symbol' if abnormal else 'low OMR grade', 'grade': grade}
                if bounds is not None and all(k in bounds.attrib for k in ('x','y','w','h')):
                    x,y,w,h = [float(bounds.get(k)) for k in ('x','y','w','h')]
                    item['bbox'] = [max(0,x/width-.015), max(0,y/height-.015),
                                    min(1,(x+w)/width+.015), min(1,(y+h)/height+.015)]
                findings.append(item)
    return {'sheets': sheets, 'systems': systems, 'staves': staves, 'findings': findings,
            'note': 'Grades prioritize inspection; high grades do not prove correctness.'}
