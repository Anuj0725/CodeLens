document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        // Sidebar State
        ingestUrl: '',
        repoFilter: '',
        isIngesting: false,
        ingestMessage: '',
        ingestSuccess: false,
        repositories: [],

        // Chat State
        currentQuery: '',
        isAsking: false,
        messages: [],

        init() {
            // Configure marked.js options if needed
            const renderer = new marked.Renderer();
            renderer.code = function(code, language) {
                const escapedCode = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                return `<div class="relative group my-4 rounded-xl overflow-hidden border border-tp-border bg-[#0d1117]">
                            <div class="flex items-center justify-between px-4 py-2 bg-tp-panel2 border-b border-tp-border text-xs text-tp-muted font-mono">
                                <span>${language || 'code'}</span>
                                <button onclick="navigator.clipboard.writeText(decodeURIComponent('${encodeURIComponent(code)}')); this.innerHTML='<svg class=\'w-3.5 h-3.5\' fill=\'none\' stroke=\'currentColor\' viewBox=\'0 0 24 24\'><path stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'2\' d=\'M5 13l4 4L19 7\'></path></svg>Copied!'; setTimeout(() => this.innerHTML='<svg class=\'w-3.5 h-3.5\' fill=\'none\' stroke=\'currentColor\' viewBox=\'0 0 24 24\'><path stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'2\' d=\'M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z\'></path></svg>Copy', 2000)" class="flex items-center gap-1.5 hover:text-tp-text transition-colors">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                                    Copy
                                </button>
                            </div>
                            <div class="p-4 overflow-x-auto text-sm text-tp-text font-mono leading-relaxed">
                                <pre><code>${escapedCode}</code></pre>
                            </div>
                        </div>`;
            };
            marked.setOptions({
                renderer: renderer,
                breaks: true,
                gfm: true
            });
            this.fetchRepositories();
        },

        
        async deleteRepo(repo) {
            try {
                const response = await fetch(`http://localhost:8000/repositories/${encodeURIComponent(repo)}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    if (this.repoFilter === repo) this.repoFilter = '';
                    this.fetchRepositories();
                } else {
                    console.error("Failed to delete repository");
                }
            } catch (error) {
                console.error("Network error while deleting repository", error);
            }
        },

        async fetchRepositories() {
            try {
                const response = await fetch('http://localhost:8000/repositories');
                const data = await response.json();
                if (response.ok && data.repositories) {
                    this.repositories = data.repositories;
                }
            } catch (error) {
                console.error("Could not fetch repositories", error);
            }
        },

        async ingestRepo() {
            if (!this.ingestUrl) return;
            
            this.isIngesting = true;
            this.ingestMessage = '';
            
            try {
                let sType = this.ingestUrl.startsWith('https://github.com/') ? 'github' : 'web';
                
                const response = await fetch('http://localhost:8000/ingest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_type: sType,
                        url: this.ingestUrl
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    this.ingestSuccess = true;
                    // Auto-set the repo filter if not set
                    if (!this.repoFilter) {
                        try {
                            const urlObj = new URL(this.ingestUrl);
                            const pathParts = urlObj.pathname.split('/').filter(p => p);
                            if (pathParts.length >= 2) {
                                this.repoFilter = `${pathParts[0]}/${pathParts[1]}`;
                            }
                        } catch (e) { }
                    }
                    this.ingestMessage = data.message || `Success! Added ${data.chunks_added}, Skipped ${data.chunks_skipped}`;
                    this.ingestUrl = ''; // Clear input on success
                    this.fetchRepositories(); // Refresh the list!
                } else {
                    this.ingestSuccess = false;
                    this.ingestMessage = data.detail || 'Ingestion failed.';
                }
            } catch (error) {
                this.ingestSuccess = false;
                this.ingestMessage = 'Network error. Is the server running?';
                console.error(error);
            } finally {
                this.isIngesting = false;
                // Clear message after 5 seconds
                setTimeout(() => { this.ingestMessage = ''; }, 5000);
            }
        },

        async askQuestion() {
            if (!this.currentQuery.trim() || this.isAsking) return;
            
            const query = this.currentQuery.trim();
            this.currentQuery = ''; // clear input immediately
            
            // Add user message
            this.messages.push({
                role: 'user',
                content: query
            });
            
            this.scrollToBottom();
            this.isAsking = true;
            
            try {
                const response = await fetch('http://localhost:8000/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        repo_filter: this.repoFilter || undefined
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    this.messages.push({
                        role: 'assistant',
                        rawContent: data.answer,
                        content: (() => {
                            let parsed = marked.parse(data.answer);
                            let seen = new Set();
                            return parsed.replace(/\[Source: (.*?)\]/g, (match, src) => {
                                if (seen.has(src)) return '';
                                seen.add(src);
                                const filename = src.includes('—') ? src.split('—').pop().trim() : src;
                                return `<span class="inline-block bg-tp-bordersoft text-tp-muted px-2 py-0.5 rounded-full text-[10px] border border-tp-border mx-1 align-baseline leading-none shadow-sm">${filename}</span>`;
                            });
                        })(),
                        sources: data.sources,
                        latency: data.latency_ms,
                        cache_hit: data.cache_hit
                    });
                } else {
                    this.messages.push({
                        role: 'assistant',
                        content: marked.parse(`**Error:** ${data.detail || 'Something went wrong.'}`),
                        sources: []
                    });
                }
            } catch (error) {
                this.messages.push({
                    role: 'assistant',
                    content: marked.parse('**Network Error:** Could not connect to the CodeLens API. Make sure the server is running on `http://localhost:8000`.'),
                    sources: []
                });
                console.error(error);
            } finally {
                this.isAsking = false;
                // Removed scrollToBottom so the user doesn't lose their place when a long response finishes
            }
        },
        
        scrollToBottom() {
            setTimeout(() => {
                const anchor = document.getElementById('scroll-anchor');
                if (anchor) {
                    anchor.scrollIntoView({ behavior: 'smooth' });
                }
            }, 100);
        }
    }));
});
