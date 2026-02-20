/* ══════════════════════════════════════════════════════════════
   tryMe — Viewer  (beacon · fade · tooltip-close · pointer · popovers)
   ══════════════════════════════════════════════════════════════ */

class TryMeViewer {
    constructor() {
        this.demoId         = null;
        this.demo           = null;
        this.steps          = [];
        this.stepIndex      = 0;
        this.history        = [];
        this._transitioning = false;
        this._currentStep   = null;   // kept for resize re-positioning
        this._resizeTimer   = null;

        this._init();
    }

    async _init() {
        const parts = location.pathname.split('/').filter(Boolean);
        this.demoId = parts.length >= 2 ? parts[1] : null;

        if (!this.demoId) {
            document.body.innerHTML = '<div style="padding:60px;text-align:center;color:var(--text-muted);">No demo ID in URL.</div>';
            return;
        }

        const res = await fetch(`/api/demos/${this.demoId}/full`);
        if (!res.ok) {
            document.body.innerHTML = '<div style="padding:60px;text-align:center;color:var(--text-muted);">Demo not found.</div>';
            return;
        }
        this.demo  = await res.json();
        this.steps = this.demo.steps || [];

        document.title = `${this.demo.title} — Replica`;
        document.getElementById('vt-title').textContent = this.demo.title;

        if (!this.steps.length) {
            document.getElementById('no-steps-screen').style.display = 'flex';
            return;
        }

        this._bindTooltipClose();
        this._renderCurrentStep();

        // Re-position banner when the window is resized so pixel positions stay accurate.
        window.addEventListener('resize', () => {
            clearTimeout(this._resizeTimer);
            this._resizeTimer = setTimeout(() => {
                if (!this._currentStep) return;
                const step = this._currentStep;
                const hasTooltip  = !!(step.tooltip_html || step.tooltip || '').replace(/<[^>]*>/g, '').trim();
                const hasCtaLabel = !!(step.banner_cta_label && step.banner_cta_label.trim());
                if (hasTooltip || hasCtaLabel) this._positionBanner(step, true);
            }, 80);
        });
    }

    // ── Step rendering ────────────────────────────────────────

