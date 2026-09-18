"""Build a rhythm-validated MusicXML from compact, explicitly spelled note tokens."""
import argparse, math, re, sys
from pathlib import Path
from fractions import Fraction as F
import xml.etree.ElementTree as ET
from scorelib import load,dump

D={'w':(F(4),'whole'),'h':(F(2),'half'),'q':(F(1),'quarter'),'e':(F(1,2),'eighth'),'s':(F(1,4),'16th'),'t':(F(1,8),'32nd'),'x':(F(1,16),'64th')}

def add(p,tag,value=None,**kw):
    e=ET.SubElement(p,tag,{k.replace('_','-'):str(v) for k,v in kw.items()})
    if value is not None:e.text=str(value)
    return e

def keys(obj,allowed,where):
    extra=set(obj)-set(allowed.split())
    if extra:raise ValueError(f'{where}: unknown fields {sorted(extra)}')

def validate_meter(time):
    if not isinstance(time,list) or len(time)!=2 or any(type(x) is not int for x in time):
        raise ValueError('Meter must be [positive integer beats, power-of-two denominator]')
    if time[0]<=0 or time[1]<=0 or time[1] & (time[1]-1):
        raise ValueError('Invalid numeric meter')

def parse_token(t,length):
    if t=='Rm':return {'pitches':[],'duration':length,'type':None,'dots':0,'measure_rest':True}
    m=re.fullmatch(r'(R|[A-G](?:bb|##|b|#|n)?-?\d|\[[^\]]+\])([whqestx])(\.{0,2})',t)
    if not m:raise ValueError('Invalid note token: '+t)
    p,d,dots=m.groups();base,typ=D[d];duration=base*sum(F(1,2**i) for i in range(len(dots)+1));pitches=[]
    if p!='R':
        for raw in (p[1:-1].split(',') if p.startswith('[') else [p]):
            n=re.fullmatch(r'([A-G])(bb|##|b|#|n)?(-?\d)',raw)
            if not n:raise ValueError('Invalid pitch: '+raw)
            step,acc,octave=n.groups();alter={'bb':-2,'b':-1,None:0,'n':0,'#':1,'##':2}[acc]
            pitches.append((step,alter,int(octave)))
        if len(pitches)!=len(set(pitches)):raise ValueError('Duplicate note in chord: '+t)
    return {'pitches':pitches,'duration':duration,'type':typ,'dots':len(dots),'measure_rest':False}

