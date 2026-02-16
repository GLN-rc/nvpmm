/* ══════════════════════════════════════════════════════════════
   tryMe — Viewer
   ══════════════════════════════════════════════════════════════ */

class TryMeViewer {
    constructor() {
        this.demoId     = null;
        this.demo       = null;   // full demo object
        this.steps      = [];     // ordered steps with hotspots
        this.stepIndex  = 0;      // current step (0-based)
        this.persona    = null;   // selected persona string
        this.history    = [];     // stack of step indices for back navigation

        this._init();
    }

    async _init() {
        // Get demoId from URL: /demo/{demoId}
        const parts = location.pathname.split('/').filter(Boolean);
        this.demoId = parts.length >= 2 ? parts[1] : null;

        if (!this.demoId) {
            document.body.innerHTML = '<div style="padding:60px;text-align:center;color:var(--text-muted);">No demo ID in URL.</div>';
            return;
        }

        // Fetch full demo
        const res = await fetch(`/api/demos/${this.demoId}/full`);
        if (!res.ok) {
            document.body.innerHTML = '<div style="padding:60px;text-align:center;color:var(--text-muted);">Demo not found.</div>';
            return;
        }
        this.demo  = await res.json();
        this.steps = this.demo.steps || [];

        // Set page title
        document.title = `${this.demo.title} — tryMe`;
        document.getElementById('pg-demo-title').textContent = this.demo.title;
        document.getElementById('pg-demo-desc').textContent  = this.demo.description || '';
        document.getElementById('vt-title').textContent      = this.demo.title;

        // Check sessionStorage for returning viewer
        const savedPersona = sessionStorage.getItem(`tryme-persona-${this.demoId}`);

        if (!this.steps.length) {
            // Skip gate, show empty state directly
            this._showViewer();
            document.getElementById('no-steps-screen').style.display = 'flex';
            return;
        }

        if (savedPersona) {
            this.persona = savedPersona;
            this._showViewer();
            this._renderCurrentStep();
        } else {
            this._renderPersonaGate();
        }
    }

    // ── Persona gate ──────────────────────────────────────────

    _renderPersonaGate() {
        const container = document.getElementById('pg-personas');
        const personas  = this.demo.personas && this.demo.personas.length
            ? this.demo.personas
            : []; // show nothing if no personas configured

        if (!personas.length) {
            // Auto-start with no persona selection
            this._showViewer();
            this._renderCurrentStep();
            return;
        }

        container.innerHTML = personas.map(p => `
            <div class="persona-option" onclick="viewer._selectPersona(this, '${this._esc(p)}')">
                <div class="check"></div>
                <span>${this._esc(p)}</span>
            </div>
        `).join('');
    }

    _selectPersona(el, persona) {
        this.persona = persona;
        document.querySelectorAll('.persona-option').forEach(o => o.classList.remove('selected'));
        el.classList.add('selected');
    }

    startDemo() {
        if (this.demo.personas && this.demo.personas.length && !this.persona) {
            // flash the persona selector
            const container = document.getElementById('pg-personas');
            container.style.outline = '2px solid var(--accent-warm)';
            setTimeout(() => container.style.outline = '', 600);
            return;
        }
        if (this.persona) {
            sessionStorage.setItem(`tryme-persona-${this.demoId}`, this.persona);
        }
        this._showViewer();
        this._renderCurrentStep();
    }

    _showViewer() {
        document.getElementById('persona-gate').classList.add('hidden');
        document.getElementById('viewer-layout').style.display = 'grid';
    }

    // ── Step rendering ────────────────────────────────────────

