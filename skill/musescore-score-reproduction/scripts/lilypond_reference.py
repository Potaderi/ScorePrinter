"""Independent absolute-pitch LilyPond oracle for the documented small subset only."""
import argparse,re,sys
from pathlib import Path
from fractions import Fraction as F
import xml.etree.ElementTree as ET
from scorelib import load,dump,sha
from build_score import build

D={1:'w',2:'h',4:'q',8:'e',16:'s',32:'t',64:'x'}

def body(text,var):
    m=re.search(r'^'+re.escape(var)+r'\s*=\s*',text,re.M)
    if not m:raise ValueError('Variable not found: '+var)
    start=text.index('{',m.end());prefix=text[m.end():start].strip()
    offset=0
    if prefix:
        t=re.fullmatch(r"\\transpose\s+c([',]*)\s+c([',]*)",prefix)
        if not t:raise ValueError('Unsupported variable prefix: '+prefix)
        octv=lambda s:s.count("'")-s.count(',')
        offset=octv(t[2])-octv(t[1])
    level=1;i=start+1
    while level and i<len(text):
        level+=(text[i]=='{')-(text[i]=='}');i+=1
    if level:raise ValueError('Unclosed variable body')
    return text[start+1:i-1],offset

def reference(source,config):
    text=Path(source).read_text(encoding='utf-8-sig');text=re.sub(r'%[^\n]*','',text)
    if config.get('source_sha256') and sha(source)!=config['source_sha256']:raise ValueError('Source hash does not match independent reference map')
    lengths=[F(x) for x in config['lengths']];spec={k:v for k,v in config.items() if k in ('title','composer','source','key','time','time_symbol','staves','tempo')}
    spec['voices']=[{'id':v['id'],'staff':v['staff']} for v in config['voices']]
    spec['measures']=[{'number':i+config.get('first_number',1),'length':str(n),'voices':{}} for i,n in enumerate(lengths)];spec['slurs']=[]
    for row in config['voices']:
        music,offset=body(text,row['variable'])
        # Only commands proven irrelevant to the absolute pitches are consumed.
        # All other tokens (relative mode, functions, ornaments, repeats...) fail.
        music=re.sub(r'\\key\s+[a-g]+\s+\\(?:major|minor)|\\time\s+\d+/\d+|\\partial\s+\d+|\\voice(?:One|Two|Three|Four)|\\bar\s+"[^\"]*"',' ',music)
        music=re.sub(r'[{}|\[\]]',' ',music)
        pattern=r"(?:[a-g](?:is|es)?|r|s)[',]*\d*\.*|[()]"
        residue=re.sub(pattern,'',music).strip()
        if residue:raise ValueError('Unsupported LilyPond tokens: '+residue)
        tokens=re.findall(pattern,music);den=4;dots=0;bar=0;t=F(0);streams=[[] for _ in lengths];anchor=None;last=None;spacer=F(0)
        for token in tokens:
            if token in ('(',')'):
                if last is None:raise ValueError('Slur before any note')
                if token=='(':
                    if anchor is not None:raise ValueError('Nested slurs unsupported')
                    anchor=last
                else:
                    if anchor is None:raise ValueError('Slur stop without start')
                    spec['slurs'].append({'start':anchor,'end':last});anchor=None
                continue
            m=re.fullmatch(r"([a-g](?:is|es)?|r|s)([',]*)(\d*)(\.*)",token);pitch,octave,dur,dot=m.groups()
            if dur:den=int(dur);dots=len(dot)
            elif dot:dots=len(dot)
            if den not in D or dots>2:raise ValueError('Unsupported source duration')
            duration=F(4,den)*sum(F(1,2**i) for i in range(dots+1))
            if pitch=='s':
                if bar!=len(lengths) or not config.get('trailing_spacer'):raise ValueError('Only documented trailing alignment spacers supported')
                spacer+=duration;continue
            if bar>=len(lengths):raise ValueError('Source has more notes than configured bars')
            label='R' if pitch=='r' else pitch[0].upper()+('#' if pitch.endswith('is') else 'b' if pitch.endswith('es') else '')+str(3+offset+octave.count("'")-octave.count(','))
            streams[bar].append(label+D[den]+'.'*dots);last=[bar+1,row['id'],len(streams[bar])];t+=duration
            if t>lengths[bar]:raise ValueError('Source overfills mapped measure '+str(bar+1))
            if t==lengths[bar]:bar+=1;t=F(0)
        if bar!=len(lengths) or t or anchor is not None:raise ValueError('Incomplete source or unclosed slur')
        if spacer!=F(config.get('trailing_spacer','0')):raise ValueError('Trailing spacer differs from map')
        for i,tokens in enumerate(streams):spec['measures'][i]['voices'][row['id']]=' '.join(tokens)
    for i,extra in config.get('measure_annotations',{}).items():spec['measures'][int(i)-1].update(extra)
    spec['note_marks']=config.get('note_marks',[])
    return spec

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--map',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    try:
        if a.out.exists():raise ValueError('Output already exists')
        spec=reference(a.source,load(a.map));root=build(spec);a.out.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(root).write(a.out,encoding='utf-8',xml_declaration=True)
        dump(a.out.with_suffix('.provenance.json'),{'source_sha256':sha(a.source),'mapping_sha256':sha(a.map),'reference_sha256':sha(a.out),'scope':'Absolute pitches and inherited durations from source; mapped headers/structure must be independently read from PDF.'})
        print('Independent source reference:',a.out);return 0
    except Exception as e:print('ORACLE ERROR:',e,file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
