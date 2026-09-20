"""Notation mutations, safe correction and incremental review invariants."""
import copy
import io
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_score import build
from scorelib import audit, parse, dump, load, sha
from reference_patch import proposal
from musicxml_patch import apply_patch
from revision_review import revision_changes
from pdf_to_mscz import make_triage, prepare, write_index


class NotationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.a, self.b = self.directory/'a.musicxml', self.directory/'b.musicxml'
        self.root = build({'staves':[{'sign':'G','line':2}], 'voices':[{'id':'v','staff':1}],
                           'measures':[{'voices':{'v':'C4q D4q E4q F4q'}} for _ in range(4)]})

    def save(self, root, path):
        ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)

    def pair(self):
        self.save(self.root, self.a)
        self.save(self.root, self.b)
        self.assertTrue(audit(self.a,self.b)['passed'], parse(self.a)['issues'])

    def change(self, selector, text=None, attr=None, value=None):
        root = ET.parse(self.b).getroot()
        node = root.find(selector)
        if attr is not None:
            node.set(attr,value)
        else:
            node.text = text
        self.save(root,self.b)
        self.assertFalse(audit(self.a,self.b)['passed'])

    def note(self, number=0):
        return self.root.findall('.//note')[number]

    def notation(self, xml, number=0):
        note=self.note(number)
        container=note.find('notations')
        if container is None:container=ET.SubElement(note,'notations')
        container.append(ET.fromstring(xml))

    def direction(self, xml, measure=0, end=False):
        node=ET.fromstring('<direction><direction-type>'+xml+'</direction-type></direction>')
        m=self.root.findall('part/measure')[measure]
        m.insert(len(m) if end else 1,node)

    def test_lyric_text_verse_and_syllabic(self):
        self.note().append(ET.fromstring('<lyric number="1"><syllabic>begin</syllabic><text>Al</text></lyric>'))
        for selector,text,attr,value in [('.//lyric/text','El',None,None),('.//lyric',None,'number','2'),('.//syllabic','single',None,None)]:
            with self.subTest(selector=selector):
                self.pair();self.change(selector,text,attr,value)

    def test_lyric_is_bound_to_note(self):
        self.note().append(ET.fromstring('<lyric><text>Ah</text></lyric>'))
        self.pair()
        node=self.note().find('lyric');self.note().remove(node);self.note(1).append(node)
        self.save(self.root,self.b);self.assertFalse(audit(self.a,self.b)['passed'])

    def test_lyric_font_runs_equivalent(self):
        self.note().append(ET.fromstring('<lyric><text>Hello</text></lyric>'))
        self.pair()
        lyric=self.note().find('lyric');lyric.remove(lyric.find('text'))
        lyric.extend([ET.fromstring('<text font-weight="bold">Hel</text>'),ET.fromstring('<text>lo</text>')])
        self.save(self.root,self.b);self.assertTrue(audit(self.a,self.b)['passed'])

    def test_lyric_elision_and_extension_retained(self):
        self.note().append(ET.fromstring('<lyric><text>a</text><elision> </elision><text>b</text><extend type="start"/></lyric>'))
        self.pair();self.change('.//extend',attr='type',value='stop')

    def test_ornament_type_and_auxiliary_accidental(self):
        self.notation('<ornaments><mordent/><accidental-mark placement="above">sharp</accidental-mark></ornaments>')
        self.pair();self.change('.//accidental-mark',attr='placement',value='below')
        self.pair();self.change('.//accidental-mark','natural')
        self.pair();self.change('.//mordent',attr='long',value='yes')

    def test_technical_fingering(self):
        self.notation('<technical><fingering>2</fingering></technical>')
        self.pair();self.change('.//fingering','3')

    def test_fermata_defaults_equivalent(self):
        self.notation('<fermata/>');self.pair()
        node=self.root.find('.//fermata');node.text='normal';node.set('type','upright')
        self.save(self.root,self.b);self.assertTrue(audit(self.a,self.b)['passed'])

    def test_grace_order_is_significant(self):
        m=self.root.find('part/measure')
        for step in ('D','E'):
            m.insert(1,ET.fromstring(f'<note><grace slash="yes"/><pitch><step>{step}</step><octave>4</octave></pitch><voice>1</voice><type>eighth</type></note>'))
        self.pair()
        notes=m.findall('note')[:2];index=list(m).index(notes[0]);m.remove(notes[1]);m.insert(index,notes[1])
        self.save(self.root,self.b);self.assertFalse(audit(self.a,self.b)['passed'])

    def test_tuplet_endpoints_and_number_normalization(self):
        self.notation('<tuplet type="start" number="1"/>')
        self.notation('<tuplet type="stop" number="1"/>',2)
        self.pair()
        for node in self.root.findall('.//tuplet'):node.set('number','6')
        self.save(self.root,self.b);self.assertTrue(audit(self.a,self.b)['passed'])
        self.change('.//tuplet',attr='bracket',value='yes')

    def test_tuplet_ratio_changes(self):
        for n in self.root.findall('.//note'):
            n.find('duration').text='320'
            n.append(ET.fromstring('<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>'))
        for div in self.root.findall('.//divisions'):div.text='480'
        self.pair();self.change('.//actual-notes','5')

    def test_harmony_root_bass_and_degree(self):
        self.root.find('part/measure').insert(1,ET.fromstring('<harmony><root><root-step>C</root-step></root><kind>major</kind><bass><bass-step>E</bass-step></bass><degree><degree-value>9</degree-value><degree-alter>0</degree-alter><degree-type>add</degree-type></degree></harmony>'))
        for tag,value in [('root-step','D'),('bass-step','G'),('degree-value','11')]:
            self.pair();self.change('.//'+tag,value)

    def test_harmony_frame_visibility_only_matters_with_frame(self):
        harmony=ET.fromstring('<harmony><root><root-step>C</root-step></root><kind>major</kind></harmony>')
        self.root.find('part/measure').insert(1,harmony);self.pair()
        harmony.set('print-frame','no');self.save(self.root,self.b)
        self.assertTrue(audit(self.a,self.b)['passed'])
        harmony.append(ET.fromstring('<frame><frame-strings>6</frame-strings><frame-frets>4</frame-frets></frame>'))
        self.pair();self.change('.//harmony',attr='print-frame',value='yes')

    def test_direction_spans(self):
        for kind,start,attribute,value in [('wedge','crescendo','niente','yes'),('octave-shift','down','size','15'),('pedal','start','sign','no')]:
            with self.subTest(kind=kind):
                original=copy.deepcopy(self.root)
                self.direction(f'<{kind} type="{start}" number="1"/>')
                self.direction(f'<{kind} type="stop" number="1"/>',2,True)
                self.pair();self.change('.//'+kind,attr=attribute,value=value)
                self.root=original

    def test_span_stop_attributes_not_discarded(self):
        self.direction('<bracket type="start" line-end="down"/>')
        self.direction('<bracket type="stop" line-end="up"/>',1,True)
        self.pair();self.change('.//bracket[@type="stop"]',attr='line-end',value='none')

    def test_unknown_attribute_at_stop_blocks_pass(self):
        self.direction('<wedge type="crescendo"/>');self.direction('<wedge type="stop" alien="x"/>',1)
        self.save(self.root,self.a);self.save(self.root,self.b)
        report=audit(self.a,self.b);self.assertTrue(report['equal_in_checked_scope']);self.assertFalse(report['passed'])

    def test_pedal_change_preserved(self):
        self.direction('<pedal type="start"/>');self.direction('<pedal type="change"/>',1);self.direction('<pedal type="stop"/>',2)
        self.pair();self.assertEqual(1,len([m for m in parse(self.a)['marks'] if m['kind']=='pedal-change']))
        self.change('.//pedal[@type="change"]',attr='type',value='continue')

    def test_repeat_ending_number(self):
        m=self.root.find('part/measure');b=ET.SubElement(m,'barline');b.append(ET.fromstring('<ending number="1" type="start"/>'))
        self.pair();self.change('.//ending',attr='number',value='2')

    def test_default_repeat_bar_style_equivalent(self):
        m=self.root.find('part/measure');b=ET.SubElement(m,'barline',location='right')
        ET.SubElement(b,'repeat',direction='backward');self.pair()
        ET.SubElement(b,'bar-style').text='light-heavy'
        self.save(self.root,self.b);self.assertTrue(audit(self.a,self.b)['passed'])
        self.change('.//bar-style','dashed')

    def test_documented_span_defaults_equivalent(self):
        self.direction('<octave-shift type="down"/>');self.direction('<octave-shift type="stop"/>',1)
        self.pair()
        for node in self.root.findall('.//octave-shift'):node.set('size','8')
        self.save(self.root,self.b);self.assertTrue(audit(self.a,self.b)['passed'])

    def test_lyric_named_type_not_discarded(self):
        self.note().append(ET.fromstring('<lyric number="1" name="verse"><text>A</text></lyric>'))
        self.pair();self.change('.//lyric',attr='name',value='chorus')

    def test_reference_patch_preserves_notes_and_copies_lyrics_notations(self):
        self.note().append(ET.fromstring('<lyric><text>Word</text></lyric>'))
        self.notation('<fermata/>');self.notation('<technical><fingering>3</fingering></technical>')
        self.pair()
        reference=copy.deepcopy(self.root)
        for node in list(self.note()):
            if node.tag in ('notations','lyric'):self.note().remove(node)
        self.save(self.root,self.b)
        self.assertFalse(audit(self.a,self.b)['passed'])
        spec=proposal(self.b,self.a,'Same-edition fixture independent source')
        corrected=apply_patch(self.b,spec);self.save(corrected,self.b)
        self.assertTrue(audit(self.a,self.b)['passed'])
        self.assertEqual([],proposal(self.b,self.a,'Same source')['operations'])

    def test_reference_patch_rejects_wrong_event_and_empty_evidence(self):
        self.pair()
        with self.assertRaises(ValueError):proposal(self.b,self.a,'')
        self.change('.//pitch/step','G')
        with self.assertRaises(ValueError):proposal(self.b,self.a,'Same edition')

    def test_reference_patch_rejects_ambiguous_unisons(self):
        clone=copy.deepcopy(self.note());clone.insert(0,ET.Element('chord'))
        m=self.root.find('part/measure');m.insert(list(m).index(self.note())+1,clone)
        self.pair()
        with self.assertRaises(ValueError):proposal(self.b,self.a,'Same edition')

    def test_reference_barline_patch(self):
        self.pair();self.change('.//bar-style','light-light')
        result=apply_patch(self.b,proposal(self.b,self.a,'Same source',barlines=True))
        self.save(result,self.b);self.assertTrue(audit(self.a,self.b)['passed'])

    def test_part_label_mutation_and_guarded_repair(self):
        self.pair();self.change('.//part-name','Incorrect instrument')
        spec={'input_sha256':sha(self.b),'operations':[{'scope':'document','select':'part-list/score-part[1]/part-name',
              'op':'text','before':'Incorrect instrument','after':self.root.findtext('.//part-name'),
              'reason':'Independently read source staff label'}]}
        self.save(apply_patch(self.b,spec),self.b);self.assertTrue(audit(self.a,self.b)['passed'])

    def test_revision_local_note_change(self):
        self.pair();self.change('.//pitch/step','G')
        result=revision_changes(self.a,self.b)
        self.assertEqual([(1,1)],[(r['part'],r['measure']) for r in result['review_targets']])
        self.assertFalse(result['approval_transferred'])

    def test_revision_context_change_expands_downstream(self):
        self.pair();self.change('.//key/fifths','1')
        self.assertEqual(4,len(revision_changes(self.a,self.b)['review_targets']))

    def test_revision_changed_note_expands_span(self):
        self.notation('<slur type="start"/>');self.notation('<slur type="stop"/>',11)
        self.pair();self.change('.//pitch/step','G')
        self.assertEqual([1,2,3],[r['measure'] for r in revision_changes(self.a,self.b)['review_targets']])

    def test_revision_unknown_semantics_require_full_review(self):
        self.notation('<unknown/>');self.save(self.root,self.a);self.save(self.root,self.b)
        self.assertEqual(4,len(revision_changes(self.a,self.b)['review_targets']))

    def test_revision_unchanged_has_no_targets(self):
        self.pair();self.assertEqual([],revision_changes(self.a,self.b)['review_targets'])

    def test_triage_cache_and_render_links(self):
        try:import pymupdf
        except ImportError:self.skipTest('PyMuPDF not installed')
        source=self.directory/'source.pdf'
        with pymupdf.open() as doc:
            doc.new_page();doc.save(source)
        job=self.directory/'job';state=prepare(source,job)
        folder=job/'omr/attempt-001/export';folder.mkdir(parents=True)
        project=folder/'test.omr';project.write_bytes(b'fake project')
        dump(folder.parent/'engine.json',{'warnings':[]})
        state['attempts']=['omr/attempt-001']
        diagnostics={'staves':[],'findings':[{'page':1,'bbox':[0,0,1,.2],'reason':'fixture'}],'systems':[],'sheets':[]}
        with patch('pdf_to_mscz.project_diagnostics',return_value=diagnostics) as mocked:
            make_triage(job,state);crops=list((job/'crops').glob('*.png'));times=[p.stat().st_mtime_ns for p in crops]
            make_triage(job,state)
            self.assertEqual(1,mocked.call_count);self.assertEqual(times,[p.stat().st_mtime_ns for p in crops])
            project.write_bytes(b'changed project');make_triage(job,state);self.assertEqual(2,mocked.call_count)
        rev=job/'scores/001/rev-001';rev.mkdir(parents=True)
        for number in (10,2,1):(rev/f'score-{number}.png').write_bytes(b'fixture')
        state['scores']=[{'id':'001','current':'scores/001/rev-001'}];write_index(job,state)
        page=(job/'index.html').read_text(encoding='utf-8')
        self.assertLess(page.index('score-2.png'),page.index('score-10.png'))


if __name__=='__main__':unittest.main()
