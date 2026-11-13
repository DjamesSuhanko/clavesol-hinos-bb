# Pacote para CantusCaeli

`build.py` chama `app_package.build_app_package` depois de gerar as partituras
e antes da finalização do site. O deploy existente publica o resultado em
`dist/downloads/cantuscaeli-bb.zip`.

Inclui somente sequence.json, timing.json, score.musicxml e score-N.svg de
cada hino/coro, mais manifest.json com formato, tonalidade, tamanhos e SHA-256.
Usa os arquivos finais de dist, incluindo as sequências geradas no build.
O manifesto permite ao aplicativo verificar integridade, coleção e páginas.
Os IDs vêm do catálogo; não há contagem de hinos fixa no gerador.

Falhas, arquivos ausentes e limites excedidos interrompem o build; um ZIP
parcial não é publicado. O ZIP usa nomes e timestamps estáveis. MSCZ e outros
arquivos do site não entram no pacote. Nenhum arquivo musical fonte é alterado.

Este build não foi executado nesta implementação, conforme orientação do
proprietário de reservar a validação funcional para si.
