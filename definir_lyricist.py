#!/usr/bin/env python3
"""Define o crédito de cifras em um .mscz dentro do diretório informado.

Uso: python3 definir_lyricist.py /caminho/para/hino-1
Não cria backup; substitui o arquivo original após verificar o ZIP gerado.
"""

import argparse
import base64
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

CREDITO = "Cifra: Djames Suhanko"
ESTILOS_LETRISTA = {"poet", "lyricist", "Lyricist"}


def versao(texto):
    numeros = [int(n) for n in re.findall(r"\d+", texto or "")[:3]]
    return tuple((numeros + [0, 0, 0])[:3])


def novo_eid():
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")


def inserir_credito(xml_original):
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    raiz = ET.fromstring(xml_original, parser=parser)
    if raiz.tag != "museScore":
        raise ValueError("XML não parece ser uma partitura nativa do MuseScore.")
    score = raiz.find("Score")
    if score is None:
        raise ValueError("Elemento <Score> não encontrado.")

    programa = raiz.findtext("programVersion", default="")
    recente = versao(raiz.get("version", "")) >= (4, 7, 0) or versao(programa) >= (4, 6, 5)
    estilo = "poet" if recente else "lyricist"

    # Metadado exibido em Arquivo > Propriedades do projeto.
    tags = [t for t in score.findall("metaTag") if t.get("name") == "lyricist"]
    if len(tags) > 1:
        raise ValueError("Foram encontrados vários metadados lyricist; arquivo não modificado.")
    if tags:
        tag = tags[0]
        tag.text = CREDITO
    else:
        tag = ET.Element("metaTag", {"name": "lyricist"})
        tag.text = CREDITO
        filhos = list(score)
        pos = next((i for i, el in enumerate(filhos) if el.tag == "Staff"), len(filhos))
        score.insert(pos, tag)

    # O letreiro visível fica na primeira VBox da primeira pauta, antes do primeiro compasso.
    pautas = score.findall("Staff")
    pauta = next((p for p in pautas if p.get("id") == "1"), pautas[0] if pautas else None)
    if pauta is None:
        raise ValueError("Primeira pauta <Staff> não encontrada.")
    filhos = list(pauta)
    primeiro_compasso = next((i for i, el in enumerate(filhos) if el.tag == "Measure"), len(filhos))
    caixas = [el for el in filhos[:primeiro_compasso] if el.tag == "VBox"]
    if caixas:
        caixa = caixas[0]
    else:
        caixa = ET.Element("VBox")
        ET.SubElement(caixa, "height").text = "10"
        if score.find(".//eid") is not None:
            ET.SubElement(caixa, "eid").text = novo_eid()
        pauta.insert(0, caixa)

    creditos_visuais = [t for t in caixa.findall("Text") if t.findtext("style", default="") in ESTILOS_LETRISTA]
    if len(creditos_visuais) > 1:
        raise ValueError("Há vários textos Lyricist no quadro inicial; arquivo não modificado.")
    if creditos_visuais:
        texto_bloco = creditos_visuais[0]
    else:
        texto_bloco = ET.Element("Text")
        if score.find(".//eid") is not None:
            ET.SubElement(texto_bloco, "eid").text = novo_eid()
        ET.SubElement(texto_bloco, "style").text = estilo
        caixa.append(texto_bloco)

    # Atualiza o estilo antigo somente quando o formato for recente.
    estilo_elemento = texto_bloco.find("style")
    if estilo_elemento is None:
        estilo_elemento = ET.SubElement(texto_bloco, "style")
    estilo_elemento.text = estilo
    conteudo = texto_bloco.find("text")
    if conteudo is None:
        conteudo = ET.SubElement(texto_bloco, "text")
    for filho in list(conteudo):
        conteudo.remove(filho)
    conteudo.text = CREDITO

    novo_xml = ET.tostring(raiz, encoding="utf-8", xml_declaration=True)
    # Não muda o arquivo se ambas as informações já estavam corretas.
    return novo_xml


def processar(diretorio):
    if not diretorio.is_dir():
        raise ValueError(f"Diretório inexistente: {diretorio}")
    arquivos = sorted(p for p in diretorio.iterdir() if p.is_file() and p.suffix.lower() == ".mscz")
    if len(arquivos) != 1:
        raise ValueError(f"Esperado exatamente 1 arquivo .mscz em {diretorio}; encontrados {len(arquivos)}.")
    arquivo = arquivos[0]

    with ZipFile(arquivo, "r") as origem:
        nomes = [info.filename for info in origem.infolist() if info.filename.lower().endswith(".mscx")]
        if len(nomes) != 1:
            raise ValueError(f"Esperado exatamente 1 XML .mscx dentro de {arquivo.name}; encontrados {len(nomes)}.")
        nome_xml = nomes[0]
        xml_original = origem.read(nome_xml)
        xml_novo = inserir_credito(xml_original)
        # Evita regravar se não houve alteração semântica.
        if xml_original == xml_novo:
            print(f"Sem alterações: {arquivo}")
            return

        # Arquivo temporário é apenas para gravação atômica: NÃO é backup.
        fd, temp_nome = tempfile.mkstemp(prefix=".lyricist-", suffix=".tmp", dir=diretorio)
        os.close(fd)
        temporario = Path(temp_nome)
        try:
            with ZipFile(temporario, "w") as destino:
                destino.comment = origem.comment
                for item in origem.infolist():
                    dados = xml_novo if item.filename == nome_xml else origem.read(item)
                    destino.writestr(item, dados)
            with ZipFile(temporario, "r") as conferido:
                problema = conferido.testzip()
                if problema:
                    raise ValueError(f"ZIP gerado falhou na verificação: {problema}")
                raiz_conf = ET.fromstring(conferido.read(nome_xml))
                score_conf = raiz_conf.find("Score")
                if score_conf is None or not any(
                    t.get("name") == "lyricist" and t.text == CREDITO
                    for t in score_conf.findall("metaTag")
                ):
                    raise ValueError("Falha ao validar o metadado gravado.")
            os.chmod(temporario, stat.S_IMODE(arquivo.stat().st_mode))
            os.replace(temporario, arquivo)
        finally:
            temporario.unlink(missing_ok=True)

    print(f"Atualizado: {arquivo}")
    print(f"Lyricist: {CREDITO}")


def main():
    parser = argparse.ArgumentParser(description="Define o campo Lyricist em um único arquivo .mscz dentro de um diretório (sem backup).")
    parser.add_argument("diretorio", type=Path, help="Diretório do hino ou coro, contendo um único .mscz")
    args = parser.parse_args()
    try:
        processar(args.diretorio.expanduser().resolve())
    except (OSError, ValueError, ET.ParseError, BadZipFile) as erro:
        parser.exit(1, f"Erro: {erro}\n")


if __name__ == "__main__":
    main()
