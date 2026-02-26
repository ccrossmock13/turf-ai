        let currentTab = 'overview';

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        }

        async function loadAllData() {
            await Promise.all([
                loadStats(),
                loadCacheStats(),
                loadRecentQuestions(),
                checkAPIStatus()
            ]);
        }

        async function loadStats() {
            try {
                const [statsRes, cacheRes] = await Promise.all([
                    fetch('/admin/stats'),
                    fetch('/admin/cache')
                ]);

                const stats = await statsRes.json();
                const cache = await cacheRes.json();

                // Update stat cards
                document.getElementById('statQueries').textContent = stats.total_feedback || 0;
                document.getElementById('statToday').textContent = stats.today_count || '-';
                document.getElementById('statPositive').textContent = stats.positive_feedback || 0;
                document.getElementById('statNegative').textContent = stats.negative_feedback || 0;

                const pending = stats.unreviewed_negative || 0;
                const pendingEl = document.getElementById('statPending');
                pendingEl.textContent = pending;
                pendingEl.className = 'stat-number' + (pending > 0 ? ' warning' : '');

                document.getElementById('statAvgConf').textContent = stats.avg_confidence
                    ? Math.round(stats.avg_confidence) + '%'
                    : '-';

                // Cache hit rate
                const embCache = cache.embedding_cache || {};
                const total = (embCache.hits || 0) + (embCache.misses || 0);
                const hitRate = total > 0 ? Math.round((embCache.hits / total) * 100) : 0;
                document.getElementById('statCacheRate').textContent = hitRate + '%';

                // Training progress
                const ready = stats.approved_for_training || 0;
                const needed = 50;
                const percentage = Math.min((ready / needed) * 100, 100);
                document.getElementById('trainingProgress').style.width = percentage + '%';
                document.getElementById('trainingProgress').textContent = Math.round(percentage) + '%';
                document.getElementById('trainingText').textContent =
                    ready >= needed
                        ? `Ready to train! ${ready} approved examples`
                        : `${ready} of ${needed} approved examples needed`;

                // Enable/disable generate button
                const genBtn = document.getElementById('generateTrainingBtn');
                if (genBtn) {
                    genBtn.disabled = ready < needed;
                    genBtn.title = ready < needed ? `Need ${needed - ready} more approved examples` : 'Generate training file';
                }

                // Update topic stats
                updateTopicStats(stats.topic_counts || {});

                // Update confidence distribution
                updateConfidenceDistribution(stats.confidence_distribution || {});

                // Render analytics charts if tab is visible
                if (currentTab === 'analytics') {
                    renderAnalyticsCharts(stats);
                }

            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        function updateTopicStats(topics) {
            const container = document.getElementById('topTopics');
            const sorted = Object.entries(topics).sort((a, b) => b[1] - a[1]).slice(0, 5);
            const max = sorted.length > 0 ? sorted[0][1] : 1;

            if (sorted.length === 0) {
                container.innerHTML = '<div class="empty-state">No data yet</div>';
                return;
            }

            container.innerHTML = sorted.map(([topic, count]) => {
                const width = Math.round((count / max) * 100);
                return `
                    <div class="topic-item">
                        <div class="topic-name">${escapeHtml(topic)}</div>
                        <div class="topic-bar-container">
                            <div class="topic-bar" style="width: ${width}%">${count}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateConfidenceDistribution(dist) {
            const total = (dist.high || 0) + (dist.medium || 0) + (dist.low || 0);
            if (total === 0) return;

            const highPct = Math.round((dist.high || 0) / total * 100);
            const medPct = Math.round((dist.medium || 0) / total * 100);
            const lowPct = Math.round((dist.low || 0) / total * 100);

            document.getElementById('confHigh').style.width = highPct + '%';
            document.getElementById('confHigh').textContent = highPct + '%';
            document.getElementById('confMed').style.width = medPct + '%';
            document.getElementById('confMed').textContent = medPct + '%';
            document.getElementById('confLow').style.width = lowPct + '%';
            document.getElementById('confLow').textContent = lowPct + '%';
        }

        async function loadRecentQuestions() {
            try {
                const response = await fetch('/admin/feedback/all');
                const feedback = await response.json();
                const container = document.getElementById('recentQuestions');

                const recent = feedback.slice(0, 8);
                if (recent.length === 0) {
                    container.innerHTML = '<div class="empty-state">No questions yet</div>';
                    return;
                }

                container.innerHTML = recent.map(item => {
                    const time = item.timestamp
                        ? new Date(item.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
                        : '';
                    const confClass = item.confidence >= 80 ? 'conf-high' : item.confidence >= 60 ? 'conf-medium' : 'conf-low';

                    return `
                        <div class="question-item">
                            <div class="question-time">${time}</div>
                            <div class="question-text">${escapeHtml(item.question)}</div>
                            ${item.rating === 'positive' ? '<span class="conf-high question-confidence">👍</span>' : item.rating === 'negative' ? '<span class="conf-low question-confidence">👎</span>' : ''}
                        </div>
                    `;
                }).join('');
            } catch (error) {
                console.error('Error loading recent questions:', error);
            }
        }

        async function checkAPIStatus() {
            // Weather API
            const weatherStatus = document.getElementById('weatherStatus');
            const weatherText = document.getElementById('weatherStatusText');
            try {
                const res = await fetch('/api/weather?city=Louisville&state=KY');
                if (res.ok) {
                    weatherStatus.className = 'status-indicator status-online';
                    weatherText.textContent = 'Connected';
                } else {
                    weatherStatus.className = 'status-indicator status-warning';
                    weatherText.textContent = 'No API Key';
                }
            } catch {
                weatherStatus.className = 'status-indicator status-offline';
                weatherText.textContent = 'Error';
            }

            // Tavily status (no direct way to test, assume based on env)
            const tavilyStatus = document.getElementById('tavilyStatus');
            const tavilyText = document.getElementById('tavilyStatusText');
            tavilyStatus.className = 'status-indicator status-online';
            tavilyText.textContent = 'Configured';
        }

        async function loadCacheStats() {
            try {
                const response = await fetch('/admin/cache');
                const cache = await response.json();

                const emb = cache.embedding_cache || {};
                document.getElementById('embCacheSize').textContent = emb.size || 0;
                document.getElementById('embCacheHits').textContent = emb.hits || 0;
                document.getElementById('embCacheMisses').textContent = emb.misses || 0;
                document.getElementById('embCacheRate').textContent = emb.hit_rate || '0%';

                const url = cache.source_url_cache || {};
                document.getElementById('urlCacheSize').textContent = url.size || 0;
                document.getElementById('urlCacheHits').textContent = url.hits || 0;
                document.getElementById('urlCacheMisses').textContent = url.misses || 0;
                document.getElementById('urlCacheRate').textContent = url.hit_rate || '0%';
            } catch (error) {
                console.error('Error loading cache stats:', error);
            }
        }

        // Facebook-style moderation state
        let modQueue = [];
        let modIndex = 0;
        let modFilter = 'all';
        let modSessionStats = { approved: 0, rejected: 0, skipped: 0 };
        let modEditMode = false;
        let modSkippedItems = [];

        // Bulk mode state
        let bulkMode = false;
        let selectedItems = new Set();

        const REJECT_REASONS = [
            { id: 'inaccurate', text: 'Inaccurate information', desc: 'Contains factual errors' },
            { id: 'outdated', text: 'Outdated information', desc: 'Recommendations are no longer current' },
            { id: 'incomplete', text: 'Incomplete answer', desc: 'Missing important details' },
            { id: 'off_topic', text: 'Off-topic response', desc: 'Doesn\'t address the question' },
            { id: 'harmful', text: 'Potentially harmful advice', desc: 'Could damage turf or environment' },
            { id: 'other', text: 'Other issue', desc: 'Different problem' }
        ];

        function setModFilter(filter) {
            modFilter = filter;
            document.querySelectorAll('.mod-filter-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.filter === filter);
            });
            loadReviewQueue();
        }

        async function loadReviewQueue() {
            document.getElementById('modLoading').style.display = 'block';
            document.getElementById('modCardContainer').style.display = 'none';
            document.getElementById('bulkListContainer').style.display = 'none';
            document.getElementById('modEmpty').style.display = 'none';

            try {
                // Use priority queue endpoint for priority filter
                const endpoint = modFilter === 'priority'
                    ? '/admin/priority-queue'
                    : `/admin/review-queue?type=${modFilter}`;

                const response = await fetch(endpoint);
                modQueue = await response.json();
                modIndex = 0;
                modSkippedItems = [];
                selectedItems.clear();
                updateBulkSelectedCount();

                document.getElementById('modLoading').style.display = 'none';

                if (modQueue.length === 0) {
                    document.getElementById('modEmpty').style.display = 'block';
                    updateModProgress();
                } else if (bulkMode) {
                    document.getElementById('bulkListContainer').style.display = 'block';
                    renderBulkList();
                } else {
                    document.getElementById('modCardContainer').style.display = 'block';
                    renderCurrentItem();
                }

                // Load trending issues on first load
                loadTrendingIssues();
            } catch (error) {
                console.error('Error loading review queue:', error);
                document.getElementById('modLoading').style.display = 'none';
                document.getElementById('modEmpty').style.display = 'block';
                document.querySelector('.mod-empty-title').textContent = 'Error';
                document.querySelector('.mod-empty-text').textContent = 'Failed to load queue';
            }
        }

        // =====================================================================
        // BULK MODE FUNCTIONS
        // =====================================================================

        function toggleBulkMode() {
            bulkMode = !bulkMode;
            const btn = document.getElementById('bulkModeBtn');
            btn.textContent = bulkMode ? '☑ Bulk Mode' : '☐ Bulk Mode';
            btn.classList.toggle('active', bulkMode);

            document.getElementById('bulkActionsBar').style.display = bulkMode ? 'flex' : 'none';

            if (bulkMode) {
                document.getElementById('modCardContainer').style.display = 'none';
                document.getElementById('bulkListContainer').style.display = 'block';
                renderBulkList();
            } else {
                document.getElementById('bulkListContainer').style.display = 'none';
                if (modQueue.length > 0) {
                    document.getElementById('modCardContainer').style.display = 'block';
                    renderCurrentItem();
                }
                selectedItems.clear();
                updateBulkSelectedCount();
            }
        }

        function renderBulkList() {
            const container = document.getElementById('bulkListContainer');

            container.innerHTML = modQueue.map(item => {
                const isSelected = selectedItems.has(item.id);
                const confClass = item.confidence >= 80 ? 'conf-high' : item.confidence >= 60 ? 'conf-medium' : 'conf-low';

                return `
                    <div class="bulk-item ${isSelected ? 'selected' : ''}" onclick="toggleItemSelection(${item.id})">
                        <input type="checkbox" class="bulk-item-checkbox"
                            ${isSelected ? 'checked' : ''}
                            onclick="event.stopPropagation(); toggleItemSelection(${item.id})">
                        <div class="bulk-item-content">
                            <div class="bulk-item-question">${escapeHtml(item.question)}</div>
                            <div class="bulk-item-answer">${escapeHtml(item.ai_answer?.substring(0, 200) || '')}...</div>
                            <div class="bulk-item-meta">
                                <span class="bulk-item-badge confidence ${confClass}">${item.confidence ? Math.round(item.confidence) + '%' : 'N/A'}</span>
                                ${item.review_type === 'user_flagged' ? '<span class="bulk-item-badge priority">👎 User Flagged</span>' : ''}
                                ${item.is_trending ? '<span class="bulk-item-badge trending">🔥 Trending</span>' : ''}
                                ${item.frequency > 1 ? '<span class="bulk-item-badge">' + item.frequency + 'x asked</span>' : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            updateModProgress();
        }

        function toggleItemSelection(id) {
            if (selectedItems.has(id)) {
                selectedItems.delete(id);
            } else {
                selectedItems.add(id);
            }
            updateBulkSelectedCount();

            // Update visual state
            const items = document.querySelectorAll('.bulk-item');
            items.forEach(item => {
                const checkbox = item.querySelector('.bulk-item-checkbox');
                const itemId = parseInt(checkbox.onclick.toString().match(/toggleItemSelection\((\d+)\)/)?.[1]);
                if (itemId === id) {
                    item.classList.toggle('selected', selectedItems.has(id));
                    checkbox.checked = selectedItems.has(id);
                }
            });
        }

        function selectAllVisible() {
            modQueue.forEach(item => selectedItems.add(item.id));
            updateBulkSelectedCount();
            renderBulkList();
        }

        function clearSelection() {
            selectedItems.clear();
            updateBulkSelectedCount();
            renderBulkList();
        }

        function updateBulkSelectedCount() {
            document.getElementById('bulkSelectedCount').textContent = selectedItems.size;
        }

        async function bulkApprove() {
            if (selectedItems.size === 0) {
                alert('No items selected');
                return;
            }

            if (!confirm(`Approve ${selectedItems.size} items?`)) return;

            try {
                const response = await fetch('/admin/bulk-moderate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ids: Array.from(selectedItems),
                        action: 'approve'
                    })
                });

                const result = await response.json();
                alert(`Approved: ${result.success}, Failed: ${result.failed}`);

                modSessionStats.approved += result.success;
                selectedItems.clear();
                loadReviewQueue();
                loadStats();
            } catch (error) {
                console.error('Bulk approve error:', error);
                alert('Error processing bulk approve');
            }
        }

        async function bulkReject() {
            if (selectedItems.size === 0) {
                alert('No items selected');
                return;
            }

            const reason = prompt('Rejection reason (optional):');
            if (!confirm(`Reject ${selectedItems.size} items?`)) return;

            try {
                const response = await fetch('/admin/bulk-moderate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ids: Array.from(selectedItems),
                        action: 'reject',
                        reason: reason
                    })
                });

                const result = await response.json();
                alert(`Rejected: ${result.success}, Failed: ${result.failed}`);

                modSessionStats.rejected += result.success;
                selectedItems.clear();
                loadReviewQueue();
                loadStats();
            } catch (error) {
                console.error('Bulk reject error:', error);
                alert('Error processing bulk reject');
            }
        }

        async function bulkApproveHighConfidence() {
            const minConf = prompt('Minimum confidence % to auto-approve:', '80');
            if (!minConf) return;

            if (!confirm(`Auto-approve all items with confidence >= ${minConf}%?`)) return;

            try {
                const response = await fetch('/admin/bulk-approve-high-confidence', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        min_confidence: parseInt(minConf),
                        limit: 100
                    })
                });

                const result = await response.json();
                alert(`Auto-approved: ${result.success} items\n${result.message || ''}`);

                modSessionStats.approved += result.success;
                loadReviewQueue();
                loadStats();
            } catch (error) {
                console.error('Auto-approve error:', error);
                alert('Error processing auto-approve');
            }
        }

        // =====================================================================
        // TRENDING ISSUES
        // =====================================================================

        async function loadTrendingIssues() {
            try {
                const response = await fetch('/admin/trending-issues?min_frequency=2&days=7');
                const trending = await response.json();

                const container = document.getElementById('trendingList');
                const alert = document.getElementById('trendingAlert');

                if (trending.length === 0) {
                    alert.style.display = 'none';
                    return;
                }

                container.innerHTML = trending.slice(0, 5).map(item => `
                    <div class="trending-item">
                        <div class="trending-item-text">${escapeHtml(item.question)}</div>
                        <div class="trending-item-stats">
                            <span>${item.frequency}x asked</span>
                            <span>${item.avg_confidence ? item.avg_confidence + '% conf' : 'N/A'}</span>
                            ${item.negative_count > 0 ? '<span>👎 ' + item.negative_count + '</span>' : ''}
                            <span class="trending-item-severity ${item.severity}">${item.severity}</span>
                        </div>
                    </div>
                `).join('');

                alert.style.display = 'block';
            } catch (error) {
                console.error('Error loading trending issues:', error);
            }
        }

        function hideTrendingAlert() {
            document.getElementById('trendingAlert').style.display = 'none';
        }

        // =====================================================================
        // EXPORT FUNCTIONS
        // =====================================================================

        async function exportAnalyticsJson() {
            try {
                const response = await fetch('/admin/export/analytics');
                const data = await response.json();

                // Download as JSON file
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'analytics_export.json';
                a.click();
                URL.revokeObjectURL(url);
            } catch (error) {
                console.error('Export error:', error);
                alert('Error exporting analytics');
            }
        }

        function updateModProgress() {
            const total = modQueue.length + modSessionStats.approved + modSessionStats.rejected;
            const reviewed = modSessionStats.approved + modSessionStats.rejected;
            const remaining = modQueue.length;

            document.getElementById('modProgressText').textContent = remaining > 0
                ? `${modIndex + 1} of ${remaining} remaining`
                : 'Queue complete';

            const pct = total > 0 ? (reviewed / total) * 100 : 100;
            document.getElementById('modProgressFill').style.width = pct + '%';

            document.getElementById('modApproved').textContent = modSessionStats.approved;
            document.getElementById('modRejected').textContent = modSessionStats.rejected;
            document.getElementById('modSkipped').textContent = modSessionStats.skipped;
        }

        function renderCurrentItem() {
            if (modIndex >= modQueue.length) {
                // Check if we have skipped items to review
                if (modSkippedItems.length > 0) {
                    modQueue = modSkippedItems;
                    modSkippedItems = [];
                    modIndex = 0;
                    renderCurrentItem();
                    return;
                }
                document.getElementById('modCardContainer').style.display = 'none';
                document.getElementById('modEmpty').style.display = 'block';
                updateModProgress();
                return;
            }

            const item = modQueue[modIndex];
            const reviewType = item.review_type;

            // Determine flag display based on review type
            let flagIcon, flagText, flagClass;
            if (reviewType === 'user_flagged') {
                flagIcon = '👎';
                flagText = 'User Flagged (Negative)';
                flagClass = 'user';
            } else if (reviewType === 'no_feedback') {
                flagIcon = '❓';
                flagText = 'No Feedback Provided';
                flagClass = 'none';
            } else {
                flagIcon = '⚠️';
                flagText = 'Auto-Flagged (Low Confidence)';
                flagClass = 'auto';
            }

            const confClass = item.confidence >= 80 ? 'high' : item.confidence >= 60 ? 'medium' : 'low';
            const confText = item.confidence !== null ? Math.round(item.confidence) + '% confidence' : 'No score';

            const sources = (item.sources || []).slice(0, 5);
            const sourcesHtml = sources.map(s => {
                const name = s.name || s.title || 'Source';
                const score = s.score != null ? (s.score * 100).toFixed(0) + '%' : '';
                const ns = s.namespace || '';
                return `<span class="mod-source" title="${escapeHtml(ns)}">${escapeHtml(name)}${score ? ' <strong>' + score + '</strong>' : ''}</span>`;
            }).join('');

            const userNoteHtml = item.user_correction ? `
                <div class="mod-section">
                    <div class="mod-user-note">
                        <div class="mod-user-note-label">User Correction Suggested:</div>
                        <div>${escapeHtml(item.user_correction)}</div>
                    </div>
                </div>
            ` : '';

            const rejectReasonsHtml = REJECT_REASONS.map(r => `
                <button class="mod-reject-reason" onclick="submitReject('${r.id}', '${escapeHtml(r.text)}')">
                    <strong>${r.text}</strong><br>
                    <span style="color: #6c757d; font-size: 12px;">${r.desc}</span>
                </button>
            `).join('');

            document.getElementById('modCardContainer').innerHTML = `
                <div class="mod-card">
                    <div class="mod-card-header">
                        <div class="mod-flag">
                            <div class="mod-flag-icon ${flagClass}">
                                ${flagIcon}
                            </div>
                            <div class="mod-flag-text">
                                ${flagText}
                            </div>
                        </div>
                        <div class="mod-confidence ${confClass}">${confText}</div>
                    </div>
                    <div class="mod-card-body">
                        <div class="mod-section">
                            <div class="mod-label">Question</div>
                            <div class="mod-question">${escapeHtml(item.question)}</div>
                        </div>
                        <div class="mod-section">
                            <div class="mod-label">AI Response</div>
                            <div class="mod-answer">${escapeHtml(item.ai_answer)}</div>
                        </div>
                        ${sourcesHtml ? `
                            <div class="mod-section">
                                <div class="mod-label">Sources Used (${sources.length})</div>
                                <div class="mod-sources">${sourcesHtml}</div>
                            </div>
                        ` : '<div class="mod-section"><div class="mod-label">Sources</div><div style="color:#9ca3af;font-size:13px;">No sources recorded</div></div>'}
                        <div class="mod-section">
                            <div class="mod-label">Confidence Breakdown</div>
                            <div style="display:flex;align-items:center;gap:12px;">
                                <div style="flex:1;background:#e9ecef;height:12px;border-radius:6px;overflow:hidden;">
                                    <div style="height:100%;width:${item.confidence || 0}%;background:${item.confidence >= 80 ? '#28a745' : item.confidence >= 60 ? '#ffc107' : '#dc3545'};border-radius:6px;transition:width 0.3s;"></div>
                                </div>
                                <span style="font-weight:600;font-size:13px;color:${item.confidence >= 80 ? '#28a745' : item.confidence >= 60 ? '#856404' : '#dc3545'};min-width:40px;">${item.confidence != null ? Math.round(item.confidence) + '%' : 'N/A'}</span>
                            </div>
                            <div style="display:flex;gap:16px;margin-top:6px;font-size:11px;color:#6c757d;">
                                <span>Sources: ${sources.length}</span>
                                ${sources.length > 0 ? `<span>Best match: ${(Math.max(...sources.map(s => s.score || 0)) * 100).toFixed(0)}%</span>` : ''}
                                ${item.review_type === 'user_flagged' ? '<span style="color:#dc3545;">User flagged</span>' : ''}
                                ${item.needs_review ? '<span style="color:#d97706;">Auto-flagged</span>' : ''}
                            </div>
                        </div>
                        ${userNoteHtml}
                        <div class="mod-section" id="modEditSection" style="display: none;">
                            <div class="mod-label">Edit Answer <span style="color: #6c757d; font-weight: normal;">(will be used for training)</span></div>
                            <textarea class="mod-edit-area" id="modEditArea" placeholder="Enter corrected answer...">${item.user_correction || item.ai_answer}</textarea>
                        </div>
                    </div>
                    <div class="mod-card-footer">
                        <div class="mod-actions" id="modMainActions">
                            <button class="mod-btn mod-btn-approve" onclick="submitApprove()">
                                ✓ Approve <kbd>A</kbd>
                            </button>
                            <button class="mod-btn mod-btn-edit" onclick="toggleEditMode()">
                                ✎ Edit <kbd>E</kbd>
                            </button>
                            <button class="mod-btn mod-btn-reject" onclick="showRejectReasons()">
                                ✗ Reject <kbd>R</kbd>
                            </button>
                        </div>
                        <div class="mod-actions" id="modEditActions" style="display: none;">
                            <button class="mod-btn mod-btn-approve" onclick="submitApproveWithEdit()">
                                ✓ Save & Approve
                            </button>
                            <button class="mod-btn mod-btn-skip" onclick="toggleEditMode()">
                                Cancel
                            </button>
                        </div>
                        <div class="mod-reject-reasons" id="modRejectReasons">
                            <div class="mod-label">Select Rejection Reason:</div>
                            ${rejectReasonsHtml}
                            <button class="mod-secondary-btn" onclick="hideRejectReasons()" style="width: 100%; margin-top: 8px;">
                                Cancel
                            </button>
                        </div>
                        <div class="mod-secondary-actions">
                            <button class="mod-secondary-btn" onclick="skipItem()">
                                Skip for now <kbd>S</kbd>
                            </button>
                            <button class="mod-secondary-btn" onclick="promoteToGolden()" style="color:#1a4d2e;" title="Save this Q&A as a golden answer for future matching">
                                ★ Promote to Golden
                            </button>
                            ${modIndex > 0 ? `<button class="mod-secondary-btn" onclick="prevItem()">← Previous</button>` : ''}
                            ${modIndex < modQueue.length - 1 ? `<button class="mod-secondary-btn" onclick="nextItem()">Next →</button>` : ''}
                        </div>
                    </div>
                </div>
            `;

            updateModProgress();
            modEditMode = false;
        }

        function toggleEditMode() {
            modEditMode = !modEditMode;
            document.getElementById('modEditSection').style.display = modEditMode ? 'block' : 'none';
            document.getElementById('modMainActions').style.display = modEditMode ? 'none' : 'flex';
            document.getElementById('modEditActions').style.display = modEditMode ? 'flex' : 'none';
            document.getElementById('modRejectReasons').classList.remove('active');

            if (modEditMode) {
                document.getElementById('modEditArea').focus();
            }
        }

        function showRejectReasons() {
            document.getElementById('modRejectReasons').classList.add('active');
        }

        function hideRejectReasons() {
            document.getElementById('modRejectReasons').classList.remove('active');
        }

        async function submitApprove() {
            await moderateCurrentItem('approve', null, null);
        }

        async function submitApproveWithEdit() {
            const editedAnswer = document.getElementById('modEditArea').value.trim();
            if (!editedAnswer) {
                alert('Please enter a corrected answer');
                return;
            }
            await moderateCurrentItem('approve', editedAnswer, 'Edited by moderator');
        }

        async function submitReject(reasonId, reasonText) {
            await moderateCurrentItem('reject', null, reasonText);
        }

        async function moderateCurrentItem(action, correctedAnswer, reason) {
            const item = modQueue[modIndex];

            try {
                const response = await fetch('/admin/moderate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: item.id,
                        action,
                        corrected_answer: correctedAnswer,
                        reason
                    })
                });

                const result = await response.json();
                if (result.success) {
                    // Update session stats
                    if (action === 'approve') {
                        modSessionStats.approved++;
                    } else {
                        modSessionStats.rejected++;
                    }

                    // Remove from queue and advance
                    modQueue.splice(modIndex, 1);
                    if (modIndex >= modQueue.length && modIndex > 0) {
                        modIndex = modQueue.length - 1;
                    }

                    loadStats();
                    renderCurrentItem();
                } else {
                    alert('Error: ' + (result.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error moderating item:', error);
                alert('Error processing action');
            }
        }

        function skipItem() {
            const item = modQueue[modIndex];
            modSkippedItems.push(item);
            modSessionStats.skipped++;
            modQueue.splice(modIndex, 1);
            if (modIndex >= modQueue.length && modIndex > 0) {
                modIndex = modQueue.length - 1;
            }
            renderCurrentItem();
        }

        function nextItem() {
            if (modIndex < modQueue.length - 1) {
                modIndex++;
                renderCurrentItem();
            }
        }

        function prevItem() {
            if (modIndex > 0) {
                modIndex--;
                renderCurrentItem();
            }
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (currentTab !== 'review') return;
            if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
            if (modQueue.length === 0) return;

            switch(e.key.toLowerCase()) {
                case 'a':
                    e.preventDefault();
                    if (modEditMode) {
                        submitApproveWithEdit();
                    } else {
                        submitApprove();
                    }
                    break;
                case 'r':
                    e.preventDefault();
                    if (!modEditMode) {
                        showRejectReasons();
                    }
                    break;
                case 'e':
                    e.preventDefault();
                    toggleEditMode();
                    break;
                case 's':
                    e.preventDefault();
                    skipItem();
                    break;
                case 'arrowleft':
                    e.preventDefault();
                    prevItem();
                    break;
                case 'arrowright':
                    e.preventDefault();
                    nextItem();
                    break;
                case 'escape':
                    hideRejectReasons();
                    if (modEditMode) toggleEditMode();
                    break;
                case 'b':
                    e.preventDefault();
                    toggleBulkMode();
                    break;
            }
        });

        async function loadAuditLog() {
            try {
                const response = await fetch('/admin/moderator-history');
                const history = await response.json();

                document.getElementById('auditLoading').style.display = 'none';
                const list = document.getElementById('auditList');

                if (history.length === 0) {
                    list.innerHTML = '<div class="empty-state"><p>No moderation actions yet</p></div>';
                    return;
                }

                list.innerHTML = history.map(item => {
                    const iconClass = item.action === 'approve' ? 'approve' :
                                      item.action === 'reject' ? 'reject' : 'correct';
                    const icon = item.action === 'approve' ? '✓' :
                                 item.action === 'reject' ? '✗' : '✎';
                    const actionText = item.action === 'approve' ? 'Approved' :
                                       item.action === 'reject' ? 'Rejected' : 'Corrected';

                    const timestamp = item.timestamp ? new Date(item.timestamp).toLocaleString() : '';

                    return `
                        <div class="audit-item">
                            <div class="audit-icon ${iconClass}">${icon}</div>
                            <div class="audit-content">
                                <div class="audit-action">${actionText}</div>
                                <div class="audit-question">${escapeHtml(item.question || 'Unknown question')}</div>
                                <div class="audit-meta">${item.moderator} • ${timestamp}</div>
                                ${item.reason ? `<div class="audit-reason">"${escapeHtml(item.reason)}"</div>` : ''}
                            </div>
                        </div>
                    `;
                }).join('');
            } catch (error) {
                console.error('Error loading audit log:', error);
                document.getElementById('auditLoading').style.display = 'none';
                document.getElementById('auditList').innerHTML = '<div class="empty-state"><p>Error loading audit log</p></div>';
            }
        }

        // Keep old function name for backwards compatibility
        async function loadReviewFeedback() {
            await loadReviewQueue();
        }

        async function loadAllFeedback() {
            try {
                const response = await fetch('/admin/feedback/all');
                const feedback = await response.json();

                document.getElementById('allLoading').style.display = 'none';
                const list = document.getElementById('allList');

                if (feedback.length === 0) {
                    list.innerHTML = '<div class="empty-state"><p>No feedback yet</p></div>';
                    return;
                }

                list.innerHTML = feedback.map(item => createFeedbackCard(item, false)).join('');
            } catch (error) {
                console.error('Error loading feedback:', error);
            }
        }

        function createFeedbackCard(item, showActions) {
            const ratingClass = item.rating === 'positive' ? 'rating-positive' : item.rating === 'negative' ? 'rating-negative' : 'rating-unrated';
            const ratingText = item.rating === 'positive' ? '👍 Positive' : item.rating === 'negative' ? '👎 Negative' : 'No Feedback';

            const correctionHtml = item.correction ? `
                <div class="feedback-correction">
                    <div class="correction-label">User's Correction:</div>
                    <div>${escapeHtml(item.correction)}</div>
                </div>
            ` : '';

            const actionsHtml = showActions && item.correction ? `
                <div class="feedback-actions">
                    <button class="btn btn-success" onclick="approveFeedback(${item.id})">✓ Approve</button>
                    <button class="btn btn-danger" onclick="rejectFeedback(${item.id})">✗ Reject</button>
                </div>
            ` : '';

            const timestamp = item.timestamp ? new Date(item.timestamp).toLocaleString() : '';

            return `
                <div class="feedback-card" id="card-${item.id}">
                    <div class="feedback-header">
                        <div class="feedback-rating ${ratingClass}">${ratingText}</div>
                        <div class="timestamp">${timestamp}</div>
                    </div>
                    <div class="feedback-question">${escapeHtml(item.question)}</div>
                    <div class="feedback-answer">${escapeHtml(item.ai_answer)}</div>
                    ${correctionHtml}
                    ${actionsHtml}
                </div>
            `;
        }

        async function approveFeedback(id) {
            try {
                const card = document.getElementById('card-' + id);
                const correction = card.querySelector('.feedback-correction div:last-child')?.textContent || '';

                await fetch('/admin/feedback/approve', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id, correction})
                });

                card.remove();
                loadStats();
            } catch (error) {
                alert('Error approving feedback');
            }
        }

        async function rejectFeedback(id) {
            try {
                await fetch('/admin/feedback/reject', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id})
                });
                document.getElementById('card-' + id).remove();
                loadStats();
            } catch (error) {
                alert('Error rejecting feedback');
            }
        }

        async function generateTrainingFile() {
            if (!confirm('Generate JSONL training file from all approved corrections?\n\nThis will create a file ready for OpenAI fine-tuning.')) return;
            try {
                const response = await fetch('/admin/training/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await response.json();
                if (data.success) {
                    alert(`Training file generated!\n\n${data.num_examples} examples\nFile: ${data.filepath}\n\nReady for fine-tuning via the Feedback Loop section.`);
                } else {
                    const current = data.current_count || 0;
                    const needed = data.needed || 50;
                    alert(`Not enough approved examples.\n\nCurrent: ${current}\nNeeded: ${needed}\n\nApprove more corrections in the Review tab to reach the threshold.`);
                }
            } catch (error) {
                alert('Error generating training file: ' + error.message);
            }
        }

        function exportData() {
            alert('Export feature coming soon');
        }

        async function testAPIs() {
            await checkAPIStatus();
            alert('API status updated');
        }

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            if (tab === 'overview') {
                document.getElementById('overviewTab').classList.add('active');
            } else if (tab === 'review') {
                document.getElementById('reviewTab').classList.add('active');
                loadReviewQueue();
            } else if (tab === 'audit') {
                document.getElementById('auditTab').classList.add('active');
                loadAuditLog();
            } else if (tab === 'analytics') {
                document.getElementById('analyticsTab').classList.add('active');
                loadAllFeedback();
                loadStats().then(() => {});
            } else if (tab === 'system') {
                document.getElementById('systemTab').classList.add('active');
                loadCacheStats();
            } else if (tab === 'intelligence') {
                document.getElementById('intelligenceTab').classList.add('active');
                loadIntelligenceOverview();
            }
        }

        async function loadKnowledgeStatus() {
            try {
                const response = await fetch('/admin/knowledge');
                const data = await response.json();

                // Pinecone total
                const totalEl = document.getElementById('kbPineconeTotal');
                totalEl.textContent = (data.pinecone_total_vectors || 0).toLocaleString();

                // Scraped sources summary
                const sourcesEl = document.getElementById('kbScrapedSources');
                if (data.scraped_sources) {
                    const sourceNames = {
                        'disease_guides': 'Disease Guides',
                        'weed_guides': 'Weed Guides',
                        'pest_guides': 'Pest/Insect Guides',
                        'cultural_practices': 'Cultural Practices',
                        'nematode_guides': 'Nematode Guides',
                        'abiotic_disorders': 'Abiotic Disorders',
                        'irrigation': 'Irrigation',
                        'fertility': 'Fertility/Nutrition'
                    };
                    let html = '<div style="display: flex; flex-wrap: wrap; gap: 6px;">';
                    for (const [key, info] of Object.entries(data.scraped_sources)) {
                        const label = sourceNames[key] || key;
                        html += `<span style="background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 4px; font-size: 12px;">${escapeHtml(label)}</span>`;
                    }
                    html += '</div>';
                    sourcesEl.innerHTML = html;
                }

                // PDF stats
                document.getElementById('kbIndexed').textContent = data.indexed_files || 0;
                document.getElementById('kbChunks').textContent = data.total_chunks || 0;
                document.getElementById('kbTotal').textContent = data.total_pdfs || 0;

                const unindexed = data.unindexed || 0;
                const unindexedEl = document.getElementById('kbUnindexed');
                unindexedEl.textContent = unindexed;
                unindexedEl.style.color = unindexed > 0 ? '#dc3545' : '#28a745';

                const listEl = document.getElementById('kbUnindexedList');
                if (data.unindexed_sample && data.unindexed_sample.length > 0) {
                    listEl.innerHTML = '<strong>Sample unindexed:</strong> ' +
                        data.unindexed_sample.slice(0, 5).map(f => escapeHtml(f)).join(', ') +
                        (data.unindexed > 5 ? '...' : '');
                } else {
                    listEl.innerHTML = '<span style="color: #28a745;">All PDFs indexed</span>';
                }
            } catch (error) {
                console.error('Error loading knowledge status:', error);
            }
        }

        async function buildKnowledge(limit) {
            const statusEl = document.getElementById('kbBuildStatus');
            statusEl.innerHTML = '<span style="color: #0d6efd;">Starting indexing...</span>';

            try {
                const response = await fetch('/admin/knowledge/build', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({limit})
                });
                const data = await response.json();

                if (data.success) {
                    statusEl.innerHTML = '<span style="color: #28a745;">' + escapeHtml(data.message) + '</span>';
                    // Auto-refresh status after processing delay (10s per file is typical)
                    const refreshDelay = Math.min(limit * 10000, 60000);
                    statusEl.innerHTML += `<br><span style="color: #6c757d; font-size: 12px;">Auto-refreshing in ${Math.round(refreshDelay/1000)}s...</span>`;
                    setTimeout(() => {
                        loadKnowledgeStatus();
                        statusEl.innerHTML = '';
                    }, refreshDelay);
                } else {
                    statusEl.innerHTML = '<span style="color: #dc3545;">Error: ' + escapeHtml(data.message || 'Unknown error') + '</span>';
                }
            } catch (error) {
                statusEl.innerHTML = '<span style="color: #dc3545;">Error starting build: ' + escapeHtml(error.message) + '</span>';
            }
        }

        // =====================================================================
        // FINE-TUNING & FEEDBACK LOOP FUNCTIONS
        // =====================================================================

        async function loadFineTuningStatus() {
            try {
                const response = await fetch('/admin/fine-tuning/status');
                const data = await response.json();

                document.getElementById('ftExamples').textContent = data.training_examples_ready || 0;
                document.getElementById('ftNeeded').textContent = data.min_examples_needed || 50;
                document.getElementById('ftReady').textContent = data.ready_to_train ? '✓ Yes' : '✗ No';
                document.getElementById('ftReady').style.color = data.ready_to_train ? '#28a745' : '#dc3545';

                const btn = document.getElementById('startFineTuningBtn');
                btn.disabled = !data.ready_to_train;

                if (data.active_fine_tuned_model) {
                    const shortModel = data.active_fine_tuned_model.split(':').pop().substring(0, 20);
                    document.getElementById('ftModel').textContent = shortModel + '...';
                    document.getElementById('ftModel').title = data.active_fine_tuned_model;
                } else {
                    document.getElementById('ftModel').textContent = 'None';
                }

                // Show recent jobs
                if (data.recent_jobs && data.recent_jobs.length > 0) {
                    document.getElementById('ftJobs').innerHTML = `
                        <strong>Recent Jobs:</strong>
                        <div style="margin-top: 8px;">
                            ${data.recent_jobs.slice(0, 3).map(job => `
                                <div style="padding: 6px 0; border-bottom: 1px solid #eee;">
                                    <span class="bulk-item-badge ${job.status === 'succeeded' ? 'conf-high' : job.status === 'failed' ? 'conf-low' : ''}">${job.status}</span>
                                    ${job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}
                                </div>
                            `).join('')}
                        </div>
                    `;
                }

            } catch (error) {
                console.error('Error loading fine-tuning status:', error);
            }
        }

        async function startFineTuning() {
            if (!confirm('Start fine-tuning pipeline? This will upload training data and begin model training.')) {
                return;
            }

            const statusEl = document.getElementById('ftStatus');
            statusEl.innerHTML = '<span style="color: #007bff;">⏳ Starting fine-tuning pipeline...</span>';

            try {
                const response = await fetch('/admin/fine-tuning/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const result = await response.json();

                if (result.success) {
                    statusEl.innerHTML = `
                        <span style="color: #28a745;">✓ Fine-tuning started!</span><br>
                        <span style="font-size: 12px;">Job ID: ${result.job_id}</span>
                    `;
                } else {
                    statusEl.innerHTML = `<span style="color: #dc3545;">✗ ${result.error || 'Failed to start'}</span>`;
                }

                loadFineTuningStatus();

            } catch (error) {
                statusEl.innerHTML = '<span style="color: #dc3545;">✗ Error starting fine-tuning</span>';
                console.error('Fine-tuning error:', error);
            }
        }

        async function loadSourceQuality() {
            try {
                const response = await fetch('/admin/source-quality');
                const data = await response.json();

                const lowQuality = data.low_quality || [];

                if (lowQuality.length > 0) {
                    document.getElementById('lowQualitySources').innerHTML = `
                        <strong style="color: #dc3545;">⚠️ Low Quality Sources (${lowQuality.length})</strong>
                        <div style="margin-top: 8px; font-size: 13px;">
                            ${lowQuality.slice(0, 5).map(s => `
                                <div style="padding: 8px; background: #fff3cd; border-radius: 4px; margin-bottom: 6px;">
                                    <strong>${escapeHtml(s.name)}</strong><br>
                                    <span style="color: #6c757d;">Score: ${(s.score * 100).toFixed(0)}% | 👍 ${s.positive} | 👎 ${s.negative}</span>
                                </div>
                            `).join('')}
                        </div>
                    `;
                } else {
                    document.getElementById('lowQualitySources').innerHTML = `
                        <span style="color: #28a745;">✓ No low-quality sources detected</span>
                    `;
                }

            } catch (error) {
                console.error('Error loading source quality:', error);
            }
        }

        async function runEvaluation() {
            if (!confirm('Run evaluation against test questions? This may take a minute.')) {
                return;
            }

            const statusEl = document.getElementById('ftStatus');
            statusEl.innerHTML = '<span style="color: #007bff;">⏳ Running evaluation...</span>';

            try {
                const response = await fetch('/admin/eval/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });

                const result = await response.json();

                if (result.error) {
                    statusEl.innerHTML = `<span style="color: #dc3545;">✗ ${result.error}</span>`;
                    return;
                }

                const summary = result.summary || {};
                statusEl.innerHTML = `
                    <div style="background: #e8f5e9; padding: 12px; border-radius: 6px;">
                        <strong>✓ Evaluation Complete</strong><br>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 8px; font-size: 13px;">
                            <div>Questions: ${summary.total_questions || 0}</div>
                            <div>Avg Score: ${summary.avg_overall_score || 0}%</div>
                            <div>Avg Confidence: ${summary.avg_confidence || 0}%</div>
                            <div>Keyword Match: ${summary.avg_keyword_score || 0}%</div>
                        </div>
                    </div>
                `;

                loadEvalHistory();

            } catch (error) {
                statusEl.innerHTML = '<span style="color: #dc3545;">✗ Evaluation failed</span>';
                console.error('Evaluation error:', error);
            }
        }

        async function loadEvalHistory() {
            try {
                const response = await fetch('/admin/eval/history?limit=5');
                const history = await response.json();

                if (history.length === 0) {
                    document.getElementById('evalHistory').innerHTML = `
                        <p style="color: #6c757d; font-size: 13px;">No evaluations run yet.</p>
                    `;
                    return;
                }

                document.getElementById('evalHistory').innerHTML = `
                    <table style="width: 100%; font-size: 13px;">
                        <tr style="text-align: left; color: #6c757d;">
                            <th>Date</th>
                            <th>Questions</th>
                            <th>Score</th>
                            <th>Confidence</th>
                        </tr>
                        ${history.map(h => `
                            <tr>
                                <td>${new Date(h.run_date).toLocaleDateString()}</td>
                                <td>${h.total_questions}</td>
                                <td>${h.avg_overall_score}%</td>
                                <td>${h.avg_confidence}%</td>
                            </tr>
                        `).join('')}
                    </table>
                `;

            } catch (error) {
                console.error('Error loading eval history:', error);
            }
        }

        // =====================================================================
        // INTELLIGENCE ENGINE FUNCTIONS
        // =====================================================================

        async function loadIntelligenceOverview() {
            try {
                const response = await fetch('/api/intelligence/overview');
                const data = await response.json();

                document.getElementById('intelGoldenCount').textContent = data.golden_answers || 0;
                document.getElementById('intelABTests').textContent = data.active_ab_tests || 0;
                document.getElementById('intelSources').textContent = data.tracked_sources || 0;
                document.getElementById('intelCalibPoints').textContent = data.calibration_points || 0;
                document.getElementById('intelTopics').textContent = data.topic_clusters || 0;
                document.getElementById('intelEscalations').textContent = data.open_escalations || 0;
                document.getElementById('intelRegTests').textContent = data.regression_tests || 0;

                const predAcc = data.prediction_accuracy;
                document.getElementById('intelPredAccuracy').textContent =
                    predAcc && predAcc.total > 0 ? (predAcc.accuracy * 100).toFixed(0) + '%' : 'N/A';

                // Enterprise overview cards
                const hs = data.system_health_score || 0;
                document.getElementById('intelHealthScore').textContent = hs > 0 ? hs.toFixed(0) : '-';
                document.getElementById('intelHealthScore').style.color =
                    hs >= 80 ? '#059669' : hs >= 60 ? '#d97706' : '#dc2626';
                document.getElementById('intelTotalCost').textContent =
                    data.total_cost_usd != null ? '$' + data.total_cost_usd.toFixed(4) : '-';
                document.getElementById('intelAnomalies').textContent = data.active_anomalies || 0;
                document.getElementById('intelAlerts').textContent = data.active_alerts || 0;
                document.getElementById('intelBreakers').textContent = data.open_circuit_breakers || 0;
                document.getElementById('intelPromptVersions').textContent = data.prompt_versions || 0;
                document.getElementById('intelGaps').textContent = data.knowledge_gaps || 0;
                document.getElementById('intelPipelineCount').textContent = data.pipeline_requests_tracked || 0;

                // Anthropic-grade overview cards
                document.getElementById('intelFlagsEnabled').textContent = data.feature_flags_enabled || 0;
                document.getElementById('intelRateBlocked').textContent = data.rate_limit_blocked || 0;
                const budgetPct = data.budget_daily_pct || 0;
                document.getElementById('intelBudgetDailyPct').textContent = budgetPct.toFixed(0) + '%';
                document.getElementById('intelBudgetDailyPct').style.color =
                    budgetPct >= 100 ? '#dc2626' : budgetPct >= 80 ? '#d97706' : '#059669';
                const trReady = data.training_ready;
                document.getElementById('intelTrainingReady').textContent = trReady ? 'YES' : 'No';
                document.getElementById('intelTrainingReady').style.color = trReady ? '#059669' : '#6b7280';

                loadGoldenAnswers();
                loadEscalations();
                loadSourceLeaderboard();
                loadCalibration();
                loadTopics();
                loadRegressionDashboard();
                loadABTests();
                loadSatisfactionStats();
                loadIntelEvents();
                // Enterprise panels
                loadPipelineMetrics();
                loadExecutiveHealth();
                loadAnomalies();
                loadAlerts();
                loadCircuitBreakers();
                loadPromptVersions();
                loadKnowledgeGaps();
                loadConversationMetrics();
                loadROI();
                // Anthropic-grade panels
                loadFeatureFlags();
                loadCostBudget();
                loadDataRetention();
                loadTrainingStatus();
            } catch (error) {
                console.error('Error loading intelligence overview:', error);
            }
        }

        async function loadGoldenAnswers() {
            try {
                const response = await fetch('/api/intelligence/golden-answers');
                const data = await response.json();
                const el = document.getElementById('goldenAnswersList');

                if (!data || data.length === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No golden answers yet. Detect weak patterns and create golden answers to improve recurring questions.</p>';
                    return;
                }

                el.innerHTML = data.slice(0, 10).map(ga => `
                    <div style="padding: 8px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 6px; font-size: 13px;">
                        <div style="font-weight: 600; color: #1a4d2e;">${escapeHtml(ga.question).substring(0, 80)}...</div>
                        <div style="color: #6b7280; margin-top: 2px;">${escapeHtml(ga.answer).substring(0, 120)}...</div>
                        <div style="display: flex; gap: 8px; margin-top: 4px; font-size: 11px; color: #9ca3af;">
                            <span>Used: ${ga.times_used}x</span>
                            ${ga.category ? `<span>Category: ${escapeHtml(ga.category)}</span>` : ''}
                            ${ga.avg_rating_when_used ? `<span>Avg rating: ${(ga.avg_rating_when_used * 100).toFixed(0)}%</span>` : ''}
                            <button onclick="deleteGoldenAnswer(${ga.id})" style="color: #dc2626; background: none; border: none; cursor: pointer; font-size: 11px;">Delete</button>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error loading golden answers:', error);
            }
        }

        async function createGoldenAnswer() {
            const question = document.getElementById('goldenQuestion').value.trim();
            const answer = document.getElementById('goldenAnswer').value.trim();
            const category = document.getElementById('goldenCategory').value.trim();

            if (!question || !answer) { alert('Question and answer are required.'); return; }

            try {
                const response = await fetch('/api/intelligence/golden-answers', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ question, answer, category: category || null })
                });
                const data = await response.json();
                if (data.success) {
                    document.getElementById('goldenQuestion').value = '';
                    document.getElementById('goldenAnswer').value = '';
                    document.getElementById('goldenCategory').value = '';
                    loadGoldenAnswers();
                    loadIntelligenceOverview();
                }
            } catch (error) { alert('Error creating golden answer: ' + error.message); }
        }

        async function deleteGoldenAnswer(id) {
            if (!confirm('Delete this golden answer?')) return;
            try {
                await fetch(`/api/intelligence/golden-answers/${id}`, { method: 'DELETE' });
                loadGoldenAnswers();
                loadIntelligenceOverview();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadWeakPatterns() {
            try {
                const response = await fetch('/api/intelligence/weak-patterns');
                const data = await response.json();
                const el = document.getElementById('weakPatterns');

                if (!data || data.length === 0) {
                    el.innerHTML = '<p style="color: #059669; font-size: 13px; padding: 8px; background: #dcfce7; border-radius: 6px;">No weak patterns detected. Your answers are performing well.</p>';
                    return;
                }

                el.innerHTML = '<div style="font-weight: 600; font-size: 13px; margin-bottom: 6px; color: #dc2626;">Weak Patterns Found (' + data.length + ')</div>' +
                    data.map(p => `
                    <div style="padding: 8px; border: 1px solid #fecaca; border-radius: 6px; margin-bottom: 6px; font-size: 13px; background: #fef2f2;">
                        <div style="font-weight: 600;">${escapeHtml(p.question).substring(0, 100)}</div>
                        <div style="display: flex; gap: 12px; margin-top: 4px; font-size: 11px; color: #6b7280;">
                            <span>Occurrences: ${p.occurrences}</span>
                            <span>Avg Confidence: ${p.avg_confidence}%</span>
                            <span style="color: #dc2626;">Negative Rate: ${(p.negative_rate * 100).toFixed(0)}%</span>
                        </div>
                        <button onclick="document.getElementById('goldenQuestion').value='${escapeHtml(p.question).replace(/'/g, "\\'")}'" style="margin-top: 4px; font-size: 11px; color: #1a4d2e; background: #dcfce7; border: none; padding: 2px 8px; border-radius: 4px; cursor: pointer;">Use as Golden Answer Template</button>
                    </div>
                `).join('');
            } catch (error) { console.error('Error loading weak patterns:', error); }
        }

        async function loadEscalations() {
            try {
                const [queueResp, statsResp] = await Promise.all([
                    fetch('/api/intelligence/escalations'),
                    fetch('/api/intelligence/escalations/stats')
                ]);
                const queue = await queueResp.json();
                const stats = await statsResp.json();

                // Stats bar
                const statsEl = document.getElementById('escalationStats');
                statsEl.innerHTML = `
                    <div style="padding: 6px 12px; background: #fef2f2; border-radius: 6px; font-size: 12px;">
                        <span style="font-weight: 600; color: #dc2626;">${stats.open_count || 0}</span> Open
                    </div>
                    <div style="padding: 6px 12px; background: #dcfce7; border-radius: 6px; font-size: 12px;">
                        <span style="font-weight: 600; color: #059669;">${stats.resolved_count || 0}</span> Resolved
                    </div>
                    <div style="padding: 6px 12px; background: #f3f4f6; border-radius: 6px; font-size: 12px;">
                        Avg Resolution: <span style="font-weight: 600;">${stats.avg_resolution_hours || 0}h</span>
                    </div>
                `;

                // Queue
                const queueEl = document.getElementById('escalationQueue');
                if (!queue || queue.length === 0) {
                    queueEl.innerHTML = '<p style="color: #059669; font-size: 13px; padding: 8px; background: #dcfce7; border-radius: 6px;">No open escalations. System is running smoothly.</p>';
                    return;
                }

                const modeColors = {
                    'hallucination': '#dc2626', 'safety_concern': '#dc2626',
                    'low_confidence': '#d97706', 'predicted_negative': '#d97706',
                    'insufficient_sources': '#7c3aed', 'wrong_category': '#2563eb',
                    'outdated_info': '#0891b2', 'off_topic': '#6b7280'
                };

                queueEl.innerHTML = queue.slice(0, 15).map(esc => `
                    <div style="padding: 10px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 8px; font-size: 13px; border-left: 3px solid ${modeColors[esc.failure_mode] || '#6b7280'};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 600;">${escapeHtml(esc.question).substring(0, 80)}...</span>
                            <span style="font-size: 11px; padding: 2px 8px; border-radius: 4px; background: ${modeColors[esc.failure_mode] || '#6b7280'}22; color: ${modeColors[esc.failure_mode] || '#6b7280'}; font-weight: 600;">${esc.failure_mode}</span>
                        </div>
                        <div style="color: #6b7280; margin-top: 4px; font-size: 12px;">${escapeHtml((esc.failure_details || '').substring(0, 150))}</div>
                        <div style="display: flex; gap: 8px; margin-top: 6px; font-size: 11px; color: #9ca3af;">
                            <span>Priority: ${esc.priority}/10</span>
                            <span>Confidence: ${esc.confidence ? esc.confidence.toFixed(0) : 'N/A'}%</span>
                            ${esc.predicted_satisfaction ? `<span>Pred. Satisfaction: ${(esc.predicted_satisfaction * 100).toFixed(0)}%</span>` : ''}
                        </div>
                        ${esc.suggested_fix ? `<div style="margin-top: 6px; padding: 6px; background: #f0fdf4; border-radius: 4px; font-size: 12px; color: #166534;"><strong>Suggested fix:</strong> ${escapeHtml(esc.suggested_fix).substring(0, 200)}...</div>` : ''}
                        <div style="margin-top: 6px; display: flex; gap: 6px;">
                            <button onclick="resolveEscalation(${esc.id}, 'dismiss')" style="font-size: 11px; padding: 3px 8px; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 4px; cursor: pointer;">Dismiss</button>
                            <button onclick="resolveEscalation(${esc.id}, 'approve_with_fix')" style="font-size: 11px; padding: 3px 8px; background: #dcfce7; border: 1px solid #bbf7d0; border-radius: 4px; cursor: pointer; color: #166534;">Fix & Promote</button>
                        </div>
                    </div>
                `).join('');
            } catch (error) { console.error('Error loading escalations:', error); }
        }

        async function resolveEscalation(id, action) {
            try {
                await fetch(`/api/intelligence/escalations/${id}/resolve`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ action, resolved_by: 'admin' })
                });
                loadEscalations();
                loadIntelligenceOverview();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadSourceLeaderboard() {
            try {
                const response = await fetch('/api/intelligence/sources?limit=20&min_appearances=1');
                const data = await response.json();
                const el = document.getElementById('sourceLeaderboard');

                if (!data || data.length === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No source reliability data yet. Source trust scores build as users rate answers.</p>';
                    return;
                }

                el.innerHTML = `
                    <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                        <tr style="text-align: left; color: #6b7280; border-bottom: 1px solid #e5e7eb;">
                            <th style="padding: 4px 6px;">Source</th>
                            <th style="padding: 4px 6px;">Trust</th>
                            <th style="padding: 4px 6px;">+/-</th>
                            <th style="padding: 4px 6px;">Uses</th>
                        </tr>
                        ${data.slice(0, 15).map(s => {
                            const trustColor = s.trust_score >= 0.7 ? '#059669' : s.trust_score >= 0.4 ? '#d97706' : '#dc2626';
                            const trustPct = (s.trust_score * 100).toFixed(0);
                            return `<tr style="border-bottom: 1px solid #f3f4f6;">
                                <td style="padding: 4px 6px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(s.source_title || s.source_id)}">${escapeHtml((s.source_title || s.source_id || '').substring(0, 40))}</td>
                                <td style="padding: 4px 6px; color: ${trustColor}; font-weight: 600;">${trustPct}%</td>
                                <td style="padding: 4px 6px;"><span style="color: #059669;">+${s.positive_count}</span> / <span style="color: #dc2626;">-${s.negative_count}</span></td>
                                <td style="padding: 4px 6px;">${s.total_appearances}</td>
                            </tr>`;
                        }).join('')}
                    </table>
                `;
            } catch (error) { console.error('Error loading source leaderboard:', error); }
        }

        async function loadCalibration() {
            try {
                const response = await fetch('/api/intelligence/calibration-report');
                const data = await response.json();
                const el = document.getElementById('calibrationReport');

                if (!data.overall || data.overall.total_points === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No calibration data yet. Calibration points are recorded when users rate answers.</p>';
                    return;
                }

                const ece = data.overall.ece;
                const eceColor = ece < 5 ? '#059669' : ece < 15 ? '#d97706' : '#dc2626';

                let html = `
                    <div style="display: flex; gap: 12px; margin-bottom: 12px;">
                        <div style="padding: 8px 12px; background: #f3f4f6; border-radius: 6px; font-size: 12px;">
                            Data Points: <strong>${data.overall.total_points}</strong>
                        </div>
                        <div style="padding: 8px 12px; background: ${eceColor}15; border-radius: 6px; font-size: 12px;">
                            ECE: <strong style="color: ${eceColor};">${ece.toFixed(1)}</strong>
                        </div>
                    </div>
                `;

                // Calibration curve as text bars
                if (data.overall.bins && data.overall.bins.length > 0) {
                    html += '<div style="font-size: 11px; color: #6b7280; margin-bottom: 4px;">Predicted vs Actual Satisfaction:</div>';
                    html += data.overall.bins.map(b => {
                        const barWidth = Math.max(5, b.actual_satisfaction);
                        const gap = Math.abs(b.predicted_avg - b.actual_satisfaction);
                        const gapColor = gap < 10 ? '#059669' : gap < 20 ? '#d97706' : '#dc2626';
                        return `<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px; font-size: 11px;">
                            <span style="width: 55px; text-align: right; color: #6b7280;">${b.bin_low.toFixed(0)}-${b.bin_high.toFixed(0)}%</span>
                            <div style="flex: 1; height: 14px; background: #f3f4f6; border-radius: 3px; overflow: hidden;">
                                <div style="width: ${barWidth}%; height: 100%; background: #1a4d2e; border-radius: 3px;"></div>
                            </div>
                            <span style="width: 40px; color: ${gapColor}; font-weight: 600;">${b.actual_satisfaction.toFixed(0)}%</span>
                            <span style="width: 20px; color: #9ca3af;">(${b.count})</span>
                        </div>`;
                    }).join('');
                }

                // Miscalibrated topics
                if (data.most_miscalibrated && data.most_miscalibrated.length > 0) {
                    html += '<div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: #dc2626;">Most Miscalibrated Topics:</div>';
                    html += data.most_miscalibrated.slice(0, 5).map(([topic, ece]) =>
                        `<div style="font-size: 11px; color: #6b7280; padding: 2px 0;">${escapeHtml(topic || 'General')}: ECE ${ece.toFixed(1)}</div>`
                    ).join('');
                }

                el.innerHTML = html;
            } catch (error) { console.error('Error loading calibration:', error); }
        }

        async function loadTopics() {
            try {
                const response = await fetch('/api/intelligence/topics');
                const data = await response.json();
                const el = document.getElementById('topicDashboard');

                if (!data.clusters || data.clusters.length === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No topic clusters yet. Run clustering after accumulating enough questions.</p>';
                    return;
                }

                let html = `<div style="font-size: 12px; color: #6b7280; margin-bottom: 8px;">${data.total_clusters} clusters detected</div>`;

                // Problematic topics
                if (data.problematic && data.problematic.length > 0) {
                    html += '<div style="font-weight: 600; font-size: 12px; color: #dc2626; margin-bottom: 4px;">Problematic Topics:</div>';
                    html += data.problematic.map(t => `
                        <div style="padding: 6px; border: 1px solid #fecaca; border-radius: 4px; margin-bottom: 4px; font-size: 12px; background: #fef2f2;">
                            <strong>${escapeHtml(t.name || 'Unnamed')}</strong> — ${t.question_count} questions, ${(t.negative_rate * 100).toFixed(0)}% negative
                        </div>
                    `).join('');
                }

                // Emerging topics
                if (data.emerging && data.emerging.length > 0) {
                    html += '<div style="font-weight: 600; font-size: 12px; color: #2563eb; margin-top: 8px; margin-bottom: 4px;">Emerging Topics:</div>';
                    html += data.emerging.map(t => `
                        <div style="padding: 6px; border: 1px solid #bfdbfe; border-radius: 4px; margin-bottom: 4px; font-size: 12px; background: #eff6ff;">
                            <strong>${escapeHtml(t.name || 'Unnamed')}</strong> — ${t.question_count} questions
                        </div>
                    `).join('');
                }

                // All clusters
                html += '<div style="font-weight: 600; font-size: 12px; color: #374151; margin-top: 8px; margin-bottom: 4px;">All Clusters:</div>';
                html += data.clusters.slice(0, 20).map(t => {
                    const confColor = (t.avg_confidence || 0) >= 70 ? '#059669' : (t.avg_confidence || 0) >= 50 ? '#d97706' : '#dc2626';
                    return `<div style="display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; border-bottom: 1px solid #f3f4f6;">
                        <span>${escapeHtml(t.name || 'Unnamed')}</span>
                        <span style="color: #6b7280;">${t.question_count}q | <span style="color: ${confColor};">${(t.avg_confidence || 0).toFixed(0)}%</span></span>
                    </div>`;
                }).join('');

                el.innerHTML = html;
            } catch (error) { console.error('Error loading topics:', error); }
        }

        async function runClustering() {
            try {
                const response = await fetch('/api/intelligence/topics/cluster', { method: 'POST' });
                const data = await response.json();
                alert(`Clustering complete: ${data.clusters_created || 0} clusters created from ${data.questions_processed || 0} questions.`);
                loadTopics();
                loadIntelligenceOverview();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadRegressionDashboard() {
            try {
                const response = await fetch('/api/intelligence/regression-dashboard');
                const data = await response.json();
                const el = document.getElementById('regressionDashboard');

                let html = `<div style="font-size: 12px; color: #6b7280; margin-bottom: 8px;">${data.test_count} active tests</div>`;

                if (data.latest_run) {
                    const run = data.latest_run;
                    const passColor = run.failed > 0 ? '#dc2626' : run.warned > 0 ? '#d97706' : '#059669';
                    html += `
                        <div style="padding: 8px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 8px; background: ${passColor}08;">
                            <div style="font-weight: 600; font-size: 13px;">Latest Run</div>
                            <div style="display: flex; gap: 12px; margin-top: 4px; font-size: 12px;">
                                <span style="color: #059669;">Pass: ${run.passed}</span>
                                <span style="color: #d97706;">Warn: ${run.warned}</span>
                                <span style="color: #dc2626;">Fail: ${run.failed}</span>
                                <span style="color: #6b7280;">Drift: ${run.avg_drift_score ? run.avg_drift_score.toFixed(3) : 'N/A'}</span>
                            </div>
                        </div>
                    `;

                    // Show failed/warned results
                    if (data.latest_results) {
                        const issues = data.latest_results.filter(r => r.status !== 'pass');
                        if (issues.length > 0) {
                            html += issues.slice(0, 5).map(r => {
                                const statusColor = r.status === 'fail' ? '#dc2626' : '#d97706';
                                return `<div style="padding: 4px 6px; font-size: 12px; border-left: 2px solid ${statusColor}; margin-bottom: 4px;">
                                    <span style="color: ${statusColor}; font-weight: 600;">[${r.status.toUpperCase()}]</span>
                                    ${escapeHtml((r.question || '').substring(0, 60))}
                                    <span style="color: #9ca3af;"> drift: ${r.drift_score ? r.drift_score.toFixed(3) : 'N/A'}</span>
                                </div>`;
                            }).join('');
                        }
                    }
                } else {
                    html += '<p style="color: #6b7280; font-size: 13px;">No regression runs yet. Add tests and run the suite.</p>';
                }

                el.innerHTML = html;
            } catch (error) { console.error('Error loading regression dashboard:', error); }
        }

        async function runRegressionSuite() {
            try {
                const response = await fetch('/api/intelligence/regression-run', { method: 'POST' });
                const data = await response.json();
                if (data.error) { alert(data.error); return; }
                alert(`Regression suite complete: ${data.passed} passed, ${data.warned} warned, ${data.failed} failed`);
                loadRegressionDashboard();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function addRegressionTest() {
            const question = document.getElementById('regTestQuestion').value.trim();
            const expected = document.getElementById('regTestExpected').value.trim();
            const criteria = document.getElementById('regTestCriteria').value.trim();

            if (!question || !expected) { alert('Question and expected answer are required.'); return; }

            try {
                const response = await fetch('/api/intelligence/regression-tests', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ question, expected_answer: expected, criteria: criteria || null })
                });
                const data = await response.json();
                if (data.success) {
                    document.getElementById('regTestQuestion').value = '';
                    document.getElementById('regTestExpected').value = '';
                    document.getElementById('regTestCriteria').value = '';
                    loadRegressionDashboard();
                    loadIntelligenceOverview();
                    alert('Regression test added!');
                }
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadABTests() {
            try {
                const response = await fetch('/api/intelligence/ab-tests');
                const data = await response.json();
                const el = document.getElementById('abTestsList');

                if (!data || data.length === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No active A/B tests. Create answer versions and tests via the API to start experimenting.</p>';
                    return;
                }

                el.innerHTML = data.map(test => `
                    <div style="padding: 8px; border: 1px solid #e5e7eb; border-radius: 6px; margin-bottom: 6px; font-size: 13px;">
                        <div style="font-weight: 600;">${escapeHtml(test.name)}</div>
                        <div style="color: #6b7280; font-size: 12px;">Pattern: "${escapeHtml(test.pattern)}" | Impressions: ${test.total_impressions}</div>
                        <button onclick="analyzeABTest(${test.id})" style="margin-top: 4px; font-size: 11px; padding: 2px 8px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; cursor: pointer; color: #2563eb;">Analyze Results</button>
                    </div>
                `).join('');
            } catch (error) { console.error('Error loading A/B tests:', error); }
        }

        async function analyzeABTest(testId) {
            try {
                const response = await fetch(`/api/intelligence/ab-tests/${testId}/analyze`);
                const data = await response.json();
                let msg = `A/B Test: ${data.name}\nStatus: ${data.status}\nImpressions: ${data.total_impressions}\n\n`;
                for (const [vid, stats] of Object.entries(data.versions || {})) {
                    msg += `Version ${vid}: ${stats.total} rated, ${stats.positive_rate * 100}% positive, Wilson: [${stats.wilson_lower}, ${stats.wilson_upper}]\n`;
                }
                if (data.significant) { msg += `\nWinner: Version ${data.winner} (statistically significant)`; }
                else { msg += '\nNo statistically significant winner yet.'; }
                alert(msg);
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadSatisfactionStats() {
            try {
                const response = await fetch('/api/intelligence/satisfaction/accuracy');
                const data = await response.json();
                const el = document.getElementById('satisfactionStats');

                if (!data || data.total === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No prediction data yet. The model trains automatically from user feedback.</p>';
                    return;
                }

                el.innerHTML = `
                    <div style="display: flex; gap: 12px; margin-bottom: 8px;">
                        <div style="padding: 8px 12px; background: #f3f4f6; border-radius: 6px; font-size: 12px;">
                            Accuracy: <strong style="color: ${data.accuracy >= 0.7 ? '#059669' : '#d97706'};">${(data.accuracy * 100).toFixed(1)}%</strong>
                        </div>
                        <div style="padding: 8px 12px; background: #f3f4f6; border-radius: 6px; font-size: 12px;">
                            Predictions: <strong>${data.total}</strong> (${data.correct} correct)
                        </div>
                        <div style="padding: 8px 12px; background: #f3f4f6; border-radius: 6px; font-size: 12px;">
                            Model v<strong>${data.model_version || 0}</strong>
                        </div>
                    </div>
                `;
            } catch (error) { console.error('Error loading satisfaction stats:', error); }
        }

        async function trainSatisfactionModel() {
            try {
                const response = await fetch('/api/intelligence/satisfaction/train', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    alert(`Model trained!\nAccuracy: ${(data.accuracy * 100).toFixed(1)}%\nSamples: ${data.samples}\nVersion: ${data.version}`);
                    loadSatisfactionStats();
                } else {
                    alert(data.reason || 'Training failed');
                }
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadIntelEvents() {
            try {
                const response = await fetch('/api/intelligence/events?limit=30');
                const data = await response.json();
                const el = document.getElementById('intelEventLog');

                if (!data || data.length === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No intelligence events yet.</p>';
                    return;
                }

                const sevColors = { 'info': '#6b7280', 'warning': '#d97706', 'error': '#dc2626', 'critical': '#dc2626' };

                el.innerHTML = `
                    <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
                        <tr style="text-align: left; color: #9ca3af; border-bottom: 1px solid #e5e7eb;">
                            <th style="padding: 3px 6px;">Time</th>
                            <th style="padding: 3px 6px;">Subsystem</th>
                            <th style="padding: 3px 6px;">Event</th>
                            <th style="padding: 3px 6px;">Details</th>
                        </tr>
                        ${data.map(e => {
                            const time = e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '';
                            return `<tr style="border-bottom: 1px solid #f3f4f6; color: ${sevColors[e.severity] || '#6b7280'};">
                                <td style="padding: 3px 6px;">${time}</td>
                                <td style="padding: 3px 6px; font-weight: 600;">${escapeHtml(e.subsystem)}</td>
                                <td style="padding: 3px 6px;">${escapeHtml(e.event_type)}</td>
                                <td style="padding: 3px 6px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(e.details || '')}">${escapeHtml((e.details || '').substring(0, 80))}</td>
                            </tr>`;
                        }).join('')}
                    </table>
                `;
            } catch (error) { console.error('Error loading intel events:', error); }
        }

        // ============== ENTERPRISE INTELLIGENCE FUNCTIONS ==============

        async function loadPipelineMetrics() {
            try {
                const response = await fetch('/api/intelligence/pipeline-metrics?period=24h');
                const data = await response.json();
                const el = document.getElementById('pipelineMetrics');
                const lat = data.latency || {};
                const cost = data.cost || {};
                const tp = data.throughput || {};
                const steps = data.steps || {};

                el.innerHTML = `
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px;">
                        <div style="text-align: center; padding: 8px; background: #f0fdf4; border-radius: 6px;">
                            <div style="font-size: 18px; font-weight: 700; color: #059669;">${(lat.p50 || 0).toFixed(0)}ms</div>
                            <div style="font-size: 10px; color: #6b7280;">P50 Latency</div>
                        </div>
                        <div style="text-align: center; padding: 8px; background: #fffbeb; border-radius: 6px;">
                            <div style="font-size: 18px; font-weight: 700; color: #d97706;">${(lat.p95 || 0).toFixed(0)}ms</div>
                            <div style="font-size: 10px; color: #6b7280;">P95 Latency</div>
                        </div>
                        <div style="text-align: center; padding: 8px; background: #fef2f2; border-radius: 6px;">
                            <div style="font-size: 18px; font-weight: 700; color: #dc2626;">${(lat.p99 || 0).toFixed(0)}ms</div>
                            <div style="font-size: 10px; color: #6b7280;">P99 Latency</div>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: #4b5563; margin-bottom: 8px;">
                        <strong>24h Summary:</strong> ${lat.count || 0} requests | $${(cost.total_cost_usd || 0).toFixed(4)} total |
                        $${(cost.avg_cost_per_request || 0).toFixed(6)}/req | ${(tp.avg_requests_per_hour || 0).toFixed(1)} req/hr
                    </div>
                    ${steps.count > 0 ? `<div style="font-size: 11px; color: #6b7280;">
                        <strong>Avg step times:</strong> ${Object.entries(steps.steps || {}).map(([k,v]) =>
                            `${k}=${v.toFixed(0)}ms`).join(' | ')}
                    </div>` : ''}
                `;
            } catch (error) { document.getElementById('pipelineMetrics').innerHTML = '<p style="color: #6b7280; font-size: 13px;">No pipeline data yet.</p>'; }
        }

        async function loadExecutiveHealth() {
            try {
                const response = await fetch('/api/intelligence/executive/health');
                const data = await response.json();
                const el = document.getElementById('executiveHealth');
                const score = data.health_score || 0;
                const color = score >= 80 ? '#059669' : score >= 60 ? '#d97706' : '#dc2626';

                let html = `
                    <div style="text-align: center; margin-bottom: 12px;">
                        <div style="font-size: 48px; font-weight: 800; color: ${color};">${score.toFixed(0)}</div>
                        <div style="font-size: 14px; color: ${color}; font-weight: 600; text-transform: uppercase;">${data.status || 'unknown'}</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 11px;">
                `;
                for (const [key, comp] of Object.entries(data.components || {})) {
                    const cColor = comp.score >= 80 ? '#059669' : comp.score >= 60 ? '#d97706' : '#dc2626';
                    html += `<div style="padding: 4px 8px; border-left: 3px solid ${cColor}; background: #fafafa; border-radius: 4px;">
                        <div style="font-weight: 600; color: #374151;">${key.replace(/_/g, ' ')}: <span style="color: ${cColor};">${comp.score.toFixed(0)}</span></div>
                        <div style="color: #9ca3af; font-size: 10px;">${escapeHtml(comp.detail || '')}</div>
                    </div>`;
                }
                html += '</div>';
                el.innerHTML = html;
            } catch (error) { document.getElementById('executiveHealth').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Health data unavailable.</p>'; }
        }

        async function loadAnomalies() {
            try {
                const response = await fetch('/api/intelligence/anomalies?limit=20');
                const data = await response.json();
                const el = document.getElementById('anomalyList');
                const anomalies = data.anomalies || [];

                if (anomalies.length === 0) {
                    el.innerHTML = '<p style="color: #059669; font-size: 13px;">No anomalies detected. System is operating normally.</p>';
                    return;
                }

                const sevColors = { info: '#6b7280', warning: '#d97706', critical: '#dc2626' };
                el.innerHTML = anomalies.slice(0, 10).map(a => `
                    <div style="padding: 6px 8px; border-left: 3px solid ${sevColors[a.severity] || '#6b7280'}; margin-bottom: 4px; font-size: 12px; background: #fafafa; border-radius: 4px;">
                        <span style="font-weight: 600; color: ${sevColors[a.severity]};">[${(a.severity || '').toUpperCase()}]</span>
                        ${escapeHtml(a.message || '')}
                        <span style="color: #9ca3af; font-size: 10px; margin-left: 8px;">${a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</span>
                    </div>
                `).join('');
            } catch (error) { document.getElementById('anomalyList').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Anomaly data unavailable.</p>'; }
        }

        async function runAnomalyCheck() {
            try {
                const response = await fetch('/api/intelligence/anomalies/check', { method: 'POST' });
                const data = await response.json();
                alert(`Anomaly check complete: ${data.count || 0} anomalies detected.`);
                loadAnomalies();
                loadIntelligenceOverview();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadAlerts() {
            try {
                const [rulesRes, histRes] = await Promise.all([
                    fetch('/api/intelligence/alert-rules'),
                    fetch('/api/intelligence/alerts?limit=20')
                ]);
                const rules = (await rulesRes.json()).rules || [];
                const alerts = (await histRes.json()).alerts || [];

                const rulesEl = document.getElementById('alertRulesList');
                rulesEl.innerHTML = rules.length === 0
                    ? '<p style="color: #6b7280; font-size: 13px;">No alert rules configured.</p>'
                    : `<div style="font-size: 12px;">${rules.map(r => `
                        <div style="padding: 4px 8px; border: 1px solid ${r.enabled ? '#e5e7eb' : '#fecaca'}; border-radius: 4px; margin-bottom: 3px; display: flex; justify-content: space-between; align-items: center;">
                            <span><strong>${escapeHtml(r.name)}</strong>: ${escapeHtml(r.metric)} ${r.condition} ${r.threshold}
                            ${r.fire_count > 0 ? `<span style="color: #d97706;">(fired ${r.fire_count}x)</span>` : ''}</span>
                            <span style="color: ${r.enabled ? '#059669' : '#dc2626'}; font-size: 10px;">${r.enabled ? 'ON' : 'OFF'}</span>
                        </div>
                    `).join('')}</div>`;

                const histEl = document.getElementById('alertHistory');
                histEl.innerHTML = alerts.length === 0
                    ? '<p style="color: #6b7280; font-size: 12px;">No alerts fired yet.</p>'
                    : alerts.slice(0, 10).map(a => `
                        <div style="padding: 3px 6px; font-size: 11px; border-bottom: 1px solid #f3f4f6;">
                            <span style="color: #d97706; font-weight: 600;">${escapeHtml(a.rule_name || '')}</span>:
                            ${escapeHtml((a.message || '').substring(0, 80))}
                            <span style="color: #9ca3af; margin-left: 4px;">${a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : ''}</span>
                        </div>
                    `).join('');
            } catch (error) { console.error('Error loading alerts:', error); }
        }

        async function loadCircuitBreakers() {
            try {
                const response = await fetch('/api/intelligence/circuit-breakers');
                const data = await response.json();
                const el = document.getElementById('circuitBreakerList');
                const breakers = data.breakers || [];

                if (breakers.length === 0) {
                    el.innerHTML = '<p style="color: #059669; font-size: 13px;">No circuit breakers tripped. All sources operating normally.</p>';
                    return;
                }

                el.innerHTML = breakers.map(b => {
                    const stateColor = b.state === 'open' ? '#dc2626' : '#059669';
                    return `<div style="padding: 6px 8px; border-left: 3px solid ${stateColor}; margin-bottom: 4px; font-size: 12px; background: #fafafa; border-radius: 4px;">
                        <strong>${escapeHtml(b.source_id)}</strong>
                        <span style="color: ${stateColor}; font-weight: 600; margin-left: 8px;">${b.state.toUpperCase()}</span>
                        <span style="color: #6b7280; margin-left: 8px;">Failures: ${b.failure_count} | Trips: ${b.total_trips}</span>
                        ${b.recovery_at ? `<span style="color: #9ca3af; margin-left: 8px; font-size: 10px;">Recovery: ${new Date(b.recovery_at).toLocaleTimeString()}</span>` : ''}
                    </div>`;
                }).join('');
            } catch (error) { document.getElementById('circuitBreakerList').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Circuit breaker data unavailable.</p>'; }
        }

        async function loadPromptVersions() {
            try {
                const response = await fetch('/api/intelligence/prompt-versions');
                const data = await response.json();
                const el = document.getElementById('promptVersionList');
                const versions = data.versions || [];

                if (versions.length === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No prompt versions tracked yet. Prompt versioning activates when you create your first version.</p>';
                    return;
                }

                el.innerHTML = versions.map(v => `
                    <div style="padding: 6px 8px; border: 1px solid ${v.is_active ? '#059669' : '#e5e7eb'}; border-radius: 4px; margin-bottom: 4px; font-size: 12px; background: ${v.is_active ? '#f0fdf4' : '#fff'};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span><strong>v${v.version}</strong> ${v.is_active ? '<span style="color: #059669; font-weight: 700;">[ACTIVE]</span>' : ''}
                            ${escapeHtml(v.description || '')}</span>
                            <span style="color: #6b7280; font-size: 10px;">${v.total_queries} queries | conf: ${v.avg_confidence ? v.avg_confidence.toFixed(1) : 'N/A'}</span>
                        </div>
                        ${!v.is_active ? `<button onclick="activatePromptVersion(${v.id})" style="margin-top: 4px; font-size: 10px; padding: 2px 8px; background: #1a4d2e; color: white; border: none; border-radius: 4px; cursor: pointer;">Activate</button>` : ''}
                    </div>
                `).join('');
            } catch (error) { document.getElementById('promptVersionList').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Prompt version data unavailable.</p>'; }
        }

        async function activatePromptVersion(id) {
            if (!confirm('Activate this prompt version? This will deactivate the current active version.')) return;
            try {
                await fetch(`/api/intelligence/prompt-versions/${id}/activate`, { method: 'POST' });
                loadPromptVersions();
                loadIntelligenceOverview();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadKnowledgeGaps() {
            try {
                const response = await fetch('/api/intelligence/knowledge-gaps');
                const data = await response.json();
                const el = document.getElementById('knowledgeGapList');
                const gaps = data.gaps || [];

                if (gaps.length === 0) {
                    el.innerHTML = '<p style="color: #059669; font-size: 13px;">No knowledge gaps detected. Content coverage looks good.</p>';
                    return;
                }

                const sevColors = { critical: '#dc2626', high: '#dc2626', medium: '#d97706', low: '#6b7280' };
                el.innerHTML = gaps.slice(0, 10).map(g => `
                    <div style="padding: 6px 8px; border-left: 3px solid ${sevColors[g.severity] || '#6b7280'}; margin-bottom: 4px; font-size: 12px; background: #fafafa; border-radius: 4px;">
                        <div><strong>${escapeHtml(g.topic || 'Unknown')}</strong>
                        <span style="color: ${sevColors[g.severity]}; font-weight: 600; margin-left: 8px;">${(g.severity || '').toUpperCase()}</span>
                        <span style="color: #6b7280; margin-left: 8px;">${g.gap_type} | ${g.question_count} questions</span></div>
                        <div style="color: #4b5563; font-size: 11px; margin-top: 2px;">${escapeHtml(g.recommended_action || '')}</div>
                    </div>
                `).join('');
            } catch (error) { document.getElementById('knowledgeGapList').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Knowledge gap data unavailable.</p>'; }
        }

        async function detectKnowledgeGaps() {
            try {
                const response = await fetch('/api/intelligence/knowledge-gaps/detect', { method: 'POST' });
                const data = await response.json();
                alert(`Gap detection complete: ${data.count || 0} gaps found.`);
                loadKnowledgeGaps();
                loadIntelligenceOverview();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadConversationMetrics() {
            try {
                const response = await fetch('/api/intelligence/conversations');
                const data = await response.json();
                const el = document.getElementById('conversationMetrics');

                if (data.error || data.total_conversations === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No conversation data yet. Run analysis to populate.</p>';
                    return;
                }

                const rb = data.resolution_breakdown || {};
                el.innerHTML = `
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px; font-size: 12px;">
                        <div style="padding: 6px; background: #f0fdf4; border-radius: 4px; text-align: center;">
                            <div style="font-size: 20px; font-weight: 700; color: #059669;">${data.total_conversations}</div>
                            <div style="font-size: 10px; color: #6b7280;">Total Conversations</div>
                        </div>
                        <div style="padding: 6px; background: #eff6ff; border-radius: 4px; text-align: center;">
                            <div style="font-size: 20px; font-weight: 700; color: #2563eb;">${(data.avg_turns || 0).toFixed(1)}</div>
                            <div style="font-size: 10px; color: #6b7280;">Avg Turns</div>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: #4b5563;">
                        <strong>Resolution:</strong> Resolved: ${rb.resolved || 0} | Single-turn: ${rb.single_turn || 0} |
                        Extended: ${rb.extended || 0} | <span style="color: #dc2626;">Frustrated: ${rb.frustrated || 0}</span>
                    </div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">
                        Frustration: ${(data.avg_frustration || 0).toFixed(3)} | Topic drift: ${(data.avg_topic_drift || 0).toFixed(3)}
                    </div>
                `;
            } catch (error) { document.getElementById('conversationMetrics').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Conversation data unavailable.</p>'; }
        }

        async function analyzeConversations() {
            try {
                const response = await fetch('/api/intelligence/conversations/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ days: 7 })
                });
                await response.json();
                alert('Conversation analysis complete.');
                loadConversationMetrics();
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function trainGradientBoosted() {
            try {
                document.getElementById('gradientBoostedPanel').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
                const response = await fetch('/api/intelligence/gradient-boosted/train', { method: 'POST' });
                const data = await response.json();

                const el = document.getElementById('gradientBoostedPanel');
                if (data.status === 'trained') {
                    el.innerHTML = `
                        <div style="font-size: 13px; color: #059669; font-weight: 600; margin-bottom: 8px;">Model trained successfully</div>
                        <div style="font-size: 12px; color: #4b5563;">
                            Accuracy: <strong>${(data.accuracy * 100).toFixed(1)}%</strong> |
                            Samples: ${data.samples} | Trees: ${data.trees}
                        </div>
                        ${data.feature_importance ? `<div style="margin-top: 8px; font-size: 11px;">
                            <strong>Top features:</strong>
                            ${Object.entries(data.feature_importance)
                                .sort((a,b) => b[1] - a[1])
                                .slice(0, 5)
                                .map(([k,v]) => `${k}: ${(v*100).toFixed(1)}%`)
                                .join(' | ')}
                        </div>` : ''}
                    `;
                } else {
                    el.innerHTML = `<p style="color: #d97706; font-size: 13px;">${data.status}: ${data.message || `${data.count || 0} samples (need 50+)`}</p>`;
                }
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadFeatureImportance() {
            try {
                const response = await fetch('/api/intelligence/gradient-boosted/importance');
                const data = await response.json();
                const el = document.getElementById('gradientBoostedPanel');

                if (data.status === 'no_model') {
                    el.innerHTML = '<p style="color: #d97706; font-size: 13px;">No model trained yet. Click "Train Model" first.</p>';
                    return;
                }

                const ranked = data.ranked || [];
                el.innerHTML = `
                    <div style="font-size: 12px; color: #4b5563; margin-bottom: 8px;">
                        Accuracy: <strong>${data.accuracy ? (data.accuracy * 100).toFixed(1) + '%' : 'N/A'}</strong> |
                        Trees: ${data.trees || 0} | Trained: ${data.trained_at ? new Date(data.trained_at).toLocaleString() : 'N/A'}
                    </div>
                    ${ranked.slice(0, 10).map(f => {
                        const w = Math.max(5, f.importance * 100 * 5);
                        return `<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px; font-size: 11px;">
                            <span style="width: 130px; color: #4b5563;">${f.feature}</span>
                            <div style="height: 8px; width: ${w}px; background: #1a4d2e; border-radius: 4px;"></div>
                            <span style="color: #6b7280;">${(f.importance * 100).toFixed(1)}%</span>
                        </div>`;
                    }).join('')}
                `;
            } catch (error) { alert('Error: ' + error.message); }
        }

        async function loadROI() {
            try {
                const response = await fetch('/api/intelligence/executive/roi');
                const data = await response.json();
                const el = document.getElementById('roiPanel');

                if (data.error) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">ROI data unavailable.</p>';
                    return;
                }

                const all = data.all_time || {};
                const month = data.last_30_days || {};
                el.innerHTML = `
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 12px;">
                        <div style="padding: 12px; background: #f0fdf4; border-radius: 8px;">
                            <div style="font-weight: 700; color: #1a4d2e; margin-bottom: 6px;">All Time</div>
                            <div>Queries: <strong>${all.queries || 0}</strong></div>
                            <div>AI Cost: <strong>$${(all.cost_usd || 0).toFixed(4)}</strong></div>
                            <div>Est. Hours Saved: <strong>${(all.est_hours_saved || 0).toFixed(1)}</strong></div>
                            <div>Est. Cost Saved: <strong>$${(all.est_cost_saved || 0).toFixed(2)}</strong></div>
                            <div>Cost/Query: <strong>$${(all.cost_per_query || 0).toFixed(6)}</strong></div>
                        </div>
                        <div style="padding: 12px; background: #eff6ff; border-radius: 8px;">
                            <div style="font-weight: 700; color: #2563eb; margin-bottom: 6px;">Last 30 Days</div>
                            <div>Queries: <strong>${month.queries || 0}</strong></div>
                            <div>AI Cost: <strong>$${(month.cost_usd || 0).toFixed(4)}</strong></div>
                            <div>Est. Hours Saved: <strong>${(month.est_hours_saved || 0).toFixed(1)}</strong></div>
                            <div>Est. Cost Saved: <strong>$${(month.est_cost_saved || 0).toFixed(2)}</strong></div>
                            <div>Cost/Query: <strong>$${(month.cost_per_query || 0).toFixed(6)}</strong></div>
                        </div>
                    </div>
                `;
            } catch (error) { document.getElementById('roiPanel').innerHTML = '<p style="color: #6b7280; font-size: 13px;">ROI data unavailable.</p>'; }
        }

        // ── Anthropic-Grade Panel Functions ──

        async function loadFeatureFlags() {
            try {
                const response = await fetch('/api/intelligence/feature-flags');
                const flags = await response.json();
                const el = document.getElementById('featureFlagsPanel');

                if (!flags || flags.length === 0) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">No feature flags configured.</p>';
                    return;
                }

                let html = '<div style="font-size: 12px;">';
                flags.forEach(f => {
                    const color = f.enabled ? '#059669' : '#dc2626';
                    const label = f.enabled ? 'ON' : 'OFF';
                    html += `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #f3f4f6;">
                            <div>
                                <strong>${f.flag_name}</strong>
                                <span style="color: #6b7280; margin-left: 8px;">${f.description || ''}</span>
                            </div>
                            <button onclick="toggleFlag('${f.flag_name}', ${!f.enabled})"
                                style="background: ${color}; color: white; border: none; padding: 2px 10px; border-radius: 4px; cursor: pointer; font-size: 11px;">
                                ${label}
                            </button>
                        </div>`;
                });
                html += '</div>';
                el.innerHTML = html;
            } catch (error) { document.getElementById('featureFlagsPanel').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Feature flags unavailable.</p>'; }
        }

        async function toggleFlag(flagName, enabled) {
            try {
                await fetch('/api/intelligence/feature-flags', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({flag_name: flagName, enabled: enabled})
                });
                loadFeatureFlags();
            } catch (error) { console.error('Error toggling flag:', error); }
        }

        async function loadCostBudget() {
            try {
                const response = await fetch('/api/intelligence/cost-budget/status');
                const data = await response.json();
                const el = document.getElementById('costBudgetPanel');

                const dailyPct = data.daily_pct || 0;
                const monthlyPct = data.monthly_pct || 0;
                const dailyColor = dailyPct >= 100 ? '#dc2626' : dailyPct >= 80 ? '#d97706' : '#059669';
                const monthlyColor = monthlyPct >= 100 ? '#dc2626' : monthlyPct >= 80 ? '#d97706' : '#059669';

                el.innerHTML = `
                    <div style="font-size: 12px; padding: 8px 0;">
                        <div style="margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span>Daily: $${(data.daily_spend || 0).toFixed(4)} / $${(data.daily_budget || 10).toFixed(2)}</span>
                                <strong style="color: ${dailyColor};">${dailyPct.toFixed(1)}%</strong>
                            </div>
                            <div style="background: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden;">
                                <div style="background: ${dailyColor}; width: ${Math.min(100, dailyPct)}%; height: 100%; border-radius: 4px;"></div>
                            </div>
                        </div>
                        <div>
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span>Monthly: $${(data.monthly_spend || 0).toFixed(4)} / $${(data.monthly_budget || 200).toFixed(2)}</span>
                                <strong style="color: ${monthlyColor};">${monthlyPct.toFixed(1)}%</strong>
                            </div>
                            <div style="background: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden;">
                                <div style="background: ${monthlyColor}; width: ${Math.min(100, monthlyPct)}%; height: 100%; border-radius: 4px;"></div>
                            </div>
                        </div>
                        <div style="margin-top: 8px; color: #6b7280;">
                            Action: <strong>${data.action || 'none'}</strong>
                        </div>
                    </div>
                `;
            } catch (error) { document.getElementById('costBudgetPanel').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Budget data unavailable.</p>'; }
        }

        async function loadDataRetention() {
            try {
                const response = await fetch('/api/intelligence/data-retention/status');
                const data = await response.json();
                const el = document.getElementById('dataRetentionPanel');

                if (data.error) {
                    el.innerHTML = '<p style="color: #6b7280; font-size: 13px;">Retention data unavailable.</p>';
                    return;
                }

                let html = '<div style="font-size: 11px; max-height: 250px; overflow-y: auto;">';
                html += '<table style="width: 100%; border-collapse: collapse;"><tr style="background: #f3f4f6;"><th style="padding: 4px; text-align: left;">Table</th><th style="padding: 4px; text-align: right;">Rows</th><th style="padding: 4px; text-align: right;">TTL (days)</th></tr>';
                const tables = data.tables || {};
                Object.entries(tables).sort((a, b) => (b[1].row_count || 0) - (a[1].row_count || 0)).forEach(([name, info]) => {
                    const ttl = info.ttl_days === 0 ? 'Never' : info.ttl_days;
                    html += `<tr style="border-bottom: 1px solid #f3f4f6;"><td style="padding: 3px 4px;">${name}</td><td style="padding: 3px 4px; text-align: right;">${info.row_count}</td><td style="padding: 3px 4px; text-align: right;">${ttl}</td></tr>`;
                });
                html += '</table></div>';

                if (data.last_cleanups && data.last_cleanups.length > 0) {
                    html += '<div style="margin-top: 8px; font-size: 11px; color: #6b7280;">Last cleanup: ' + data.last_cleanups[0].timestamp + '</div>';
                }

                el.innerHTML = html;
            } catch (error) { document.getElementById('dataRetentionPanel').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Retention data unavailable.</p>'; }
        }

        async function runDataRetention() {
            try {
                const response = await fetch('/api/intelligence/data-retention/run', {method: 'POST'});
                const data = await response.json();
                alert('Cleanup complete: ' + (data.total_deleted || 0) + ' rows deleted');
                loadDataRetention();
            } catch (error) { alert('Cleanup failed: ' + error.message); }
        }

        async function loadTrainingStatus() {
            try {
                const response = await fetch('/api/intelligence/training/status');
                const data = await response.json();
                const el = document.getElementById('trainingStatusPanel');

                const readyColor = data.ready ? '#059669' : '#6b7280';
                const readyLabel = data.ready ? 'READY' : 'Not Ready';

                let html = `
                    <div style="font-size: 12px; padding: 8px 0;">
                        <div style="text-align: center; margin-bottom: 12px;">
                            <div style="font-size: 24px; font-weight: 700; color: ${readyColor};">${readyLabel}</div>
                        </div>`;

                if (data.reasons && data.reasons.length > 0) {
                    html += '<div style="margin-bottom: 8px;"><strong>Reasons:</strong><ul style="margin: 4px 0; padding-left: 16px;">';
                    data.reasons.forEach(r => { html += '<li style="color: #d97706;">' + r + '</li>'; });
                    html += '</ul></div>';
                }

                const metrics = data.metrics || {};
                if (Object.keys(metrics).length > 0) {
                    html += '<div style="font-size: 11px; color: #6b7280;">';
                    Object.entries(metrics).forEach(([k, v]) => {
                        html += k.replace(/_/g, ' ') + ': <strong>' + v + '</strong><br>';
                    });
                    html += '</div>';
                }

                html += '</div>';
                el.innerHTML = html;
            } catch (error) { document.getElementById('trainingStatusPanel').innerHTML = '<p style="color: #6b7280; font-size: 13px;">Training status unavailable.</p>'; }
        }

        // =====================================================================
        // PROMOTE TO GOLDEN ANSWER
        // =====================================================================

        async function promoteToGolden() {
            if (modIndex >= modQueue.length) return;
            const item = modQueue[modIndex];
            const category = prompt('Category for this golden answer (optional):');
            if (category === null) return; // user cancelled

            try {
                const response = await fetch('/admin/promote-to-golden', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: item.question,
                        answer: item.ai_answer,
                        category: category || null
                    })
                });
                const result = await response.json();
                if (result.success) {
                    alert('Promoted to golden answer!');
                } else {
                    alert('Error: ' + (result.error || 'Unknown'));
                }
            } catch (error) {
                alert('Error promoting: ' + error.message);
            }
        }

        // =====================================================================
        // ANALYTICS CHARTS (pure canvas, no external libs)
        // =====================================================================

        // Polyfill roundRect for older browsers
        if (!CanvasRenderingContext2D.prototype.roundRect) {
            CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
                const radii = Array.isArray(r) ? r : [r, r, r, r];
                this.moveTo(x + radii[0], y);
                this.lineTo(x + w - radii[1], y);
                this.quadraticCurveTo(x + w, y, x + w, y + radii[1]);
                this.lineTo(x + w, y + h - radii[2]);
                this.quadraticCurveTo(x + w, y + h, x + w - radii[2], y + h);
                this.lineTo(x + radii[3], y + h);
                this.quadraticCurveTo(x, y + h, x, y + h - radii[3]);
                this.lineTo(x, y + radii[0]);
                this.quadraticCurveTo(x, y, x + radii[0], y);
                this.closePath();
            };
        }

        function drawBarChart(canvasId, labels, data, color, yLabel) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            ctx.scale(dpr, dpr);
            const W = rect.width, H = rect.height;
            const pad = { top: 20, right: 16, bottom: 36, left: 40 };
            const chartW = W - pad.left - pad.right;
            const chartH = H - pad.top - pad.bottom;

            ctx.clearRect(0, 0, W, H);
            if (data.length === 0) {
                ctx.fillStyle = '#9ca3af';
                ctx.font = '13px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('No data yet', W / 2, H / 2);
                return;
            }

            const max = Math.max(...data, 1);
            const barW = Math.min(chartW / data.length * 0.7, 32);
            const gap = chartW / data.length;

            // Y axis gridlines
            ctx.strokeStyle = '#e9ecef';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const y = pad.top + chartH - (chartH * i / 4);
                ctx.beginPath();
                ctx.moveTo(pad.left, y);
                ctx.lineTo(W - pad.right, y);
                ctx.stroke();
                ctx.fillStyle = '#9ca3af';
                ctx.font = '10px -apple-system, sans-serif';
                ctx.textAlign = 'right';
                ctx.fillText(Math.round(max * i / 4), pad.left - 6, y + 3);
            }

            // Bars
            data.forEach((val, i) => {
                const barH = (val / max) * chartH;
                const x = pad.left + i * gap + (gap - barW) / 2;
                const y = pad.top + chartH - barH;

                const grad = ctx.createLinearGradient(x, y, x, y + barH);
                grad.addColorStop(0, color);
                grad.addColorStop(1, color + '99');
                ctx.fillStyle = grad;
                ctx.beginPath();
                ctx.roundRect(x, y, barW, barH, [3, 3, 0, 0]);
                ctx.fill();
            });

            // X labels
            ctx.fillStyle = '#6c757d';
            ctx.font = '10px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            labels.forEach((label, i) => {
                const x = pad.left + i * gap + gap / 2;
                ctx.fillText(label, x, H - 8);
            });
        }

        function drawLineChart(canvasId, labels, data, color, yLabel, yMax) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            ctx.scale(dpr, dpr);
            const W = rect.width, H = rect.height;
            const pad = { top: 20, right: 16, bottom: 36, left: 40 };
            const chartW = W - pad.left - pad.right;
            const chartH = H - pad.top - pad.bottom;

            ctx.clearRect(0, 0, W, H);
            if (data.length === 0) {
                ctx.fillStyle = '#9ca3af';
                ctx.font = '13px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('No data yet', W / 2, H / 2);
                return;
            }

            const max = yMax || Math.max(...data, 1);
            const gap = data.length > 1 ? chartW / (data.length - 1) : chartW;

            // Y gridlines
            ctx.strokeStyle = '#e9ecef';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const y = pad.top + chartH - (chartH * i / 4);
                ctx.beginPath();
                ctx.moveTo(pad.left, y);
                ctx.lineTo(W - pad.right, y);
                ctx.stroke();
                ctx.fillStyle = '#9ca3af';
                ctx.font = '10px -apple-system, sans-serif';
                ctx.textAlign = 'right';
                ctx.fillText(Math.round(max * i / 4) + (yMax === 100 ? '%' : ''), pad.left - 6, y + 3);
            }

            // Area fill
            ctx.beginPath();
            data.forEach((val, i) => {
                const x = pad.left + (data.length > 1 ? i * gap : chartW / 2);
                const y = pad.top + chartH - ((val || 0) / max) * chartH;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.lineTo(pad.left + (data.length > 1 ? (data.length - 1) * gap : chartW / 2), pad.top + chartH);
            ctx.lineTo(pad.left, pad.top + chartH);
            ctx.closePath();
            ctx.fillStyle = color + '18';
            ctx.fill();

            // Line
            ctx.beginPath();
            data.forEach((val, i) => {
                const x = pad.left + (data.length > 1 ? i * gap : chartW / 2);
                const y = pad.top + chartH - ((val || 0) / max) * chartH;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();

            // Dots
            data.forEach((val, i) => {
                const x = pad.left + (data.length > 1 ? i * gap : chartW / 2);
                const y = pad.top + chartH - ((val || 0) / max) * chartH;
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();
            });

            // X labels (show every few)
            ctx.fillStyle = '#6c757d';
            ctx.font = '10px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            const step = Math.max(1, Math.floor(labels.length / 7));
            labels.forEach((label, i) => {
                if (i % step === 0 || i === labels.length - 1) {
                    const x = pad.left + (data.length > 1 ? i * gap : chartW / 2);
                    ctx.fillText(label, x, H - 8);
                }
            });
        }

        function drawStackedBarChart(canvasId, labels, datasets) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            const rect = canvas.getBoundingClientRect();
            canvas.width = rect.width * dpr;
            canvas.height = rect.height * dpr;
            ctx.scale(dpr, dpr);
            const W = rect.width, H = rect.height;
            const pad = { top: 20, right: 16, bottom: 36, left: 40 };
            const chartW = W - pad.left - pad.right;
            const chartH = H - pad.top - pad.bottom;

            ctx.clearRect(0, 0, W, H);
            if (labels.length === 0) {
                ctx.fillStyle = '#9ca3af';
                ctx.font = '13px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('No data yet', W / 2, H / 2);
                return;
            }

            const totals = labels.map((_, i) => datasets.reduce((sum, ds) => sum + (ds.data[i] || 0), 0));
            const max = Math.max(...totals, 1);
            const barW = Math.min(chartW / labels.length * 0.7, 32);
            const gap = chartW / labels.length;

            // Y gridlines
            ctx.strokeStyle = '#e9ecef';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const y = pad.top + chartH - (chartH * i / 4);
                ctx.beginPath();
                ctx.moveTo(pad.left, y);
                ctx.lineTo(W - pad.right, y);
                ctx.stroke();
                ctx.fillStyle = '#9ca3af';
                ctx.font = '10px -apple-system, sans-serif';
                ctx.textAlign = 'right';
                ctx.fillText(Math.round(max * i / 4), pad.left - 6, y + 3);
            }

            // Stacked bars
            labels.forEach((_, i) => {
                let yOffset = 0;
                const x = pad.left + i * gap + (gap - barW) / 2;
                datasets.forEach(ds => {
                    const val = ds.data[i] || 0;
                    const barH = (val / max) * chartH;
                    const y = pad.top + chartH - yOffset - barH;
                    ctx.fillStyle = ds.color;
                    ctx.beginPath();
                    ctx.roundRect(x, y, barW, barH, yOffset === 0 ? [3, 3, 0, 0] : [0, 0, 0, 0]);
                    ctx.fill();
                    yOffset += barH;
                });
            });

            // X labels
            ctx.fillStyle = '#6c757d';
            ctx.font = '10px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            const step = Math.max(1, Math.floor(labels.length / 7));
            labels.forEach((label, i) => {
                if (i % step === 0 || i === labels.length - 1) {
                    const x = pad.left + i * gap + gap / 2;
                    ctx.fillText(label, x, H - 8);
                }
            });

            // Legend
            ctx.font = '11px -apple-system, sans-serif';
            let legendX = pad.left;
            datasets.forEach(ds => {
                ctx.fillStyle = ds.color;
                ctx.fillRect(legendX, 4, 10, 10);
                ctx.fillStyle = '#495057';
                ctx.textAlign = 'left';
                ctx.fillText(ds.label, legendX + 14, 13);
                legendX += ctx.measureText(ds.label).width + 28;
            });
        }

        function renderAnalyticsCharts(stats) {
            const dailyCounts = stats.daily_counts || [];
            const confTrend = stats.confidence_trend || [];
            const dailyRatings = stats.daily_ratings || {};

            // Volume chart
            const volLabels = dailyCounts.map(d => {
                const dt = new Date(d.date + 'T00:00:00');
                return (dt.getMonth() + 1) + '/' + dt.getDate();
            });
            const volData = dailyCounts.map(d => d.count);
            drawBarChart('volumeChart', volLabels, volData, '#1a4d2e', 'Queries');

            // Confidence trend
            const confLabels = confTrend.map(d => {
                const dt = new Date(d.date + 'T00:00:00');
                return (dt.getMonth() + 1) + '/' + dt.getDate();
            });
            const confData = confTrend.map(d => d.avg_confidence || 0);
            drawLineChart('confidenceChart', confLabels, confData, '#2563eb', 'Confidence %', 100);

            // Ratings stacked bar
            const ratingDays = Object.keys(dailyRatings).sort();
            const ratLabels = ratingDays.map(d => {
                const dt = new Date(d + 'T00:00:00');
                return (dt.getMonth() + 1) + '/' + dt.getDate();
            });
            drawStackedBarChart('ratingsChart', ratLabels, [
                { label: 'Positive', color: '#28a745', data: ratingDays.map(d => dailyRatings[d].positive || 0) },
                { label: 'Negative', color: '#dc3545', data: ratingDays.map(d => dailyRatings[d].negative || 0) },
                { label: 'Unrated', color: '#adb5bd', data: ratingDays.map(d => dailyRatings[d].unrated || 0) }
            ]);
        }

        // Initial load
        loadAllData();
        loadFineTuningStatus();
        loadSourceQuality();
        loadEvalHistory();
        loadKnowledgeStatus();
