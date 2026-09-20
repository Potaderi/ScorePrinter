"""Semantic MusicXML notation and span normalization (formatting is separate).

Unknown children/attributes remain review issues; matching unknown XML is not proof
that the notation is understood. See references/notation-coverage.md.
"""

VISUAL = set('default-x default-y relative-x relative-y color font-family font-style font-size '
             'font-weight placement halign valign justify letter-spacing underline overline '
             'line-through rotation enclosure id bezier-x bezier-y bezier-x2 bezier-y2 '
             'bezier-offset bezier-offset2 dash-length space-length spread end-length'.split())
SEMANTIC = set('type number name text parentheses bracket line-type line-end direction times '
               'print-object print-dot print-lyric slash steal-time-following steal-time-previous '
               'make-time long approach departure trill-step two-note-turn start-note beats '
               'second-beat last-beat accelerate size niente sign abbreviated substitution '
               'alternate show-number show-type use-symbols stack-degrees degrees-symbol '
               'plus-minus location shape filled smufl time-only placement line line-shape print-frame'.split()) - {'placement'}
ELEMENTS = set('ornaments trill-mark turn delayed-turn inverted-turn delayed-inverted-turn '
               'vertical-turn inverted-vertical-turn shake wavy-line mordent inverted-mordent '
               'schleifer tremolo haydn accidental-mark '
               'technical up-bow down-bow harmonic natural artificial base-pitch touching-pitch '
               'sounding-pitch open-string thumb-position fingering pluck double-tongue triple-tongue '
               'stopped snap-pizzicato fret string hammer-on pull-off bend bend-alter pre-bend release '
               'with-bar tap heel toe fingernails hole hole-type hole-closed hole-shape arrow '
               'arrow-direction arrow-style arrowhead handbell brass-bend flip smear open half-muted '
               'harmon-mute harmon-closed golpe '
               'articulations accent strong-accent staccato tenuto detached-legato staccatissimo '
               'spiccato scoop plop doit falloff breath-mark caesura stress unstress soft-accent '
               'fermata arpeggiate non-arpeggiate '
               'tuplet tuplet-actual tuplet-normal tuplet-number tuplet-type tuplet-dot '
               'lyric syllabic text elision extend laughing humming end-line end-paragraph '
               'harmony root root-step root-alter numeral numeral-root numeral-alter numeral-key '
               'numeral-fifths numeral-mode function kind inversion bass bass-step bass-alter '
               'degree degree-value degree-alter degree-type frame frame-strings frame-frets '
               'first-fret frame-note barre '
               'wedge octave-shift pedal dashes bracket segno coda metronome beat-unit beat-unit-dot '
               'per-minute beat-unit-tied metronome-note metronome-type metronome-dot '
               'metronome-beam metronome-tuplet actual-notes normal-notes normal-type normal-dot '
               'metronome-relation tied slur glissando slide staff-details staff-lines staff-size '
               'staff-type staff-tuning tuning-step tuning-alter tuning-octave capo '
               'notehead notehead-text display-text display-accidental grace unpitched '
               'display-step display-octave repeat ending'.split())


def semantic(node, issue, where, omit=()):
    if node.tag not in ELEMENTS:
        issue(where, 'Unsupported notation element: '+node.tag)
    attrs = {}
    for key,value in node.attrib.items():
        # Placement identifies the auxiliary pitch of ornament accidentals.
        if key == "placement" and node.tag == "accidental-mark":
            attrs[key] = value
            continue
        if key in omit or key in VISUAL:
            continue
        if key not in SEMANTIC and key != '{http://www.w3.org/XML/1998/namespace}lang':
            issue(where, 'Unsupported notation attribute: '+node.tag+'/'+key)
        attrs[key] = value
    if attrs.get('print-object') == 'yes':
        del attrs['print-object']
    if node.tag == 'harmony' and node.find('frame') is None:
        attrs.pop('print-frame',None)  # No chord diagram exists to show/hide.
    if node.tag == 'fermata':
        attrs.setdefault('type','upright')
    if node.tag in ('mordent','inverted-mordent'):
        attrs.setdefault('long','no')
    defaults = {'wedge': {'line-type':'solid','niente':'no'},
                'octave-shift': {'size':'8'},
                'tuplet': {'show-number':'actual','show-type':'none','line-shape':'straight'}}
    # Defaults apply to both endpoints; bracket presence is implementation-dependent.
    for key, value in defaults.get(node.tag,{}).items():
        attrs.setdefault(key,value)
    if node.tag == 'pedal':
        attrs.setdefault('line','no')
        attrs.setdefault('sign','no' if attrs['line']=='yes' else 'yes')
        attrs.setdefault('abbreviated','no')
    text = (node.text or '').strip()
    if node.tag == 'fermata' and not text:
        text = 'normal'
    if node.tag in ('text','elision'):
        text = node.text or ''  # lyric punctuation/elision/space must not vanish
    return [node.tag,text,attrs,[semantic(c,issue,where) for c in node]]


def lyric_value(node, issue, where):
    value = semantic(node,issue,where,omit=('number','name'))
    children = []
    # XML may split a single syllable into adjacent text runs for font changes.
    for item in value[3]:
        if item[0] in ('end-line','end-paragraph'):
            continue
        if item[0]=='text' and children and children[-1][0]=='text' and children[-1][2]==item[2]:
            children[-1][1] += item[1]
        else:
            children.append(item)
    if children and children[0][0]=='text':
        children.insert(0,['syllabic','single',{},[]])
    value[3] = children
    verse=node.get('number','1')
    name=node.get('name','')
    return {'verse':verse, 'name':'' if name==verse else name, 'value':value}


class SpanTracker:
    def __init__(self, marks, issue):
        self.marks,self.issue,self.open = marks,issue,{}

    def add(self, node, anchor, scope):
        kind,typ = node.tag,node.get('type')
        key = (kind,scope,node.get('number','1'))
        starts = ('start','crescendo','diminuendo','up','down','sostenuto')
        if typ in starts:
            if key in self.open:
                self.issue(anchor,'Duplicate open '+kind)
            self.open[key]=(dict(anchor),semantic(node,self.issue,anchor,omit=('number',)))
        elif typ in ('stop','discontinue'):
            end_value=semantic(node,self.issue,anchor,omit=('number','type'))
            if key not in self.open:
                self.issue(anchor,'Unmatched '+kind+' '+str(typ))
                return
            start,value=self.open.pop(key)
            self.marks.append({'kind':kind,'start':start,'end':dict(anchor),'value':value,
                               'end_type':typ,'end_value':end_value})
        elif typ in ('continue','change'):
            value=semantic(node,self.issue,anchor,omit=('number',))
            if key not in self.open:
                self.issue(anchor,'Unmatched '+kind+' '+typ)
            self.marks.append(dict(anchor,kind=kind+'-'+typ,value=value))
        else:
            self.issue(anchor,'Unsupported '+kind+' type '+str(typ))

    def finish(self):
        for (kind,scope,number),(anchor,value) in self.open.items():
            self.issue(anchor,'Unclosed '+kind)
