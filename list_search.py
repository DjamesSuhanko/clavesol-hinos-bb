"""Search controls for card listings; leaves articles and player pages untouched."""
import re


def add_search(body, base):
    if 'data-list-search' in body or 'class="category-page"' not in body:
        return body
    if not re.search(r'class="(?:card|score-card)"', body):
        return body
    controls='''<div class="list-search" data-list-search hidden><label for="list-search-input">Buscar nesta página</label><div class="list-search-row"><input id="list-search-input" type="search" placeholder="Número, título ou palavra-chave" autocomplete="off"><button type="button" id="list-search-clear">Limpar busca</button></div><p id="list-search-count" role="status" aria-live="polite" aria-atomic="true"></p></div><p id="list-search-empty" hidden>Nenhum resultado. Tente outro número ou parte do título.</p>'''
    body=re.sub(r'(<p class="lead">.*?</p>)',lambda m:m[0]+controls,body,count=1,flags=re.S)
    return f'<link rel="stylesheet" href="{base}/assets/list-search.css">'+body+f'<script type="module" src="{base}/assets/list-search.mjs"></script>'
