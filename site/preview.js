(() => {
  const card = document.createElement('aside');
  card.id = 'book-preview';
  card.className = 'book-preview';
  card.setAttribute('role', 'tooltip');
  card.hidden = true;
  document.body.append(card);
  let anchor = null, openTimer, closeTimer, version = 0;
  const linkAt = target => target instanceof Element ? target.closest('[data-book-preview]') : null;

  function close() {
    clearTimeout(openTimer); clearTimeout(closeTimer);
    version++;
    anchor?.removeAttribute('aria-describedby');
    anchor = null;
    card.hidden = true;
  }

  function position() {
    if (!anchor || card.hidden) return;
    const r = anchor.getBoundingClientRect();
    const margin = 12, gap = 8;
    const w = card.offsetWidth, h = card.offsetHeight;
    const below = innerHeight - r.bottom - margin;
    const above = r.top - margin;
    const top = below >= h || below >= above ? r.bottom + gap : r.top - h - gap;
    card.style.left = Math.max(margin, Math.min(r.left, innerWidth - w - margin)) + 'px';
    card.style.top = Math.max(margin, Math.min(top, innerHeight - h - margin)) + 'px';
  }

  function safeCover(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' ? url.href : '';
    } catch { return ''; }
  }

  async function open(link) {
    if (!link.isConnected) return;
    close();
    const b = bySlug[link.dataset.bookPreview];
    if (!b) return;
    anchor = link;
    const current = version;
    link.setAttribute('aria-describedby', card.id);
    card.innerHTML = `<div class="book-preview-top">
      <div class="book-preview-cover">Loading cover…</div>
      <div><h2>${esc(b.title)}</h2><p class="book-preview-author">${esc(b.author)}</p>
      <div class="book-preview-meta">${esc([b.pub, b.date].filter(Boolean).join(' · '))}
      <div class="book-preview-genres">${esc(b.genres.join(', '))}</div></div></div></div>
      <div class="book-preview-summary"><strong>${esc(b.overall || 'Unrated')}</strong> · ${int(b.n)} reviews
      <div class="book-preview-scores">${esc(distTxt(b.dist))}<br>Mean ${f2(b.mean)} · Adjusted ${f2(b.adj)}</div></div>
      <p class="book-preview-description">Loading description…</p>
      <p class="book-preview-hint">Open the title for all reviews · Esc to dismiss</p>`;
    card.hidden = false;
    position();
    try {
      const d = await detail(b.slug);
      if (current !== version || anchor !== link) return;
      card.querySelector('.book-preview-description').textContent = d.d || 'No description available.';
      const cover = card.querySelector('.book-preview-cover');
      const url = safeCover(d.cover);
      cover.textContent = 'No cover available';
      if (url) {
        const img = document.createElement('img');
        img.alt = `Cover of ${b.title}`;
        img.referrerPolicy = 'no-referrer';
        img.addEventListener('error', () => { img.remove(); cover.textContent = 'No cover available'; });
        img.src = url;
        cover.replaceChildren(img);
      }
      position();
    } catch {
      if (current !== version) return;
      card.querySelector('.book-preview-cover').textContent = 'Cover unavailable';
      card.querySelector('.book-preview-description').textContent = 'Preview details unavailable. Open the title to try again.';
    }
  }

  function schedule(link, delay) {
    clearTimeout(closeTimer); clearTimeout(openTimer);
    if (anchor === link && !card.hidden) return;
    // Invalidate any pending response from the previous book immediately.
    close();
    openTimer = setTimeout(() => open(link), delay);
  }
  function scheduleClose() {
    clearTimeout(openTimer);
    closeTimer = setTimeout(close, 180);
  }
  document.addEventListener('pointerover', e => {
    if (e.pointerType === 'touch') return;
    const link = linkAt(e.target);
    if (link && !link.contains(e.relatedTarget)) schedule(link, 250);
    if (card.contains(e.target)) clearTimeout(closeTimer);
  });
  document.addEventListener('pointerout', e => {
    const link = linkAt(e.target);
    if ((link && !link.contains(e.relatedTarget)) || (card.contains(e.target) && !card.contains(e.relatedTarget))) {
      if (!card.contains(e.relatedTarget) && !anchor?.contains(e.relatedTarget)) scheduleClose();
    }
  });
  document.addEventListener('focusin', e => { const link = linkAt(e.target); if (link) schedule(link, 0); });
  document.addEventListener('focusout', e => { if (linkAt(e.target)) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
  document.addEventListener('click', close);
  addEventListener('hashchange', close);
  addEventListener('resize', close);
  document.addEventListener('scroll', e => { if (!card.contains(e.target)) close(); }, true);
  new MutationObserver(() => { if (anchor && !anchor.isConnected) close(); })
    .observe(document.querySelector('#out'), { childList: true, subtree: true });
})();
