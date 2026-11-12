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
        for para in body.iter(f"{NS}p"):
            chunks = []
            for node in para.iter():
                if node.tag == f"{NS}t":
                    chunks.append(node.text or "")
                elif node.tag in (f"{NS}tab", f"{NS}br"):
                    chunks.append(" ")
            line = "".join(chunks).strip()
            if line:
                rows.append(line)
        text = "\n".join(rows) + "\n"
        return text, len(rows), len(body.findall(f".//{NS}tbl"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_zip", type=Path)
    ap.add_argument("part", type=Path)
    ap.add_argument("--pid-log", type=Path)
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
    args.part.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.part.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.part)
    print(f"Treaty: {para_count} nonempty paragraphs, {table_count} table, {len(text)} characters")


if __name__ == "__main__":
    main()