    _renderCurrentStep() {
        if (!this.steps.length) return;
        const step = this.steps[this.stepIndex];

        // Persona badge
        if (this.persona) {
            const badge = document.getElementById('persona-badge');
            badge.textContent = this.persona;
            badge.style.display = 'inline-flex';
        }

        // Progress pills
        this._renderProgressPills();

        // Step label
        document.getElementById('step-label').textContent =
            `Step ${this.stepIndex + 1} of ${this.steps.length}`;

        // Tooltip banner
        const banner = document.getElementById('tooltip-banner');
        if (step.tooltip && step.tooltip.trim()) {
            banner.textContent = step.tooltip;
            banner.classList.add('visible');
        } else {
            banner.classList.remove('visible');
        }

        // Screenshot
        const container = document.getElementById('screenshot-container');
        const img = document.getElementById('demo-img');
        const noSteps = document.getElementById('no-steps-screen');

        if (step.image_path) {
            noSteps.style.display = 'none';
            container.style.display = 'inline-block';
            img.onload = () => this._renderHotspots(step);
            img.src = step.image_path;
        } else {
            // No screenshot — still show hotspots area with message
            container.style.display = 'none';
            noSteps.style.display   = 'flex';
            noSteps.innerHTML = `<div class="icon">📷</div><p>Step ${this.stepIndex+1}: ${this._esc(step.title || 'Untitled')} — no screenshot uploaded yet.</p>`;
        }

        // Nav buttons
        document.getElementById('nav-back').disabled    = this.history.length === 0;
        document.getElementById('nav-forward').disabled = this.stepIndex >= this.steps.length - 1;
        document.getElementById('nav-step-display').textContent = `${this.stepIndex + 1} / ${this.steps.length}`;
    }

    _renderProgressPills() {
        const container = document.getElementById('progress-pills');
        container.innerHTML = this.steps.map((_, i) => {
            const cls = i < this.stepIndex ? 'done' : i === this.stepIndex ? 'current' : '';
            return `<div class="progress-pill ${cls}"></div>`;
        }).join('');
    }

    _renderHotspots(step) {
        const overlay = document.getElementById('hotspot-overlay');
        const img     = document.getElementById('demo-img');
        overlay.innerHTML = '';

        const hotspots = step.hotspots || [];
        hotspots.forEach(hs => {
            const el = document.createElement('div');
            el.className = 'hs-region';
            el.style.left   = (hs.x * 100) + '%';
            el.style.top    = (hs.y * 100) + '%';
            el.style.width  = (hs.width  * 100) + '%';
            el.style.height = (hs.height * 100) + '%';

            // Tooltip popover
            if (hs.label) {
                const tip = document.createElement('div');
                tip.className = 'hs-tooltip';
                tip.textContent = hs.label;
                el.appendChild(tip);
            }

            // Click handler
            el.addEventListener('click', (e) => {
                this._spawnRipple(e);
                this._executeAction(hs);
            });

            overlay.appendChild(el);
        });
    }

    _spawnRipple(e) {
        const ripple = document.createElement('div');
        ripple.className = 'click-ripple';
        ripple.style.left = e.clientX + 'px';
        ripple.style.top  = e.clientY + 'px';
        document.body.appendChild(ripple);
        setTimeout(() => ripple.remove(), 480);
    }

    _executeAction(hs) {
        switch (hs.action_type) {
            case 'next':
                this._advanceToIndex(this.stepIndex + 1);
                break;
            case 'goto': {
                const idx = this.steps.findIndex(s => s.id === hs.action_target);
                if (idx !== -1) this._advanceToIndex(idx);
                else this._advanceToIndex(this.stepIndex + 1);
                break;
            }
            case 'end':
                this._showCompletion();
                break;
            default:
                this._advanceToIndex(this.stepIndex + 1);
        }
    }

    _advanceToIndex(newIndex) {
        if (newIndex >= this.steps.length) {
            this._showCompletion();
            return;
        }
        this.history.push(this.stepIndex);
        this.stepIndex = newIndex;
        this._renderCurrentStep();
    }

    // ── Navigation buttons ────────────────────────────────────

    goBack() {
        if (!this.history.length) return;
        this.stepIndex = this.history.pop();
        this._renderCurrentStep();
    }

    goForward() {
        if (this.stepIndex >= this.steps.length - 1) { this._showCompletion(); return; }
        this._advanceToIndex(this.stepIndex + 1);
    }

    // ── Completion ────────────────────────────────────────────

    _showCompletion() {
        document.getElementById('viewer-layout').style.display = 'none';
        document.getElementById('completion-screen').classList.add('visible');
    }

    restart() {
        this.stepIndex = 0;
        this.history   = [];
        document.getElementById('completion-screen').classList.remove('visible');
        document.getElementById('viewer-layout').style.display = 'grid';
        this._renderCurrentStep();
    }

    // ── Utils ─────────────────────────────────────────────────

    _esc(s) {
        return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
}

const viewer = new TryMeViewer();
