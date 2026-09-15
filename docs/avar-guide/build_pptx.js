/**
 * build_pptx.js — בונה מצגת PowerPoint (RTL) מתוך content.json
 * Builds the Hebrew RTL product-showcase deck from the shared content file.
 */
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

const BASE = __dirname;
const content = JSON.parse(fs.readFileSync(path.join(BASE, 'content.json'), 'utf-8'));
const DIMS = JSON.parse(fs.readFileSync(path.join(BASE, 'image-dims.json'), 'utf-8'));

// ── palette (Midnight Executive, matched to the product's own brand navy) ────
const NAVY = '0F2447';
const NAVY2 = '1A3A6B';
const BLUE = '2A5298';
const ICE = 'CADCFC';
const INK = '16202F';
const BODY = '3A4759';
const MUTED = '7B8798';
const LINE = 'DDE3EC';
const CARD = 'FFFFFF';
const BG = 'F4F6FA';
const FONT = 'Arial';

const W = 13.333, H = 7.5;
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.author = 'AVAR';
pres.title = content.meta.title;

const rtl = { rtlMode: true, align: 'right', fontFace: FONT };

/** Header block shared by every content slide (kicker pill + title). */
function header(slide, kicker, title) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: W - 0.6 - 1.9, y: 0.36, w: 1.9, h: 0.34, rectRadius: 0.17, fill: { color: 'E5EBF6' }, line: { color: 'E5EBF6' },
  });
  slide.addText(kicker, {
    ...rtl, x: W - 0.6 - 1.9, y: 0.36, w: 1.9, h: 0.34,
    fontSize: 11, bold: true, color: BLUE, align: 'center', valign: 'middle', isTextBox: true, margin: 0,
  });
  slide.addText(title, {
    ...rtl, x: 0.6, y: 0.82, w: W - 1.2, h: 0.82,
    fontSize: 28, bold: true, color: NAVY, valign: 'middle', isTextBox: true, margin: 0,
  });
}

/** Screenshot placed inside a box, scaled to fit and centred. */
function placeImage(slide, file, box) {
  const [iw, ih] = DIMS[file];
  const ratio = iw / ih;
  let w = box.w, h = w / ratio;
  if (h > box.h) { h = box.h; w = h * ratio; }
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  slide.addImage({
    path: path.join(BASE, 'assets', file), x, y, w, h,
    shadow: { type: 'outer', color: '0F2447', opacity: 0.22, blur: 14, offset: 4, angle: 90 },
  });
  return { x, y, w, h };
}

// ═══ 1. Title slide ═════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: NAVY } });
  s.addShape(pres.ShapeType.ellipse, { x: W - 4.2, y: -2.2, w: 6.4, h: 6.4, fill: { color: NAVY2 }, line: { color: NAVY2 } });
  s.addShape(pres.ShapeType.ellipse, { x: -2.4, y: H - 3.4, w: 5.6, h: 5.6, fill: { color: '15305A' }, line: { color: '15305A' } });
  s.addText('AVAR', {
    x: 0.8, y: 1.6, w: W - 1.6, h: 1.75, fontSize: 88, bold: true, color: 'FFFFFF',
    align: 'center', fontFace: FONT, charSpacing: 6, isTextBox: true,
  });
  s.addText(content.meta.productFull.toUpperCase(), {
    x: 0.8, y: 3.15, w: W - 1.6, h: 0.4, fontSize: 12, color: 'A8BCDD',
    align: 'center', fontFace: FONT, charSpacing: 3, isTextBox: true,
  });
  s.addText('מערכת אימות הערכות מודיעיניות', {
    ...rtl, x: 0.8, y: 3.75, w: W - 1.6, h: 0.6, fontSize: 26, bold: true, color: 'FFFFFF',
    align: 'center', isTextBox: true,
  });
  s.addText(content.meta.subtitle, {
    ...rtl, x: 1.6, y: 4.45, w: W - 3.2, h: 0.6, fontSize: 15, color: 'D6E0F0', align: 'center', isTextBox: true,
  });
  s.addText(content.meta.audience, {
    ...rtl, x: 1.6, y: 5.3, w: W - 3.2, h: 0.4, fontSize: 12, color: '93A8CB', align: 'center', isTextBox: true,
  });
  s.addNotes('שקף פתיחה — הצגת המוצר AVAR למשתמשים חדשים.');
}

