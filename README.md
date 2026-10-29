# Clave Sol — Hinário Bb

486 partituras já aferidas, com os arquivos originais SVG, MusicXML e MuseScore, player e cursor sincronizado. Não há exportação PDF.

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


## Clave de Sol oitava abaixo nas vozes graves

As pautas anteriormente em clave de Fá usam agora a clave de Sol com o pequeno **8 abaixo**. A região escrita fica uma oitava acima, mas tenor e baixo continuam soando na altura anterior. A transposição do instrumento em Si♭ é preservada, assim como a pauta superior, as letras, as repetições e as introduções.

A alteração foi aplicada aos arquivos MuseScore (`score.mscz`) e MusicXML, com reexportação das páginas SVG e do cursor. No MusicXML, `clef-octave-change=-1` determina a posição gráfica; os valores de altura das notas permanecem iguais para conservar a reprodução. Não se deve aumentar também os valores de `pitch/octave`.

O script `scripts/treble_octave_below.py` reproduz a migração. Ele prepara os arquivos em uma pasta externa, compara a sequência completa de notas, tempos, fermatas, introdução e percurso do cursor, e verifica as letras antes de substituir os arquivos. Use `--apply` para aplicar; sem essa opção, apenas prepara e valida. Os arquivos anteriores são copiados para `backup/` dentro da pasta de preparação.

```bash
.venv/bin/python scripts/treble_octave_below.py --stage /caminho/fora/do/repositorio --jobs 4 --apply
```

A exportação usa o MuseScore instalado, com miniaturas em 72 dpi e páginas SVG vetoriais. O mapa do cursor é recalculado com a escala correspondente. Executar novamente sobre partituras já convertidas não modifica seus arquivos.
