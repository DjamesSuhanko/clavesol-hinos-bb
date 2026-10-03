# Clave Sol — Hinário Bb

241 partituras já aferidas, com os arquivos originais SVG, MusicXML e MuseScore, player e cursor sincronizado. Não há exportação PDF.

## Ativar o GitHub Pages

1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Deixe Custom domain vazio.
3. Actions → **Publicar hinário** → Run workflow → main → Run workflow.
4. Aguarde o workflow concluir. Endereço: https://djamessuhanko.github.io/clavesol-hinos-bb/

O primeiro commit usa `[skip ci]` para aguardar essa configuração. Os próximos pushes em main publicam automaticamente.

## Desenvolvimento

Requer Python 3.12 ou superior.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build.py
BASE_PATH=/clavesol-hinos-bb .venv/bin/python scripts/check_links.py
```

Para prévia na raiz local: `BASE_PATH= .venv/bin/python build.py`, seguido de `python3 -m http.server 8000 --directory dist`.

## Adicionar uma partitura

Com MuseScore instalado, use neste repositório:

```bash
.venv/bin/python criar_licao.py '/caminho/completo/Hino.mscz' --hinos --hinario bb
```

Confira o resultado local antes de fazer commit e push. Não altere a coleção em `hinario.json`: cada repositório contém apenas seu próprio hinário. Os links de navegação retornam ao blog principal. Aparência e player são cópias da versão validada do Clave Sol; alterações futuras nesses componentes devem ser aplicadas aos três repositórios.
