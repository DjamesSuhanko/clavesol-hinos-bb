from pathlib import Path
import json, os, shutil
from score_catalog import load_catalog
from music_pages import build_music
from site_layout import page as layout
from cache_assets import finish_build
from seo import finish_seo
ROOT = Path(__file__).resolve().parent
config = json.loads((ROOT/'hinario.json').read_text())
BASE = os.environ.get('BASE_PATH', '/' + config['repository']).rstrip('/')
OUT = ROOT/'dist'
catalog = load_catalog(ROOT)
assert catalog.scores and all(s.parent == 'hinos/' + config['collection'] and s.playback == 'generated' and s.timing for s in catalog.scores)
if OUT.exists(): shutil.rmtree(OUT)
shutil.copytree(ROOT/'assets', OUT/'assets')
for score in catalog.scores:
 (OUT/'assets'/score.assets/'sequence.json').write_text(json.dumps(score.sequence,separators=(',',':')))
def page(title,body):
 for route in ('partituras', 'partituras/hinos'):
  body = body.replace(f'href="{BASE}/{route}/"', f'href="https://clavesol.com.br/{route}/"')
 body = body.replace(f'href="{BASE}/partituras/hinos/{config["collection"]}/"', f'href="{BASE}/"')
 return layout(title,body,BASE)
build_music(OUT,BASE,page,catalog)
collection_route = 'partituras/hinos/' + config['collection']
shutil.copyfile(OUT/collection_route/'index.html',OUT/'index.html')
(OUT/'404.html').write_text(page('Página não encontrada',f'<section class="category-page"><h1>Partitura não encontrada.</h1><a class="button" href="{BASE}/">Voltar ao hinário</a></section>'))
(OUT/'.nojekyll').touch()
seo = json.loads((ROOT/'seo.json').read_text())
seo['site_url'] = os.environ.get('SITE_URL',seo['site_url'])
finish_seo(OUT,BASE,seo,aliases={collection_route:'','musica':'partituras'})
finish_build(OUT,BASE)
print(f"{len(catalog.scores)} partituras validadas; site em {OUT}")
