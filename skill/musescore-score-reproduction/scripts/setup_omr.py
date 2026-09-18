"""Download hash-pinned Windows Audiveris into a project without system installation."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from scorelib import dump, sha

ASSETS = {
    'eng.traineddata': ('https://raw.githubusercontent.com/tesseract-ocr/tessdata/4.1.0/eng.traineddata',
                        'daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047'),
    'audiveris.msi': ('https://github.com/Audiveris/audiveris/releases/download/5.11.0/'
                      'Audiveris-5.11.0-windowsConsole-x86_64.msi',
                      '5f1b4e96a12c53c7da426814b76e599363c4181e291855996e0a6878dda95f71'),
    'lessmsi.zip': ('https://github.com/activescott/lessmsi/releases/download/v2.12.9/lessmsi-v2.12.9.zip',
                    '5b4e187e74b184ad3a63ccf06c3d17dae2b8c4b6c298a996dbd51a9f6db29d21'),
}


def download(url, target, expected):
    if target.exists():
        if sha(target) != expected:
            raise ValueError('Existing download hash differs: ' + str(target))
        return
    part = target.with_suffix(target.suffix + '.partial')
    with urllib.request.urlopen(url, timeout=90) as response, part.open('wb') as file:
        while chunk := response.read(1024 * 1024):
            file.write(chunk)
    if sha(part) != expected:
        raise ValueError('Download SHA-256 mismatch: ' + url)
    part.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if os.name != 'nt':
        print('Use the official Audiveris package for your OS, then pass --audiveris PATH. '
              'https://github.com/Audiveris/audiveris/releases', file=sys.stderr)
        return 2
    out = args.out.resolve()
    try:
        if out.exists():
            raise ValueError('Use a new output directory')
        out.mkdir(parents=True)
        for name, (url, digest) in ASSETS.items():
            print('Downloading', name, flush=True)
            download(url, out / name, digest)
        with zipfile.ZipFile(out / 'lessmsi.zip') as archive:
            archive.extractall(out / 'lessmsi')
        # lessmsi only extracts files: no msiexec, registry registration or global installation.
        with (out / 'extract.log').open('wb') as log:
            subprocess.run([str(out/'lessmsi/lessmsi.exe'), 'x', str(out/'audiveris.msi'),
                            str(out/'application') + '\\'], check=True,
                           stdout=log, stderr=subprocess.STDOUT, timeout=180)
        exe = out / 'application/SourceDir/Audiveris/Audiveris.exe'
        if not exe.is_file():
            raise ValueError('Unexpected MSI layout; see extract.log')
        (out/'tessdata').mkdir()
        (out/'eng.traineddata').replace(out/'tessdata/eng.traineddata')
        dump(out/'engine-config.json', {'audiveris': str(exe), 'tessdata': str(out/'tessdata'), 'version': '5.11.0',
                                       'assets': ASSETS})
        print('Audiveris:', exe)
        print('Next: install PyMuPDF locally: python -m pip install --target <project>/deps pymupdf')
        print('Engine configuration:', out/'engine-config.json')
        print('Full legacy-compatible English OCR data included. Other lyric languages need their own traineddata.')
        return 0
    except Exception as error:
        print('SETUP ERROR:', error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