    async _renderCurrentStep(animate = false) {
        if (!this.steps.length || this._transitioning) return;
        const step   = this.steps[this.stepIndex];
        this._currentStep = step;   // save for resize re-positioning
        const isLast = this.stepIndex >= this.steps.length - 1;

        // Progress pills
        this._renderProgressPills();

        // Step label
        document.getElementById('step-label').textContent =
            `Step ${this.stepIndex + 1} of ${this.steps.length}`;

        // Nav buttons
        document.getElementById('nav-back').disabled = this.history.length === 0;
        const fwdBtn = document.getElementById('nav-forward');
        fwdBtn.textContent = isLast ? 'Finish →' : 'Next →';
        fwdBtn.disabled = false;
        document.getElementById('nav-step-display').textContent = `${this.stepIndex + 1} / ${this.steps.length}`;

        // (crossfade handled below in screenshot section)

        // ── Tooltip banner — content only; position applied after image loads ──
        const banner      = document.getElementById('tooltip-banner');
        const tooltipText = document.getElementById('tooltip-text');
        const tooltipCta  = document.getElementById('tooltip-cta');

        // Use rich HTML if available, otherwise fall back to plain text
        const htmlContent = step.tooltip_html || (step.tooltip ? step.tooltip.replace(/\n/g, '<br>') : '');
        const hasTooltip  = !!(htmlContent.replace(/<[^>]*>/g, '').trim());
        const hasCtaLabel = !!(step.banner_cta_label && step.banner_cta_label.trim());

        // Hide banner during image transition to avoid position glitch
        banner.className = 'step-tooltip-banner';   // remove 'visible', clears pointer classes
        banner.style.left = banner.style.top = banner.style.transform = '';

        if (hasTooltip || hasCtaLabel) {
            tooltipText.innerHTML = htmlContent;   // render rich text
            if (hasCtaLabel) {
                tooltipCta.textContent = step.banner_cta_label;
                tooltipCta.classList.remove('hidden');
                tooltipCta._action = step.banner_cta_action || 'next';
                tooltipCta._target = step.banner_cta_target || null;
            } else {
                tooltipCta.classList.add('hidden');
            }
        } else {
            tooltipCta.classList.add('hidden');
        }

        // ── Screenshot ──
        const container = document.getElementById('screenshot-container');
        const imgEl     = document.getElementById('demo-img');
        const imgNext   = document.getElementById('demo-img-next');
        const noSteps   = document.getElementById('no-steps-screen');

        if (step.image_path) {
            noSteps.style.display   = 'none';
            container.style.display = 'inline-block';

            // Normalise both URLs to relative paths for comparison
            // (imgEl.src is absolute: "http://host/uploads/…", step.image_path is "/uploads/…")
            const currentRelSrc = imgEl.src
                ? imgEl.src.replace(location.origin, '').split('?')[0]
                : '';
            const targetRelSrc = step.image_path.split('?')[0];
            const sameImage = (currentRelSrc === targetRelSrc && currentRelSrc !== '');

            if (animate && !sameImage && imgEl.complete && imgEl.naturalWidth) {
                // Different image, current image already loaded — do crossfade
                this._transitioning = true;
                // Preload next image into the back layer
                await new Promise(resolve => {
                    imgNext.onload  = resolve;
                    imgNext.onerror = resolve;
                    imgNext.src = step.image_path;
                    imgNext.style.opacity = '0';
                    // If browser already has it cached and onload won't fire,
                    // fall back after a short timeout
                    setTimeout(resolve, 1500);
                });
                // Both images loaded — crossfade: fade old out, new in simultaneously
                imgEl.style.transition  = 'opacity 0.25s ease';
                imgNext.style.transition = 'opacity 0.25s ease';
                imgEl.style.opacity  = '0';
                imgNext.style.opacity = '1';
                await new Promise(r => setTimeout(r, 260));
                // Swap: promote next layer to main, reset back layer
                imgEl.style.transition = 'none';
                imgNext.style.transition = 'none';
                imgEl.src = step.image_path;
                imgEl.style.opacity = '1';
                imgNext.style.opacity = '0';
                imgNext.src = '';
                this._transitioning = false;
                // Wait one frame so the browser recomputes layout with the new image
                // before we read offsetWidth/Height for banner positioning.
                await new Promise(r => requestAnimationFrame(r));
            } else if (!sameImage) {
                // First display — wait for image to load
                await new Promise(resolve => {
                    const onDone = () => { imgEl.onload = null; imgEl.onerror = null; resolve(); };
                    imgEl.onload  = onDone;
                    imgEl.onerror = onDone;
                    imgEl.src = step.image_path;
                });
            }
            // Always re-render hotspots and position banner after image is ready.
            // Wait one rAF after rendering hotspots so the browser computes their
            // offsetLeft/Top before _positionBanner reads them.
            this._renderHotspots(step);
            await new Promise(r => requestAnimationFrame(r));
            this._positionBanner(step, hasTooltip || hasCtaLabel);
        } else {
            container.style.display = 'none';
            noSteps.style.display   = 'flex';
            noSteps.innerHTML = `<div class="icon">📷</div><p>Step ${this.stepIndex+1}: ${this._esc(step.title || 'Untitled')} — no screenshot yet.</p>`;
            this._transitioning = false;
        }
    }

    _renderProgressPills() {
        const container = document.getElementById('progress-pills');
        container.innerHTML = this.steps.map((_, i) => {
            const cls = i < this.stepIndex ? 'done' : i === this.stepIndex ? 'current' : '';
            return `<div class="progress-pill ${cls}" title="Step ${i+1}" onclick="viewer._jumpTo(${i})"></div>`;
        }).join('');
    }

    _jumpTo(index) {
        if (index === this.stepIndex || this._transitioning) return;
        this.history.push(this.stepIndex);
        this.stepIndex = index;
        this._renderCurrentStep(true);
    }

    // ── Hotspot rendering ─────────────────────────────────────

