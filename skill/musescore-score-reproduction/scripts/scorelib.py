"""Standard-library MusicXML normalization. Unsupported constructs block full PASS."""
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
import hashlib, json, zipfile, xml.etree.ElementTree as ET
from notation import semantic, lyric_value, SpanTracker

TYPES={'maxima':32,'long':16,'breve':8,'whole':4,'half':2,'quarter':1,'eighth':F(1,2),'16th':F(1,4),'32nd':F(1,8),'64th':F(1,16),'128th':F(1,32)}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def atom(e):
    return [e.tag,(e.text or '').strip(),{k:v for k,v in sorted(e.attrib.items()) if k in ('type','number','direction','times','parentheses','cautionary','editorial')},[atom(c) for c in e]]
def token(obj): return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':'))

def xml_root(path):
    path=Path(path)
    if path.suffix.lower()=='.mxl':
        with zipfile.ZipFile(path) as z:
            c=ET.fromstring(z.read('META-INF/container.xml'))
            name=next(e.get('full-path') for e in c.iter() if e.tag.split('}')[-1]=='rootfile' and e.get('full-path','').endswith(('.xml','.musicxml')))
            data=z.read(name)
    else: data=path.read_bytes()
    if len(data)>50_000_000: raise ValueError('XML exceeds 50 MB limit')
    if b'<!ENTITY' in data.upper(): raise ValueError('Entity declarations are not supported')
    root=ET.fromstring(data)
    for e in root.iter(): e.tag=e.tag.split('}')[-1]
    if root.tag!='score-partwise':raise ValueError('Only score-partwise MusicXML is supported')
    return root

