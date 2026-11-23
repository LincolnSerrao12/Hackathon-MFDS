const pptxgen = require("pptxgenjs");
const React = require("react");
const RDS = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const SKILL = "/home/lincoln/.claude/skills/synced/5227a851-6ee8-4849-9a24-e58678798931_ddef60f3-a29f-42a3-8f49-1f5c7662f602/pptx";
const { applyTheme } = require(SKILL + "/scripts/apply_theme.js");

const OUT = process.argv[2];

const THEME = {
  name: "AquaFlare",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B2545", lt1: "FFFFFF", dk2: "13315C", lt2: "EAF4F6",
    accent1: "0097A7", accent2: "F2A541", accent3: "4F7CAC", accent4: "5DAE8B", accent5: "D1495B", accent6: "8D99AE",
    hlink: "0097A7", folHlink: "8D99AE",
  },
};
const HEX = { navy: "0B2545", aqua: "0097A7", aquaLight: "5FD3DF", white: "FFFFFF", amber: "F2A541", mid: "13315C" };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "ME3 File System Intelligence";
pres.author = "ME3 team";
const C = pres.SchemeColor;
const S = pres.ShapeType;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "DARK_TITLE",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.2, w: 8.8, h: 1.5, fontSize: 44, bold: true, color: C.background1, align: "left", valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.85, w: 7.2, h: 1.0, fontSize: 18, color: C.background2, align: "left", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "DARK_DIVIDER",
  background: { color: C.text2 },
  slideNumber: { x: 9.1, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.background2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.6, w: 8.8, h: 1.2, fontSize: 44, bold: true, color: C.background1, align: "left", valign: "bottom" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.95, w: 7.5, h: 1.0, fontSize: 18, color: C.background2, align: "left", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  slideNumber: { x: 9.1, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75, fontSize: 32, bold: true, color: C.text1, align: "left", valign: "middle" }, text: "" } },
    { text: { text: "ME3 File System Intelligence", options: { x: 0.5, y: 5.2, w: 4, h: 0.3, fontSize: 10, color: C.text2, margin: 0, isTextBox: true } } },
  ],
});

// ---------- helpers ----------
async function iconData(Comp, hex, size = 256) {
  const svg = RDS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + hex, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}
const shadow = () => ({ type: "outer", color: "0B2545", blur: 6, offset: 2, angle: 90, opacity: 0.12 });

function card(slide, name, x, y, w, h, fill) {
  slide.addShape(S.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill || C.background2 }, line: { type: "none" }, shadow: shadow(), objectName: name });
}
async function iconCircle(slide, name, Comp, x, y, d, bg, fg) {
  slide.addShape(S.ellipse, { x, y, w: d, h: d, fill: { color: bg || C.accent1 }, line: { type: "none" }, objectName: name + " circle" });
  const pad = d * 0.25;
  slide.addImage({ data: await iconData(Comp, fg || "FFFFFF"), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, altText: name, objectName: name });
}
function T(slide, text, o) { // text box helper: left aligned, no padding
  slide.addText(text, Object.assign({ isTextBox: true, margin: 0, fontSize: 14, color: C.text1, align: "left", valign: "top" }, o));
}
function bullets(items, opts = {}) {
  return items.map((t, i) => ({ text: t, options: Object.assign({ bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 4 }, opts) }));
}
function box(slide, name, text, x, y, w, h, o = {}) {
  slide.addText(text, Object.assign({
    shape: S.roundRect, rectRadius: 0.07, x, y, w, h, fill: { color: C.accent1 }, color: C.background1, fontSize: 13, bold: true,
    align: "center", valign: "middle", margin: 0.05, objectName: name, isTextBox: true,
  }, o));
}
function arrow(slide, x1, y1, x2, y2, o = {}) {
  slide.addShape(S.line, Object.assign({
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    flipH: x2 < x1, flipV: y2 < y1, line: { color: HEX.mid, width: 1.75, endArrowType: "triangle" },
  }, o));
}
function content(title, section, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
function code(slide, name, lines, x, y, w, h, size = 12) {
  slide.addShape(S.roundRect, { x, y, w, h, rectRadius: 0.06, fill: { color: C.text1 }, line: { type: "none" }, objectName: name + " bg" });
  slide.addText(lines.map((l, i) => ({ text: l, options: { breakLine: i < lines.length - 1 } })), {
    x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h - 0.2, fontFace: "Courier New", fontSize: size, color: "9FE8F0", margin: 0, valign: "top", isTextBox: true, objectName: name,
  });
}
function th(t) { return { text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 }, fontSize: 12, valign: "middle" } }; }
function td(t, o = {}) { return { text: t, options: Object.assign({ fontSize: 12, color: C.text1, valign: "middle" }, o) }; }

