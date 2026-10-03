from pathlib import Path
from tempfile import TemporaryDirectory
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from musicxml_audio import parse_musicxml

class Fermatas(unittest.TestCase):
 def test_simultaneous_marks_and_rest_keep_notated_cursor(self):
  with TemporaryDirectory() as d:
   p=Path(d)/'score.musicxml'
   note='<note><pitch><step>C</step><octave>4</octave></pitch><duration>3</duration><notations><fermata type="upright"/><fermata type="inverted"/></notations></note>'
   body='<measure><sound tempo="60"/>'+note+'<note><rest/><duration>1</duration><notations><fermata/></notations></note></measure>'
   p.write_text('<score-partwise><part id="P1">'+body+'</part><part id="P2">'+body+'</part></score-partwise>')
   s=parse_musicxml(p,include_cursor=True)
   self.assertEqual(s['fermatas'],[{'start':0,'end':3},{'start':3,'end':4}])
   self.assertEqual(s['duration'],4)
   self.assertEqual(s['cursorEvents'],[{'measure':1,'time':0},{'measure':1,'time':3}])
if __name__=='__main__':unittest.main()
