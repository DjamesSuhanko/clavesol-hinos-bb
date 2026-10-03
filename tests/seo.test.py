from pathlib import Path
from tempfile import TemporaryDirectory
from html.parser import HTMLParser
from unittest.mock import patch
import json
import sys
from xml.etree import ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from seo import finish_seo

class Metadata(HTMLParser):
    def __init__(self, source):
        super().__init__(); self.tags = {}; self.canonical = ''; self.feed(source)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = attrs.get('name') or attrs.get('property')
            assert key not in self.tags, f'Duplicate metadata: {key}'
            self.tags[key] = attrs.get('content')
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical = attrs['href']

config = {'site_url': 'https://clavesol.com.br', 'site_name': 'Clave Sol',
          'description': 'Descrição padrão', 'default_image': 'default.jpg',
          'default_image_alt': 'Clarinete', 'social_profiles': ['https://www.youtube.com/@ClaveSolMusic']}
source = '<html><head><title>Música &amp; estudo · Clave Sol</title><meta name="description" content="old"></head><body><p class="lead">Descrição da página.</p></body></html>'
with patch.dict('os.environ', {'SITE_URL': 'https://example.org'}):
 for base in ('', '/clavesol'):
  with TemporaryDirectory() as folder:
   out = Path(folder); (out/'assets').mkdir()
   for image in ('default.jpg', 'capa.webp', 'social.png'):
    (out/'assets'/image).write_bytes(b'image fixture')
   for name in ('index.html', 'artigos/teste/index.html', 'musica/index.html', 'partituras/index.html', '404.html'):
    target = out/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(source)
   info = {'artigos/teste': {'type': 'article', 'title': 'Música </script> & estudo',
            'description': 'Um "teste" & detalhes', 'image': 'capa.webp', 'socialimage': 'social.png'}}
   finish_seo(out, base, config, info, {'musica': 'partituras'})
   home = 'https://example.org' + base + '/'
   article = (out/'artigos/teste/index.html').read_text()
   meta = Metadata(article)
   assert meta.canonical == home + 'artigos/teste/'
   assert meta.tags['description'] == info['artigos/teste']['description']
   assert meta.tags['og:type'] == 'article'
   assert meta.tags['og:image'].startswith(home + 'assets/social.png?v=')
   assert meta.tags['twitter:image'] == meta.tags['og:image']
   assert meta.tags['og:url'] == meta.canonical
   data = json.loads(article.split('<script type="application/ld+json">')[1].split('</script>')[0])
   assert data['headline'] == info['artigos/teste']['title']
   assert '<script> & estudo' not in article
   assert Metadata((out/'index.html').read_text()).tags['og:image'].startswith(home+'assets/default.jpg?v=')
   assert Metadata((out/'musica/index.html').read_text()).canonical == home+'partituras/'
   assert Metadata((out/'404.html').read_text()).tags['robots'] == 'noindex,follow'
   locations = [node.text for node in ET.parse(out/'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
   assert set(locations) == {home, home+'artigos/teste/', home+'partituras/'}
   assert len(locations) == 3
   assert f'Sitemap: {home}sitemap.xml' in (out/'robots.txt').read_text()
   # Changing a sharing image changes its URL even when its filename is unchanged.
   old_image = meta.tags['og:image']
   (out/'assets/social.png').write_bytes(b'new image fixture')
   for target in out.rglob('*.html'): target.write_text(source)
   finish_seo(out, base, config, info, {'musica': 'partituras'})
   assert Metadata((out/'artigos/teste/index.html').read_text()).tags['og:image'] != old_image
   info['artigos/teste']['socialimage'] = '../missing.jpg'
   try: finish_seo(out, base, config, info)
   except ValueError: pass
   else: raise AssertionError('Invalid sharing images must fail the build')
print('SEO: sharing metadata, defaults, escaping, canonical aliases, sitemap, 404 and base paths: OK')
