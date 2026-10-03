"""Invisible voice gaps must not hide real mismatches or change the source."""
import base64
import copy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from criar_licao import synchronize_media


def positions(times,widths):
    elements=''.join(f'<element id="{i}" sx="{width}"/>' for i,width in enumerate(widths))
    events=''.join(f'<event elid="{i}" position="{time*1000}"/>' for i,time in enumerate(times))
    return base64.b64encode(f'<score><elements>{elements}</elements><events>{events}</events></score>'.encode()).decode()

class Gaps(unittest.TestCase):
    def fixture(self,widths=(5,0,5)):
        media={'metadata':{'duration':4},'mposXML':positions([0],[5]),'sposXML':positions([0,1,2],widths)}
        sequence={'duration':3,'measureStarts':[{'time':0,'measure':1}],
                  'cursorEvents':[{'time':0,'measure':1},{'time':1.5,'measure':1}]}
        return media,sequence

    def test_extra_zero_width_is_removed_without_modifying_input(self):
        media,seq=self.fixture();before=copy.deepcopy(media)
        result,_,_=synchronize_media(media,seq)
        events=ET.fromstring(base64.b64decode(result['sposXML'])).findall('events/event')
        self.assertEqual([(e.get('elid'),e.get('position')) for e in events],[('0','0.000'),('2','1500.000')])
        self.assertEqual(media,before)

    def test_real_excess_and_partial_explanation_are_rejected(self):
        for widths in [(5,1,5),(5,0,0)]:
            with self.subTest(widths=widths):
                with self.assertRaisesRegex(ValueError,'quantidade'):
                    synchronize_media(*self.fixture(widths))

    def test_existing_zero_width_match_is_preserved(self):
        media,seq=self.fixture()
        seq['cursorEvents'].insert(1,{'time':.75,'measure':1})
        result,_,_=synchronize_media(media,seq)
        self.assertEqual(len(ET.fromstring(base64.b64decode(result['sposXML'])).findall('events/event')),3)

    def test_measure_mismatch_still_rejected(self):
        media,seq=self.fixture();seq['cursorEvents'][-1]['measure']=2
        with self.assertRaisesRegex(ValueError,'compasso diferente'):
            synchronize_media(media,seq)

if __name__=='__main__':unittest.main()
