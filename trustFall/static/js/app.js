/* trustFall — frontend */

const API = '';
let vendors = [];
let activeVendorId = null;

// ── Boot ──────────────────────────────────────────────────────────────────────
async function boot() {
    document.getElementById('btn-add-vendor').addEventListener('click', () => openModal('modal-add-vendor'));
    document.getElementById('btn-save-vendor').addEventListener('click', saveVendor);
    document.getElementById('btn-view-pending').addEventListener('click', showAllPending);
    await loadVendors();
}

// ── API helper ────────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
    const { method = 'GET', json } = opts;
    const res = await fetch(API + path, {
        method,
        headers: json ? { 'Content-Type': 'application/json' } : {},
        body: json ? JSON.stringify(json) : undefined,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
    }
    return res.json();
}

// ── Vendors ───────────────────────────────────────────────────────────────────
async function loadVendors() {
    vendors = await apiFetch('/api/vendors');
    renderVendorList();
    updatePendingBadge();
}

function renderVendorList() {
    const el = document.getElementById('vendor-list');
    if (!vendors.length) {
        el.innerHTML = '<div style="font-size:12px;color:rgba(255,255,255,0.3);padding:4px 0">No vendors yet</div>';
        return;
    }
    el.innerHTML = vendors.map(v => {
        const pending = v.pending_count || 0;
        const cls = v.id === activeVendorId ? ' active' : '';
        return `
        <div class="vendor-item${cls}" onclick="selectVendor('${v.id}')">
            <div style="display:flex;align-items:center;justify-content:space-between">
                <div class="vendor-item-name">${esc(v.name)}</div>
                ${pending ? `<span class="vendor-pending">${pending}</span>` : ''}
            </div>
            <div class="vendor-item-meta">
                <span>${v.page_count || 0} page${v.page_count !== 1 ? 's' : ''} watched</span>
            </div>
        </div>`;
    }).join('');
}

function updatePendingBadge() {
    const total = vendors.reduce((sum, v) => sum + (v.pending_count || 0), 0);
    const section = document.getElementById('pending-section');
    const badge = document.getElementById('pending-badge');
    if (total > 0) {
        section.style.display = '';
        badge.textContent = `${total} change${total !== 1 ? 's' : ''} awaiting your review`;
    } else {
        section.style.display = 'none';
    }
}

