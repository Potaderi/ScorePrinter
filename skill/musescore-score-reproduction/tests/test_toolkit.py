"""Run: python -m unittest discover -s tests -v (from this skill folder)."""
import copy,importlib.util,io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
from contextlib import redirect_stdout
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_score import build
from scorelib import audit,parse,dump,sha
from score_pipeline import finalize
from lilypond_reference import reference
from source_project import inventory

SPEC={'title':'Test','key':0,'time':[4,4],'tempo':100,'staves':[{'sign':'G','line':2}],'voices':[{'id':'v','staff':1}],'measures':[{'voices':{'v':'C4q D4q E4q F4q'}},{'voices':{'v':'F4q G4e A4e B4h'}}],'slurs':[{'start':[1,'v',2],'end':[2,'v',2]}],'ties':[{'start':[1,'v',4],'end':[2,'v',1]}],'note_marks':[{'at':[2,'v',2],'beams':['begin']},{'at':[2,'v',3],'beams':['end']}]}
class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=Path(self.temp.name);self.a=self.d/'expected.musicxml';self.b=self.d/'actual.musicxml';self.save(build(SPEC),self.a);self.save(build(SPEC),self.b)
    def save(self,r,path):ET.ElementTree(r).write(path,encoding='utf-8',xml_declaration=True)
    def mutate(self,fn):
        r=ET.parse(self.b).getroot();fn(r);self.save(r,self.b)
    def check(self,**kw):return audit(self.a,self.b,**kw)
    def test_identity_and_cross_bar_spans(self):
        self.assertTrue(self.check(display=True)['passed']);self.assertEqual(2,len([m for m in parse(self.a)['marks'] if m['kind'] in ('tie','slur')]))
    def test_wrong_pitch(self):
        self.mutate(lambda r:r.find('.//pitch/step').__setattr__('text','D'));self.assertFalse(self.check()['passed'])
    def test_wrong_octave(self):
        self.mutate(lambda r:r.find('.//pitch/octave').__setattr__('text','5'));self.assertFalse(self.check()['passed'])
    def test_wrong_duration(self):
        self.mutate(lambda r:r.find('.//note/duration').__setattr__('text','9'));self.assertFalse(self.check()['passed']);self.assertTrue(self.check()['issues'])
    def test_missing_note(self):
        self.mutate(lambda r:r.find('part/measure').remove(r.find('.//note')));self.assertFalse(self.check()['passed'])
    def test_missing_slur(self):
        self.mutate(lambda r:[n.remove(s) for n in r.findall('.//notations') for s in n.findall('slur')]);self.assertFalse(self.check()['passed'])
    def test_wrong_slur_endpoint(self):
        def fn(r):
            nts=r.findall('.//notations');stop=next(s for n in nts for s in n.findall('slur') if s.get('type')=='stop');parent=next(n for n in nts if stop in list(n));parent.remove(stop);ET.SubElement(r.findall('part/measure')[1].findall('note')[-1],'notations').append(stop)
        self.mutate(fn);self.assertFalse(self.check()['passed'])
    def test_missing_tie(self):
        def fn(r):
            for n in r.findall('.//note'):
                for t in n.findall('tie'):n.remove(t)
                for nt in n.findall('notations'):
                    for t in nt.findall('tied'):nt.remove(t)
        self.mutate(fn);self.assertFalse(self.check()['passed'])
    def test_wrong_meter(self):
        self.mutate(lambda r:r.find('.//time/beats').__setattr__('text','3'));self.assertFalse(self.check()['passed'])
    def test_wrong_key(self):
        self.mutate(lambda r:r.find('.//key/fifths').__setattr__('text','1'));self.assertFalse(self.check()['passed'])
    def test_wrong_tempo(self):
        self.mutate(lambda r:r.find('.//sound').set('tempo','120'));self.assertFalse(self.check()['passed'])
    def test_wrong_barline(self):
        self.mutate(lambda r:r.find('.//bar-style').__setattr__('text','light-light'));self.assertFalse(self.check()['passed'])
    def test_beam_scope(self):
        self.mutate(lambda r:r.find('.//beam').__setattr__('text','end'));self.assertTrue(self.check()['passed']);self.assertFalse(self.check(display=True)['passed'])
    def test_accidental_scope(self):
        self.mutate(lambda r:ET.SubElement(r.find('.//note'),'accidental').__setattr__('text','natural'));self.assertTrue(self.check()['passed']);self.assertFalse(self.check(display=True)['passed'])
    def test_unknown_notation_is_not_pass(self):
        self.mutate(lambda r:ET.SubElement(ET.SubElement(r.find('.//note'),'notations'),'ornaments'))
        self.assertFalse(self.check()['passed']);self.assertTrue(self.check()['issues'])
    def test_divisions_equivalence(self):
        def fn(r):
            for d in r.findall('.//divisions')+r.findall('.//duration'):d.text=str(int(d.text)*3)
        self.mutate(fn);self.assertTrue(self.check()['passed'])
    def test_label_and_voice_id_equivalence(self):
        def fn(r):
            for m in r.findall('.//measure'):m.set('number','X1')
            for v in r.findall('.//note/voice'):v.text='9'
        self.mutate(fn);self.assertTrue(self.check()['passed'])
    def test_redundant_key_not_modulation(self):
        def fn(r):
            a=r.findall('part/measure/attributes')[1];k=ET.SubElement(a,'key',number='1');ET.SubElement(k,'fifths').text='0'
        self.mutate(fn);self.assertTrue(self.check()['passed'])
    def test_mxl_and_namespace(self):
        mxl=self.d/'a.mxl'
        with zipfile.ZipFile(mxl,'w') as z:
            z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="score.musicxml"/></rootfiles></container>');z.write(self.a,'score.musicxml')
        self.assertTrue(audit(mxl,self.b)['passed'])
        r=ET.parse(self.b).getroot()
        for e in r.iter():e.tag='{http://www.musicxml.org/ns/musicxml}'+e.tag
        self.save(r,self.b);self.assertTrue(self.check()['passed'])
    def test_empty_score_fails(self):
        r=ET.Element('score-partwise');self.save(r,self.a);self.save(r,self.b);self.assertFalse(self.check()['passed'])
    def test_pickup_and_measure_rest(self):
        s=copy.deepcopy(SPEC);s['slurs']=[];s['ties']=[];s['note_marks']=[];s['measures']=[{'length':'1/2','voices':{'v':'C4e'}},{'voices':{'v':'Rm'}}]
        r=build(s);self.save(r,self.a);self.save(r,self.b);self.assertTrue(self.check()['passed'])
    def test_wrong_voice_assignment(self):
        s=copy.deepcopy(SPEC);s['voices'].append({'id':'low','staff':1})
        for m in s['measures']:m['voices']['low']='C3w'
        self.save(build(s),self.a);self.save(build(s),self.b)
        def fn(r):
            for v in r.findall('.//note/voice'):v.text='2' if v.text=='1' else '1'
        self.mutate(fn);self.assertFalse(self.check()['passed']);self.assertTrue(self.check(merge=True)['passed'])
    def test_chord_merging_is_explicit(self):
        s={'staves':[{'sign':'G','line':2}],'voices':[{'id':'a','staff':1},{'id':'b','staff':1}],'measures':[{'voices':{'a':'C4w','b':'C4w'}}]}
        t={'staves':s['staves'],'voices':[s['voices'][0]],'measures':[{'voices':{'a':'C4w'}}]}
        self.save(build(s),self.a);self.save(build(t),self.b);self.assertFalse(self.check()['passed']);self.assertTrue(self.check(merge=True)['passed'])
    def test_partial_duplicate_not_collapsed(self):
        s={'staves':[{'sign':'G','line':2}],'voices':[{'id':'a','staff':1},{'id':'b','staff':1}],'measures':[{'voices':{'a':'C4w','b':'C4h D4h'}}]}
        t={'staves':s['staves'],'voices':[s['voices'][0]],'measures':[{'voices':{'a':'C4w'}}]}
        self.save(build(s),self.a);self.save(build(t),self.b);self.assertFalse(self.check(merge=True)['passed'])
    def test_build_rejects_underfill_typo_tie(self):
        for edit in ('underfill','typo','tie'):
            s=copy.deepcopy(SPEC)
            if edit=='underfill':s['measures'][0]['voices']['v']='C4q'
            elif edit=='typo':s['measures'][0]['lenght']='4'
            else:s['ties'][0]['end']=[2,'v',2]
            with self.assertRaises(ValueError):build(s)
    def test_invalid_meter_break_repeat_rejected(self):
        cases=[('time',[4,0]),('time',[3,3]),('time_symbol','typo')]
        for field,value in cases:
            s=copy.deepcopy(SPEC);s[field]=value
            with self.assertRaises(ValueError):build(s)
        for field,value in [('break','typo'),('repeat','forward')]:
            s=copy.deepcopy(SPEC);s['measures'][0][field]=value
            with self.assertRaises(ValueError):build(s)
    def test_symbol_only_change_is_encoded(self):
        s=copy.deepcopy(SPEC);s['measures'][1]['time_symbol']='common'
        r=build(s);self.assertEqual('common',r.findall('part/measure')[1].find('attributes/time').get('symbol'))
    def test_nonconsecutive_tie_rejected(self):
        s=copy.deepcopy(SPEC);s['measures'][1]['voices']['v']='F4q F4e A4e B4h';s['ties'][0]['end']=[2,'v',2]
        with self.assertRaises(ValueError):build(s)
    def test_source_oracles_match_saved_expected_counts(self):
        for n,count in [('ode',245),('greensleeves',266)]:
            mapping=json.loads((ROOT/'examples'/f'{n}-reference-map.json').read_text());spec=reference(ROOT/'examples'/f'{n}-original.ly',mapping)
            self.save(build(spec),self.a);parsed=parse(self.a);self.assertEqual(count,len(parsed['events']));self.assertEqual([],parsed['issues'])
    def test_lilypond_unknown_command_rejected(self):
        source=self.d/'source.ly';source.write_text("voice = { \\relative c' { c4 d e f } }")
        cfg={'staves':[{'sign':'G','line':2}],'voices':[{'id':'v','staff':1,'variable':'voice'}],'lengths':['4']}
        with self.assertRaises(ValueError):reference(source,cfg)
    def test_finalize_cannot_skip_review_or_use_stale_artifact(self):
        folder=self.d/'job';folder.mkdir()
        for name in ('score.mscz','score.pdf'):(folder/name).write_bytes(b'test fixture')
        import shutil
        shutil.copyfile(self.a,folder/'roundtrip.musicxml')
        dump(folder/'audit.json',audit(self.a,folder/'roundtrip.musicxml'))
        p={'input':str(self.a),'input_sha256':sha(self.a),'expected':str(self.a),'expected_sha256':sha(self.a),'source':str(self.a),'source_sha256':sha(self.a),'musicxml_sha256':sha(folder/'roundtrip.musicxml')};dump(folder/'provenance.json',p)
        r={'mscz_sha256':sha(folder/'score.mscz'),'pdf_sha256':sha(folder/'score.pdf'),'source_sha256':sha(self.a),'audit_sha256':sha(folder/'audit.json'),'reference_independently_checked':False,'reviewer':'','method':'','measures':[]};dump(folder/'review.json',r)
        with redirect_stdout(io.StringIO()):self.assertEqual(1,finalize(folder))
        r.update(reference_independently_checked=True,reviewer='Synthetic test fixture',method='Unit test only',measures=[{'part':1,'measure':i,'staff':'1','source_content':'pass','notation_and_beams':'pass','evidence':'Synthetic test fixture'} for i in (1,2)]);dump(folder/'review.json',r)
        with redirect_stdout(io.StringIO()):self.assertEqual(0,finalize(folder))
        old_audit=json.loads((folder/'audit.json').read_text());stale=copy.deepcopy(old_audit);stale['schema']=0
        dump(folder/'audit.json',stale);r['audit_sha256']=sha(folder/'audit.json');dump(folder/'review.json',r)
        with redirect_stdout(io.StringIO()):self.assertEqual(1,finalize(folder))
        dump(folder/'audit.json',old_audit);r['audit_sha256']=sha(folder/'audit.json');dump(folder/'review.json',r)
        (folder/'score.mscz').write_bytes(b'changed')
        with redirect_stdout(io.StringIO()):self.assertEqual(1,finalize(folder))
    def test_protected_inventory(self):
        f=self.d/'outside.txt';f.write_text('before');excluded=self.d/'outputs';excluded.mkdir();a=inventory(self.d,[excluded]);(excluded/'new.txt').write_text('generated');self.assertEqual(a,inventory(self.d,[excluded]));f.write_text('changed');self.assertNotEqual(a,inventory(self.d,[excluded]))
if __name__=='__main__':unittest.main()
