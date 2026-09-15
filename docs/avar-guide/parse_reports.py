#!/usr/bin/env python3
"""
parse_reports.py — משחזר נתוני סשן מלאים מתוך דו"ח AVAR שיוצא כ-HTML
Reconstructs a full AVAR session object from an exported report HTML file,
reversing the markup that src/frontend/utils/exportHtml.js produces.
"""
import sys, os, re, json, datetime
import lxml.html as LH

# ─── inline markup → markdown ────────────────────────────────────────────────

def inline_md(el):
    """Reverse inlineHtml(): <strong> → **x**, <a href> (+ tier badge) → [x](url)."""
    out = []

    def walk(node, in_link=False):
        if node.tag == 'strong':
            out.append('**' + (node.text_content() or '') + '**')
            if node.tail: out.append(node.tail)
            return
        if node.tag == 'a':
            href = node.get('href', '')
            text = node.text_content() or href
            out.append(f'[{text}]({href})' if text != href else href)
            if node.tail: out.append(node.tail)
            return
        if node.tag == 'span' and re.match(r'^T[123]$', (node.text_content() or '').strip()):
            # tier badge emitted next to a link — drop it, the URL carries the tier
            if node.tail: out.append(node.tail)
            return
        if node.text: out.append(node.text)
        for ch in node:
            walk(ch)
        if node.tail and not in_link: out.append(node.tail)

    if el.text: out.append(el.text)
    for ch in el:
        walk(ch)
    return re.sub(r'[ \t]+', ' ', ''.join(out)).strip()


def block_md(container):
    """Reverse mdToHtml(): rebuild the markdown of one rendered section."""
    lines = []
    for el in container:
        style = el.get('style', '') or ''
        if el.tag == 'h3':
            lines.append('### ' + inline_md(el))
        elif el.tag == 'h2':
            lines.append('## ' + inline_md(el))
        elif el.tag == 'hr':
            lines.append('---')
        elif el.tag == 'div' and 'height:0.4em' in style:
            lines.append('')
        elif el.tag == 'div' and 'display:flex' in style:
            spans = el.findall('span')
            if len(spans) >= 2:
                marker = (spans[0].text_content() or '').strip()
                body = inline_md(spans[1])
                lines.append(f'- {body}' if marker == '•' else f'{marker} {body}')
            else:
                lines.append(inline_md(el))
        elif el.tag == 'p':
            lines.append(inline_md(el))
        elif el.tag == 'pre':
            lines.append(el.text_content())
        else:
            txt = inline_md(el)
            if txt: lines.append(txt)
    return '\n'.join(lines).strip()


# ─── badge readers ───────────────────────────────────────────────────────────

LEVEL = {'גבוה': 'high', 'בינוני': 'medium', 'נמוך': 'low'}

def level_after(text, prefix):
    m = re.search(re.escape(prefix) + r'\s*(גבוה|בינוני|נמוך)', text)
    return LEVEL.get(m.group(1)) if m else None


# ─── section extraction ──────────────────────────────────────────────────────

def sections_of(doc):
    """Map each <details> section title → its content element."""
    out = {}
    for det in doc.xpath('//div[@class="container"]/details'):
        summary = det.find('summary')
        name = summary.findtext('span', '').strip() if summary is not None else ''
        body = det.xpath('./div')
        if name and body:
            out[name] = body[0]
    return out