def parse(path):
    root=xml_root(path)
    out={'events':[],'attributes':[],'marks':[],'display':[],'layout':[],'measures':[],'labels':[],'issues':[],'notes':[]}
    def issue(where,msg):out['issues'].append({'location':where,'reason':msg})
    def record(category,loc,**kw):out[category].append(dict(loc,**kw))
    for pi,part in enumerate(root.findall('part'),1):
        definition=next((p for p in root.findall('part-list/score-part') if p.get('id')==part.get('id')),None)
        if definition is not None:
            for tag in ('part-name','part-abbreviation'):
                label=definition.find(tag)
                if label is not None and label.get('print-object')!='no':
                    text=' '.join(''.join(label.itertext()).split())
                    if text:record('labels',{'part':pi},kind=tag,value=text)
        # Normalize arbitrary export voice IDs per staff, keeping ordinal identities.
        pairs={}
        for n in part.findall('measure/note'):
            st=n.findtext('staff','1');v=n.findtext('voice','1');pairs.setdefault(st,set()).add(v)
        order=lambda v:(0,int(v)) if v.isdigit() else (1,v)
        vmap={(st,v):str(i+1) for st,vs in pairs.items() for i,v in enumerate(sorted(vs,key=order))}
        divisions=1;active={};spans={};notation_spans=SpanTracker(out['marks'],issue)
        for mi,m in enumerate(part.findall('measure'),1):
            loc={'part':pi,'measure':mi};cursor=F(0);last=None;extent=F(0);intervals={};grace_order={}
            for e in m:
                where=dict(loc,onset=str(cursor))
                if e.tag=='attributes':
                    for a in e:
                        if a.tag=='divisions':divisions=int(a.text);continue
                        if a.tag in ('key','time','clef','staves','transpose'):
                            kind=a.tag;st=a.get('number','all' if kind in ('key','time','transpose') else '1')
                            if kind=='key':
                                if a.find('fifths') is None:issue(where,'Nontraditional key signature');continue
                                value={'fifths':int(a.findtext('fifths')),'mode':a.findtext('mode','')}
                            elif kind=='time':
                                if len(a.findall('beats'))!=1 or not (a.findtext('beats','').isdigit()):issue(where,'Composite or senza-misura meter');continue
                                value={'beats':a.findtext('beats'),'beat_type':a.findtext('beat-type'),'symbol':a.get('symbol','normal')}
                            elif kind=='clef':value={'sign':a.findtext('sign'),'line':a.findtext('line',''),'octave':a.findtext('clef-octave-change','0')}
                            elif kind=='staves':value=int(a.text)
                            else:value={c.tag:c.text for c in a}
                            targets=sorted(pairs) if st=='all' else [st]
                            for target in targets:
                                k=(kind,target)
                                if active.get(k)!=value:record('attributes',where,kind=kind,staff=target,value=value);active[k]=value
                        elif a.tag=='staff-details':
                            value=semantic(a,issue,where,omit=('number','print-object'))
                            children=value[3]
                            # Standard staff-lines=5 is the default, not a musical change.
                            if a.attrib.keys()-{'number','print-object'} or any(c[0]!='staff-lines' or c[1]!='5' for c in children):
                                record('attributes',where,kind='staff-details',staff=a.get('number','1'),value=value)
                        elif a.tag not in ('instruments',):
                            issue(where,'Unsupported attribute: '+a.tag)
                        else:issue(where,'Requires manual review: '+a.tag)
                elif e.tag in ('backup','forward'):
                    cursor+=F(int(e.findtext('duration')),divisions)*(-1 if e.tag=='backup' else 1)
                    if cursor<0:issue(where,'Negative cursor after '+e.tag)
                    extent=max(extent,cursor)
                elif e.tag=='note':
                    st=e.findtext('staff','1');voice=vmap[(st,e.findtext('voice','1'))]
                    chord=e.find('chord') is not None
                    if chord and (last is None or last[1:]!=(st,voice)):issue(where,'Chord without compatible preceding note')
                    onset=last[0] if chord and last else cursor
                    dur=F(int(e.findtext('duration','0')),divisions)
                    grace=e.find('grace') is not None
                    if grace and dur:issue(where,'Grace note unexpectedly advances metrical time')
                    if dur<=0 and not grace:issue(where,'Non-positive note duration')
                    if not chord:cursor+=dur;last=(onset,st,voice)
                    extent=max(extent,cursor)
                    where=dict(loc,staff=st,voice=voice,onset=str(onset))
                    if grace:
                        gkey=(st,voice,str(onset))
                        if not chord:grace_order[gkey]=grace_order.get(gkey,0)+1
                        where['grace_index']=grace_order.get(gkey,1)
                        value=semantic(e.find('grace'),issue,where)
                        if 'make-time' in value[2]:value[2]['make-time']=str(F(value[2]['make-time'])/divisions)
                        record('marks',where,kind='grace',value=value)
                    if e.get('print-object')=='no' and e.find('rest') is not None:
                        out['notes'].append(dict(where,info='Hidden alignment rest excluded'));continue
                    pitch=e.find('pitch');rest=e.find('rest');unpitched=e.find('unpitched')
                    if pitch is None and rest is None and unpitched is None:issue(where,'Unsupported note without pitch/rest');continue
                    spelling=None if rest is not None else (['unpitched',unpitched.findtext('display-step'),unpitched.findtext('display-octave')] if unpitched is not None else [pitch.findtext('step'),str(F(pitch.findtext('alter','0'))),int(pitch.findtext('octave'))])
                    if unpitched is not None:issue(where,'Percussion instrument mapping requires independent review')
                    typ=e.findtext('type','');dots=len(e.findall('dot'));ratio=None
                    tm=e.find('time-modification')
                    if tm is not None:
                        ratio=[int(tm.findtext('actual-notes')),int(tm.findtext('normal-notes'))]
                        if any(c.tag not in ('actual-notes','normal-notes','normal-type','normal-dot') for c in tm):issue(where,'Unsupported time-modification child')
                    if typ and typ not in TYPES:issue(where,'Unsupported duration type '+typ)
                    elif typ:
                        calculated=F(TYPES[typ])*sum(F(1,2**i) for i in range(dots+1))
                        if ratio:calculated*=F(ratio[1],ratio[0])
                        if calculated!=dur and not grace:issue(where,'Duration disagrees with type/dots/ratio')
                    if rest is not None and rest.get('measure')=='yes':typ='measure';dots=0
                    record('events',where,pitch=spelling,duration=str(dur),type=typ,dots=dots,ratio=ratio)
                    if not chord:
                        segments=intervals.setdefault((st,voice),[])
                        if any(onset<b and onset+dur>a for a,b in segments):issue(where,'Overlapping events within one voice')
                        segments.append((onset,onset+dur))
                    note_allowed={'pitch','rest','duration','voice','type','dot','accidental','stem','staff','beam','notations','chord','tie','time-modification','grace','lyric','unpitched','notehead','notehead-text','instrument'}
                    for ch in e:
                        if ch.tag not in note_allowed:issue(where,'Unsupported note child: '+ch.tag)
                    for lyric in e.findall('lyric'):
                        record('marks',dict(where,pitch=spelling),kind='lyric',value=lyric_value(lyric,issue,where))
                    for tag in ('notehead','notehead-text'):
                        for item in e.findall(tag):record('marks',dict(where,pitch=spelling),kind=tag,value=semantic(item,issue,where))
                    if e.find('instrument') is not None:issue(where,'Explicit note instrument mapping requires review')
                    acc=e.find('accidental')
                    if acc is not None:record('display',where,kind='accidental',value=atom(acc))
                    if e.find('stem') is not None:record('display',where,kind='stem',value=e.findtext('stem'))
                    if e.get('print-object')=='no':issue(where,'Hidden pitched note requires manual review')
                    # Use beam markers once per chord, independent of its pitches.
                    if not chord:
                        for beam in e.findall('beam'):record('display',where,kind='beam',level=beam.get('number','1'),value=beam.text)
                    ties=e.findall('notations/tied') or e.findall('tie')
                    span_tags=[('tie',x) for x in ties]+[('slur',x) for x in e.findall('notations/slur')]
                    for kind,sp in sorted(span_tags,key=lambda x:x[1].get('type')!='stop'):
                        typ_s=sp.get('type');sid=sp.get('number','1')
                        k=(kind,st,voice,token(spelling) if kind=='tie' else sid)
                        anchor=dict(where,pitch=spelling)
                        if typ_s=='start':
                            if k in spans:issue(where,'Duplicate open '+kind)
                            spans[k]=anchor
                        elif typ_s=='stop':
                            if k not in spans:issue(where,'Unmatched '+kind+' stop')
                            else:out['marks'].append({'kind':kind,'start':spans.pop(k),'end':anchor})
                        elif typ_s!='continue':issue(where,'Unsupported '+kind+' type '+str(typ_s))
                    nt=e.find('notations')
                    if nt is not None:
                        for n in nt:
                            if n.tag in ('slur','tied'):continue
                            if n.tag in ('tuplet','glissando','slide'):
                                notation_spans.add(n,dict(where,pitch=spelling),(st,voice))
                            elif n.tag in ('articulations','fermata','arpeggiate','non-arpeggiate','ornaments','technical'):
                                if n.tag in ('ornaments','technical','articulations') and len(n)==0:issue(where,'Empty '+n.tag)
                                if n.tag=='ornaments':
                                    for item in n.findall('wavy-line'):notation_spans.add(item,dict(where,pitch=spelling),(st,voice))
                                    children=[c for c in n if c.tag!='wavy-line']
                                    if children:
                                        clone=ET.Element('ornaments',n.attrib);clone.extend(children)
                                        record('marks',dict(where,pitch=spelling),kind=n.tag,value=semantic(clone,issue,where))
                                else:record('marks',dict(where,pitch=spelling),kind=n.tag,value=semantic(n,issue,where))
                            else:issue(where,'Unsupported notation: '+n.tag)
                elif e.tag=='direction':
                    at=cursor+F(int(e.findtext('offset','0')),divisions)
                    dloc=dict(loc,staff=e.findtext('staff','1'),onset=str(at))
                    sound=e.find('sound')
                    if sound is not None:
                        for k,v in sound.attrib.items():
                            if k=='tempo':record('marks',dloc,kind='tempo',value=str(F(v)))
                            elif k not in ('dynamics',):issue(dloc,'Unsupported playback directive '+k)
                    for d in e.findall('direction-type/*'):
                        if d.tag=='metronome':record('marks',dloc,kind='metronome',value=[(x.tag,x.text or '') for x in d])
                        elif d.tag=='dynamics':record('marks',dloc,kind='dynamics',value=[x.tag for x in d])
                        elif d.tag in ('words','rehearsal'):record('marks',dloc,kind=d.tag,value=' '.join(''.join(d.itertext()).split()))
                        elif d.tag in ('wedge','octave-shift','pedal','dashes','bracket'):
                            notation_spans.add(d,dloc,(dloc['staff'],))
                        elif d.tag in ('segno','coda'):record('marks',dloc,kind=d.tag,value=semantic(d,issue,dloc))
                        else:issue(dloc,'Unsupported direction '+d.tag)
                elif e.tag=='harmony':
                    at=cursor+F(int(e.findtext('offset','0')),divisions)
                    hloc=dict(loc,staff=e.findtext('staff','1'),onset=str(at))
                    clone=ET.Element('harmony',e.attrib);clone.extend(c for c in e if c.tag not in ('offset','staff'))
                    record('marks',hloc,kind='harmony',value=semantic(clone,issue,hloc))
                elif e.tag=='barline':
                    repeat=e.find('repeat')
                    repeat_style=({'forward':'heavy-light','backward':'light-heavy'}.get(repeat.get('direction'))
                                  if repeat is not None else None)
                    for b in e:
                        if b.tag=='bar-style':
                            if b.text!='regular' and b.text!=repeat_style:record('marks',loc,kind='barline',side=e.get('location','right'),value=b.text)
                        elif b.tag in ('repeat','ending'):record('marks',loc,kind=b.tag,side=e.get('location','right'),value=semantic(b,issue,loc))
                        else:issue(loc,'Unsupported barline element '+b.tag)
                elif e.tag=='print':
                    for flag in ('new-page','new-system'):
                        if e.get(flag)=='yes':record('layout',loc,kind=flag)
                else:issue(where,'Unsupported measure element '+e.tag)
            out['measures'].append(dict(loc,duration=str(extent)))
            meter=active.get(('time','1'))
            if meter and extent>F(int(meter['beats'])*4,int(meter['beat_type'])):issue(loc,'Overfull measure')
        for k,v in spans.items():issue(v,'Unclosed '+k[0])
        notation_spans.finish()
    if not root.findall('part') or not out['events']:issue({},'Empty score')
    return out

