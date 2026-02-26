    // =========================================================================
    // Data
    // =========================================================================
    const states = [
        'Alabama','Alaska','Arizona','Arkansas','California','Colorado','Connecticut',
        'Delaware','Florida','Georgia','Hawaii','Idaho','Illinois','Indiana','Iowa',
        'Kansas','Kentucky','Louisiana','Maine','Maryland','Massachusetts','Michigan',
        'Minnesota','Mississippi','Missouri','Montana','Nebraska','Nevada','New Hampshire',
        'New Jersey','New Mexico','New York','North Carolina','North Dakota','Ohio',
        'Oklahoma','Oregon','Pennsylvania','Rhode Island','South Carolina','South Dakota',
        'Tennessee','Texas','Utah','Vermont','Virginia','Washington','West Virginia',
        'Wisconsin','Wyoming'
    ];

    const stateClimateZones = {
        'Alabama':'7b-8a','Alaska':'4a-7b','Arizona':'9a-10b','Arkansas':'7a-8a','California':'8a-10b',
        'Colorado':'5a-6b','Connecticut':'6a-6b','Delaware':'7a-7b','Florida':'9a-10b','Georgia':'7b-9a',
        'Hawaii':'10b-12a','Idaho':'5a-6b','Illinois':'5b-6b','Indiana':'5b-6b','Iowa':'5a-5b',
        'Kansas':'5b-6b','Kentucky':'6a-7a','Louisiana':'8a-9a','Maine':'4a-5b','Maryland':'6b-7b',
        'Massachusetts':'5b-6b','Michigan':'5a-6a','Minnesota':'3b-4b','Mississippi':'7b-8b',
        'Missouri':'5b-7a','Montana':'4a-5b','Nebraska':'4b-5b','Nevada':'6a-9b','New Hampshire':'4b-5b',
        'New Jersey':'6b-7a','New Mexico':'6a-8b','New York':'4b-7a','North Carolina':'7a-8a',
        'North Dakota':'3b-4b','Ohio':'5b-6b','Oklahoma':'6b-7b','Oregon':'6a-9b','Pennsylvania':'5b-7a',
        'Rhode Island':'6a-6b','South Carolina':'7b-8b','South Dakota':'4a-5a','Tennessee':'6b-7b',
        'Texas':'7a-9b','Utah':'5a-7b','Vermont':'4a-5a','Virginia':'6a-7b','Washington':'5b-8b',
        'West Virginia':'5b-6b','Wisconsin':'4a-5b','Wyoming':'4a-5b'
    };

    const allGrassTypes = [
        { value: 'bentgrass', label: 'Bentgrass' },
        { value: 'hybrid bermudagrass', label: 'Hybrid Bermudagrass' },
        { value: 'bermudagrass', label: 'Common Bermudagrass' },
        { value: 'poa annua', label: 'Poa annua' },
        { value: 'kentucky bluegrass', label: 'Kentucky Bluegrass' },
        { value: 'tall fescue', label: 'Tall Fescue' },
        { value: 'perennial ryegrass', label: 'Perennial Ryegrass' },
        { value: 'annual ryegrass', label: 'Annual Ryegrass' },
        { value: 'zoysiagrass', label: 'Zoysiagrass' },
        { value: 'paspalum', label: 'Paspalum' },
        { value: 'st. augustinegrass', label: 'St. Augustinegrass' },
        { value: 'centipedegrass', label: 'Centipedegrass' },
        { value: 'bahiagrass', label: 'Bahiagrass' },
        { value: 'fine fescue', label: 'Fine Fescue' },
        { value: 'buffalograss', label: 'Buffalograss' },
        { value: 'kikuyugrass', label: 'Kikuyugrass' },
        { value: 'bluegrass-ryegrass mix', label: 'Bluegrass/Ryegrass Mix' },
        { value: 'bluegrass-fescue mix', label: 'Bluegrass/Fescue Mix' },
        { value: 'fescue-ryegrass mix', label: 'Fescue/Ryegrass Mix' },
        { value: 'native mix', label: 'Native / Low-Input Mix' }
    ];
    const greensGrassTypes = ['bentgrass','hybrid bermudagrass','bermudagrass','poa annua','paspalum','zoysiagrass'];
    const fairwaysGrassTypes = [
        'hybrid bermudagrass','bermudagrass','bentgrass','kentucky bluegrass',
        'perennial ryegrass','zoysiagrass','tall fescue','paspalum','poa annua',
        'kikuyugrass','bluegrass-ryegrass mix','bluegrass-fescue mix','fine fescue'
    ];
    const roughGrassTypes = [
        'kentucky bluegrass','tall fescue','perennial ryegrass','hybrid bermudagrass',
        'bermudagrass','fine fescue','zoysiagrass','st. augustinegrass','bahiagrass',
        'buffalograss','kikuyugrass','bluegrass-ryegrass mix','bluegrass-fescue mix',
        'fescue-ryegrass mix','native mix'
    ];
    // Secondary/overseeded grass options for fairways and roughs
    const overseedGrassTypes = [
        'perennial ryegrass','annual ryegrass','tall fescue','kentucky bluegrass',
        'fine fescue','bluegrass-ryegrass mix','fescue-ryegrass mix'
    ];

    // =========================================================================
    // Initialization
    // =========================================================================
    function populateGrassSelect(selectId, filterList) {
        const sel = document.getElementById(selectId);
        const currentVal = sel.value;
        while (sel.options.length > 1) sel.remove(1);
        const grassList = filterList ? allGrassTypes.filter(g => filterList.includes(g.value)) : allGrassTypes;
        grassList.forEach(g => { const opt = document.createElement('option'); opt.value = g.value; opt.textContent = g.label; sel.appendChild(opt); });
        if (currentVal) sel.value = currentVal;
    }

    // Populate state dropdown
    const stateSelect = document.getElementById('state');
    states.forEach(s => { const opt = document.createElement('option'); opt.value = s; opt.textContent = s; stateSelect.appendChild(opt); });

    // Auto-fill climate zone when state changes
    stateSelect.addEventListener('change', function() {
        const zone = stateClimateZones[this.value];
        const czEl = document.getElementById('climate_zone');
        if (zone && !czEl.value) czEl.value = zone;
    });

    // Populate all grass dropdowns
    populateGrassSelect('primary_grass', null);
    populateGrassSelect('greens_grass', greensGrassTypes);
    populateGrassSelect('fairways_grass', fairwaysGrassTypes);
    populateGrassSelect('rough_grass', roughGrassTypes);
    populateGrassSelect('tees_grass', fairwaysGrassTypes);
    populateGrassSelect('fairways_secondary_grass', overseedGrassTypes);
    populateGrassSelect('rough_secondary_grass', overseedGrassTypes);

    // =========================================================================
    // Tabs
    // =========================================================================
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        });
    });

    // =========================================================================
    // Facility type toggle
    // =========================================================================
    function onFacilityTypeChange() {
        const isGolf = document.getElementById('turf_type').value === 'golf_course';
        document.getElementById('golf-grass-section').style.display = isGolf ? 'block' : 'none';
        document.getElementById('primary-grass-group').style.display = isGolf ? 'none' : 'block';
        document.getElementById('n-budget-golf').style.display = isGolf ? 'grid' : 'none';
        document.getElementById('n-budget-simple').style.display = isGolf ? 'none' : 'grid';
        updateCompleteness();
    }

    // =========================================================================
    // Completeness indicator
    // =========================================================================
    const coreFields = ['state', 'role', 'turf_type'];
    function getCoreGrassFields() {
        return document.getElementById('turf_type').value === 'golf_course' ? ['greens_grass'] : ['primary_grass'];
    }
    function fieldHasValue(id) { const el = document.getElementById(id); return el && el.value && el.value.trim() !== ''; }

    function updateCompleteness() {
        let score = 0, max = 0;
        // Core (required)
        [...coreFields, ...getCoreGrassFields()].forEach(f => { max += 30; if (fieldHasValue(f)) score += 30; });
        // Valuable
        [() => fieldHasValue('soil_type'), () => sprayers.length > 0].forEach(fn => { max += 10; if (fn()) score += 10; });
        // Check mowing
        max += 10;
        const isGolf = document.getElementById('turf_type').value === 'golf_course';
        if (isGolf ? fieldHasValue('mow_greens') : fieldHasValue('mow_primary')) score += 10;
        // Bonus
        ['green_speed_target', 'budget_tier'].forEach(f => { max += 5; if (fieldHasValue(f)) score += 5; });
        max += 5; if (document.querySelectorAll('.problem-cb:checked').length > 0) score += 5;

        const pct = Math.round((score / max) * 100);
        const bar = document.getElementById('completeness-bar');
        const label = document.getElementById('completeness-label');
        bar.style.width = pct + '%';
        bar.style.background = pct >= 100 ? '#16a34a' : pct >= 60 ? '#eab308' : '#ef4444';
        if (pct >= 90) {
            label.textContent = 'Excellent — AI answers are fully personalized';
        } else if (pct >= 60) {
            label.textContent = pct + '% — Good foundation. Add mowing, soil, or programs for better answers.';
        } else {
            const missing = [...coreFields, ...getCoreGrassFields()].filter(f => !fieldHasValue(f)).map(f => f.replace(/_/g,' '));
            label.textContent = pct + '% — Add: ' + (missing.length ? missing.join(', ') : 'more details');
        }
    }

    // Update completeness when key fields change (both change and input for real-time)
    ['state','role','turf_type','primary_grass','greens_grass','soil_type','green_speed_target','budget_tier','mow_greens','mow_primary'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', updateCompleteness);
            el.addEventListener('input', updateCompleteness);
        }
    });

    // =========================================================================
    // Profile save/load
    // =========================================================================
    const simpleFields = [
        'course_name', 'city', 'state', 'primary_grass', 'role', 'turf_type',
        'greens_grass', 'fairways_grass', 'rough_grass', 'tees_grass',
        'soil_type', 'irrigation_source', 'notes',
        'primary_grass_cultivar', 'greens_grass_cultivar', 'fairways_grass_cultivar',
        'rough_grass_cultivar', 'tees_grass_cultivar',
        'greens_acreage', 'fairways_acreage', 'rough_acreage', 'tees_acreage',
        'soil_ph', 'soil_om', 'water_ph', 'water_ec',
        'green_speed_target', 'budget_tier', 'climate_zone',
        'fairways_secondary_grass', 'rough_secondary_grass'
    ];

    // =========================================================================
    // Autosave
    // =========================================================================
    let autosaveTimer = null;
    let isDirty = false;

    function markDirty() {
        isDirty = true;
        if (autosaveTimer) clearTimeout(autosaveTimer);
        const indicator = document.getElementById('autosave-indicator');
        indicator.style.display = 'block';
        indicator.className = 'autosave-indicator saving';
        document.getElementById('autosave-text').textContent = 'Unsaved changes...';
        autosaveTimer = setTimeout(autoSave, 2000);
    }

    async function autoSave() {
        if (!isDirty) return;
        const indicator = document.getElementById('autosave-indicator');
        indicator.className = 'autosave-indicator saving';
        document.getElementById('autosave-text').textContent = 'Saving...';
        try {
            const resp = await fetch('/api/profile', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(buildProfileData())
            });
            if (resp.ok) {
                isDirty = false;
                indicator.className = 'autosave-indicator saved';
                document.getElementById('autosave-text').textContent = '\u2713 Saved';
                updateCompleteness();
                loadContextPreview();
                setTimeout(() => { if (!isDirty) indicator.style.display = 'none'; }, 3000);
            }
        } catch (e) {
            document.getElementById('autosave-text').textContent = 'Save failed';
        }
    }

    // Warn on unsaved changes
    window.addEventListener('beforeunload', function(e) {
        if (isDirty) { e.preventDefault(); e.returnValue = ''; }
    });

    // Attach autosave listeners to all form fields
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('input, select, textarea').forEach(el => {
            el.addEventListener('input', markDirty);
            el.addEventListener('change', markDirty);
        });
    });

    function buildProfileData() {
        const data = {};
        simpleFields.forEach(f => { const el = document.getElementById(f); if (el) data[f] = el.value || null; });

        // Pack secondary grasses into secondary_grasses JSON
        const secGrasses = {};
        if (data.fairways_secondary_grass) secGrasses.fairways = data.fairways_secondary_grass;
        if (data.rough_secondary_grass) secGrasses.rough = data.rough_secondary_grass;
        data.secondary_grasses = Object.keys(secGrasses).length ? JSON.stringify(secGrasses) : null;
        // Remove the individual keys (not DB columns)
        delete data.fairways_secondary_grass;
        delete data.rough_secondary_grass;

        // Mowing heights as JSON
        const isGolf = document.getElementById('turf_type').value === 'golf_course';
        if (isGolf) {
            data.mowing_heights = JSON.stringify({
                greens: document.getElementById('mow_greens').value || null,
                fairways: document.getElementById('mow_fairways').value || null,
                tees: document.getElementById('mow_tees').value || null,
                rough: document.getElementById('mow_rough').value || null
            });
        } else {
            const mh = document.getElementById('mow_primary').value;
            data.mowing_heights = mh ? JSON.stringify({primary: mh}) : null;
        }

        // N budget as JSON
        if (isGolf) {
            data.annual_n_budget = JSON.stringify({
                greens: document.getElementById('n_greens').value || null,
                fairways: document.getElementById('n_fairways').value || null,
                tees: document.getElementById('n_tees').value || null,
                rough: document.getElementById('n_rough').value || null
            });
        } else {
            const nb = document.getElementById('n_primary').value;
            data.annual_n_budget = nb ? JSON.stringify({primary: nb}) : null;
        }

        // Common problems
        const problems = [];
        document.querySelectorAll('.problem-cb:checked').forEach(cb => problems.push(cb.value));
        data.common_problems = JSON.stringify(problems);

        // Preferred products
        const prodText = (document.getElementById('preferred_products').value || '').trim();
        data.preferred_products = JSON.stringify(prodText ? prodText.split(',').map(s => s.trim()).filter(Boolean) : []);

        // Overseeding
        data.overseeding_program = JSON.stringify({
            grass: document.getElementById('overseed_grass').value || null,
            date: document.getElementById('overseed_date').value || null,
            rate: document.getElementById('overseed_rate').value || null
        });

        // Irrigation schedule
        data.irrigation_schedule = JSON.stringify({
            system_type: document.getElementById('irr_system_type').value || null,
            run_times: document.getElementById('irr_run_times').value || null,
            zones: document.getElementById('irr_zones').value || null
        });

        // Aerification program
        data.aerification_program = JSON.stringify({
            dates: document.getElementById('aer_dates').value || null,
            tine_type: document.getElementById('aer_tine_type').value || null,
            depth: document.getElementById('aer_depth').value || null,
            areas: document.getElementById('aer_areas').value || null
        });

        // Topdressing program
        data.topdressing_program = JSON.stringify({
            material: document.getElementById('td_material').value || null,
            rate: document.getElementById('td_rate').value || null,
            frequency: document.getElementById('td_frequency').value || null
        });

        // Bunker sand
        data.bunker_sand = JSON.stringify({
            type: document.getElementById('bunker_type').value || null,
            depth: document.getElementById('bunker_depth').value || null,
            drainage: document.getElementById('bunker_drainage').value || null
        });

        // PGR program
        data.pgr_program = JSON.stringify({
            product: document.getElementById('pgr_product').value || null,
            rate: document.getElementById('pgr_rate').value || null,
            interval: document.getElementById('pgr_interval').value || null,
            areas: document.getElementById('pgr_areas').value || null
        });

        // Wetting agent program
        data.wetting_agent_program = JSON.stringify({
            product: document.getElementById('wa_product').value || null,
            rate: document.getElementById('wa_rate').value || null,
            interval: document.getElementById('wa_interval').value || null
        });

        // Maintenance calendar
        const cal = {};
        ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].forEach(m => {
            const val = document.getElementById('cal_' + m).value.trim();
            if (val) cal[m] = val;
        });
        data.maintenance_calendar = Object.keys(cal).length ? JSON.stringify(cal) : null;

        return data;
    }

    async function loadProfile() {
        try {
            const resp = await fetch('/api/profile');
            if (!resp.ok) return;
            const data = await resp.json();

            // Simple fields
            simpleFields.forEach(f => { const el = document.getElementById(f); if (el && data[f]) el.value = data[f]; });

            // Secondary grasses (JSON object → individual selects)
            const secGrasses = data.secondary_grasses;
            if (secGrasses && typeof secGrasses === 'object') {
                if (secGrasses.fairways) document.getElementById('fairways_secondary_grass').value = secGrasses.fairways;
                if (secGrasses.rough) document.getElementById('rough_secondary_grass').value = secGrasses.rough;
            }

            // Mowing heights (JSON object)
            const mh = data.mowing_heights;
            if (mh && typeof mh === 'object') {
                if (mh.greens) document.getElementById('mow_greens').value = mh.greens;
                if (mh.fairways) document.getElementById('mow_fairways').value = mh.fairways;
                if (mh.tees) document.getElementById('mow_tees').value = mh.tees;
                if (mh.rough) document.getElementById('mow_rough').value = mh.rough;
                if (mh.primary) document.getElementById('mow_primary').value = mh.primary;
            }

            // N budget (JSON object)
            const nb = data.annual_n_budget;
            if (nb && typeof nb === 'object') {
                if (nb.greens) document.getElementById('n_greens').value = nb.greens;
                if (nb.fairways) document.getElementById('n_fairways').value = nb.fairways;
                if (nb.tees) document.getElementById('n_tees').value = nb.tees;
                if (nb.rough) document.getElementById('n_rough').value = nb.rough;
                if (nb.primary) document.getElementById('n_primary').value = nb.primary;
            }

            // Common problems (JSON array)
            const problems = data.common_problems;
            if (Array.isArray(problems)) {
                problems.forEach(p => {
                    const cb = document.querySelector(`.problem-cb[value="${p}"]`);
                    if (cb) cb.checked = true;
                });
            }

            // Preferred products (JSON array → comma string)
            const prods = data.preferred_products;
            if (Array.isArray(prods) && prods.length) {
                document.getElementById('preferred_products').value = prods.join(', ');
            }

            // Overseeding (JSON object)
            const os = data.overseeding_program;
            if (os && typeof os === 'object') {
                if (os.grass) document.getElementById('overseed_grass').value = os.grass;
                if (os.date) document.getElementById('overseed_date').value = os.date;
                if (os.rate) document.getElementById('overseed_rate').value = os.rate;
            }

            // Irrigation schedule
            const irr = data.irrigation_schedule;
            if (irr && typeof irr === 'object') {
                if (irr.system_type) document.getElementById('irr_system_type').value = irr.system_type;
                if (irr.run_times) document.getElementById('irr_run_times').value = irr.run_times;
                if (irr.zones) document.getElementById('irr_zones').value = irr.zones;
            }

            // Aerification program
            const aer = data.aerification_program;
            if (aer && typeof aer === 'object') {
                if (aer.dates) document.getElementById('aer_dates').value = aer.dates;
                if (aer.tine_type) document.getElementById('aer_tine_type').value = aer.tine_type;
                if (aer.depth) document.getElementById('aer_depth').value = aer.depth;
                if (aer.areas) document.getElementById('aer_areas').value = aer.areas;
            }

            // Topdressing program
            const td = data.topdressing_program;
            if (td && typeof td === 'object') {
                if (td.material) document.getElementById('td_material').value = td.material;
                if (td.rate) document.getElementById('td_rate').value = td.rate;
                if (td.frequency) document.getElementById('td_frequency').value = td.frequency;
            }

            // Bunker sand
            const bs = data.bunker_sand;
            if (bs && typeof bs === 'object') {
                if (bs.type) document.getElementById('bunker_type').value = bs.type;
                if (bs.depth) document.getElementById('bunker_depth').value = bs.depth;
                if (bs.drainage) document.getElementById('bunker_drainage').value = bs.drainage;
            }

            // PGR program
            const pgr = data.pgr_program;
            if (pgr && typeof pgr === 'object') {
                if (pgr.product) document.getElementById('pgr_product').value = pgr.product;
                if (pgr.rate) document.getElementById('pgr_rate').value = pgr.rate;
                if (pgr.interval) document.getElementById('pgr_interval').value = pgr.interval;
                if (pgr.areas) document.getElementById('pgr_areas').value = pgr.areas;
            }

            // Wetting agent
            const wa = data.wetting_agent_program;
            if (wa && typeof wa === 'object') {
                if (wa.product) document.getElementById('wa_product').value = wa.product;
                if (wa.rate) document.getElementById('wa_rate').value = wa.rate;
                if (wa.interval) document.getElementById('wa_interval').value = wa.interval;
            }

            // Maintenance calendar
            const cal = data.maintenance_calendar;
            if (cal && typeof cal === 'object') {
                ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].forEach(m => {
                    if (cal[m]) document.getElementById('cal_' + m).value = cal[m];
                });
            }

            onFacilityTypeChange();
            updateCompleteness();
            loadContextPreview();
            loadProfilesList();
        } catch (e) {
            console.error('Failed to load profile', e);
        }
    }

    async function saveProfile() {
        const btn = document.getElementById('save-btn');
        const toast = document.getElementById('save-toast');
        btn.disabled = true;
        btn.textContent = 'Saving...';

        try {
            const resp = await fetch('/api/profile', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(buildProfileData())
            });
            if (resp.ok) {
                toast.style.display = 'inline';
                btn.textContent = 'Saved';
                updateCompleteness();
                loadContextPreview();
                if (window.location.search.includes('setup=1')) {
                    document.getElementById('go-chat-btn').style.display = 'inline-block';
                }
                setTimeout(() => { toast.style.display = 'none'; btn.disabled = false; btn.textContent = 'Save Profile'; }, 2500);
            } else {
                alert('Failed to save profile');
                btn.disabled = false; btn.textContent = 'Save Profile';
            }
        } catch (e) {
            alert('Failed to save profile');
            btn.disabled = false; btn.textContent = 'Save Profile';
        }
    }

    // =========================================================================
    // Context preview
    // =========================================================================
    function toggleContextPreview() {
        document.getElementById('context-card').classList.toggle('open');
    }

    async function loadContextPreview() {
        try {
            const resp = await fetch('/api/profile/context-preview');
            if (resp.ok) {
                const data = await resp.json();
                document.getElementById('ai-context-text').textContent = data.context || 'No profile data yet. Fill in fields above and save.';
            }
        } catch (e) {}
    }

    // =========================================================================
    // Setup mode
    // =========================================================================
    if (window.location.search.includes('setup=1')) {
        document.getElementById('welcome-banner').style.display = 'block';
        document.getElementById('skip-link').style.display = 'block';
    }

    loadProfile();

    // =========================================================================
    // Sprayer Management
    // =========================================================================
    let sprayers = [];

    async function loadSprayers() {
        try {
            const resp = await fetch('/api/sprayers');
            if (resp.ok) { sprayers = await resp.json(); renderSprayers(); updateCompleteness(); }
        } catch (e) { console.error('Failed to load sprayers', e); }
    }

    function renderSprayers() {
        const container = document.getElementById('sprayers-list');
        if (!sprayers.length) {
            container.innerHTML = '<div style="text-align:center;padding:16px;color:#9ca3af;font-size:13px;">No sprayers configured yet. Add one below.</div>';
            return;
        }
        container.innerHTML = sprayers.map(s => {
            const areas = (Array.isArray(s.areas) ? s.areas : []).map(a => a.charAt(0).toUpperCase() + a.slice(1));
            const areaStr = areas.length ? areas.join(', ') : '<span style="color:#9ca3af">No areas assigned</span>';
            return `<div class="sprayer-card">
                <div class="sprayer-card-body">
                    <div class="sprayer-name">${escapeHtml(s.name)}${s.is_default ? '<span class="sprayer-default-badge">DEFAULT</span>' : ''}</div>
                    <div class="sprayer-detail">${s.gpa} GPA &middot; ${s.tank_size} gal tank${s.nozzle_type ? ' &middot; ' + escapeHtml(s.nozzle_type) : ''}</div>
                    <div class="sprayer-detail">Areas: ${areaStr}</div>
                </div>
                <button onclick="editSprayer(${s.id})" class="sprayer-link" style="color:#2d7a4a;">Edit</button>
                <button onclick="deleteSprayer(${s.id})" class="sprayer-link" style="color:#dc2626;">Delete</button>
            </div>`;
        }).join('');
    }

    function showSprayerForm() {
        document.getElementById('sprayer-form').style.display = 'block';
        document.getElementById('add-sprayer-btn').style.display = 'none';
        document.getElementById('sprayer-edit-id').value = '';
        ['sprayer-name','sprayer-gpa','sprayer-tank','sprayer-nozzle'].forEach(id => document.getElementById(id).value = '');
        document.getElementById('sprayer-default').checked = false;
        document.querySelectorAll('.sprayer-area-cb').forEach(cb => cb.checked = false);
        document.getElementById('sprayer-name').focus();
    }

    function cancelSprayerForm() {
        document.getElementById('sprayer-form').style.display = 'none';
        document.getElementById('add-sprayer-btn').style.display = 'block';
    }

    function editSprayer(id) {
        const s = sprayers.find(x => x.id === id);
        if (!s) return;
        document.getElementById('sprayer-form').style.display = 'block';
        document.getElementById('add-sprayer-btn').style.display = 'none';
        document.getElementById('sprayer-edit-id').value = s.id;
        document.getElementById('sprayer-name').value = s.name;
        document.getElementById('sprayer-gpa').value = s.gpa;
        document.getElementById('sprayer-tank').value = s.tank_size;
        document.getElementById('sprayer-nozzle').value = s.nozzle_type || '';
        document.getElementById('sprayer-default').checked = !!s.is_default;
        const areas = Array.isArray(s.areas) ? s.areas : [];
        document.querySelectorAll('.sprayer-area-cb').forEach(cb => { cb.checked = areas.includes(cb.value); });
    }

    async function saveSprayer() {
        const name = document.getElementById('sprayer-name').value.trim();
        const gpa = parseFloat(document.getElementById('sprayer-gpa').value);
        const tankSize = parseFloat(document.getElementById('sprayer-tank').value);
        if (!name) { alert('Sprayer name is required'); return; }
        if (!gpa || gpa <= 0) { alert('GPA is required'); return; }
        if (!tankSize || tankSize <= 0) { alert('Tank size is required'); return; }
        const areas = [];
        document.querySelectorAll('.sprayer-area-cb:checked').forEach(cb => areas.push(cb.value));
        const data = { name, gpa, tank_size: tankSize, nozzle_type: document.getElementById('sprayer-nozzle').value.trim() || null, areas, is_default: document.getElementById('sprayer-default').checked };
        const editId = document.getElementById('sprayer-edit-id').value;
        if (editId) data.id = parseInt(editId);
        try {
            const resp = await fetch('/api/sprayers', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
            if (resp.ok) { cancelSprayerForm(); await loadSprayers(); } else { const err = await resp.json(); alert(err.error || 'Failed to save sprayer'); }
        } catch (e) { alert('Failed to save sprayer'); }
    }

    async function deleteSprayer(id) {
        if (!confirm('Delete this sprayer?')) return;
        try { const resp = await fetch(`/api/sprayers/${id}`, { method: 'DELETE' }); if (resp.ok) await loadSprayers(); } catch (e) {}
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    loadSprayers();

    // =========================================================================
    // Multi-course profile switcher
    // =========================================================================
    let profilesList = [];

    async function loadProfilesList() {
        try {
            const resp = await fetch('/api/profiles');
            if (!resp.ok) return;
            profilesList = await resp.json();
            if (profilesList.length > 1) {
                renderProfileSwitcher();
            } else {
                document.getElementById('profile-switcher').style.display = 'none';
            }
        } catch (e) {}
    }

    function renderProfileSwitcher() {
        const switcher = document.getElementById('profile-switcher');
        const select = document.getElementById('profile-select');
        switcher.style.display = 'block';
        select.innerHTML = '';
        profilesList.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.course_name;
            opt.textContent = p.course_name + (p.is_active ? ' (Active)' : '');
            opt.selected = p.is_active;
            select.appendChild(opt);
        });
    }

    async function switchProfile(courseName) {
        try {
            await fetch('/api/profiles/activate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({course_name: courseName})
            });
            isDirty = false;
            window.location.reload();
        } catch (e) {}
    }

    function showAddCourseModal() {
        document.getElementById('add-course-modal').style.display = 'flex';
        document.getElementById('new-course-name').value = '';
        document.getElementById('new-course-source').value = 'blank';
        document.getElementById('template-select-group').style.display = 'none';
        document.getElementById('new-course-name').focus();
        // Load templates
        fetch('/api/profile/templates').then(r => r.json()).then(templates => {
            const sel = document.getElementById('template-select');
            sel.innerHTML = '';
            templates.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = t.label;
                sel.appendChild(opt);
            });
        }).catch(() => {});
    }

    function closeAddCourseModal() {
        document.getElementById('add-course-modal').style.display = 'none';
    }

    // Toggle template select visibility
    document.getElementById('new-course-source').addEventListener('change', function() {
        document.getElementById('template-select-group').style.display = this.value === 'template' ? 'block' : 'none';
    });

    async function addCourse() {
        const name = document.getElementById('new-course-name').value.trim();
        if (!name) { alert('Course name is required'); return; }
        const source = document.getElementById('new-course-source').value;
        try {
            if (source === 'duplicate') {
                const current = document.getElementById('course_name').value || 'My Course';
                await fetch('/api/profiles/duplicate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({source: current, new_name: name})
                });
            } else if (source === 'template') {
                const templateId = document.getElementById('template-select').value;
                await fetch('/api/profile/from-template', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({template: templateId, course_name: name})
                });
            } else {
                // Blank — just save a minimal profile
                await fetch('/api/profile', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({course_name: name})
                });
            }
            // Switch to the new course
            await fetch('/api/profiles/activate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({course_name: name})
            });
            isDirty = false;
            window.location.reload();
        } catch (e) {
            alert('Failed to create course');
        }
    }
