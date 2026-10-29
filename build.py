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

# >>> CLAVE SOL CARROSSEL E CATALOGO - INICIO
# Recursos do carrossel e catalogos do Mose; nao altera os MusicXML.
from carousel import banner as _clavesol_banner, images as _clavesol_images
import hashlib as _clavesol_hashlib
import re as _clavesol_re

for _name in ('carrossel.css', 'carrossel.mjs'):
    _src = ROOT / 'assets' / _name
    _dst = OUT / 'assets' / _name
    if not _src.is_file():
        raise FileNotFoundError(f'Recurso do carrossel ausente: {_src}')
    _dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_src, _dst)

(OUT / 'carrossel').mkdir(parents=True, exist_ok=True)
for _name in _clavesol_images(ROOT):
    shutil.copy2(ROOT / 'carrossel' / _name, OUT / 'carrossel' / _name)

# A entrada pode ser diferente em um hinario antigo, na Harpa ou em musicas.
_clavesol_collection = config['collection']
_clavesol_route = ('partituras/musicas' if _clavesol_collection == 'musicas'
                    else 'partituras/hinos/' + _clavesol_collection)
for _relative in ('index.html', _clavesol_route + '/index.html'):
    _target = OUT / _relative
    if not _target.is_file():
        continue
    _html = _target.read_text(encoding='utf-8')
    if 'class="collection-carousel"' in _html:
        continue  # Evita carrossel duplicado em builds modernos.
    _banner = _clavesol_banner(ROOT, BASE)
    _match = _clavesol_re.search(r'<div\s+class=["\']list-search["\'][^>]*>', _html)
    if not _match:
        _match = _clavesol_re.search(r'<div\s+class=["\']prose["\'][^>]*>', _html)
    if _match:
        _html = _html[:_match.start()] + _banner + _html[_match.start():]
    elif '<main id="conteudo">' in _html:
        _html = _html.replace('<main id="conteudo">', '<main id="conteudo">' + _banner, 1)
    else:
        raise ValueError(f'Nao foi encontrado o ponto de insercao do carrossel em {_target}')
    _target.write_text(_html, encoding='utf-8')

_clavesol_json = ROOT / 'cardapio.json'
_clavesol_sha = ROOT / 'cardapio.sha256'
if _clavesol_json.is_file() != _clavesol_sha.is_file():
    raise ValueError('cardapio.json e cardapio.sha256 devem existir juntos na raiz do site')
if _clavesol_json.is_file():
    _payload = _clavesol_json.read_bytes()
    json.loads(_payload.decode('utf-8'))
    _expected = _clavesol_sha.read_text(encoding='utf-8').strip().split()[0].lower()
    _actual = _clavesol_hashlib.sha256(_payload).hexdigest()
    if _expected != _actual:
        raise ValueError('cardapio.sha256 nao corresponde ao cardapio.json')
    shutil.copy2(_clavesol_json, OUT / 'cardapio.json')
    shutil.copy2(_clavesol_sha, OUT / 'cardapio.sha256')
else:
    print('Aviso: sem cardapio.json/sha256 na raiz; publicacao do catalogo ignorada')
# <<< CLAVE SOL CARROSSEL E CATALOGO - FIM

finish_build(OUT,BASE)
print(f"{len(catalog.scores)} partituras validadas; site em {OUT}")
