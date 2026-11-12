"""Extract official Word text and retain list labels and table cell boundaries."""
import html,io,re,zipfile
from xml.etree import ElementTree as E
from parse_treaty import Numbering, NS

def clean(text):
    return re.sub(r'\s+', ' ', text).strip()

def extract(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        media=[n for n in z.namelist() if n.startswith('word/media/')]
        if media:raise ValueError(f'images deferred: {len(media)} media files')
        root=E.fromstring(z.read('word/document.xml'))
        image_nodes=[n for n in root.iter() if n.tag.endswith('}blip') or n.tag.endswith('}imagedata')]
        graphics=[n for n in root.iter() if n.tag in (NS+'drawing',NS+'pict',NS+'object')]
        if media or image_nodes or graphics:
            raise ValueError(f'images deferred: {len(image_nodes)} source occurrences, {len(media)} media files')
        active_runs=[r for r in root.iter(NS+'r') if ''.join(t.text or '' for t in r.iter(NS+'t')).strip()]
        if any(re.search(r'Symbol|Wingdings|Webdings',' '.join(n.attrib.values()),re.I) for r in active_runs for n in r.findall(NS+'rPr/'+NS+'rFonts')):
            raise ValueError('font-encoded Word glyph requires an independent mapping')
        if any(n.tag in (NS+'strike',NS+'dstrike') and n.get(NS+'val','1') not in ('0','false','off') for r in active_runs for n in r.findall(NS+'rPr/*')):
            raise ValueError('Word strikethrough requires semantic-format preservation')
        if any(n.tag==NS+'vertAlign' and n.get(NS+'val') in ('superscript','subscript') for r in active_runs for n in r.findall(NS+'rPr/*')):
            raise ValueError('Word superscript/subscript requires semantic-format preservation')
        if any(n.tag.endswith('}oMath') for n in root.iter()):
            raise ValueError('OOXML equation requires a separate verified extractor')
        for name in ('word/footnotes.xml','word/endnotes.xml'):
            if name in z.namelist() and any((t.text or '').strip() for t in E.fromstring(z.read(name)).iter(NS+'t')):
                raise ValueError(f'nonempty {name} requires reference preservation')
        for name in z.namelist():
            if re.fullmatch(r'word/(header|footer)\d+\.xml',name):
                text=clean(' '.join(t.text or '' for t in E.fromstring(z.read(name)).iter(NS+'t')))
                if text and not re.fullmatch(r'\d+',text):
                    raise ValueError(f'non-page-number {name} requires handling')
        numbering=Numbering(z) if 'word/numbering.xml' in z.namelist() else None
        numbered=0
        def paragraph(p):
            nonlocal numbered
            chunks=[]
            for node in p.iter():
                if node.tag==NS+'t': chunks.append(node.text or '')
                elif node.tag in (NS+'tab',NS+'br'): chunks.append(' ')
                elif node.tag==NS+'sym': raise ValueError('font-encoded symbol requires an independent mapping')
            text=clean(''.join(chunks))
            label=numbering.label(p) if numbering else ''
            if label: numbered+=1
            return (label+' '+text).strip() if text or label else ''
        lines=[]
        body=root.find(NS+'body')
        tables=0
        for child in body:
            if child.tag==NS+'p':
                text=paragraph(child)
                if text: lines.append(text)
            elif child.tag==NS+'tbl':
                if len(list(child.iter(NS+'tbl')))!=1: raise ValueError('nested table requires handling')
                # Keep the original physical cells and OOXML horizontal spans.
                # Vertical merges need a separate grid proof and remain held.
                if child.find('.//'+NS+'vMerge') is not None:
                    raise ValueError('vertically merged table cells require handling')
                if child.find('.//'+NS+'gridSpan') is not None:
                    tables+=1;lines.append('<table>')
                    for row in child.findall(NS+'tr'):
                        lines.append('<tr>')
                        for cell in row.findall(NS+'tc'):
                            span=cell.find(NS+'tcPr/'+NS+'gridSpan')
                            attr=f' colspan="{int(span.get(NS+"val"))}"' if span is not None else ''
                            lines.append('<td'+attr+'>')
                            for p in cell.findall(NS+'p'):
                                line=paragraph(p)
                                if line:lines.append('<p>'+html.escape(line)+'</p>')
                            lines.append('</td>')
                        lines.append('</tr>')
                    lines.append('</table>');continue
                matrix=[]
                for row in child.findall(NS+'tr'):
                    cells=[]
                    for cell in row.findall(NS+'tc'):
                        parts=[paragraph(p) for p in cell.findall(NS+'p')]
                        cells.append('<br>'.join(t for t in parts if t).replace('|','&#124;'))
                    matrix.append(cells)
                width=max((len(row) for row in matrix),default=0)
                if width:
                    tables+=1
                    for index,row in enumerate(matrix):
                        lines.append('| '+' | '.join(row+['']*(width-len(row)))+' |')
                        if index==0: lines.append('| '+' | '.join(['---']*width)+' |')
            elif child.tag==NS+'sectPr': pass
            else: raise ValueError(f'unhandled Word body element: {child.tag}')
        text='\n'.join(lines)+'\n'
        # The OOXML proof is separate and supplies the independent expected text.
        return text, {'numbered_paragraphs':numbered,'source_images':0,'tables':tables}
