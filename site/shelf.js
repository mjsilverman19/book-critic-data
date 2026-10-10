// Shelf and For you. The shelf lives in this browser's localStorage as { slug: { v, t } },
// where v is the reader's rating on the site's scale (4 rave … 1 pan, 0 want to read) and t the time it was set.
// For you ranks unshelved books by critic affinity: critics whose ratings track the reader's vote for the books they
// rated above their own average and against those they rated below it. Everything runs on the data index.json already loads.
(() => {
  const KEY = 'bookmarks-shelf';
  const MID = 2.5;     // midpoint of the 1–4 scale: rave +1.5 … pan −1.5
  const SHRINK = 3;    // affinity is divided by (shared books + SHRINK), so one shared book counts for little
  const DAMP = 1;      // added to the evidence weight when turning a candidate's votes into a fit score
  const QUALITY = 1;   // weight of the book's adjusted mean in the final score
  const AUTHOR = 0.15; // bonus per point of liking for an author already on the shelf (capped at 3)
  const CHOICES = [[4, 'rave'], [3, 'positive'], [2, 'mixed'], [1, 'pan'], [0, 'want to read']];

  let shelf = {};
  try { shelf = JSON.parse(localStorage.getItem(KEY)) || {}; } catch { shelf = {}; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(shelf)); } catch {} };
  const yours = v => v ? LABEL[v] : 'want to read';
  const day = t => t ? new Date(t).toISOString().slice(0, 10) : '';

  // ---- rating control on the book page ----
  function mine(slug) {
    const cur = shelf[slug]?.v;
    return 'Yours ' + CHOICES.map(([v, l]) =>
      `<button type="button" class="tx${cur === v ? ' on' : ''}" data-rate="${v}" aria-pressed="${cur === v}">${l}</button>`).join(' · ');
  }
  const book = V.book;
  V.book = slug => {
    const done = book(slug);
    const meta = document.querySelector('#head .meta');
    if (meta) meta.insertAdjacentHTML('beforeend', `<br><span id="mine">${mine(slug)}</span>`);
    return done;
  };
  $('#head').addEventListener('click', e => {
    const btn = e.target.closest('[data-rate]');
    if (btn) {
      const v = +btn.dataset.rate;
      if (shelf[S.arg]?.v === v) delete shelf[S.arg];
      else shelf[S.arg] = { v, t: Date.now() };
      save();
      $('#mine').innerHTML = mine(S.arg);
      return;
    }
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'export') exportShelf();
    if (act === 'import') importShelf();
  });

  // ---- reviews grouped by book and by reviewer, rebuilt when the source filter changes R ----
  // A review's reviewer is its critic, or its outlet when unsigned (Kirkus, Publishers Weekly).
  let builtFor = null, byBook, byRev;
  function index() {
    if (builtFor === R) return;
    builtFor = R; byBook = new Map(); byRev = new Map();
    const push = (m, k, r) => { const a = m.get(k); a ? a.push(r) : m.set(k, [r]); };
    for (const r of R) {
      const e = r.c || r.o;
      if (!r.v || !e || e.mean == null) continue;
      push(byBook, r.b, r); push(byRev, e, r);
    }
  }

  function recommend() {
    index();
    const rated = Object.entries(shelf).filter(([s, x]) => x.v && bySlug[s]);
    // affinity: does the critic rate above their own average the books you rate above the midpoint?
    const aff = new Map();
    for (const [s, { v: u }] of rated) {
      for (const r of byBook.get(bySlug[s]) || []) {
        const e = r.c || r.o;
        const a = aff.get(e) || aff.set(e, { e, s: 0, n: 0 }).get(e);
        a.s += (u - MID) * (r.v - e.mean); a.n++;
      }
    }
    const acc = new Map();
    const slot = b => acc.get(b) || acc.set(b, { s: 0, w: 0, why: [], au: 0 }).get(b);
    for (const a of aff.values()) {
      a.w = a.s / (a.n + SHRINK);
      if (a.w <= 0) continue; // only critics who agree with you vote, so every reason shown is one
      for (const r of byRev.get(a.e)) {
        if (shelf[r.b.slug]) continue;
        const c = a.w * (r.v - a.e.mean), x = slot(r.b);
        x.s += c; x.w += Math.abs(a.w);
        if (c > 0) x.why.push([c, a.e, r.v]);
      }
    }
    const au = {};
    for (const [s, { v }] of rated) { const b = bySlug[s]; if (b.aut) au[b.aut] = (au[b.aut] || 0) + v - MID; }
    for (const b of B) if (b.aut && au[b.aut] > 0 && b.n && !shelf[b.slug]) slot(b).au = Math.min(au[b.aut], 3);
    const rows = [];
    for (const [b, x] of acc) {
      const fit = x.s / (x.w + DAMP);
      if (fit <= 0 && !x.au) continue;
      x.why.sort((p, q) => q[0] - p[0]);
      rows.push({ ...b, b, fit, au: x.au, why: x.why.slice(0, 2),
        score: fit + QUALITY * ((b.adj ?? 3.27) - 3.27) + AUTHOR * x.au });
    }
    const closest = [...aff.values()].filter(a => a.w > 0 && a.n >= 2).sort((p, q) => q.w - p.w).slice(0, 5);
    return { rows, closest, rated: rated.length };
  }

  const who = e => cByName[e.name] === e ? cLink(e) : oLink(e);
  const why = r => [
    ...r.why.map(([, e, v]) => `${who(e)} <span class="d">${LABEL[v]}</span>`),
    ...(r.au ? ['<span class="d">author on your shelf</span>'] : []),
  ].join(', ');

  // ---- views ----
  const authorCol = { k: 'author', label: 'Author', cls: 'desk', f: r => r.author ? `<span class="f" data-fk="a" data-fv="${esc(r.aut)}" title="Show only ${esc(r.aut)}">${esc(r.author)}</span>` : '' };

  V.shelf = () => {
    const rows = Object.entries(shelf).filter(([s]) => bySlug[s]).map(([s, x]) => ({ ...bySlug[s], mine: x.v, t: x.t }));
    head(`<div class="meta">${int(rows.length)} ${rows.length === 1 ? 'book' : 'books'}, kept in this browser · <button type="button" class="tx" data-act="export">export</button> · <button type="button" class="tx" data-act="import">import</button></div>`);
    table([
      { k: 'title', label: 'Title', f: titleCell },
      authorCol,
      { k: 'date', label: 'Date', cls: 'nw', f: dateCell },
      { k: 'mine', label: 'Yours', num: 1, v: r => r.mine || null, f: r => r.mine ? LABEL[r.mine] : '<span class="d">want to read</span>' },
      { k: 'n', label: 'Reviews', num: 1 },
      { k: 'mean', label: 'Mean', num: 1, f: r => f2(r.mean) },
      { k: 'adj', label: 'Adjusted', num: 1, tip: TIP.adj, f: r => f2(r.adj) },
      { k: 't', label: 'Added', num: 1, cls: 'nw', f: r => day(r.t) },
    ], rows, { sort: 't', noun: 'books', min: 1, empty: () =>
      !rows.length ? 'Nothing on your shelf yet. Open any book and choose a rating to add it.'
      : S.q ? `No matches on your shelf. <a href="${href('books', '', { q: S.q })}">Search all books</a>`
      : 'No matches' });
  };

  V.foryou = () => {
    const { rows, closest, rated } = recommend();
    head(rated ? `<div class="meta">From ${int(rated)} rated ${rated === 1 ? 'book' : 'books'}${closest.length ? ' · closest critics ' + closest.map(a => who(a.e)).join(', ') : ''}</div>` : '');
    table([
      { k: 'title', label: 'Title', f: titleCell },
      authorCol,
      { k: 'date', label: 'Date', cls: 'nw', f: dateCell },
      { k: 'n', label: 'Reviews', num: 1 },
      { k: 'adj', label: 'Adjusted', num: 1, tip: TIP.adj, f: r => f2(r.adj) },
      { k: 'score', label: 'Match', num: 1, tip: TIP.match, f: r => f2(r.score) },
      { k: 'why', label: 'Why', cls: 'nw', v: r => r.why.length, f: why },
    ], rows, { sort: 'score', noun: 'books', min: 3, empty: () =>
      !rated ? `Rate a few books to see recommendations. Ratings are set on each book page and collected on your <a href="#/shelf">shelf</a>.`
      : 'No matches' });
  };
  TIP.match = 'How much critics whose ratings track yours liked this book relative to their own average, plus a pull toward its adjusted mean and a small bonus for authors you rated well';

  // ---- export and import ----
  function exportShelf() {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(shelf, null, 1)], { type: 'application/json' }));
    a.download = 'bookmarks-shelf.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  function importShelf() {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'application/json,.json';
    input.addEventListener('change', async () => {
      try {
        const data = JSON.parse(await input.files[0].text());
        for (const [s, x] of Object.entries(data)) {
          if (bySlug[s] && Number.isInteger(x?.v) && x.v >= 0 && x.v <= 4) shelf[s] = { v: x.v, t: +x.t || Date.now() };
        }
        save(); route();
      } catch { head('<div class="meta">That file could not be read as a shelf export.</div>'); }
    });
    input.click();
  }
})();