    _renderHotspots(step) {
        const overlay = document.getElementById('hotspot-overlay');
        overlay.innerHTML = '';

        (step.hotspots || []).forEach(hs => {
            // Outer region div
            const el = document.createElement('div');
            el.className = 'hs-region';
            el.dataset.hsId = hs.id;   // used by _positionBanner for anchor lookup
            el.style.left   = (hs.x * 100) + '%';
            el.style.top    = (hs.y * 100) + '%';
            el.style.width  = (hs.width  * 100) + '%';
            el.style.height = (hs.height * 100) + '%';

            // ── Beacon dot ──
            if (hs.beacon) {
                const beacon = document.createElement('div');
                beacon.className = 'hs-beacon';
                el.appendChild(beacon);
            }

            // ── Popover (instruction) ──
            if (hs.popover_label || hs.popover_cta_label) {
                const pop = document.createElement('div');
                pop.className = 'hs-popover';
                // Pointer triangle is a CSS ::after on the popover

                if (hs.popover_label) {
                    const txt = document.createElement('p');
                    txt.className = 'hs-popover-text';
                    txt.textContent = hs.popover_label;
                    pop.appendChild(txt);
                }

                if (hs.popover_cta_label) {
                    const cta = document.createElement('button');
                    cta.className = 'hs-popover-cta';
                    cta.textContent = hs.popover_cta_label;
                    cta.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this._spawnRipple(e);
                        this._executeAction({ action_type: hs.popover_cta_action, action_target: hs.popover_cta_target });
                    });
                    pop.appendChild(cta);
                }

                el.appendChild(pop);
            }

            // ── Click handler on region ──
            el.addEventListener('click', (e) => {
                // Don't double-fire if CTA button was clicked
                if (e.target.classList.contains('hs-popover-cta')) return;
                this._spawnRipple(e);
                this._executeAction(hs);
            });

            overlay.appendChild(el);
        });
    }

    // Position the banner after the image has loaded.
    // The banner and hotspot overlay both live inside screenshot-container, so
    // hotspot offsetLeft/Top are directly usable as banner left/top values.
    // --ptr-h / --ptr-v CSS vars are set so the pointer triangle aims at the
    // hotspot center even when the banner is clamped to the screen edge.
    _positionBanner(step, hasBannerContent) {
        const banner = document.getElementById('tooltip-banner');
        if (!hasBannerContent) {
            banner.className = 'step-tooltip-banner'; // stay hidden
            return;
        }

        const sc  = document.getElementById('screenshot-container');
        const ptr = step.banner_pointer || 'none';

        // Park offscreen so browser computes real banner dimensions before we use them.
        banner.style.cssText = 'left:-9999px;top:-9999px;transform:none;';
        banner.className = 'step-tooltip-banner visible';
        if (ptr !== 'none') banner.classList.add(`pointer-${ptr}`);

        const bw = banner.offsetWidth;
        const bh = banner.offsetHeight;

        const anchorId = step.banner_hotspot_id;
        if (anchorId && sc) {
            const hsEl = document.querySelector(`.hs-region[data-hs-id="${anchorId}"]`);
            if (hsEl) {
                // hsEl lives in .hotspot-overlay (top:0;left:0 inside sc) — same coords as banner.
                const hsCx = hsEl.offsetLeft + hsEl.offsetWidth  / 2;
                const hsCy = hsEl.offsetTop  + hsEl.offsetHeight / 2;
                const gap  = 12;
                let left, top;

                if (ptr === 'bottom') {
                    left = hsCx - bw / 2;
                    top  = hsCy - hsEl.offsetHeight / 2 - bh - gap;
                } else if (ptr === 'top') {
                    left = hsCx - bw / 2;
                    top  = hsCy + hsEl.offsetHeight / 2 + gap;
                } else if (ptr === 'right') {
                    left = hsCx - hsEl.offsetWidth / 2 - bw - gap;
                    top  = hsCy - bh / 2;
                } else if (ptr === 'left') {
                    left = hsCx + hsEl.offsetWidth / 2 + gap;
                    top  = hsCy - bh / 2;
                } else {
                    left = hsCx - bw / 2;
                    top  = hsCy - hsEl.offsetHeight / 2 - bh - gap;
                }

                // Clamp within screenshot-container bounds
                const clampedLeft = Math.max(8, Math.min(left, sc.offsetWidth  - bw - 8));
                const clampedTop  = Math.max(8, Math.min(top,  sc.offsetHeight - bh - 8));

                // Set pointer offset vars so triangle aims at hotspot center even after clamping
                // --ptr-h: px from banner left to hotspot center (for top/bottom pointers)
                // --ptr-v: px from banner top  to hotspot center (for left/right pointers)
                const ptrH = hsCx - clampedLeft;
                const ptrV = hsCy - clampedTop;
                banner.style.setProperty('--ptr-h', Math.max(16, Math.min(ptrH, bw - 16)) + 'px');
                banner.style.setProperty('--ptr-v', Math.max(16, Math.min(ptrV, bh - 16)) + 'px');

                banner.style.left      = clampedLeft + 'px';
                banner.style.top       = clampedTop  + 'px';
                banner.style.transform = 'none';
                return;
            }
        }

        // No hotspot anchor — try saved banner_x/banner_y fractional coordinates
        if (step.banner_x != null && step.banner_y != null && sc && sc.offsetWidth) {
            let left2 = step.banner_x * sc.offsetWidth;
            let top2  = step.banner_y * sc.offsetHeight;
            left2 = Math.max(8, Math.min(left2, sc.offsetWidth  - bw - 8));
            top2  = Math.max(8, Math.min(top2,  sc.offsetHeight - bh - 8));
            banner.style.left      = left2 + 'px';
            banner.style.top       = top2  + 'px';
            banner.style.transform = 'none';
            return;
        }

        // Final fallback: float centered near top of the image
        banner.style.left      = '50%';
        banner.style.top       = '16px';
        banner.style.transform = 'translateX(-50%)';
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
            case 'none': break; // do nothing — just show hover/popover
            case 'next':
                this._advanceToIndex(this.stepIndex + 1); break;
            case 'goto': {
                const idx = this.steps.findIndex(s => s.id === hs.action_target);
                this._advanceToIndex(idx !== -1 ? idx : this.stepIndex + 1);
                break;
            }
            case 'end':
                this._showCompletion(); break;
            default:
                break; // unknown action — do nothing
        }
    }

    _advanceToIndex(newIndex) {
        if (newIndex >= this.steps.length) { this._showCompletion(); return; }
        this.history.push(this.stepIndex);
        this.stepIndex = newIndex;
        this._renderCurrentStep(true);
    }

    // ── Navigation ────────────────────────────────────────────

    goBack() {
        if (!this.history.length || this._transitioning) return;
        this.stepIndex = this.history.pop();
        this._renderCurrentStep(true);
    }

    goForward() {
        if (this._transitioning) return;
        if (this.stepIndex >= this.steps.length - 1) { this._showCompletion(); return; }
        this._advanceToIndex(this.stepIndex + 1);
    }

    // ── Tooltip close ─────────────────────────────────────────

    _bindTooltipClose() {
        const btn = document.getElementById('tooltip-close-btn');
        const banner = document.getElementById('tooltip-banner');
        if (btn) {
            btn.addEventListener('click', () => {
                banner.classList.add('dismissed');
            });
        }

        // CTA button
        const cta = document.getElementById('tooltip-cta');
        if (cta) {
            cta.addEventListener('click', () => {
                this._spawnRipple({ clientX: cta.getBoundingClientRect().left, clientY: cta.getBoundingClientRect().top });
                this._executeAction({ action_type: cta._action || 'next', action_target: cta._target || null });
            });
        }
    }

    // ── Completion ────────────────────────────────────────────

    _showCompletion() {
        document.getElementById('viewer-layout').style.display = 'none';
        document.getElementById('completion-screen').classList.add('visible');
    }

    restart() {
        this.stepIndex      = 0;
        this.history        = [];
        this._transitioning = false;
        // Un-dismiss tooltip
        document.getElementById('tooltip-banner')?.classList.remove('dismissed');
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
