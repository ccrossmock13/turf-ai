        let chatHistory = [];
        let currentFeedback = { rating: null, question: null, answer: null, sources: [], confidence: null };
        let activeConversationId = null;

        // Dark mode — init from localStorage or OS preference
        (function initTheme() {
            const saved = localStorage.getItem('darkMode');
            if (saved === 'true' || (saved === null && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                document.body.classList.add('dark-mode');
            }
            // Update toggle icon
            requestAnimationFrame(() => {
                const btn = document.getElementById('theme-toggle-btn');
                if (btn) btn.textContent = document.body.classList.contains('dark-mode') ? '☀️' : '🌙';
            });
        })();

        function toggleDarkMode() {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('darkMode', isDark);
            const btn = document.getElementById('theme-toggle-btn');
            if (btn) btn.textContent = isDark ? '☀️' : '🌙';
        }

        // Conversation sidebar
        function toggleConvSidebar() {
            const sidebar = document.getElementById('conv-sidebar');
            sidebar.classList.toggle('collapsed');
            if (!sidebar.classList.contains('collapsed')) {
                loadConversationList();
            }
        }

        async function loadConversationList() {
            try {
                const res = await fetch('/api/conversations');
                if (!res.ok) return;
                const convos = await res.json();
                const list = document.getElementById('conv-sidebar-list');
                list.innerHTML = convos.slice(0, 20).map(c => {
                    const title = c.first_question ? c.first_question.substring(0, 60) : 'New conversation';
                    const date = c.last_active ? new Date(c.last_active).toLocaleDateString() : '';
                    const active = c.id === activeConversationId ? ' active' : '';
                    return `<div class="conv-item${active}" role="listitem" tabindex="0" onclick="loadConversation(${c.id})" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();loadConversation(${c.id})}" aria-label="${escapeHtml(title)}">
                        <div class="conv-item-title">${escapeHtml(title)}</div>
                        <div class="conv-item-meta">${date} · ${c.message_count || 0} msgs</div>
                    </div>`;
                }).join('');
                if (convos.length === 0) {
                    list.innerHTML = '<div style="padding:16px;color:var(--color-text-muted);font-size:13px;">No conversations yet</div>';
                }
            } catch(e) { /* silent */ }
        }

        async function loadConversation(conversationId) {
            try {
                const res = await fetch(`/api/conversations/${conversationId}/messages`);
                if (!res.ok) return;
                const messages = await res.json();
                activeConversationId = conversationId;
                const container = document.getElementById('chat-container');
                container.innerHTML = '';
                chatHistory = [];
                messages.forEach(msg => {
                    if (msg.role === 'user') {
                        container.innerHTML += `
                            <div class="message user">
                                <div class="message-content">
                                    <div class="message-bubble">${escapeHtml(msg.content)}</div>
                                </div>
                            </div>`;
                    } else if (msg.role === 'assistant') {
                        container.innerHTML += `
                            <div class="message assistant">
                                <div class="message-avatar">AI</div>
                                <div class="message-content">
                                    <div class="message-bubble">${renderMarkdown(msg.content)}</div>
                                </div>
                            </div>`;
                    }
                    chatHistory.push({ role: msg.role, content: msg.content });
                });
                container.scrollTop = container.scrollHeight;
                loadConversationList(); // refresh active state
            } catch(e) { /* silent */ }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function getSourceBadge(source) {
            const url = (source.url || '').toLowerCase();
            const note = (source.note || '').toLowerCase();
            if (note.startsWith('web search')) return '<span class="source-type-badge stb-web">Web</span>';
            if (url.includes('product-label') || url.includes('epa_label')) return '<span class="source-type-badge stb-label">Label</span>';
            if (url.includes('sds') || url.includes('safety')) return '<span class="source-type-badge stb-sds">SDS</span>';
            if (url.includes('spray-program')) return '<span class="source-type-badge stb-program">Program</span>';
            if (url.includes('ntep') || url.includes('research') || url.includes('solution-sheet')) return '<span class="source-type-badge stb-research">Research</span>';
            return '<span class="source-type-badge stb-label">Ref</span>';
        }

        // Mobile menu functions
        function openMobileMenu() {
            const nav = document.getElementById('mobile-nav');
            nav.classList.add('visible');
            document.body.style.overflow = 'hidden';
        }

        function closeMobileMenu(event) {
            if (event && event.target !== event.currentTarget) return;
            const nav = document.getElementById('mobile-nav');
            nav.classList.remove('visible');
            document.body.style.overflow = '';
        }

        // Handle back button on mobile
        window.addEventListener('popstate', function() {
            closeMobileMenu();
        });

        function renderMarkdown(text) {
            // Use marked.js for full markdown support (tables, code blocks, nested lists, etc.)
            // Falls back to basic escaping if marked isn't loaded
            if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
                marked.setOptions({ breaks: true, gfm: true });
                return DOMPurify.sanitize(marked.parse(text));
            }
            // Fallback: basic escaping + line breaks
            let html = escapeHtml(text);
            html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
            html = html.replace(/\n\n/g, '<br><br>');
            html = html.replace(/\n/g, '<br>');
            return html;
        }

        function openPhotoLightbox(src, caption) {
            const overlay = document.createElement('div');
            overlay.className = 'photo-lightbox';
            overlay.onclick = () => overlay.remove();
            overlay.innerHTML = `<img src="${src}" alt="${escapeHtml(caption)}" />`;
            document.body.appendChild(overlay);
        }

        function handlePhotoUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            if (file.size > 5 * 1024 * 1024) {
                alert('Photo must be under 5MB. Please try a smaller image.');
                event.target.value = '';
                return;
            }

            if (!file.type.startsWith('image/')) {
                alert('Please select an image file.');
                event.target.value = '';
                return;
            }

            const optionalText = document.getElementById('question-input').value.trim();
            submitPhotoForDiagnosis(file, optionalText);
            event.target.value = '';
        }

        function addUserPhotoMessage(imageDataUrl, optionalText) {
            const welcome = document.getElementById('welcome-state');
            if (welcome) welcome.remove();

            const container = document.getElementById('chat-container');
            const msgId = 'msg-' + Date.now();
            const textHtml = optionalText ? `<div style="margin-top:8px">${escapeHtml(optionalText)}</div>` : '';

            container.innerHTML += `
                <div class="message user" id="${msgId}">
                    <div class="message-avatar">You</div>
                    <div class="message-content">
                        <div class="message-bubble">
                            <img src="${imageDataUrl}" class="user-photo-preview" alt="Uploaded photo" />
                            ${textHtml || '<div style="font-size:13px;opacity:0.8">Photo uploaded for diagnosis</div>'}
                        </div>
                    </div>
                </div>
            `;
            chatHistory.push({ role: 'user', content: '[Photo uploaded]' + (optionalText ? ': ' + optionalText : '') });
            container.scrollTop = container.scrollHeight;
        }

        async function submitPhotoForDiagnosis(file, optionalText) {
            const reader = new FileReader();
            reader.onload = async function(e) {
                const imageDataUrl = e.target.result;
                addUserPhotoMessage(imageDataUrl, optionalText);
                addLoadingMessage();

                document.getElementById('question-input').value = '';
                document.getElementById('send-btn').disabled = true;
                document.getElementById('upload-btn').disabled = true;

                try {
                    const formData = new FormData();
                    formData.append('image', file);
                    if (optionalText) formData.append('question', optionalText);
                    if (userLocation) formData.append('location', JSON.stringify(userLocation));

                    const response = await fetch('/diagnose', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.status === 401) {
                        window.location.href = '/login';
                        return;
                    }
                    if (!response.ok) throw new Error('Server error');

                    const data = await response.json();
                    removeLoadingMessage();
                    addAssistantMessage(data, optionalText || 'Photo diagnosis');

                } catch (error) {
                    removeLoadingMessage();
                    const container = document.getElementById('chat-container');
                    container.innerHTML += `
                        <div class="message assistant">
                            <div class="message-avatar">AI</div>
                            <div class="message-content">
                                <div class="message-bubble" style="border-left-color: #fee2e2;">
                                    Sorry, I couldn't analyze the photo. Please try again or describe the problem in text.
                                </div>
                            </div>
                        </div>
                    `;
                }

                document.getElementById('send-btn').disabled = false;
                document.getElementById('upload-btn').disabled = false;
                document.getElementById('question-input').focus();
            };
            reader.readAsDataURL(file);
        }

        // Load user info and profile indicator on page load
        async function loadUserInfo() {
            try {
                const resp = await fetch('/api/me');
                if (resp.status === 401) return; // Not logged in (demo mode)
                const data = await resp.json();
                if (data.authenticated && data.user) {
                    const nameEl = document.getElementById('user-name-display');
                    if (nameEl) nameEl.textContent = data.user.name;
                    if (data.profile && data.profile.primary_grass) {
                        const parts = [data.profile.primary_grass];
                        if (data.profile.region) parts.push(data.profile.region);
                        if (data.profile.course_name) parts.push(data.profile.course_name);
                        const indicator = document.getElementById('profile-indicator');
                        const summary = document.getElementById('profile-summary');
                        if (indicator && summary) {
                            summary.textContent = parts.join(' \u00B7 ');
                            indicator.style.display = '';
                        }
                    }
                    if (data.user.is_admin) {
                        document.querySelectorAll('.nav-links, .mobile-nav-links').forEach(function(nav) {
                            if (!nav.querySelector('a[href="/admin"]')) {
                                var a = document.createElement('a');
                                a.href = '/admin';
                                a.textContent = 'Admin';
                                a.style.cssText = 'color:#fbbf24;font-weight:600';
                                nav.appendChild(a);
                            }
                        });
                    }
                }
            } catch (e) { /* silent */ }
        }
        loadUserInfo();

        function startNewChat() {
            chatHistory = [];
            document.getElementById('chat-container').innerHTML = `
                <div class="welcome-state" id="welcome-state">
                    <div class="welcome-icon">🌿</div>
                    <h1 class="welcome-title">How can I help?</h1>
                    <p class="welcome-subtitle">Ask about turf diseases, products, cultural practices, or equipment</p>
                    <div class="suggested-questions">
                        <button class="suggested-btn" onclick="askSuggested('What fungicide should I use for dollar spot on bentgrass?')">Dollar spot control on bentgrass</button>
                        <button class="suggested-btn" onclick="askSuggested('What is the difference between prodiamine and dithiopyr?')">Barricade vs Dimension</button>
                        <button class="suggested-btn" onclick="askSuggested('How do I calibrate a boom sprayer?')">Sprayer calibration</button>
                        <button class="suggested-btn" onclick="askSuggested('How to identify and treat brown patch?')">Brown patch ID &amp; treatment</button>
                    </div>
                </div>
            `;
            document.getElementById('question-input').value = '';
            // Clear server-side session
            fetch('/api/new-session', { method: 'POST' }).catch(() => {});
        }

        function askSuggested(question) {
            document.getElementById('question-input').value = question;
            askQuestion();
        }

        function handleKeyPress(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                askQuestion();
            }
        }

        function addUserMessage(question) {
            const welcome = document.getElementById('welcome-state');
            if (welcome) welcome.remove();

            const container = document.getElementById('chat-container');
            const msgId = 'msg-' + Date.now();
            container.innerHTML += `
                <div class="message user" id="${msgId}">
                    <div class="message-avatar">You</div>
                    <div class="message-content">
                        <div class="message-bubble">${escapeHtml(question)}</div>
                    </div>
                </div>
            `;
            chatHistory.push({ role: 'user', content: question });
            return msgId;
        }

        let _loadingStageTimer = null;
        function addLoadingMessage() {
            const container = document.getElementById('chat-container');
            container.innerHTML += `
                <div class="loading-message" id="loading-msg">
                    <div class="message-avatar" style="background: linear-gradient(135deg, #1a4d2e, #2d7a4a); color: white;">AI</div>
                    <div style="display: flex; align-items: center;">
                        <div class="typing-indicator">
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                        </div>
                        <span class="loading-status" id="loading-status">Searching knowledge base...</span>
                    </div>
                </div>
            `;
            container.scrollTop = container.scrollHeight;
            // Progressive stages
            const stages = [
                { text: 'Analyzing sources...', delay: 2500 },
                { text: 'Writing answer...', delay: 5500 },
                { text: 'Verifying accuracy...', delay: 9000 }
            ];
            stages.forEach(stage => {
                const timer = setTimeout(() => {
                    const el = document.getElementById('loading-status');
                    if (el) el.textContent = stage.text;
                }, stage.delay);
                if (!_loadingStageTimer) _loadingStageTimer = [];
                _loadingStageTimer.push(timer);
            });
        }

        function removeLoadingMessage() {
            if (_loadingStageTimer) {
                _loadingStageTimer.forEach(t => clearTimeout(t));
                _loadingStageTimer = null;
            }
            const loading = document.getElementById('loading-msg');
            if (loading) loading.remove();
        }

        function addAssistantMessage(data, question) {
            const container = document.getElementById('chat-container');
            const msgId = 'assistant-' + Date.now();

            const confidence = data.confidence?.score ?? 0;
            let badgeClass = 'confidence-low';
            let badgeText = 'Low Confidence';
            if (confidence >= 75) {
                badgeClass = 'confidence-high';
                badgeText = 'High Confidence';
            } else if (confidence >= 55) {
                badgeClass = 'confidence-good';
                badgeText = 'Good Confidence';
            }

            const formattedAnswer = data.answer
                ? renderMarkdown(data.answer)
                : 'No answer available.';

            const sourcesHtml = (data.sources || []).map(s => {
                const name = escapeHtml(s.name || s.title || 'Source');
                const badge = getSourceBadge(s);
                if (s.url) {
                    return `<a href="${encodeURI(s.url)}" target="_blank" class="source-chip" title="${escapeHtml(s.note || s.url || '')}">${badge}${name}</a>`;
                }
                return `<span class="source-chip" title="${escapeHtml(s.note || '')}">${badge}${name}</span>`;
            }).join('');

            // Weather info
            let weatherHtml = '';
            if (data.weather && data.weather.summary) {
                const warnings = (data.weather.warnings || [])
                    .filter(w => w.severity === 'high')
                    .map(w => `<div class="weather-warning">⚠️ ${escapeHtml(w.message)}</div>`)
                    .join('');
                weatherHtml = `
                    <div class="weather-info">
                        <div class="weather-summary">${escapeHtml(data.weather.summary).replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</div>
                        ${warnings}
                    </div>
                `;
            }

            // Web search indicator
            let webSearchHtml = '';
            if (data.web_search_used) {
                webSearchHtml = `<div class="web-search-notice">🌐 Includes web search results - verify rates with product labels</div>`;
            }

            // Disease reference photos
            let photosHtml = '';
            if (data.images && data.images.length > 0) {
                const photoCards = data.images.map(img => {
                    const caption = img.caption ? escapeHtml(img.caption) : '';
                    const captionAttr = caption.replace(/'/g, '&#39;');
                    return `
                        <div class="disease-photo">
                            <img src="${encodeURI(img.url)}" alt="${caption}"
                                 loading="lazy" onclick="openPhotoLightbox(this.src, '${captionAttr}')"
                                 onerror="this.parentElement.style.display='none'" />
                            ${caption ? `<div class="photo-caption">${caption}</div>` : ''}
                        </div>
                    `;
                }).join('');
                photosHtml = `<div class="disease-photos">${photoCards}</div>`;
            }

            // Recommended products → "Log This Spray" buttons
            let sprayBtnsHtml = '';
            if (data.recommended_products && data.recommended_products.length > 0) {
                const btns = data.recommended_products.map(p =>
                    `<a href="/spray-tracker?product_id=${encodeURIComponent(p.id)}" class="spray-link-btn" title="Log ${escapeHtml(p.name)} in Spray Tracker">🧪 ${escapeHtml(p.name)}</a>`
                ).join('');
                sprayBtnsHtml = `
                    <div class="spray-link-row">
                        <span class="spray-link-label">Quick log:</span>
                        ${btns}
                    </div>
                `;
            }

            container.innerHTML += `
                <div class="message assistant" id="${msgId}">
                    <div class="message-avatar">AI</div>
                    <div class="message-content">
                        <div class="message-bubble">
                            <div class="confidence-badge ${badgeClass}">${badgeText}</div>
                            ${webSearchHtml}
                            ${weatherHtml}
                            <div id="answer-text-${msgId}">${data.cached ? formattedAnswer : ''}</div>
                            ${photosHtml}
                            ${sourcesHtml ? `
                                <div class="sources-list">
                                    <div class="sources-label">Sources</div>
                                    ${sourcesHtml}
                                </div>
                            ` : ''}
                            ${sprayBtnsHtml}
                            <div class="feedback-row" id="feedback-${msgId}">
                                <span class="feedback-label">Helpful?</span>
                                <button class="feedback-btn" onclick="selectFeedback('${msgId}', 'positive')">👍</button>
                                <button class="feedback-btn" onclick="selectFeedback('${msgId}', 'negative')">👎</button>
                                <span class="feedback-thanks" id="thanks-${msgId}">Thanks!</span>
                                <button class="regenerate-btn" onclick="regenerateAnswer('${msgId}')" title="Regenerate answer">↻ Retry</button>
                            </div>
                            <div class="feedback-categories" id="categories-${msgId}">
                                <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="wrong_rate"> Wrong rate</label>
                                <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="wrong_product"> Wrong product</label>
                                <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="missing_info"> Missing info</label>
                                <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="unclear"> Unclear</label>
                                <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="other"> Other</label>
                            </div>
                            <div class="correction-input" id="correction-${msgId}">
                                <textarea placeholder="What was wrong? (optional)" id="correction-text-${msgId}"></textarea>
                                <button class="correction-submit" onclick="submitFeedback('${msgId}')">Send</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            chatHistory.push({ role: 'assistant', content: data.answer, msgId });
            currentFeedback = {
                rating: null,
                question: question,
                answer: data.answer,
                sources: data.sources || [],
                confidence: data.confidence,
                msgId: msgId
            };

            // Streaming text reveal for non-cached answers
            if (!data.cached) {
                streamRevealText('answer-text-' + msgId, formattedAnswer, container);
            } else {
                container.scrollTop = container.scrollHeight;
            }
        }

        function streamRevealText(elementId, html, scrollContainer) {
            const el = document.getElementById(elementId);
            if (!el) return;
            // Parse the HTML to extract text nodes for progressive reveal
            el.innerHTML = html;
            el.style.opacity = '0';
            // Quick fade-in with slight delay to feel like streaming
            requestAnimationFrame(() => {
                el.style.transition = 'opacity 0.4s ease-in';
                el.style.opacity = '1';
                if (scrollContainer) scrollContainer.scrollTop = scrollContainer.scrollHeight;
            });
        }

        // User location for weather integration
        let userLocation = null;

        // Get user location on page load
        function getUserLocation() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        userLocation = {
                            lat: position.coords.latitude,
                            lon: position.coords.longitude
                        };
                        console.log('Location obtained:', userLocation);
                    },
                    (error) => {
                        console.log('Location not available:', error.message);
                    },
                    { timeout: 5000 }
                );
            }
        }
        getUserLocation();

        async function askQuestion() {
            const input = document.getElementById('question-input');
            const question = input.value.trim();
            if (!question) return;

            input.value = '';
            document.getElementById('send-btn').disabled = true;
            addUserMessage(question);

            const requestBody = { question };
            if (userLocation) requestBody.location = userLocation;

            // Try SSE streaming first, fall back to regular /ask
            try {
                await askStreaming(question, requestBody);
            } catch (sseError) {
                console.warn('SSE streaming failed, falling back to /ask:', sseError);
                await askFallback(question, requestBody);
            }

            document.getElementById('send-btn').disabled = false;
            document.getElementById('question-input').focus();
        }

        async function askStreaming(question, requestBody) {
            // Create message bubble for streaming tokens
            const container = document.getElementById('chat-container');
            const msgId = 'msg-' + Date.now();
            container.innerHTML += `
                <div class="message assistant">
                    <div class="message-avatar">AI</div>
                    <div class="message-content">
                        <div class="message-bubble" id="${msgId}-bubble">
                            <div id="${msgId}-text" class="streaming-text"><span class="streaming-cursor">▊</span></div>
                        </div>
                    </div>
                </div>
            `;
            container.scrollTop = container.scrollHeight;

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000);

            const response = await fetch('/ask-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (response.status === 401) { window.location.href = '/login'; return; }
            if (!response.ok) throw new Error('SSE response not ok');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';
            let metadata = null;
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const evt = JSON.parse(line.slice(6));
                        if (evt.error) throw new Error(evt.error);
                        if (evt.token) {
                            fullText += evt.token;
                            const textEl = document.getElementById(msgId + '-text');
                            if (textEl) {
                                textEl.innerHTML = renderMarkdown(fullText) + '<span class="streaming-cursor">▊</span>';
                                container.scrollTop = container.scrollHeight;
                            }
                        }
                        if (evt.done) {
                            metadata = evt;
                        }
                    } catch (parseErr) {
                        if (parseErr.message !== 'Rate limited' && parseErr.message !== 'Query blocked') {
                            console.warn('SSE parse error:', parseErr);
                        } else { throw parseErr; }
                    }
                }
            }

            // Remove streaming cursor
            const textEl = document.getElementById(msgId + '-text');
            if (textEl) textEl.innerHTML = renderMarkdown(fullText);

            // Add sources and confidence below the answer
            if (metadata) {
                const bubble = document.getElementById(msgId + '-bubble');
                if (bubble && metadata.sources && metadata.sources.length > 0) {
                    let sourcesHtml = '<div class="sources-section"><span class="sources-label">Sources:</span>';
                    metadata.sources.forEach(s => {
                        const name = typeof s === 'string' ? s : (s.source || s.name || 'Source');
                        const badge = getSourceBadge(typeof s === 'object' ? s : {name: s});
                        sourcesHtml += `<span class="source-chip">${badge}${escapeHtml(name.split('/').pop())}</span>`;
                    });
                    sourcesHtml += '</div>';
                    bubble.innerHTML += sourcesHtml;
                }
                if (bubble && metadata.confidence) {
                    bubble.insertAdjacentHTML('afterbegin', `<div class="confidence-badge confidence-${metadata.confidence.label?.toLowerCase()?.replace(/\s+/g,'-') || 'moderate'}">${metadata.confidence.label} (${metadata.confidence.score}%)</div>`);
                }
                // Add full feedback block (matching fallback path)
                if (bubble) {
                    bubble.innerHTML += `
                        <div class="feedback-row" id="feedback-${msgId}">
                            <span class="feedback-label">Helpful?</span>
                            <button class="feedback-btn" onclick="selectFeedback('${msgId}','positive')">👍</button>
                            <button class="feedback-btn" onclick="selectFeedback('${msgId}','negative')">👎</button>
                            <span class="feedback-thanks" id="thanks-${msgId}">Thanks!</span>
                            <button class="regenerate-btn" onclick="regenerateAnswer('${msgId}')" title="Regenerate answer">↻ Retry</button>
                        </div>
                        <div class="feedback-categories" id="categories-${msgId}">
                            <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="wrong_rate"> Wrong rate</label>
                            <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="wrong_product"> Wrong product</label>
                            <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="missing_info"> Missing info</label>
                            <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="unclear"> Unclear</label>
                            <label class="feedback-category" onclick="toggleCategory(this)"><input type="checkbox" value="other"> Other</label>
                        </div>
                        <div class="correction-input" id="correction-${msgId}">
                            <textarea placeholder="What was wrong? (optional)" id="correction-text-${msgId}"></textarea>
                            <button class="correction-submit" onclick="submitFeedback('${msgId}')">Send</button>
                        </div>
                    `;
                }
                // Set currentFeedback state so selectFeedback/submitFeedback work
                currentFeedback = {
                    rating: null, question: question, answer: fullText,
                    sources: metadata.sources || [], confidence: metadata.confidence,
                    msgId: msgId
                };
                if (!window._feedbackQuestions) window._feedbackQuestions = {};
                window._feedbackQuestions[msgId] = question;
            }
        }

        async function askFallback(question, requestBody) {
            addLoadingMessage();
            try {
                let data = null;
                let lastError = null;
                for (let attempt = 0; attempt < 2; attempt++) {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 45000);
                    try {
                        if (attempt === 1) {
                            const loadingEl = document.querySelector('.loading-message .loading-status');
                            if (loadingEl) loadingEl.textContent = 'Still thinking... retrying';
                        }
                        const response = await fetch('/ask', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(requestBody),
                            signal: controller.signal
                        });
                        clearTimeout(timeoutId);
                        if (response.status === 401) { window.location.href = '/login'; return; }
                        if (!response.ok) throw new Error('Server error');
                        data = await response.json();
                        break;
                    } catch (err) {
                        clearTimeout(timeoutId);
                        lastError = err;
                        if (attempt === 0 && (err.name === 'AbortError' || err.message === 'Failed to fetch')) continue;
                        throw err;
                    }
                }
                if (!data) throw lastError || new Error('Request failed');
                removeLoadingMessage();
                addAssistantMessage(data, question);
            } catch (error) {
                removeLoadingMessage();
                const container = document.getElementById('chat-container');
                const errorMsg = error.name === 'AbortError'
                    ? 'The request timed out. Please try again.'
                    : 'Sorry, something went wrong. Please try again.';
                container.innerHTML += `
                    <div class="message assistant">
                        <div class="message-avatar">AI</div>
                        <div class="message-content">
                            <div class="message-bubble" style="border-color: #fee2e2;">${errorMsg}</div>
                        </div>
                    </div>
                `;
            }
        }

        function selectFeedback(msgId, rating) {
            currentFeedback.rating = rating;
            currentFeedback.msgId = msgId;

            const feedbackRow = document.getElementById('feedback-' + msgId);
            const btns = feedbackRow.querySelectorAll('.feedback-btn');
            btns.forEach(btn => btn.classList.remove('selected-positive', 'selected-negative'));

            if (rating === 'positive') {
                btns[0].classList.add('selected-positive');
                submitFeedback(msgId);
            } else {
                btns[1].classList.add('selected-negative');
                document.getElementById('categories-' + msgId).classList.add('visible');
                document.getElementById('correction-' + msgId).classList.add('visible');
            }
        }

        function toggleCategory(label) {
            label.classList.toggle('selected');
            const cb = label.querySelector('input[type="checkbox"]');
            cb.checked = !cb.checked;
        }

        function getSelectedCategories(msgId) {
            const container = document.getElementById('categories-' + msgId);
            if (!container) return [];
            const checked = container.querySelectorAll('input[type="checkbox"]:checked');
            return Array.from(checked).map(cb => cb.value);
        }

        async function regenerateAnswer(msgId) {
            const question = currentFeedback.question;
            if (!question) return;
            // Remove the current assistant message
            const msgEl = document.getElementById(msgId);
            if (msgEl) msgEl.remove();
            addLoadingMessage();
            try {
                const requestBody = { question, regenerate: true };
                if (userLocation) requestBody.location = userLocation;
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });
                if (!response.ok) throw new Error('Server error');
                const data = await response.json();
                removeLoadingMessage();
                addAssistantMessage(data, question);
            } catch (error) {
                removeLoadingMessage();
                const container = document.getElementById('chat-container');
                container.innerHTML += `
                    <div class="message assistant">
                        <div class="message-avatar">AI</div>
                        <div class="message-content">
                            <div class="message-bubble" style="border-color: #fee2e2;">
                                Sorry, regeneration failed. Please try again.
                            </div>
                        </div>
                    </div>
                `;
            }
        }

        async function submitFeedback(msgId) {
            const correctionEl = document.getElementById('correction-text-' + msgId);
            const correction = correctionEl ? correctionEl.value : '';
            const categories = getSelectedCategories(msgId);

            try {
                await fetch('/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: currentFeedback.question,
                        answer: currentFeedback.answer,
                        rating: currentFeedback.rating,
                        correction: correction || null,
                        categories: categories.length > 0 ? categories : null,
                        sources: currentFeedback.sources,
                        confidence: currentFeedback.confidence
                    })
                });

                document.getElementById('categories-' + msgId)?.classList.remove('visible');
                document.getElementById('correction-' + msgId)?.classList.remove('visible');
                document.getElementById('thanks-' + msgId).classList.add('visible');

            } catch (error) {
                console.error('Feedback error:', error);
            }
        }
