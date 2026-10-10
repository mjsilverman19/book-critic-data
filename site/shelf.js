// Shelf, For you and Closest critics. The shelf lives in this browser's localStorage as { slug: { v, t } },
// where v is the reader's rating on the site's scale (4 rave … 1 pan, 0 want to read) and t the time it was set.
//
// The model, all computed in the browser from the reviews index.json already loads:
//   1. Baseline. Every rated review is split into global mean + reviewer lean + book quality, fitted by
//      regularized alternating means. Book quality is the consensus with each reviewer's leniency removed,
//      and reviewer lean is how much kinder or harsher a critic is than others on the same books.
//   2. Reader. The reader gets a lean of their own, and each rated book a residual: how much more or less the
//      reader liked it than the baseline expects.
//   3. Critic similarity. Over the books both have rated, a shrunk correlation of the reader's residuals with
//      the critic's. Only critics with two or more shared books and a positive score count as neighbors.
//   4. Likely rating. Baseline for the reader plus the neighbors' residuals on the book, weighted by similarity
//      and shrunk toward zero when few neighbors reviewed it.
//   5. Taste votes. Every critic who reviewed a book you rated is weighted by how closely they matched your
//      rating, damped by the square root of their review count. Their raves of other books count +1 and their
//      pans −1. This is the strongest signal for finding books you would want.
//   6. Ranking. Likely rating + 2 × taste votes + genre share + liked authors, with repeat authors pushed down.
//   7. Critics to follow. Signed critics with 5+ reviews who came within a step of you on every shared book,
//      listed with their raves you have not shelved.
// Tested offline by treating 150 critics as readers (some of their ratings as the shelf, the rest hidden):
// the taste votes roughly double the share of hidden raves found in the top 100 compared with the version
// before them, and the leniency-adjusted baseline orders hidden books better than the adjusted mean.
(() => {
  const KEY = 'bookmarks-shelf';
  const LB = 5, LC = 10;   // shrinkage for book quality and reviewer lean (in reviews' worth of zero)
  const LU = 3;            // shrinkage for the reader's lean
  const ALPHA = 0.5;       // added to each sum of squares in the similarity, damping one-book coincidences
  const LS = 3;            // similarity is scaled by shared / (shared + LS)
  const MIN_SHARED = 2;    // shared books before a critic counts as a neighbor
  const BETA = 3;          // shrinks the neighbors' adjustment toward zero when their evidence is thin
  const W_TASTE = 2, W_GENRE = 0.5, W_AUTHOR = 0.3, W_REPEAT = 0.15;
  const PICKS = 25;        // recommendations shown at a time beneath the shelf
  const CRITICS = 10;      // critics to follow listed beneath the shelf
  const CHOICES = [[4, 'rave'], [3, 'positive'], [2, 'mixed'], [1, 'pan'], [0, 'want to read']];

  let shelf = {};
  try { shelf = JSON.parse(localStorage.getItem(KEY)) || {}; } catch { shelf = {}; }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(shelf)); } catch {} };
  const yours = v => v ? LABEL[v] : 'want to read';
  const day = t => t ? new Date(t).toISOString().slice(0, 10) : '';

  // ---- rating control on the book page ----
  function mine(slug) {
    const cur = shelf[slug]?.v;
    // the same bare select as the genre and year filters: dim until set, then full color
    return (cur == null ? '' : 'yours ') + `<select id="rate" aria-label="Your rating"${cur == null ? '' : ' class="set"'}>`
      + `<option value="">${cur == null ? 'rate it' : 'remove'}</option>`
      + CHOICES.map(([v, l]) => `<option value="${v}"${cur === v ? ' selected' : ''}>${l}</option>`).join('') + '</select>';
  }
  const book = V.book;
  V.book = slug => {
    const done = book(slug);
    const meta = document.querySelector('#head .meta');
    if (meta) meta.insertAdjacentHTML('beforeend', ` · <span id="mine">${mine(slug)}</span>`);
    return done;
  };
  $('#head').addEventListener('change', e => {
    if (e.target.id !== 'rate') return;
    const v = e.target.value;
    if (v === '') delete shelf[S.arg];
    else shelf[S.arg] = { v: +v, t: shelf[S.arg]?.t || Date.now() };
    save();
    $('#mine').innerHTML = mine(S.arg);
  });
  $('#head').addEventListener('click', e => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'export') exportShelf();
    if (act === 'import') importShelf();
  });

  // ---- review arrays and baseline, rebuilt when the source filter changes R ----
  // A review's reviewer is its critic, or its outlet when unsigned (Kirkus, Publishers Weekly).
  // One review per reviewer and book: some critics appear twice, via Book Marks and a backfill source.
  let M = null;
  function model() {
    if (M?.R === R) return M;
    B.forEach((b, i) => b._i = i);
    const rid = new Map(), ents = [], rb = [], re = [], rv = [], seen = new Set();
    for (const r of R) {
      const e = r.c || r.o;
      if (!r.v || !e) continue;
      let id = rid.get(e);
      if (id === undefined) { id = ents.length; rid.set(e, id); ents.push(e); }
      const k = id * B.length + r.b._i;
      if (seen.has(k)) continue;
      seen.add(k); rb.push(r.b._i); re.push(id); rv.push(r.v);
    }
    const n = rv.length, NB = B.length, NE = ents.length;
    const nb = new Float64Array(NB), ne = new Float64Array(NE), byBook = Array.from({ length: NB }, () => []), byRev = Array.from({ length: NE }, () => []);
    let mu = 0;
    for (let k = 0; k < n; k++) { nb[rb[k]]++; ne[re[k]]++; mu += rv[k]; byBook[rb[k]].push(k); byRev[re[k]].push(k); }
    mu /= n;
    const bb = new Float64Array(NB), be = new Float64Array(NE);
    for (let it = 0; it < 6; it++) {
      const sb = new Float64Array(NB), se = new Float64Array(NE);
      for (let k = 0; k < n; k++) sb[rb[k]] += rv[k] - mu - be[re[k]];
      for (let i = 0; i < NB; i++) bb[i] = sb[i] / (nb[i] + LB);
      for (let k = 0; k < n; k++) se[re[k]] += rv[k] - mu - bb[rb[k]];
      for (let i = 0; i < NE; i++) be[i] = se[i] / (ne[i] + LC);
    }
    const res = new Float64Array(n);
    for (let k = 0; k < n; k++) res[k] = rv[k] - mu - be[re[k]] - bb[rb[k]];
    return M = { R, ents, rid, rb, re, rv, res, nb, ne, bb, be, mu, byBook, byRev };
  }

  function recommend() {
    const m = model(), { rb, re, rv, res, nb, ne, bb, be, mu, byBook, byRev, ents } = m;
    const all = Object.entries(shelf).filter(([s]) => bySlug[s]).map(([s, x]) => ({ b: bySlug[s], i: bySlug[s]._i, u: x.v }));
    const rated = all.filter(x => x.u);
    if (!rated.length) return { rows: [], critics: [], rated: 0 };
    const on = new Set(all.map(x => x.i));

    // reader lean and residuals
    const bu = rated.reduce((s, x) => s + x.u - mu - bb[x.i], 0) / (rated.length + LU);
    for (const x of rated) x.e = x.u - mu - bu - bb[x.i];

    // critic similarity on residuals
    const sims = new Map();
    for (const x of rated) for (const k of byBook[x.i]) {
      const a = sims.get(re[k]) || sims.set(re[k], { id: re[k], e: ents[re[k]], num: 0, xu: 0, xc: 0, n: 0, pairs: [] }).get(re[k]);
      a.num += x.e * res[k]; a.xu += x.e * x.e; a.xc += res[k] * res[k]; a.n++; a.pairs.push([x.b, x.u, rv[k]]);
    }
    const near = [];
    for (const a of sims.values()) {
      a.sim = a.num / Math.sqrt((a.xu + ALPHA) * (a.xc + ALPHA)) * a.n / (a.n + LS);
      a.lean = be[a.id];
      if (a.n >= MIN_SHARED && a.sim > 0) near.push(a);
    }

    // neighbors' residuals on other books
    const S = new Map(), W = new Map(), why = new Map();
    for (const a of near) for (const k of byRev[a.id]) {
      const i = rb[k];
      if (on.has(i)) continue;
      S.set(i, (S.get(i) || 0) + a.sim * res[k]); W.set(i, (W.get(i) || 0) + a.sim);
      if (res[k] > 0) (why.get(i) || why.set(i, []).get(i)).push([a.sim, a.e, rv[k]]); // closest critics first
    }

    // taste critics: everyone who reviewed a book you rated, weighted by how closely their rating matched yours
    // (same 1, one step 2/3, two steps 1/3, opposite 0) and damped by 1 / sqrt(1 + their review count), so a
    // specialist who agreed with you twice outweighs Kirkus agreeing on everything
    const taste = new Map();
    for (const x of rated) for (const k of byBook[x.i]) {
      const t = taste.get(re[k]) || taste.set(re[k], { id: re[k], e: ents[re[k]], w: 0, n: 0, agreed: 0, pairs: [] }).get(re[k]);
      const match = 1 - Math.abs(x.u - rv[k]) / 3;
      t.w += match; t.n++; t.agreed += match >= 0.6; t.pairs.push([x.b, x.u, rv[k]]);
    }
    // their verdicts on books you have not shelved: raves count +1, pans −1
    const vote = new Map(), voters = new Map();
    for (const t of taste.values()) {
      t.w /= Math.sqrt(1 + ne[t.id]);
      for (const k of byRev[t.id]) {
        const i = rb[k];
        if (on.has(i)) continue;
        const c = t.w * (rv[k] - 2.5) / 1.5;
        vote.set(i, (vote.get(i) || 0) + c);
        if (rv[k] >= 3) (voters.get(i) || voters.set(i, []).get(i)).push([c, t.e, rv[k]]);
      }
    }
    let top = 0;
    for (const [i, c] of vote) { const v = c / (nb[i] + 1) ** 0.15; vote.set(i, v); if (Math.abs(v) > top) top = Math.abs(v); }
    const gc = {};
    for (const x of all) for (const g of x.b.genres) gc[g] = (gc[g] || 0) + 1;
    const au = {};
    for (const x of rated) if (x.b.aut) au[x.b.aut] = (au[x.b.aut] || 0) + x.e;

    const rows = [];
    for (let i = 0; i < B.length; i++) {
      if (nb[i] < 3 || on.has(i)) continue;
      const b = B[i];
      const adjust = (S.get(i) || 0) / ((W.get(i) || 0) + BETA);
      const pred = Math.min(4, Math.max(1, mu + bu + bb[i] + adjust));
      const genre = b.genres.length ? Math.max(...b.genres.map(g => gc[g] || 0)) / all.length : 0;
      const liked = b.aut && au[b.aut] > 0 ? 1 : 0;
      const tv = top ? (vote.get(i) || 0) / top : 0;
      const w = [...(why.get(i) || []), ...(voters.get(i) || [])].sort((p, q) => q[0] - p[0])
        .filter((x, j, a) => a.findIndex(y => y[1] === x[1]) === j).slice(0, 2);
      rows.push({ ...b, b, pred, rank: pred + W_TASTE * tv + W_GENRE * genre + W_AUTHOR * liked, why: w, liked, genre });
    }
    rows.sort((p, q) => q.rank - p.rank);
    const seenAut = {};
    for (const r of rows) if (r.aut) { r.rank -= W_REPEAT * (seenAut[r.aut] || 0); seenAut[r.aut] = (seenAut[r.aut] || 0) + 1; }
    rows.sort((p, q) => q.rank - p.rank);

    // critics to follow: signed critics with a body of work (5+ reviews) and raves you have not shelved, who came
    // within a step of you on every book you share. Ranked by agreement, damped more gently than the votes above
    // so a critic who matched you twice in 50 reviews leads one who matched once in 5
    const critics = [...taste.values()].filter(t => cByName[t.e.name] === t.e && ne[t.id] >= 5 && t.agreed === t.n)
      .map(t => {
        const raves = byRev[t.id].filter(k => rv[k] === 4 && !on.has(rb[k])).sort((p, q) => bb[rb[q]] - bb[rb[p]]);
        return { ...t, score: t.pairs.reduce((s, [, u, v]) => s + 1 - Math.abs(u - v) / 3, 0) / Math.log2(2 + ne[t.id]),
          raves: raves.slice(0, 3).map(k => B[rb[k]]), more: raves.length };
      })
      .filter(t => t.more).sort((p, q) => q.score - p.score).slice(0, CRITICS);
    return { rows, critics, rated: rated.length, bu };
  }

  const who = e => cByName[e.name] === e ? cLink(e) : oLink(e);
  const why = r => {
    const out = r.why.map(([, e, v]) => `${who(e)} <span class="d">${LABEL[v]}</span>`);
    if (r.liked) out.push('<span class="d">author you rated well</span>');
    if (!out.length) out.push(`<span class="d">${r.genre >= 0.25 ? 'in your genres' : 'strong consensus'}</span>`);
    return out.join(', ');
  };

  // ---- views ----
  const authorCol = { k: 'author', label: 'Author', cls: 'desk', f: r => r.author ? `<span class="f" data-fk="a" data-fv="${esc(r.aut)}" title="Show only ${esc(r.aut)}">${esc(r.author)}</span>` : '' };

  // a plain table for the sections beneath the shelf; the shelf itself uses the explorer's sortable table
  const plain = (cols, rows) => `<div class="scroll"><table class="plain"><thead><tr>${cols.map(c =>
    `<th class="${c.num ? 'r ' : ''}${c.cls || ''}"${c.tip ? ` title="${esc(c.tip)}"` : ''}>${c.label}</th>`).join('')}</tr></thead><tbody>${rows.map(r =>
    `<tr>${cols.map(c => `<td class="${c.num ? 'r ' : ''}${c.cls || ''}">${c.f(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;

  const pickCols = [
    { label: 'Title', f: titleCell },
    { ...authorCol, f: r => esc(r.author) },
    { label: 'Date', cls: 'nw', f: dateCell },
    { label: 'Reviews', num: 1, f: r => int(r.n) },
    { label: 'Likely', num: 1, tip: TIP.likely, f: r => `${f2(r.pred)} <span class="d">${LABEL[Math.round(r.pred)]}</span>` },
    { label: 'Why', cls: 'nw list', f: why },
  ];
  const short = b => `<a href="#/book/${enc(b.slug)}" data-book-preview="${esc(b.slug)}">${esc(b.title.split(/:\s/)[0])}</a>`;
  const shelfTake = t => t.pairs.slice().sort((p, q) => q[1] - p[1]).slice(0, 3)
    
    .map(([b, u, v]) => `${short(b)} <span class="d">${LABEL[v]}${v === u ? '' : ', you ' + LABEL[u]}</span>`).join(', ') + (t.n > 3 ? ` <span class="d">+${t.n - 3}</span>` : '');
  const criticCols = [
    { label: 'Critic', cls: 'nw', f: t => who(t.e) },
    { label: 'On your shelf', cls: 'nw list', tip: TIP.onshelf, f: shelfTake },
    { label: 'Also raved', cls: 'nw list', tip: TIP.raved, f: t => t.raves.length
      ? t.raves.map(short).join(', ') + (t.more > t.raves.length ? ` <span class="d">+${t.more - t.raves.length}</span>` : '')
      : '<span class="d">nothing else unshelved</span>' },
    { label: 'Reviews', num: 1, f: t => int(t.e.n) },
  ];

  let picks = [], shown = 0;
  function below(count) {
    const { rows, critics, rated } = recommend();
    if (!count) return $('#below').innerHTML = '';
    if (!rated) return $('#below').innerHTML = `<h2 class="sec">For you</h2><p class="empty">Rate a few books to see recommendations. Books marked want to read are not used.</p>`;
    picks = rows; shown = 0;
    $('#below').innerHTML = `<h2 class="sec">For you</h2><div class="meta">Ranked from ${int(rated)} rated ${rated === 1 ? 'book' : 'books'}${rated < 10 ? '. Recommendations sharpen past ten' : ''}</div><div id="picks"></div>`
      + `<h2 class="sec">Critics to follow</h2>`
      + (critics.length ? `<div class="meta">Critics who rated your books similarly</div>${plain(criticCols, critics)}`
        : '<p class="empty">No critic of your rated books agrees with you yet.</p>');
    morePicks();
  }
  function morePicks() {
    shown = Math.min(shown + PICKS, picks.length);
    $('#picks').innerHTML = (picks.length ? plain(pickCols, picks.slice(0, shown)) : '<p class="empty">No recommendations yet.</p>')
      + (shown < picks.length ? `<button type="button" class="tx d more" data-act="picks">${int(Math.min(PICKS, picks.length - shown))} more</button>` : '');
  }
  $('#below').addEventListener('click', e => { if (e.target.closest('[data-act=picks]')) morePicks(); });

  V.shelf = () => {
    const rows = Object.entries(shelf).filter(([s]) => bySlug[s]).map(([s, x]) => ({ ...bySlug[s], mine: x.v, t: x.t }));
    head(`<div class="meta">${int(rows.length)} ${rows.length === 1 ? 'book' : 'books'}</div>`);
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
    below(rows.length);
  };
  V.foryou = () => location.replace('#/shelf'); // the old For you tab now lives beneath the shelf
  Object.assign(TIP, {
    likely: 'Predicted rating on the 1–4 scale: the book’s quality with critic leniency removed, adjusted for your own lean. The list order also weighs how the critics who matched you on your books rated it, your genres, and authors you liked',
    onshelf: 'This critic’s ratings of books you rated, with yours where they differ',
    raved: 'This critic’s raves you have not shelved, best-regarded first',
  });

  // ---- export and import ----
  function exportShelf() {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(shelf, null, 1)], { type: 'application/json' }));
    a.download = 'shelf.json';
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
