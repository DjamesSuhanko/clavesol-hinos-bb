from pathlib import Path
from tempfile import TemporaryDirectory
import sys, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from musicxml_audio import parse_musicxml

class Introduction(unittest.TestCase):
 def parse(self, body):
  with TemporaryDirectory() as d:
   p=Path(d)/'s.musicxml';p.write_text('<score-partwise><part>'+body+'</part></score-partwise>')
   return parse_musicxml(p)
 def test_hino_6(self):
  s=parse_musicxml(Path(__file__).parent/"fixtures/hino-6-introduction.musicxml")
  self.assertEqual(s["introEnd"],16)
  self.assertEqual(s["duration"],176)
  self.assertEqual(s["measureOrder"].count(5),3)
 def test_first_repeat_visit_and_no_star(self):
  note='<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>'
  mark='<harmony><kind text="*">none</kind></harmony>'
  body='<measure><sound tempo="60"/><barline location="left"><repeat direction="forward"/></barline>'+note+mark+note+'<barline><repeat direction="backward" times="3"/></barline></measure>'
  s=self.parse(body);self.assertEqual(s['introEnd'],2);self.assertEqual(s['duration'],6)
  self.assertNotIn('introEnd',self.parse(body.replace(mark,'')))
 def test_tied_note_with_tempo_change(self):
  start='<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><tie type="start"/></note>'
  stop=start.replace('start','stop')
  s=self.parse('<measure><sound tempo="60"/><direction><direction-type><words>*</words></direction-type></direction>'+start+'</measure><measure><sound tempo="120"/>'+stop+'</measure>')
  self.assertEqual(s['introEnd'],1.5)
if __name__=='__main__':unittest.main()