def build(spec):
    keys(spec,'title composer source key time time_symbol staves voices measures slurs ties note_marks tempo','score')
    staves=spec['staves'];voices=spec['voices'];measures=spec['measures']
    validate_meter(spec.get('time',[4,4]))
    if spec.get('time_symbol','normal') not in ('normal','common','cut'):raise ValueError('Invalid time symbol')
    if not staves or not voices or not measures:raise ValueError('Empty staves, voices or measures')
    for s in staves:keys(s,'sign line octave','staff')
    for v in voices:keys(v,'id staff','voice')
    if len({v['id'] for v in voices})!=len(voices):raise ValueError('Duplicate voice id')
    for v in voices:
        if not 1<=v['staff']<=len(staves):raise ValueError('Invalid voice staff')
    for i in range(1,len(staves)+1):
        if not 1<=sum(v['staff']==i for v in voices)<=4:raise ValueError('Each staff needs 1..4 voices')
    parsed=[];divisions=1;time=spec.get('time',[4,4]);default_fifths=spec.get('key',0)
    for mi,m in enumerate(measures,1):
        keys(m,'number length voices key time time_symbol break barline repeat','measure '+str(mi))
        time=m.get('time',time);validate_meter(time)
        if m.get('time_symbol','normal') not in ('normal','common','cut'):raise ValueError('Invalid time symbol')
        if 'break' in m and m['break'] not in ('system','page'):raise ValueError('Break must be system or page')
        if 'repeat' in m and m['repeat']!='backward':raise ValueError('Only backward repeats at right barlines are supported by JSON entry')
        normal=F(time[0]*4,time[1]);length=F(m.get('length',normal))
        if length<=0:raise ValueError('Non-positive bar length')
        if set(m['voices'])!={v['id'] for v in voices}:raise ValueError(f'Measure {mi}: voice set differs')
        bars={}
        for v in voices:
            tokens=m['voices'][v['id']];tokens=tokens.split() if isinstance(tokens,str) else tokens
            ev=[parse_token(t,length) for t in tokens]
            if sum((e['duration'] for e in ev),F(0))!=length:raise ValueError(f'Measure {mi}, {v["id"]}: durations do not fill {length} quarters')
            bars[v['id']]=ev
            for e in ev:divisions=math.lcm(divisions,e['duration'].denominator)
        parsed.append((m,time,normal,length,bars))
    root=ET.Element('score-partwise',version='4.0');add(add(root,'work'),'work-title',spec.get('title','Untitled'))
    ident=add(root,'identification');add(ident,'creator',spec.get('composer',''),type='composer')
    if spec.get('source'):add(ident,'source',spec['source'])
    partlist=add(root,'part-list');pd=add(partlist,'score-part',id='P1');add(pd,'part-name','Score')
    part=add(root,'part',id='P1');lookup={};anchors={};bar_start=F(0);time_symbol=spec.get('time_symbol','normal')
    for mi,(m,time,normal,length,bars) in enumerate(parsed,1):
        bar=add(part,'measure',number=m.get('number',mi),implicit='yes' if length!=normal else 'no')
        if m.get('break'):add(bar,'print',**{('new-page' if m['break']=='page' else 'new-system'):'yes'})
        attrs=add(bar,'attributes')
        if mi==1:add(attrs,'divisions',divisions)
        if mi==1 or 'key' in m:add(add(attrs,'key'),'fifths',m.get('key',default_fifths))
        if mi==1 or 'time' in m or 'time_symbol' in m:
            time_symbol=m.get('time_symbol',time_symbol)
            ts=add(attrs,'time',symbol=time_symbol);add(ts,'beats',time[0]);add(ts,'beat-type',time[1])
        if mi==1:
            if len(staves)>1:add(attrs,'staves',len(staves))
            for si,s in enumerate(staves,1):
                c=add(attrs,'clef',number=si);add(c,'sign',s['sign']);add(c,'line',s['line'])
                if s.get('octave'):add(c,'clef-octave-change',s['octave'])
            if spec.get('tempo'):
                d=add(bar,'direction',placement='above');mt=add(add(d,'direction-type'),'metronome');add(mt,'beat-unit','quarter');add(mt,'per-minute',spec['tempo']);add(d,'staff',1);add(d,'sound',tempo=spec['tempo'])
        for vi,v in enumerate(voices,1):
            if vi>1:add(add(bar,'backup'),'duration',int(length*divisions))
            onset=bar_start
            for ei,event in enumerate(bars[v['id']],1):
                notes=[]
                for ci,pitch in enumerate(event['pitches'] or [None]):
                    n=add(bar,'note')
                    if ci:add(n,'chord')
                    if pitch is None:add(n,'rest',**({'measure':'yes'} if event['measure_rest'] else {}))
                    else:
                        p=add(n,'pitch');add(p,'step',pitch[0]);add(p,'alter',pitch[1]);add(p,'octave',pitch[2])
                    add(n,'duration',int(event['duration']*divisions));add(n,'voice',vi)
                    if event['type']:add(n,'type',event['type'])
                    for _ in range(event['dots']):add(n,'dot')
                    add(n,'staff',v['staff']);notes.append(n)
                lookup[(mi,v['id'],ei)]=notes
                anchors[(mi,v['id'],ei)]=(onset,onset+event['duration'])
                onset+=event['duration']
        bar_start+=length
        style=m.get('barline','light-heavy' if mi==len(parsed) else '')
        if style or m.get('repeat'):
            b=add(bar,'barline',location='right')
            if style:add(b,'bar-style',style)
            if m.get('repeat'):add(b,'repeat',direction=m['repeat'])
    def nodes(ref):
        if tuple(ref) not in lookup:raise ValueError('Annotation target does not exist: '+str(ref))
        return lookup[tuple(ref)]
    def notation(n):
        nt=n.find('notations')
        return add(n,'notations') if nt is None else nt
    for i,sl in enumerate(spec.get('slurs',[]),1):
        keys(sl,'start end placement','slur')
        for typ,ref in [('start',sl['start']),('stop',sl['end'])]:
            add(notation(nodes(ref)[0]),'slur',type=typ,number=i,**({'placement':sl['placement']} if typ=='start' and sl.get('placement') else {}))
    for tie in spec.get('ties',[]):
        keys(tie,'start end','tie');a=nodes(tie['start']);b=nodes(tie['end'])
        if tie['start'][1]!=tie['end'][1] or anchors[tuple(tie['start'])][1]!=anchors[tuple(tie['end'])][0]:
            raise ValueError('Tie endpoints must be consecutive events in the same voice')
        pitch=lambda n:tuple(n.findtext('pitch/'+x) for x in ['step','alter','octave'])
        if [pitch(n) for n in a]!=[pitch(n) for n in b] or any(n.find('rest') is not None for n in a+b):raise ValueError('Tied pitches differ')
        for typ,ns in [('start',a),('stop',b)]:
            for n in ns:add(n,'tie',type=typ);add(notation(n),'tied',type=typ)
    for mark in spec.get('note_marks',[]):
        keys(mark,'at stem beams accidental parentheses articulation','note mark');ns=nodes(mark['at'])
        for n in ns:
            if mark.get('stem'):add(n,'stem',mark['stem'])
            if mark.get('accidental'):add(n,'accidental',mark['accidental'],**({'parentheses':'yes','cautionary':'yes'} if mark.get('parentheses') else {}))
        for level,value in enumerate(mark.get('beams',[]),1):add(ns[0],'beam',value,number=level)
        if mark.get('articulation'):add(add(notation(ns[0]),'articulations'),mark['articulation'])
    # MusicXML note children must follow schema order.
    order='chord pitch rest duration tie voice type dot accidental time-modification stem staff beam notations'.split()
    for n in root.findall('part/measure/note'):n[:]=sorted(n,key=lambda x:order.index(x.tag))
    ET.indent(root)
    return root

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('spec',type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    try:
        root=build(load(a.spec))
        if a.out.exists():raise ValueError('Output exists; use a new output name to preserve work')
        a.out.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(root).write(a.out,encoding='utf-8',xml_declaration=True)
        print('Built',a.out,len(root.findall('part/measure')),'measures')
        return 0
    except Exception as e:print('BUILD ERROR:',str(e),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
