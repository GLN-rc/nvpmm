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
        const explanations = this.metricExplanations || {};

        // Helper to get explanation
        const getExp = (key) => explanations[key] || {};

        // Render metric insights first if available
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
        metricsContainer.innerHTML = insightsHtml + `
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
                <h4>LLM Discoverability</h4>
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
            </div>

            <div class="analysis-card">
                <h4>GEO (AI Citation) Factors</h4>
                <div class="metric">
                    <span class="metric-label">Citation Ready</span>
                    <span class="metric-value ${geo.citation_ready ? 'good' : 'warning'}">${geo.citation_ready ? 'Yes' : 'No'}</span>
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

        container.innerHTML = `
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
                    <thead>
                        <tr style="background: var(--grey-lightest);">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid var(--grey-light);">Metric</th>
                            <th style="padding: 12px; text-align: center; border-bottom: 2px solid var(--grey-light); background: var(--olive-green); color: white;">Your Site</th>
                            ${competitors.map(c => `
                                <th style="padding: 12px; text-align: center; border-bottom: 2px solid var(--grey-light);">${c.domain || c.url}</th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">Word Count</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); font-weight: 600;">${yourSeo.word_count || 'N/A'}</td>
                            ${competitors.map(c => `
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light);">${c.seo_factors?.word_count || 'N/A'}</td>
                            `).join('')}
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">Has Structured Data</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); font-weight: 600;">${yourSite?.content_analysis?.has_structured_data ? '✓' : '✗'}</td>
                            ${competitors.map(c => `
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light);">${c.content_analysis?.has_structured_data ? '✓' : '✗'}</td>
                            `).join('')}
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">FAQ Schema</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); font-weight: 600;">${yourSite?.llm_discoverability?.faq_schema ? '✓' : '✗'}</td>
                            ${competitors.map(c => `
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light);">${c.llm_discoverability?.faq_schema ? '✓' : '✗'}</td>
                            `).join('')}
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">Statistics Present</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); font-weight: 600;">${yourSite?.geo_factors?.statistics_present ? '✓' : '✗'}</td>
                            ${competitors.map(c => `
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light);">${c.geo_factors?.statistics_present ? '✓' : '✗'}</td>
                            `).join('')}
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">Citation Ready</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); font-weight: 600;">${yourSite?.geo_factors?.citation_ready ? '✓' : '✗'}</td>
                            ${competitors.map(c => `
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light);">${c.geo_factors?.citation_ready ? '✓' : '✗'}</td>
                            `).join('')}
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid var(--grey-light);">Issues Found</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light); font-weight: 600;">${yourSite?.issues?.length || 0}</td>
                            ${competitors.map(c => `
                                <td style="padding: 12px; text-align: center; border-bottom: 1px solid var(--grey-light);">${c.issues?.length || 0}</td>
                            `).join('')}
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
    }

    renderCopySuggestions(analysis, recommendations) {
        const container = document.getElementById('copy-suggestions-list');
        if (!container) return;

        const seo = analysis?.seo_factors || {};
        const currentTitle = seo.title || '';
        const currentH1 = seo.h1_tags?.[0] || '';

        // Generate specific copy suggestions
        const suggestions = [];

        // Title suggestions
        suggestions.push({
            category: "Page Title",
            current: currentTitle || "(No title found)",
            suggestions: [
                `${this.extractCompanyName(currentTitle)} | Secure Isolated Browsing for Enterprise`,
                `Enterprise Browser Isolation | Protect Against Web Threats | ${this.extractCompanyName(currentTitle)}`,
                `Zero-Trust Web Security | ${this.extractCompanyName(currentTitle)} - Isolated Browsing Solution`
            ],
            why: "Titles should be 50-60 chars, include primary keyword near start, and communicate value."
        });

        // Headline/H1 suggestions
        suggestions.push({
            category: "Main Headline (H1)",
            current: currentH1 || "(No H1 found)",
            suggestions: [
                "Protect Your Enterprise from Web-Based Threats with Isolated Browsing",
                "Browse Securely. Work Confidently. Zero Trust Made Simple.",
                "The Only Browser Isolation Platform Built for [Your Specific Differentiator]"
            ],
            why: "Your headline should pass the 5-second test: Can visitors immediately understand what you do and why it matters?"
        });

        // Meta description suggestions
        suggestions.push({
            category: "Meta Description",
            current: seo.meta_description || "(No meta description found)",
            suggestions: [
                "Replica Cyber provides enterprise browser isolation that protects your team from web threats without slowing them down. See a demo in 2 minutes.",
                "Stop web-based attacks before they reach your network. Replica Cyber's isolated browsing keeps threats contained. Request a free security assessment.",
                "Join 500+ enterprises using Replica Cyber for zero-trust web security. 99.9% threat prevention rate. Book your demo today."
            ],
            why: "Meta descriptions are your ad copy in search results. Include a CTA and specific benefit."
        });

        // CTA suggestions
        suggestions.push({
            category: "Call-to-Action Buttons",
            current: "(Review your current CTAs)",
            suggestions: [
                "See How It Works (2-min demo)",
                "Get Your Free Security Assessment",
                "Start Protecting Your Team Today",
                "Calculate Your Risk Exposure →"
            ],
            why: "Specific CTAs outperform generic ones like 'Learn More' or 'Get Started'."
        });

        // Value prop suggestions
        suggestions.push({
            category: "Value Proposition Statement",
            current: "(Add to your hero section)",
            suggestions: [
                "Web threats stopped at the source. Your productivity stays intact.",
                "100% of web threats isolated. 0% impact on your team's workflow.",
                "Enterprise security teams choose Replica Cyber because [specific differentiator]."
            ],
            why: "Lead with the outcome your customers want, not your product features."
        });

        // Social proof suggestions
        suggestions.push({
            category: "Social Proof / Trust Signals",
            current: "(Add these elements to your page)",
            suggestions: [
                "Trusted by 500+ enterprise security teams worldwide",
                '"Replica Cyber reduced our web-based incidents by 94%" - [Customer Name], CISO at [Company]',
                "SOC 2 Type II Certified | FedRAMP Authorized | ISO 27001 Compliant",
                "Featured in Gartner's Market Guide for Browser Isolation"
            ],
            why: "Social proof builds credibility with humans AND signals authority to AI systems."
        });

        // Render suggestions
        container.innerHTML = suggestions.map(s => `
            <div style="background: white; border: 1px solid var(--grey-light); border-radius: 8px; padding: 20px; margin-bottom: 15px;">
                <h4 style="color: var(--olive-green-dark); margin-bottom: 10px;">${s.category}</h4>
                <div style="background: #f9f9f9; padding: 10px; border-radius: 4px; margin-bottom: 15px; font-size: 0.85rem;">
                    <strong>Current:</strong> <span style="color: #666;">${s.current}</span>
                </div>
                <p style="font-size: 0.85rem; color: #888; margin-bottom: 10px;"><em>Why this matters:</em> ${s.why}</p>
                <div style="margin-top: 10px;">
                    <strong style="font-size: 0.85rem;">Suggested copy (click to copy):</strong>
                    ${s.suggestions.map(suggestion => `
                        <div class="copy-item" onclick="navigator.clipboard.writeText(this.innerText.trim()); this.style.background='#e8f5e9'; setTimeout(() => this.style.background='#f5f5f5', 1000);"
                             style="background: #f5f5f5; padding: 12px; margin-top: 8px; border-radius: 4px; cursor: pointer; font-size: 0.9rem; border-left: 3px solid var(--persimmon);">
                            ${suggestion}
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

    exportReport() {
        if (!this.currentResults) {
            alert('No results to export');
            return;
        }

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
