/**
 * build_docx.js — בונה מסמך Word (RTL) מתוך content.json
 * Builds the Hebrew RTL product guide (.docx) from the shared content file.
 */
const {
  Document, Packer, Paragraph, TextRun, ImageRun, HeadingLevel, AlignmentType,
  PageBreak, TableOfContents, BorderStyle, convertInchesToTwip, LevelFormat,
} = require('docx');
const fs = require('fs');
const path = require('path');

const BASE = __dirname;
const content = JSON.parse(fs.readFileSync(path.join(BASE, 'content.json'), 'utf-8'));
const DIMS = JSON.parse(fs.readFileSync(path.join(BASE, 'image-dims.json'), 'utf-8'));

const NAVY = '0F2447';
const BLUE = '2A5298';
const BODY = '333F4F';
const MUTED = '7B8798';
const FONT = 'Arial';

// Usable width inside 1" margins on A4 (≈6.27") at 96 dpi
const IMG_W = 590;

/** Hebrew paragraph — RTL direction and right alignment everywhere. */
function p(runs, opts = {}) {
  return new Paragraph({
    bidirectional: true,
    alignment: opts.alignment || AlignmentType.RIGHT,
    spacing: opts.spacing || { after: 120, line: 300 },
    ...opts,
    children: Array.isArray(runs) ? runs : [runs],
  });
}

function t(text, opts = {}) {
  return new TextRun({ text, rightToLeft: true, font: FONT, ...opts });
}

function heading(text, level) {
  return new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    heading: level,
    spacing: { before: 280, after: 160 },
    children: [t(text, { bold: true, color: NAVY, size: level === HeadingLevel.HEADING_1 ? 32 : 26 })],
  });
}

function kicker(text) {
  return p(t(text, { bold: true, color: BLUE, size: 18, allCaps: false }), { spacing: { after: 60 } });
}

function bullet(text) {
  return new Paragraph({
    bidirectional: true,
    alignment: AlignmentType.RIGHT,
    numbering: { reference: 'avar-bullets', level: 0 },
    spacing: { after: 100, line: 290 },
    children: [t(text, { size: 21, color: BODY })],
  });
}

function figure(file, caption) {
  const [iw, ih] = DIMS[file];
  const w = IMG_W, h = Math.round(IMG_W * ih / iw);
  const out = [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 160, after: 60 },
      children: [new ImageRun({
        type: 'jpg',
        data: fs.readFileSync(path.join(BASE, 'assets', file)),
        transformation: { width: w, height: h },
      })],
    }),
  ];
  if (caption) {
    out.push(p(t(caption, { size: 17, color: MUTED, italics: true }), {
      alignment: AlignmentType.CENTER, spacing: { after: 220 },
    }));
  }
  return out;
}

// ── Cover ───────────────────────────────────────────────────────────────────
const cover = [
  p(new TextRun({ text: '', font: FONT }), { spacing: { after: 1800 } }),
  p(new TextRun({ text: 'AVAR', font: FONT, bold: true, size: 96, color: NAVY }), { alignment: AlignmentType.CENTER }),
  p(new TextRun({ text: content.meta.productFull, font: FONT, size: 20, color: MUTED, allCaps: true }), {
    alignment: AlignmentType.CENTER, spacing: { after: 400 },
  }),
  p(t('מערכת אימות הערכות מודיעיניות', { bold: true, size: 40, color: NAVY }), { alignment: AlignmentType.CENTER }),
  p(t(content.meta.subtitle, { size: 24, color: BODY }), { alignment: AlignmentType.CENTER, spacing: { after: 240 } }),
  p(t(content.meta.audience, { size: 20, color: MUTED }), { alignment: AlignmentType.CENTER, spacing: { after: 1400 } }),
  p(t(content.meta.note, { size: 17, color: MUTED, italics: true }), { alignment: AlignmentType.CENTER }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ── Table of contents ───────────────────────────────────────────────────────
const toc = [
  heading('תוכן העניינים', HeadingLevel.HEADING_1),
  new TableOfContents('תוכן', { hyperlink: true, headingStyleRange: '1-2' }),
  p(t('לעדכון מספרי העמודים: לחצו על הטבלה ובחרו "עדכן שדה" (F9).', { size: 17, color: MUTED, italics: true }),
    { spacing: { before: 200 } }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ── Body ────────────────────────────────────────────────────────────────────
const body = [];
content.sections.forEach((sec, i) => {
  body.push(kicker(sec.kicker));
  body.push(heading(sec.title, HeadingLevel.HEADING_1));

  if (sec.docx && !sec.steps) body.push(p(t(sec.docx, { size: 21, color: BODY })));

  if (sec.steps) {
    sec.steps.forEach(st => {
      body.push(new Paragraph({
        bidirectional: true,
        alignment: AlignmentType.RIGHT,
        spacing: { before: 140, after: 40 },
        children: [t(`${st.n}. ${st.name}`, { bold: true, size: 22, color: NAVY })],
      }));
      body.push(p(t(st.text, { size: 21, color: BODY }), { indent: { right: 240 } }));
    });
    if (sec.docx) {
      body.push(p(t(sec.docx, { size: 21, color: BODY, italics: true }), { spacing: { before: 200 } }));
    }
  } else {
    (sec.bullets || []).forEach(b => body.push(bullet(b)));
  }

  if (sec.image) figure(sec.image, sec.caption).forEach(x => body.push(x));

  if (i < content.sections.length - 1) body.push(new Paragraph({ children: [new PageBreak()] }));
});

// ── Document ────────────────────────────────────────────────────────────────
const doc = new Document({
  creator: 'AVAR',
  title: content.meta.title,
  description: content.meta.subtitle,
  numbering: {
    config: [{
      reference: 'avar-bullets',
      levels: [{
        level: 0,
        format: LevelFormat.BULLET,
        text: '•',
        alignment: AlignmentType.RIGHT,
        style: { paragraph: { indent: { right: convertInchesToTwip(0.3), hanging: convertInchesToTwip(0.22) } } },
      }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: FONT, size: 21, color: BODY } },
    },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 32, bold: true, color: NAVY } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: NAVY } },
    ],
  },
  sections: [{
    properties: {
      page: {
        margin: {
          top: convertInchesToTwip(1), bottom: convertInchesToTwip(1),
          left: convertInchesToTwip(1), right: convertInchesToTwip(1),
        },
      },
    },
    children: [...cover, ...toc, ...body],
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(BASE, 'AVAR-guide.docx');
  fs.writeFileSync(out, buf);
  console.log('wrote', out, Math.round(buf.length / 1024), 'KB');
});
