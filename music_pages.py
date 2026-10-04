"""Static category, collection and score pages built from the Markdown catalog."""
from html import escape as E


def quantity(number, noun):
    return f'{number} {noun}{"s" if number != 1 else ""}'


def score_card(score, base, catalog):
    assets = f'{base}/assets/{score.assets}'
    if score.pages:
        thumb = f'<div class="score-thumb"><img src="{assets}/{score.pages[0][0]}" alt="Prévia de {E(score.title)}" loading="lazy"></div>'
    else:
        thumb = '<div class="score-thumb type-art" aria-hidden="true">𝄞</div>'
    meta = ' · '.join(filter(None, [score.author, score.instrument,
                                  quantity(len(score.pages), 'página') if score.pages else 'Arquivo para baixar']))
    download = ''
    if score.downloads:
        name, label = score.downloads[0]
        download = f'<a class="download" href="{assets}/{name}" download>Baixar {label}</a>'
    return f'<article class="score-card" data-search="{E(str(score.lesson or "") + " " + score.title + " " + score.author + " " + score.instrument)}">{thumb}<div><p class="eyebrow">{E(catalog.groups[score.parent].title)}</p><h3>{E(score.title)}</h3><p>{E(meta)}</p><a class="button" href="{base}/{score.route}/">Abrir partitura</a>{download}</div></article>'


def featured_score(catalog, base):
    if not catalog.scores:
        return '<p>As primeiras partituras serão publicadas aqui.</p>'
    return score_card(catalog.scores[0], base, catalog)


def score_body(score, catalog, base):
    assets = f'{base}/assets/{score.assets}'
    crumbs = [f'<a href="{base}/partituras/">Partituras</a>']
    parts = score.key.split('/')
    for length in range(1, len(parts)):
        key = '/'.join(parts[:length])
        crumbs.append(f'<a href="{base}/partituras/{key}/">{E(catalog.groups[key].title)}</a>')
    toolbar = ''
    if score.pages:
        toolbar += '<label for="score-zoom">Tamanho da partitura</label><select id="score-zoom"><option value="100">Ajustar à tela</option><option value="150">150%</option><option value="200">200%</option></select>'
    for name, label in score.downloads:
        toolbar += f'<a class="button" href="{assets}/{name}" download>Baixar {label}</a>'
    player = ''
    if score.playback == 'generated':
        timing = f' data-timing="{assets}/timing.json"' if score.timing else ''
        follow = '<label><input id="follow-cursor" type="checkbox" checked> Acompanhar cursor</label><span id="current-measure"></span>' if score.timing else ''
        player = f'''<div class="score-player" id="score-player" data-playback="generated" data-sequence="{assets}/sequence.json"{timing} data-measures="{score.measures}"><div class="player-main"><button id="play-toggle" class="play-toggle" type="button">Reproduzir</button><input id="playback-progress" type="range" min="0" max="1000" value="0" aria-label="Posição da reprodução"><span id="playback-time">0:00 / 0:00</span></div><div class="player-options"><button id="restart-score" type="button">Voltar ao início</button><label for="playback-bpm">Andamento (♩ BPM)</label><input id="playback-bpm" type="number" min="{score.sequence['quarterBpm'] * .1:g}" max="{score.sequence['quarterBpm'] * 4:g}" step="any" value="{score.sequence['quarterBpm']:g}" disabled aria-describedby="tempo-display"><button id="original-tempo" type="button" disabled>Andamento original</button><span id="tempo-display">Original: {E(score.sequence['marking'])}</span><label><input id="mute-score" type="checkbox"> Mudo para solfejo</label>{follow}</div><p id="playback-status" role="status">Carregando partitura…</p></div>'''
    elif score.audio:
        sources = ''.join(f'<source src="{assets}/{name}" type="{mime}">' for name, mime in score.audio)
        timing = f' data-timing="{assets}/timing.json"' if score.timing else ''
        follow = '<label><input id="follow-cursor" type="checkbox" checked> Acompanhar cursor</label><span id="current-measure"></span>' if score.timing else ''
        status = 'Carregando cursor…' if score.timing else 'Pronto para reproduzir'
        player = f'''<div class="score-player" id="score-player" data-playback="recorded"{timing} data-measures="{score.measures}"><audio id="score-audio" controls preload="none">{sources}<a href="{assets}/{score.audio[0][0]}">Baixar áudio</a></audio><div class="player-options"><button id="restart-score" type="button">Voltar ao início</button><label for="playback-speed">Velocidade</label><select id="playback-speed"><option value="0.5">0,5×</option><option value="0.75">0,75×</option><option value="1" selected>Normal</option><option value="1.25">1,25×</option><option value="1.5">1,5×</option></select>{follow}</div><p id="playback-status" role="status">{status}</p></div>'''
    sheets = []
    page_links = []
    for number, (name, width, height) in enumerate(score.pages, 1):
        page_links.append(f'<a href="#pagina-{number}">Página {number}</a>')
        cursor = '<div id="score-cursor" hidden aria-hidden="true"></div>' if score.timing and number == 1 else ''
        sheets.append(f'''<section class="score-page" id="pagina-{number}"><h2>Página {number} de {len(score.pages)}</h2><a class="text-link" href="{assets}/{name}" target="_blank" rel="noopener">Abrir página original</a><div class="score-viewport" tabindex="0" role="region" aria-label="Partitura, página {number}, com rolagem horizontal"><div class="score-sheet" data-page="{number}">{cursor}<img src="{assets}/{name}" alt="{E(score.title)}, página {number} de {len(score.pages)}" width="{width:g}" height="{height:g}"></div></div></section>''')
    pager = f'<nav class="score-page-links" aria-label="Páginas da partitura">{"".join(page_links)}</nav>' if len(page_links) > 1 else ''
    notes = score.body.replace('{{BASE}}', base)
    subtitle = ' · '.join(filter(None, [score.author, score.instrument]))
    script = f'<script type="module" src="{base}/assets/music.js"></script>' if score.pages or score.playback != 'none' else ''
    return f'''<section class="article-layout score-section"><nav class="breadcrumbs" aria-label="Caminho da partitura">{'<span>/</span>'.join(crumbs)}</nav><p class="eyebrow">ESTANTE DE PARTITURAS</p><h1>{E(score.title)}</h1><p class="lead">{E(subtitle)}</p><p>{E(score.description)}</p><div class="score-toolbar">{toolbar}</div>{player}{pager}{''.join(sheets)}<article class="prose score-notes">{notes}</article></section>{script}'''


