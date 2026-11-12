"""Preserve official Word HTML paragraphs and table geometry; prove source words."""
import re
from bs4 import BeautifulSoup,Comment
from lxml import html as LH

def words(blob):
    tree=LH.fromstring(blob)
    bodies=tree.xpath('//body');start=bodies[0] if bodies else tree
    for n in start.xpath('.//script|.//style'):n.drop_tree()
    chunks=[];blocks={'p','div','table','tr','td','th','br','li','h1','h2','h3'}
    def walk(node):
        if not isinstance(node.tag,str):return
        if node.tag.lower() in blocks:chunks.append(' ')
        if node.text:chunks.append(node.text)
        for child in node:
            walk(child)
            if child.tail:chunks.append(child.tail)
        if node.tag.lower() in blocks:chunks.append(' ')
    walk(start)
    return ''.join(chunks).split()

def extract(raw):
    soup=BeautifulSoup(raw,'html.parser')
    if not soup.body:raise ValueError('official HTML has no body')
    body=soup.body
    if body.find_all(['img','svg','canvas','object','embed','v:shape','v:group']) or re.search(br'<(?:img|svg|canvas|object|embed|v:imagedata|v:shape|v:group)\b',raw,re.I):
        raise ValueError('images deferred: HTML image markup')
    if body.find(['ol','ul']):raise ValueError('HTML automatic lists require handling')
    for node in body.find_all(['script','style']):node.decompose()
    for node in body.find_all(string=lambda n:isinstance(n,Comment)):node.extract()
    for node in list(body.find_all(True)):
        style=node.get('style','')
        face=node.get('face','')
        if re.search(r'(?:symbol|wingdings|webdings)',style+' '+face,re.I):
            raise ValueError('font-encoded HTML glyph requires an independent mapping')
        if node.name in ('font','span'):
            semantic=[]
            if re.search(r'(?:text-decoration|mso-text-decoration).*?line-through',style,re.I):semantic.append('s')
            if re.search(r'vertical-align\s*:\s*super',style,re.I):semantic.append('sup')
            if re.search(r'vertical-align\s*:\s*sub',style,re.I):semantic.append('sub')
            if semantic:
                for tag in semantic:
                    wrapper=soup.new_tag(tag)
                    for child in list(node.contents):wrapper.append(child.extract())
                    node.append(wrapper)
            node.unwrap();continue
        node.attrs={k:v for k,v in node.attrs.items() if k in ('colspan','rowspan','href','name','id')}
    text=body.decode_contents().replace('\r\n','\n').replace('\r','\n').strip().replace('</p>','</p>\n')+'\n'
    expected=words(raw);actual=words(text)
    if expected!=actual:
        raise ValueError(f'independent HTML words differ: {len(expected)} vs {len(actual)}')
    return text,{'source_images':0,'tables':len(body.find_all('table')),'numbered_paragraphs':0}, {
        'source_tokens':len(expected),'output_tokens':len(actual),'word_sequence_equal':True}
