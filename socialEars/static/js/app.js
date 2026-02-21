/* socialEars — frontend */

const API = '';
let keywords    = [];
let sources     = new Set(['reddit', 'hackernews']);
let subreddits  = [];        // all available
let selectedSubs = new Set();
let activeRunId  = null;
let pollTimer    = null;
let activeTab    = 'pain';

// ── Boot ──────────────────────────────────────────────────────────────────────
async function boot() {
    await loadSubreddits();
    await loadHistory();
    bindKeywordInput();
    bindSourceToggles();
    bindSubToggleAll();
    document.getElementById('run-btn').addEventListener('click', startRun);
}

// ── Subreddits ────────────────────────────────────────────────────────────────
async function loadSubreddits() {
    try {
        const data = await apiFetch('/api/subreddits');
        subreddits = data;
        selectedSubs = new Set(data.map(s => s.name)); // all selected by default
        renderSubredditList();
    } catch(e) { console.error('Failed to load subreddits', e); }
}

function renderSubredditList() {
    const el = document.getElementById('subreddit-list');
    el.innerHTML = subreddits.map(s => `
        <div class="subreddit-item">
            <input type="checkbox" id="sub-${s.name}" ${selectedSubs.has(s.name) ? 'checked' : ''}
                   onchange="toggleSub('${s.name}', this.checked)">
            <label for="sub-${s.name}">${s.label}</label>
            <span class="personas">${s.personas.join(' · ')}</span>
        </div>
    `).join('');
}

function toggleSub(name, checked) {
    if (checked) selectedSubs.add(name);
    else selectedSubs.delete(name);
}

function bindSubToggleAll() {
    document.getElementById('sub-toggle-all').addEventListener('click', () => {
        const allSelected = selectedSubs.size === subreddits.length;
        if (allSelected) selectedSubs.clear();
        else subreddits.forEach(s => selectedSubs.add(s.name));
        renderSubredditList();
    });
}

// ── Keyword chip input ────────────────────────────────────────────────────────
function bindKeywordInput() {
    const input = document.getElementById('keyword-input');
    const wrap  = document.getElementById('chip-wrap');

    wrap.addEventListener('click', () => input.focus());

    input.addEventListener('keydown', e => {
        if ((e.key === 'Enter' || e.key === ',') && input.value.trim()) {
            e.preventDefault();
            addKeyword(input.value.trim().replace(/,/g, ''));
            input.value = '';
        } else if (e.key === 'Backspace' && !input.value && keywords.length) {
            removeKeyword(keywords[keywords.length - 1]);
        }
    });
}

function addKeyword(kw) {
    kw = kw.trim();
    if (!kw || keywords.includes(kw)) return;
    keywords.push(kw);
    renderChips();
}

function removeKeyword(kw) {
    keywords = keywords.filter(k => k !== kw);
    renderChips();
}

function renderChips() {
    const wrap  = document.getElementById('chip-wrap');
    const input = document.getElementById('keyword-input');
    wrap.innerHTML = '';
    keywords.forEach(kw => {
        const chip = document.createElement('div');
        chip.className = 'chip';
        chip.innerHTML = `<span>${esc(kw)}</span><span class="chip-remove" onclick="removeKeyword('${esc(kw)}')">×</span>`;
        wrap.appendChild(chip);
    });
    wrap.appendChild(input);
    input.focus();
}

// ── Source toggles ────────────────────────────────────────────────────────────
function bindSourceToggles() {
    document.querySelectorAll('.source-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const src = btn.dataset.source;
            if (sources.has(src)) {
                if (sources.size === 1) return; // keep at least one
                sources.delete(src);
                btn.classList.remove('active');
            } else {
                sources.add(src);
                btn.classList.add('active');
            }
            // Show/hide subreddit section
            document.getElementById('subreddit-section').style.display =
                sources.has('reddit') ? '' : 'none';
        });
    });
}

// ── Run ───────────────────────────────────────────────────────────────────────
async function startRun() {
    if (!keywords.length) {
        alert('Add at least one keyword first.');
        return;
    }

    const btn = document.getElementById('run-btn');
    btn.disabled = true;

    const body = {
        keywords,
        subreddits: sources.has('reddit') ? Array.from(selectedSubs) : [],
        sources:    Array.from(sources),
        time_filter: document.getElementById('time-filter').value,
    };

    try {
        const res = await apiFetch('/api/runs', { method: 'POST', json: body });
        activeRunId = res.run_id;
        await loadHistory();
        showRunProgress(activeRunId);
        startPolling(activeRunId);
    } catch(e) {
        btn.disabled = false;
        alert('Failed to start run: ' + e.message);
    }
}