def parse_claims(el):
    """Rebuild analysis.keyClaims and analysis.assumptions from the claims section."""
    claims, assumptions = [], []
    for i, card in enumerate(el.xpath('./div[contains(@style,"border-radius:10px")]')):
        rows = card.xpath('./div')
        is_assumption = 'fde68a' in (card.get('style') or '')
        if is_assumption:
            head = rows[0]
            badges = head.text_content()
            a = {
                'text': (head.findtext('p') or '').strip(),
                'type': 'implicit' if 'סמויה' in badges else 'explicit',
                'riskIfWrong': level_after(badges, 'סיכון אם שגוי:') or 'low',
            }
            if len(rows) > 1:
                ps = rows[1].findall('p')
                if len(ps) > 1: a['riskReasoning'] = (ps[1].text_content() or '').strip()
            assumptions.append(a)
            continue

        c = {'id': f'claim-{i+1}', 'text': (rows[0].findtext('p') or '').strip(),
             'confidence': 'low', 'sourceCount': 0, 'sourceRefs': []}
        for row in rows[1:]:
            txt = row.text_content()
            if 'ביטחון:' in txt:
                c['confidence'] = level_after(txt, 'ביטחון:') or 'low'
                m = re.search(r'(\d+)\s*מקורות', txt)
                if m: c['sourceCount'] = int(m.group(1))
                ps = row.findall('p')
                if ps: c['confidenceReasoning'] = (ps[-1].text_content() or '').strip()
            elif 'סיכון אם שגוי:' in txt:
                c['riskIfWrong'] = level_after(txt, 'סיכון אם שגוי:') or 'low'
                ps = row.findall('p')
                if ps: c['riskReasoning'] = (ps[-1].text_content() or '').strip()
            elif 'מקורות ועדויות' in txt:
                for li in row.xpath('.//li'):
                    spans = li.findall('span')
                    c['sourceRefs'].append(inline_md(spans[-1]) if spans else li.text_content().strip())
        claims.append(c)
    return claims, assumptions


def parse_entities(el):
    """Rebuild analysis.entities from the entities section."""
    keys = {'אנשים': ('persons', 'role'), 'ארגונים': ('organizations', 'type'),
            'מיקומים': ('locations', 'type'), 'אירועים': ('events', None)}
    ents = {}
    for group in el.xpath('./div'):
        h3 = group.findtext('h3', '').strip()
        if h3 not in keys: continue
        key, sub = keys[h3]
        items = []
        for chip in group.xpath('./div/div'):
            spans = chip.findall('span')
            if not spans: continue
            name = (spans[0].text_content() or '').strip()
            rel = LEVEL.get((spans[-1].text_content() or '').strip(), 'low')
            item = {'relevance': rel}
            if key == 'events':
                item['description'] = name
                if len(spans) > 2: item['date'] = (spans[1].text_content() or '').strip()
            else:
                item['name'] = name
                if sub and len(spans) > 2: item[sub] = (spans[1].text_content() or '').strip()
            items.append(item)
        ents[key] = items
    return ents or None


def parse_strategic(el):
    """Rebuild strategicView from the strategic-view section."""
    if 'לא נבחנה ראייה אסטרטגית' in el.text_content():
        return None
    view = {'lenses': []}
    for box in el.xpath('./div'):
        style = box.get('style', '')
        if 'dbeafe' in style:  # big-picture callout
            ps = box.findall('p')
            if len(ps) > 1: view['bigPicture'] = (ps[1].text_content() or '').strip()
            continue
        head, body = box.xpath('./div')[:2]
        spans = head.findall('span')
        lens = {
            'title': (spans[0].text_content() or '').strip(),
            'likelihood': level_after(spans[1].text_content() if len(spans) > 1 else '', 'סבירות:') or 'medium',
            'indicators': [], 'scenarios': [],
        }
        mode = None
        for node in body:
            txt = (node.text_content() or '').strip()
            if node.tag == 'p':
                if txt.startswith('אינדיקטורים'): mode = 'ind'; continue
                if txt.startswith('תרחישים'): mode = 'sc'; continue
                if mode is None and 'assessment' not in lens: lens['assessment'] = txt
            elif node.tag == 'ul' and mode == 'ind':
                lens['indicators'] = [(li.text_content() or '').strip() for li in node.findall('li')]
            elif node.tag == 'div' and mode == 'sc':
                sc = {'worstCase': 'fca5a5' in (node.get('style') or ''), 'secondOrderEffects': []}
                ps = node.findall('p')
                if ps:
                    spans = ps[0].findall('span')
                    sc['title'] = (spans[-1].text_content() or '').strip() if spans else ''
                for sub in node[1:]:
                    st = (sub.text_content() or '').strip()
                    if sub.tag == 'p' and st.startswith('השלכות מסדר שני'): continue
                    if sub.tag == 'ul':
                        sc['secondOrderEffects'] = [(li.text_content() or '').strip() for li in sub.findall('li')]
                    elif sub.tag == 'p' and st.startswith('השלכה:'):
                        sc['implication'] = st[len('השלכה:'):].strip()
                    elif sub.tag == 'p' and 'description' not in sc:
                        sc['description'] = st
                lens['scenarios'].append(sc)
        view['lenses'].append(lens)
    return view if view['lenses'] else None


