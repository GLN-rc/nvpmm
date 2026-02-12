'use strict';

class BlogPdfApp {
    constructor() {
        // Form elements
        this.form       = document.getElementById('generate-form');
        this.blogUrlIn  = document.getElementById('blog-url');
        this.pageSelIn  = document.getElementById('page-preference');
        this.docInput   = document.getElementById('brand-doc-input');
        this.docDropArea = document.getElementById('doc-drop-area');
        this.docFileList = document.getElementById('doc-file-list');
        this.generateBtn = document.getElementById('generate-btn');

        // Sections
        this.inputSection   = document.getElementById('input-section');
        this.loadingSection = document.getElementById('loading-section');
        this.resultsSection = document.getElementById('results-section');

        // Loading
        this.loadingMsg = document.getElementById('loading-message');
        this.steps = {
            fetch: document.getElementById('step-fetch'),
            doc:   document.getElementById('step-doc'),
            ai:    document.getElementById('step-ai'),
            pdf:   document.getElementById('step-pdf'),
        };

        // Results
        this.downloadBtn     = document.getElementById('download-btn');
        this.newBriefBtn     = document.getElementById('new-brief-btn');
        this.extraPageBanner = document.getElementById('extra-page-banner');
        this.upgradeBtn      = document.getElementById('upgrade-pages-btn');
        this.keepBtn         = document.getElementById('keep-pages-btn');

        // State
        this.brandDocFiles = [];   // multiple files
        this.currentPdfB64 = null;
        this.currentFilename = null;
        this.currentExtracted = null;
        this.currentBlogUrl  = null;

        this.init();
    }

    init() {
        // Form submit
        this.form.addEventListener('submit', e => this.handleSubmit(e));

        // File upload
        document.getElementById('browse-doc-link').addEventListener('click', (e) => {
            e.stopPropagation();  // prevent bubble to drop area which also calls .click()
            this.docInput.click();
        });
        this.docDropArea.addEventListener('click', () => this.docInput.click());
        this.docInput.addEventListener('change', e => {
            if (e.target.files.length) this.addDocFiles(Array.from(e.target.files));
        });

        // Drag & drop
        this.docDropArea.addEventListener('dragover', e => {
            e.preventDefault();
            this.docDropArea.classList.add('dragover');
        });
        this.docDropArea.addEventListener('dragleave', () => {
            this.docDropArea.classList.remove('dragover');
        });
        this.docDropArea.addEventListener('drop', e => {
            e.preventDefault();
            this.docDropArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) this.addDocFiles(Array.from(e.dataTransfer.files));
        });

        // Results buttons
        this.downloadBtn.addEventListener('click', () => this.triggerDownload());
        this.newBriefBtn.addEventListener('click', () => this.reset());

        // Extra page banner
        this.upgradeBtn.addEventListener('click', () => {
            this.extraPageBanner.classList.add('hidden');
            this.pageSelIn.value = '3';
            this.regenerate();
        });
        this.keepBtn.addEventListener('click', () => {
            this.extraPageBanner.classList.add('hidden');
        });

        // Tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });
    }

    // ── File handling ──────────────────────────────────────────────────────
    addDocFiles(files) {
        const allowed = ['.pdf', '.docx', '.doc', '.txt', '.md'];
        for (const file of files) {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (!allowed.includes(ext)) {
                alert(`Skipped "${file.name}" — only PDF, DOCX, TXT, or MD accepted.`);
                continue;
            }
            // Deduplicate by name
            if (!this.brandDocFiles.find(f => f.name === file.name)) {
                this.brandDocFiles.push(file);
            }
        }
        this.docInput.value = ''; // reset so same file can be re-added after removal
        this.renderDocFiles();
    }

    renderDocFiles() {
        if (!this.brandDocFiles.length) {
            this.docFileList.innerHTML = '';
            return;
        }
        this.docFileList.innerHTML = this.brandDocFiles.map((f, i) => {
            const size = (f.size / 1024).toFixed(1);
            return `
            <div class="file-item">
                <span class="file-name">📄 ${this.esc(f.name)} <span style="color:var(--grey-medium)">(${size} KB)</span></span>
                <button class="remove-btn" data-idx="${i}" title="Remove">✕</button>
            </div>`;
        }).join('');
        this.docFileList.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.idx);
                this.brandDocFiles.splice(idx, 1);
                this.renderDocFiles();
            });
        });
    }

    // ── Submit ─────────────────────────────────────────────────────────────
    async handleSubmit(e) {
        e.preventDefault();

        const url = this.blogUrlIn.value.trim();
        if (!url) {
            this.blogUrlIn.focus();
            return;
        }

        this.currentBlogUrl = url;
        this.showLoading();

        const formData = new FormData();
        formData.append('blog_url', url);
        formData.append('page_preference', this.pageSelIn.value);
        for (const file of this.brandDocFiles) {
            formData.append('brand_docs', file);
        }

        await this.callGenerate(formData);
    }

    async regenerate() {
        if (!this.currentBlogUrl) return;
        this.showLoading();

        const formData = new FormData();
        formData.append('blog_url', this.currentBlogUrl);
        formData.append('page_preference', this.pageSelIn.value);
        for (const file of this.brandDocFiles) {
            formData.append('brand_docs', file);
        }

        await this.callGenerate(formData);
    }

    async callGenerate(formData) {
        try {
            // Simulate step-by-step progress
            this.setStep('fetch');
            await this.delay(800);
            this.completeStep('fetch');
            this.setStep('doc');
            await this.delay(500);
            this.completeStep('doc');
            this.setStep('ai');
            this.setLoadingMsg('AI is extracting content...');

            const response = await fetch('/api/generate', {
                method: 'POST',
                body: formData
            });

            this.completeStep('ai');
            this.setStep('pdf');
            this.setLoadingMsg('Building PDF...');
            await this.delay(400);

            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(err.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            this.completeStep('pdf');

            await this.delay(300);
            this.showResults(data);

        } catch (err) {
            this.hideLoading();
            this.showError(err.message);
        }
    }

    // ── Results rendering ──────────────────────────────────────────────────
    showResults(data) {
        this.currentPdfB64    = data.pdf_b64;
        this.currentFilename  = data.filename;
        this.currentExtracted = data.extracted;

        this.hideLoading();
        this.resultsSection.classList.remove('hidden');

        const ex = data.extracted || {};

        // Extra page banner
        if (ex.needs_extra_page && this.pageSelIn.value === '2') {
            this.extraPageBanner.classList.remove('hidden');
        } else {
            this.extraPageBanner.classList.add('hidden');
        }

        // Preview tab
        this.setText('prev-title', ex.title || '—');
        this.setText('prev-subtitle', ex.subtitle || '—');
        this.setText('prev-exec-summary', ex.exec_summary || '—');

        const tkList = document.getElementById('prev-takeaways');
        tkList.innerHTML = (ex.takeaways || []).map(t =>
            `<li>${this.esc(t)}</li>`
        ).join('');

        const sectionsEl = document.getElementById('prev-sections');
        sectionsEl.innerHTML = (ex.sections || []).map((s, i) => `
            <div class="section-preview">
                <h4>${this.esc(s.header || `Section ${i + 1}`)}</h4>
                <p>${this.esc(s.body || '')}</p>
            </div>
        `).join('');

        this.setText('prev-elev-header', ex.elevator_pitch_header || '');
        this.setText('prev-elev-body', ex.elevator_pitch_body || '(No elevator pitch found in brand doc)');
        const ctaLine = [ex.cta_text, ex.cta_url].filter(Boolean).join('  ');
        this.setText('prev-elev-cta', ctaLine || '');

        // Images tab
        this.renderImageSuggestions(ex.image_suggestions || [], ex);

        this.switchTab('preview');
    }

    renderImageSuggestions(suggestions, extracted) {
        const list = document.getElementById('image-suggestions-list');
        const none = document.getElementById('no-image-suggestions');

        if (!suggestions || suggestions.length === 0) {
            list.innerHTML = '';
            none.classList.remove('hidden');
            return;
        }

        none.classList.add('hidden');

        list.innerHTML = suggestions.map((s, i) => {
            const sectionLabel = s.section_index !== undefined
                ? (extracted.sections || [])[s.section_index]?.header || `Section ${s.section_index + 1}`
                : `Image ${i + 1}`;
            return `
            <div class="image-suggestion-card" id="img-card-${i}">
                <h4>📌 ${this.esc(sectionLabel)}</h4>
                <p>${this.esc(s.description || '')}</p>
                <div class="image-actions">
                    <button class="btn btn-wine btn-sm" onclick="app.generateImage(${i})">
                        ✨ Generate Image
                    </button>
                    <label class="btn btn-outline btn-sm" style="cursor:pointer;">
                        ⬆ Upload Image
                        <input type="file" class="image-upload-input" accept="image/*"
                               onchange="app.uploadImage(${i}, this)">
                    </label>
                </div>
                <div class="image-result hidden" id="img-result-${i}"></div>
            </div>`;
        }).join('');
    }

    async generateImage(suggestionIndex) {
        if (!this.currentExtracted) return;

        const suggestion = (this.currentExtracted.image_suggestions || [])[suggestionIndex];
        if (!suggestion) return;

        const card = document.getElementById(`img-card-${suggestionIndex}`);
        const btn = card.querySelector('.btn-wine');
        const resultEl = document.getElementById(`img-result-${suggestionIndex}`);

        btn.disabled = true;
        btn.innerHTML = '<span class="inline-spinner"></span>Generating...';

        try {
            // Call OpenAI image generation
            const resp = await fetch('/api/generate-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: suggestion.prompt,
                    section_index: suggestion.section_index
                })
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || 'Image generation failed');
            }

            const data = await resp.json();

            // Re-generate PDF with this image
            await this.regenerateWithImage(suggestion.section_index, data.image_b64, 'generated.png');

            resultEl.textContent = '✅ Image generated and added to PDF. Download updated brief.';
            resultEl.className = 'image-result success';
            resultEl.classList.remove('hidden');

        } catch (err) {
            resultEl.textContent = `⚠ ${err.message}`;
            resultEl.className = 'image-result error';
            resultEl.classList.remove('hidden');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '✨ Generate Image';
        }
    }

    async uploadImage(suggestionIndex, fileInput) {
        const file = fileInput.files[0];
        if (!file || !this.currentExtracted) return;

        const resultEl = document.getElementById(`img-result-${suggestionIndex}`);
        resultEl.textContent = 'Processing...';
        resultEl.className = 'image-result';
        resultEl.classList.remove('hidden');

        try {
            const formData = new FormData();
            formData.append('brief_json', JSON.stringify(this.currentExtracted));
            formData.append('section_index', suggestionIndex);
            formData.append('image_file', file);

            const resp = await fetch('/api/regenerate-with-image', {
                method: 'POST',
                body: formData
            });

            if (!resp.ok) throw new Error('Regeneration failed');

            const data = await resp.json();
            this.currentPdfB64   = data.pdf_b64;
            this.currentFilename = data.filename;

            resultEl.textContent = '✅ Image added to PDF. Download updated brief.';
            resultEl.className = 'image-result success';

        } catch (err) {
            resultEl.textContent = `⚠ ${err.message}`;
            resultEl.className = 'image-result error';
        }
    }

    async regenerateWithImage(sectionIndex, imageB64, filename) {
        const blob = this.b64ToBlob(imageB64, 'image/png');
        const file = new File([blob], filename, { type: 'image/png' });

        const formData = new FormData();
        formData.append('brief_json', JSON.stringify(this.currentExtracted));
        formData.append('section_index', sectionIndex);
        formData.append('image_file', file);

        const resp = await fetch('/api/regenerate-with-image', {
            method: 'POST',
            body: formData
        });

        if (!resp.ok) throw new Error('Regeneration failed');
        const data = await resp.json();
        this.currentPdfB64   = data.pdf_b64;
        this.currentFilename = data.filename;
    }

    // ── Download ───────────────────────────────────────────────────────────
    triggerDownload() {
        if (!this.currentPdfB64) return;
        const blob = this.b64ToBlob(this.currentPdfB64, 'application/pdf');
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href     = url;
        a.download = this.currentFilename || 'replica-brief.pdf';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // ── Loading state ──────────────────────────────────────────────────────
    showLoading() {
        this.inputSection.classList.add('hidden');
        this.resultsSection.classList.add('hidden');
        this.loadingSection.classList.remove('hidden');
        // Reset steps
        Object.values(this.steps).forEach(s => {
            s.classList.remove('active', 'completed');
        });
        this.setLoadingMsg('Fetching blog content...');
    }

    hideLoading() {
        this.loadingSection.classList.add('hidden');
    }

    setStep(name) {
        const el = this.steps[name];
        if (el) el.classList.add('active');
        const messages = {
            fetch: 'Fetching blog content...',
            doc:   'Reading brand document...',
            ai:    'AI is extracting and structuring content...',
            pdf:   'Building your PDF...'
        };
        this.setLoadingMsg(messages[name] || '');
    }

    completeStep(name) {
        const el = this.steps[name];
        if (el) {
            el.classList.remove('active');
            el.classList.add('completed');
        }
    }

    setLoadingMsg(msg) {
        if (this.loadingMsg) this.loadingMsg.textContent = msg;
    }

    // ── Tabs ───────────────────────────────────────────────────────────────
    switchTab(tabId) {
        document.querySelectorAll('.tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tabId);
        });
        document.querySelectorAll('.tab-content').forEach(tc => {
            tc.classList.toggle('active', tc.id === `tab-${tabId}`);
        });
    }

    // ── Reset ──────────────────────────────────────────────────────────────
    reset() {
        this.currentPdfB64    = null;
        this.currentFilename  = null;
        this.currentExtracted = null;
        this.currentBlogUrl   = null;

        this.blogUrlIn.value   = '';
        this.pageSelIn.value   = '2';
        this.brandDocFiles     = [];
        this.docInput.value    = '';
        this.renderDocFiles();

        this.resultsSection.classList.add('hidden');
        this.loadingSection.classList.add('hidden');
        this.inputSection.classList.remove('hidden');
        this.extraPageBanner.classList.add('hidden');
        window.scrollTo(0, 0);
    }

    // ── Error ──────────────────────────────────────────────────────────────
    showError(message) {
        this.inputSection.classList.remove('hidden');
        // Show inline error near submit button
        let errEl = document.getElementById('form-error');
        if (!errEl) {
            errEl = document.createElement('p');
            errEl.id = 'form-error';
            errEl.style.cssText = 'color:#d32f2f;text-align:center;margin-top:12px;font-size:0.9rem;';
            document.querySelector('.submit-row').after(errEl);
        }
        errEl.textContent = `⚠ ${message}`;
        setTimeout(() => { if (errEl) errEl.textContent = ''; }, 8000);
    }

    // ── Helpers ────────────────────────────────────────────────────────────
    esc(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    b64ToBlob(b64, type) {
        const binary = atob(b64);
        const arr = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
        return new Blob([arr], { type });
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Boot
const app = new BlogPdfApp();