def differences(a,b):
    ca=Counter(token(x) for x in a);cb=Counter(token(x) for x in b)
    return {'missing':[json.loads(x) for x in (ca-cb).elements()],'extra':[json.loads(x) for x in (cb-ca).elements()]}

def audit(expected,actual,*,display=False,layout=False,merge=False):
    e=parse(expected);a=parse(actual);categories=['events','attributes','marks','measures','labels']
    if display:categories.append('display')
    if layout:categories.append('layout')
    if merge:
        def no_voice(obj):
            if isinstance(obj,dict):return {k:no_voice(v) for k,v in obj.items() if k!='voice'}
            if isinstance(obj,list):return [no_voice(x) for x in obj]
            return obj
        for score in (e,a):
            for cat in ('events','marks','display'):
                # Only documented print condensation may collapse duplicates.
                score[cat]=list({token(no_voice(x)):no_voice(x) for x in score[cat]}.values())
    diffs={cat:differences(e[cat],a[cat]) for cat in categories}
    equality=all(not d['missing'] and not d['extra'] for d in diffs.values())
    issues=e['issues']+a['issues']
    return {'schema':2,'expected_sha256':sha(expected),'actual_sha256':sha(actual),'mode':'condensed' if merge else 'voices','scope':categories,'passed':equality and not issues,'equal_in_checked_scope':equality,'status':'PASS' if equality and not issues else 'REVIEW_REQUIRED' if equality else 'FAIL','expected_events':len(e['events']),'actual_events':len(a['events']),'issues':issues,'differences':diffs,'limitations':['Equality does not establish that the expected score was correctly read from the source.','Content mode excludes explicit accidentals/stems/beams; enable --display for their comparison.','Layout, header metadata, timbre, playback realization, fonts and pixels are not certified.']}
