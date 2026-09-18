"""Behavioral checks for unseen-PDF jobs, failure recovery and guarded corrections."""
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_score import build
from scorelib import dump, sha, xml_root
from musicxml_patch import apply_patch
from omr_engine import run_engine, project_diagnostics
from staff_inventory import staff_hints, coverage_findings
from pdf_to_mscz import accept, contained, make_revision, recognize, prepare, read_job, make_triage

SPEC = {'staves': [{'sign':'G','line':2}], 'voices':[{'id':'v','staff':1}],
        'measures':[{'voices':{'v':'C4q D4q E4q F4q'}}]}


class NewPdfTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.xml = self.root/'notes.musicxml'
        ET.ElementTree(build(SPEC)).write(self.xml, encoding='utf-8', xml_declaration=True)

    def change(self, **values):
        operation = {'part':1,'measure':1,'select':'note[1]/pitch/step','op':'text',
                     'before':'C','after':'D','reason':'Independent source reading'}
        operation.update(values)
        return {'input_sha256':sha(self.xml),'operations':[operation]}

    def job(self):
        job = self.root/'job'
        job.mkdir()
        (job/'source.pdf').write_bytes(b'PDF fixture, not an image-recognition test')
        folder = job/'scores/001/rev-001'
        folder.mkdir(parents=True)
        (folder/'score.mscz').write_bytes(b'Synthetic artifact')
        state = {'source_sha256':sha(job/'source.pdf'),'pages':[{'page':1},{'page':2}],
                 'attempts':[],'errors':[], 'status':'REVIEW_REQUIRED',
                 'scores':[{'id':'001','current':'scores/001/rev-001',
                            'revisions':[{'path':'scores/001/rev-001','state':'REVIEW_REQUIRED'}]}]}
        dump(job/'job.json',state)
        review = {'source_sha256':state['source_sha256'],'reviewer':'Synthetic fixture',
                  'method':'Test fixture; does not claim actual source review',
                  'pages':[{'page':1,'classification':'music','status':'pass','evidence':'fixture',
                            'source_inventory':'One complete staff','score_ids':['001']},
                           {'page':2,'classification':'non-music','status':'pass','evidence':'blank fixture'}],
                  'score_revisions':{'001':sha(folder/'score.mscz')},'coverage_resolutions':[]}
        dump(job/'source-review.json',review)
        dump(job/'triage.json',{'items':[]})
        return job,state,review

    def accepted(self,job):
        # Isolate whole-PDF coverage rules; score-level audit is tested separately.
        with patch('pdf_to_mscz.finalize_score',return_value=0),redirect_stdout(io.StringIO()):
            return accept(job)

    def test_patch_preserves_untouched_music(self):
        root = apply_patch(self.xml,self.change())
        self.assertEqual('D',root.findtext('.//note/pitch/step'))
        self.assertEqual(['D','D','E','F'],[n.findtext('pitch/step') for n in root.findall('.//note')])

    def test_patch_stale_hash_rejected(self):
        spec=self.change();spec['input_sha256']='stale'
        with self.assertRaises(ValueError):apply_patch(self.xml,spec)

    def test_patch_wrong_old_pitch_rejected(self):
        with self.assertRaises(ValueError):apply_patch(self.xml,self.change(before='B'))

    def test_patch_ambiguous_address_rejected(self):
        with self.assertRaises(ValueError):apply_patch(self.xml,self.change(select='note/pitch/step'))

    def test_patch_requires_source_reason(self):
        with self.assertRaises(ValueError):apply_patch(self.xml,self.change(reason=''))

    def test_patch_can_insert_missing_complex_symbol(self):
        root=apply_patch(self.xml,self.change(select='note[1]',op='insert',xml='<notations><ornaments><trill-mark/></ornaments></notations>'))
        self.assertIsNotNone(root.find('.//ornaments/trill-mark'))

    def test_patch_can_replace_measure_for_arbitrary_notation(self):
        root=apply_patch(self.xml,self.change(select='.',op='replace',xml='<measure number="1"><direction><direction-type><words>rit.</words></direction-type></direction></measure>'))
        self.assertEqual('rit.',root.findtext('.//words'))

    def test_patch_can_remove_spurious_direction(self):
        root=apply_patch(self.xml,self.change(select='note[1]',op='remove'))
        self.assertEqual(3,len(root.findall('.//note')))

    def test_patch_attribute_requires_before_value(self):
        root=apply_patch(self.xml,self.change(select='.',op='attribute',name='number',before='1',after='0'))
        self.assertEqual('0',root.find('part/measure').get('number'))
        with self.assertRaises(ValueError):apply_patch(self.xml,self.change(select='.',op='attribute',name='number',before='9',after='0'))

    def test_five_line_inventory_and_missing_staff(self):
        width,height=300,240
        pixels=bytearray([255])*(width*height)
        for top in (30,130):
            for line in range(5):
                y=top+line*8
                pixels[y*width+15:y*width+285]=bytes([0])*270
        hints=staff_hints(bytes(pixels),width,height)
        self.assertEqual(2,len(hints))
        hints=[dict(h,page=1) for h in hints]
        findings=coverage_findings(hints,[dict(hints[0])])
        self.assertEqual(1,len(findings))
        self.assertEqual('coverage',findings[0]['kind'])

    def test_no_staff_in_blank_page(self):
        self.assertEqual([],staff_hints(bytes([255])*100*100,100,100))

    def test_source_page_cannot_disappear_from_review(self):
        job,state,review=self.job();review['pages'].pop();dump(job/'source-review.json',review)
        self.assertEqual(1,self.accepted(job))

    def test_duplicate_source_page_rejected(self):
        job,state,review=self.job();review['pages'][1]=copy.deepcopy(review['pages'][0]);dump(job/'source-review.json',review)
        self.assertEqual(1,self.accepted(job))

    def test_all_outputs_must_map_to_source(self):
        job,state,review=self.job();state['scores'].append({'id':'002','revisions':[]});dump(job/'job.json',state)
        self.assertEqual(1,self.accepted(job))

    def test_unresolved_missing_staff_blocks_acceptance(self):
        job,state,review=self.job();dump(job/'triage.json',{'items':[{'kind':'coverage','id':'missing-staff'}]})
        self.assertEqual(1,self.accepted(job))
        review['coverage_resolutions']=[{'id':'missing-staff','status':'pass','evidence':'Synthetic fixture repair'}]
        dump(job/'source-review.json',review)
        self.assertEqual(0,self.accepted(job))

    def test_source_review_must_cover_current_revision(self):
        job,state,review=self.job();(job/'scores/001/rev-001/score.mscz').write_bytes(b'Changed')
        self.assertEqual(1,self.accepted(job))

    def test_latest_failed_revision_cannot_accept_old_success(self):
        job,state,review=self.job();state['scores'][0]['revisions'].append({'path':'scores/001/rev-002','state':'CONVERSION_FAILED'});dump(job/'job.json',state)
        self.assertEqual(1,self.accepted(job))

    def test_changed_source_rejected(self):
        job,state,review=self.job();(job/'source.pdf').write_bytes(b'Other PDF')
        with self.assertRaises(ValueError):read_job(job)

    def test_no_score_cannot_be_accepted(self):
        job,state,review=self.job();state['scores']=[];dump(job/'job.json',state)
        self.assertEqual(1,self.accepted(job))

    def test_unregistered_omr_movement_blocks_acceptance(self):
        job,state,review=self.job()
        folder=job/'omr/attempt-001';folder.mkdir(parents=True)
        dump(folder/'engine.json',{'candidates':['missing-movement.musicxml']})
        state['attempts']=['omr/attempt-001'];dump(job/'job.json',state)
        self.assertEqual(1,self.accepted(job))

    def test_job_paths_cannot_escape(self):
        with self.assertRaises(ValueError):contained(self.root,'../outside')

    def test_engine_retains_all_movements(self):
        exe=self.root/'Audiveris.exe';exe.write_bytes(b'not executed')
        pdf=self.root/'source.pdf';pdf.write_bytes(b'fixture')
        def fake(command,**kwargs):
            folder=Path(command[command.index('-output')+1]);folder.mkdir()
            for name in ('movement-1.musicxml','movement-2.musicxml'):
                (folder/name).write_bytes(self.xml.read_bytes())
            return SimpleNamespace(returncode=0)
        with patch('omr_engine.subprocess.run',side_effect=fake):
            report=run_engine(pdf,self.root/'omr',exe)
        self.assertEqual(2,len(report['candidates']))
        self.assertFalse(report['accuracy_claim'])

    def test_empty_success_is_not_recognized_score(self):
        exe=self.root/'Audiveris.exe';exe.write_bytes(b'fixture');pdf=self.root/'source.pdf';pdf.write_bytes(b'fixture')
        with patch('omr_engine.subprocess.run',return_value=SimpleNamespace(returncode=0)):
            report=run_engine(pdf,self.root/'omr',exe)
        self.assertEqual('NEEDS_TRANSCRIPTION',report['status'])

    def test_engine_timeout_is_recorded(self):
        exe=self.root/'Audiveris.exe';exe.write_bytes(b'fixture');pdf=self.root/'source.pdf';pdf.write_bytes(b'fixture')
        with patch('omr_engine.subprocess.run',side_effect=subprocess.TimeoutExpired('audiveris',1)):
            report=run_engine(pdf,self.root/'omr',exe,timeout=1)
        self.assertTrue(report['timed_out']);self.assertFalse(report['accuracy_claim'])

    def test_failed_rebuild_invalidates_previous_current(self):
        job,state,review=self.job();score=state['scores'][0]
        exe=self.root/'MuseScore.exe';exe.write_bytes(b'fixture')
        with patch('pdf_to_mscz.convert',side_effect=ValueError('Synthetic conversion failure')):
            make_revision(job,state,score,self.xml,exe)
        self.assertNotIn('current',score)
        self.assertEqual('NEEDS_CORRECTION',state['status'])

    def test_resume_uses_cached_omr_and_keeps_all_exports(self):
        job,state,review=self.job();state['scores']=[]
        folder=job/'omr/attempt-001';folder.mkdir(parents=True)
        for name in ('a.musicxml','b.musicxml'):(folder/name).write_bytes(self.xml.read_bytes())
        dump(folder/'engine.json',{'candidates':['a.musicxml','b.musicxml']})
        state['attempts']=['omr/attempt-001']
        args=SimpleNamespace(retry_omr=False,musescore='unused',convert_timeout=10)
        with patch('pdf_to_mscz.make_revision') as convert,patch('pdf_to_mscz.run_engine') as engine,redirect_stdout(io.StringIO()):
            recognize(job,state,args)
        self.assertEqual(2,len(state['scores']));self.assertEqual(2,convert.call_count);engine.assert_not_called()

    def test_omr_coordinates_and_incomplete_sheet_diagnostics(self):
        p=self.root/'fixture.omr'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('book.xml','<book><sheet number="1"><input><number>2</number></input><steps>LOAD GRID</steps></sheet></book>')
            z.writestr('sheet#1/sheet#1.xml','<sheet><picture width="1000" height="1000"/><page><system id="1"><stack id="2" abnormal="true"/><part><staff id="1"><lines><line><point x="50" y="100"/><point x="950" y="200"/></line></lines></staff></part><sig><note id="3" grade="0.1"><bounds x="400" y="100" w="20" h="20"/></note></sig></system></page></sheet>')
        report=project_diagnostics(p)
        self.assertFalse(report['sheets'][0]['completed']);self.assertEqual(2,report['staves'][0]['page'])
        self.assertEqual(2,len(report['findings']));self.assertIn('bbox',report['findings'][1])


try:
    import pymupdf
except ImportError:
    pymupdf=None


@unittest.skipUnless(pymupdf,'PyMuPDF optional integration dependency unavailable')
class PdfPageTests(unittest.TestCase):
    def test_prepare_preserves_all_pages_and_hints_without_omr(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);pdf=root/'new-score.pdf'
            with pymupdf.open() as doc:
                page=doc.new_page(width=400,height=300)
                for y in (70,78,86,94,102):page.draw_line((20,y),(380,y),width=1)
                doc.new_page(width=400,height=300)
                doc.save(pdf)
            state=prepare(pdf,root/'job',dpi=100)
            self.assertEqual(2,len(state['pages']));self.assertEqual(1,len(state['pages'][0]['staff_hints']))
            self.assertEqual([],state['pages'][1]['staff_hints'])
            self.assertEqual(sha(pdf),sha(root/'job/source.pdf'))
            with self.assertRaises(ValueError):prepare(pdf,root/'job',dpi=100)

    def test_non_pdf_fails_before_creating_job(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'broken.pdf';source.write_bytes(b'not PDF')
            with self.assertRaises(Exception):prepare(source,root/'job')
            self.assertFalse((root/'job').exists())


if __name__=='__main__':unittest.main()
