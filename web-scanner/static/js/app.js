/**
 * Website Competitor Scanner - Frontend Application
 */

class WebsiteScanner {
    constructor() {
        this.form = document.getElementById('scan-form');
        this.fileInput = document.getElementById('file-input');
        this.fileDropArea = document.getElementById('file-drop-area');
        this.fileList = document.getElementById('file-list');
        this.uploadedFiles = [];

        this.inputSection = document.getElementById('input-section');
        this.loadingSection = document.getElementById('loading-section');
        this.resultsSection = document.getElementById('results-section');

        this.init();
    }

    init() {
        // Form submission
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));

        // File upload handling
        this.fileDropArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Drag and drop
        this.fileDropArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.fileDropArea.classList.add('dragover');
        });

        this.fileDropArea.addEventListener('dragleave', () => {
            this.fileDropArea.classList.remove('dragover');
        });

        this.fileDropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.fileDropArea.classList.remove('dragover');
            this.handleFileDrop(e.dataTransfer.files);
        });

        // Tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => this.filterRecommendations(btn.dataset.filter));
        });

        // New scan button
        document.getElementById('new-scan-btn')?.addEventListener('click', () => this.resetForm());
    }

    handleFileSelect(e) {
        this.addFiles(e.target.files);
    }

    handleFileDrop(files) {
        this.addFiles(files);
    }

    addFiles(files) {
        const allowedTypes = ['.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'];

        for (const file of files) {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (allowedTypes.includes(ext)) {
                if (!this.uploadedFiles.find(f => f.name === file.name)) {
                    this.uploadedFiles.push(file);
                }
            }
        }

        this.renderFileList();
    }

    renderFileList() {
        this.fileList.innerHTML = this.uploadedFiles.map((file, index) => `
            <div class="file-item">
                <span class="file-name">${file.name}</span>
                <button type="button" class="remove-btn" data-index="${index}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        `).join('');

        this.fileList.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.uploadedFiles.splice(parseInt(btn.dataset.index), 1);
                this.renderFileList();
            });
        });
    }

    async handleSubmit(e) {
        e.preventDefault();

        const yourWebsite = document.getElementById('your-website').value.trim();
        const competitorUrls = document.getElementById('competitor-urls').value.trim();
        const focusAreas = document.getElementById('focus-areas').value.trim();

        if (!yourWebsite) {
            alert('Please enter your website URL');
            return;
        }

        // Show loading
        this.showLoading();

        try {
            // Build form data
            const formData = new FormData();
            formData.append('your_website', yourWebsite);
            formData.append('competitor_urls', competitorUrls.replace(/\n/g, ','));

            if (focusAreas) {
                formData.append('focus_areas', focusAreas);
            }

            for (const file of this.uploadedFiles) {
                formData.append('brand_docs', file);
            }

            // Simulate progress updates
            this.updateProgress('your-site');
            await this.delay(500);

            // Make API request
            const response = await fetch('/api/scan', {
                method: 'POST',
                body: formData
            });

            this.updateProgress('competitors');
            await this.delay(300);

            if (!response.ok) {
                throw new Error(`Analysis failed: ${response.statusText}`);
            }

            this.updateProgress('documents');
            await this.delay(300);

            const results = await response.json();

            this.updateProgress('analysis');
            await this.delay(300);

            // Display results
            this.displayResults(results);

        } catch (error) {
            console.error('Analysis error:', error);
            alert(`Error: ${error.message}`);
            this.resetForm();
        }
    }

    showLoading() {
        this.inputSection.style.display = 'none';
        this.loadingSection.classList.add('active');
        this.resultsSection.classList.remove('active');
    }

    hideLoading() {
        this.loadingSection.classList.remove('active');
    }

    updateProgress(step) {
        const steps = document.querySelectorAll('.progress-step');
        let reachedCurrent = false;

        steps.forEach(s => {
            if (s.dataset.step === step) {
                s.classList.add('active');
                s.classList.remove('completed');
                reachedCurrent = true;
            } else if (!reachedCurrent) {
                s.classList.remove('active');
                s.classList.add('completed');
            } else {
                s.classList.remove('active', 'completed');
            }
        });

        const messages = {
            'your-site': 'Analyzing your website...',
            'competitors': 'Scanning competitor websites...',
            'documents': 'Processing your documents...',
            'analysis': 'Generating recommendations...'
        };

        document.getElementById('loading-message').textContent = messages[step] || 'Analyzing...';
    }

    displayResults(results) {
        this.hideLoading();
        this.resultsSection.classList.add('active');
        this.resultsSection.style.display = 'block';

        // Store results for export
        this.currentResults = results;

        // Store metric explanations for tooltips
        this.metricExplanations = results.metric_explanations || {};

        // Show which URL was analyzed
        const analyzedUrl = results.your_site_analysis?.url || 'Unknown';
        document.getElementById('analyzed-url').textContent = `Page analyzed: ${analyzedUrl}`;

        // Render priority actions
        this.renderPriorityActions(results.priority_actions);

        // Render copy suggestions
        this.renderCopySuggestions(results.your_site_analysis, results.recommendations);

        // Render all recommendations
        this.renderRecommendations(results.recommendations);

        // Render site analysis with explanations
        this.renderSiteAnalysis(results.your_site_analysis, results.metric_insights);

        // Render competitor comparison
        this.renderCompetitorComparison(results.your_site_analysis, results.competitor_analyses);

        // Set up export button
        document.getElementById('export-btn')?.addEventListener('click', () => this.exportReport());

        // Scroll to results
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    renderPriorityActions(actions) {
        const container = document.getElementById('priority-list');

        if (!actions || actions.length === 0) {
            container.innerHTML = '<p>No priority actions identified.</p>';
            return;
        }

        container.innerHTML = actions.map((action, index) => `
            <div class="priority-item">
                <div class="priority-number">${index + 1}</div>
                <div class="priority-content">
                    <h4>${action.title}</h4>
                    <p>
                        <span class="badge badge-category">${action.category}</span>
                        <span class="badge badge-impact-${action.impact}">Impact: ${action.impact}</span>
                        <span class="badge badge-effort-${action.effort}">Effort: ${action.effort}</span>
                    </p>
                    ${action.description ? `<p style="margin-top: 8px; color: #666;">${action.description}</p>` : ''}
                    ${action.all_actions && action.all_actions.length > 0 ? `
                        <div style="margin-top: 10px; padding: 10px; background: #f5f5f5; border-radius: 6px;">
                            <strong style="font-size: 0.85rem;">Action steps:</strong>
                            <ul style="margin: 5px 0 0 20px; font-size: 0.85rem;">
                                ${action.all_actions.map(a => `<li>${a}</li>`).join('')}
                            </ul>
                        </div>
                    ` : (action.first_step ? `<p style="margin-top: 8px;"><strong>First step:</strong> ${action.first_step}</p>` : '')}
                </div>
            </div>
        `).join('');
    }

    renderRecommendations(recommendations) {
        const container = document.getElementById('recommendations-list');

        if (!recommendations || recommendations.length === 0) {
            container.innerHTML = '<p>No recommendations available.</p>';
            return;
        }

        container.innerHTML = recommendations.map(rec => `
            <div class="recommendation" data-category="${rec.category}">
                <div class="recommendation-header">
                    <h3 class="recommendation-title">${rec.title}</h3>
                    <div class="recommendation-badges">
                        <span class="badge badge-category">${rec.category}</span>
                        <span class="badge badge-impact-${rec.impact}">Impact: ${rec.impact}</span>
                        <span class="badge badge-effort-${rec.effort}">Effort: ${rec.effort}</span>
                    </div>
                </div>
                <p class="recommendation-description">${rec.description}</p>
                ${rec.specific_actions && rec.specific_actions.length > 0 ? `
                    <div class="recommendation-actions">
                        <h4>Action Steps:</h4>
                        <ul>
                            ${rec.specific_actions.map(action => `<li>${action}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                ${rec.expected_outcome ? `
                    <p style="margin-top: 12px; font-size: 0.875rem; color: var(--olive-green);">
                        <strong>Expected outcome:</strong> ${rec.expected_outcome}
                    </p>
                ` : ''}
            </div>
        `).join('');
    }

    renderSiteAnalysis(analysis, metricInsights) {
        const metricsContainer = document.getElementById('site-metrics');
        const issuesList = document.getElementById('issues-list');
        const strengthsList = document.getElementById('strengths-list');

        if (!analysis) {
            metricsContainer.innerHTML = '<p>No analysis data available.</p>';
            return;
        }

        const seo = analysis.seo_factors || {};
        const tech = analysis.technical_factors || {};
        const llm = analysis.llm_discoverability || {};
        const geo = analysis.geo_factors || {};
        const msg = analysis.page_messaging || {};
        const explanations = this.metricExplanations || {};

        // Helper to get explanation
        const getExp = (key) => explanations[key] || {};

        // Page Messaging Summary card
        const messagingHtml = `
            <div class="analysis-card" style="grid-column: 1 / -1; border-left: 4px solid var(--persimmon);">
                <h4 style="color: var(--persimmon); margin-bottom: 14px;">Page Messaging Summary</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px;">
                    <div style="background: #fafafa; padding: 12px; border-radius: 6px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Primary Message (H1 / Hero)</div>
                        <div style="font-size: 0.95rem; font-weight: 600; color: #222;">${msg.primary_message || '<em style="color:#aaa">Not detected</em>'}</div>
                    </div>
                    <div style="background: #fafafa; padding: 12px; border-radius: 6px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Value Proposition (First visible paragraph)</div>
                        <div style="font-size: 0.9rem; color: #444;">${msg.value_proposition || '<em style="color:#aaa">Not detected</em>'}</div>
                    </div>
                    <div style="background: #fafafa; padding: 12px; border-radius: 6px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Apparent Audience</div>
                        <div style="font-size: 0.9rem; color: #444;">${msg.apparent_audience || '<em style="color:#aaa">Not explicitly stated on page</em>'}</div>
                    </div>
                    <div style="background: #fafafa; padding: 12px; border-radius: 6px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 4px;">Page Tone</div>
                        <div style="font-size: 0.9rem; color: #444;">${msg.tone || 'Unknown'}</div>
                    </div>
                </div>
                ${msg.key_claims && msg.key_claims.length > 0 ? `
                    <div style="margin-top: 12px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 6px;">Key Section Headlines (H2s)</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                            ${msg.key_claims.map(c => `<span style="background: #f0f4e8; color: var(--olive-green-dark); padding: 4px 10px; border-radius: 12px; font-size: 0.82rem;">${c}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
                ${msg.cta_language && msg.cta_language.length > 0 ? `
                    <div style="margin-top: 12px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 6px;">CTA / Button Language Found</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                            ${msg.cta_language.map(c => `<span style="background: #fff0e8; color: var(--persimmon); padding: 4px 10px; border-radius: 12px; font-size: 0.82rem;">${c}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;

        // Render metric insights if available
        let insightsHtml = '';
        if (metricInsights && metricInsights.length > 0) {
            insightsHtml = `
                <div class="analysis-card" style="grid-column: 1 / -1; background: linear-gradient(135deg, #fff9e6 0%, #fff 100%); border-left: 4px solid var(--persimmon);">
                    <h4 style="color: var(--persimmon); margin-bottom: 15px;">Key Insights vs Competitors</h4>
                    ${metricInsights.map(insight => `
                        <div style="margin-bottom: 15px; padding: 12px; background: white; border-radius: 8px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <strong>${getExp(insight.metric)?.name || insight.metric}</strong>
                                <span class="badge ${insight.status === 'behind' ? 'badge-impact-high' : 'badge-impact-low'}">${insight.status === 'behind' ? 'Needs Work' : 'Ahead'}</span>
                            </div>
                            <p style="font-size: 0.9rem; color: #666; margin-bottom: 8px;">
                                <strong>You:</strong> ${insight.your_value} | <strong>Competitors:</strong> ${insight.competitor_avg}
                            </p>
                            <p style="font-size: 0.85rem; color: #888; margin-bottom: 8px;"><em>Why it matters:</em> ${insight.explanation}</p>
                            <p style="font-size: 0.85rem; color: var(--olive-green);"><strong>Recommendation:</strong> ${insight.recommendation}</p>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        // Metrics cards
        metricsContainer.innerHTML = messagingHtml + insightsHtml + `
            <div class="analysis-card">
                <h4>SEO Factors</h4>
                <div class="metric">
                    <span class="metric-label">Title Length</span>
                    <span class="metric-value ${seo.title_length >= 30 && seo.title_length <= 60 ? 'good' : 'warning'}">${seo.title_length || 0} chars</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Meta Description</span>
                    <span class="metric-value ${seo.meta_description_length >= 120 && seo.meta_description_length <= 160 ? 'good' : 'warning'}">${seo.meta_description_length || 0} chars</span>
                </div>
                <div class="metric">
                    <span class="metric-label">H1 Tags</span>
                    <span class="metric-value ${(seo.h1_tags?.length || 0) === 1 ? 'good' : 'warning'}">${seo.h1_tags?.length || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Word Count</span>
                    <span class="metric-value">${seo.word_count || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Images Missing Alt</span>
                    <span class="metric-value ${(seo.images_without_alt || 0) === 0 ? 'good' : 'warning'}">${seo.images_without_alt || 0}</span>
                </div>
            </div>

            <div class="analysis-card">
                <h4>Technical Factors</h4>
                <div class="metric">
                    <span class="metric-label">HTTPS</span>
                    <span class="metric-value ${tech.https ? 'good' : 'bad'}">${tech.https ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Sitemap</span>
                    <span class="metric-value ${tech.has_sitemap ? 'good' : 'warning'}">${tech.has_sitemap ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Robots.txt</span>
                    <span class="metric-value ${tech.has_robots_txt ? 'good' : 'warning'}">${tech.has_robots_txt ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Mobile Viewport</span>
                    <span class="metric-value ${tech.mobile_friendly_hints?.length > 0 ? 'good' : 'bad'}">${tech.mobile_friendly_hints?.length > 0 ? 'Yes' : 'No'}</span>
                </div>
            </div>

            <div class="analysis-card">
                <h4>LLM &amp; GEO Discoverability</h4>
                <div class="metric">
                    <span class="metric-label">Structured Content</span>
                    <span class="metric-value ${llm.structured_content ? 'good' : 'warning'}">${llm.structured_content ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">FAQ Schema</span>
                    <span class="metric-value ${llm.faq_schema ? 'good' : 'warning'}">${llm.faq_schema ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">How-To Schema</span>
                    <span class="metric-value ${llm.how_to_schema ? 'good' : 'warning'}">${llm.how_to_schema ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">External Citations</span>
                    <span class="metric-value">${llm.citations_and_sources || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Statistics Present</span>
                    <span class="metric-value ${geo.statistics_present ? 'good' : 'warning'}">${geo.statistics_present ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Comparison Tables</span>
                    <span class="metric-value ${geo.comparison_tables ? 'good' : 'warning'}">${geo.comparison_tables ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">AI Citation Ready</span>
                    <span class="metric-value ${geo.citation_ready ? 'good' : 'warning'}">${geo.citation_ready ? 'Yes' : 'No'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Lists/Bullet Points</span>
                    <span class="metric-value">${geo.lists_and_bullets || 0}</span>
                </div>
            </div>
        `;

        // Issues
        const issues = analysis.issues || [];
        issuesList.innerHTML = issues.length > 0 ? issues.map(issue => `
            <li class="issue-item">
                <span class="issue-icon ${issue.severity}">!</span>
                <span>${issue.issue} <small>(${issue.category})</small></span>
            </li>
        `).join('') : '<li>No issues found!</li>';

        // Strengths
        const strengths = analysis.strengths || [];
        strengthsList.innerHTML = strengths.length > 0 ? strengths.map(strength => `
            <li class="strength-item">
                <span class="strength-icon">✓</span>
                <span>${strength.strength} <small>(${strength.category})</small></span>
            </li>
        `).join('') : '<li>Analysis in progress...</li>';
    }

    renderCompetitorComparison(yourSite, competitors) {
        const container = document.getElementById('competitor-comparison');

        if (!competitors || competitors.length === 0) {
            container.innerHTML = '<p>No competitor data available.</p>';
            return;
        }

        const yourSeo = yourSite?.seo_factors || {};
        const yourWords = yourSeo.word_count || 0;

        // Metric definitions with tooltips
        const metrics = [
            {
                label: 'Word Count',
                tooltip: 'Total words on the homepage. More content generally signals depth & expertise. Homepages: aim for 500–1,000+. Key landing pages: 1,500–2,500+. If a competitor has significantly more words, search engines and AI may view their page as more comprehensive.',
                good: (v) => v >= 500,
                warn: (v) => v > 0 && v < 500,
                your: yourSeo.word_count ?? 'N/A',
                comp: (c) => c.seo_factors?.word_count ?? 'N/A',
                context: (v) => {
                    if (!yourWords || !v || isNaN(v)) return '';
                    if (v > yourWords * 1.5) return ' ▲ more than you';
                    if (v < yourWords * 0.7) return ' ▼ less than you';
                    return ' ≈ similar';
                }
            },
            {
                label: 'Structured Data',
                tooltip: 'Structured data (JSON-LD / schema.org markup) tells search engines and AI exactly what your page is about — product, organization, FAQ, etc. It enables rich results in Google (star ratings, FAQ dropdowns) and makes your content more citable by AI systems like ChatGPT and Perplexity. ✓ is good, ✗ is a missed opportunity.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.content_analysis?.has_structured_data ? '✓' : '✗',
                comp: (c) => c.content_analysis?.has_structured_data ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'FAQ Schema',
                tooltip: 'FAQ schema markup tags your Q&A content so Google can display it as expandable "People Also Ask" results, and so AI assistants (ChatGPT, Gemini, Perplexity) can extract and surface your answers directly. ✓ = implemented, ✗ = missing. Low effort, high visibility impact.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.llm_discoverability?.faq_schema ? '✓' : '✗',
                comp: (c) => c.llm_discoverability?.faq_schema ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'Statistics / Data',
                tooltip: 'Does the page include specific numbers, percentages, or data points? (e.g. "94% of threats stopped", "10,000 customers"). AI systems strongly prefer citing pages with concrete data over vague claims. ✓ means detectable numbers found, ✗ means the page relies on qualitative language only.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.geo_factors?.statistics_present ? '✓' : '✗',
                comp: (c) => c.geo_factors?.statistics_present ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'AI Citation Ready',
                tooltip: 'A composite score: does the page have statistics AND either expert quotes or multiple lists? Citation-ready content is what AI tools (ChatGPT, Perplexity, Gemini) pull from when answering user questions. ✓ means your page is more likely to be recommended or quoted by AI search engines.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.geo_factors?.citation_ready ? '✓' : '✗',
                comp: (c) => c.geo_factors?.citation_ready ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'Comparison Tables',
                tooltip: 'HTML tables on the page. Tables are extremely effective for winning "X vs Y" and "best [product]" queries — both in featured snippets and AI responses. If a competitor has tables and you don\'t, they have a structural advantage for comparison searches.',
                good: (v) => v === '✓',
                warn: () => false,
                your: yourSite?.geo_factors?.comparison_tables ? '✓' : '✗',
                comp: (c) => c.geo_factors?.comparison_tables ? '✓' : '✗',
                context: () => ''
            },
            {
                label: 'Lists / Bullets',
                tooltip: 'Number of bulleted or numbered lists. Lists are highly scannable for humans and easily extractable by AI. They frequently become featured snippets. Aim for 3+ lists on key pages.',
                good: (v) => v >= 3,
                warn: (v) => v > 0 && v < 3,
                your: yourSite?.geo_factors?.lists_and_bullets ?? 'N/A',
                comp: (c) => c.geo_factors?.lists_and_bullets ?? 'N/A',
                context: () => ''
            },
            {
                label: 'Issues Found',
                tooltip: 'Number of SEO / technical issues detected on the page (missing meta tags, broken alt text, no sitemap, etc.). Fewer is better — this is a rough health indicator. Your own issue list in the "Your Site Analysis" tab has the full details.',
                good: (v) => !isNaN(v) && Number(v) === 0,
                warn: (v) => !isNaN(v) && Number(v) > 0 && Number(v) <= 3,
                your: yourSite?.issues?.length ?? 0,
                comp: (c) => c.issues?.length ?? 0,
                context: () => ''
            }
        ];

        const cellStyle = (val, m) => {
            const v = val;
            if (m.good(v)) return 'color: var(--success); font-weight: 600;';
            if (m.warn(v)) return 'color: var(--warning); font-weight: 600;';
            if (v === '✗') return 'color: var(--error);';
            return '';
        };

        const tableHtml = `
            <style>
                .tt-wrap { position: relative; display: inline-flex; align-items: center; gap: 5px; cursor: default; }
                .tt-icon { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px;
                           border-radius: 50%; background: #ccc; color: white; font-size: 10px; font-weight: 700;
                           cursor: help; flex-shrink: 0; }
                .tt-box { display: none; position: absolute; left: 0; top: 100%; margin-top: 4px; z-index: 100;
                          background: #222; color: #fff; font-size: 0.78rem; line-height: 1.45; padding: 10px 12px;
                          border-radius: 6px; width: 280px; box-shadow: 0 4px 16px rgba(0,0,0,0.25); pointer-events: none; }
                .tt-wrap:hover .tt-box { display: block; }
            </style>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
                    <thead>
                        <tr style="background: var(--grey-lightest);">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid var(--grey-light); min-width: 180px;">Metric</th>
                            <th style="padding: 12px; text-align: center; border-bottom: 2px solid var(--grey-light); background: var(--olive-green); color: white; min-width: 100px;">Your Site</th>
                            ${competitors.map(c => `
                                <th style="padding: 12px; text-align: center; border-bottom: 2px solid var(--grey-light); min-width: 120px;">${c.domain || c.url || 'Competitor'}</th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${metrics.map(m => `
                            <tr>
                                <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">
                                    <span class="tt-wrap">
                                        ${m.label}
                                        <span class="tt-icon">?</span>
                                        <span class="tt-box">${m.tooltip}</span>
                                    </span>
                                </td>
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); ${cellStyle(m.your, m)}">${m.your}</td>
                                ${competitors.map(c => {
                                    const val = m.comp(c);
                                    const ctx = m.context(val);
                                    return `<td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); ${cellStyle(val, m)}">${val}<span style="font-size:0.72rem; color:#999;">${ctx}</span></td>`;
                                }).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        // Competitor blurbs
        const blurbsHtml = competitors.map(c => {
            if (c.status !== 'success') return '';
            const msg = c.page_messaging || {};
            const seo = c.seo_factors || {};
            const domain = c.domain || c.url || 'Competitor';
            return `
                <div style="background: white; border: 1px solid var(--grey-light); border-radius: 8px; padding: 20px; margin-top: 16px;">
                    <h4 style="margin: 0 0 12px 0; color: var(--olive-green-dark);">${domain}</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.875rem;">
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">What they're conveying</div>
                            <div style="color: #333;">${msg.primary_message || seo.title || '<em style="color:#aaa">Not detected</em>'}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">Apparent audience</div>
                            <div style="color: #333;">${msg.apparent_audience || '<em style="color:#aaa">Not explicitly stated</em>'}</div>
                        </div>
                        <div style="grid-column: 1 / -1;">
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">Value prop visitor would walk away with</div>
                            <div style="color: #333;">${msg.value_proposition || '<em style="color:#aaa">Not detected — page may rely on visuals or a single headline</em>'}</div>
                        </div>
                        ${msg.tone ? `
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">Tone</div>
                            <div style="color: #333;">${msg.tone}</div>
                        </div>` : ''}
                        ${msg.cta_language && msg.cta_language.length > 0 ? `
                        <div>
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 3px;">CTA language</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px;">
                                ${msg.cta_language.slice(0, 5).map(ct => `<span style="background: #fff0e8; color: var(--persimmon); padding: 2px 8px; border-radius: 10px; font-size: 0.78rem;">${ct}</span>`).join('')}
                            </div>
                        </div>` : ''}
                        ${msg.keyword_targets && msg.keyword_targets.length > 0 ? `
                        <div style="grid-column: 1 / -1;">
                            <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 5px;">Keywords they appear to be targeting</div>
                            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                ${msg.keyword_targets.map(kw => `<span style="background: var(--grey-lightest); color: var(--grey-dark); border: 1px solid var(--grey-light); padding: 2px 10px; border-radius: 10px; font-size: 0.78rem; font-weight: 500;">${kw}</span>`).join('')}
                            </div>
                        </div>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = tableHtml + `
            <h4 style="margin: 28px 0 4px; color: var(--olive-green-dark);">Competitor Messaging Breakdown</h4>
            <p style="font-size: 0.85rem; color: #888; margin-bottom: 0;">What each competitor is trying to say, who they're talking to, and the value prop a visitor would walk away with.</p>
            ${blurbsHtml}
        `;
    }

    renderCopySuggestions(analysis, recommendations) {
        const container = document.getElementById('copy-suggestions-list');
        if (!container) return;

        const seo = analysis?.seo_factors || {};
        const msg = analysis?.page_messaging || {};
        const geo = analysis?.geo_factors || {};
        const llm = analysis?.llm_discoverability || {};
        const currentTitle = seo.title || '';
        const currentH1 = seo.h1_tags?.[0] || '';
        const currentMeta = seo.meta_description || '';
        const companyName = this.extractCompanyName(currentTitle);

        // Pull actual CTAs found on the page
        const existingCtas = msg.cta_language || [];
        const existingCtaStr = existingCtas.length > 0
            ? existingCtas.slice(0, 4).join(' / ')
            : '(none detected)';

        // Pull key claims / H2s actually on the page
        const existingClaims = msg.key_claims || [];
        const existingValueProp = msg.value_proposition || '';

        // Title length feedback
        const titleLen = seo.title_length || 0;
        const titleFeedback = titleLen === 0 ? 'Missing — critical issue'
            : titleLen < 30 ? `${titleLen} chars — too short, losing keyword opportunity`
            : titleLen > 60 ? `${titleLen} chars — too long, will be cut off in search results`
            : `${titleLen} chars — good length`;

        // Meta description feedback
        const metaLen = seo.meta_description_length || 0;
        const metaFeedback = metaLen === 0 ? 'Missing — search engines will auto-generate one (often poor)'
            : metaLen > 160 ? `${metaLen} chars — will be truncated in results`
            : metaLen < 120 ? `${metaLen} chars — could be longer to include more value`
            : `${metaLen} chars — good length`;

        const suggestions = [];

        // --- 1. Page Title ---
        const titleSugs = [];
        if (currentTitle) {
            // Derive suggestions from actual title
            const kw = currentTitle.split(/[|\-–—]/)[1]?.trim() || '';
            titleSugs.push(`${companyName} | ${kw || 'Secure Isolated Browsing'} — Enterprise-Grade Protection`);
            titleSugs.push(`${kw || 'Browser Isolation'} for Enterprise Security Teams | ${companyName}`);
        }
        titleSugs.push(`Zero-Trust Web Security Built for Enterprise | ${companyName}`);
        suggestions.push({
            category: "Page Title",
            current: `${currentTitle || '(No title found)'} — ${titleFeedback}`,
            items: titleSugs,
            why: `Titles are the #1 on-page SEO factor. They appear in browser tabs, search results, and are read first by AI systems. Optimal length: 50–60 characters. Include your primary keyword in the first half.`
        });

        // --- 2. Main Headline (H1) ---
        const h1Sug = [];
        if (currentH1) {
            // Suggest improvements based on what's actually there
            h1Sug.push(`${currentH1} — Without Slowing Your Team Down`);
            h1Sug.push(`The ${currentH1.split(' ').slice(0, 3).join(' ')} Built for Enterprise Security`);
        }
        h1Sug.push('Stop Web-Based Threats Before They Reach Your Network');
        h1Sug.push('Isolated Browsing. Zero Compromise. Full Productivity.');
        suggestions.push({
            category: "Main Headline (H1)",
            current: currentH1 || '(No H1 found — this is a critical SEO issue)',
            items: h1Sug,
            why: "Your H1 is the first thing both visitors and AI systems read. It must answer 'What does this company do and why should I care?' within 5 seconds. One H1 per page only."
        });

        // --- 3. Meta Description ---
        const metaSugs = [
            `${companyName} isolates web sessions so threats never reach your network. Protect your team without impacting productivity. Book a 15-min demo.`,
            `Stop phishing, malware, and zero-day attacks at the browser layer. ${companyName} gives enterprise teams secure, isolated browsing. Free security assessment.`,
            `Trusted by enterprise security teams for zero-trust web access. ${companyName} isolates threats before they hit your endpoints. See how it works in 2 minutes.`
        ];
        suggestions.push({
            category: "Meta Description",
            current: `${currentMeta ? currentMeta.slice(0, 120) + (currentMeta.length > 120 ? '…' : '') : '(None found)'} — ${metaFeedback}`,
            items: metaSugs,
            why: "Meta descriptions are your ad copy in search results — they don't affect ranking directly, but they determine whether someone clicks. Include a clear benefit and a specific CTA. Aim for 150–160 characters."
        });

        // --- 4. Hero / Value Prop statement ---
        const vpSugs = [
            'Web threats stopped at the source. Your productivity stays intact.',
            '100% of web-borne threats isolated. 0% impact on your team\'s workflow.',
            `Enterprise security teams trust ${companyName} because we eliminate the browser as an attack surface — without adding friction.`
        ];
        suggestions.push({
            category: "Hero Value Proposition",
            current: existingValueProp
                ? `"${existingValueProp.slice(0, 120)}${existingValueProp.length > 120 ? '…' : ''}"`
                : '(No clear value prop statement detected in hero area)',
            items: vpSugs,
            why: "Your value prop should appear above the fold and answer: Who is this for? What problem does it solve? Why you specifically? Lead with the customer outcome, not the product feature."
        });

        // --- 5. CTA copy ---
        const ctaSugs = [
            'See How It Works (2-min demo)',
            'Get Your Free Security Assessment',
            'Start Protecting Your Team Today',
            'Calculate Your Risk Exposure →',
            'Watch a 90-Second Overview'
        ];
        const genericCtaWarning = existingCtas.some(c =>
            /^(learn more|get started|click here|submit|contact us|read more)$/i.test(c.trim())
        );
        suggestions.push({
            category: "Call-to-Action Buttons",
            current: `Found on page: ${existingCtaStr}${genericCtaWarning ? ' ⚠ generic CTAs detected' : ''}`,
            items: ctaSugs,
            why: "Generic CTAs ('Learn More', 'Get Started') tell visitors nothing about what they'll get. Specific, benefit-driven CTAs improve click-through rates significantly. The CTA should match what stage of awareness the visitor is at."
        });

        // --- 6. Social proof / trust signals ---
        const trustSugs = [
            `Trusted by 500+ enterprise security teams in ${new Date().getFullYear()}`,
            `"${companyName} reduced our web-based incidents by 94%" — [Customer Name], CISO at [Company]`,
            'SOC 2 Type II Certified | FedRAMP Authorized | ISO 27001 Compliant',
            "Featured in Gartner's Market Guide for Browser Isolation"
        ];
        suggestions.push({
            category: "Social Proof & Trust Signals",
            current: '(Add trust signals near your primary CTA and hero section)',
            items: trustSugs,
            why: "Trust signals reduce purchase anxiety and are critical for enterprise buyers. AI systems also use trust signals as authority indicators when deciding what to recommend. Place them near your primary CTA for maximum conversion impact."
        });

        // --- 7. Differentiation / "Why us" ---
        const diffSugs = [
            `Unlike VPNs or endpoint agents, ${companyName} isolates threats at the browser layer — nothing ever touches your network.`,
            `The only [category] solution that [your specific differentiator] without requiring [common objection].`,
            `While competitors require agents on every device, ${companyName} works with your existing infrastructure from day one.`
        ];
        suggestions.push({
            category: "Differentiation Statement",
            current: '(Add a "Why us" or "How we\'re different" section)',
            items: diffSugs,
            why: "Enterprise buyers evaluate multiple vendors. If your differentiation isn't explicit, visitors — and AI systems answering 'best [category]' queries — have no reason to choose you over a competitor. Use 'Unlike X, we...' or 'The only solution that...' patterns."
        });

        // --- 8. FAQ / AI-optimized copy (if no FAQ schema) ---
        if (!llm.faq_schema) {
            const faqSugs = [
                'Q: How is browser isolation different from a VPN?\nA: A VPN encrypts traffic but doesn\'t prevent malicious web content from reaching your device. Browser isolation runs the entire web session in a remote container — threats never execute locally.',
                'Q: Does it slow down browsing?\nA: No. [Company] uses streaming rendering so pages load at full speed with zero malware risk.',
                'Q: What threats does it protect against?\nA: Phishing, drive-by downloads, ransomware delivery via web, zero-day exploits, and malvertising — all blocked at the browser layer before they reach your endpoints.'
            ];
            suggestions.push({
                category: "FAQ Copy (for AI & Voice Search)",
                current: '(No FAQ section or FAQ schema detected)',
                items: faqSugs,
                why: "Adding a FAQ section with FAQPage schema markup can trigger rich results in Google and gets your answers surfaced by AI assistants (ChatGPT, Perplexity, Gemini). Write questions exactly as your buyers would ask them. Low effort, high visibility payoff."
            });
        }

        // --- 9. Statistics / data points (if none found) ---
        if (!geo.statistics_present) {
            const statSugs = [
                '[X]% of breaches involve web-based vectors — isolate them at the source.',
                'Deployed across [X] enterprise organizations, protecting [X]M endpoints.',
                'Average time to deploy: [X] hours. Average reduction in web-borne incidents: [X]%.'
            ];
            suggestions.push({
                category: "Statistics & Data Points",
                current: '(No specific numbers or statistics detected on page)',
                items: statSugs,
                why: "AI systems like ChatGPT and Perplexity strongly prefer citing pages with specific data. Content with concrete numbers is viewed as more credible by both humans and AI. Replace vague claims like 'significantly reduces risk' with specific percentages or quantities."
            });
        }

        // --- 10. Section headlines derived from existing H2s ---
        if (existingClaims.length > 0) {
            const improvedH2s = existingClaims.slice(0, 3).map(h2 => {
                // Make H2s more benefit-driven
                return `${h2.replace(/^(our|the)\s+/i, '')} — Built for Enterprise Security Teams`;
            });
            improvedH2s.push('Trusted by Security Teams at [Fortune 500 Companies]');
            suggestions.push({
                category: "Section Headlines (H2 improvements)",
                current: `Current H2s found: ${existingClaims.slice(0, 3).join(' / ')}`,
                items: improvedH2s,
                why: "Section headlines (H2s) are used by AI to understand page structure and are often extracted as standalone content. Benefit-driven H2s perform better in AI summaries than feature-focused ones. Each H2 should make sense on its own."
            });
        }

        // Render
        container.innerHTML = suggestions.map(s => `
            <div style="background: white; border: 1px solid var(--grey-light); border-radius: 8px; padding: 20px; margin-bottom: 15px;">
                <h4 style="color: var(--olive-green-dark); margin-bottom: 10px;">${s.category}</h4>
                <div style="background: #f9f9f9; padding: 10px; border-radius: 4px; margin-bottom: 12px; font-size: 0.85rem;">
                    <strong>Current:</strong> <span style="color: #666;">${s.current}</span>
                </div>
                <p style="font-size: 0.82rem; color: #888; margin-bottom: 10px; border-left: 3px solid var(--grey-light); padding-left: 8px;"><em>Why this matters:</em> ${s.why}</p>
                <div style="margin-top: 10px;">
                    <strong style="font-size: 0.82rem; color: #555;">Suggested copy (click to copy):</strong>
                    ${s.items.map(item => `
                        <div class="copy-item"
                             onclick="navigator.clipboard.writeText(this.dataset.text); this.style.background='#e8f5e9'; setTimeout(() => this.style.background='#f5f5f5', 1200);"
                             data-text="${item.replace(/"/g, '&quot;')}"
                             style="background: #f5f5f5; padding: 12px; margin-top: 8px; border-radius: 4px; cursor: pointer; font-size: 0.875rem; border-left: 3px solid var(--persimmon); white-space: pre-wrap;">
                            ${item}
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    }

    extractCompanyName(title) {
        if (!title) return 'Your Company';
        // Try to extract company name from title
        const parts = title.split(/[|\-–—]/);
        return parts[0]?.trim() || 'Your Company';
    }

    async exportReport() {
        if (!this.currentResults) {
            alert('No results to export');
            return;
        }

        const btn = document.getElementById('export-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Generating...';
        btn.disabled = true;

        try {
            const response = await fetch('/api/export-docx', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(this.currentResults)
            });

            if (!response.ok) {
                throw new Error('Failed to generate document');
            }

            // Get the blob from response
            const blob = await response.blob();

            // Create download link
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `website-optimization-report-${new Date().toISOString().split('T')[0]}.docx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            btn.textContent = 'Downloaded!';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.disabled = false;
            }, 2000);

        } catch (error) {
            console.error('Export error:', error);
            alert('Error generating report. Please try again.');
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

    // Legacy text export - kept for reference
    _exportReportText() {
        const results = this.currentResults;
        const analysis = results.your_site_analysis || {};
        const seo = analysis.seo_factors || {};
        const date = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

        // Build report content
        let report = `WEBSITE OPTIMIZATION REPORT
Generated: ${date}
URL Analyzed: ${analysis.url || 'N/A'}

${'='.repeat(60)}

EXECUTIVE SUMMARY
${'='.repeat(60)}

This report analyzes your website for SEO, GEO (Generative Engine Optimization),
and LLM discoverability factors. Below are prioritized recommendations to improve
your visibility in both traditional search and AI-powered search engines.

${'='.repeat(60)}

TOP PRIORITY ACTIONS
${'='.repeat(60)}

`;

        // Add priority actions
        (results.priority_actions || []).forEach((action, i) => {
            report += `
${i + 1}. ${action.title}
   Category: ${action.category} | Impact: ${action.impact} | Effort: ${action.effort}

   ${action.description || ''}

   Action Steps:
${(action.all_actions || [action.first_step]).filter(Boolean).map(a => `   • ${a}`).join('\n')}

`;
        });

        report += `
${'='.repeat(60)}

SITE ANALYSIS METRICS
${'='.repeat(60)}

SEO Factors:
• Title: ${seo.title || 'Missing'}
• Title Length: ${seo.title_length || 0} characters (optimal: 50-60)
• Meta Description: ${seo.meta_description ? 'Present' : 'Missing'}
• Meta Description Length: ${seo.meta_description_length || 0} characters (optimal: 150-160)
• H1 Tags: ${seo.h1_tags?.length || 0} (optimal: 1)
• Word Count: ${seo.word_count || 0}
• Images Missing Alt Text: ${seo.images_without_alt || 0}

Technical Factors:
• HTTPS: ${analysis.technical_factors?.https ? 'Yes' : 'No'}
• Sitemap: ${analysis.technical_factors?.has_sitemap ? 'Yes' : 'No'}
• Robots.txt: ${analysis.technical_factors?.has_robots_txt ? 'Yes' : 'No'}

LLM Discoverability:
• Structured Content: ${analysis.llm_discoverability?.structured_content ? 'Yes' : 'No'}
• FAQ Schema: ${analysis.llm_discoverability?.faq_schema ? 'Yes' : 'No'}

GEO (AI Citation) Factors:
• Statistics Present: ${analysis.geo_factors?.statistics_present ? 'Yes' : 'No'}
• Citation Ready: ${analysis.geo_factors?.citation_ready ? 'Yes' : 'No'}
• Lists/Bullets: ${analysis.geo_factors?.lists_and_bullets || 0}

${'='.repeat(60)}

ALL RECOMMENDATIONS
${'='.repeat(60)}

`;

        // Add all recommendations
        (results.recommendations || []).forEach((rec, i) => {
            report += `
${i + 1}. [${rec.category}] ${rec.title}
   Impact: ${rec.impact} | Effort: ${rec.effort}

   ${rec.description}

   Action Steps:
${(rec.specific_actions || []).map(a => `   • ${a}`).join('\n')}

   Expected Outcome: ${rec.expected_outcome || 'Improved performance'}

`;
        });

        report += `
${'='.repeat(60)}

ISSUES FOUND
${'='.repeat(60)}

`;
        (analysis.issues || []).forEach(issue => {
            report += `• [${issue.severity?.toUpperCase()}] ${issue.issue} (${issue.category})\n`;
        });

        report += `

${'='.repeat(60)}

STRENGTHS
${'='.repeat(60)}

`;
        (analysis.strengths || []).forEach(strength => {
            report += `• ${strength.strength} (${strength.category})\n`;
        });

        report += `

${'='.repeat(60)}
Report generated by Website Competitor Scanner
${'='.repeat(60)}
`;

        // Download as text file
        const blob = new Blob([report], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `website-optimization-report-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    switchTab(tabId) {
        // Update tab buttons
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabId);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `tab-${tabId}`);
        });
    }

    filterRecommendations(category) {
        // Update filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === category);
        });

        // Filter recommendations
        document.querySelectorAll('.recommendation').forEach(rec => {
            if (category === 'all' || rec.dataset.category === category) {
                rec.style.display = 'block';
            } else {
                rec.style.display = 'none';
            }
        });
    }

    resetForm() {
        this.form.reset();
        this.uploadedFiles = [];
        this.fileList.innerHTML = '';
        this.inputSection.style.display = 'block';
        this.resultsSection.style.display = 'none';
        this.resultsSection.classList.remove('active');

        // Reset progress
        document.querySelectorAll('.progress-step').forEach(step => {
            step.classList.remove('active', 'completed');
        });

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    new WebsiteScanner();
});