async function saveVendor() {
    const name    = document.getElementById('input-vendor-name').value.trim();
    const website = document.getElementById('input-vendor-website').value.trim();
    const url     = document.getElementById('input-vendor-url').value.trim();
    const notes   = document.getElementById('input-vendor-notes').value.trim();

    if (!name || !website) { alert('Vendor name and website are required.'); return; }

    const btn = document.getElementById('btn-save-vendor');
    btn.disabled = true;
    btn.textContent = 'Adding...';

    try {
        const vendor = await apiFetch('/api/vendors', { method: 'POST', json: { name, website, notes: notes || null } });

        if (url) {
            await apiFetch('/api/pages', {
                method: 'POST',
                json: { vendor_id: vendor.id, url, label: 'Starting Page', suggested_by: 'user' }
            });
        }

        closeModal('modal-add-vendor');
        ['input-vendor-name','input-vendor-website','input-vendor-url','input-vendor-notes']
            .forEach(id => document.getElementById(id).value = '');

        await loadVendors();
        selectVendor(vendor.id);
    } catch(e) {
        alert('Error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Add Vendor';
    }
}

// ── Vendor detail view ────────────────────────────────────────────────────────
async function selectVendor(vendorId) {
    activeVendorId = vendorId;
    renderVendorList();

    const vendor = vendors.find(v => v.id === vendorId);
    document.getElementById('main-title').textContent = vendor?.name || 'Vendor';
    document.getElementById('main-meta').innerHTML = `
        <span>${vendor?.website || ''}</span>
        <button class="btn-icon" onclick="checkAllPages('${vendorId}')">Check all pages now</button>
    `;

    document.getElementById('main-body').innerHTML = '<div class="loading-row"><span class="spinner"></span> Loading...</div>';

    try {
        const [pages, changes] = await Promise.all([
            apiFetch(`/api/vendors/${vendorId}/pages`),
            apiFetch(`/api/changes`),
        ]);

        const vendorChanges = changes.filter(c =>
            pages.some(p => p.id === c.page_id) && c.user_verdict === 'pending'
        );

        document.getElementById('main-body').innerHTML = `
            ${vendorChanges.length ? renderChangesSection(vendorChanges) : ''}
            ${renderPagesSection(pages, vendorId)}
        `;
    } catch(e) {
        document.getElementById('main-body').innerHTML = `<div class="banner banner-error">Failed to load vendor: ${esc(e.message)}</div>`;
    }
}

function renderChangesSection(changes) {
    return `
    <div class="pages-section">
        <div class="pages-section-header">
            <div class="pages-section-title">Pending Review (${changes.length})</div>
        </div>
        ${changes.map(c => renderChangeRow(c)).join('')}
    </div>`;
}

function renderChangeRow(c) {
    const date = new Date(c.detected_at * 1000).toLocaleDateString();
    return `
    <div class="change-row" onclick="openDiff('${c.id}')">
        <div class="change-row-header">
            <span class="badge badge-${c.llm_score}">${c.llm_score}</span>
            <div class="change-summary">${esc(c.diff_summary || 'Change detected — click to review')}</div>
        </div>
        <div class="change-meta">
            <span>${esc(c.label)}</span>
            <span>${date}</span>
            <span style="color:var(--highlight-2);font-style:italic">Click to review →</span>
        </div>
    </div>`;
}

function renderPagesSection(pages, vendorId) {
    return `
    <div class="pages-section">
        <div class="pages-section-header">
            <div class="pages-section-title">Watched Pages (${pages.length})</div>
            <button class="btn-icon" onclick="loadSuggestions('${vendorId}')">+ Find more pages to watch</button>
        </div>
        <div id="suggestions-area"></div>
        ${pages.length ? pages.map(p => renderPageRow(p)).join('') :
            '<div style="font-size:13px;color:var(--grey-medium);padding:8px 0">No pages being watched yet. Click "Find more pages to watch" above.</div>'
        }
    </div>`;
}

function renderPageRow(p) {
    const lastChecked = p.last_checked
        ? 'Last checked ' + new Date(p.last_checked * 1000).toLocaleDateString()
        : 'Not yet checked';
    const lastChanged = p.last_changed
        ? 'Change detected ' + new Date(p.last_changed * 1000).toLocaleDateString()
        : 'No changes detected yet';
    const movedWarning = p.page_moved_flag
        ? '<span class="page-moved-warning">⚠ Page may have moved — verify URL</span>' : '';
    const pending = p.pending_changes > 0
        ? `<span class="badge badge-medium">${p.pending_changes} change${p.pending_changes !== 1 ? 's' : ''} to review</span>` : '';
    const paused = p.status === 'paused'
        ? '<span style="font-size:11px;color:var(--grey-medium);margin-left:4px">(monitoring paused)</span>' : '';

    return `
    <div class="page-row ${p.page_moved_flag ? 'moved' : ''}" id="page-row-${p.id}">
        <div class="page-row-header">
            <div>
                <div class="page-row-label">${esc(p.label)}${paused}</div>
                <div class="page-row-url"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.url)}</a></div>
            </div>
            <div class="page-row-actions">
                <button class="btn-icon" id="check-btn-${p.id}" onclick="checkOnePage('${p.id}')">Check now</button>
                <button class="btn-icon" onclick="openBaselineModal('${p.id}')" title="Paste text from the vendor's page to use as your comparison baseline">Set my baseline</button>
                <button class="btn-icon" onclick="togglePause('${p.id}', '${p.status}')" title="${p.status === 'paused' ? 'Resume monitoring this page' : 'Pause monitoring this page'}">${p.status === 'paused' ? 'Resume' : 'Pause'}</button>
                <button class="btn-icon" onclick="deletePage('${p.id}')" title="Stop watching this page">Stop watching</button>
            </div>
        </div>
        <div class="page-row-footer" id="page-meta-${p.id}">
            <span class="page-meta">${lastChecked}</span>
            <span class="page-meta">${lastChanged}</span>
            ${pending}
            ${movedWarning}
        </div>
        <div id="check-result-${p.id}"></div>
    </div>`;
}

// ── Check pages ───────────────────────────────────────────────────────────────
async function checkOnePage(pageId) {
    const btn = document.getElementById(`check-btn-${pageId}`);
    const resultEl = document.getElementById(`check-result-${pageId}`);
    const metaEl = document.getElementById(`page-meta-${pageId}`);
    if (!btn) return;

    btn.disabled = true;
    btn.textContent = 'Checking...';
    btn.classList.add('checking');
    if (resultEl) resultEl.innerHTML = '<div class="loading-row" style="margin-top:6px"><span class="spinner"></span> Fetching page — this may take a moment...</div>';

    try {
        const result = await apiFetch(`/api/pages/${pageId}/check`, { method: 'POST' });

        // Update the meta line immediately without full page reload
        const now = new Date().toLocaleDateString();
        if (metaEl) {
            const lastChangedText = result.changed
                ? `Change detected ${now}`
                : (metaEl.querySelector('.page-meta:nth-child(2)')?.textContent || 'No changes detected yet');
            metaEl.innerHTML = `
                <span class="page-meta">Last checked ${now}</span>
                <span class="page-meta">${lastChangedText}</span>
                ${result.changed ? `<span class="badge badge-${result.score}">${result.score} change to review</span>` : ''}
                ${result.page_moved ? '<span class="page-moved-warning">⚠ Page may have moved — verify URL</span>' : ''}
            `;
        }

        if (result.error) {
            if (resultEl) resultEl.innerHTML = `<div class="banner banner-error" style="margin-top:8px">
                Could not fetch this page: ${esc(result.error)}
                ${result.blocked ? '<br><em>The site may be blocking automated access.</em>' : ''}
            </div>`;
        } else if (result.baseline) {
            if (resultEl) resultEl.innerHTML = `<div class="banner banner-success" style="margin-top:8px">
                ✓ First snapshot saved as your baseline. Future checks will compare against this version.
            </div>`;
        } else if (result.changed) {
            if (resultEl) resultEl.innerHTML = `<div class="banner banner-warning" style="margin-top:8px">
                <strong>${esc(result.score?.toUpperCase())} significance change detected</strong><br>
                ${esc(result.summary)}
                <br><button class="btn-icon" style="margin-top:8px" onclick="openDiff('${result.event_id}')">Review what changed →</button>
            </div>`;
            await loadVendors();
        } else {
            if (resultEl) resultEl.innerHTML = `<div class="banner banner-success" style="margin-top:8px">✓ No changes since last check.</div>`;
        }
    } catch(e) {
        if (resultEl) resultEl.innerHTML = `<div class="banner banner-error" style="margin-top:8px">Error: ${esc(e.message)}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Check now';
        btn.classList.remove('checking');
    }
}

async function checkAllPages(vendorId) {
    const vendor = vendors.find(v => v.id === vendorId);
    document.getElementById('main-meta').innerHTML = `
        <span>${vendor?.website || ''}</span>
        <span class="loading-row" style="display:inline-flex;gap:6px"><span class="spinner"></span> Checking all pages — please wait...</span>
    `;
    try {
        await apiFetch(`/api/vendors/${vendorId}/check-all`, { method: 'POST' });
        await selectVendor(vendorId);
    } catch(e) {
        alert('Error checking pages: ' + e.message);
        await selectVendor(vendorId);
    }
}

// ── Suggestions ───────────────────────────────────────────────────────────────
async function loadSuggestions(vendorId) {
    const area = document.getElementById('suggestions-area');
    if (!area) return;

    // Toggle off if already showing
    if (area.innerHTML.trim()) { area.innerHTML = ''; return; }

    area.innerHTML = '<div class="loading-row"><span class="spinner"></span> Searching for trust and policy pages...</div>';

    try {
        const suggestions = await apiFetch(`/api/vendors/${vendorId}/suggest`);
        if (!suggestions.length) {
            area.innerHTML = '<div class="banner banner-warning" style="margin-bottom:12px">No additional pages found automatically. You can add URLs manually by editing a vendor.</div>';
            return;
        }

        // Render with checkboxes so user can select multiple and add at once
        area.innerHTML = `
        <div class="suggestions-panel">
            <div class="suggestions-title">
                Suggested pages to watch
                <span style="font-weight:400;color:var(--grey-medium)">— select any you want to add</span>
            </div>
            ${suggestions.map((s, i) => `
            <div class="suggestion-item">
                <input type="checkbox" id="sug-${i}" checked style="flex-shrink:0;accent-color:var(--headline)">
                <label for="sug-${i}" class="suggestion-info" style="cursor:pointer">
                    <div class="suggestion-label">${esc(s.label)}</div>
                    <div class="suggestion-url" title="${esc(s.url)}">${esc(s.url)}</div>
                </label>
                <span class="suggestion-source" title="Found via ${esc(s.source)}">${esc(s.source)}</span>
            </div>`).join('')}
            <div style="display:flex;gap:8px;margin-top:12px;align-items:center">
                <button class="btn-primary" style="width:auto;padding:8px 18px"
                    onclick="addSelectedSuggestions('${vendorId}', ${JSON.stringify(suggestions).replace(/"/g, '&quot;')}, this)">
                    Add selected pages
                </button>
                <button class="btn-secondary" onclick="document.getElementById('suggestions-area').innerHTML=''">Cancel</button>
            </div>
        </div>`;
    } catch(e) {
        area.innerHTML = `<div class="banner banner-error" style="margin-bottom:12px">Error finding suggestions: ${esc(e.message)}</div>`;
    }
}

async function addSelectedSuggestions(vendorId, suggestions, btn) {
    // Collect checked suggestions
    const selected = suggestions.filter((s, i) => {
        const cb = document.getElementById(`sug-${i}`);
        return cb && cb.checked;
    });

    if (!selected.length) { alert('Select at least one page to add.'); return; }

    btn.disabled = true;
    btn.textContent = `Adding ${selected.length} page${selected.length !== 1 ? 's' : ''}...`;

    let added = 0, errors = 0;
    for (const s of selected) {
        try {
            await apiFetch('/api/pages', {
                method: 'POST',
                json: { vendor_id: vendorId, url: s.url, label: s.label, suggested_by: 'tool' }
            });
            added++;
        } catch(e) {
            if (!e.message.includes('already')) errors++;
        }
    }

    const area = document.getElementById('suggestions-area');
    if (area) {
        area.innerHTML = `<div class="banner banner-success" style="margin-bottom:12px">
            ✓ Added ${added} page${added !== 1 ? 's' : ''} to your watchlist.
            ${errors ? `${errors} could not be added.` : ''}
        </div>`;
    }

    await selectVendor(vendorId);
}

// ── Diff modal ────────────────────────────────────────────────────────────────
async function openDiff(eventId) {
    const modal  = document.getElementById('modal-diff');
    const body   = document.getElementById('modal-diff-body');
    const footer = document.getElementById('modal-diff-footer');
    modal.style.display = 'flex';
    body.innerHTML = '<div class="loading-row"><span class="spinner"></span> Loading change details...</div>';
    footer.innerHTML = '';

    try {
        const c = await apiFetch(`/api/changes/${eventId}`);
        document.getElementById('modal-diff-title').textContent = `${c.vendor_name} — ${c.label}`;

        // Compute line diff for display
        const added = [], removed = [];
        if (c.prev_text && c.curr_text) {
            const prevSet = new Set(c.prev_text.split('\n'));
            const currSet = new Set(c.curr_text.split('\n'));
            c.curr_text.split('\n').forEach(l => { if (l.trim() && !prevSet.has(l)) added.push(l); });
            c.prev_text.split('\n').forEach(l => { if (l.trim() && !currSet.has(l)) removed.push(l); });
        }

        body.innerHTML = `
        <div class="diff-section">
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
                <span class="badge badge-${c.llm_score}">${c.llm_score} significance</span>
                <span style="font-size:12px;color:var(--grey-medium)">Detected ${new Date(c.detected_at * 1000).toLocaleDateString()}</span>
                <a href="${esc(c.url)}" target="_blank" rel="noopener" style="font-size:11px;color:var(--highlight-2)">View live page ↗</a>
            </div>
            <div style="font-size:14px;color:var(--body-text);line-height:1.6;margin-bottom:10px;font-weight:500">${esc(c.diff_summary)}</div>
            <div style="font-size:12px;color:var(--grey-medium);font-style:italic;margin-bottom:16px;line-height:1.5">${esc(c.llm_reasoning)}</div>
        </div>

        ${removed.length ? `
        <div class="diff-section">
            <div class="diff-section-title">Text removed (${removed.length} line${removed.length !== 1 ? 's' : ''})</div>
            ${removed.slice(0,25).map(l => `<div class="diff-removed">- ${esc(l.trim())}</div>`).join('')}
            ${removed.length > 25 ? `<div style="font-size:11px;color:var(--grey-medium);margin-top:4px">…and ${removed.length - 25} more lines</div>` : ''}
        </div>` : ''}

        ${added.length ? `
        <div class="diff-section">
            <div class="diff-section-title">Text added (${added.length} line${added.length !== 1 ? 's' : ''})</div>
            ${added.slice(0,25).map(l => `<div class="diff-added">+ ${esc(l.trim())}</div>`).join('')}
            ${added.length > 25 ? `<div style="font-size:11px;color:var(--grey-medium);margin-top:4px">…and ${added.length - 25} more lines</div>` : ''}
        </div>` : ''}

        ${!added.length && !removed.length ? `
        <div class="banner banner-warning">Could not compute line diff — download snapshots below to compare manually.</div>` : ''}
        `;

        footer.innerHTML = `
            <a href="/api/changes/${eventId}/download?version=previous" class="btn-icon" download>↓ Download previous version</a>
            <a href="/api/changes/${eventId}/download?version=current"  class="btn-icon" download>↓ Download current version</a>
            <button class="btn-secondary" onclick="setVerdict('${eventId}', 'dismissed')">Dismiss — not significant</button>
            <button class="btn-primary" style="width:auto;padding:9px 20px" onclick="setVerdict('${eventId}', 'confirmed')">Confirm — this matters</button>
        `;
    } catch(e) {
        body.innerHTML = `<div class="banner banner-error">Error loading change: ${esc(e.message)}</div>`;
    }
}

async function setVerdict(eventId, verdict) {
    try {
        await apiFetch(`/api/changes/${eventId}/verdict`, { method: 'PATCH', json: { verdict } });
        closeModal('modal-diff');
        await loadVendors();
        if (activeVendorId) await selectVendor(activeVendorId);
    } catch(e) {
        alert('Error: ' + e.message);
    }
}

// ── All pending view ──────────────────────────────────────────────────────────
async function showAllPending() {
    activeVendorId = null;
    renderVendorList();
    document.getElementById('main-title').textContent = 'All Pending Changes';
    document.getElementById('main-meta').innerHTML = '';
    document.getElementById('main-body').innerHTML = '<div class="loading-row"><span class="spinner"></span> Loading...</div>';

    try {
        const changes = await apiFetch('/api/changes?verdict=pending');
        if (!changes.length) {
            document.getElementById('main-body').innerHTML = `
                <div class="empty-state"><div class="icon">✓</div><p>Nothing pending review. You're all caught up.</p></div>`;
            return;
        }
        document.getElementById('main-body').innerHTML = changes.map(c => renderChangeRow(c)).join('');
    } catch(e) {
        document.getElementById('main-body').innerHTML = `<div class="banner banner-error">Error: ${esc(e.message)}</div>`;
    }
}

