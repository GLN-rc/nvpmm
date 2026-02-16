/* ══════════════════════════════════════════════════════════════
   tryMe — Editor
   ══════════════════════════════════════════════════════════════ */

class TryMeEditor {
    constructor() {
        this.demoId      = null;   // loaded from URL
        this.demo        = null;   // full demo object
        this.steps       = [];     // ordered step list
        this.activeStep  = null;   // current step object
        this.hotspots    = [];     // hotspots for active step
        this.personas    = [];     // static persona list

        this.tool        = 'draw'; // 'draw' | 'select'
        this.activeHotspotId = null;

        // Canvas drawing state
        this.drawing     = false;
        this.drawStart   = null;
        this.drawCurrent = null;

        // Drag-and-drop reorder state
        this.draggedStepId = null;

        this._init();
    }

    async _init() {
        // Get demoId from URL: /editor/{demoId}
        const parts = location.pathname.split('/').filter(Boolean);
        this.demoId = parts.length >= 2 ? parts[1] : null;

        // Load persona list
        const pRes = await fetch('/api/personas');
        const pData = await pRes.json();
        this.personas = pData.personas;

        if (this.demoId) {
            await this.loadDemo();
        } else {
            // No demo yet — create one immediately (blank)
            const res = await fetch('/api/demos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'Untitled Demo', description: '', personas: [] })
            });
            const demo = await res.json();
            this.demoId = demo.id;
            history.replaceState({}, '', `/editor/${this.demoId}`);
            await this.loadDemo();
        }

