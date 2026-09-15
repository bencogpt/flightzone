#!/usr/bin/env python3
"""
בונה מצגת HTML עצמאית (קובץ אחד) מתוך content.json + assets/
Builds a single self-contained HTML deck from content.json and the JPEG assets.
"""
import json, base64, html, os

BASE = os.path.dirname(os.path.abspath(__file__))
content = json.load(open(os.path.join(BASE, 'content.json'), encoding='utf-8'))

def img_data(name):
    """Embed a JPEG as a data: URI so the deck is one portable file."""
    p = os.path.join(BASE, 'assets', name)
    with open(p, 'rb') as f:
        return 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode('ascii')

e = html.escape
meta = content['meta']
slides = []

# ── Slide 1: title ───────────────────────────────────────────────────────────
slides.append(f'''<section class="slide slide-title">
  <div class="title-wrap">
    <div class="logo">AVAR</div>
    <div class="logo-sub">{e(meta["productFull"])}</div>
    <h1>{e(meta["title"].split("—")[1].strip())}</h1>
    <p class="lede">{e(meta["subtitle"])}</p>
    <p class="audience">{e(meta["audience"])}</p>
  </div>
</section>''')

# ── Slide 2: table of contents ───────────────────────────────────────────────
toc_items = ''.join(
    f'<li><span class="toc-n">{i+1:02d}</span><span class="toc-k">{e(s["kicker"])}</span>'
    f'<span class="toc-t">{e(s["title"])}</span></li>'
    for i, s in enumerate(content['sections'])
)
slides.append(f'''<section class="slide slide-toc">
  <h2 class="sec-title">מה יש במדריך</h2>
  <ol class="toc">{toc_items}</ol>
</section>''')

# ── Content slides ───────────────────────────────────────────────────────────
for s in content['sections']:
    kicker = e(s['kicker'])
    title = e(s['title'])

    if 'steps' in s:  # pipeline slide — numbered cards, no screenshot
        cards = ''.join(
            f'<div class="step"><div class="step-n">{e(st["n"])}</div>'
            f'<div class="step-body"><h3>{e(st["name"])}</h3><p>{e(st["text"])}</p></div></div>'
            for st in s['steps']
        )
        slides.append(f'''<section class="slide">
  <div class="kicker">{kicker}</div>
  <h2 class="sec-title">{title}</h2>
  <div class="steps">{cards}</div>
</section>''')
        continue

    bullets = ''.join(f'<li>{e(b)}</li>' for b in s.get('bullets', []))

    if 'image' in s:  # split layout — text right, screenshot left (RTL)
        slides.append(f'''<section class="slide">
  <div class="kicker">{kicker}</div>
  <h2 class="sec-title">{title}</h2>
  <div class="split">
    <div class="split-text"><ul>{bullets}</ul></div>
    <figure class="shot">
      <img src="{img_data(s["image"])}" alt="{e(s.get("caption", title))}" loading="lazy">
      <figcaption>{e(s.get('caption', ''))}</figcaption>
    </figure>
  </div>
</section>''')
    else:  # text-only slide — wide bullet cards
        cards = ''.join(f'<div class="pcard">{e(b)}</div>' for b in s.get('bullets', []))
        extra = f'<p class="closing">{e(s["docx"])}</p>' if s.get('docx') else ''
        slides.append(f'''<section class="slide">
  <div class="kicker">{kicker}</div>
  <h2 class="sec-title">{title}</h2>
  <div class="pcards">{cards}</div>
  {extra}
</section>''')

# ── Closing slide ────────────────────────────────────────────────────────────
slides.append(f'''<section class="slide slide-title">
  <div class="title-wrap">
    <div class="logo">AVAR</div>
    <p class="lede">כל הערכה ראויה למי שינסה להפריך אותה — לפני שהיא יוצאת מהדלת</p>
    <p class="audience">{e(meta["note"])}</p>
  </div>
</section>''')

deck = '\n'.join(slides)
total = len(slides)