// ── Page controls ─────────────────────────────────────────────────────────────
async function togglePause(pageId, currentStatus) {
    try {
        await apiFetch(`/api/pages/${pageId}/pause`, { method: 'PATCH' });
        if (activeVendorId) await selectVendor(activeVendorId);
    } catch(e) { alert('Error: ' + e.message); }
}

async function deletePage(pageId) {
    if (!confirm('Stop watching this page? This cannot be undone.')) return;
    try {
        await apiFetch(`/api/pages/${pageId}`, { method: 'DELETE' });
        if (activeVendorId) await selectVendor(activeVendorId);
    } catch(e) { alert('Error: ' + e.message); }
}

// ── Modal helpers ─────────────────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

document.addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.style.display = 'none';
    }
});

// ── Paste baseline ────────────────────────────────────────────────────────────
let baselinePageId = null;

function openBaselineModal(pageId) {
    baselinePageId = pageId;
    document.getElementById('baseline-text').value = '';
    document.getElementById('baseline-date').value = '';
    document.getElementById('baseline-char-count').textContent = '';
    openModal('modal-baseline');

    // Live char count as user pastes
    document.getElementById('baseline-text').oninput = function() {
        const n = this.value.trim().length;
        document.getElementById('baseline-char-count').textContent =
            n ? `${n.toLocaleString()} characters` : '';
    };

    document.getElementById('btn-save-baseline').onclick = saveBaseline;
}

async function saveBaseline() {
    const text = document.getElementById('baseline-text').value.trim();
    const date = document.getElementById('baseline-date').value || null;

    if (!text) { alert('Please paste some text first.'); return; }
    if (text.length < 100) { alert('That looks too short to be a policy page — please paste more text.'); return; }

    const btn = document.getElementById('btn-save-baseline');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
        const result = await apiFetch(`/api/pages/${baselinePageId}/baseline`, {
            method: 'POST',
            json: { text, as_of_date: date }
        });

        closeModal('modal-baseline');

        // Show confirmation on the page row
        const resultEl = document.getElementById(`check-result-${baselinePageId}`);
        if (resultEl) resultEl.innerHTML = `<div class="banner banner-success" style="margin-top:8px">
            ✓ Baseline saved (${result.char_count.toLocaleString()} characters${date ? ', as of ' + new Date(date).toLocaleDateString() : ''}).
            Future "Check now" runs will compare against this version.
        </div>`;

    } catch(e) {
        alert('Error saving baseline: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Save as baseline';
    }
}

// ── Escape ────────────────────────────────────────────────────────────────────
function esc(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

boot();
