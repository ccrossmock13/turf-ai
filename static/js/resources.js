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

        let allResources = [];
        let currentFilter = 'product labels';
        let currentPage = 1;
        const ITEMS_PER_PAGE = 24;
        let filteredCache = [];

        async function loadResources() {
            try {
                const response = await fetch('/api/resources');
                allResources = await response.json();
                filterResources();
            } catch (error) {
                console.error('Error loading resources:', error);
                document.getElementById('totalCount').textContent = 'Error loading resources';
            }
        }

        function getBadgeClass(category) {
            const lower = category.toLowerCase();
            if (lower.includes('label')) return 'badge-label';
            if (lower.includes('sheet')) return 'badge-sheet';
            if (lower.includes('program')) return 'badge-program';
            if (lower.includes('ntep')) return 'badge-ntep';
            return 'badge-label';
        }

        function getBrand(filename) {
            const lower = filename.toLowerCase();
            if (lower.includes('syngenta') || lower.includes('heritage') || lower.includes('primo') || lower.includes('daconil')) return 'Syngenta';
            if (lower.includes('basf') || lower.includes('lexicon') || lower.includes('xzemplar') || lower.includes('insignia')) return 'BASF';
            if (lower.includes('envu') || lower.includes('acclaim') || lower.includes('certainty') || lower.includes('monument')) return 'Envu';
            return '';
        }

        function cleanFilename(filename) {
            return filename.replace('.pdf', '').replace(/-/g, ' ').replace(/_/g, ' ').split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
        }

        function displayResources(resources) {
            filteredCache = resources;
            const grid = document.getElementById('resourceGrid');
            const noResults = document.getElementById('noResults');

            if (resources.length === 0) {
                grid.style.display = 'none';
                noResults.style.display = 'block';
                removePagination();
                return;
            }

            grid.style.display = 'grid';
            noResults.style.display = 'none';

            const totalPages = Math.ceil(resources.length / ITEMS_PER_PAGE);
            if (currentPage > totalPages) currentPage = totalPages;
            const start = (currentPage - 1) * ITEMS_PER_PAGE;
            const pageItems = resources.slice(start, start + ITEMS_PER_PAGE);

            grid.innerHTML = pageItems.map(resource => {
                const category = resource.category;
                const brand = getBrand(resource.filename);
                const displayName = cleanFilename(resource.filename);
                const badgeClass = getBadgeClass(category);

                return `
                    <div class="resource-card" onclick="window.open('${resource.url}', '_blank')">
                        <span class="resource-badge ${badgeClass}">${category}</span>
                        <div class="resource-name">${displayName}</div>
                        <div class="resource-meta">
                            <div class="resource-brand">${brand || 'Reference'}</div>
                            <div class="resource-icon">→</div>
                        </div>
                    </div>
                `;
            }).join('');

            document.getElementById('totalCount').innerHTML = `<strong>${resources.length}</strong> resources available`;
            renderPagination(totalPages);
        }

        function renderPagination(totalPages) {
            removePagination();
            if (totalPages <= 1) return;
            const grid = document.getElementById('resourceGrid');
            const pag = document.createElement('div');
            pag.id = 'pagination';
            pag.style.cssText = 'grid-column:1/-1;display:flex;justify-content:center;align-items:center;gap:12px;padding:16px 0;';
            pag.innerHTML = `
                <button onclick="changePage(-1)" ${currentPage <= 1 ? 'disabled' : ''}
                    style="padding:8px 16px;border:1px solid #e5e7eb;border-radius:6px;background:white;cursor:pointer;font-size:14px;">← Prev</button>
                <span style="font-size:14px;color:#6b7280;">Page ${currentPage} of ${totalPages}</span>
                <button onclick="changePage(1)" ${currentPage >= totalPages ? 'disabled' : ''}
                    style="padding:8px 16px;border:1px solid #e5e7eb;border-radius:6px;background:white;cursor:pointer;font-size:14px;">Next →</button>
            `;
            grid.appendChild(pag);
        }

        function removePagination() {
            const existing = document.getElementById('pagination');
            if (existing) existing.remove();
        }

        function changePage(delta) {
            currentPage += delta;
            displayResources(filteredCache);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function filterResources() {
            currentPage = 1;
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();

            let filtered = allResources.filter(resource => {
                const matchesSearch = resource.filename.toLowerCase().includes(searchTerm);
                const category = resource.category.toLowerCase();
                const matchesFilter = category === currentFilter;
                return matchesSearch && matchesFilter;
            });

            displayResources(filtered);
        }

        document.getElementById('searchInput').addEventListener('input', filterResources);

        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentFilter = this.dataset.filter;
                filterResources();
            });
        });

        loadResources();