function startPolling(runId) {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
        try {
            const run = await apiFetch(`/api/runs/${runId}`);
            if (run.status === 'done') {
                clearInterval(pollTimer);
                await loadHistory();
                await showReport(runId);
                document.getElementById('run-btn').disabled = false;
            } else if (run.status === 'error') {
                clearInterval(pollTimer);
                await loadHistory();
                showError(run.error_msg || 'An error occurred during analysis.');
                document.getElementById('run-btn').disabled = false;
            } else {
                // Update progress display
                updateProgress(run);
            }
        } catch(e) { console.error('Poll error', e); }
    }, 2500);
}

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
    const runs = await apiFetch('/api/runs');
    const el = document.getElementById('run-history');
    if (!runs.length) { el.innerHTML = '<div style="font-size:12px;color:var(--text-dim)">No runs yet</div>'; return; }
    el.innerHTML = runs.map(r => {
        const kws   = r.keywords.join(', ');
        const date  = new Date(r.created_at * 1000).toLocaleDateString();
        const posts = r.post_count ? `${r.post_count} posts` : '';
        const cls   = r.id === activeRunId ? ' active' : '';
        return `
        <div class="run-item${cls}" onclick="loadRun('${r.id}')">
            <div class="run-item-keywords" title="${esc(kws)}">${esc(kws)}</div>
            <div class="run-item-meta">
                <span class="run-status ${r.status}">${r.status}</span>
                <span>${date}</span>
                ${posts ? `<span>${posts}</span>` : ''}
            </div>
        </div>`;
    }).join('');
}

async function loadRun(runId) {
    activeRunId = runId;
    await loadHistory(); // refresh active highlight
    const run = await apiFetch(`/api/runs/${runId}`);
    if (run.status === 'done') {
        await showReport(runId);
    } else if (run.status === 'running' || run.status === 'pending') {
        showRunProgress(runId);
        startPolling(runId);
    } else if (run.status === 'error') {
        showError(run.error_msg || 'Run failed.');
    }
}

// ── Display ───────────────────────────────────────────────────────────────────
function showRunProgress(runId) {
    document.getElementById('main-title').textContent = 'Collecting & analysing…';
    document.getElementById('main-meta').textContent  = '';
    document.getElementById('main-body').innerHTML = `
        <div class="progress-wrap">
            <div class="progress-label">
                <span class="spinner"></span>
                <span id="progress-msg">Fetching posts from Reddit and Hacker News…</span>
            </div>
            <div class="progress-bar-bg"><div class="progress-bar" id="progress-bar" style="width:15%"></div></div>
        </div>
    `;
}

function updateProgress(run) {
    const bar = document.getElementById('progress-bar');
    const msg = document.getElementById('progress-msg');
    if (!bar) return;
    if (run.status === 'running' && run.post_count > 0) {
        bar.style.width = '60%';
        if (msg) msg.textContent = `Collected ${run.post_count} posts — running LLM analysis…`;
    } else {
        bar.style.width = '30%';
    }
}

async function showReport(runId) {
    const [report, run] = await Promise.all([
        apiFetch(`/api/runs/${runId}/report`),
        apiFetch(`/api/runs/${runId}`),
    ]);

    const kws = run.keywords.join(', ');
    document.getElementById('main-title').textContent = kws;
    document.getElementById('main-meta').innerHTML =
        `<span>${report.post_count} posts analysed</span>
         <span>${run.sources.join(' + ')}</span>
         <span>${new Date(run.created_at * 1000).toLocaleDateString()}</span>`;

    document.getElementById('main-body').innerHTML = `
        <div class="summary-card">${esc(report.summary)}</div>
        <div class="topic-pills">${(report.top_topics || []).map(t => `<span class="topic-pill">${esc(t)}</span>`).join('')}</div>
        <div class="report-tabs">
            <button class="tab-btn active" onclick="switchTab('pain',  this)">Pain Points (${report.pain_points.length})</button>
            <button class="tab-btn"        onclick="switchTab('lang',  this)">Language to Steal (${report.language.length})</button>
            <button class="tab-btn"        onclick="switchTab('comp',  this)">Competitive (${report.competitive.length})</button>
            <button class="tab-btn"        onclick="switchTab('posts', this, '${runId}')">Raw Posts</button>
        </div>
        <div id="tab-content">
            ${renderPainPoints(report.pain_points)}
        </div>
    `;
    activeTab = 'pain';
}