def parse_transparency(el):
    """Rebuild report metadata, telemetry, agentOutputs and the transparency log."""
    meta = {}
    # each label sits in its own <p>, so read them per-element — text_content()
    # of the whole block runs the lists together
    for para in el.xpath('./div[1]/p'):
        line = (para.text_content() or '').strip()
        for label, key in (('סוכנים שהופעלו:', 'agentsActivated'),
                           ('מיומנויות שהופעלו:', 'skillsActivated')):
            if line.startswith(label):
                vals = line[len(label):].strip()
                meta[key] = [v.strip() for v in vals.split(',') if v.strip() and v.strip() != '—']

    telemetry = None
    nums = el.xpath('.//div[contains(@style,"font-size:1.4em")]')
    if len(nums) >= 4:
        def n(v):
            v = (v or '').strip()
            return int(float(v[:-1]) * 1000) if v.endswith('K') else int(v or 0)
        telemetry = {
            'llmCalls': n(nums[0].text_content()),
            'inputTokens': n(nums[1].text_content()),
            'outputTokens': n(nums[2].text_content()),
            'searchCalls': n(nums[3].text_content()),
        }

    outputs = {}
    for i, det in enumerate(el.xpath('.//details')):
        summ = det.find('summary')
        spans = summ.findall('span')
        name = (spans[-1].text_content() or '').strip()
        skills = [(s.text_content() or '').strip() for s in summ.xpath('./div/span')]
        skills = [s for s in skills if s and s != 'ללא מיומנויות']
        pre = det.xpath('.//pre')
        aid = f'agent-{i+1}'
        outputs[aid] = {'agentId': aid, 'agentName': name, 'skills': skills,
                        'output': pre[0].text_content() if pre else ''}
    return meta, telemetry, outputs


def parse_audit(el):
    """Rebuild searchAudit from the audit section."""
    LANG = {'עב': 'he', 'EN': 'en', 'ER': 'ar'}
    audit = []
    base = datetime.datetime(2026, 1, 1, 9, 0, 0)
    for det in el.xpath('./details'):
        summ = det.find('summary')
        lang = LANG.get((summ.findtext('span') or '').strip(), 'en')
        inner = summ.find('div')
        query = (inner.findtext('p') or '').strip()
        meta_spans = inner.xpath('./div/span')
        agent = (meta_spans[0].text_content() or '').strip() if meta_spans else ''
        tail = inner.xpath('./div')[0].text_content()
        tm = re.search(r'(\d{1,2}:\d{2}:\d{2})', tail)
        cm = re.search(r'(\d+)\s*תוצאות', tail)
        ts = base
        if tm:
            hh, mm, ss = (int(x) for x in tm.group(1).split(':'))
            ts = base.replace(hour=hh, minute=mm, second=ss)
        results = []
        for card in det.xpath('./div/div'):
            a = card.find('.//a')
            if a is None: continue
            ps = card.findall('p')
            r = {'title': (a.text_content() or '').strip(), 'url': a.get('href', '')}
            tier = card.xpath('.//span[starts-with(text(),"T")]')
            if tier:
                tv = (tier[0].text_content() or 'T2').strip()
                r['sourceTier'] = int(tv[1]) if len(tv) > 1 and tv[1].isdigit() else 2
            texts = [(p.text_content() or '').strip() for p in ps]
            texts = [t for t in texts if t and not t.startswith('http')]
            if texts:
                if re.match(r'^\d{4}-\d{2}-\d{2}', texts[0]):
                    r['date'] = texts[0]
                    if len(texts) > 1: r['snippet'] = texts[1]
                else:
                    r['snippet'] = texts[0]
            results.append(r)
        audit.append({'agent': agent, 'lang': lang, 'query': query,
                      'count': int(cm.group(1)) if cm else len(results),
                      'results': results, 'ts': int(ts.timestamp() * 1000)})
    return audit