(async () => {
  // ============ 1. TITLE ============
  pres.addSection({ title: "Overview" });
  {
    const s = pres.addSlide({ masterName: "DARK_TITLE", sectionTitle: "Overview" });
    s.addText("ME3 File System Intelligence", { placeholder: "title" });
    s.addText("Local-first search, organisation and cleanup for your files, with a privacy gate in front of any cloud AI.", { placeholder: "body" });
    const ic = [fa.FaSearch, fa.FaDatabase, fa.FaShieldAlt, fa.FaCloud];
    const lab = ["Search", "Index", "Privacy", "Cloud AI"];
    for (let i = 0; i < 4; i++) {
      const x = 0.6 + i * 1.35;
      await iconCircle(s, lab[i] + " icon", ic[i], x, 4.0, 0.7, i === 2 ? C.accent2 : C.accent1, i === 2 ? HEX.navy : "FFFFFF");
      T(s, lab[i], { x: x - 0.2, y: 4.78, w: 1.1, h: 0.3, fontSize: 12, color: C.background2, align: "center" });
    }
    s.addNotes("Overview of ME3: what it is, how it is built, which libraries and algorithms it uses, and how to operate it.");
  }

  // ============ 2. PROBLEM / GOALS ============
  {
    const s = content("What ME3 does", "Overview", "Three requirements from the brief, all implemented. Plus cleanup, organisation ideas and the privacy gate.");
    const items = [
      [fa.FaBolt, "Efficient live index", "An incremental crawler and a live watcher keep a 100k-file index fresh without full rescans."],
      [fa.FaServer, "Local + remote", "Local disks, SFTP servers and Google Drive sit behind one Source interface."],
      [fa.FaSearch, "Search by meaning", "Ask for \"fee receipt from last semester\". Text and images are found by meaning, plus type, date and size filters."],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05;
      card(s, "Goal card " + (i + 1), x, 1.3, 2.9, 2.75);
      await iconCircle(s, items[i][1] + " icon", items[i][0], x + 0.2, 1.5, 0.65);
      T(s, items[i][1], { x: x + 0.2, y: 2.3, w: 2.5, h: 0.4, fontSize: 18, bold: true });
      T(s, items[i][2], { x: x + 0.2, y: 2.75, w: 2.5, h: 1.2, fontSize: 14 });
    }
    s.addShape(S.roundRect, { x: 0.5, y: 4.3, w: 9.0, h: 0.7, rectRadius: 0.08, fill: { color: C.text1 }, line: { type: "none" }, objectName: "Extras strip" });
    T(s, "Plus: duplicate and large-file cleanup, AI organisation ideas, and an on-device privacy gate that decides what may leave the machine.",
      { x: 0.75, y: 4.3, w: 8.5, h: 0.7, fontSize: 14, color: C.background1, valign: "middle" });
  }

  // ============ 3. BENCHMARKS ============
  {
    const s = content("Built for scale", "Overview", "Benchmarks on 100k synthetic files (2.1 GB), from the README. Search latencies are warm; the first query loads the model (about 3 s).");
    s.addChart(pres.charts.BAR, [{
      name: "Files", labels: ["Document", "Image", "Code", "Audio", "Archive", "Video", "Other"],
      values: [51133, 13964, 10978, 7001, 6937, 6918, 3072],
    }], {
      x: 0.5, y: 1.2, w: 4.9, h: 3.8, barDir: "bar", chartColors: [HEX.aqua],
      showTitle: true, title: "Benchmark dataset: files by type", titleFontSize: 13, titleColor: HEX.navy, titleFontFace: "+mn-lt",
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: HEX.navy, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "#,##0",
      catAxisLabelColor: HEX.navy, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin",
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    });
    const stats = [["2.2 s", "crawl 100k files"], ["5 ms", "keyword search"], ["13-30 ms", "hybrid search, warm"], ["8 s", "duplicate analysis"]];
    for (let i = 0; i < 4; i++) {
      const x = 5.6 + (i % 2) * 2.0, y = 1.3 + Math.floor(i / 2) * 1.85;
      card(s, "Stat card " + (i + 1), x, y, 1.9, 1.7);
      T(s, stats[i][0], { x: x + 0.1, y: y + 0.3, w: 1.7, h: 0.6, fontSize: i === 2 ? 26 : 32, bold: true, color: C.accent1, align: "center", valign: "middle" });
      T(s, stats[i][1], { x: x + 0.1, y: y + 1.0, w: 1.7, h: 0.5, fontSize: 13, align: "center" });
    }
  }

  // ============ 4. ARCHITECTURE ============
  pres.addSection({ title: "Architecture" });
  {
    const s = content("System architecture", "Architecture", "Modular monolith: one FastAPI process with background worker threads and one SQLite file. The privacy gate is the only path to the cloud LLM.");
    box(s, "Web UI", "Web UI  (HTML + JS, served by FastAPI)", 0.5, 1.2, 6.6, 0.5, { fill: { color: C.text2 } });
    arrow(s, 3.8, 1.7, 3.8, 2.0);
    box(s, "API", "FastAPI  api.py:  search, sources, cleanup, privacy, suggest", 0.5, 2.0, 6.6, 0.5, { fill: { color: C.text2 } });
    arrow(s, 3.8, 2.5, 3.8, 2.75);
    const mods = [["Search", "FTS5 + vectors"], ["Cleanup", "dupes, large, stale"], ["Sources", "Local, SFTP, Drive"], ["Privacy gate", "redact, preview"]];
    for (let i = 0; i < 4; i++) {
      const x = 0.5 + i * (1.55 + 0.1333);
      box(s, mods[i][0], [{ text: mods[i][0], options: { bold: true, fontSize: 13, breakLine: true } }, { text: mods[i][1], options: { bold: false, fontSize: 11 } }],
        x, 2.75, 1.55, 0.85, { fill: { color: i === 3 ? C.accent2 : C.accent1 }, color: i === 3 ? C.text1 : C.background1 });
    }
    arrow(s, 3.8, 3.6, 3.8, 3.85);
    box(s, "Pipeline", "Indexing pipeline (background, low priority):  crawl / watch  >  extract  >  embed", 0.5, 3.85, 6.6, 0.5, { fill: { color: C.accent3 } });
    arrow(s, 3.8, 4.35, 3.8, 4.6);
    box(s, "SQLite", "SQLite file:  files, FTS5 index, sqlite-vec vectors", 0.5, 4.6, 6.6, 0.5, { fill: { color: C.accent6 }, color: C.text1 });
    // cloud box
    s.addShape(S.roundRect, { x: 7.65, y: 2.45, w: 1.85, h: 1.45, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: HEX.aqua, width: 1.5, dashType: "dash" }, objectName: "Cloud box" });
    T(s, [{ text: "Claude (optional)", options: { bold: true, breakLine: true } }, { text: "sees redacted metadata only, after you click send", options: { fontSize: 11 } }],
      { x: 7.75, y: 2.55, w: 1.65, h: 1.25, fontSize: 13, align: "center", valign: "middle" });
    arrow(s, 7.1 - 0.0, 3.175, 7.65, 3.175, { line: { color: HEX.amber, width: 2, dashType: "dash", endArrowType: "triangle" } });
    T(s, "Everything else stays on the device", { x: 7.65, y: 4.05, w: 1.85, h: 0.6, fontSize: 12, italic: true, align: "center" });
  }

  // ============ 5. INDEXING PIPELINE ============
  {
    const s = content("Tiered indexing pipeline", "Architecture", "Metadata first so every file is searchable by name in seconds; then text; then embeddings lazily at low priority.");
    const steps = [["1", "Crawl / watch", "Sources list entries"], ["2", "Diff", "size + mtime vs DB"], ["3", "Extract", "txt, code, pdf, docx"], ["4", "Embed", "MiniLM, CLIP"], ["5", "Store", "SQLite"]];
    for (let i = 0; i < 5; i++) {
      const x = 0.5 + i * 1.825;
      s.addShape(S.roundRect, { x, y: 1.3, w: 1.7, h: 1.15, rectRadius: 0.08, fill: { color: i % 2 ? C.text2 : C.text1 }, line: { type: "none" }, objectName: "Step " + steps[i][0] });
      T(s, steps[i][0], { x: x + 0.12, y: 1.38, w: 0.4, h: 0.3, fontSize: 14, bold: true, color: C.accent2 });
      T(s, steps[i][1], { x: x + 0.12, y: 1.68, w: 1.5, h: 0.3, fontSize: 15, bold: true, color: C.background1 });
      T(s, steps[i][2], { x: x + 0.12, y: 2.02, w: 1.5, h: 0.35, fontSize: 12, color: C.background2 });
      if (i < 4) arrow(s, x + 1.7, 1.875, x + 1.825, 1.875, { line: { color: HEX.aqua, width: 2, endArrowType: "triangle" } });
    }
    const tiers = [
      ["Tier 1: metadata", "Name, path, size, mtime for every file. 100k files in about 2 seconds, so name search works immediately."],
      ["Tier 2: text", "Text from txt, code, PDF, DOCX and Google Docs goes into FTS5 in the background, capped at 20k characters per file."],
      ["Tier 3: meaning", "Embeddings are computed lazily on low-priority threads (nice 10), so the app stays responsive while indexing."],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05;
      card(s, "Tier card " + (i + 1), x, 2.75, 2.9, 1.5);
      T(s, tiers[i][0], { x: x + 0.2, y: 2.87, w: 2.5, h: 0.3, fontSize: 15, bold: true, color: C.accent1 });
      T(s, tiers[i][1], { x: x + 0.2, y: 3.2, w: 2.55, h: 1.0, fontSize: 12 });
    }
    T(s, "Live updates: watchdog (inotify) for local folders, polling fallback, remote sources rescanned every 120 s.",
      { x: 0.5, y: 4.5, w: 9.0, h: 0.5, fontSize: 14, valign: "middle" });
  }

  // ============ 6. STORAGE ============
  {
    const s = content("Storage model", "Architecture", "One SQLite file keeps deployment trivial: FTS5 for keywords and the sqlite-vec extension for nearest-neighbour search live in the same database.");
    s.addTable([
      [th("Table"), th("Holds")],
      [td("sources", { bold: true }), td("Configured roots: local folder, SFTP host, Google Drive")],
      [td("files", { bold: true }), td("path, name, ext, kind, size, mtime, hash, extracted and embedded flags")],
      [td("fts (FTS5)", { bold: true }), td("Full-text index over name, path and body; bm25 weights 6 / 2 / 1")],
      [td("vec_text", { bold: true }), td("384-d MiniLM vector per document (name + first 1500 chars)")],
      [td("vec_img", { bold: true }), td("512-d CLIP vector per image")],
    ], { x: 0.5, y: 1.25, w: 5.6, colW: [1.5, 4.1], rowH: 0.55, border: { type: "solid", pt: 0.75, color: "C9D6DC" }, fill: { color: C.background1 }, margin: 0.08 });
    card(s, "Why SQLite card", 6.4, 1.25, 3.1, 3.3);
    await iconCircle(s, "Database icon", fa.FaDatabase, 6.6, 1.45, 0.6);
    T(s, "Why one SQLite file", { x: 6.6, y: 2.2, w: 2.8, h: 0.35, fontSize: 16, bold: true });
    T(s, bullets(["No server to install", "Thread-local connections", "Batched writes (2000 rows)", "Rebuildable from the sources"]), { x: 6.6, y: 2.6, w: 2.8, h: 1.8, fontSize: 14 });
  }

  // ============ 7-8. LIBRARIES ============
  pres.addSection({ title: "Libraries" });
  {
    const s = content("Libraries: platform and files", "Libraries", "Libraries that provide the web app, command line, live watching and file text extraction.");
    s.addTable([
      [th("Library"), th("What it does"), th("Where ME3 uses it")],
      [td("FastAPI + Uvicorn", { bold: true }), td("Async web framework and server"), td("api.py: REST API and the UI at /")],
      [td("Pydantic", { bold: true }), td("Request validation"), td("api.py: typed request bodies")],
      [td("Typer + Rich", { bold: true }), td("CLI and terminal output"), td("cli.py: serve, index, search, add-sftp ...")],
      [td("watchdog", { bold: true }), td("File-system events (inotify)"), td("watcher.py: live index updates")],
      [td("SQLite FTS5", { bold: true }), td("Full-text search with bm25"), td("db.py, search.py: keyword ranking")],
      [td("pypdf", { bold: true }), td("PDF text extraction"), td("extract.py: PDF bodies into FTS")],
      [td("python-docx", { bold: true }), td("Word document reading"), td("extract.py: DOCX bodies into FTS")],
      [td("pytest + ruff", { bold: true }), td("Tests and linting"), td("tests/ (17 tests), make test, make lint")],
    ], { x: 0.5, y: 1.2, w: 9.0, colW: [2.1, 3.1, 3.8], rowH: 0.42, border: { type: "solid", pt: 0.75, color: "C9D6DC" }, fill: { color: C.background1 }, margin: 0.08 });
  }
  {
    const s = content("Libraries: AI, privacy, connectors", "Libraries", "The AI stack runs on-device (torch CPU). Only the anthropic client talks to the network, and only with redacted payloads.");
    s.addTable([
      [th("Library"), th("What it does"), th("Where ME3 uses it")],
      [td("sentence-transformers", { bold: true }), td("MiniLM text and CLIP image embeddings"), td("embed.py: meaning search (torch, CPU)")],
      [td("sqlite-vec", { bold: true }), td("Vector index inside SQLite"), td("embed.py, search.py: cosine k-NN")],
      [td("Presidio + spaCy", { bold: true }), td("Named-entity PII detection"), td("privacy.py: names, emails, cards, IPs")],
      [td("anthropic", { bold: true }), td("Claude API client"), td("llm.py: organisation suggestions")],
      [td("python-dotenv", { bold: true }), td("Loads .env"), td("llm.py: reads ANTHROPIC_API_KEY")],
      [td("paramiko", { bold: true }), td("SSH / SFTP client"), td("connectors/sftp.py: NAS and servers")],
      [td("google-api-python-client", { bold: true }), td("Drive API and OAuth flow"), td("connectors/gdrive.py: Drive source")],
      [td("Pillow", { bold: true }), td("Image decoding"), td("embed.py: loads images for CLIP")],
    ], { x: 0.5, y: 1.2, w: 9.0, colW: [2.4, 3.0, 3.6], rowH: 0.42, border: { type: "solid", pt: 0.75, color: "C9D6DC" }, fill: { color: C.background1 }, margin: 0.08 });
  }

  // ============ 9. ALGORITHM: INCREMENTAL CRAWL ============
  pres.addSection({ title: "Algorithms" });
  {
    const s = content("Algorithm: incremental crawl", "Algorithms", "Cost is proportional to what changed, not to the size of the tree. crawler.py upsert() returns new, changed or same.");
    T(s, "Each file entry from a Source is compared with its stored row by size and modification time.", { x: 0.5, y: 1.25, w: 4.3, h: 0.9, fontSize: 15 });
    T(s, bullets(["Entries are written in batches of 2000", "Files missing from the walk are removed", "The watcher feeds the same upsert path, debounced 1.5 s", "Hashes are computed later, only when needed"]),
      { x: 0.5, y: 2.2, w: 4.3, h: 2.5, fontSize: 14 });
    box(s, "Entry", "File entry", 5.2, 1.25, 4.3, 0.5, { fill: { color: C.text2 } });
    arrow(s, 7.35, 1.75, 7.35, 2.0);
    box(s, "Compare", "Same size and mtime as stored row?", 5.2, 2.0, 4.3, 0.5, { fill: { color: C.text2 } });
    const out = [["new", "Insert row + FTS row", C.accent4], ["changed", "Reset text, hash, embedding", C.accent2], ["same", "Skip: no write", C.accent6], ["gone", "Delete row", C.accent5]];
    for (let i = 0; i < 4; i++) {
      const y = 2.8 + i * 0.57;
      box(s, "Outcome " + out[i][0], out[i][0], 5.2, y, 1.0, 0.45, { fill: { color: out[i][2] }, color: C.text1 });
      T(s, out[i][1], { x: 6.35, y, w: 3.1, h: 0.45, fontSize: 14, valign: "middle" });
    }
  }

  // ============ 10. ALGORITHM: NL QUERY PARSER ============
  {
    const s = content("Algorithm: natural-language filters", "Algorithms", "nlq.py is a rule-based parser (keyword tables, regex, date arithmetic). It runs on-device, so no LLM is needed to understand a query. Output verified by running nlq.parse_full.");
    s.addShape(S.roundRect, { x: 0.5, y: 1.25, w: 9.0, h: 0.75, rectRadius: 0.08, fill: { color: C.text1 }, line: { type: "none" }, objectName: "Query bar" });
    T(s, "fee receipt PDFs larger than 5MB from last semester", { x: 0.75, y: 1.25, w: 8.5, h: 0.75, fontSize: 20, color: C.background1, valign: "middle", bold: true });
    arrow(s, 5.0, 2.0, 5.0, 2.4);
    const chips = [["Search text", "fee receipt", C.accent1], ["File type", "pdf", C.accent3], ["Min size", "5 MB", C.accent4], ["Date range", "last semester", C.accent2]];
    for (let i = 0; i < 4; i++) {
      const x = 0.5 + i * 2.275;
      card(s, "Chip " + chips[i][0], x, 2.4, 2.15, 1.05);
      T(s, chips[i][0], { x: x + 0.15, y: 2.5, w: 1.9, h: 0.3, fontSize: 12, color: C.text2 });
      T(s, chips[i][1], { x: x + 0.15, y: 2.85, w: 1.9, h: 0.45, fontSize: 18, bold: true, color: chips[i][2] === C.accent2 ? C.text1 : chips[i][2] });
    }
    T(s, bullets([
      "Word tables map photos, videos, spreadsheets, slides to kinds and extensions",
      "Size patterns (5MB, 2 GB) become byte limits; months, years and last week / month / semester become date ranges",
      "Stop words are stripped; what remains goes to keyword and meaning search",
    ]), { x: 0.5, y: 3.7, w: 9.0, h: 1.4, fontSize: 14 });
  }

  // ============ 11. ALGORITHM: HYBRID SEARCH ============
  {
    const s = content("Algorithm: hybrid search", "Algorithms", "Reciprocal rank fusion needs no score calibration: it only uses rank positions, so BM25 and cosine scores can be mixed safely. K=60.");
    const rk = [["Keyword", "FTS5 prefix match, bm25 weights name 6, path 2, body 1", C.accent1],
      ["Text meaning", "MiniLM cosine k-NN, noise cut-off 0.30", C.accent3],
      ["Image meaning", "CLIP cosine k-NN, cut-off 0.18 (forced) or 0.26", C.accent4]];
    for (let i = 0; i < 3; i++) {
      const y = 1.25 + i * 1.05;
      s.addShape(S.roundRect, { x: 0.5, y, w: 4.4, h: 0.9, rectRadius: 0.08, fill: { color: rk[i][2] }, line: { type: "none" }, objectName: "Ranker " + rk[i][0] });
      T(s, rk[i][0], { x: 0.7, y: y + 0.08, w: 4.0, h: 0.3, fontSize: 15, bold: true, color: C.background1 });
      T(s, rk[i][1], { x: 0.7, y: y + 0.4, w: 4.0, h: 0.45, fontSize: 12, color: C.background1 });
      arrow(s, 4.9, y + 0.45, 5.4, 2.65, { line: { color: HEX.mid, width: 1.5, endArrowType: "triangle" } });
    }
    s.addShape(S.roundRect, { x: 5.4, y: 1.8, w: 4.1, h: 1.7, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: HEX.aqua, width: 1.5 }, objectName: "RRF box" });
    T(s, "Reciprocal rank fusion", { x: 5.55, y: 1.9, w: 3.8, h: 0.3, fontSize: 15, bold: true });
    T(s, "score(d) = sum over rankers of 1 / (60 + rank)", { x: 5.55, y: 2.3, w: 3.8, h: 0.7, fontSize: 18, bold: true, color: C.accent1 });
    T(s, "Type, date and size filters are applied to every candidate list first.", { x: 5.55, y: 3.0, w: 3.8, h: 0.45, fontSize: 12 });
    T(s, "Each result carries a \"why\" tag (keyword, meaning, image). If embeddings are unavailable, search falls back to keyword-only.",
      { x: 5.4, y: 3.7, w: 4.1, h: 1.2, fontSize: 14 });
    T(s, "Result: about 13-30 ms warm on 100k files.", { x: 0.5, y: 4.45, w: 4.4, h: 0.5, fontSize: 14, bold: true, color: C.accent1, valign: "middle" });
  }

  // ============ 12. ALGORITHM: EMBEDDINGS ============
  {
    const s = content("Algorithm: semantic embeddings", "Algorithms", "Both models run locally on CPU; nothing is sent anywhere. Vectors are stored in sqlite-vec and queried by cosine distance.");
    const cols = [
      [fa.FaFileAlt, "MiniLM for text", "all-MiniLM-L6-v2, 384 dimensions", ["Input: file name + first ~1500 characters", "Finds \"fee receipt\" in a file called scan_0042.pdf", "A synonym lexicon covers everyday words the small model misses"]],
      [fa.FaImage, "CLIP for images", "clip-ViT-B-32, 512 dimensions", ["Input: image pixels", "Text queries are embedded into the same space", "\"Beach photos\" finds IMG_0412.jpg with no tags needed"]],
    ];
    for (let i = 0; i < 2; i++) {
      const x = 0.5 + i * 4.6;
      card(s, "Embedding card " + (i + 1), x, 1.25, 4.4, 3.0);
      await iconCircle(s, cols[i][1] + " icon", cols[i][0], x + 0.2, 1.4, 0.6);
      T(s, cols[i][1], { x: x + 0.95, y: 1.4, w: 3.3, h: 0.3, fontSize: 18, bold: true });
      T(s, cols[i][2], { x: x + 0.95, y: 1.75, w: 3.3, h: 0.3, fontSize: 12, color: C.text2 });
      T(s, bullets(cols[i][3]), { x: x + 0.2, y: 2.2, w: 4.0, h: 1.95, fontSize: 14 });
    }
    T(s, "Embedding runs lazily in the background: each file is marked pending, done or skipped, and changed files are re-queued.",
      { x: 0.5, y: 4.4, w: 9.0, h: 0.6, fontSize: 14, valign: "middle" });
  }

  // ============ 13. ALGORITHM: DUPLICATES ============
  {
    const s = content("Algorithm: duplicate detection", "Algorithms", "A three-stage funnel avoids hashing most files. Only local sources are hashed; remote files would need a download. Removing a duplicate moves it to data/trash/ so it can be restored.");
    const st = [["1  Group by size", "Files with a unique size cannot be duplicates", 9.0, C.accent3],
      ["2  Partial hash", "SHA-1 of the first 64 KB inside each size group", 7.4, C.accent1],
      ["3  Full hash", "Streamed SHA-1 in 1 MB chunks, only inside matching buckets", 5.8, C.accent4]];
    for (let i = 0; i < 3; i++) {
      const w = st[i][2], x = 0.5 + (9.0 - w) / 2, y = 1.25 + i * 0.95;
      s.addShape(S.roundRect, { x, y, w, h: 0.8, rectRadius: 0.08, fill: { color: st[i][3] }, line: { type: "none" }, objectName: "Funnel " + (i + 1) });
      T(s, st[i][0], { x: x + 0.2, y: y + 0.08, w: w - 0.4, h: 0.3, fontSize: 15, bold: true, color: C.background1 });
      T(s, st[i][1], { x: x + 0.2, y: y + 0.42, w: w - 0.4, h: 0.3, fontSize: 12, color: C.background1 });
    }
    T(s, bullets(["Wasted space = size x (copies - 1), groups sorted by waste", "Full hashes are cached in the DB, so reruns are fast", "Also lists large files (over 50 MB) and stale media (untouched for a year)"]),
      { x: 0.5, y: 4.15, w: 9.0, h: 1.0, fontSize: 14 });
  }

  // ============ 14. PRIVACY GATE ============
  {
    const s = content("Algorithm: privacy gate", "Algorithms", "privacy.py is the only code path that can reach llm.py. The UI shows the exact redacted payload and requires an explicit send click.");
    const flow = [["File metadata", "path, name, kind, size, date"], ["Detect", "Presidio NER + regex rules"], ["Redact", "typed placeholders"], ["Preview", "you see the payload"], ["Send", "only on your click"]];
    for (let i = 0; i < 5; i++) {
      const x = 0.5 + i * 1.825;
      s.addShape(S.roundRect, { x, y: 1.25, w: 1.7, h: 1.0, rectRadius: 0.08, fill: { color: i === 4 ? C.accent2 : (i % 2 ? C.text2 : C.text1) }, line: { type: "none" }, objectName: "Flow " + flow[i][0] });
      T(s, flow[i][0], { x: x + 0.1, y: 1.33, w: 1.5, h: 0.3, fontSize: 14, bold: true, color: i === 4 ? C.text1 : C.background1 });
      T(s, flow[i][1], { x: x + 0.1, y: 1.67, w: 1.5, h: 0.5, fontSize: 11, color: i === 4 ? C.text1 : C.background2 });
      if (i < 4) arrow(s, x + 1.7, 1.75, x + 1.825, 1.75, { line: { color: HEX.aqua, width: 2, endArrowType: "triangle" } });
    }
    card(s, "Detect card", 0.5, 2.55, 4.4, 2.45);
    T(s, "What is detected", { x: 0.7, y: 2.65, w: 4.0, h: 0.3, fontSize: 16, bold: true, color: C.accent1 });
    T(s, bullets(["Names, emails, phones, IPs (Presidio + spaCy)", "Cards (Luhn check), IBAN, SSN", "India: PAN, Aadhaar, IFSC, UPI, passport, account no.", "Secrets: API keys, passwords, tokens"]), { x: 0.7, y: 3.0, w: 4.0, h: 1.95, fontSize: 13 });
    card(s, "Redact card", 5.1, 2.55, 4.4, 2.45);
    T(s, "What the cloud sees", { x: 5.3, y: 2.65, w: 4.0, h: 0.3, fontSize: 16, bold: true, color: C.accent1 });
    T(s, bullets(["Findings become <EMAIL_1>, <PAN_1> ...: structure stays, identity goes", "The home-directory username in paths is removed", "Never file contents, only redacted names and metadata"]), { x: 5.3, y: 3.0, w: 4.0, h: 1.95, fontSize: 13 });
  }

  // ============ 15. AI ORGANISATION ============
  {
    const s = content("Organisation suggestions", "Algorithms", "On-device ideas always work. The cloud step is optional and needs both an API key in .env and a click on the send button.");
    card(s, "On-device card", 0.5, 1.25, 4.4, 3.4);
    await iconCircle(s, "Laptop icon", fa.FaLaptop, 0.7, 1.4, 0.6, C.accent4);
    T(s, "On-device (always)", { x: 1.45, y: 1.5, w: 3.3, h: 0.4, fontSize: 18, bold: true });
    T(s, bullets(["Rule-based scan for messy folders", "Ranks folders by clutter", "Samples files from the messiest ones", "Works with no API key"]), { x: 0.7, y: 2.2, w: 4.0, h: 2.3, fontSize: 14 });
    card(s, "Cloud card", 5.1, 1.25, 4.4, 3.4);
    await iconCircle(s, "Cloud icon", fa.FaCloud, 5.3, 1.4, 0.6, C.accent2, HEX.navy);
    T(s, "Cloud AI (optional)", { x: 6.05, y: 1.5, w: 3.3, h: 0.4, fontSize: 18, bold: true });
    T(s, bullets(["Model: claude-haiku-5-5 (ME3_LLM_MODEL overrides)", "Receives only the redacted sample", "Returns a summary and up to 6 folder suggestions as JSON", "Nothing is moved automatically"]), { x: 5.3, y: 2.2, w: 4.0, h: 2.3, fontSize: 14 });
    T(s, "Two-step UI: Analyse and preview first, then Send redacted preview.", { x: 0.5, y: 4.75, w: 8.5, h: 0.35, fontSize: 14, bold: true, color: C.accent1 });
  }

  // ============ 16. DIVIDER ============
  pres.addSection({ title: "User manual" });
  {
    const s = pres.addSlide({ masterName: "DARK_DIVIDER", sectionTitle: "User manual" });
    s.addText("User manual", { placeholder: "title" });
    s.addText("Install, add your storage, search, clean up, and use the privacy tools.", { placeholder: "body" });
  }

  // ============ 17. START ============
  {
    const s = content("1. Start the app", "User manual", "No virtual environment: libraries live in ./libs and env.sh sets PYTHONPATH. Models are cached in ./models and HF_HUB_OFFLINE=1 prevents network calls at runtime.");
    const steps = [["Open a terminal", "in the project folder"], ["Load the environment", "env.sh points Python at ./libs and ./models"], ["Start the server", "or simply run make run"], ["Open the browser", "the UI is the home page"]];
    for (let i = 0; i < 4; i++) {
      const y = 1.25 + i * 0.85;
      s.addShape(S.ellipse, { x: 0.5, y: y + 0.05, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Step number " + (i + 1) });
      T(s, String(i + 1), { x: 0.5, y: y + 0.05, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle" });
      T(s, steps[i][0], { x: 1.15, y, w: 3.3, h: 0.3, fontSize: 15, bold: true });
      T(s, steps[i][1], { x: 1.15, y: y + 0.32, w: 3.3, h: 0.45, fontSize: 12, color: C.text2 });
    }
    code(s, "Start commands", ["cd ~/Desktop/AquaFlare/me3-fsi", "source env.sh", "python -m me3 serve --port 8765", "", "# then open", "http://127.0.0.1:8765"], 4.7, 1.25, 4.8, 2.0, 13);
    card(s, "Optional card", 4.7, 3.45, 4.8, 1.55);
    T(s, "Optional: cloud AI", { x: 4.9, y: 3.55, w: 4.4, h: 0.3, fontSize: 15, bold: true, color: C.accent1 });
    T(s, "Create a .env file in the project root with ANTHROPIC_API_KEY=... (it is gitignored). Without it, everything except cloud suggestions works.",
      { x: 4.9, y: 3.9, w: 4.4, h: 1.05, fontSize: 13 });
  }

  // ============ 18. ADD SOURCES ============
  {
    const s = content("2. Add your storage", "User manual", "Use the Sources card at the top of the page. The first scan is fast; text and meaning indexing continue in the background.");
    const cols = [
      [fa.FaFolderOpen, "Local", ["Choose Local", "Type a folder path, e.g. ~/Documents", "Press Add"], "CLI: python -m me3 index <folder>"],
      [fa.FaServer, "SFTP / NAS", ["Choose SFTP", "Host, port, user", "Password or key file path", "Remote folder, then Add"], "CLI: python -m me3 add-sftp <host> ..."],
      [fa.FaGoogleDrive, "Google Drive", ["Put the OAuth credentials file in the project root", "Run gdrive-auth and approve in the browser", "Then add the Drive source"], "CLI: python -m me3 add-gdrive"],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05;
      card(s, "Source card " + (i + 1), x, 1.25, 2.9, 3.75);
      await iconCircle(s, cols[i][1] + " icon", cols[i][0], x + 0.2, 1.4, 0.6);
      T(s, cols[i][1], { x: x + 0.95, y: 1.5, w: 1.9, h: 0.4, fontSize: 17, bold: true });
      T(s, bullets(cols[i][2]), { x: x + 0.2, y: 2.2, w: 2.55, h: 2.0, fontSize: 13 });
      T(s, cols[i][3], { x: x + 0.2, y: 4.3, w: 2.55, h: 0.6, fontSize: 11, color: C.text2 });
    }
  }

  // ============ 19. SEARCH ============
  {
    const s = content("3. Search", "User manual", "Describe what you remember. Dropdown filters for type, size and date combine with whatever the query text implies; explicit filters win.");
    T(s, "Type in plain language. Each result shows why it matched: keyword, meaning or image.", { x: 0.5, y: 1.2, w: 9.0, h: 0.4, fontSize: 15 });
    s.addTable([
      [th("Try this"), th("What ME3 does")],
      [td("fee receipt from last semester", { bold: true }), td("Keyword + meaning search, limited to the last semester's dates")],
      [td("photos from the beach trip", { bold: true }), td("Images only; CLIP matches the beach scene, not the file name")],
      [td("pdf larger than 5MB", { bold: true }), td("Extension and size filters from the query text")],
      [td("videos in March 2024", { bold: true }), td("Video kind and a date range for that month")],
      [td("invoice", { bold: true }), td("Keyword hits in names and text, plus similar documents by meaning")],
    ], { x: 0.5, y: 1.7, w: 9.0, colW: [3.2, 5.8], rowH: 0.46, border: { type: "solid", pt: 0.75, color: "C9D6DC" }, fill: { color: C.background1 }, margin: 0.08 });
    T(s, "Use the filter row (type, min / max MB, dates) to narrow results further.", { x: 0.5, y: 4.65, w: 9.0, h: 0.4, fontSize: 14, bold: true, color: C.accent1 });
  }

  // ============ 20. CLEANUP / ORGANISE / PRIVACY TABS ============
  {
    const s = content("4. Cleanup, Organise, Privacy", "User manual", "Cleanup never deletes permanently: trashed files go to data/trash/ and can be restored.");
    const cols = [
      [fa.FaTrashAlt, "Cleanup tab", ["Press Analyse", "Review duplicates, largest files and old media", "Select files, then move to trash", "Reversible: data/trash/"]],
      [fa.FaLightbulb, "Organise (AI) tab", ["Analyse and preview shows the exact payload", "Inspect it: nothing is sent yet", "Send redacted preview to cloud AI", "Read the suggestions"]],
      [fa.FaShieldAlt, "Privacy tab", ["Paste any text into the playground", "Press Redact", "See what would be detected and its placeholder", "Use it to test your own data"]],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05;
      card(s, "Tab card " + (i + 1), x, 1.25, 2.9, 3.75);
      await iconCircle(s, cols[i][1] + " icon", cols[i][0], x + 0.2, 1.4, 0.6, i === 1 ? C.accent2 : C.accent1, i === 1 ? HEX.navy : "FFFFFF");
      T(s, cols[i][1], { x: x + 0.95, y: 1.5, w: 1.9, h: 0.4, fontSize: 15, bold: true });
      T(s, bullets(cols[i][2]), { x: x + 0.2, y: 2.25, w: 2.55, h: 2.6, fontSize: 13 });
    }
  }

  // ============ 21. CLI CHEAT SHEET ============
  {
    const s = content("Command cheat sheet", "User manual", "All commands need `source env.sh` first. make targets wrap the same commands.");
    s.addTable([
      [th("Command"), th("Purpose")],
      [td("python -m me3 serve --port 8765", { fontFace: "Courier New", fontSize: 11 }), td("Start the web app and API")],
      [td("python -m me3 index <folder>", { fontFace: "Courier New", fontSize: 11 }), td("Index a folder from the terminal (--no-embed skips embeddings)")],
      [td("python -m me3 search \"query\"", { fontFace: "Courier New", fontSize: 11 }), td("Search from the terminal")],
      [td("python -m me3 add-sftp <host> ...", { fontFace: "Courier New", fontSize: 11 }), td("Register an SFTP / NAS source")],
      [td("python -m me3 gdrive-auth", { fontFace: "Courier New", fontSize: 11 }), td("Authorise Google Drive (browser consent)")],
      [td("python -m me3 add-gdrive", { fontFace: "Courier New", fontSize: 11 }), td("Register the Drive source")],
      [td("make test / lint / build", { fontFace: "Courier New", fontSize: 11 }), td("Run the 17 tests, ruff, or build the wheel")],
    ], { x: 0.5, y: 1.2, w: 9.0, colW: [4.0, 5.0], rowH: 0.45, border: { type: "solid", pt: 0.75, color: "C9D6DC" }, fill: { color: C.background1 }, margin: 0.08 });
    T(s, "Tip: find the server with  ss -ltnp | grep :8765  rather than pkill -f.", { x: 0.5, y: 4.7, w: 9.0, h: 0.35, fontSize: 13, color: C.text2 });
  }

  // ============ 22. STATUS / NEXT ============
  {
    const s = pres.addSlide({ masterName: "DARK_DIVIDER", sectionTitle: "User manual" });
    s.addText("Status and next steps", { placeholder: "title" });
    const cols = [["Working", C.accent4, ["Live index, hybrid search, NL filters", "SFTP tested end to end", "Privacy gate, cleanup, 17 tests passing"]],
      ["Known limits", C.accent2, ["Drive not yet tested on a real account", "Image search verified on synthetic scenes", "SFTP passwords stored in the local DB"]],
      ["Next", C.accent1, ["Validate on a real ~/Documents and ~/Pictures", "Live Drive and cloud AI tests", "Better embedding model, OCR, SMB"]]];
    for (let i = 0; i < 3; i++) {
      const x = 0.6 + i * 3.0;
      T(s, cols[i][0], { x, y: 3.1, w: 2.8, h: 0.35, fontSize: 18, bold: true, color: cols[i][1] === C.accent1 ? C.accent1 : cols[i][1] });
      T(s, bullets(cols[i][2], { color: C.background1 }), { x, y: 3.5, w: 2.8, h: 1.6, fontSize: 13, color: C.background1 });
    }
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
