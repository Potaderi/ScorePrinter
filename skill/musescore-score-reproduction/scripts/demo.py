"""One-command, project-independent end-to-end demonstration using bundled sources."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--musescore',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    out=a.out.resolve()
    if out.exists():print('Use a new output folder',file=sys.stderr);return 2
    out.mkdir(parents=True)
    def run(script,*args):
        r=subprocess.run([sys.executable,str(ROOT/'scripts'/script),*map(str,args)],cwd=out)
        if r.returncode:raise RuntimeError(f'{script}: exit {r.returncode}')
    try:
        run('lilypond_reference.py','--source',ROOT/'examples/ode-original.ly','--map',ROOT/'examples/ode-reference-map.json','--out',out/'reference.musicxml')
        run('build_score.py',ROOT/'examples/ode-entry.json','--out',out/'entry.musicxml')
        run('score_pipeline.py','convert','--input',out/'entry.musicxml','--expected',out/'reference.musicxml','--source',ROOT/'examples/ode-original.pdf','--musescore',a.musescore.resolve(),'--out',out/'result','--expected-role','independent-reference')
        print('Created:',out/'result/score.mscz');print('Automated checks complete. Source/notation review remains in result/review.json.')
        return 0
    except Exception as e:print(e,file=sys.stderr);return 1
if __name__=='__main__':sys.exit(main())
