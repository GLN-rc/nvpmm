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

        // Undo stack — stores {type, data} objects
        this._undoStack  = [];

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
        this._initBannerDrag();
        this._initRteToolbar();

        // Global keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            const inInput = ['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !inInput) {
                e.preventDefault();
                this.undo();
            }
        });
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

        // Enable toolbar upload label now that a step is active
        const uploadLabel = document.getElementById('toolbar-upload-label');
        if (uploadLabel) uploadLabel.classList.remove('disabled');

        // Update sidebar highlight
        document.querySelectorAll('.step-item').forEach(el => el.classList.remove('active'));
        const item = document.getElementById(`step-item-${stepId}`);
        if (item) item.classList.add('active');

        // Populate meta bar
        document.getElementById('step-title-input').value        = step.title || '';
        document.getElementById('step-notes-input').value        = step.notes || '';
        document.getElementById('banner-cta-label').value        = step.banner_cta_label || '';
        document.getElementById('banner-cta-action').value       = step.banner_cta_action || 'next';
        document.getElementById('banner-pointer').value          = step.banner_pointer || 'none';
        // Load rich-text HTML into the contenteditable RTE
        const rteEl = document.getElementById('step-tooltip-input');
        if (rteEl) {
            // Prefer tooltip_html; fall back to plain tooltip with newlines as <br>
            if (step.tooltip_html) {
                rteEl.innerHTML = step.tooltip_html;
            } else if (step.tooltip) {
                rteEl.innerHTML = step.tooltip.replace(/\n/g, '<br>');
            } else {
                rteEl.innerHTML = '';
            }
        }
        this._toggleBannerCtaTarget(step.banner_cta_action || 'next', step.banner_cta_target);
        this._renderBannerCtaStepOptions(step.banner_cta_target);

        // Render canvas
        if (step.image_path) {
            await this._loadCanvasImage(step.image_path);
        } else {
            this._renderEmptyCanvas();
        }

        this._renderHotspotList();
        this._updateHotspotAnchorSelect();
        this._updateEditorBanner();
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
        const step = this.steps.find(s => s.id === stepId);
        if (!step) return;
        // Push to undo stack before deleting
        this._undoStack.push({ type: 'step', demoId: this.demoId, step: JSON.parse(JSON.stringify(step)) });
        const res = await fetch(`/api/demos/${this.demoId}/steps/${stepId}`, { method: 'DELETE' });
        if (!res.ok) { this._undoStack.pop(); this.showToast('Delete failed', 'error'); return; }
        this.steps = this.steps.filter(s => s.id !== stepId);
        this._renderStepList();
        this._updateStepCounter();
        if (this.activeStep && this.activeStep.id === stepId) {
            this.activeStep = null;
            if (this.steps.length > 0) this.selectStep(this.steps[0].id);
            else this._renderEmptyCanvas();
        }
        this.showToast('Step deleted — Ctrl+Z to undo', 'success');
    }

    async undo() {
        const item = this._undoStack.pop();
        if (!item) { this.showToast('Nothing to undo', 'error'); return; }

        if (item.type === 'step') {
            // Re-create the step
            const fd = new FormData();
            fd.append('title', item.step.title || '');
            fd.append('tooltip', item.step.tooltip || '');
            const res = await fetch(`/api/demos/${item.demoId}/steps`, { method: 'POST', body: fd });
            if (!res.ok) { this.showToast('Undo failed', 'error'); return; }
            const restored = await res.json();
            // Re-upload image if it existed
            if (item.step.image_path) {
                // image is already on disk — just update the path reference
                const pfd = new FormData();
                pfd.append('title', item.step.title || '');
                await fetch(`/api/demos/${item.demoId}/steps/${restored.id}`, { method: 'PATCH', body: pfd });
            }
            restored.hotspots = [];
            this.steps.push(restored);
            this._renderStepList();
            this._updateStepCounter();
            this.selectStep(restored.id);
            this.showToast('Step restored', 'success');

        } else if (item.type === 'hotspot') {
            // Re-create the hotspot
            const res = await fetch(`/api/steps/${item.stepId}/hotspots`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item.hotspot)
            });
            if (!res.ok) { this.showToast('Undo failed', 'error'); return; }
            const restored = await res.json();
            this.hotspots.push(restored);
            this.activeStep.hotspots = this.hotspots;
            this.activeHotspotId = restored.id;
            this._renderHotspotList();
            this._renderStepList();
            this._redrawHotspots();
            this.showToast('Hotspot restored', 'success');
        }
    }

    async saveStepMeta() {
        if (!this.activeStep) { this.showToast('Select a step first', 'error'); return; }
        const title             = document.getElementById('step-title-input').value.trim();
        const rteEl             = document.getElementById('step-tooltip-input');
        const tooltip_html      = rteEl ? rteEl.innerHTML : '';
        // Plain-text fallback for legacy/search (strip tags)
        const tooltip           = rteEl ? (rteEl.innerText || rteEl.textContent || '') : '';
        const notes             = document.getElementById('step-notes-input').value || '';
        const banner_cta_label  = document.getElementById('banner-cta-label').value.trim();
        const banner_cta_action = document.getElementById('banner-cta-action').value;
        const banner_pointer    = document.getElementById('banner-pointer').value;
        const banner_cta_target = banner_cta_action === 'goto'
            ? (document.getElementById('banner-cta-target')?.value || null) : null;
        const banner_hotspot_id = document.getElementById('banner-hotspot-anchor')?.value || null;

        const fd = new FormData();
        fd.append('title',             title);
        fd.append('tooltip',           tooltip);
        fd.append('tooltip_html',      tooltip_html);
        fd.append('notes',             notes);
        fd.append('banner_cta_label',  banner_cta_label);
        fd.append('banner_cta_action', banner_cta_action);
        fd.append('banner_pointer',    banner_pointer);
        fd.append('banner_cta_target', banner_cta_target || '');
        fd.append('banner_hotspot_id', banner_hotspot_id || '');
        // Save drag position if set
        if (this.activeStep.banner_x != null) fd.append('banner_x', this.activeStep.banner_x);
        if (this.activeStep.banner_y != null) fd.append('banner_y', this.activeStep.banner_y);

        const res = await fetch(`/api/demos/${this.demoId}/steps/${this.activeStep.id}`, { method: 'PATCH', body: fd });
        if (!res.ok) { this.showToast('Save failed', 'error'); return; }

        // Update local cache
        const updates = { title, tooltip, tooltip_html, notes, banner_cta_label,
                          banner_cta_action, banner_pointer, banner_cta_target, banner_hotspot_id };
        Object.assign(this.activeStep, updates);
        const s = this.steps.find(s => s.id === this.activeStep.id);
        if (s) Object.assign(s, updates);
        this._renderStepList();
        this._updateEditorBanner();
        this.showToast('Step saved ✓', 'success');
    }

    _toggleBannerCtaTarget(action, currentTarget) {
        const group = document.getElementById('banner-cta-target-group');
        if (group) group.style.display = action === 'goto' ? 'block' : 'none';
    }

    // ── Editor banner preview ─────────────────────────────────

    _updateEditorBanner() {
        const preview = document.getElementById('editor-banner-preview');
        const textEl  = document.getElementById('editor-banner-text');
        const ctaBtn  = document.getElementById('editor-banner-cta');
        if (!preview || !textEl) return;

        const canvasContainer = document.getElementById('canvas-container');
        if (!this.activeStep || !canvasContainer || canvasContainer.style.display === 'none') {
            preview.style.display = 'none'; return;
        }
        preview.style.display = 'flex';

        const rteEl    = document.getElementById('step-tooltip-input');
        const htmlContent = rteEl ? rteEl.innerHTML : '';
        const ctaLabel = (document.getElementById('banner-cta-label')?.value || '').trim();
        const hasText  = !!(rteEl?.innerText?.trim() || ctaLabel);

        // Fade when empty
        preview.style.opacity = hasText ? '1' : '0.32';

        // Render HTML into preview (safe — user-entered content only)
        textEl.innerHTML = htmlContent;

        // CTA button
        if (ctaBtn) {
            if (ctaLabel) { ctaBtn.textContent = ctaLabel; ctaBtn.style.display = 'block'; }
            else          { ctaBtn.style.display = 'none'; }
        }

        // Pointer arrow
        const ptr = document.getElementById('banner-pointer')?.value || 'none';
        preview.dataset.pointer = ptr;

        // Fade dependent dropdowns
        const ctaActionSel = document.getElementById('banner-cta-action');
        const ptrSel       = document.getElementById('banner-pointer');
        if (ctaActionSel) ctaActionSel.style.opacity = ctaLabel ? '1' : '0.38';
        if (ptrSel)       ptrSel.style.opacity       = hasText  ? '1' : '0.38';

        // ── Position banner preview relative to anchor hotspot ──
        this._positionEditorBanner();
    }

    // Position the editor banner preview.
    // The preview lives inside canvas-container — the same element the hotspot canvas
    // draws on — so hs fraction × container size gives direct px offsets.
    // --ptr-h / --ptr-v CSS vars are set so the pointer triangle aims at the hotspot center
    // even when the banner is clamped to the container edge.
    _positionEditorBanner() {
        const preview   = document.getElementById('editor-banner-preview');
        const container = document.getElementById('canvas-container');
        if (!preview || !container || !container.offsetWidth) return;

        const anchorId = document.getElementById('banner-hotspot-anchor')?.value || '';
        const ptr      = document.getElementById('banner-pointer')?.value || 'none';

        if (anchorId) {
            const hs = this.hotspots.find(h => h.id === anchorId);
            if (hs) {
                const hsCx = (hs.x + hs.width  / 2) * container.offsetWidth;
                const hsCy = (hs.y + hs.height / 2) * container.offsetHeight;
                const hsW  = hs.width  * container.offsetWidth;
                const hsH  = hs.height * container.offsetHeight;
                const bw   = preview.offsetWidth  || 300;
                const bh   = preview.offsetHeight || 80;
                const gap  = 12;
                let left, top;

                if (ptr === 'bottom') {
                    left = hsCx - bw / 2;
                    top  = hsCy - hsH / 2 - bh - gap;
                } else if (ptr === 'top') {
                    left = hsCx - bw / 2;
                    top  = hsCy + hsH / 2 + gap;
                } else if (ptr === 'right') {
                    left = hsCx - hsW / 2 - bw - gap;
                    top  = hsCy - bh / 2;
                } else if (ptr === 'left') {
                    left = hsCx + hsW / 2 + gap;
                    top  = hsCy - bh / 2;
                } else {
                    left = hsCx - bw / 2;
                    top  = hsCy - hsH / 2 - bh - gap;
                }

                // Clamp within canvas-container
                const clampedLeft = Math.max(8, Math.min(left, container.offsetWidth  - bw - 8));
                const clampedTop  = Math.max(8, Math.min(top,  container.offsetHeight - bh - 8));

                // Set pointer offset vars so triangle aims at hotspot center even after clamping
                const ptrH = hsCx - clampedLeft;
                const ptrV = hsCy - clampedTop;
                preview.style.setProperty('--ptr-h', Math.max(16, Math.min(ptrH, bw - 16)) + 'px');
                preview.style.setProperty('--ptr-v', Math.max(16, Math.min(ptrV, bh - 16)) + 'px');

                preview.style.left      = clampedLeft + 'px';
                preview.style.top       = clampedTop  + 'px';
                preview.style.transform = 'none';
                return;
            }
        }

        // No hotspot anchor — use saved banner_x/banner_y if available
        const bx = this.activeStep?.banner_x;
        const by = this.activeStep?.banner_y;
        if (bx != null && by != null && container.offsetWidth) {
            const bw2 = preview.offsetWidth  || 300;
            const bh2 = preview.offsetHeight || 80;
            let left2 = bx * container.offsetWidth;
            let top2  = by * container.offsetHeight;
            left2 = Math.max(8, Math.min(left2, container.offsetWidth  - bw2 - 8));
            top2  = Math.max(8, Math.min(top2,  container.offsetHeight - bh2 - 8));
            preview.style.left      = left2 + 'px';
            preview.style.top       = top2  + 'px';
            preview.style.transform = 'none';
            return;
        }

        // Final fallback: float centered near the top of the image
        preview.style.left      = '50%';
        preview.style.top       = '16px';
        preview.style.transform = 'translateX(-50%)';
    }

    // Populate the hotspot anchor dropdown for the active step
    _updateHotspotAnchorSelect() {
        const sel = document.getElementById('banner-hotspot-anchor');
        if (!sel) return;
        const currentVal = this.activeStep?.banner_hotspot_id || '';
        sel.innerHTML = '<option value="">— Float (top-center) —</option>';
        (this.hotspots || []).forEach((hs, i) => {
            const opt = document.createElement('option');
            opt.value = hs.id;
            opt.textContent = hs.label || `Hotspot ${i + 1}`;
            if (hs.id === currentVal) opt.selected = true;
            sel.appendChild(opt);
        });
    }

    // ── Rich Text Editor toolbar ───────────────────────────────

    _initRteToolbar() {
        const toolbar = document.getElementById('rte-toolbar');
        const rteEl   = document.getElementById('step-tooltip-input');
        if (!toolbar || !rteEl) return;

        // Format buttons (execCommand)
        toolbar.querySelectorAll('.rte-btn[data-cmd]').forEach(btn => {
            btn.addEventListener('mousedown', (e) => {
                e.preventDefault(); // keep focus in rte
                document.execCommand(btn.dataset.cmd, false, null);
                rteEl.dispatchEvent(new Event('input', { bubbles: true }));
                this._updateRteToolbarState();
            });
        });

        // Colour swatches
        toolbar.querySelectorAll('.rte-color[data-color]').forEach(btn => {
            btn.addEventListener('mousedown', (e) => {
                e.preventDefault();
                document.execCommand('foreColor', false, btn.dataset.color);
                rteEl.dispatchEvent(new Event('input', { bubbles: true }));
                this._updateRteToolbarState();
            });
        });

        // Update active states when selection changes
        rteEl.addEventListener('keyup',    () => this._updateRteToolbarState());
        rteEl.addEventListener('mouseup',  () => this._updateRteToolbarState());
        rteEl.addEventListener('focus',    () => this._updateRteToolbarState());
    }

    _updateRteToolbarState() {
        const toolbar = document.getElementById('rte-toolbar');
        if (!toolbar) return;
        // Toggle active state for format buttons
        toolbar.querySelectorAll('.rte-btn[data-cmd]').forEach(btn => {
            try {
                const active = document.queryCommandState(btn.dataset.cmd);
                btn.classList.toggle('active', active);
            } catch { /* ignore unsupported commands */ }
        });
    }

    _initBannerDrag() {
        // Banner is draggable within canvas-container.
        // Dragging stores banner_x/banner_y as fractions of canvas-container,
        // which is the same coordinate space the viewer uses.
        const getPreview = () => document.getElementById('editor-banner-preview');
        const getContainer = () => document.getElementById('canvas-container');

        let dragging = false, startX, startY, origLeft, origTop;

        document.addEventListener('mousedown', (e) => {
            const preview = getPreview();
            if (!preview || !preview.contains(e.target)) return;
            if (e.target.id === 'editor-banner-cta') return;
            e.preventDefault();
            e.stopPropagation();

            const container = getContainer();
            if (!container) return;
            dragging = true;

            // preview.style.left/top are already set as px by _positionEditorBanner
            origLeft = parseFloat(preview.style.left) || 0;
            origTop  = parseFloat(preview.style.top)  || 0;
            // Handle translateX(-50%) default case
            if (preview.style.transform && preview.style.transform !== 'none') {
                const cr = preview.getBoundingClientRect();
                const cc = container.getBoundingClientRect();
                origLeft = cr.left - cc.left;
                origTop  = cr.top  - cc.top;
                preview.style.transform = 'none';
            }
            startX = e.clientX;
            startY = e.clientY;
            preview.style.cursor = 'grabbing';
        });

        document.addEventListener('mousemove', (e) => {
            if (!dragging) return;
            const preview = getPreview();
            const container = getContainer();
            if (!preview || !container) return;

            const newLeft = origLeft + (e.clientX - startX);
            const newTop  = origTop  + (e.clientY - startY);
            preview.style.left = newLeft + 'px';
            preview.style.top  = newTop  + 'px';

            // Store as fraction of canvas-container for saving
            if (container.offsetWidth) {
                this.activeStep.banner_x = newLeft / container.offsetWidth;
                this.activeStep.banner_y = newTop  / container.offsetHeight;
            }
        });

        document.addEventListener('mouseup', () => {
            if (!dragging) return;
            dragging = false;
            const preview = getPreview();
            if (preview) preview.style.cursor = 'grab';
        });
    }

    _renderBannerCtaStepOptions(currentTarget) {
        const sel = document.getElementById('banner-cta-target');
        if (!sel || !this.activeStep) return;
        const others = this.steps.filter(s => s.id !== this.activeStep.id);
        sel.innerHTML = others.map((s, i) =>
            `<option value="${s.id}" ${currentTarget === s.id ? 'selected' : ''}>Step ${this.steps.indexOf(s)+1}: ${this._esc(s.title) || 'Untitled'}</option>`
        ).join('') || '<option value="">No other steps</option>';
    }

    async handleScreenshotUpload(input) {
        if (!input.files[0]) return;
        if (!this.activeStep) {
            this.showToast('Add a step first, then upload a screenshot', 'error');
            input.value = '';
            return;
        }
        console.log('[upload] starting upload for step', this.activeStep.id, 'demo', this.demoId);
        const fd = new FormData();
        fd.append('image', input.files[0]);
        const url = `/api/demos/${this.demoId}/steps/${this.activeStep.id}`;
        console.log('[upload] PATCH', url, 'file:', input.files[0].name, input.files[0].size, 'bytes');
        let res;
        try {
            res = await fetch(url, { method: 'PATCH', body: fd });
        } catch (err) {
            console.error('[upload] fetch error:', err);
            this.showToast('Upload failed — network error', 'error');
            input.value = '';
            return;
        }
        console.log('[upload] response status:', res.status);
        if (!res.ok) {
            const text = await res.text();
            console.error('[upload] server error:', text);
            this.showToast('Upload failed — server error', 'error');
            input.value = '';
            return;
        }
        const updated = await res.json();
        console.log('[upload] updated step:', updated);
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
        // Show upload button only if a step is active
        const hasStep = !!this.activeStep;
        const msg = document.getElementById('no-screenshot-msg');
        const btn = document.getElementById('no-screenshot-upload-btn');
        if (msg) msg.textContent = hasStep
            ? 'No screenshot yet — upload one to get started'
            : 'Add a step first, then upload a screenshot';
        if (btn) btn.style.display = hasStep ? 'inline-block' : 'none';
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

        // Select-mode drag/resize state
        this._dragHs   = null;   // hotspot being dragged/resized
        this._dragMode = null;   // 'move' | 'resize'
        this._dragOrigin = null; // {mx,my, x,y,w,h} at mousedown

        const HANDLE = 10; // px from edge counts as resize

        canvas.addEventListener('mousedown', e => {
            if (!this.activeStep) return;
            const pt = this._canvasPt(e);
            if (this.tool === 'draw') {
                this.drawing   = true;
                this.drawStart = pt;
                this.drawCurrent = pt;
            } else {
                // Select mode — hit-test for resize handle first, then body
                const hs = this._hotspotAtPoint(pt);
                if (hs) {
                    this.activeHotspotId = hs.id;
                    const cvs = document.getElementById('hotspot-canvas');
                    const hx = hs.x * cvs.width, hy = hs.y * cvs.height;
                    const hw = hs.width * cvs.width, hh = hs.height * cvs.height;
                    const nearRight  = pt.x >= hx + hw - HANDLE;
                    const nearBottom = pt.y >= hy + hh - HANDLE;
                    this._dragHs = hs;
                    this._dragOrigin = { mx: pt.x, my: pt.y, x: hs.x, y: hs.y, w: hs.width, h: hs.height };
                    this._dragMode = (nearRight || nearBottom) ? 'resize' : 'move';
                    canvas.style.cursor = this._dragMode === 'resize' ? 'nwse-resize' : 'grab';
                } else {
                    this.activeHotspotId = null;
                    this._dragHs = null;
                }
                this._renderHotspotList();
                this._redrawHotspots();
            }
        });

        canvas.addEventListener('mousemove', e => {
            const pt = this._canvasPt(e);
            if (this.tool === 'draw') {
                if (!this.drawing) return;
                this.drawCurrent = pt;
                this._redrawHotspots();
                const cvs = document.getElementById('hotspot-canvas');
                const ctx = cvs.getContext('2d');
                const r = this._normalizeRect(this.drawStart, this.drawCurrent);
                ctx.strokeStyle = '#0dcaff';
                ctx.lineWidth = 2;
                ctx.setLineDash([4, 4]);
                ctx.strokeRect(r.x, r.y, r.w, r.h);
                ctx.fillStyle = 'rgba(13,202,255,0.10)';
                ctx.fillRect(r.x, r.y, r.w, r.h);
                ctx.setLineDash([]);
            } else {
                // Update cursor when hovering over resize handle
                if (!this._dragHs) {
                    const hs = this._hotspotAtPoint(pt);
                    if (hs) {
                        const cvs = document.getElementById('hotspot-canvas');
                        const nearRight  = pt.x >= hs.x * cvs.width + hs.width * cvs.width - HANDLE;
                        const nearBottom = pt.y >= hs.y * cvs.height + hs.height * cvs.height - HANDLE;
                        canvas.style.cursor = (nearRight || nearBottom) ? 'nwse-resize' : 'grab';
                    } else {
                        canvas.style.cursor = 'default';
                    }
                    return;
                }
                if (!this._dragOrigin) return;
                const cvs = document.getElementById('hotspot-canvas');
                const dx = (pt.x - this._dragOrigin.mx) / cvs.width;
                const dy = (pt.y - this._dragOrigin.my) / cvs.height;
                if (this._dragMode === 'move') {
                    this._dragHs.x = Math.max(0, Math.min(1 - this._dragOrigin.w, this._dragOrigin.x + dx));
                    this._dragHs.y = Math.max(0, Math.min(1 - this._dragOrigin.h, this._dragOrigin.y + dy));
                } else {
                    this._dragHs.width  = Math.max(0.02, this._dragOrigin.w + dx);
                    this._dragHs.height = Math.max(0.02, this._dragOrigin.h + dy);
                }
                this._redrawHotspots();
            }
        });

        canvas.addEventListener('mouseup', async e => {
            if (this.tool === 'draw') {
                if (!this.drawing) return;
                this.drawing = false;
                // Snapshot step ID NOW before any async work, to avoid race conditions
                const targetStepId = this.activeStep?.id;
                if (!targetStepId) return;
                const end = this._canvasPt(e);
                const canvasEl = document.getElementById('hotspot-canvas');
                const r = this._normalizeRect(this.drawStart, end);
                if (r.w < 10 || r.h < 10) { this._redrawHotspots(); return; }
                this._createHotspot(r.x / canvasEl.width, r.y / canvasEl.height, r.w / canvasEl.width, r.h / canvasEl.height, targetStepId);
            } else {
                if (this._dragHs && this._dragOrigin) {
                    // Persist the updated position/size to the server
                    canvas.style.cursor = 'default';
                    const hs = this._dragHs;
                    await fetch(`/api/steps/${this.activeStep.id}/hotspots/${hs.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ x: hs.x, y: hs.y, width: hs.width, height: hs.height })
                    });
                    this._renderHotspotList();
                }
                this._dragHs = null;
                this._dragOrigin = null;
                this._dragMode = null;
            }
        });

        canvas.addEventListener('mouseleave', () => {
            if (this.tool === 'draw' && this.drawing) {
                this.drawing = false; this._redrawHotspots();
            }
            if (this._dragHs) {
                this._dragHs = null; this._dragOrigin = null; this._dragMode = null;
            }
        });

        // Handle window resize
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
        // Scale from CSS pixels to canvas pixels (they may differ if canvas is scaled by CSS)
        const scaleX = canvas.width  / rect.width;
        const scaleY = canvas.height / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top)  * scaleY
        };
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

            ctx.strokeStyle = isActive ? '#0dcaff' : 'rgba(13,202,255,0.55)';
            ctx.lineWidth   = isActive ? 2 : 1.5;
            ctx.fillStyle   = isActive ? 'rgba(13,202,255,0.14)' : 'rgba(13,202,255,0.06)';
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 4);
            ctx.fill();
            ctx.stroke();

            // Resize handle (bottom-right corner) for active hotspot
            if (isActive) {
                const hs2 = 8;
                ctx.fillStyle = '#0dcaff';
                ctx.fillRect(x + w - hs2, y + h - hs2, hs2, hs2);
            }

            // Hotspot number label
            const idx = this.hotspots.indexOf(hs) + 1;
            ctx.fillStyle = isActive ? '#0dcaff' : 'rgba(13,202,255,0.7)';
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

    async _createHotspot(x, y, width, height, stepId) {
        // Use the snapshotted stepId — never read this.activeStep here to avoid races
        const sid = stepId || this.activeStep?.id;
        if (!sid) return;
        const res = await fetch(`/api/steps/${sid}/hotspots`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label: '', x, y, width, height, action_type: 'none', action_target: null })
        });
        if (!res.ok) { this.showToast('Failed to save hotspot', 'error'); return; }
        const hs = await res.json();
        this.showToast('Hotspot added — edit it in the panel →', 'success');

        // Refresh everything from server to ensure data integrity
        const newHsId = hs.id;
        await this._refreshFromServer(sid, newHsId);
    }

    // Reload steps from server, re-select the given step, and optionally highlight a hotspot
    async _refreshFromServer(activeStepId, highlightHotspotId) {
        const res = await fetch(`/api/demos/${this.demoId}`);
        if (!res.ok) return;
        const freshDemo = await res.json();
        this.demo  = freshDemo;
        this.steps = freshDemo.steps || [];

        // Find the step we want to re-select
        const targetStep = this.steps.find(s => s.id === activeStepId) || this.steps[0];
        if (!targetStep) { this._renderStepList(); this._updateStepCounter(); return; }

        this.activeStep = targetStep;
        this.hotspots   = targetStep.hotspots || [];
        this.activeHotspotId = highlightHotspotId || null;

        this._renderStepList();
        this._updateStepCounter();
        this._renderHotspotList();
        this._updateHotspotAnchorSelect();
        this._redrawHotspots();

        // Update sidebar highlight
        document.querySelectorAll('.step-item').forEach(el => el.classList.remove('active'));
        const item = document.getElementById(`step-item-${targetStep.id}`);
        if (item) item.classList.add('active');
    }

    async deleteHotspot(hotspotId) {
        const hs = this.hotspots.find(h => h.id === hotspotId);
        if (hs) this._undoStack.push({ type: 'hotspot', stepId: this.activeStep.id, hotspot: JSON.parse(JSON.stringify(hs)) });
        const res = await fetch(`/api/steps/${this.activeStep.id}/hotspots/${hotspotId}`, { method: 'DELETE' });
        if (!res.ok) { this._undoStack.pop(); return; }
        this.hotspots = this.hotspots.filter(h => h.id !== hotspotId);
        this.activeStep.hotspots = this.hotspots;
        const s = this.steps.find(s => s.id === this.activeStep.id);
        if (s) s.hotspots = this.hotspots;
        if (this.activeHotspotId === hotspotId) this.activeHotspotId = null;
        this._renderHotspotList();
        this._updateHotspotAnchorSelect();
        this._renderStepList();
        this._redrawHotspots();
        this.showToast('Hotspot removed — Ctrl+Z to undo', 'success');
    }

    async saveHotspot(hotspotId) {
        const label            = document.getElementById(`hs-label-${hotspotId}`).value;
        const actionType       = document.getElementById(`hs-action-${hotspotId}`).value;
        const actionTarget     = actionType === 'goto'
            ? document.getElementById(`hs-target-${hotspotId}`)?.value || null : null;
        const beacon           = document.getElementById(`hs-beacon-${hotspotId}`)?.checked ? 1 : 0;
        const popover_label    = document.getElementById(`hs-popover-label-${hotspotId}`)?.value || '';

        const res = await fetch(`/api/steps/${this.activeStep.id}/hotspots/${hotspotId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                label, action_type: actionType, action_target: actionTarget,
                beacon, popover_label,
                popover_cta_label: '', popover_cta_action: 'next', popover_cta_target: null
            })
        });
        if (!res.ok) { this.showToast('Failed to save hotspot', 'error'); return; }
        const updated = await res.json();
        const idx = this.hotspots.findIndex(h => h.id === hotspotId);
        if (idx !== -1) this.hotspots[idx] = updated;
        this.activeStep.hotspots = this.hotspots;
        // Sync into master steps array too so step-list badges are current
        const s = this.steps.find(st => st.id === this.activeStep.id);
        if (s) s.hotspots = this.hotspots;
        this._renderHotspotList();
        this._updateHotspotAnchorSelect();
        this._renderStepList();
        this._redrawHotspots();
        this.showToast('Hotspot saved ✓', 'success');
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
            const actionLabel = { none: 'No action', next: 'Next Step', goto: 'Go to Step', end: 'End Demo' }[hs.action_type] || 'No action';
            const actionClass = `action-${hs.action_type}`;

            if (isActive) {
                // Render edit form inline
                const stepsExcludingSelf = this.steps.filter(s => s.id !== this.activeStep.id);
                const gotoOptions = stepsExcludingSelf.map((s, si) =>
                    `<option value="${s.id}" ${hs.action_target === s.id ? 'selected' : ''}>Step ${this.steps.indexOf(s)+1}: ${this._esc(s.title) || 'Untitled'}</option>`
                ).join('');

                // popover CTA goto options
                const popoverGotoOptions = stepsExcludingSelf.map(s =>
                    `<option value="${s.id}" ${hs.popover_cta_target === s.id ? 'selected' : ''}>Step ${this.steps.indexOf(s)+1}: ${this._esc(s.title) || 'Untitled'}</option>`
                ).join('');

                return `
                <div class="hotspot-edit-form" id="hs-form-${hs.id}">
                    <div class="form-title">
                        <span>Hotspot ${i+1}</span>
                        <button class="btn btn-danger btn-sm" onclick="editor.deleteHotspot('${hs.id}')">Delete</button>
                    </div>

                    <div class="field-group">
                        <label>Popover instruction</label>
                        <input type="text" id="hs-popover-label-${hs.id}" value="${this._esc(hs.popover_label || '')}" placeholder="e.g. Click here to continue">
                    </div>

                    <div class="field-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="hs-beacon-${hs.id}" ${hs.beacon ? 'checked' : ''}>
                            Show beacon
                        </label>
                    </div>

                    <!-- label kept as hidden so saveHotspot can still read it -->
                    <input type="hidden" id="hs-label-${hs.id}" value="${this._esc(hs.label)}">

                    <hr style="border-color:var(--border-light);margin:8px 0;">

                    <div class="field-group">
                        <label>Hotspot click action</label>
                        <select id="hs-action-${hs.id}" onchange="editor._toggleActionTarget('${hs.id}')">
                            <option value="none" ${(!hs.action_type||hs.action_type==='none')?'selected':''}>— Do nothing</option>
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

    _togglePopoverCtaTarget(hotspotId) {
        const sel = document.getElementById(`hs-popover-cta-action-${hotspotId}`);
        const group = document.getElementById(`hs-popover-cta-target-group-${hotspotId}`);
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

    // ── Bulk screenshot import ────────────────────────────────

    async handleBulkUpload(input) {
        if (!input.files || !input.files.length) return;

        // Sort files by name (numeric prefix or timestamp order)
        const files = Array.from(input.files).sort((a, b) =>
            a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
        );

        this.showToast(`Importing ${files.length} screenshot${files.length !== 1 ? 's' : ''}…`, 'success');

        let created = 0;
        for (const file of files) {
            // Derive a step title from filename: strip leading "01-" prefix and extension
            const rawName = file.name.replace(/\.[^.]+$/, '');           // remove extension
            const cleanName = rawName.replace(/^\d+[-_.\s]+/, '');       // strip leading number
            const title = cleanName.replace(/[-_]/g, ' ')                // dashes/underscores → spaces
                .replace(/\b\w/g, c => c.toUpperCase());                 // title case

            // Create the step
            const stepRes = await fetch(`/api/demos/${this.demoId}/steps`, {
                method: 'POST',
                body: (() => {
                    const fd = new FormData();
                    fd.append('title', title);
                    fd.append('tooltip', '');
                    return fd;
                })()
            });
            if (!stepRes.ok) { this.showToast(`Failed on file: ${file.name}`, 'error'); continue; }
            const step = await stepRes.json();
            step.hotspots = [];

            // Upload the screenshot to that step
            const imgFd = new FormData();
            imgFd.append('image', file);
            const imgRes = await fetch(`/api/demos/${this.demoId}/steps/${step.id}`, {
                method: 'PATCH', body: imgFd
            });
            if (imgRes.ok) {
                const updated = await imgRes.json();
                step.image_path = updated.image_path;
            }

            this.steps.push(step);
            created++;
        }

        this._renderStepList();
        this._updateStepCounter();
        if (this.steps.length > 0 && created > 0) {
            // Select the first newly created step
            const firstNew = this.steps[this.steps.length - created];
            this.selectStep(firstNew.id);
        }
        this.showToast(`✓ ${created} step${created !== 1 ? 's' : ''} created — add tooltips and hotspots to each`, 'success');
        input.value = '';
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
