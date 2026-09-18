"""Preserve source provenance and detect changes to protected existing files."""
import argparse,sys,urllib.request
from pathlib import Path
from scorelib import sha,dump,load

def inventory(root,exclude):
    result={};root=root.resolve();exclude=[p.resolve() for p in exclude]
    for p in root.rglob('*'):
        resolved=p.resolve()
        if any(resolved==x or x in resolved.parents for x in exclude):continue
        if p.is_symlink():continue
        if p.is_file():result[str(p.relative_to(root))]={'sha256':sha(p),'size':p.stat().st_size}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='cmd',required=True)
    f=subs.add_parser('fetch');f.add_argument('--url',required=True);f.add_argument('--out',required=True,type=Path);f.add_argument('--license',required=True);f.add_argument('--sha256')
    f=subs.add_parser('snapshot');f.add_argument('--root',required=True,type=Path);f.add_argument('--exclude',action='append',default=[],type=Path);f.add_argument('--out',required=True,type=Path)
    f=subs.add_parser('check');f.add_argument('snapshot',type=Path);f.add_argument('--report',required=True,type=Path)
    a=p.parse_args()
    try:
        if a.cmd=='fetch':
            if not a.url.startswith(('https://','http://')):raise ValueError('HTTP(S) URLs only')
            if a.out.exists() or a.out.with_suffix(a.out.suffix+'.json').exists():raise ValueError('Source output exists')
            req=urllib.request.Request(a.url,headers={'User-Agent':'MuseScore-Reproduction/1.0'})
            with urllib.request.urlopen(req,timeout=60) as response:
                data=response.read(100_000_001)
                if len(data)>100_000_000:raise ValueError('Download exceeds 100 MB')
                final=response.url;mime=response.headers.get('Content-Type','')
            if a.out.suffix.lower()=='.pdf' and not data.startswith(b'%PDF-'):raise ValueError('URL did not return a PDF')
            import hashlib
            digest=hashlib.sha256(data).hexdigest()
            if a.sha256 and digest.lower()!=a.sha256.lower():raise ValueError('Download hash mismatch')
            a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(data)
            dump(a.out.with_suffix(a.out.suffix+'.json'),{'url':a.url,'final_url':final,'sha256':digest,'license_claim':a.license,'mime':mime,'bytes':len(data)})
            print('Saved',a.out,digest);return 0
        if a.cmd=='snapshot':
            if a.out.exists():raise ValueError('Snapshot exists')
            dump(a.out,{'root':str(a.root.resolve()),'exclude':[str(p.resolve()) for p in a.exclude]+[str(a.out.resolve())],'files':inventory(a.root,a.exclude+[a.out])});print('Snapshot saved');return 0
        old=load(a.snapshot);new=inventory(Path(old['root']),[Path(p) for p in old['exclude']]);before=old['files']
        changed=[p for p in before if p in new and before[p]['sha256']!=new[p]['sha256']];missing=sorted(set(before)-set(new));added=sorted(set(new)-set(before))
        r={'existing_files_unchanged':not changed and not missing,'changed':changed,'missing':missing,'added':added};dump(a.report,r);print(r);return 0 if r['existing_files_unchanged'] else 1
    except Exception as e:print('ERROR:',e,file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
