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

        // Render priority actions
        this.renderPriorityActions(results.priority_actions);

        // Render all recommendations
        this.renderRecommendations(results.recommendations);

        // Render site analysis
        this.renderSiteAnalysis(results.your_site_analysis);

        // Render competitor comparison
        this.renderCompetitorComparison(results.your_site_analysis, results.competitor_analyses);

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
                    ${action.first_step ? `<p style="margin-top: 8px;"><strong>First step:</strong> ${action.first_step}</p>` : ''}
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

    renderSiteAnalysis(analysis) {
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

        // Metrics cards
        metricsContainer.innerHTML = `
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