// ═══ 2. Agenda ══════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: BG };
  header(s, 'תוכן', 'מה יש במדריך');
  const items = content.sections;
  const half = Math.ceil(items.length / 2);
  [[0, half, W / 2 + 0.05], [half, items.length, 0.6]].forEach(([from, to, x]) => {
    const col = items.slice(from, to);
    const rows = col.map((sec, i) => ({
      text: `${String(from + i + 1).padStart(2, '0')}   ${sec.title}`,
      options: { breakLine: i < col.length - 1 },
    }));
    s.addText(rows, {
      ...rtl, x, y: 1.85, w: W / 2 - 0.65, h: 5.0,
      fontSize: 12, color: BODY, lineSpacing: 22, isTextBox: true, margin: 0, valign: 'top',
    });
  });
  s.addNotes('סדר היום: מהבעיה, דרך הזרימה המלאה של המערכת, ועד המנוע הניתן להרחבה.');
}

// ═══ 3. Content slides ══════════════════════════════════════════════════════
for (const sec of content.sections) {
  const s = pres.addSlide();
  s.background = { color: BG };
  header(s, sec.kicker, sec.title);

  // ── pipeline: six numbered cards, 3 × 2 ──────────────────────────────────
  if (sec.steps) {
    const cw = (W - 1.2 - 0.4) / 3, ch = 1.95;
    sec.steps.forEach((st, i) => {
      const col = i % 3, row = Math.floor(i / 3);
      // RTL reading order: first card on the right
      const x = W - 0.6 - cw - col * (cw + 0.2);
      const y = 1.9 + row * (ch + 0.3);
      s.addShape(pres.ShapeType.roundRect, {
        x, y, w: cw, h: ch, rectRadius: 0.08,
        fill: { color: CARD }, line: { color: LINE, width: 1 },
      });
      s.addShape(pres.ShapeType.ellipse, { x: x + cw - 0.75, y: y + 0.22, w: 0.5, h: 0.5, fill: { color: NAVY }, line: { color: NAVY } });
      s.addText(st.n, {
        x: x + cw - 0.75, y: y + 0.22, w: 0.5, h: 0.5, fontSize: 15, bold: true, color: 'FFFFFF',
        align: 'center', valign: 'middle', fontFace: FONT, isTextBox: true, margin: 0,
      });
      s.addText(st.name, {
        ...rtl, x: x + 0.25, y: y + 0.24, w: cw - 1.1, h: 0.42,
        fontSize: 13, bold: true, color: NAVY, valign: 'middle', isTextBox: true, margin: 0,
      });
      s.addText(st.text, {
        ...rtl, x: x + 0.25, y: y + 0.76, w: cw - 0.5, h: ch - 1.0,
        fontSize: 11, color: BODY, lineSpacing: 16, valign: 'top', isTextBox: true, margin: 0,
      });
    });
    s.addNotes(sec.docx || '');
    continue;
  }

  // ── with screenshot: bullets on the right, image on the left ─────────────
  if (sec.image) {
    const colW = 4.3;
    const bx = W - 0.6 - colW;
    const rows = sec.bullets.map((b, i) => ({
      text: b, options: { bullet: true, breakLine: i < sec.bullets.length - 1, paraSpaceAfter: 9 },
    }));
    s.addText(rows, {
      ...rtl, x: bx, y: 1.9, w: colW, h: 4.9,
      fontSize: 12, color: BODY, lineSpacing: 17, valign: 'top', isTextBox: true, margin: 0,
    });
    const box = { x: 0.6, y: 1.9, w: W - 1.2 - colW - 0.45, h: 4.55 };
    const placed = placeImage(s, sec.image, box);
    if (sec.caption) {
      s.addText(sec.caption, {
        ...rtl, x: box.x, y: Math.min(placed.y + placed.h + 0.12, 6.62), w: box.w, h: 0.32,
        fontSize: 10, color: MUTED, align: 'center', isTextBox: true, margin: 0,
      });
    }
    s.addNotes(sec.caption || '');
    continue;
  }

  // ── text-only: bullet cards in two columns ───────────────────────────────
  const n = sec.bullets.length;
  const rowsPerCol = Math.ceil(n / 2);
  const cw = (W - 1.2 - 0.25) / 2;
  const ch = Math.min(1.05, (4.4 - (rowsPerCol - 1) * 0.16) / rowsPerCol);
  sec.bullets.forEach((b, i) => {
    const col = Math.floor(i / rowsPerCol), row = i % rowsPerCol;
    const x = W - 0.6 - cw - col * (cw + 0.25);
    const y = 1.9 + row * (ch + 0.16);
    s.addShape(pres.ShapeType.roundRect, {
      x, y, w: cw, h: ch, rectRadius: 0.07,
      fill: { color: CARD }, line: { color: LINE, width: 1 },
    });
    s.addShape(pres.ShapeType.ellipse, { x: x + cw - 0.30, y: y + ch / 2 - 0.06, w: 0.12, h: 0.12, fill: { color: BLUE }, line: { color: BLUE } });
    s.addText(b, {
      ...rtl, x: x + 0.22, y: y + 0.06, w: cw - 0.72, h: ch - 0.12,
      fontSize: 12, color: BODY, lineSpacing: 16, valign: 'middle', isTextBox: true, margin: 0,
    });
  });
  if (sec.docx) {
    const y = 1.9 + rowsPerCol * (ch + 0.16) + 0.12;
    // size the closing callout to its text instead of stretching it to the slide foot
    const charsPerLine = Math.floor((W - 1.7) / (0.0072 * 12));
    const lines = Math.ceil(sec.docx.length / charsPerLine);
    const h = Math.min(Math.max(0.6, 6.85 - y), lines * 0.235 + 0.36);
    s.addShape(pres.ShapeType.roundRect, {
      x: 0.6, y, w: W - 1.2, h, rectRadius: 0.07,
      fill: { color: 'E9EDF5' }, line: { color: 'E9EDF5' },
    });
    s.addText(sec.docx, {
      ...rtl, x: 0.85, y, w: W - 1.7, h,
      fontSize: 12, bold: true, color: NAVY, valign: 'middle', lineSpacing: 17, isTextBox: true, margin: 0,
    });
  }
  s.addNotes(sec.docx || '');
}

// ═══ 4. Closing slide ═══════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.ShapeType.ellipse, { x: -2.0, y: -2.6, w: 6.0, h: 6.0, fill: { color: NAVY2 }, line: { color: NAVY2 } });
  s.addText('AVAR', {
    x: 0.8, y: 2.3, w: W - 1.6, h: 1.2, fontSize: 64, bold: true, color: 'FFFFFF',
    align: 'center', fontFace: FONT, charSpacing: 5, isTextBox: true,
  });
  s.addText('כל הערכה ראויה למי שינסה להפריך אותה — לפני שהיא יוצאת מהדלת', {
    ...rtl, x: 1.4, y: 3.7, w: W - 2.8, h: 0.7, fontSize: 18, color: ICE, align: 'center', isTextBox: true,
  });
  s.addText(content.meta.note, {
    ...rtl, x: 1.8, y: 4.9, w: W - 3.6, h: 0.6, fontSize: 11, color: '93A8CB', align: 'center', isTextBox: true,
  });
}

const out = path.join(BASE, 'AVAR-presentation.pptx');
pres.writeFile({ fileName: out }).then(() => console.log('wrote', out));
