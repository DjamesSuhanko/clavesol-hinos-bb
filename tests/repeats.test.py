from pathlib import Path
from tempfile import TemporaryDirectory
import base64,json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from musicxml_audio import parse_musicxml
from criar_licao import synchronize_media

F='<barline location="left"><repeat direction="forward"/></barline>'
B='<barline location="right"><repeat direction="backward"/></barline>'
N='<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>'
def ending(numbers,kind):
 return f'<barline location="{"left" if kind=="start" else "right"}"><ending number="{numbers}" type="{kind}"/></barline>'

class Repeats(unittest.TestCase):
 def parse(self,rows):
  with TemporaryDirectory() as d:
   p=Path(d)/'score.musicxml'
   p.write_text('<score-partwise><part id="P1">'+''.join('<measure>'+('<sound tempo="60"/>' if i==0 else '')+r+'</measure>' for i,r in enumerate(rows))+'</part></score-partwise>')
   return parse_musicxml(p,include_cursor=True)
 def test_simple_repeat_and_implicit_start(self):
  for first in [F,'']:
   s=self.parse([first+N,N+B,N])
   self.assertEqual(s['measureOrder'],[1,2,1,2,3])
   self.assertEqual([e['measure'] for e in s['cursorEvents']],[1,2,1,2,3])
   self.assertEqual([e['visit'] for e in s['cursorEvents']],[1,2,3,4,5])
   self.assertEqual(s['duration'],5)
 def test_two_endings(self):
  s=self.parse([F+N,ending('1','start')+N+ending('1','stop')+B,ending('2','start')+N+ending('2','discontinue'),N])
  self.assertEqual(s['measureOrder'],[1,2,1,3,4])
 def test_three_passes_shared_ending(self):
  s=self.parse([F+N,ending('1,2','start')+N+ending('1,2','stop')+B,ending('3','start')+N+ending('3','discontinue'),N])
  self.assertEqual(s['measureOrder'],[1,2,1,2,1,3,4])
 def test_nested_and_adjacent_repeats(self):
  s=self.parse([F+N,F+N,N+B,N+B,F+N,N+B])
  self.assertEqual(s['measureOrder'],[1,2,3,2,3,4,1,2,3,2,3,4,5,6,5,6])
 def test_tempo_restored_on_backward_jump(self):
  s=self.parse([F+N,'<sound tempo="120"/>'+N+B])
  self.assertEqual([n['duration'] for n in s['notes']],[1,.5,1,.5])
  self.assertEqual(s['duration'],3)
 def test_fermatas_repeated_at_each_visit(self):
  s=self.parse([F+N.replace('</note>','<notations><fermata/></notations></note>')+B])
  self.assertEqual(s['fermatas'],[dict(start=0,end=1),dict(start=1,end=2)])
 def test_missing_first_house_and_visual_mismatch_rejected(self):
  with self.assertRaisesRegex(ValueError,'primeira'):
   self.parse([F+N,ending('2','start')+N+ending('2','stop')+B,ending('3','start')+N+ending('3','discontinue')])
  with self.assertRaisesRegex(ValueError,'mostra'):
   self.parse([F+N,ending('2','start').replace('/>','>1.2.</ending>')+N+ending('2','stop')+B])
 def test_jump_and_unclosed_repeat_remain_blocked(self):
  with self.assertRaisesRegex(ValueError,'saltos'):
   self.parse([N+'<sound dacapo="yes"/>'])
  with self.assertRaisesRegex(ValueError,'fechamento'):
   self.parse([F+N])
 def test_attributes_restored_on_repeated_entry(self):
  # The opening measure inherits divisions=1; a later measure changes it.
  s=self.parse([F+N,'<attributes><divisions>2</divisions><transpose><chromatic>-2</chromatic></transpose></attributes>'+N+B])
  self.assertEqual([n['duration'] for n in s['notes']],[1,.5,1,.5])
  self.assertEqual([n['midi'] for n in s['notes']],[60,58,60,58])
 def test_forward_skip_preserves_intended_tie(self):
  start=N.replace('</note>','<tie type="start"/></note>')
  stop=N.replace('</note>','<tie type="stop"/></note>')
  s=self.parse([F+start,ending('1','start')+stop+ending('1','stop')+B,ending('2','start')+stop+ending('2','discontinue')])
  self.assertEqual(s['measureOrder'],[1,2,1,3])
  self.assertEqual([(n['time'],n['duration']) for n in s['notes']],[(0,2),(2,2)])
 def test_repeat_count_and_bound(self):
  s=self.parse([F+N+B.replace('direction="backward"','direction="backward" times="3"')])
  self.assertEqual(s['measureOrder'],[1,1,1])
  with self.assertRaisesRegex(ValueError,'entre 1 e 32'):
   self.parse([N+B.replace('direction="backward"','direction="backward" times="1000000"')])
 def test_cursor_checks_each_visit_not_just_measure_number(self):
  s=self.parse([F+N,N+B])
  def xml(ids):
   elements=''.join(f'<element id="{i}" sx="1"/>' for i in set(ids))
   events=''.join(f'<event elid="{v}" position="{i*1000}"/>' for i,v in enumerate(ids))
   return base64.b64encode(f'<score><elements>{elements}</elements><events>{events}</events></score>'.encode()).decode()
  media=dict(metadata={'duration':4},mposXML=xml([0,1,0,1]),sposXML=xml([0,1,0,1]))
  synchronize_media(media,s)
  s['cursorEvents'][2]['visit']=1
  with self.assertRaisesRegex(ValueError,'compasso diferente'):
   synchronize_media(media,s)

if __name__=='__main__':unittest.main()
