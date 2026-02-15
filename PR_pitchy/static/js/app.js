'use strict';

class PRPitchyApp {
    constructor() {
        this.newsFiles = [];
        this.brandFiles = [];
        this.selectedTier = 2;
        this.results = null;
        this.pitchIndex = {};  // keyed by DOM id, stores {subject_line, body}
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
        btn.innerHTML = '<span class="spinner"></span> Analyzing & planning campaign…';
        this.setStatus('Scanning publications, planning waves, and drafting pitches — this takes 30–60 seconds…');

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
            this.pitchIndex = {};
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
        this.renderCampaign(data.waves, data.campaign_plan);

        this.switchTab('assessment');
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    renderStatsBar(data) {
        const na = data.news_analysis || {};
        const score = na.newsworthiness_score || 0;
        const scoreColor = score >= 7 ? 'var(--success)' : score >= 5 ? '#9a7030' : 'var(--error)';
        const wc = data.wave_counts || {};

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
                <div class="stat-value">${wc.wave_1 || 0}</div>
                <div class="stat-label">Wave 1 (Exclusive)</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${wc.wave_2 || 0}</div>
                <div class="stat-label">Wave 2 (Launch Day)</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${wc.wave_3 || 0}</div>
                <div class="stat-label">Wave 3 (Follow-on)</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${data.articles_scanned || 0}</div>
                <div class="stat-label">Articles Read</div>
            </div>
        `;
    }

    // ── Assessment tab ─────────────────────────────────────────────────
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

        const excl = na.exclusive_viability || {};

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
            <span style="background: #eaf2e6; color: #5a7a4a; padding: 3px 10px; border-radius: 10px; font-size: 0.78rem; font-weight: 500;">${d}</span>
        `).join('');

        const exclusiveHtml = excl.can_offer_exclusive ? `
            <div class="exclusive-offer-box" style="margin-bottom:16px;">
                <div class="exclusive-offer-label">Exclusive Viability</div>
                <div><strong>Can offer:</strong> ${excl.what_to_offer || '—'}</div>
                ${excl.embargo_window_suggested ? `<div style="margin-top:3px;font-size:0.8rem;opacity:0.8;">Suggested window: ${excl.embargo_window_suggested}</div>` : ''}
            </div>` : '';

        const timingHtml = na.campaign_timing_notes ? `
            <div style="margin-bottom:16px;">
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; font-weight: 600; margin-bottom: 6px;">Campaign Timing Notes</div>
                <div style="font-size: 0.84rem; color: var(--body-text); font-style: italic;">${na.campaign_timing_notes}</div>
            </div>` : '';

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

                ${exclusiveHtml}
                ${timingHtml}

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

    // ── Campaign Waves tab ─────────────────────────────────────────────
    renderCampaign(waves, plan) {
        const container = document.getElementById('targets-list');
        if (!waves && !plan) {
            container.innerHTML = '<div class="empty-state">No campaign generated. Try adding more news context.</div>';
            return;
        }

        plan = plan || {};
        waves = waves || {};
        let html = '';

        // Campaign summary banner
        if (plan.campaign_summary) {
            html += `
                <div class="campaign-summary-banner">
                    <div class="campaign-summary-label">Campaign Strategy</div>
                    <div class="campaign-summary-text">${plan.campaign_summary}</div>
                </div>`;
        }

        // ── Wave 1 ──
        html += `<div class="wave-section">
            <div class="wave-header">
                <span class="wave-badge wave-badge-1">Wave 1</span>
                <span class="wave-title">Exclusive / Embargo</span>
                <span class="wave-timing">${plan.wave_1?.timing_label || '48h before launch'}</span>
            </div>
            <div class="wave-divider"></div>`;

        const w1 = waves.wave_1;
        if (w1 && w1.target_data) {
            // Exclusive offer highlight
            if (w1.exclusive_offer) {
                html += `<div class="exclusive-offer-box">
                    <div class="exclusive-offer-label">What you're offering exclusively</div>
                    ${w1.exclusive_offer}
                </div>`;
            }
            // Contingency box
            if (w1.contingency) {
                html += this._renderContingencyBox(w1.contingency);
            }
            html += this._renderTargetCard(w1.target_data, 'w1', 0, w1.angle_note || w1.rationale || '', null, 1);
        } else {
            html += `<div class="no-wave1-notice">No exclusive pitch recommended for this story — either the newsworthiness score is below threshold, no outlet scored 8+ for fit, or there's nothing unique enough to offer as a genuine exclusive. Proceed directly to Wave 2.</div>`;
        }

        html += `</div>`; // end wave-section

        // ── Wave 2 ──
        const wave2List = waves.wave_2 || [];
        html += `<div class="wave-section">
            <div class="wave-header">
                <span class="wave-badge wave-badge-2">Wave 2</span>
                <span class="wave-title">Launch Day</span>
                <span class="wave-timing">${plan.wave_2?.timing_label || 'Launch Day'}</span>
            </div>
            <div class="wave-divider"></div>`;

        if (plan.wave_2?.wave_2_note) {
            html += `<div class="wave-2-note">📋 ${plan.wave_2.wave_2_note}</div>`;
        }

        if (wave2List.length === 0) {
            html += `<div class="no-wave1-notice">No Wave 2 targets generated.</div>`;
        } else {
            wave2List.forEach((entry, i) => {
                html += this._renderTargetCard(entry.target_data, 'w2', i, entry.angle_note || '', null, 2);
            });
        }
        html += `</div>`;

        // ── Wave 3 ──
        const wave3List = waves.wave_3 || [];
        html += `<div class="wave-section">
            <div class="wave-header">
                <span class="wave-badge wave-badge-3">Wave 3</span>
                <span class="wave-title">Follow-on</span>
                <span class="wave-timing">${plan.wave_3?.timing_label || '1-2 weeks post-launch'}</span>
            </div>
            <div class="wave-divider"></div>`;

        if (plan.wave_3?.wave_3_strategy) {
            html += `<div class="wave-strategy-note">
                <div class="wave-strategy-note-label">How to use Wave 2 coverage as social proof</div>
                ${plan.wave_3.wave_3_strategy}
            </div>`;
        }

        if (plan.contingency_if_wave2_thin) {
            html += `<div class="wave-strategy-note" style="margin-top:-6px;">
                <div class="wave-strategy-note-label">If Wave 2 coverage is thin</div>
                ${plan.contingency_if_wave2_thin}
            </div>`;
        }

        if (wave3List.length === 0) {
            html += `<div class="no-wave1-notice">No Wave 3 targets generated.</div>`;
        } else {
            wave3List.forEach((entry, i) => {
                html += this._renderTargetCard(entry.target_data, 'w3', i, entry.angle_note || '', entry.format_suggestion || '', 3);
            });
        }
        html += `</div>`;

        container.innerHTML = html;
    }

    _renderContingencyBox(contingency) {
        return `<div class="contingency-box">
            <div class="contingency-box-title">If the exclusive doesn't work out</div>
            ${contingency.if_rejected ? `
            <div class="contingency-row">
                <span class="contingency-trigger">If rejected:</span>
                <span class="contingency-action">${contingency.if_rejected}</span>
            </div>` : ''}
            ${contingency.if_no_response_48h ? `
            <div class="contingency-row">
                <span class="contingency-trigger">No response in 48h:</span>
                <span class="contingency-action">${contingency.if_no_response_48h}</span>
            </div>` : ''}
            ${contingency.second_choice_exclusive ? `
            <div class="contingency-row">
                <span class="contingency-trigger">Second choice exclusive:</span>
                <span class="contingency-action">${contingency.second_choice_exclusive}</span>
            </div>` : ''}
        </div>`;
    }

    _renderTargetCard(target, wavePrefix, idx, angleNote, formatSuggestion, waveNum) {
        if (!target) return '';
        const domId = `target-${wavePrefix}-${idx}`;
        const pitchId = `pitch-${wavePrefix}-${idx}`;
        const score = target.fit_score || 0;
        const scoreClass = score >= 7 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';
        const pitch = target.pitch || {};
        const headlines = (target.recent_headlines || []).slice(0, 5);
        const authors = target.known_authors || [];

        // Register pitch in index for clipboard use
        if (pitch.subject_line) {
            this.pitchIndex[pitchId] = { subject_line: pitch.subject_line, body: pitch.body || '' };
        }

        const waveBadgeColor = waveNum === 1 ? '#e8e4ef' : waveNum === 2 ? '#dde4ee' : '#f0eae9';
        const waveBadgeText = waveNum === 1 ? 'Exclusive' : waveNum === 2 ? 'Launch Day' : 'Follow-on';

        return `
        <div class="target-card" id="${domId}">
            <div class="target-header" onclick="app.toggleTarget('${domId}')">
                <div class="target-score ${scoreClass}">${score}</div>
                <div class="target-meta">
                    <div class="target-name">${target.publication || '—'}</div>
                    <div class="target-sub">${target.beat || ''} · ${target.audience || ''}</div>
                </div>
                <div class="target-badges">
                    <span class="badge badge-tier${target.tier || 2}">Tier ${target.tier || 2}</span>
                    <span class="badge" style="background:${waveBadgeColor};color:var(--headline);">${waveBadgeText}</span>
                    ${score >= 7 ? '<span class="badge" style="background:#eaf2e6;color:#5a7a4a;">Strong fit</span>' : ''}
                </div>
                <span class="chevron">▼</span>
            </div>
            <div class="target-body">

                <div class="target-section">
                    <div class="target-section-label">Why This Outlet</div>
                    <div style="font-size: 0.84rem; color: var(--body-text);">${target.fit_reasoning || ''}</div>
                </div>

                ${angleNote ? `
                <div class="angle-note-box">
                    <div class="angle-note-label">Angle for this outlet</div>
                    ${angleNote}
                </div>` : `
                <div class="target-section">
                    <div class="target-section-label">Angle to Use</div>
                    <div style="font-size: 0.84rem; color: var(--body-text); background: var(--table-shade); padding: 10px 12px; border-radius: 6px; border-left: 3px solid var(--highlight-2);">${target.best_angle || ''}</div>
                </div>`}

                ${formatSuggestion ? `<span class="format-suggestion-tag">📝 ${formatSuggestion}</span>` : ''}

                <div class="target-section" style="margin-top: 12px;">
                    <div class="target-section-label">Target Journalist Type</div>
                    <div style="font-size: 0.84rem; color: var(--grey-medium); font-style: italic;">${target.suggested_journalist_type || ''}</div>
                    ${authors.length > 0 ? `
                    <div style="margin-top: 5px; font-size: 0.78rem; color: var(--highlight-2);">
                        <strong>Known contributors:</strong> ${authors.join(', ')}
                    </div>` : ''}
                </div>

                ${headlines.length > 0 ? `
                <div class="target-section">
                    <div class="target-section-label">Recent Headlines (reverse-engineer their beat)</div>
                    <ul class="recent-headlines-list">
                        ${headlines.map(h => `<li>${h}</li>`).join('')}
                    </ul>
                </div>` : ''}

                ${pitch.subject_line ? `
                <div class="target-section">
                    <div class="target-section-label">Draft Pitch Email</div>
                    <div class="pitch-box">
                        <div class="pitch-subject">Subject: ${pitch.subject_line}</div>
                        <div class="pitch-body">${(pitch.body || '').replace(/\n/g, '<br>')}</div>
                        <button class="copy-pitch-btn" onclick="app.copyPitchById('${pitchId}', this)">Copy pitch</button>
                    </div>
                    ${pitch.personalization_notes ? `
                    <div style="font-size: 0.75rem; color: var(--grey-medium); margin-top: 6px; font-style: italic;">
                        <strong>Personalization rationale:</strong> ${pitch.personalization_notes}
                    </div>` : ''}
                    ${pitch.companion_content_recommended ? `
                    <div style="font-size: 0.75rem; color: var(--grey-medium); margin-top: 4px; font-style: italic;">
                        <strong>Attach / offer:</strong> ${pitch.companion_content_recommended}
                    </div>` : ''}
                    ${pitch.exclusive_offer_line ? `
                    <div style="font-size: 0.78rem; color: var(--headline); margin-top: 6px; font-weight: 600;">
                        🔒 Exclusive offer line: "${pitch.exclusive_offer_line}"
                    </div>` : ''}
                    ${pitch.follow_on_hook ? `
                    <div style="font-size: 0.78rem; color: #7a5058; margin-top: 6px; font-style: italic;">
                        🔗 Follow-on hook: "${pitch.follow_on_hook}"
                    </div>` : ''}
                </div>` : ''}

            </div>
        </div>`;
    }

    toggleTarget(domId) {
        const card = document.getElementById(domId);
        if (card) card.classList.toggle('open');
    }

    copyPitchById(pitchId, btn) {
        const pitch = this.pitchIndex[pitchId];
        if (!pitch) return;
        const text = `Subject: ${pitch.subject_line}\n\n${pitch.body}`;
        navigator.clipboard.writeText(text);
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
