from pathlib import Path
from tempfile import TemporaryDirectory
import sys,json,re
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cache_assets import finish_build

def render(base='', css='body{}', module='export const eventAt=0;', text='Article'):
 with TemporaryDirectory() as folder:
  out=Path(folder);assets=out/'assets';assets.mkdir()
  for name,data in {'style.css':css,'music-synth.mjs':module,'music-timing.mjs':module,'music.js':"import {eventAt} from './music-timing.mjs';",'score.json':'{}'}.items():(assets/name).write_text(data)
  (out/'index.html').write_text(f'<link href="{base}/assets/style.css"><script src="{base}/assets/music.js"></script><audio data-sequence="{base}/assets/score.json" data-timing="{base}/assets/score.json"></audio><p>{text}</p><script data-version="__CLAVESOL_VERSION__"></script>')
  finish_build(out,base)
  return (out/'index.html').read_text(),(assets/'music.js').read_text(),json.loads((out/'version.json').read_text())['version']
a=render();assert a==render(), 'Build must be stable for identical content'
assert a[2]!=render(text='New article')[2], 'Article changes must invalidate release'
assert a[2]!=render(css='body{color:red}')[2]
assert a[1]!=render(module='export const eventAt=1;')[1]
assert re.search(r'/assets/music.js\?v=[a-f0-9]{16}',a[0]).group()!=re.search(r'/assets/music.js\?v=[a-f0-9]{16}',render(module='export const eventAt=1;')[0]).group()
assert '__CLAVESOL_VERSION__' not in a[0]
assert 'data-sequence="/assets/score.json?v=' in a[0]
assert 'data-timing="/assets/score.json?v=' in a[0]
assert 'href="/clavesol/assets/style.css?v=' in render('/clavesol')[0]
print('Stable builds, article/CSS/module invalidation and both base paths: OK')
