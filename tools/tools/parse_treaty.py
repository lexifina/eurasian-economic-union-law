"""Parse the official Russian Word Treaty member from its official attachment ZIP."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PAGE = "https://docs.eaeunion.org/docs/ru-ru/0053610/itia_05062014"
ZIP_URL = "https://docs.eaeunion.org/upload/iblock/e6e/08na98hg7eon2u3d6rmjkpqjedfn502r/itia_05062014_att.zip"


def value(element, name, default=None):
    child = element.find(f"{NS}{name}") if element is not None else None
    return child.get(f"{NS}val", default) if child is not None else default


def format_counter(number: int, fmt: str) -> str:
    if fmt == "decimal":
        return str(number)
    if fmt == "decimalZero":
        return f"{number:02d}"
    if fmt in ("lowerLetter", "upperLetter"):
        if number < 1:
            raise ValueError('nonpositive alphabetic Word counter requires handling')
        result = ""
        while number:
            number, rem = divmod(number - 1, 26)
            result = chr(65 + rem) + result
        return result.lower() if fmt == "lowerLetter" else result
    if fmt in ("lowerRoman", "upperRoman"):
        if not 1 <= number <= 3999:
            raise ValueError('Roman Word counter outside 1..3999 requires handling')
        result = ""
        for amount, letters in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                                (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                                (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
            count, number = divmod(number, amount)
            result += letters * count
        return result.lower() if fmt == "lowerRoman" else result
    raise ValueError(f"unsupported Word numbering format: {fmt}")


class Numbering:
    """Render source OOXML lists, including starts, overrides and level restarts."""

    def __init__(self, archive):
        root = ET.fromstring(archive.read("word/numbering.xml"))
        abstracts = {a.get(f"{NS}abstractNumId"): a for a in root.findall(f"{NS}abstractNum")}
        self.levels = {}
        for num in root.findall(f"{NS}num"):
            num_id = num.get(f"{NS}numId")
            abstract = abstracts[value(num, "abstractNumId")]
            if abstract.find(f"{NS}numStyleLink") is not None:
                raise ValueError("numbering style link requires explicit resolution")
            levels = {int(l.get(f"{NS}ilvl")): dict(
                start=int(value(l, "start", "1")), fmt=value(l, "numFmt", "decimal"),
                text=value(l, "lvlText", ""), restart=int(value(l, "lvlRestart", str(int(l.get(f"{NS}ilvl"))))),
                legal=l.find(f"{NS}isLgl") is not None,
            ) for l in abstract.findall(f"{NS}lvl")}
            for override in num.findall(f"{NS}lvlOverride"):
                index = int(override.get(f"{NS}ilvl"))
                lvl = override.find(f"{NS}lvl")
                if lvl is not None:
                    levels[index] = dict(start=int(value(lvl, "start", "1")),
                        fmt=value(lvl, "numFmt", "decimal"), text=value(lvl, "lvlText", ""),
                        restart=int(value(lvl, "lvlRestart", str(index))), legal=lvl.find(f"{NS}isLgl") is not None)
                start = value(override, "startOverride")
                if start is not None:
                    levels[index]["start"] = int(start)
            self.levels[num_id] = levels
        self.counters = {}
        self.styles = {}
        if "word/styles.xml" in archive.namelist():
            styles = ET.fromstring(archive.read("word/styles.xml"))
            self.styles = {s.get(f"{NS}styleId"): s for s in styles.findall(f"{NS}style")}

    def paragraph_numbering(self, paragraph):
        props = paragraph.find(f"{NS}pPr")
        direct = props.find(f"{NS}numPr") if props is not None else None
        num_id, level = value(direct, "numId"), value(direct, "ilvl")
        style_id = value(props, "pStyle")
        seen = set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            style = self.styles.get(style_id)
            if style is None:
                break
            inherited = style.find(f"{NS}pPr/{NS}numPr")
            if num_id is None:
                num_id = value(inherited, "numId")
            if level is None:
                level = value(inherited, "ilvl")
            style_id = value(style, "basedOn")
        if num_id in (None, "0"):
            return None
        return num_id, int(level or 0)

    def label(self, paragraph):
        numbering = self.paragraph_numbering(paragraph)
        if numbering is None:
            return ""
        num_id, level = numbering
        definitions = self.levels[num_id]
        current = definitions[level]
        state = self.counters.setdefault(num_id, {})
        state[level] = state[level] + 1 if level in state else current['start']
        for deeper in list(state):
            restart = definitions[deeper]['restart']
            if deeper > level and restart != 0 and level <= restart - 1:
                del state[deeper]
        if current['fmt'] == 'none':
            return ""
        if current['fmt'] == 'bullet':
            if any(0xE000 <= ord(c) <= 0xF8FF for c in current['text']):
                raise ValueError('font-encoded Word bullet requires an independent glyph mapping')
            return current['text']
        def replace(match):
            index = int(match.group(1)) - 1
            definition = definitions[index]
            return format_counter(state.get(index, definition['start']),
                                  'decimal' if current['legal'] else definition['fmt'])
        return re.sub(r'%([1-9])', replace, current['text'])


def paragraphs(docx: bytes) -> tuple[str, int, int]:
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        body = root.find(f"{NS}body")
        if body is None:
            raise ValueError("Word body missing")
        media = [n for n in z.namelist() if n.startswith("word/media/")]
        if media:
            raise ValueError(f"Treaty Word document contains {len(media)} images")
        for part in ("word/footnotes.xml", "word/endnotes.xml"):
            if part in z.namelist() and any((t.text or "").strip() for t in ET.fromstring(z.read(part)).iter(f"{NS}t")):
                raise ValueError(f"nonempty {part} needs handling")
        rows = []
        numbering = Numbering(z)
        def paragraph(para):
            chunks = []
            for node in para.iter():
                if node.tag == f"{NS}t":
                    chunks.append(node.text or "")
                elif node.tag in (f"{NS}tab", f"{NS}br"):
                    chunks.append(" ")
            line = "".join(chunks).strip()
            label = numbering.label(para)
            if line or label:
                return f"{label} {line}".strip() if label else line
            return ''
        para_count=0
        import html
        for child in body:
            if child.tag==NS+'p':
                line=paragraph(child)
                if line:rows.append(line);para_count+=1
            elif child.tag==NS+'tbl':
                if len(list(child.iter(NS+'tbl')))!=1 or child.find('.//'+NS+'vMerge') is not None:
                    raise ValueError('Treaty table grid needs separate handling')
                rows.append('<table>')
                for row in child.findall(NS+'tr'):
                    rows.append('<tr>')
                    for cell in row.findall(NS+'tc'):
                        span=cell.find(NS+'tcPr/'+NS+'gridSpan')
                        attr=f' colspan="{int(span.get(NS+"val"))}"' if span is not None else ''
                        rows.append('<td'+attr+'>')
                        for para in cell.findall(NS+'p'):
                            line=paragraph(para)
                            if line:rows.append('<p>'+html.escape(line)+'</p>');para_count+=1
                        rows.append('</td>')
                    rows.append('</tr>')
                rows.append('</table>')
            elif child.tag!=NS+'sectPr':raise ValueError('Unsupported Treaty body node '+child.tag)
        text = "\n".join(rows) + "\n"
        return text, para_count, len(body.findall(f".//{NS}tbl"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_zip", type=Path)
    ap.add_argument("part", type=Path)
    ap.add_argument("--pid-log", type=Path)
    ap.add_argument("--corrects", help="Exact earlier part filename replaced by this new part")
    args = ap.parse_args()
    if args.pid_log:
        with args.pid_log.open("a", encoding="utf-8") as f:
            f.write(str(os.getpid()) + "\n")
    if os.name == "nt":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    raw = args.source_zip.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        members = [x for x in outer.infolist() if x.filename.lower().endswith(".docx")]
        if len(members) != 2:
            raise ValueError(f"expected two Word files, found {len(members)}")
        small = min(members, key=lambda x: x.file_size)
        text, para_count, table_count = paragraphs(outer.read(small))
    if re.sub(r"\s+", " ", text.splitlines()[0]).strip() != "ДОГОВОР О ЕВРАЗИЙСКОМ ЭКОНОМИЧЕСКОМ СОЮЗЕ":
        raise ValueError("unexpected Treaty opening")
    if len(text) < 180_000:
        raise ValueError("Treaty text unexpectedly short")
    part = {
        "country": {
            "code": "EAEU", "name": "Eurasian Economic Union", "slug": "eurasian-economic-union",
            "lang": "ru", "tz": "Europe/Moscow", "future_branch": "futuro",
            "publisher": {"name": "Евразийский экономический союз", "email": "publisher@eaeu.invalid"},
            "default_in_force_rule": {"text": "Entry into force is taken from each document's own portal metadata.", "source": PAGE},
            "licence_note": "The portal displays © Евразийский экономический союз, 2026; no text licence was stated on the document page."
        },
        "sources": [{"name": "Правовой портал Евразийского экономического союза", "url": PAGE,
                     "retrieved": "2026-11-12", "licence": "No express text licence stated on the page; © Евразийский экономический союз, 2026.",
                     "notes": "Signed Treaty and Word attachment."}],
        "laws": {"dogovor-2014-05-29": {"label": "Договор о Евразийском экономическом союзе от 29 мая 2014 года",
                  "title": "Договор о Евразийском экономическом союзе", "kind": "treaty",
                  "enacted": "2014-05-29", "published": "2014-06-05", "url": PAGE}},
        "acts": [{"slug": "dogovor-o-evraziyskom-ekonomicheskom-soyuze", "short": "Договор о ЕАЭС",
                  "title": "Договор о Евразийском экономическом союзе", "url": PAGE,
                  "first_law": "dogovor-2014-05-29", "earlier_laws": [],
                  "versions": [{"from": "2015-01-01", "source_url": ZIP_URL,
                                "sha256": hashlib.sha256(raw).hexdigest(),
                                "source_images": 0,
                                "units": {"tekst-dogovora": {"label": "Текст Договора", "kind": "text", "text": text}},
                                "credits": {}, "note": "Signed Treaty text; annexes are held for a separate completeness check."}]}],
        "applies": [],
        "decisions": ["The official portal states 29 May 2014 adoption, 5 June 2014 publication and 1 January 2015 entry into force.",
                      "The Word member in the portal's Russian attachment ZIP is the signed Treaty, not a later consolidation.",
                      "Annexes and later amending protocols are not claimed as part of this checked version."],
        "ai_use": ["A model wrote parsing code and metadata; legal words came only from the official Word file."]
    }
    if args.corrects:
        part['corrects'] = args.corrects
        part['acts'][0]['versions'][0]['correction'] = {
            'reason': 'Restore automatic paragraph labels from the official Word numbering definitions.',
            'in_force_basis': 'Official portal document metadata states entry into force on 1 January 2015.',
        }
        part['decisions'].append('Automatic list labels are rendered from the official numbering.xml; legal wording is unchanged.')
    args.part.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.part.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.part)
    print(f"Treaty: {para_count} nonempty paragraphs, {table_count} table, {len(text)} characters")


if __name__ == "__main__":
    main()
