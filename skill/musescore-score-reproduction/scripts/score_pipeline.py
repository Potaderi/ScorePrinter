"""Run a fresh MuseScore import/reopen/export/audit job, or verify a reviewed job."""
import argparse, os, shutil, subprocess, sys, zipfile
from pathlib import Path
from scorelib import audit,dump,load,sha,parse

def executable(value):
    if value:
        p=Path(value).expanduser().resolve()
        if not p.is_file():raise ValueError('MuseScore executable not found: '+str(p))
        return p
    for name in ('MuseScore4.exe','musescore','mscore','musescore4'):
        p=shutil.which(name)
        if p:return Path(p)
    for base in ('C:/Program Files/MuseScore 4/bin/MuseScore4.exe','/Applications/MuseScore 4.app/Contents/MacOS/mscore'):
        if Path(base).is_file():return Path(base)
    raise ValueError('Provide --musescore /path/to/executable')

def run_ms(exe,args,folder,label,timeout):
    env=os.environ.copy()
    for key,sub in [('APPDATA','roaming'),('LOCALAPPDATA','local'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('TEMP','temp'),('TMP','temp')]:
        dest=folder/'runtime'/sub;dest.mkdir(parents=True,exist_ok=True);env[key]=str(dest)
    # Native portable build stores its own settings next to its executable.
    # Environment variables do not isolate all OS-owned preference mechanisms.
    if os.name=='nt':env['QT_QPA_PLATFORM']='windows'
    elif sys.platform.startswith('linux') and not env.get('DISPLAY'):env['QT_QPA_PLATFORM']='offscreen'
    command=[str(exe),*map(str,args)]
    proc=subprocess.run(command,cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (folder/(label+'.log')).write_bytes(proc.stdout)
    dump(folder/(label+'-command.json'),{'argv':command,'exit_code':proc.returncode})
    if proc.returncode:raise ValueError(f'MuseScore exit {proc.returncode}; see {label}.log and portable application logs')

def check_zip(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise ValueError('Corrupt MSCZ')
        if not any(n.endswith('.mscx') for n in z.namelist()):raise ValueError('MSCZ has no score')

def convert(a):
    exe=executable(a.musescore);src=a.input.resolve();expected=a.expected.resolve();out=a.out.resolve()
    if not src.is_file() or not expected.is_file() or not a.source.is_file():raise ValueError('Input, expected score and source must exist')
    if out.exists():raise ValueError('Output directory must be new; use a fresh name')
    out.mkdir(parents=True)
    run_ms(exe,['--version'],out,'version',a.timeout)
    final=out/'score.mscz';xml=out/'roundtrip.musicxml'
    if src.suffix.lower()=='.mscz':check_zip(src)
    run_ms(exe,['-o',final,src],out,'import',a.timeout);check_zip(final)
    # Separate process: opening a saved MSCZ is an essential verification step.
    job=[{'in':str(final),'out':[str(xml),str(out/'score.pdf'),str(out/'score.png')]}]
    dump(out/'export-job.json',job)
    run_ms(exe,['-r','150','-j',out/'export-job.json'],out,'reopen-export',a.timeout)
    for p in (final,xml,out/'score.pdf'):
        if not p.is_file() or not p.stat().st_size:raise ValueError('Missing output '+str(p))
    source=a.source.resolve()
    provenance={'input':str(src),'input_sha256':sha(src),'expected':str(expected),'expected_sha256':sha(expected),'source':str(source),'source_sha256':sha(source),'mscz_sha256':sha(final),'musicxml_sha256':sha(xml),'pdf_sha256':sha(out/'score.pdf'),'musescore':str(exe),'expected_role':a.expected_role}
    dump(out/'provenance.json',provenance)
    report=audit(expected,xml,display=a.display,layout=a.layout,merge=a.merge_voices)
    dump(out/'audit.json',report)
    score=parse(xml)
    units=sorted({(e['part'],e['measure'],e['staff']) for e in score['events']})
    ledger={'schema':1,'mscz_sha256':sha(final),'pdf_sha256':sha(out/'score.pdf'),'source_sha256':sha(source),'audit_sha256':sha(out/'audit.json'),'reference_independently_checked':False,'reviewer':'','method':'','scope':'Compare the original source, not merely input vs output. Check missing/extra symbols, all notes/rests, voice distinction, accidental display, beams, ties/slurs, expressive marks, repeats and text.','measures':[{'part':p,'measure':m,'staff':s,'source_content':'pending','notation_and_beams':'pending','evidence':''} for p,m,s in units],'unsupported_feature_resolutions':[]}
    dump(out/'review.json',ledger)
    print('AUTOMATED',report['status'],'-',out)
    print('Review source vs exported PDF, then fill review.json and run finalize. No automatic source-reading claim.')
    return 0 if report['passed'] else 1

def finalize(folder):
    folder=Path(folder).resolve();p=load(folder/'provenance.json');review=load(folder/'review.json');a=load(folder/'audit.json');errors=[]
    for field,path in [('mscz_sha256',folder/'score.mscz'),('pdf_sha256',folder/'score.pdf'),('source_sha256',Path(p['source'])),('audit_sha256',folder/'audit.json')]:
        if not path.is_file() or review.get(field)!=sha(path):errors.append('Changed or missing reviewed file: '+field)
    for field,path in [('input_sha256',p['input']),('expected_sha256',p['expected']),('musicxml_sha256',folder/'roundtrip.musicxml')]:
        if not Path(path).is_file() or p[field]!=sha(path):errors.append('Changed audit input: '+field)
    if not a.get('equal_in_checked_scope'):errors.append('Semantic mismatches remain')
    required={(e['part'],e['measure'],e['staff']) for e in parse(folder/'roundtrip.musicxml')['events']}
    supplied=[(e['part'],e['measure'],e['staff']) for e in review.get('measures',[])]
    if set(supplied)!=required or len(supplied)!=len(required):errors.append('Incomplete or duplicate review coverage')
    if review.get('reference_independently_checked') is not True:errors.append('Independent source check not attested')
    if not review.get('reviewer','').strip() or not review.get('method','').strip():errors.append('Reviewer and method required')
    for row in review.get('measures',[]):
        if row.get('source_content')!='pass' or row.get('notation_and_beams')!='pass' or not row.get('evidence','').strip():errors.append(f'Unreviewed part/measure/staff: {row.get("part")}/{row.get("measure")}/{row.get("staff")}')
    resolutions=review.get('unsupported_feature_resolutions',[])
    if a.get('issues'):
        if len(resolutions)!=len(a['issues']) or any(r.get('issue')!=i or r.get('status')!='pass' or not r.get('evidence') for i,r in zip(a['issues'],resolutions)):errors.append('Unsupported features lack explicit independent resolutions')
    result={'accepted':not errors,'scope':a['scope'],'requires_human_or_agent_source_review':True,'errors':errors,'review_sha256':sha(folder/'review.json'),'mscz_sha256':sha(folder/'score.mscz')}
    dump(folder/'acceptance.json',result)
    print('ACCEPTED IN DOCUMENTED SCOPE' if not errors else 'NOT ACCEPTED')
    for e in errors[:8]:print(e)
    return 0 if not errors else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('convert');p.add_argument('--input',required=True,type=Path);p.add_argument('--expected',required=True,type=Path);p.add_argument('--source',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--musescore');p.add_argument('--timeout',type=int,default=120);p.add_argument('--expected-role',choices=['independent-reference','transcription-roundtrip'],default='transcription-roundtrip');p.add_argument('--display',action='store_true');p.add_argument('--layout',action='store_true');p.add_argument('--merge-voices',action='store_true')
    p=sub.add_parser('finalize');p.add_argument('folder',type=Path)
    p=sub.add_parser('doctor');p.add_argument('--musescore')
    a=parser.parse_args()
    try:
        if a.command=='convert':return convert(a)
        if a.command=='finalize':return finalize(a.folder)
        exe=executable(a.musescore);print('Python',sys.version.split()[0]);print('MuseScore',exe);print('Qt platforms:',[x.name for x in (exe.parent/'platforms').glob('*')]);return 0
    except Exception as e:print('ERROR:',e,file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
