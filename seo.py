"""Static sharing metadata and search discovery, generated before asset versioning."""
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import re
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree as ET


class PageText(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.title = []
        self.lead = []
        self.in_title = self.in_lead = False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'p' and 'lead' in attrs.get('class', '').split() and not self.lead:
            self.in_lead = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'p':
            self.in_lead = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.in_lead:
            self.lead.append(data)


def finish_seo(out, base, config, metadata=None, aliases=None):
    metadata, aliases = metadata or {}, aliases or {}
    origin = os.environ.get('SITE_URL', config['site_url']).rstrip('/')
    parts = urlsplit(origin)
    if parts.scheme not in ('http', 'https') or not parts.netloc or parts.path or parts.query or parts.fragment:
        raise ValueError('SITE_URL/seo.json site_url deve ser uma origem absoluta, sem caminho, query ou fragmento.')
    home = origin + base + '/'

    def public_url(route):
        return home + quote(route.strip('/'), safe='/') + ('/' if route else '')

    def image_data(name):
        relative = Path(name)
        path = (out / 'assets' / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to((out / 'assets').resolve()) or not path.is_file():
            raise ValueError(f'Imagem de SEO inexistente ou fora de assets/: {name}')
        mime = mimetypes.guess_type(name)[0]
        if mime not in ('image/jpeg', 'image/png', 'image/webp', 'image/gif'):
            raise ValueError(f'Use JPG, PNG, WebP ou GIF como imagem de SEO: {name}')
        digest = sha256(path.read_bytes()).hexdigest()[:16]
        return home + 'assets/' + quote(relative.as_posix(), safe='/') + '?v=' + digest, mime

    image_data(config['default_image'])
    urls = set()
    for path in sorted(out.rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        if path.name == '404.html':
            source = source.replace('</head>', '<meta name="robots" content="noindex,follow"></head>')
            path.write_text(source, encoding='utf-8')
            continue
        route = path.parent.relative_to(out).as_posix()
        route = '' if route == '.' else route
        canonical_route = aliases.get(route, route)
        canonical = public_url(canonical_route)
        parsed = PageText(source)
        info = metadata.get(canonical_route, {})
        title = ''.join(parsed.title)
        description = info.get('description') or ' '.join(''.join(parsed.lead).split()) or config['description']
        selected = info.get('socialimage') or info.get('image') or config['default_image']
        image, mime = image_data(selected)
        alt = info.get('socialimagealt') or (config['default_image_alt'] if selected == config['default_image'] else f'Imagem de capa: {info.get("title", title)}')
        article = info.get('type') == 'article'
        def meta(key, value, attr='name'):
            return f'<meta {attr}="{key}" content="{escape(value, quote=True)}">'
        tags = [meta('description', description),
                f'<link rel="canonical" href="{escape(canonical, quote=True)}">',
                meta('robots', 'index,follow,max-image-preview:large')]
        for key, value in {'og:type': 'article' if article else 'website', 'og:site_name': config['site_name'],
                           'og:locale': 'pt_BR', 'og:title': title, 'og:description': description,
                           'og:url': canonical, 'og:image': image, 'og:image:type': mime,
                           'og:image:alt': alt}.items():
            tags.append(meta(key, value, 'property'))
        for key, value in {'twitter:card': 'summary_large_image', 'twitter:title': title,
                           'twitter:description': description, 'twitter:image': image,
                           'twitter:image:alt': alt}.items():
            tags.append(meta(key, value))
        data = {'@context': 'https://schema.org', '@type': 'BlogPosting' if article else 'WebPage',
                'url': canonical, 'name': info.get('title', title), 'description': description,
                'image': image, 'inLanguage': 'pt-BR',
                'isPartOf': {'@type': 'WebSite', '@id': home + '#website', 'url': home, 'name': config['site_name']}}
        if article:
            data['headline'] = info['title']
            data['mainEntityOfPage'] = canonical
        if not route:
            data = {'@context': 'https://schema.org', '@type': 'WebSite', '@id': home + '#website',
                    'url': home, 'name': config['site_name'], 'description': description,
                    'inLanguage': 'pt-BR', 'sameAs': config.get('social_profiles', [])}
        encoded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
        tags.append(f'<script type="application/ld+json">{encoded}</script>')
        source = re.sub(r'<meta\s+name="description"\s+content="[^"]*"\s*/?>', '', source, flags=re.I)
        source = source.replace('</head>', '\n' + '\n'.join(tags) + '\n</head>')
        path.write_text(source, encoding='utf-8')
        urls.add(canonical)
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('', namespace)
    sitemap = ET.Element(f'{{{namespace}}}urlset')
    for url in sorted(urls):
        node = ET.SubElement(sitemap, f'{{{namespace}}}url')
        ET.SubElement(node, f'{{{namespace}}}loc').text = url
    ET.ElementTree(sitemap).write(out / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
    (out / 'robots.txt').write_text(f'User-agent: *\nAllow: /\n\nSitemap: {home}sitemap.xml\n', encoding='utf-8')