def build_music(out, base, page, catalog, external=None):
    external = external or {}
    def save(route, title, body):
        target = out / route
        target.mkdir(parents=True, exist_ok=True)
        (target / 'index.html').write_text(page(title, body), encoding='utf-8')

    def group_card(group):
        count = sum(s.key.startswith(group.key + '/') for s in catalog.scores)
        count += sum(len(value['scores']) for key, value in external.items() if key == group.key or key.startswith(group.key + '/'))
        explore = external.get(group.key, {}).get('url', f'{base}/partituras/{group.key}/')
        return f'<article class="card"><div class="card-body"><p class="eyebrow">{quantity(count, "partitura")}</p><h2><a href="{base}/partituras/{group.key}/">{E(group.title)}</a></h2><p>{E(group.description)}</p><a class="text-link" href="{E(explore)}">Explorar {E(group.title)}</a></div></article>'

    categories = [g for key, g in catalog.groups.items() if '/' not in key]
    intro = f'<section class="category-page"><p class="eyebrow">A SUA ESTANTE MUSICAL</p><h1>Partituras para<br><em>ler, ouvir e tocar.</em></h1><p class="lead">Escolha uma categoria para encontrar os estudos e as coleções.</p><div class="cards score-categories">{"".join(group_card(g) for g in categories)}</div></section>'
    save('partituras', 'Partituras', intro)
    save('musica', 'Partituras', intro)
    for key, group in catalog.groups.items():
        parent = key.rsplit('/', 1)[0] if '/' in key else ''
        up = 'partituras/' + parent if parent else 'partituras'
        label = catalog.groups[parent].title if parent else 'Partituras'
        children = [g for k, g in catalog.groups.items() if k.startswith(key + '/') and k.count('/') == key.count('/') + 1]
        if key == 'hinos':
            order = {'hinos/bb': 0, 'hinos/eb': 1, 'hinos/do': 2, 'hinos/outros': 3}
            children.sort(key=lambda group: order.get(group.key, 4))
        scores = [s for s in catalog.scores if s.parent == key]
        content = f'<div class="cards score-categories">{"".join(group_card(g) for g in children)}</div>' if children else ''
        content += f'<div class="score-list">{"".join(score_card(s, base, catalog) for s in scores)}</div>'
        if not children and not scores:
            content += '<p class="catalog-empty">Ainda não há partituras publicadas nesta coleção.</p>'
        body = f'<section class="category-page"><a class="text-link" href="{base}/{up}/">{E(label)}</a><p class="eyebrow">ESTANTE DE PARTITURAS</p><h1>{E(group.title)}</h1><p class="lead">{E(group.description)}</p><div class="prose">{group.body.replace("{{BASE}}", base)}</div>{content}</section>'
        save('partituras/' + key, group.title, body)
        if key == 'msa':
            save('musica/msa', group.title, body)
    for score in catalog.scores:
        body = score_body(score, catalog, base)
        save(score.route, score.title, body)
        if score.legacy:
            save(score.legacy, score.title, body)
