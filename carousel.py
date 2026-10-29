"""Banner da entrada; imagens numeradas são ordenadas numericamente."""
from html import escape
from pathlib import Path
import re
from urllib.parse import quote, urlsplit


def images(root):
    numbered=[]
    for path in (root/'carrossel').iterdir():
        number=re.fullmatch(r'(\d+)(?:[-_ ].+)?',path.stem)
        if path.is_file() and number and path.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.svg'):
            numbered.append((int(number.group(1)),path.name))
    numbered.sort()
    if len({n for n,_ in numbered}) != len(numbered):
        raise ValueError('Há números repetidos em carrossel/ (por exemplo 01.jpg e 01.png).')
    return [name for _,name in numbered] or ['padrao.svg']


def banner(root,base):
    names=images(root)
    slides=[]
    for i,name in enumerate(names):
        metadata=root/'carrossel'/(Path(name).stem+'.txt')
        description=[]
        link=''
        if metadata.exists():
            for line in metadata.read_text(encoding='utf-8').splitlines():
                if line.strip().lower().startswith('link:'):
                    link=line.strip().split(':',1)[1].strip()
                else:
                    description.append(line)
        if link:
            parsed=urlsplit(link)
            if (parsed.scheme.lower() not in ('http','https') or not parsed.netloc
                    or any(char.isspace() or ord(char)<32 for char in link)):
                raise ValueError(f'{metadata}: Link deve ser uma URL completa http:// ou https://.')
        text='\n'.join(description).strip()
        alt='' if text else 'Banner Clave Sol'
        caption=f'<span class="carousel-caption">{escape(text)}</span>' if text else ''
        hidden=' hidden' if i else ''
        loading=' loading="lazy"' if i else ' fetchpriority="high"'
        img=f'<img src="{base}/carrossel/{quote(name)}" alt="{alt}" width="1600" height="320"{loading}'
        tag='a' if link else 'div'
        href=f' href="{escape(link,quote=True)}"' if link else ''
        slides.append(f'<{tag} class="carousel-slide"{href}{hidden}>{img}>{caption}</{tag}>')
    slides=''.join(slides)
    controls='<div class="carousel-controls" hidden><button type="button" data-prev aria-label="Imagem anterior">‹</button><span data-count role="status" aria-live="polite"></span><button type="button" data-next aria-label="Próxima imagem">›</button></div>' if len(names)>1 else ''
    return f'<link rel="stylesheet" href="{base}/assets/carrossel.css"><section class="collection-carousel" aria-label="Destaques do acervo" aria-roledescription="carrossel" tabindex="0"><div class="carousel-slides">{slides}</div>{controls}</section><script type="module" src="{base}/assets/carrossel.mjs"></script>'