# ─── main ────────────────────────────────────────────────────────────────────

def parse_report(path, session_id):
    doc = LH.parse(path).getroot()
    title = doc.xpath('//div[@class="container"]/div[1]/h1')[0].text_content().strip()
    created_raw = doc.xpath('//div[@class="container"]/div[1]/div[last()]')[0].text_content()
    created = created_raw.replace('נוצר:', '').strip()

    sec = sections_of(doc)

    # report.content — rebuilt from the exported markdown sections
    parts = []
    if 'תמצית' in sec:
        parts.append(block_md(sec['תמצית']))
    for name, heading in [('עדויות סותרות', 'עדויות סותרות'),
                          ('חלופות', 'חלופות מדורגות'),
                          ('המלצות', 'המלצות')]:
        if name in sec:
            md = block_md(sec[name])
            if md and 'לא נמצאו' not in md[:40]:
                parts.append(f'## {heading}\n{md}')
    content = '\n\n'.join(p for p in parts if p)

    claims, assumptions = parse_claims(sec['טענות']) if 'טענות' in sec else ([], [])
    entities = parse_entities(sec['ישויות']) if 'ישויות' in sec else None
    strategic = parse_strategic(sec['ראייה אסטרטגית']) if 'ראייה אסטרטגית' in sec else None
    meta, telemetry, outputs = parse_transparency(sec['שקיפות']) if 'שקיפות' in sec else ({}, None, {})
    audit = parse_audit(sec['ביקורת חיפוש']) if 'ביקורת חיפוש' in sec else []

    doc_text = ''
    if 'מסמך מקורי' in sec:
        pre = sec['מסמך מקורי'].xpath('.//pre')
        if pre: doc_text = pre[0].text_content()

    # transparency log lives inside report.content for the app's שקיפות tab
    if 'שקיפות' in sec:
        tail = sec['שקיפות'].xpath('./div[last()]')
        if tail and 'border-top' in (tail[0].get('style') or ''):
            log = block_md(tail[0])
            if log: content += f'\n\n## לוג שקיפות\n{log}'

    # created is a he-IL locale string (d.m.yyyy, HH:MM:SS) — convert to ISO
    iso = None
    m = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4}),?\s*(\d{1,2}):(\d{2}):(\d{2})', created)
    if m:
        d, mo, y, hh, mm, ss = (int(x) for x in m.groups())
        iso = datetime.datetime(y, mo, d, hh, mm, ss).isoformat() + 'Z'
    iso = iso or datetime.datetime.utcnow().isoformat() + 'Z'

    return {
        'id': session_id,
        'title': title,
        'createdAt': iso,
        'completedAt': iso,
        'status': 'complete',
        'language': 'he',
        'wordCount': len(doc_text.split()) if doc_text else 0,
        'documentText': doc_text or None,
        'telemetry': telemetry,
        'searchAudit': audit,
        'report': {
            'content': content,
            'agentsActivated': meta.get('agentsActivated', []),
            'skillsActivated': meta.get('skillsActivated', []),
            'generatedAt': iso,
        },
        'analysis': {'keyClaims': claims, 'assumptions': assumptions, 'entities': entities},
        'agentOutputs': outputs,
        'strategicView': strategic,
        'events': [],
    }


if __name__ == '__main__':
    out = {}
    for path, sid in [(p, os.path.basename(p).split('-avar-report-')[1][:-5]) for p in sys.argv[2:]]:
        s = parse_report(path, sid)
        out[sid] = s
        print(f"{s['title'][:60]:62s} claims={len(s['analysis']['keyClaims'])} "
              f"assum={len(s['analysis']['assumptions'])} agents={len(s['agentOutputs'])} "
              f"audit={len(s['searchAudit'])} lenses={len((s['strategicView'] or {}).get('lenses', []))} "
              f"doc={len(s['documentText'] or '')} content={len(s['report']['content'])}")
    json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
    print('wrote', sys.argv[1])