        this._bindCanvasEvents();
        this._updatePreviewLink();
    }

    async loadDemo() {
        const res = await fetch(`/api/demos/${this.demoId}`);
        if (!res.ok) { this.showToast('Demo not found', 'error'); return; }
        this.demo = await res.json();
        this.steps = this.demo.steps || [];

        document.getElementById('demo-title-input').value = this.demo.title;
        document.title = `${this.demo.title} — tryMe Editor`;

        this._renderStepList();
        this._updateStepCounter();

        if (this.steps.length > 0) {
            this.selectStep(this.steps[0].id);
        } else {
            this._renderEmptyCanvas();
        }
    }

    // ── Step list ─────────────────────────────────────────────

    _renderStepList() {
        const list = document.getElementById('step-list');
        if (!this.steps.length) {
            list.innerHTML = `<div style="padding:20px 10px;text-align:center;font-size:12px;color:var(--text-muted);">No steps yet — click "+ Add Step" to begin</div>`;
            return;
        }
        list.innerHTML = this.steps.map((s, i) => {
            const thumbHTML = s.image_path
                ? `<div class="step-thumb"><img src="${this._esc(s.image_path)}" alt=""></div>`
                : `<div class="step-thumb">📷</div>`;
            const hotspotCount = (s.hotspots || []).length;
            return `
            <div class="step-item ${this.activeStep && this.activeStep.id === s.id ? 'active' : ''}"
                 id="step-item-${s.id}"
                 onclick="editor.selectStep('${s.id}')"
                 draggable="true"
                 ondragstart="editor._onDragStart(event, '${s.id}')"
                 ondragover="editor._onDragOver(event, '${s.id}')"
                 ondrop="editor._onDrop(event, '${s.id}')"
                 ondragend="editor._onDragEnd()">
                <span class="step-drag-handle" title="Drag to reorder">⠿</span>
                <div class="step-number">${i + 1}</div>
                ${thumbHTML}
                <div class="step-meta">
                    <div class="step-item-title">${this._esc(s.title) || '<em style="color:var(--text-muted)">Untitled step</em>'}</div>
                    <div class="step-item-sub">${hotspotCount} hotspot${hotspotCount !== 1 ? 's' : ''}</div>
                </div>
                <button class="step-delete" onclick="event.stopPropagation(); editor.deleteStep('${s.id}')" title="Delete step">✕</button>
            </div>`;
        }).join('');
    }

    _updateStepCounter() {
        const el = document.getElementById('step-counter');
        if (el) el.textContent = `${this.steps.length} step${this.steps.length !== 1 ? 's' : ''}`;
    }

    async selectStep(stepId) {
        const step = this.steps.find(s => s.id === stepId);
        if (!step) return;
        this.activeStep = step;
        this.hotspots = step.hotspots || [];
        this.activeHotspotId = null;

        // Update sidebar highlight
        document.querySelectorAll('.step-item').forEach(el => el.classList.remove('active'));
        const item = document.getElementById(`step-item-${stepId}`);
        if (item) item.classList.add('active');

        // Populate meta bar
        document.getElementById('step-title-input').value = step.title || '';
        document.getElementById('step-tooltip-input').value = step.tooltip || '';

        // Render canvas
        if (step.image_path) {
            await this._loadCanvasImage(step.image_path);
        } else {
            this._renderEmptyCanvas();
        }

        this._renderHotspotList();
    }

    async addStep() {
        const res = await fetch(`/api/demos/${this.demoId}/steps`, {
            method: 'POST',
            body: (() => {
                const fd = new FormData();
                fd.append('title', '');
                fd.append('tooltip', '');
                return fd;
            })()
        });
        if (!res.ok) { this.showToast('Failed to add step', 'error'); return; }
        const step = await res.json();
        step.hotspots = [];
        this.steps.push(step);
        this._renderStepList();
        this._updateStepCounter();
        this.selectStep(step.id);
        this.showToast('Step added', 'success');
    }

    async deleteStep(stepId) {
        if (!confirm('Delete this step and its hotspots?')) return;
        const res = await fetch(`/api/demos/${this.demoId}/steps/${stepId}`, { method: 'DELETE' });
        if (!res.ok) { this.showToast('Delete failed', 'error'); return; }
        this.steps = this.steps.filter(s => s.id !== stepId);
        this._renderStepList();
        this._updateStepCounter();
        if (this.activeStep && this.activeStep.id === stepId) {
            this.activeStep = null;
            if (this.steps.length > 0) this.selectStep(this.steps[0].id);
            else this._renderEmptyCanvas();
        }
        this.showToast('Step deleted', 'success');
    }

    async saveStepMeta() {
        if (!this.activeStep) return;
        const title   = document.getElementById('step-title-input').value;
        const tooltip = document.getElementById('step-tooltip-input').value;
        const fd = new FormData();
        fd.append('title', title);
        fd.append('tooltip', tooltip);
        await fetch(`/api/demos/${this.demoId}/steps/${this.activeStep.id}`, { method: 'PATCH', body: fd });
        // Update local cache
        this.activeStep.title   = title;
        this.activeStep.tooltip = tooltip;
        const s = this.steps.find(s => s.id === this.activeStep.id);
        if (s) { s.title = title; s.tooltip = tooltip; }
        this._renderStepList();
    }

    async handleScreenshotUpload(input) {
        if (!this.activeStep || !input.files[0]) return;
        const fd = new FormData();
        fd.append('image', input.files[0]);
        const res = await fetch(`/api/demos/${this.demoId}/steps/${this.activeStep.id}`, {
            method: 'PATCH', body: fd
        });
        if (!res.ok) { this.showToast('Upload failed', 'error'); return; }
        const updated = await res.json();
        this.activeStep.image_path = updated.image_path;
        const s = this.steps.find(s => s.id === this.activeStep.id);
        if (s) s.image_path = updated.image_path;
        this._renderStepList();
        await this._loadCanvasImage(updated.image_path);
        this.showToast('Screenshot uploaded', 'success');
        input.value = '';
    }

    async saveDemoTitle(title) {
        if (!title.trim()) return;
        await fetch(`/api/demos/${this.demoId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: title.trim() })
        });
        document.title = `${title} — tryMe Editor`;
    }

    // ── Canvas ────────────────────────────────────────────────

    _renderEmptyCanvas() {
        document.getElementById('no-screenshot').style.display = 'flex';
        document.getElementById('canvas-container').style.display = 'none';
    }

    async _loadCanvasImage(src) {
        return new Promise((resolve) => {
            const img = document.getElementById('canvas-img');
            const container = document.getElementById('canvas-container');
            const noSS = document.getElementById('no-screenshot');

            img.onload = () => {
                noSS.style.display = 'none';
                container.style.display = 'inline-block';
                this._resizeCanvas();
                this._redrawHotspots();
                resolve();
            };
            img.onerror = () => {
                noSS.style.display = 'flex';
                container.style.display = 'none';
                resolve();
            };
            img.src = src + '?t=' + Date.now(); // cache-bust after re-upload
        });
    }

    _resizeCanvas() {
        const img = document.getElementById('canvas-img');
        const canvas = document.getElementById('hotspot-canvas');
        canvas.width  = img.offsetWidth;
        canvas.height = img.offsetHeight;
    }

    _bindCanvasEvents() {
        const canvas = document.getElementById('hotspot-canvas');

        canvas.addEventListener('mousedown', e => {
            if (!this.activeStep) return;
            const pt = this._canvasPt(e);
            if (this.tool === 'draw') {
                this.drawing   = true;
                this.drawStart = pt;
                this.drawCurrent = pt;
            } else {
                // Select mode: find hotspot under cursor
                const hs = this._hotspotAtPoint(pt);
                this.activeHotspotId = hs ? hs.id : null;
                this._renderHotspotList();
                this._redrawHotspots();
            }
        });

        canvas.addEventListener('mousemove', e => {
            if (!this.drawing) return;
            this.drawCurrent = this._canvasPt(e);
            this._redrawHotspots();
            // Draw in-progress rect
            const canvas = document.getElementById('hotspot-canvas');
            const ctx = canvas.getContext('2d');
            const r = this._normalizeRect(this.drawStart, this.drawCurrent);
            ctx.strokeStyle = '#a29bfe';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.strokeRect(r.x, r.y, r.w, r.h);
            ctx.fillStyle = 'rgba(108,92,231,0.12)';
            ctx.fillRect(r.x, r.y, r.w, r.h);
            ctx.setLineDash([]);
        });

        canvas.addEventListener('mouseup', e => {
            if (!this.drawing) return;
            this.drawing = false;
            const end = this._canvasPt(e);
            const canvasEl = document.getElementById('hotspot-canvas');
            const r = this._normalizeRect(this.drawStart, end);
            // Ignore tiny drags (< 10px)
            if (r.w < 10 || r.h < 10) { this._redrawHotspots(); return; }
            // Convert to fractions
            const xFrac = r.x / canvasEl.width;
            const yFrac = r.y / canvasEl.height;
            const wFrac = r.w / canvasEl.width;
            const hFrac = r.h / canvasEl.height;
            this._createHotspot(xFrac, yFrac, wFrac, hFrac);
        });

        // Handle resize
        window.addEventListener('resize', () => {
            if (this.activeStep && this.activeStep.image_path) {
                this._resizeCanvas();
                this._redrawHotspots();
            }
        });
    }

    _canvasPt(e) {
        const canvas = document.getElementById('hotspot-canvas');
        const rect = canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    _normalizeRect(a, b) {
        return {
            x: Math.min(a.x, b.x),
            y: Math.min(a.y, b.y),
            w: Math.abs(b.x - a.x),
            h: Math.abs(b.y - a.y),
        };
    }

    _hotspotAtPoint(pt) {
        const canvas = document.getElementById('hotspot-canvas');
        for (const hs of this.hotspots) {
            const x = hs.x * canvas.width;
            const y = hs.y * canvas.height;
            const w = hs.width * canvas.width;
            const h = hs.height * canvas.height;
            if (pt.x >= x && pt.x <= x + w && pt.y >= y && pt.y <= y + h) return hs;
        }
        return null;
    }

    _redrawHotspots() {
        const canvas = document.getElementById('hotspot-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (const hs of this.hotspots) {
            const x = hs.x * canvas.width;
            const y = hs.y * canvas.height;
            const w = hs.width * canvas.width;
            const h = hs.height * canvas.height;
            const isActive = hs.id === this.activeHotspotId;

            ctx.strokeStyle = isActive ? '#6C5CE7' : '#a29bfe';
            ctx.lineWidth   = isActive ? 2.5 : 1.5;
            ctx.fillStyle   = isActive ? 'rgba(108,92,231,0.22)' : 'rgba(108,92,231,0.10)';
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 4);
            ctx.fill();
            ctx.stroke();

            // Hotspot number label
            const idx = this.hotspots.indexOf(hs) + 1;
            ctx.fillStyle = isActive ? '#6C5CE7' : '#a29bfe';
            ctx.beginPath();
            ctx.arc(x + 10, y + 10, 9, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 10px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(idx, x + 10, y + 10);
            ctx.textAlign = 'left';
            ctx.textBaseline = 'alphabetic';
        }
    }

    // ── Hotspots ──────────────────────────────────────────────

    async _createHotspot(x, y, width, height) {
        const res = await fetch(`/api/steps/${this.activeStep.id}/hotspots`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label: '', x, y, width, height, action_type: 'next', action_target: null })
        });
        if (!res.ok) { this.showToast('Failed to save hotspot', 'error'); return; }
        const hs = await res.json();
        this.hotspots.push(hs);
        this.activeStep.hotspots = this.hotspots;
        const s = this.steps.find(s => s.id === this.activeStep.id);
        if (s) s.hotspots = this.hotspots;
        this.activeHotspotId = hs.id;
        this._renderHotspotList();
        this._renderStepList();
        this._redrawHotspots();
        this.showToast('Hotspot added — edit it in the panel →', 'success');
    }

    async deleteHotspot(hotspotId) {
        const res = await fetch(`/api/steps/${this.activeStep.id}/hotspots/${hotspotId}`, { method: 'DELETE' });
        if (!res.ok) return;
        this.hotspots = this.hotspots.filter(h => h.id !== hotspotId);
        this.activeStep.hotspots = this.hotspots;
        const s = this.steps.find(s => s.id === this.activeStep.id);
        if (s) s.hotspots = this.hotspots;
        if (this.activeHotspotId === hotspotId) this.activeHotspotId = null;
        this._renderHotspotList();
        this._renderStepList();
        this._redrawHotspots();
        this.showToast('Hotspot removed', 'success');
    }

    async saveHotspot(hotspotId) {
        const label       = document.getElementById(`hs-label-${hotspotId}`).value;
        const actionType  = document.getElementById(`hs-action-${hotspotId}`).value;
        const actionTarget = actionType === 'goto'
            ? document.getElementById(`hs-target-${hotspotId}`)?.value || null
            : null;

        const res = await fetch(`/api/steps/${this.activeStep.id}/hotspots/${hotspotId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label, action_type: actionType, action_target: actionTarget })
        });
        if (!res.ok) { this.showToast('Failed to save hotspot', 'error'); return; }
        const updated = await res.json();
        const idx = this.hotspots.findIndex(h => h.id === hotspotId);
        if (idx !== -1) this.hotspots[idx] = updated;
        this.activeStep.hotspots = this.hotspots;
        this._renderHotspotList();
        this.showToast('Hotspot saved', 'success');
    }

    _renderHotspotList() {
        const container = document.getElementById('hotspot-list');
        const count = document.getElementById('hotspot-count');
        if (count) count.textContent = this.hotspots.length;

        if (!this.activeStep) {
            container.innerHTML = `<div class="hotspot-empty">Select a step to see its hotspots</div>`;
            return;
        }
        if (!this.hotspots.length) {
            container.innerHTML = `
            <div class="draw-instruction">
                ✏ Switch to <strong>Draw Hotspot</strong> mode and click-drag on the screenshot to define a clickable region
            </div>
            <div class="hotspot-empty">No hotspots yet on this step</div>`;
            return;
        }

        container.innerHTML = `
        <div class="draw-instruction" style="margin-bottom:8px;">
            Click a hotspot below to edit it, or draw a new one on the screenshot
        </div>
        ` + this.hotspots.map((hs, i) => {
            const isActive = hs.id === this.activeHotspotId;
            const actionLabel = { next: 'Next Step', goto: 'Go to Step', end: 'End Demo' }[hs.action_type] || hs.action_type;
            const actionClass = `action-${hs.action_type}`;

            if (isActive) {
                // Render edit form inline
                const stepsExcludingSelf = this.steps.filter(s => s.id !== this.activeStep.id);
                const gotoOptions = stepsExcludingSelf.map((s, si) =>
                    `<option value="${s.id}" ${hs.action_target === s.id ? 'selected' : ''}>Step ${this.steps.indexOf(s)+1}: ${this._esc(s.title) || 'Untitled'}</option>`
                ).join('');

                return `
                <div class="hotspot-edit-form" id="hs-form-${hs.id}">
                    <div class="form-title">
                        <span>Hotspot ${i+1}</span>
                        <button class="btn btn-danger btn-sm" onclick="editor.deleteHotspot('${hs.id}')">Delete</button>
                    </div>
                    <div class="field-group">
                        <label>Tooltip label (shown on hover)</label>
                        <input type="text" id="hs-label-${hs.id}" value="${this._esc(hs.label)}" placeholder="e.g. Click here to open Settings">
                    </div>
                    <div class="field-group">
                        <label>Click action</label>
                        <select id="hs-action-${hs.id}" onchange="editor._toggleActionTarget('${hs.id}')">
                            <option value="next" ${hs.action_type==='next'?'selected':''}>→ Advance to next step</option>
                            <option value="goto" ${hs.action_type==='goto'?'selected':''}>⤵ Go to specific step</option>
                            <option value="end"  ${hs.action_type==='end'?'selected':''}>✓ End demo</option>
                        </select>
                    </div>
                    <div class="field-group" id="hs-target-group-${hs.id}" style="${hs.action_type!=='goto'?'display:none':''}">
                        <label>Jump to step</label>
                        <select id="hs-target-${hs.id}">
                            ${gotoOptions || '<option value="">No other steps</option>'}
                        </select>
                    </div>
                    <button class="btn btn-primary btn-sm" style="width:100%;margin-top:4px;" onclick="editor.saveHotspot('${hs.id}')">Save Hotspot</button>
                </div>`;
            }

            return `
            <div class="hotspot-item" id="hs-item-${hs.id}" onclick="editor._selectHotspotById('${hs.id}')">
                <div class="hotspot-item-top">
                    <span class="hotspot-item-label">${this._esc(hs.label) || `<em style="color:var(--text-muted)">Hotspot ${i+1}</em>`}</span>
                    <span class="hotspot-action-badge ${actionClass}">${actionLabel}</span>
                </div>
                <div class="hotspot-coords">x:${(hs.x*100).toFixed(0)}% y:${(hs.y*100).toFixed(0)}% · ${(hs.width*100).toFixed(0)}×${(hs.height*100).toFixed(0)}%</div>
            </div>`;
        }).join('');
    }

    _selectHotspotById(id) {
        this.activeHotspotId = id;
        this._renderHotspotList();
        this._redrawHotspots();
    }

    _toggleActionTarget(hotspotId) {
        const sel = document.getElementById(`hs-action-${hotspotId}`);
        const group = document.getElementById(`hs-target-group-${hotspotId}`);
        if (group) group.style.display = sel.value === 'goto' ? 'block' : 'none';
    }

    // ── Tool mode ─────────────────────────────────────────────

    setTool(tool) {
        this.tool = tool;
        document.getElementById('tool-draw').classList.toggle('active', tool === 'draw');
        document.getElementById('tool-select').classList.toggle('active', tool === 'select');
        const canvas = document.getElementById('hotspot-canvas');
        canvas.classList.toggle('select-mode', tool === 'select');
        document.getElementById('canvas-hint').textContent = tool === 'draw'
            ? 'Click and drag on the screenshot to add a hotspot'
            : 'Click a hotspot to select and edit it';
    }

    // ── Drag-to-reorder steps ─────────────────────────────────

    _onDragStart(e, stepId) {
        this.draggedStepId = stepId;
        e.dataTransfer.effectAllowed = 'move';
        document.getElementById(`step-item-${stepId}`)?.classList.add('dragging');
    }
    _onDragOver(e, stepId) {
        e.preventDefault();
        document.querySelectorAll('.step-item').forEach(el => el.classList.remove('drag-over'));
        if (stepId !== this.draggedStepId)
            document.getElementById(`step-item-${stepId}`)?.classList.add('drag-over');
    }
    _onDrop(e, targetStepId) {
        e.preventDefault();
        if (!this.draggedStepId || this.draggedStepId === targetStepId) return;
        // Reorder locally
        const from = this.steps.findIndex(s => s.id === this.draggedStepId);
        const to   = this.steps.findIndex(s => s.id === targetStepId);
        const [moved] = this.steps.splice(from, 1);
        this.steps.splice(to, 0, moved);
        this._renderStepList();
        // Persist
        fetch(`/api/demos/${this.demoId}/steps/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order: this.steps.map(s => s.id) })
        });
    }
    _onDragEnd() {
        document.querySelectorAll('.step-item').forEach(el => {
            el.classList.remove('dragging', 'drag-over');
        });
        this.draggedStepId = null;
    }

    // ── Settings modal ────────────────────────────────────────

    openSettings() {
        if (!this.demo) return;
        document.getElementById('settings-title').value = this.demo.title;
        document.getElementById('settings-desc').value  = this.demo.description || '';
        const selectedPersonas = new Set(this.demo.personas || []);
        const container = document.getElementById('settings-personas');
        container.innerHTML = this.personas.map(p => `
            <span class="persona-tag ${selectedPersonas.has(p) ? 'selected' : ''}"
                  onclick="this.classList.toggle('selected')">${this._esc(p)}</span>
        `).join('');
        document.getElementById('settings-modal').classList.add('open');
    }

    closeSettings() {
        document.getElementById('settings-modal').classList.remove('open');
    }

    async saveSettings() {
        const title = document.getElementById('settings-title').value.trim();
        const desc  = document.getElementById('settings-desc').value.trim();
        const personas = [...document.querySelectorAll('#settings-personas .persona-tag.selected')]
            .map(el => el.textContent.trim());
        await fetch(`/api/demos/${this.demoId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, description: desc, personas })
        });
        if (this.demo) { this.demo.title = title; this.demo.description = desc; this.demo.personas = personas; }
        document.getElementById('demo-title-input').value = title;
        document.title = `${title} — tryMe Editor`;
        this.closeSettings();
        this.showToast('Settings saved', 'success');
    }

    // ── Misc helpers ──────────────────────────────────────────

    _updatePreviewLink() {
        const btn = document.getElementById('preview-btn');
        if (btn) btn.href = `/demo/${this.demoId}`;
    }

    copyViewerLink() {
        const url = `${location.origin}/demo/${this.demoId}`;
        navigator.clipboard.writeText(url).then(() => this.showToast('Link copied!', 'success'));
    }

    showToast(msg, type = 'success') {
        const t = document.getElementById('toast');
        t.textContent = msg;
        t.className = `toast ${type} show`;
        setTimeout(() => t.classList.remove('show'), 2600);
    }

    _esc(s) {
        return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
}

const editor = new TryMeEditor();
