'use strict';

class PRPitchyApp {
    constructor() {
        this.newsFiles = [];
        this.brandFiles = [];
        this.selectedTier = 2;
        this.results = null;
        this.initUploadZones();
        this.initTierButtons();
        this.loadPublications();
    }

    // ── File upload zones ──────────────────────────────────────────────
    initUploadZones() {
        this.initZone('news-zone', 'news-files', this.newsFiles, 'news-file-list');
        this.initZone('brand-zone', 'brand-files', this.brandFiles, 'brand-file-list');
    }

    initZone(zoneId, inputId, fileArray, listId) {
        const zone = document.getElementById(zoneId);
        const input = document.getElementById(inputId);

        zone.addEventListener('click', () => input.click());
        input.addEventListener('change', () => {
            Array.from(input.files).forEach(f => {
                if (!fileArray.find(x => x.name === f.name)) fileArray.push(f);
            });
            this.renderFileList(fileArray, listId, zoneId, inputId);
            input.value = '';
        });

        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('drag-over');
            Array.from(e.dataTransfer.files).forEach(f => {
                if (!fileArray.find(x => x.name === f.name)) fileArray.push(f);
            });
            this.renderFileList(fileArray, listId, zoneId, inputId);
        });
    }

    renderFileList(fileArray, listId, zoneId, inputId) {
        const list = document.getElementById(listId);
        list.innerHTML = fileArray.map((f, i) => `
            <div class="file-chip">
                <span>📄 ${f.name} <span style="color:#aaa; font-size:0.7rem;">(${this.formatBytes(f.size)})</span></span>
                <button onclick="app.removeFile('${zoneId}', '${inputId}', ${i}, '${listId}')" title="Remove">✕</button>
            </div>
        `).join('');
    }

    removeFile(zoneId, inputId, index, listId) {
        const arr = zoneId === 'news-zone' ? this.newsFiles : this.brandFiles;
        arr.splice(index, 1);
        this.renderFileList(arr, listId, zoneId, inputId);
    }

    formatBytes(bytes) {
        if (bytes < 1024) return bytes + 'B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(0) + 'KB';
        return (bytes / 1048576).toFixed(1) + 'MB';
    }

    // ── Tier selector ──────────────────────────────────────────────────
    initTierButtons() {
        document.querySelectorAll('.tier-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tier-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.selectedTier = parseInt(btn.dataset.tier);
            });
        });
    }

    // ── Tab switching ──────────────────────────────────────────────────
    switchTab(name) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.querySelector(`[onclick="app.switchTab('${name}')"]`).classList.add('active');
        document.getElementById(`tab-${name}`).classList.add('active');
    }

    // ── Main analyze ───────────────────────────────────────────────────
    async analyze() {
        const extraContext = document.getElementById('extra-context').value.trim();

        if (this.newsFiles.length === 0 && !extraContext) {
            this.setStatus('Please upload at least one news document or add context in the text box.');
            return;
        }

        const btn = document.getElementById('analyze-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Analyzing & finding targets…';
        this.setStatus('Scanning publications and generating pitches — this takes 20–40 seconds…');

        try {
            const formData = new FormData();
            this.newsFiles.forEach(f => formData.append('news_docs', f));
            this.brandFiles.forEach(f => formData.append('brand_docs', f));
            formData.append('extra_context', extraContext);
            formData.append('tier_filter', this.selectedTier);

            const response = await fetch('/api/pitch', { method: 'POST', body: formData });
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.message || response.statusText);
            }
            const data = await response.json();

            if (data.status === 'error') {
                throw new Error(data.message);
            }

            this.results = data;
            this.renderResults(data);
            this.setStatus('');

        } catch (e) {
            this.setStatus(`Error: ${e.message}`);
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Generate Pitches';
        }
    }

    setStatus(msg) {
        document.getElementById('status-msg').textContent = msg;
    }

    // ── Render results ─────────────────────────────────────────────────
    renderResults(data) {
        const section = document.getElementById('results-section');
        section.classList.add('active');
        section.style.display = 'block';

        this.renderStatsBar(data);
        this.renderAssessment(data.news_analysis);
        this.renderTargets(data.targets);

        // Switch to assessment tab
        this.switchTab('assessment');
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    renderStatsBar(data) {
        const na = data.news_analysis || {};
        const score = na.newsworthiness_score || 0;
        const scoreColor = score >= 7 ? 'var(--success)' : score >= 5 ? '#9a7030' : 'var(--error)';
        const goodTargets = (data.targets || []).filter(t => t.fit_score >= 7).length;

        document.getElementById('stats-bar').innerHTML = `
            <div class="stat-item">
                <div class="stat-value" style="color: ${scoreColor};">${score}/10</div>
                <div class="stat-label">Newsworthiness</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${na.news_type || '—'}</div>
                <div class="stat-label">Story Type</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${goodTargets}</div>
                <div class="stat-label">Strong Targets (7+)</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${data.publication_count || 0}</div>
                <div class="stat-label">Publications Scanned</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${data.articles_scanned || 0}</div>
                <div class="stat-label">Recent Articles Read</div>
            </div>
        `;
    }

    renderAssessment(na) {
        if (!na) return;
        const container = document.getElementById('assessment-content');
        const score = na.newsworthiness_score || 0;
        const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';

        const companion = na.companion_content_needed || {};
        const companionItems = [
            { key: 'press_release', label: 'Press Release' },
            { key: 'data_exclusive', label: 'Data Exclusive' },
            { key: 'byline_opportunity', label: 'Byline / Op-Ed' },
            { key: 'embargoed_briefing', label: 'Embargoed Briefing' },
        ];

        const anglesHtml = (na.angles || []).map(a => `
            <div class="angle-card">
                <div class="angle-name">${a.angle_name}</div>
                <div class="angle-framing">${a.framing}</div>
                <div class="angle-best-for">Best for: ${a.best_for}</div>
            </div>
        `).join('');

        const weaknessesHtml = (na.weaknesses || []).map(w => `
            <div class="weakness-item">⚠ ${w}</div>
        `).join('');

        const dataAssetsHtml = (na.data_assets || []).filter(d => d).map(d => `
            <span style="background: #eaf2e6; color: #5a7a4a; padding: 2px 10px; border-radius: 10px; font-size: 0.78rem; font-weight: 500;">${d}</span>
        `).join('');

        container.innerHTML = `
            <div class="assessment-card">
                <h3>Story Assessment</h3>

                <div class="score-row">
                    <div class="score-circle ${scoreClass}">${score}</div>
                    <div>
                        <div style="font-weight: 700; font-size: 1rem; color: var(--headline); margin-bottom: 4px;">${na.headline || ''}</div>
                        <div style="font-size: 0.82rem; color: var(--grey-medium);">${na.newsworthiness_reasoning || ''}</div>
                    </div>
                </div>

                <div class="meta-grid">
                    <div class="meta-item">
                        <div class="meta-label">Story Type</div>
                        <div class="meta-value">${na.news_type || '—'}</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Why Now</div>
                        <div class="meta-value">${na.why_now || 'No clear timely hook identified'}</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Core Story</div>
                        <div class="meta-value">${na.core_story || '—'}</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Who Cares</div>
                        <div class="meta-value">${(na.who_cares || []).join(', ') || '—'}</div>
                    </div>
                </div>

                ${dataAssetsHtml ? `
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 6px;">Data Assets Found</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 5px;">${dataAssetsHtml}</div>
                </div>` : ''}

                ${anglesHtml ? `
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 8px;">Story Angles</div>
                    <div class="angles-list">${anglesHtml}</div>
                </div>` : ''}

                <div style="margin-bottom: 16px;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 6px;">Companion Content Recommended</div>
                    <div class="companion-tags">
                        ${companionItems.map(item => `
                            <span class="companion-tag ${companion[item.key] ? 'companion-yes' : 'companion-no'}">
                                ${companion[item.key] ? '✓' : '○'} ${item.label}
                            </span>
                        `).join('')}
                    </div>
                    ${companion.reasoning ? `<div style="font-size: 0.78rem; color: var(--grey-medium); margin-top: 8px; font-style: italic;">${companion.reasoning}</div>` : ''}
                </div>

                ${weaknessesHtml ? `
                <div>
                    <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 8px;">What Would Make This More Pitchable</div>
                    <div class="weaknesses-list">${weaknessesHtml}</div>
                </div>` : ''}
            </div>
        `;
    }

    renderTargets(targets) {
        const container = document.getElementById('targets-list');
        if (!targets || targets.length === 0) {
            container.innerHTML = '<div class="empty-state">No targets generated. Try adding more news context.</div>';
            return;
        }

        container.innerHTML = targets.map((t, i) => {
            const score = t.fit_score || 0;
            const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';
            const pitch = t.pitch || {};
            const headlines = (t.recent_headlines || []).slice(0, 4);

            return `
            <div class="target-card" id="target-${i}">
                <div class="target-header" onclick="app.toggleTarget(${i})">
                    <div class="target-score ${scoreClass}">${score}</div>
                    <div class="target-meta">
                        <div class="target-name">${t.publication}</div>
                        <div class="target-sub">${t.beat || ''} · ${t.audience || ''}</div>
                    </div>
                    <div class="target-badges">
                        <span class="badge badge-tier${t.tier || 2}">Tier ${t.tier || 2}</span>
                        ${score >= 7 ? '<span class="badge" style="background:#eaf2e6;color:#5a7a4a;">Strong fit</span>' : ''}
                        ${score < 5 ? '<span class="badge" style="background:#faeaea;color:#b85050;">Weak fit</span>' : ''}
                    </div>
                    <span class="chevron">▼</span>
                </div>
                <div class="target-body">

                    <div class="target-section">
                        <div class="target-section-label">Why This Outlet</div>
                        <div style="font-size: 0.84rem; color: var(--body-text);">${t.fit_reasoning || ''}</div>
                    </div>

                    <div class="target-section">
                        <div class="target-section-label">Angle to Use</div>
                        <div style="font-size: 0.84rem; color: var(--body-text); background: var(--table-shade); padding: 10px 12px; border-radius: 6px; border-left: 3px solid var(--highlight-2);">${t.best_angle || ''}</div>
                    </div>

                    <div class="target-section">
                        <div class="target-section-label">Target Journalist Type</div>
                        <div style="font-size: 0.84rem; color: var(--grey-medium); font-style: italic;">${t.suggested_journalist_type || ''}</div>
                    </div>

                    ${headlines.length > 0 ? `
                    <div class="target-section">
                        <div class="target-section-label">Recent Headlines (what they're currently covering)</div>
                        <ul class="recent-headlines-list">
                            ${headlines.map(h => `<li>${h}</li>`).join('')}
                        </ul>
                    </div>` : ''}

                    ${pitch.subject_line ? `
                    <div class="target-section">
                        <div class="target-section-label">Draft Pitch Email</div>
                        <div class="pitch-box">
                            <div class="pitch-subject">Subject: ${pitch.subject_line}</div>
                            <div class="pitch-body">${pitch.body || ''}</div>
                            <button class="copy-pitch-btn" onclick="app.copyPitch(${i})">Copy pitch</button>
                        </div>
                        ${pitch.personalization_notes ? `
                        <div style="font-size: 0.75rem; color: var(--grey-medium); margin-top: 6px; font-style: italic;">
                            <strong>Personalization rationale:</strong> ${pitch.personalization_notes}
                        </div>` : ''}
                        ${pitch.companion_content_recommended ? `
                        <div style="font-size: 0.75rem; color: var(--grey-medium); margin-top: 4px; font-style: italic;">
                            <strong>Attach / offer:</strong> ${pitch.companion_content_recommended}
                        </div>` : ''}
                    </div>` : ''}

                </div>
            </div>
            `;
        }).join('');
    }

    toggleTarget(i) {
        const card = document.getElementById(`target-${i}`);
        card.classList.toggle('open');
    }

    copyPitch(i) {
        const target = this.results?.targets?.[i];
        if (!target?.pitch) return;
        const text = `Subject: ${target.pitch.subject_line}\n\n${target.pitch.body}`;
        navigator.clipboard.writeText(text);
        const btn = document.querySelector(`#target-${i} .copy-pitch-btn`);
        if (btn) {
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.textContent = 'Copy pitch';
                btn.classList.remove('copied');
            }, 1500);
        }
    }

    // ── Publication library ────────────────────────────────────────────
    async loadPublications() {
        try {
            const res = await fetch('/api/publications');
            const data = await res.json();
            this.renderPublications(data.publications || []);
        } catch (e) {}
    }

    renderPublications(pubs) {
        const container = document.getElementById('publications-list');
        const byTier = {};
        pubs.forEach(p => {
            if (!byTier[p.tier]) byTier[p.tier] = [];
            byTier[p.tier].push(p);
        });

        container.innerHTML = Object.entries(byTier).sort(([a],[b]) => a-b).map(([tier, list]) => `
            <div style="margin-bottom: 20px;">
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--headline); margin-bottom: 10px;">
                    Tier ${tier} — ${tier == 1 ? 'Top-tier trade & tech press' : 'Specialist & enterprise press'}
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px;">
                    ${list.map(p => `
                        <div style="background: white; border: 1px solid var(--grey-light); border-radius: 8px; padding: 14px 16px;">
                            <div style="font-weight: 700; font-size: 0.88rem; color: var(--headline); margin-bottom: 3px;">${p.name}</div>
                            <div style="font-size: 0.75rem; color: var(--grey-medium); margin-bottom: 4px;">${p.domain}</div>
                            <div style="font-size: 0.75rem; color: var(--highlight-2); margin-bottom: 4px;"><strong>Beat:</strong> ${p.beat}</div>
                            <div style="font-size: 0.75rem; color: var(--body-text);">${p.description}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    }
}

const app = new PRPitchyApp();
