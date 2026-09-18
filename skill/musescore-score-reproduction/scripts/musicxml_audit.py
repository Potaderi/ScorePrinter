"""Exit 0: equality in supported scope; 1: mismatch/review; 2: parse/usage error."""
import argparse,sys
from pathlib import Path
from scorelib import audit,dump

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected',required=True,type=Path)
    p.add_argument('--actual',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path)
    p.add_argument('--display',action='store_true',help='Also compare explicit accidentals, beams and stems')
    p.add_argument('--layout',action='store_true',help='Also compare explicit system/page breaks')
    p.add_argument('--merge-voices',action='store_true',help='Only for intentional print condensation; discards voice identities and collapses exact duplicates')
    a=p.parse_args()
    try:r=audit(a.expected,a.actual,display=a.display,layout=a.layout,merge=a.merge_voices)
    except Exception as e:
        dump(a.report,{'passed':False,'status':'ERROR','error':str(e)});print(str(e),file=sys.stderr);return 2
    dump(a.report,r)
    print(r['status'],r['expected_events'],r['actual_events'],'events')
    for cat,d in r['differences'].items():
        if d['missing'] or d['extra']:print(cat,'missing',len(d['missing']),'extra',len(d['extra']),str(d['missing'][:1] or d['extra'][:1]))
    for i in r['issues'][:6]:print('REVIEW',i)
    return 0 if r['passed'] else 1
if __name__=='__main__':sys.exit(main())