function switchTab(tab, btn, runId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeTab = tab;

    // Need current report — refetch only if posts tab
    if (tab === 'posts' && runId) {
        document.getElementById('tab-content').innerHTML = '<div style="color:var(--text-muted);font-size:13px">Loading posts…</div>';
        apiFetch(`/api/runs/${runId}/posts`).then(posts => {
            document.getElementById('tab-content').innerHTML = renderPosts(posts);
        });
        return;
    }

    // For other tabs, grab report from current DOM run
    apiFetch(`/api/runs/${activeRunId}/report`).then(report => {
        const tc = document.getElementById('tab-content');
        if (tab === 'pain') tc.innerHTML = renderPainPoints(report.pain_points);
        if (tab === 'lang') tc.innerHTML = renderLanguage(report.language);
        if (tab === 'comp') tc.innerHTML = renderCompetitive(report.competitive);
    });
}

function renderPainPoints(items) {
    if (!items || !items.length) return '<p style="color:var(--text-muted);font-size:13px">No pain points extracted.</p>';
    return `<div class="pain-grid">${items.map(pp => `
        <div class="pain-card">
            <div class="pain-card-header">
                <div class="pain-card-theme">${esc(pp.theme)}</div>
                <div class="pain-card-badges">
                    <span class="badge badge-freq-${pp.frequency || 'medium'}">${esc(pp.frequency || 'medium')}</span>
                    ${(pp.personas || []).map(p => `<span class="badge badge-persona">${esc(p)}</span>`).join('')}
                </div>
            </div>
            <div class="pain-desc">${esc(pp.description)}</div>
            ${pp.quotes && pp.quotes.length ? `
            <div class="pain-quotes">
                ${pp.quotes.slice(0,3).map(q => `<div class="pain-quote">"${esc(q)}"</div>`).join('')}
            </div>` : ''}
        </div>
    `).join('')}</div>`;
}

function renderLanguage(items) {
    if (!items || !items.length) return '<p style="color:var(--text-muted);font-size:13px">No language patterns extracted.</p>';
    return `<div class="lang-grid">${items.map(l => `
        <div class="lang-card">
            <div class="lang-phrase">${esc(l.phrase)}</div>
            <div class="lang-context">${esc(l.context)}</div>
            <div class="lang-use">✦ ${esc(l.use_in)}</div>
        </div>
    `).join('')}</div>`;
}

function renderCompetitive(items) {
    if (!items || !items.length) return '<p style="color:var(--text-muted);font-size:13px">No competitive signals found.</p>';
    return `<div class="comp-grid">${items.map(c => `
        <div class="comp-card">
            <div>
                <div class="comp-vendor">${esc(c.vendor)}</div>
                <span class="comp-sentiment ${c.sentiment || 'neutral'}">${esc(c.sentiment || 'neutral')}</span>
            </div>
            <div>
                <div class="comp-label">What they say</div>
                <div class="comp-text">${esc(c.what_they_say)}</div>
            </div>
            <div>
                <div class="comp-label">Replica opportunity</div>
                <div class="comp-text">${esc(c.opportunity)}</div>
            </div>
        </div>
    `).join('')}</div>`;
}

function renderPosts(posts) {
    if (!posts || !posts.length) return '<p style="color:var(--text-muted);font-size:13px">No posts found.</p>';
    return `<div class="posts-list">${posts.slice(0, 100).map(p => `
        <div class="post-card">
            <div class="post-card-header">
                <span class="post-source-badge ${p.source}">${p.source === 'hackernews' ? 'HN' : p.subreddit ? 'r/' + p.subreddit : 'Reddit'}</span>
                <div class="post-title">${esc(p.title || '')}</div>
            </div>
            <div class="post-text">${esc((p.text || '').slice(0, 300))}${(p.text || '').length > 300 ? '…' : ''}</div>
            <div class="post-meta">
                <span>↑ ${p.score}</span>
                ${p.num_comments ? `<span>💬 ${p.num_comments}</span>` : ''}
                <span>${(p.created_at || '').slice(0,10)}</span>
                ${p.url ? `<a href="${p.url}" target="_blank" rel="noopener">view →</a>` : ''}
            </div>
        </div>
    `).join('')}</div>`;
}

function showError(msg) {
    document.getElementById('main-title').textContent = 'Run failed';
    document.getElementById('main-body').innerHTML = `
        <div class="error-banner">⚠ ${esc(msg)}</div>
        <p style="font-size:13px;color:var(--text-muted)">Check that your Reddit API credentials are set in .env and the server console for details.</p>
    `;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

async function apiFetch(path, opts = {}) {
    const { method = 'GET', json } = opts;
    const res = await fetch(API + path, {
        method,
        headers: json ? { 'Content-Type': 'application/json' } : {},
        body:    json ? JSON.stringify(json) : undefined,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
    }
    return res.json();
}

// ── Init ──────────────────────────────────────────────────────────────────────
boot();