HTML = f'''<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>AVAR — הצגת המוצר</title>
<style>
  :root {{
    --navy:#0f2447; --navy-2:#1a3a6b; --navy-3:#2a5298;
    --ink:#0f1725; --body:#3a4759; --muted:#7b8798;
    --line:#dde3ec; --bg:#eef1f6; --card:#ffffff; --accent:#c9a227;
    color-scheme: light;
  }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; padding:0; }}
  body {{
    background:var(--bg); color:var(--ink);
    font-family:"Segoe UI",Tahoma,Arial,"Noto Sans Hebrew",sans-serif;
    -webkit-text-size-adjust:100%;
  }}
  img {{ max-width:100%; }}
  [hidden] {{ display:none !important; }}

  /* ── deck shell ── */
  .deck {{ padding: env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px); }}
  .slide {{
    display:none; max-width:1180px; margin:0 auto;
    min-height:calc(100vh - 66px); padding:40px 28px 92px;
    animation:fade .28s ease;
  }}
  .slide.on {{ display:block; }}
  @keyframes fade {{ from {{opacity:0; transform:translateY(6px);}} to {{opacity:1; transform:none;}} }}

  .kicker {{
    display:inline-block; font-size:12px; font-weight:700; letter-spacing:.12em;
    color:var(--navy-3); background:#e5ebf6; border-radius:999px;
    padding:5px 14px; margin-bottom:14px;
  }}
  .sec-title {{
    font-size:clamp(24px,3.4vw,40px); line-height:1.22; margin:0 0 26px;
    color:var(--navy); font-weight:800; letter-spacing:-.01em;
  }}

  /* ── split: bullets + screenshot ── */
  .split {{ display:grid; grid-template-columns:minmax(0,7fr) minmax(0,11fr); gap:30px; align-items:start; }}
  .split-text ul {{ margin:0; padding:0; list-style:none; }}
  .split-text li {{
    position:relative; background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:13px 44px 13px 16px; margin-bottom:10px;
    font-size:15.5px; line-height:1.6; color:var(--body);
    box-shadow:0 1px 2px rgba(15,36,71,.05);
  }}
  .split-text li::before {{
    content:""; position:absolute; top:21px; right:20px;
    width:8px; height:8px; border-radius:50%; background:var(--navy-3);
  }}
  .shot {{ margin:0; }}
  .shot img {{
    width:100%; display:block; border-radius:12px;
    border:1px solid #c9d2e0; box-shadow:0 14px 38px rgba(15,36,71,.17);
  }}
  .shot figcaption {{ margin-top:10px; font-size:13px; color:var(--muted); text-align:center; }}

  /* ── pipeline steps ── */
  .steps {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:16px; }}
  .step {{
    display:flex; gap:14px; background:var(--card); border:1px solid var(--line);
    border-radius:14px; padding:18px; box-shadow:0 1px 3px rgba(15,36,71,.06);
  }}
  .step-n {{
    flex:0 0 40px; height:40px; border-radius:50%; background:var(--navy);
    color:#fff; font-weight:800; font-size:17px;
    display:flex; align-items:center; justify-content:center;
  }}
  .step-body h3 {{ margin:2px 0 6px; font-size:16px; color:var(--navy); }}
  .step-body p {{ margin:0; font-size:14.5px; line-height:1.6; color:var(--body); }}

  /* ── text-only cards ── */
  .pcards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px; }}
  .pcard {{
    background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:18px 20px; font-size:15.5px; line-height:1.62; color:var(--body);
    box-shadow:0 1px 3px rgba(15,36,71,.06);
  }}
  .closing {{
    margin:24px 0 0; padding:18px 22px; background:#e9edf5; border-radius:12px;
    font-size:16px; line-height:1.7; color:var(--navy); font-weight:600;
  }}

  /* ── title slides ── */
  .slide-title {{
    background:linear-gradient(150deg,var(--navy) 0%,var(--navy-2) 55%,var(--navy-3) 100%);
    max-width:none; width:100%; display:none;
  }}
  .slide-title.on {{ display:flex; align-items:center; justify-content:center; }}
  .title-wrap {{ max-width:900px; text-align:center; padding:20px; }}
  .logo {{ font-size:clamp(54px,9vw,104px); font-weight:800; color:#fff; letter-spacing:.06em; line-height:1; }}
  .logo-sub {{ margin-top:10px; font-size:14px; letter-spacing:.2em; color:#a8bcdd; text-transform:uppercase; }}
  .slide-title h1 {{ margin:26px 0 0; font-size:clamp(22px,3.2vw,36px); color:#fff; font-weight:700; line-height:1.35; }}
  .lede {{ margin:16px auto 0; max-width:720px; font-size:clamp(15px,1.7vw,19px); color:#d6e0f0; line-height:1.65; }}
  .audience {{ margin-top:22px; font-size:13px; color:#93a8cb; line-height:1.7; }}

  /* ── toc ── */
  .toc {{ list-style:none; margin:0; padding:0; columns:2; column-gap:34px; }}
  .toc li {{
    break-inside:avoid; display:flex; gap:10px; align-items:baseline;
    padding:8px 0; border-bottom:1px solid var(--line); font-size:14.5px;
  }}
  .toc-n {{ color:var(--navy-3); font-weight:700; font-variant-numeric:tabular-nums; }}
  .toc-k {{ color:var(--muted); font-size:12px; min-width:88px; }}
  .toc-t {{ color:var(--body); }}

  /* ── nav bar ── */
  .bar {{
    position:fixed; bottom:0; right:0; left:0; z-index:9;
    background:rgba(255,255,255,.94); backdrop-filter:blur(8px);
    border-top:1px solid var(--line);
    display:flex; align-items:center; justify-content:center; gap:14px;
    padding:11px 16px calc(11px + env(safe-area-inset-bottom,0px));
  }}
  .bar button {{
    font:inherit; font-size:14px; font-weight:600; color:var(--navy);
    background:#fff; border:1px solid var(--line); border-radius:9px;
    padding:8px 18px; cursor:pointer;
  }}
  .bar button:hover {{ border-color:var(--navy-3); color:var(--navy-3); }}
  .bar button:disabled {{ opacity:.4; cursor:default; }}
  .counter {{ font-size:13px; color:var(--muted); font-variant-numeric:tabular-nums; min-width:74px; text-align:center; }}
  .progress {{ position:fixed; top:0; right:0; height:3px; background:var(--navy-3); z-index:10; transition:width .25s ease; }}

  @media (max-width:820px) {{
    .split {{ grid-template-columns:1fr; }}
    .toc {{ columns:1; }}
    .slide {{ padding:26px 16px 88px; }}
  }}
  @media print {{
    .bar, .progress {{ display:none; }}
    .slide {{ display:block !important; min-height:0; page-break-after:always; padding:20px; }}
    .slide-title.on, .slide-title {{ display:block !important; }}
  }}
</style>
</head>
<body>
<div class="progress" id="progress"></div>
<div class="deck" id="deck">
{deck}
</div>
<nav class="bar">
  <button id="prev" type="button">‹ הקודם</button>
  <span class="counter" id="counter"></span>
  <button id="next" type="button">הבא ›</button>
</nav>
<script>
  // ניווט בין שקפים — מקלדת, כפתורים והיסטוריית hash
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var total = slides.length, i = 0;
  var counter = document.getElementById('counter');
  var progress = document.getElementById('progress');
  var prev = document.getElementById('prev'), next = document.getElementById('next');

  function show(n) {{
    i = Math.max(0, Math.min(total - 1, n));
    slides.forEach(function (s, k) {{ s.classList.toggle('on', k === i); }});
    counter.textContent = (i + 1) + ' / ' + total;
    progress.style.width = ((i + 1) / total * 100) + '%';
    prev.disabled = i === 0; next.disabled = i === total - 1;
    window.scrollTo(0, 0);
    try {{ history.replaceState(null, '', '#' + (i + 1)); }} catch (err) {{}}
  }}
  prev.addEventListener('click', function () {{ show(i - 1); }});
  next.addEventListener('click', function () {{ show(i + 1); }});
  document.addEventListener('keydown', function (ev) {{
    // RTL: חץ שמאל מתקדם, חץ ימין חוזר
    if (ev.key === 'ArrowLeft' || ev.key === 'PageDown' || ev.key === ' ') {{ show(i + 1); ev.preventDefault(); }}
    if (ev.key === 'ArrowRight' || ev.key === 'PageUp') {{ show(i - 1); ev.preventDefault(); }}
    if (ev.key === 'Home') show(0);
    if (ev.key === 'End') show(total - 1);
  }});
  var start = parseInt((location.hash || '').replace('#', ''), 10);
  show(isNaN(start) ? 0 : start - 1);
</script>
</body>
</html>
'''

out = os.path.join(BASE, 'AVAR-presentation.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)
print('wrote', out, f'{os.path.getsize(out)//1024} KB,', total, 'slides')
