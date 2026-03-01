    // =========================================================================
    // State
    // =========================================================================
    let profile = null;
    let allProducts = [];
    let inventoryIds = new Set();
    let searchTimeout = null;
    let sprayers = [];
    let selectedSprayer = null;

    // Product rows: [{id, product, rate, rate_unit, searchQuery, searchResults, showDropdown}]
    let productRows = [];
    let nextRowId = 1;

    const ACRE_TO_1000 = 43.56;

    // =========================================================================
    // Init
    // =========================================================================
    document.addEventListener('DOMContentLoaded', async () => {
        document.getElementById('spray-date').valueAsDate = new Date();

        const currentYear = new Date().getFullYear();
        ['filter-year', 'nutrient-year'].forEach(id => {
            const sel = document.getElementById(id);
            for (let y = currentYear; y >= currentYear - 3; y--) {
                const opt = document.createElement('option');
                opt.value = y;
                opt.textContent = y;
                if (y === currentYear) opt.selected = true;
                sel.appendChild(opt);
            }
        });

        try {
            const resp = await fetch('/api/profile');
            if (resp.ok) profile = await resp.json();
        } catch (e) {}

        try {
            const resp = await fetch('/api/sprayers');
            if (resp.ok) {
                sprayers = await resp.json();
                populateSprayerDropdown();
            }
        } catch (e) {}

        try {
            const resp = await fetch('/api/products/all');
            if (resp.ok) allProducts = await resp.json();
        } catch (e) {}

        try {
            const resp = await fetch('/api/inventory/ids');
            if (resp.ok) {
                const ids = await resp.json();
                inventoryIds = new Set(ids);
                updateInventoryCount();
            }
        } catch (e) {}

        // Load spray templates
        loadTemplates();

        // Start with one empty product row
        addProductRow();

        // Check URL params for chat-to-spray integration (Feature 7)
        const urlParams = new URLSearchParams(window.location.search);
        const preselectedProductId = urlParams.get('product_id');
        if (preselectedProductId) {
            const product = allProducts.find(p => p.id === preselectedProductId);
            if (product && productRows.length > 0) {
                const row = productRows[0];
                row.product = product;
                if (product.default_rate) row.rate = product.default_rate;
                if (product.rate_unit) row.rate_unit = product.rate_unit;
                else if (product.form_type === 'liquid') row.rate_unit = 'fl oz/1000 sq ft';
                else row.rate_unit = 'lbs/1000 sq ft';
                renderProductTable();
                recalcAllRows();
            }
            // Clean URL
            window.history.replaceState({}, '', window.location.pathname);
        }
    });

    // =========================================================================
    // Tabs
    // =========================================================================
    function switchTab(name) {
        document.querySelectorAll('.tab').forEach(t => {
            t.classList.remove('active');
            if (t.getAttribute('onclick') && t.getAttribute('onclick').includes("'" + name + "'")) t.classList.add('active');
        });
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.getElementById('tab-' + name).classList.add('active');
        if (name === 'history') loadHistory();
        if (name === 'nutrients') loadNutrients();
        if (name === 'library') initLibrary();
    }

    // =========================================================================
    // Sprayer management
    // =========================================================================
    function populateSprayerDropdown() {
        const sel = document.getElementById('spray-sprayer');
        sel.innerHTML = '<option value="">Select sprayer...</option>';
        sprayers.forEach(s => {
            const areas = (typeof s.areas === 'string') ? JSON.parse(s.areas) : (s.areas || []);
            const areaStr = areas.length ? areas.map(a => a.charAt(0).toUpperCase() + a.slice(1)).join(', ') : 'All';
            const defStr = s.is_default ? ' ★' : '';
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.name} — ${s.gpa} GPA, ${s.tank_size} gal (${areaStr})${defStr}`;
            sel.appendChild(opt);
        });
        const manualOpt = document.createElement('option');
        manualOpt.value = 'manual';
        manualOpt.textContent = 'Enter manually...';
        sel.appendChild(manualOpt);
    }

    function onSprayerChange() {
        const sel = document.getElementById('spray-sprayer');
        const hint = document.getElementById('sprayer-info-hint');
        const val = sel.value;

        if (val === 'manual') {
            selectedSprayer = null;
            hint.textContent = 'Using manual GPA/tank';
            hint.style.color = '#6b7280';
        } else if (val) {
            const sprayer = sprayers.find(s => s.id == val);
            if (sprayer) {
                selectedSprayer = sprayer;
                hint.textContent = `${sprayer.gpa} GPA · ${sprayer.tank_size} gal tank`;
                hint.style.color = '#1a4d2e';
            }
        } else {
            selectedSprayer = null;
            hint.textContent = '';
        }
        updateEquipmentInfo();
        recalcAllRows();
    }

    function autoSelectSprayer(area) {
        if (!sprayers.length) return;
        let match = sprayers.find(s => {
            const areas = (typeof s.areas === 'string') ? JSON.parse(s.areas) : (s.areas || []);
            return areas.includes(area);
        });
        if (!match) match = sprayers.find(s => s.is_default);
        if (!match) match = sprayers[0];
        if (match) {
            document.getElementById('spray-sprayer').value = match.id;
            onSprayerChange();
        }
    }

    function getGpa() {
        if (selectedSprayer) return parseFloat(selectedSprayer.gpa) || 0;
        if (profile && profile.default_gpa) return parseFloat(profile.default_gpa) || 0;
        return 0;
    }

    function getTankSize() {
        if (selectedSprayer) return parseFloat(selectedSprayer.tank_size) || 0;
        if (profile && profile.tank_size) return parseFloat(profile.tank_size) || 0;
        return 0;
    }

    // =========================================================================
    // Equipment Info (TurfCloud-inspired)
    // =========================================================================
    function updateEquipmentInfo() {
        const acreage = getAcreage();
        const gpa = getGpa();
        const tankSize = getTankSize();
        const summaryEl = document.getElementById('equip-summary');
        const tanksStat = document.getElementById('equip-tanks-stat');
        const acreTankStat = document.getElementById('equip-acretank-stat');
        const tanksInput = document.getElementById('equip-tanks');
        const acresPerTankEl = document.getElementById('equip-acres-per-tank');
        const sprayerVal = document.getElementById('spray-sprayer').value;

        if (gpa > 0 && tankSize > 0) {
            summaryEl.textContent = `${selectedSprayer ? selectedSprayer.name : 'Sprayer'} · ${gpa} GPA · ${tankSize} gal tank`;
            tanksStat.style.display = '';
            acreTankStat.style.display = '';

            if (acreage > 0) {
                const totalCarrier = gpa * acreage;
                const tankCount = Math.ceil(totalCarrier / tankSize);
                const acresPerTank = (tankSize / gpa);
                tanksInput.value = tanksInput.value || tankCount;
                acresPerTankEl.textContent = acresPerTank.toFixed(2);
            } else {
                const acresPerTank = (tankSize / gpa);
                acresPerTankEl.textContent = acresPerTank.toFixed(2);
            }
        } else if (sprayerVal === 'manual') {
            summaryEl.textContent = 'Manual mode — enter number of tanks';
            tanksStat.style.display = '';
            acreTankStat.style.display = 'none';
        } else {
            summaryEl.textContent = 'Select a sprayer to see equipment info';
            tanksStat.style.display = 'none';
            acreTankStat.style.display = 'none';
        }
    }

    function onTanksInput() {
        recalcAllRows();
    }

    function getTankCount() {
        const manualTanks = parseInt(document.getElementById('equip-tanks').value);
        if (manualTanks > 0) return manualTanks;
        const acreage = getAcreage();
        const gpa = getGpa();
        const tankSize = getTankSize();
        if (acreage > 0 && gpa > 0 && tankSize > 0) {
            return Math.ceil((gpa * acreage) / tankSize);
        }
        return 0;
    }

    // =========================================================================
    // Area selection
    // =========================================================================
    function onAreaChange() {
        const area = document.getElementById('spray-area').value;
        const hint = document.getElementById('area-acreage-hint');
        if (area && profile) {
            const acreage = profile[area + '_acreage'];
            if (acreage) {
                hint.textContent = `${acreage} acres from profile`;
                hint.style.color = '#6b7280';
            } else {
                hint.textContent = 'No acreage set in profile — enter below';
                hint.style.color = '#dc2626';
            }
        } else {
            hint.textContent = '';
        }
        if (area) autoSelectSprayer(area);
        updateEquipmentInfo();
        recalcAllRows();
    }

    function getAcreage() {
        const override = parseFloat(document.getElementById('spray-acreage-override').value);
        if (override && override > 0) return override;
        const area = document.getElementById('spray-area').value;
        if (area && profile) return parseFloat(profile[area + '_acreage']) || 0;
        return 0;
    }

    // =========================================================================
    // Application method handling
    // =========================================================================
    function getMethodFormTypeFilter() {
        // No longer filtering products by form type — users curate their own inventory
        return '';
    }

    function onMethodChange() {
        const method = document.getElementById('application-method').value;
        const sprayerRow = document.getElementById('spray-sprayer').closest('.form-group');
        const isGranular = (method === 'push_spreader' || method === 'ride_on_spreader');
        const equipRow = document.getElementById('equip-info-row');
        const col4Head = document.getElementById('pt-col4-head');

        if (isGranular) {
            sprayerRow.style.opacity = '0.4';
            sprayerRow.style.pointerEvents = 'none';
            equipRow.style.display = 'none';
            col4Head.textContent = 'Total Used';
        } else {
            sprayerRow.style.opacity = '1';
            sprayerRow.style.pointerEvents = 'auto';
            equipRow.style.display = '';
            col4Head.textContent = 'Product Per Tank';
        }

        // Reset rows to correct defaults for new method
        productRows.forEach(r => {
            if (isGranular) {
                if (r.rate_unit.includes('fl oz') || r.rate_unit.includes('gal')) {
                    r.rate_unit = 'lbs/1000 sq ft';
                }
            }
        });

        renderProductTable();
        recalcAllRows();
    }

    // =========================================================================
    // Product Table — Row Management (TurfCloud-inspired)
    // =========================================================================
    function addProductRow() {
        const rowId = nextRowId++;
        const method = document.getElementById('application-method').value;
        const isGranular = (method === 'push_spreader' || method === 'ride_on_spreader');
        productRows.push({
            id: rowId,
            product: null,
            rate: '',
            rate_unit: isGranular ? 'lbs/1000 sq ft' : 'fl oz/1000 sq ft',
            searchQuery: '',
            searchResults: [],
            showDropdown: false,
            perTankAmt: '',
            perTankUnit: isGranular ? 'oz' : 'fl oz',
            totalUsed: '',
            totalUsedUnit: 'lbs'
        });
        renderProductTable();
    }

    function removeProductRow(rowId) {
        productRows = productRows.filter(r => r.id !== rowId);
        if (productRows.length === 0) addProductRow(); // Always have at least 1 row
        renderProductTable();
        recalcAllRows();
    }

    function renderProductTable() {
        const tbody = document.getElementById('product-table-body');
        const method = document.getElementById('application-method').value;
        const isGranular = (method === 'push_spreader' || method === 'ride_on_spreader');

        tbody.innerHTML = productRows.map(row => {
            const productDisplay = row.product
                ? escapeHtml(row.product.display_name)
                : '';
            const searchVal = row.product ? productDisplay : escapeHtml(row.searchQuery);

            const totalText = calcRowTotal(row);

            return `
                <tr data-row-id="${row.id}">
                    <td class="pt-product-cell">
                        <div class="pt-product-search">
                            <input class="pt-input" type="text" placeholder="Search products..."
                                value="${searchVal}"
                                oninput="onRowProductSearch(${row.id}, this.value)"
                                onfocus="onRowProductFocus(${row.id})"
                                autocomplete="off">
                            <div class="pt-product-dropdown ${row.showDropdown ? 'visible' : ''}" id="pt-dropdown-${row.id}">
                                ${renderRowDropdown(row)}
                            </div>
                        </div>
                        ${row.product ? `<div style="font-size:11px;color:#6b7280;margin-top:2px;">${escapeHtml(row.product.category)} · ${escapeHtml(row.product.form_type || '')}${row.product.npk ? ' · ' + row.product.npk.join('-') : ''}${formatSecondaryBrief(row.product)} <span style="cursor:pointer;color:#2d7a4a;" onclick="openProductDetailModal('${row.product.id.replace(/'/g, "\\'")}')">ℹ️</span></div>` : ''}
                        <div id="moa-warn-${row.id}" style="display:none;background:#fefce8;color:#92400e;padding:4px 8px;border-radius:4px;font-size:11px;margin-top:3px;border-left:3px solid #f59e0b;"></div>
                    </td>
                    <td class="pt-rate-cell">
                        <input class="pt-input" type="number" step="0.01" placeholder="0.0"
                            value="${row.rate}"
                            oninput="onRowRateInput(${row.id}, this.value)">
                    </td>
                    <td class="pt-unit-cell">
                        <select class="pt-select" onchange="onRowUnitChange(${row.id}, this.value)">
                            ${isGranular ? `
                                <option value="lbs/1000 sq ft" ${row.rate_unit === 'lbs/1000 sq ft' ? 'selected' : ''}>lbs / 1000 ft²</option>
                                <option value="oz/1000 sq ft" ${row.rate_unit === 'oz/1000 sq ft' ? 'selected' : ''}>oz / 1000 ft²</option>
                                <option value="lbs/acre" ${row.rate_unit === 'lbs/acre' ? 'selected' : ''}>lbs / acre</option>
                                <option value="oz/acre" ${row.rate_unit === 'oz/acre' ? 'selected' : ''}>oz / acre</option>
                            ` : `
                                <option value="fl oz/1000 sq ft" ${row.rate_unit === 'fl oz/1000 sq ft' ? 'selected' : ''}>fl oz / 1000 ft²</option>
                                <option value="oz/1000 sq ft" ${row.rate_unit === 'oz/1000 sq ft' ? 'selected' : ''}>oz / 1000 ft²</option>
                                <option value="gal/1000 sq ft" ${row.rate_unit === 'gal/1000 sq ft' ? 'selected' : ''}>gal / 1000 ft²</option>
                                <option value="lbs/1000 sq ft" ${row.rate_unit === 'lbs/1000 sq ft' ? 'selected' : ''}>lbs / 1000 ft²</option>
                                <option value="fl oz/acre" ${row.rate_unit === 'fl oz/acre' ? 'selected' : ''}>fl oz / acre</option>
                                <option value="oz/acre" ${row.rate_unit === 'oz/acre' ? 'selected' : ''}>oz / acre</option>
                                <option value="gal/acre" ${row.rate_unit === 'gal/acre' ? 'selected' : ''}>gal / acre</option>
                                <option value="lbs/acre" ${row.rate_unit === 'lbs/acre' ? 'selected' : ''}>lbs / acre</option>
                            `}
                        </select>
                    </td>
                    <td class="pt-pertank-cell">
                        ${isGranular ? `
                        <div style="display:flex;align-items:center;gap:4px;">
                            <input class="pt-input" type="number" step="0.01"
                                placeholder="Total used"
                                value="${row.totalUsed || ''}"
                                oninput="onRowTotalUsedInput(${row.id}, this.value)"
                                style="min-width:70px;max-width:90px;"
                                ${!row.product ? 'disabled' : ''}>
                            <select class="pt-select" onchange="onRowTotalUsedUnitChange(${row.id}, this.value)"
                                style="min-width:50px;max-width:65px;font-size:11px;padding:2px 4px;"
                                ${!row.product ? 'disabled' : ''}>
                                <option value="lbs" ${(row.totalUsedUnit || 'lbs') === 'lbs' ? 'selected' : ''}>lbs</option>
                                <option value="oz" ${row.totalUsedUnit === 'oz' ? 'selected' : ''}>oz</option>
                            </select>
                        </div>
                        ` : `
                        <div style="display:flex;align-items:center;gap:4px;">
                            <input class="pt-input pt-pertank-input" type="number" step="0.01"
                                placeholder="—"
                                value="${row.perTankAmt || ''}"
                                oninput="onRowPerTankInput(${row.id}, this.value)"
                                style="min-width:60px;max-width:80px;"
                                ${!row.product ? 'disabled' : ''}>
                            <select class="pt-select pt-pertank-unit-select" onchange="onRowPerTankUnitChange(${row.id}, this.value)"
                                style="min-width:50px;max-width:65px;font-size:11px;padding:2px 4px;"
                                ${!row.product ? 'disabled' : ''}>
                                <option value="fl oz" ${row.perTankUnit === 'fl oz' ? 'selected' : ''}>fl oz</option>
                                <option value="oz" ${row.perTankUnit === 'oz' ? 'selected' : ''}>oz</option>
                                <option value="gal" ${row.perTankUnit === 'gal' ? 'selected' : ''}>gal</option>
                                <option value="lbs" ${row.perTankUnit === 'lbs' ? 'selected' : ''}>lbs</option>
                            </select>
                        </div>
                        `}
                    </td>
                    <td class="pt-total-cell">${totalText}</td>
                    <td>
                        <button class="pt-remove-btn" onclick="removeProductRow(${row.id})" title="Remove">🗑</button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // searchScope is always 'inventory' for spray log — users manage inventory via Inventory tab

    function updateInventoryCount() {
        const el = document.getElementById('inventory-count');
        if (el) el.textContent = inventoryIds.size > 0 ? `(${inventoryIds.size} in inventory)` : '';
        const libEl = document.getElementById('library-inv-count');
        if (libEl) libEl.textContent = inventoryIds.size;
    }

    async function addToInventory(productId) {
        try {
            await fetch('/api/inventory', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ product_id: productId })
            });
            inventoryIds.add(productId);
            updateInventoryCount();
        } catch (e) {}
    }

    async function removeFromInventory(productId) {
        try {
            await fetch(`/api/inventory/${encodeURIComponent(productId)}`, { method: 'DELETE' });
            inventoryIds.delete(productId);
            updateInventoryCount();
        } catch (e) {}
    }

    async function toggleInventory(productId) {
        if (inventoryIds.has(productId)) {
            await removeFromInventory(productId);
        } else {
            await addToInventory(productId);
        }
    }

    function getProductPool() {
        // Spray log only shows inventory products
        if (inventoryIds.size > 0) {
            return allProducts.filter(p => inventoryIds.has(p.id));
        }
        return []; // Empty inventory — user must add products from Inventory tab
    }

    function renderRowDropdown(row) {
        const results = row.searchResults;
        if (!results.length) {
            if (inventoryIds.size === 0) {
                return '<div style="padding:10px;color:#9ca3af;font-size:13px;">Your inventory is empty — add products from the <b>Inventory</b> tab</div>';
            }
            return '<div style="padding:10px;color:#9ca3af;font-size:13px;">No products found in your inventory — add more from the <b>Inventory</b> tab</div>';
        }
        let html = '';
        html += results.slice(0, 20).map((p, idx) => {
            const badgeClass = 'badge-' + p.category;
            return `
                <div class="product-item" onmousedown="selectRowProduct(${row.id}, ${idx})" style="display:flex;align-items:center;justify-content:space-between;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span class="category-badge ${badgeClass}">${p.category}</span>
                        <div>
                            <div class="name">${escapeHtml(p.display_name)}</div>
                            ${p.brand ? `<div class="brand">${escapeHtml(p.brand)}</div>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        return html;
    }

    function onRowProductSearch(rowId, query) {
        const row = productRows.find(r => r.id === rowId);
        if (!row) return;
        row.searchQuery = query;
        row.product = null; // Clear selection when typing

        clearTimeout(searchTimeout);
        const formTypeFilter = getMethodFormTypeFilter();

        if (query.length < 2) {
            if (query.length === 0) {
                let pool = getProductPool();
                if (formTypeFilter) pool = pool.filter(p => p.form_type === formTypeFilter);
                row.searchResults = pool.slice(0, 20);
            } else {
                row.searchResults = [];
            }
            row.showDropdown = true;
            updateRowDropdown(row);
            return;
        }

        searchTimeout = setTimeout(async () => {
            try {
                let url = `/api/products/search?q=${encodeURIComponent(query)}&scope=inventory`;
                if (formTypeFilter) url += `&form_type=${formTypeFilter}`;
                const resp = await fetch(url);
                if (resp.ok) {
                    let results = await resp.json();
                    row.searchResults = results.slice(0, 20);
                    row.showDropdown = true;
                    updateRowDropdown(row);
                }
            } catch (e) {}
        }, 250);
    }

    function onRowProductFocus(rowId) {
        // Close all other dropdowns
        productRows.forEach(r => {
            if (r.id !== rowId) {
                r.showDropdown = false;
                const dd = document.getElementById('pt-dropdown-' + r.id);
                if (dd) dd.classList.remove('visible');
            }
        });
        const row = productRows.find(r => r.id === rowId);
        if (!row) return;
        // Show dropdown
        if (!row.searchResults.length) {
            const formTypeFilter = getMethodFormTypeFilter();
            let pool = getProductPool();
            if (formTypeFilter) pool = pool.filter(p => p.form_type === formTypeFilter);
            row.searchResults = pool.slice(0, 20);
        }
        row.showDropdown = true;
        updateRowDropdown(row);
    }

    function selectRowProduct(rowId, resultIndex) {
        const row = productRows.find(r => r.id === rowId);
        if (!row) return;
        const product = row.searchResults[resultIndex];
        if (!product) return;
        row.product = product;
        row.searchQuery = '';
        row.showDropdown = false;
        row.searchResults = [];

        // Set default rate and unit
        if (product.default_rate) row.rate = product.default_rate;
        if (product.rate_unit) row.rate_unit = product.rate_unit;
        else if (product.form_type === 'liquid') row.rate_unit = 'fl oz/1000 sq ft';
        else row.rate_unit = 'lbs/1000 sq ft';

        // Set default per-tank unit from the rate unit base
        row.perTankUnit = getBaseUnit(row.rate_unit) || 'fl oz';

        renderProductTable();
        recalcAllRows();

        // MOA rotation check
        const area = document.getElementById('spray-area').value;
        if (area && product) {
            checkMoaRotation(rowId, area, product);
        }
    }

    function updateRowDropdown(row) {
        const dd = document.getElementById('pt-dropdown-' + row.id);
        if (!dd) return;
        dd.innerHTML = renderRowDropdown(row);
        if (row.showDropdown) dd.classList.add('visible');
        else dd.classList.remove('visible');
    }

    function onRowRateInput(rowId, value) {
        const row = productRows.find(r => r.id === rowId);
        if (!row) return;
        row.rate = parseFloat(value) || '';
        // Clear totalUsed so total column recalcs from rate
        row.totalUsed = '';
        recalcAllRows();
    }

    function onRowUnitChange(rowId, value) {
        const row = productRows.find(r => r.id === rowId);
        if (!row) return;
        row.rate_unit = value;
        recalcAllRows();
    }

    // Close all dropdowns when clicking outside product cells
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.pt-product-search')) {
            productRows.forEach(r => {
                r.showDropdown = false;
                const dd = document.getElementById('pt-dropdown-' + r.id);
                if (dd) dd.classList.remove('visible');
            });
        }
    });

    // =========================================================================
    // Calculations — Per Row + Summary
    // =========================================================================
    function getBaseUnit(rateUnit) {
        if (!rateUnit) return '';
        return rateUnit.split('/')[0].trim();
    }

    function calcProductTotal(rate, rateUnit, acreage) {
        const area1000 = acreage * ACRE_TO_1000;
        if (rateUnit.includes('/1000')) return rate * area1000;
        if (rateUnit.includes('/acre')) return rate * acreage;
        return rate * area1000;
    }

    function formatProductTotal(totalProduct, rateUnit, formType) {
        let displayUnit = rateUnit.split('/')[0].trim();
        let displayTotal = totalProduct;

        if (displayUnit === 'gal') {
            // keep as-is
        } else if (displayUnit === 'fl oz') {
            // fl oz → gallons at high volumes
            if (totalProduct > 256) {
                displayTotal = totalProduct / 128;
                displayUnit = 'gal';
            }
        } else if (displayUnit === 'oz') {
            if (formType === 'liquid') {
                if (totalProduct > 256) {
                    displayTotal = totalProduct / 128;
                    displayUnit = 'gal';
                } else {
                    displayUnit = 'fl oz';
                }
            } else {
                // Granular: oz → lbs at high volumes
                if (totalProduct > 32) {
                    displayTotal = totalProduct / 16;
                    displayUnit = 'lbs';
                }
            }
        }
        // lbs stays as lbs
        return { total: displayTotal, unit: displayUnit };
    }

    // Convert between per-tank unit and rate base unit
    function convertToRateBaseUnit(amount, fromUnit, toUnit) {
        if (fromUnit === toUnit) return amount;
        const toFlOz = { 'fl oz': 1, 'gal': 128 };
        const toOz = { 'oz': 1, 'lbs': 16 };
        // fl oz / gal conversions
        if (toFlOz[fromUnit] !== undefined && toFlOz[toUnit] !== undefined) {
            return amount * toFlOz[fromUnit] / toFlOz[toUnit];
        }
        // oz / lbs conversions
        if (toOz[fromUnit] !== undefined && toOz[toUnit] !== undefined) {
            return amount * toOz[fromUnit] / toOz[toUnit];
        }
        // Cross-type (fl oz ↔ oz): treat as 1:1
        if (toFlOz[fromUnit] !== undefined && toOz[toUnit] !== undefined) {
            return amount * toFlOz[fromUnit] / toOz[toUnit];
        }
        if (toOz[fromUnit] !== undefined && toFlOz[toUnit] !== undefined) {
            return amount * toOz[fromUnit] / toFlOz[toUnit];
        }
        return amount;
    }

    function calcRateFromPerTank(row) {
        if (!row.perTankAmt || !row.product) return;
        const tankCount = getTankCount();
        const acreage = getAcreage();
        if (!tankCount || !acreage) return;

        const rateBaseUnit = getBaseUnit(row.rate_unit);
        const perTankInRateUnit = convertToRateBaseUnit(row.perTankAmt, row.perTankUnit, rateBaseUnit);
        const totalProduct = perTankInRateUnit * tankCount;

        const area1000 = acreage * ACRE_TO_1000;
        let newRate;
        if (row.rate_unit.includes('/1000')) {
            newRate = totalProduct / area1000;
        } else if (row.rate_unit.includes('/acre')) {
            newRate = totalProduct / acreage;
        } else {
            newRate = totalProduct / area1000;
        }

        row.rate = Math.round(newRate * 1000) / 1000;

        // Update rate input in DOM
        const tr = document.querySelector(`tr[data-row-id="${row.id}"]`);
        if (tr) {
            const rateInput = tr.querySelector('.pt-rate-cell input');
            if (rateInput) rateInput.value = row.rate;
        }
    }

    function onRowPerTankInput(rowId, value) {
        const row = productRows.find(r => r.id === rowId);
        if (!row || !row.product) return;
        row.perTankAmt = parseFloat(value) || '';
        row.totalUsed = '';
        calcRateFromPerTank(row);
        recalcAllRows();
    }

    function onRowPerTankUnitChange(rowId, value) {
        const row = productRows.find(r => r.id === rowId);
        if (!row) return;
        row.perTankUnit = value;
        calcRateFromPerTank(row);
        recalcAllRows();
    }

    // Granular: back-calculate rate from total product used
    function onRowTotalUsedInput(rowId, value) {
        const row = productRows.find(r => r.id === rowId);
        if (!row || !row.product) return;
        row.totalUsed = parseFloat(value) || '';
        calcRateFromTotalUsed(row);
        recalcAllRows();
    }

    function onRowTotalUsedUnitChange(rowId, value) {
        const row = productRows.find(r => r.id === rowId);
        if (!row) return;
        row.totalUsedUnit = value;
        calcRateFromTotalUsed(row);
        recalcAllRows();
    }

    function calcRateFromTotalUsed(row) {
        if (!row.totalUsed || !row.product) return;
        const acreage = getAcreage();
        if (!acreage) return;

        let totalLbs = row.totalUsed;
        if (row.totalUsedUnit === 'oz') totalLbs = row.totalUsed / 16;

        const area1000 = acreage * ACRE_TO_1000;

        let newRate;
        if (row.rate_unit.includes('/1000')) {
            if (row.rate_unit.includes('oz')) {
                newRate = (totalLbs * 16) / area1000;
            } else {
                newRate = totalLbs / area1000;
            }
        } else if (row.rate_unit.includes('/acre')) {
            if (row.rate_unit.includes('oz')) {
                newRate = (totalLbs * 16) / acreage;
            } else {
                newRate = totalLbs / acreage;
            }
        } else {
            newRate = totalLbs / area1000;
        }

        row.rate = Math.round(newRate * 1000) / 1000;

        const tr = document.querySelector(`tr[data-row-id="${row.id}"]`);
        if (tr) {
            const rateInput = tr.querySelector('.pt-rate-cell input');
            if (rateInput) rateInput.value = row.rate;
        }
    }

    function calcRowTotal(row) {
        // If total was directly entered (granular "Total Used"), display that
        if (row.totalUsed && row.product) {
            let total = row.totalUsed;
            let unit = row.totalUsedUnit || 'lbs';
            // Convert oz → lbs for display if large
            if (unit === 'oz' && total > 32) {
                total = total / 16;
                unit = 'lbs';
            }
            return `${parseFloat(total).toFixed(2)} ${unit}`;
        }
        if (!row.product || !row.rate) return '—';
        const acreage = getAcreage();
        if (!acreage) return '—';
        const totalProduct = calcProductTotal(row.rate, row.rate_unit, acreage);
        const fmt = formatProductTotal(totalProduct, row.rate_unit, row.product.form_type);
        return `${fmt.total.toFixed(2)} ${fmt.unit}`;
    }

    function recalcAllRows() {
        // Update total cells for each row (without full re-render to keep dropdowns)
        productRows.forEach(row => {
            const tr = document.querySelector(`tr[data-row-id="${row.id}"]`);
            if (!tr) return;
            const cells = tr.querySelectorAll('td');
            // cells: [product, rate, unit, perTank, total, actions]
            if (cells.length >= 5) {
                cells[4].textContent = calcRowTotal(row);
            }
        });

        updateEquipmentInfo();
        updateCalcSummary();
        validateSprayForm();
    }

    function calcLbsPer1000(product, rate, rateUnit) {
        if (product.form_type === 'liquid') {
            const density = product.density_lbs_per_gallon || 10.0;
            const baseUnit = rateUnit.split('/')[0].trim();
            if (baseUnit === 'gal') {
                if (rateUnit.includes('/1000')) return rate * density;
                return (rate * density) / ACRE_TO_1000;
            }
            // fl oz or oz for liquid → convert via density
            if (rateUnit.includes('/1000')) return (rate / 128) * density;
            return ((rate / 128) * density) / ACRE_TO_1000;
        } else {
            let rateLbs = rate;
            if (rateUnit.includes('oz')) rateLbs = rate / 16;
            if (rateUnit.includes('/1000')) return rateLbs;
            return rateLbs / ACRE_TO_1000;
        }
    }

    function updateCalcSummary() {
        const acreage = getAcreage();
        const gpa = getGpa();
        const tankSize = getTankSize();
        const calcEl = document.getElementById('calc-display');
        const area1000 = acreage * ACRE_TO_1000;
        const method = document.getElementById('application-method').value;
        const isGranular = (method === 'push_spreader' || method === 'ride_on_spreader');

        // Gather products with rate OR totalUsed
        const activeRows = productRows.filter(r => r.product && (r.rate || r.totalUsed));
        if (!activeRows.length || !acreage) {
            calcEl.classList.add('hidden');
            return;
        }
        calcEl.classList.remove('hidden');

        // Summary label
        const summaryLabel = document.getElementById('calc-summary-label');
        const summaryValue = document.getElementById('calc-summary-value');
        const tankCount = getTankCount();

        if (activeRows.length === 1) {
            const r = activeRows[0];
            // If total was directly entered, use that
            if (r.totalUsed) {
                let dispTotal = r.totalUsed;
                let dispUnit = r.totalUsedUnit || 'lbs';
                if (dispUnit === 'oz' && dispTotal > 32) { dispTotal = dispTotal / 16; dispUnit = 'lbs'; }
                summaryLabel.textContent = `${acreage} acres · ${r.rate} ${r.rate_unit}`;
                summaryValue.textContent = `${parseFloat(dispTotal).toFixed(2)} ${dispUnit}`;
            } else {
                summaryLabel.textContent = `${acreage} acres × ${r.rate} ${r.rate_unit}`;
                const total = calcProductTotal(r.rate, r.rate_unit, acreage);
                const fmt = formatProductTotal(total, r.rate_unit, r.product.form_type);
                summaryValue.textContent = `${fmt.total.toFixed(2)} ${fmt.unit}`;
            }
        } else {
            summaryLabel.textContent = `${isGranular ? 'Mix' : 'Tank Mix'} — ${activeRows.length} products on ${acreage} acres`;
            summaryValue.textContent = !isGranular && tankCount ? `${tankCount} tanks` : '';
        }

        // Total amount = tank size × number of tanks (sprayer only)
        const carrierRow = document.getElementById('calc-carrier-row');
        if (!isGranular && tankSize > 0 && tankCount > 0) {
            const totalAmount = tankSize * tankCount;
            document.getElementById('calc-carrier-value').textContent = `${totalAmount.toFixed(1)} gallons (${tankCount} × ${tankSize} gal)`;
            carrierRow.style.display = '';
        } else {
            carrierRow.style.display = 'none';
        }

        // Nutrients — N, P, K only
        const nutrientSection = document.getElementById('calc-nutrients-section');
        const nutrientBody = document.getElementById('calc-nutrients-body');
        const npkKeys = ['N', 'P₂O₅', 'K₂O'];
        const nutrientTotals = {};
        npkKeys.forEach(k => { nutrientTotals[k] = { per1000: 0, total: 0 }; });
        let hasNutrients = false;

        activeRows.forEach(r => {
            const lbsPer1000 = calcLbsPer1000(r.product, r.rate, r.rate_unit);

            if (r.product.npk) {
                const npk = r.product.npk;
                [
                    { name: 'N', pct: npk[0] || 0 },
                    { name: 'P₂O₅', pct: npk[1] || 0 },
                    { name: 'K₂O', pct: npk[2] || 0 },
                ].forEach(n => {
                    if (n.pct > 0) {
                        const per1000 = lbsPer1000 * (n.pct / 100);
                        nutrientTotals[n.name].per1000 += per1000;
                        nutrientTotals[n.name].total += per1000 * area1000;
                        hasNutrients = true;
                    }
                });
            }
        });

        if (hasNutrients) {
            const activeNutrients = npkKeys.filter(k => nutrientTotals[k].per1000 > 0);

            const html = activeNutrients.map(k => `
                <tr>
                    <td class="nutrient-name">${k}</td>
                    <td>${nutrientTotals[k].per1000.toFixed(4)} lbs</td>
                    <td>${nutrientTotals[k].total.toFixed(2)} lbs</td>
                </tr>
            `).join('');

            nutrientBody.innerHTML = html;
            nutrientSection.style.display = '';
        } else {
            nutrientSection.style.display = 'none';
        }
    }

    // =========================================================================
    // Form Validation (non-blocking warnings)
    // =========================================================================
    function validateSprayForm() {
        const warnings = [];
        const area = document.getElementById('spray-area').value;
        const acreage = getAcreage();

        if (!area) warnings.push('No area selected');
        if (area && (!acreage || acreage <= 0)) {
            warnings.push('No acreage set for ' + area + ' — set it in your profile or use the override field');
        }

        const activeRows = productRows.filter(r => r.product);
        if (!activeRows.length) {
            warnings.push('No products added to this application');
        }

        activeRows.forEach(r => {
            const name = r.product.display_name || 'Product';
            if (!r.rate || r.rate <= 0) {
                warnings.push(name + ': rate is empty or zero');
            }
            if (r.rate && r.product.default_rate && r.product.default_rate > 0) {
                const ratio = r.rate / r.product.default_rate;
                if (ratio > 3) {
                    warnings.push(name + ': rate (' + r.rate + ') is ' + ratio.toFixed(1) + 'x the default (' + r.product.default_rate + ' ' + (r.product.rate_unit || '') + ')');
                }
                if (ratio < 0.1) {
                    warnings.push(name + ': rate (' + r.rate + ') seems unusually low vs default (' + r.product.default_rate + ' ' + (r.product.rate_unit || '') + ')');
                }
            }
        });

        // Tank capacity validation — check liquid products fit in tank
        const tankSize = getTankSize();
        const gpa = getGpa();
        if (tankSize > 0 && gpa > 0 && acreage > 0) {
            const carrierGallons = gpa * acreage;
            let totalProductGallons = 0;
            activeRows.forEach(r => {
                if (!r.rate || !r.product) return;
                const unit = (r.rate_unit || '').toLowerCase();
                if (unit.includes('gal')) {
                    totalProductGallons += r.rate * (unit.includes('/1000') ? (acreage * ACRE_TO_1000) : acreage);
                } else if (unit.includes('fl oz') || unit.includes('oz')) {
                    totalProductGallons += (r.rate / 128) * (unit.includes('/1000') ? (acreage * ACRE_TO_1000) : acreage);
                }
                // Dry products (lbs) don't add liquid volume
            });
            const totalVolume = carrierGallons + totalProductGallons;
            const tanksNeeded = Math.ceil(totalVolume / tankSize);
            const fillPercent = tanksNeeded === 1 ? (totalVolume / tankSize) * 100 : 100;
            if (fillPercent > 100) {
                warnings.push('Tank overfill: total volume (' + totalVolume.toFixed(1) + ' gal) exceeds single tank capacity (' + tankSize + ' gal) — need ' + tanksNeeded + ' tank(s)');
            } else if (fillPercent > 90) {
                warnings.push('Tank nearly full (' + fillPercent.toFixed(0) + '%) — leave room for agitation');
            }
        }

        const container = document.getElementById('validation-warnings');
        if (container) {
            container.innerHTML = warnings.map(w =>
                '<div class="validation-warning"><span class="vw-icon">&#9888;</span> ' + escapeHtml(w) + '</div>'
            ).join('');
        }
        return warnings;
    }

    // =========================================================================
    // Submit spray
    // =========================================================================
    async function submitSpray() {
        const btn = document.getElementById('submit-spray-btn');
        const successEl = document.getElementById('success-msg');
        const errorEl = document.getElementById('error-msg');
        successEl.classList.remove('visible');
        errorEl.classList.remove('visible');

        const date = document.getElementById('spray-date').value;
        const area = document.getElementById('spray-area').value;
        const carrierGpa = getGpa() || null;
        const acreageOverride = parseFloat(document.getElementById('spray-acreage-override').value) || null;
        const applicationMethod = document.getElementById('application-method').value;

        if (!date || !area) {
            showError('Date and area are required');
            return;
        }

        // Gather active product rows
        const activeRows = productRows.filter(r => r.product && r.rate);
        if (!activeRows.length) {
            showError('Add at least one product with a rate');
            return;
        }

        let data;

        const tankCount = getTankCount() || null;

        if (activeRows.length > 1) {
            // Tank mix submission
            data = {
                date,
                area,
                application_method: applicationMethod,
                carrier_volume_gpa: carrierGpa,
                area_acreage: acreageOverride,
                tank_count: tankCount,
                weather_temp: parseFloat(document.getElementById('weather-temp').value) || null,
                weather_wind: document.getElementById('weather-wind').value || null,
                weather_conditions: document.getElementById('weather-conditions').value || null,
                notes: document.getElementById('spray-notes').value || null,
                products: activeRows.map(r => ({
                    product_id: r.product.id,
                    rate: r.rate,
                    rate_unit: r.rate_unit
                }))
            };
        } else {
            // Single product submission
            const r = activeRows[0];
            data = {
                date,
                area,
                application_method: applicationMethod,
                product_id: r.product.id,
                rate: r.rate,
                rate_unit: r.rate_unit,
                carrier_volume_gpa: carrierGpa,
                area_acreage: acreageOverride,
                tank_count: tankCount,
                weather_temp: parseFloat(document.getElementById('weather-temp').value) || null,
                weather_wind: document.getElementById('weather-wind').value || null,
                weather_conditions: document.getElementById('weather-conditions').value || null,
                notes: document.getElementById('spray-notes').value || null
            };
        }

        btn.disabled = true;
        btn.textContent = editingSprayId ? 'Updating...' : 'Saving...';

        try {
            // If editing, delete the old record first
            if (editingSprayId) {
                await fetch(`/api/spray/${editingSprayId}`, { method: 'DELETE' });
            }

            const resp = await fetch('/api/spray', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await resp.json();

            if (resp.ok && result.success) {
                const calc = result.calculations;
                const verb = editingSprayId ? 'updated' : 'logged';
                let successText;
                if (activeRows.length > 1) {
                    successText = `Tank mix ${verb} — ${activeRows.length} products`;
                    if (calc.tank_count) successText += ` · ${calc.tank_count} tank loads`;
                } else {
                    successText = `Application ${verb} — ${calc.total_product} ${calc.total_product_unit} total`;
                    if (calc.tank_count) successText += ` · ${calc.tank_count} tank loads`;
                }
                editingSprayId = null;
                document.getElementById('success-text').textContent = successText;
                successEl.classList.add('visible');

                // Auto-add used products to inventory
                activeRows.forEach(r => {
                    if (r.product && !inventoryIds.has(r.product.id)) {
                        addToInventory(r.product.id);
                    }
                });

                // Auto-deduct inventory quantities
                activeRows.forEach(r => {
                    if (r.product && r.totalUsed) {
                        const deductUnit = r.totalUsedUnit || r.rate_unit || 'oz';
                        fetch('/api/inventory/deduct', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                product_id: r.product.id,
                                amount: r.totalUsed,
                                unit: deductUnit
                            })
                        }).then(() => {
                            if (inventoryQuantities[r.product.id]) {
                                inventoryQuantities[r.product.id].quantity = Math.max(0,
                                    (inventoryQuantities[r.product.id].quantity || 0) - r.totalUsed);
                            }
                        }).catch(() => {});
                    }
                });

                // Reset form
                productRows = [];
                nextRowId = 1;
                addProductRow();
                document.getElementById('spray-acreage-override').value = '';
                document.getElementById('weather-temp').value = '';
                document.getElementById('weather-wind').value = '';
                document.getElementById('weather-conditions').value = '';
                document.getElementById('spray-notes').value = '';
                document.getElementById('equip-tanks').value = '';
                document.getElementById('calc-display').classList.add('hidden');

                setTimeout(() => successEl.classList.remove('visible'), 5000);
            } else {
                showError(result.error || 'Failed to save application');
            }
        } catch (e) {
            showError('Connection error. Please try again.');
        }

        btn.disabled = false;
        btn.textContent = editingSprayId ? 'Update Application' : 'Log Application';
    }

    function showError(msg) {
        const el = document.getElementById('error-msg');
        el.textContent = msg;
        el.classList.add('visible');
        setTimeout(() => el.classList.remove('visible'), 5000);
    }

    // =========================================================================
    // History tab
    // =========================================================================
    async function loadHistory() {
        const year = document.getElementById('filter-year').value;
        const area = document.getElementById('filter-area').value;
        const contentEl = document.getElementById('history-content');
        contentEl.innerHTML = '<div style="text-align:center;padding:20px;color:#9ca3af;">Loading...</div>';

        try {
            let url = '/api/spray?';
            if (year) url += `year=${year}&`;
            if (area) url += `area=${area}&`;

            const resp = await fetch(url);
            const apps = await resp.json();

            if (!apps.length) {
                contentEl.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📋</div>
                        <p>No applications found for this period</p>
                    </div>`;
                return;
            }

            contentEl.innerHTML = `
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Area</th>
                            <th>Method</th>
                            <th>Product</th>
                            <th>Rate</th>
                            <th>Total</th>
                            <th style="font-size:11px;">Weather</th>
                            <th style="font-size:11px;">Rating</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${apps.map(a => {
                            const isMix = a.products_json && a.products_json.length > 1;
                            let productCell, rateCell, totalCell;

                            if (isMix) {
                                const mixId = 'mix-' + a.id;
                                productCell = `
                                    <div style="font-weight:600">${escapeHtml(a.product_name)}</div>
                                    <span class="tank-mix-badge">Tank Mix (${a.products_json.length})</span>
                                    <button class="mix-expand-btn" onclick="toggleMixDetails('${mixId}')">details</button>
                                    <div class="mix-details" id="${mixId}">
                                        ${a.products_json.map(p => `
                                            <div style="padding:2px 0;">
                                                <span style="font-weight:500;color:#2d7a4a;cursor:pointer;text-decoration:underline;" onclick="openProductDetailModal('${(p.product_id||'').replace(/'/g,"\\'")}')">${escapeHtml(p.product_name)}</span>
                                                <span style="color:#9ca3af"> — ${p.rate} ${p.rate_unit}</span>
                                                ${p.total_product ? `<span style="color:#1a4d2e;font-weight:600"> → ${p.total_product} ${p.total_product_unit || ''}</span>` : ''}
                                            </div>
                                        `).join('')}
                                    </div>
                                `;
                                rateCell = `${a.products_json.length} products`;
                                totalCell = a.total_carrier_gallons ? `${a.total_carrier_gallons} gal` : '—';
                            } else {
                                productCell = `
                                    <div style="font-weight:600;color:#2d7a4a;cursor:pointer;text-decoration:underline;" onclick="openProductDetailModal('${(a.product_id||'').replace(/'/g,"\\'")}')">${escapeHtml(a.product_name)}</div>
                                    <div style="font-size:11px;color:#9ca3af">${a.product_category}</div>
                                `;
                                rateCell = `${a.rate} ${a.rate_unit}`;
                                totalCell = `<span style="font-weight:600">${a.total_product} ${a.total_product_unit || ''}</span>`;
                            }

                            const methodLabels = {
                                'spray_tank': 'Sprayer',
                                'push_spreader': 'Push Spreader',
                                'ride_on_spreader': 'Ride-On',
                                'hand_watering': 'Hand Water',
                                'fertigation': 'Fertigation',
                                'hose_end': 'Hose-End'
                            };
                            const methodLabel = methodLabels[a.application_method] || a.application_method || '—';

                            return `
                                <tr>
                                    <td>${a.date}</td>
                                    <td><span style="text-transform:capitalize">${a.area}</span></td>
                                    <td style="font-size:12px;">${methodLabel}</td>
                                    <td>${productCell}</td>
                                    <td>${rateCell}</td>
                                    <td>${totalCell}</td>
                                    <td style="font-size:11px;color:#6b7280;">
                                        ${a.weather_temp ? a.weather_temp + '°F' : ''}
                                        ${a.weather_conditions ? '<br>' + (a.weather_conditions || '').replace('_', ' ') : ''}
                                    </td>
                                    <td style="text-align:center;font-size:14px;cursor:pointer;" onclick="openEfficacyModal(${a.id}, ${a.efficacy_rating || 0})">
                                        ${a.efficacy_rating ? '<span style="color:#f59e0b;">' + '\u2605'.repeat(a.efficacy_rating) + '\u2606'.repeat(5 - a.efficacy_rating) + '</span>' : '<span style="color:#d1d5db;font-size:11px;">Rate</span>'}
                                    </td>
                                    <td>
                                        <button class="action-btn" onclick="duplicateSpray(${a.id})" title="Repeat this spray">🔁</button>
                                        <button class="action-btn" onclick="editSpray(${a.id})" title="Edit">✏️</button>
                                        <button class="action-btn" onclick="viewPdf(${a.id})" title="View PDF">📄</button>
                                        <button class="action-btn delete" onclick="deleteApp(${a.id})" title="Delete">🗑</button>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
                <div style="text-align:center;margin-top:12px;font-size:13px;color:#9ca3af;">
                    ${apps.length} application${apps.length !== 1 ? 's' : ''}
                </div>
            `;
        } catch (e) {
            contentEl.innerHTML = '<div class="empty-state"><p>Error loading history</p></div>';
        }
    }

    function viewPdf(id) {
        window.open(`/api/spray/pdf/single/${id}`, '_blank');
    }

    async function deleteApp(id) {
        if (!confirm('Delete this application? This cannot be undone.')) return;
        try {
            const resp = await fetch(`/api/spray/${id}`, { method: 'DELETE' });
            if (resp.ok) loadHistory();
        } catch (e) {}
    }

    let editingSprayId = null;

    async function editSpray(appId) {
        editingSprayId = appId;
        await duplicateSpray(appId);
        document.getElementById('submit-spray-btn').textContent = 'Update Application';
    }

    function downloadCsv() {
        const year = document.getElementById('filter-year')?.value || '';
        const area = document.getElementById('filter-area')?.value || '';
        let url = `/api/spray/csv?year=${year}`;
        if (area) url += `&area=${area}`;
        window.open(url, '_blank');
    }

    async function duplicateSpray(appId) {
        try {
            const resp = await fetch(`/api/spray/${appId}`);
            if (!resp.ok) return;
            const app = await resp.json();

            // Switch to Log tab
            switchTab('log');

            // Set date to today
            document.getElementById('spray-date').valueAsDate = new Date();
            // Set area
            if (app.area) {
                document.getElementById('spray-area').value = app.area;
                onAreaChange();
            }
            // Set method
            if (app.application_method) {
                document.getElementById('application-method').value = app.application_method;
                onMethodChange();
            }

            // Build product rows from stored data
            const products = (app.products_json && app.products_json.length > 0)
                ? app.products_json
                : [{
                    product_id: app.product_id,
                    product_name: app.product_name,
                    product_category: app.product_category,
                    rate: app.rate,
                    rate_unit: app.rate_unit
                }];

            productRows = [];
            nextRowId = 1;
            const isGranular = (app.application_method === 'push_spreader' || app.application_method === 'ride_on_spreader');

            for (const p of products) {
                const rowId = nextRowId++;
                const cached = allProducts.find(ap => ap.id === p.product_id);
                const product = cached || {
                    id: p.product_id,
                    display_name: p.product_name || 'Unknown Product',
                    category: p.product_category || '',
                    form_type: isGranular ? 'granular' : 'liquid'
                };
                productRows.push({
                    id: rowId,
                    product: product,
                    rate: p.rate || '',
                    rate_unit: p.rate_unit || (isGranular ? 'lbs/1000 sq ft' : 'fl oz/1000 sq ft'),
                    searchQuery: '',
                    searchResults: [],
                    showDropdown: false,
                    perTankAmt: '',
                    perTankUnit: isGranular ? 'lbs' : 'fl oz',
                    totalUsed: '',
                    totalUsedUnit: 'lbs'
                });
            }

            renderProductTable();
            recalcAllRows();

            // Set weather/notes
            if (app.weather_temp) document.getElementById('weather-temp').value = app.weather_temp;
            if (app.weather_wind) document.getElementById('weather-wind').value = app.weather_wind;
            if (app.weather_conditions) document.getElementById('weather-conditions').value = app.weather_conditions;
            if (app.notes) document.getElementById('spray-notes').value = app.notes;

            window.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (e) {
            console.error('Error duplicating spray:', e);
        }
    }

    // =========================================================================
    // Nutrients tab
    // =========================================================================
    async function loadNutrients() {
        const year = document.getElementById('nutrient-year').value;
        const contentEl = document.getElementById('nutrient-content');
        contentEl.innerHTML = '<div style="text-align:center;padding:20px;color:#9ca3af;">Loading...</div>';

        try {
            const resp = await fetch(`/api/spray/nutrients?year=${year}`);
            const data = await resp.json();

            if (!data.areas || Object.keys(data.areas).length === 0) {
                contentEl.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">🧪</div>
                        <p>No nutrient data for ${year}</p>
                    </div>`;
                return;
            }

            const cards = Object.entries(data.areas).map(([areaName, info]) => {
                if (info.applications_count === 0) return '';

                const nBudget = info.n_budget || {};
                const pct = Math.min(nBudget.pct || 0, 100);
                let barClass = 'green';
                if (pct > 90) barClass = 'red';
                else if (pct > 70) barClass = 'yellow';

                const nutrientRows = ['N', 'P2O5', 'K2O']
                    .filter(k => (info.per_1000[k] || 0) > 0)
                    .map(k => `
                        <tr>
                            <td style="font-weight:600">${k}</td>
                            <td>${info.per_1000[k].toFixed(3)} lbs</td>
                            <td>${info.totals[k].toFixed(2)} lbs</td>
                        </tr>
                    `).join('');

                return `
                    <div class="nutrient-card">
                        <h4>${areaName} ${info.acreage ? `(${info.acreage} ac)` : ''}</h4>
                        <div style="font-size:12px;color:#6b7280;margin-bottom:8px;">
                            ${info.applications_count} application${info.applications_count !== 1 ? 's' : ''}
                        </div>

                        <div style="font-weight:600;color:#374151;font-size:13px;margin-bottom:4px;">
                            Nitrogen Budget
                        </div>
                        <div class="budget-amount">
                            ${(nBudget.applied || 0).toFixed(2)}
                            <span style="font-size:13px;font-weight:400;color:#6b7280">
                                / ${nBudget.target || 0} lbs N/1000 ft²
                            </span>
                        </div>
                        <div class="budget-bar">
                            <div class="fill ${barClass}" style="width:${pct}%"></div>
                        </div>
                        <div class="budget-label">
                            <span>${pct.toFixed(0)}% applied</span>
                            <span>${(nBudget.remaining || 0).toFixed(2)} remaining</span>
                        </div>

                        ${nutrientRows ? `
                            <table class="nutrient-detail-table">
                                <thead>
                                    <tr><th>Nutrient</th><th>Per 1000 ft²</th><th>Total</th></tr>
                                </thead>
                                <tbody>${nutrientRows}</tbody>
                            </table>
                        ` : ''}
                    </div>
                `;
            }).filter(Boolean);

            if (cards.length === 0) {
                contentEl.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">🧪</div>
                        <p>No fertilizer applications logged for ${year}</p>
                    </div>`;
                return;
            }

            contentEl.innerHTML = `<div class="nutrient-cards">${cards.join('')}</div>`;

            // Populate compare year dropdown
            const compareSelect = document.getElementById('compare-year');
            if (compareSelect) {
                const currentYear = new Date().getFullYear();
                const currentVal = compareSelect.value;
                compareSelect.innerHTML = '<option value="">Compare year...</option>';
                for (let y = currentYear; y >= currentYear - 5; y--) {
                    if (String(y) !== year) {
                        compareSelect.innerHTML += `<option value="${y}" ${String(y) === currentVal ? 'selected' : ''}>${y}</option>`;
                    }
                }
            }

            // Load monthly breakdown chart
            loadMonthlyNutrients();
        } catch (e) {
            contentEl.innerHTML = '<div class="empty-state"><p>Error loading nutrient data</p></div>';
        }
    }

    function downloadSprayReport() {
        const year = document.getElementById('filter-year')?.value || '';
        const area = document.getElementById('filter-area')?.value || '';
        let url = `/api/spray/pdf/report?year=${year}`;
        if (area) url += `&area=${area}`;
        window.open(url, '_blank');
    }

    function downloadNutrientReport() {
        const year = document.getElementById('nutrient-year').value;
        window.open(`/api/spray/pdf/nutrients?year=${year}`, '_blank');
    }

    function downloadSeasonalReport() {
        const year = document.getElementById('nutrient-year').value;
        window.open(`/api/spray/pdf/report?year=${year}`, '_blank');
    }

    // =========================================================================
    // Custom product modal
    // =========================================================================
    function openCustomProductModal() {
        document.getElementById('custom-product-modal').classList.add('visible');
    }

    function closeCustomProductModal() {
        document.getElementById('custom-product-modal').classList.remove('visible');
    }

    async function saveCustomProduct() {
        const name = document.getElementById('cp-name').value.trim();
        if (!name) {
            alert('Product name is required');
            return;
        }

        const n = parseFloat(document.getElementById('cp-n').value) || 0;
        const p = parseFloat(document.getElementById('cp-p').value) || 0;
        const k = parseFloat(document.getElementById('cp-k').value) || 0;

        const data = {
            product_name: name,
            brand: document.getElementById('cp-brand').value.trim(),
            product_type: document.getElementById('cp-type').value,
            form_type: document.getElementById('cp-form').value,
            npk: (n || p || k) ? [n, p, k] : null,
            default_rate: parseFloat(document.getElementById('cp-rate').value) || null,
            rate_unit: document.getElementById('cp-rate-unit').value,
            density_lbs_per_gallon: parseFloat(document.getElementById('cp-density').value) || null,
        };

        try {
            const resp = await fetch('/api/custom-products', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await resp.json();
            if (resp.ok && result.success) {
                closeCustomProductModal();
                // Reload products and update inventory
                const productsResp = await fetch('/api/products/all');
                if (productsResp.ok) allProducts = await productsResp.json();
                if (result.product_id) {
                    inventoryIds.add(result.product_id);
                    updateInventoryCount();
                }
                // Clear modal fields
                ['cp-name','cp-brand','cp-n','cp-p','cp-k','cp-rate','cp-density'].forEach(id => {
                    document.getElementById(id).value = '';
                });
                alert('Custom product saved!');
            } else {
                alert(result.error || 'Failed to save product');
            }
        } catch (e) {
            alert('Connection error');
        }
    }

    // =========================================================================
    // Product detail modal
    // =========================================================================
    function openProductDetailModal(productId) {
        fetch(`/api/products/${encodeURIComponent(productId)}`)
            .then(r => r.json())
            .then(p => {
                if (p.error) return;
                document.getElementById('pd-title').textContent = p.display_name || 'Product Details';
                let html = '';
                html += `<div style="margin-bottom:12px;"><span class="category-badge badge-${p.category}">${escapeHtml(p.category || '')}</span></div>`;

                function row(label, value) {
                    return `<div style="display:flex;padding:8px 0;border-bottom:1px solid #f3f4f6;">
                        <span style="width:150px;font-size:13px;color:#6b7280;flex-shrink:0;">${label}</span>
                        <span style="font-size:14px;font-weight:500;color:#1f2937;">${escapeHtml(String(value))}</span>
                    </div>`;
                }

                if (p.brand) html += row('Brand', p.brand);
                if (p.active_ingredient) html += row('Active Ingredient', p.active_ingredient);
                if (p.form_type) html += row('Form Type', p.form_type);
                if (p.frac_code) html += row('FRAC Code', p.frac_code);
                if (p.hrac_group) html += row('HRAC Group', p.hrac_group);
                if (p.irac_group) html += row('IRAC Group', p.irac_group);
                if (p.npk && p.npk.length) html += row('NPK', p.npk.join('-'));
                if (p.secondary_nutrients) {
                    const sn = Object.entries(p.secondary_nutrients)
                        .filter(([k,v]) => v > 0).map(([k,v]) => k + ': ' + v + '%').join(', ');
                    if (sn) html += row('Secondary Nutrients', sn);
                }
                if (p.default_rate) html += row('Default Rate', p.default_rate + ' ' + (p.rate_unit || ''));
                if (p.density_lbs_per_gallon) html += row('Density', p.density_lbs_per_gallon + ' lbs/gal');
                if (p.targets && p.targets.length) html += row('Targets', p.targets.join(', '));
                if (p.trade_names && p.trade_names.length > 1) html += row('Trade Names', p.trade_names.join(', '));
                if (p.notes) html += row('Notes', p.notes);

                document.getElementById('pd-body').innerHTML = html;
                document.getElementById('product-detail-modal').classList.add('visible');
            })
            .catch(() => {});
    }

    function closeProductDetailModal() {
        document.getElementById('product-detail-modal').classList.remove('visible');
    }

    // =========================================================================
    // Spray Templates (Feature 5)
    // =========================================================================
    let sprayTemplates = [];

    async function loadTemplates() {
        try {
            const resp = await fetch('/api/spray-templates');
            if (resp.ok) sprayTemplates = await resp.json();
            populateTemplateDropdown();
        } catch (e) {}
    }

    function populateTemplateDropdown() {
        const sel = document.getElementById('template-select');
        if (!sel) return;
        sel.innerHTML = '<option value="">Load template...</option>';
        sprayTemplates.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name + (t.products_json ? ` (${t.products_json.length})` : '');
            sel.appendChild(opt);
        });
    }

    function loadTemplate() {
        const sel = document.getElementById('template-select');
        const tid = parseInt(sel.value);
        if (!tid) return;
        const template = sprayTemplates.find(t => t.id === tid);
        if (!template) return;

        // Set method if stored
        if (template.application_method) {
            document.getElementById('application-method').value = template.application_method;
            onMethodChange();
        }

        const isGranular = (template.application_method === 'push_spreader' || template.application_method === 'ride_on_spreader');
        productRows = [];
        nextRowId = 1;

        (template.products_json || []).forEach(p => {
            const rowId = nextRowId++;
            const cached = allProducts.find(ap => ap.id === p.product_id);
            productRows.push({
                id: rowId,
                product: cached || { id: p.product_id, display_name: p.product_name || 'Unknown', category: '', form_type: isGranular ? 'granular' : 'liquid' },
                rate: p.rate || '',
                rate_unit: p.rate_unit || (isGranular ? 'lbs/1000 sq ft' : 'fl oz/1000 sq ft'),
                searchQuery: '', searchResults: [], showDropdown: false,
                perTankAmt: '', perTankUnit: isGranular ? 'lbs' : 'fl oz',
                totalUsed: '', totalUsedUnit: 'lbs'
            });
        });

        renderProductTable();
        recalcAllRows();

        // Show delete button
        document.getElementById('delete-template-btn').style.display = 'inline';
    }

    async function saveAsTemplate() {
        const activeRows = productRows.filter(r => r.product);
        if (!activeRows.length) {
            alert('Add products before saving a template');
            return;
        }
        const name = prompt('Template name:');
        if (!name) return;

        const products = activeRows.map(r => ({
            product_id: r.product.id,
            product_name: r.product.display_name,
            rate: r.rate,
            rate_unit: r.rate_unit
        }));

        try {
            const resp = await fetch('/api/spray-templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    products,
                    application_method: document.getElementById('application-method').value
                })
            });
            if (resp.ok) {
                await loadTemplates();
                alert('Template saved!');
            }
        } catch (e) {}
    }

    async function deleteCurrentTemplate() {
        const sel = document.getElementById('template-select');
        const tid = parseInt(sel.value);
        if (!tid) return;
        if (!confirm('Delete this template?')) return;
        try {
            await fetch(`/api/spray-templates/${tid}`, { method: 'DELETE' });
            await loadTemplates();
            document.getElementById('delete-template-btn').style.display = 'none';
        } catch (e) {}
    }

    // =========================================================================
    // MOA Rotation Warnings (Feature 6)
    // =========================================================================
    async function checkMoaRotation(rowId, area, product) {
        if (!area || (!product.frac_code && !product.hrac_group && !product.irac_group)) return;
        const params = new URLSearchParams({ area });
        if (product.frac_code) params.append('frac_code', product.frac_code);
        if (product.hrac_group) params.append('hrac_group', product.hrac_group);
        if (product.irac_group) params.append('irac_group', product.irac_group);

        try {
            const resp = await fetch(`/api/spray/moa-check?${params}`);
            const data = await resp.json();
            const warnEl = document.getElementById('moa-warn-' + rowId);
            if (warnEl && data.warnings && data.warnings.length) {
                warnEl.textContent = '⚠️ ' + data.warnings[0];
                warnEl.style.display = 'block';
            } else if (warnEl) {
                warnEl.style.display = 'none';
            }
        } catch (e) {}
    }

    // =========================================================================
    // Efficacy Tracking (Feature 10)
    // =========================================================================
    let efficacyAppId = null;
    let efficacyRating = 0;

    function openEfficacyModal(appId, existingRating) {
        efficacyAppId = appId;
        efficacyRating = existingRating || 0;
        renderEfficacyStars();
        document.getElementById('efficacy-notes').value = '';
        document.getElementById('efficacy-modal').classList.add('visible');
    }

    function renderEfficacyStars() {
        const container = document.getElementById('efficacy-stars');
        container.innerHTML = [1,2,3,4,5].map(i =>
            `<span onclick="efficacyRating=${i};renderEfficacyStars()" style="cursor:pointer;font-size:32px;color:${i <= efficacyRating ? '#f59e0b' : '#d1d5db'}">${i <= efficacyRating ? '\u2605' : '\u2606'}</span>`
        ).join(' ');
    }

    async function saveEfficacy() {
        if (!efficacyAppId || !efficacyRating) return;
        try {
            await fetch(`/api/spray/${efficacyAppId}/efficacy`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    efficacy_rating: efficacyRating,
                    efficacy_notes: document.getElementById('efficacy-notes').value
                })
            });
            closeEfficacyModal();
            loadHistory();
        } catch (e) {}
    }

    function closeEfficacyModal() {
        document.getElementById('efficacy-modal').classList.remove('visible');
    }

    // =========================================================================
    // Monthly Nutrient Breakdown (Feature 9)
    // =========================================================================
    async function loadMonthlyNutrients() {
        const year = document.getElementById('nutrient-year').value;
        const compareYear = document.getElementById('compare-year')?.value || '';
        const container = document.getElementById('monthly-chart');
        if (!container) return;

        try {
            let url = `/api/spray/nutrients/monthly?year=${year}`;
            if (compareYear) url += `&compare_year=${compareYear}`;
            const resp = await fetch(url);
            const data = await resp.json();

            const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            const primary = data.primary?.months || {};

            // Aggregate all areas for N
            const monthlyN = {};
            for (let m = 1; m <= 12; m++) {
                monthlyN[m] = 0;
                if (primary[m]) {
                    Object.values(primary[m]).forEach(area => { monthlyN[m] += area.N || 0; });
                }
            }

            let maxN = Math.max(...Object.values(monthlyN), 0.1);

            // Compare year data
            let compareN = null;
            if (data.compare?.months) {
                compareN = {};
                for (let m = 1; m <= 12; m++) {
                    compareN[m] = 0;
                    if (data.compare.months[m]) {
                        Object.values(data.compare.months[m]).forEach(area => { compareN[m] += area.N || 0; });
                    }
                }
                const maxCompare = Math.max(...Object.values(compareN), 0);
                if (maxCompare > maxN) maxN = maxCompare; // Note: this won't work with const
            }

            let html = '<div style="margin-top:12px;">';
            for (let m = 1; m <= 12; m++) {
                const val = monthlyN[m];
                const pct = maxN > 0 ? (val / maxN * 100) : 0;
                html += `
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <span style="width:30px;font-size:12px;color:#6b7280;text-align:right;">${monthNames[m-1]}</span>
                        <div style="flex:1;background:#f3f4f6;border-radius:4px;height:20px;position:relative;">
                            <div style="background:#1a4d2e;height:100%;border-radius:4px;width:${pct}%;min-width:${val > 0 ? '2px' : '0'};"></div>
                            ${compareN ? `<div style="position:absolute;top:0;left:0;background:rgba(59,130,246,0.4);height:100%;border-radius:4px;width:${maxN > 0 ? (compareN[m]/maxN*100) : 0}%;"></div>` : ''}
                        </div>
                        <span style="width:50px;font-size:12px;font-weight:600;color:#374151;">${val > 0 ? val.toFixed(2) : '—'}</span>
                    </div>
                `;
            }
            html += '</div>';
            if (compareN) {
                html += `<div style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:#6b7280;">
                    <span><span style="display:inline-block;width:12px;height:12px;background:#1a4d2e;border-radius:2px;vertical-align:middle;margin-right:4px;"></span>${year}</span>
                    <span><span style="display:inline-block;width:12px;height:12px;background:rgba(59,130,246,0.4);border-radius:2px;vertical-align:middle;margin-right:4px;"></span>${compareYear}</span>
                </div>`;
            }

            container.innerHTML = html;
            document.getElementById('monthly-breakdown').style.display = 'block';
        } catch (e) {
            container.innerHTML = '';
        }
    }

    // =========================================================================
    // Mobile menu
    // =========================================================================
    function toggleMobileMenu() {
        // Simple redirect for mobile since we don't have full mobile nav here
        const links = document.querySelector('.nav-links');
        if (links.style.display === 'flex') {
            links.style.display = 'none';
        } else {
            links.style.display = 'flex';
            links.style.flexDirection = 'column';
            links.style.position = 'absolute';
            links.style.top = '100%';
            links.style.left = '0';
            links.style.right = '0';
            links.style.background = '#1a4d2e';
            links.style.padding = '12px 24px';
            links.style.gap = '12px';
        }
    }

    // =========================================================================
    // Utility
    // =========================================================================
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatSecondaryBrief(product) {
        const sec = product.secondary_nutrients;
        if (!sec) return '';
        const parts = [];
        if (sec.Fe > 0) parts.push(`${sec.Fe}%Fe`);
        if (sec.S > 0) parts.push(`${sec.S}%S`);
        if (sec.Mn > 0) parts.push(`${sec.Mn}%Mn`);
        if (sec.Mg > 0) parts.push(`${sec.Mg}%Mg`);
        if (sec.Ca > 0) parts.push(`${sec.Ca}%Ca`);
        if (sec.Zn > 0) parts.push(`${sec.Zn}%Zn`);
        if (!parts.length) return '';
        return ' · ' + parts.join(' ');
    }

    function toggleMixDetails(id) {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('visible');
    }

    // =========================================================================
    // Inventory Tab
    // =========================================================================
    let inventoryProducts = [];  // full product dicts for user's inventory
    let invSearchTimeout = null;

    async function initLibrary() {
        await loadInventoryProducts();
        await loadInventoryQuantities();
    }

    async function loadInventoryProducts() {
        try {
            const resp = await fetch('/api/inventory');
            const data = await resp.json();
            inventoryProducts = data.products || [];
        } catch (e) {
            inventoryProducts = [];
        }
        updateInventoryCount();
        renderInventoryList();
    }

    let inventoryQuantities = {};

    async function loadInventoryQuantities() {
        try {
            const resp = await fetch('/api/inventory/quantities');
            if (resp.ok) inventoryQuantities = await resp.json();
        } catch (e) {}
    }

    async function updateQuantity(productId, qty, unit) {
        try {
            await fetch('/api/inventory/quantities', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ product_id: productId, quantity: parseFloat(qty) || 0, unit })
            });
            inventoryQuantities[productId] = { ...(inventoryQuantities[productId] || {}), quantity: parseFloat(qty) || 0, unit };
        } catch (e) {}
    }

    function renderInventoryList() {
        const container = document.getElementById('inv-list');
        const catFilter = document.getElementById('inv-category-filter')?.value || '';

        let items = inventoryProducts;
        if (catFilter) {
            items = items.filter(p => p.category === catFilter);
        }

        if (!items.length) {
            if (!inventoryProducts.length) {
                container.innerHTML = '<div style="padding:24px;text-align:center;color:#9ca3af;">Your inventory is empty. Use the search above to find and add products, or they\'ll be added automatically when you log sprays.</div>';
            } else {
                container.innerHTML = '<div style="padding:24px;text-align:center;color:#9ca3af;">No products match this filter.</div>';
            }
            return;
        }

        container.innerHTML = items.map(p => {
            const q = inventoryQuantities[p.id] || {};
            const qty = q.quantity || '';
            const unit = q.unit || (p.form_type === 'liquid' ? 'gal' : 'lbs');
            const escapedId = p.id.replace(/'/g, "\\'");
            return `
                <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #f3f4f6;gap:8px;">
                    <div style="min-width:0;flex:1;cursor:pointer;" onclick="openProductDetailModal('${escapedId}')">
                        <div style="font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#2d7a4a;">${escapeHtml(p.display_name)}</div>
                        <div style="font-size:12px;color:#6b7280;">${escapeHtml(p.brand || '')}</div>
                    </div>
                    <div style="display:flex;align-items:center;gap:4px;flex-shrink:0;">
                        <input type="number" value="${qty}" placeholder="Qty" step="0.1" min="0"
                            onchange="updateQuantity('${escapedId}', this.value, this.nextElementSibling.value)"
                            style="width:55px;padding:3px 5px;border:1px solid #d1d5db;border-radius:4px;font-size:12px;text-align:right;">
                        <select onchange="updateQuantity('${escapedId}', this.previousElementSibling.value, this.value)"
                            style="padding:3px;border:1px solid #d1d5db;border-radius:4px;font-size:11px;">
                            <option value="lbs" ${unit === 'lbs' ? 'selected' : ''}>lbs</option>
                            <option value="oz" ${unit === 'oz' ? 'selected' : ''}>oz</option>
                            <option value="gal" ${unit === 'gal' ? 'selected' : ''}>gal</option>
                            <option value="fl oz" ${unit === 'fl oz' ? 'selected' : ''}>fl oz</option>
                            <option value="bags" ${unit === 'bags' ? 'selected' : ''}>bags</option>
                        </select>
                    </div>
                    <button onclick="removeInventoryItem('${escapedId}')"
                        style="padding:5px 10px;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;flex-shrink:0;
                        background:white;color:#dc2626;border:1px solid #fecaca;">
                        Remove
                    </button>
                </div>
            `;
        }).join('');
    }

    async function removeInventoryItem(productId) {
        await removeFromInventory(productId);
        inventoryProducts = inventoryProducts.filter(p => p.id !== productId);
        renderInventoryList();
    }

    function onInvAddSearch() {
        clearTimeout(invSearchTimeout);
        const query = (document.getElementById('inv-add-search')?.value || '').trim();
        const dropdown = document.getElementById('inv-add-dropdown');

        if (query.length < 2) {
            dropdown.style.display = 'none';
            return;
        }

        invSearchTimeout = setTimeout(async () => {
            try {
                const resp = await fetch(`/api/products/search?q=${encodeURIComponent(query)}&scope=all`);
                const results = await resp.json();

                if (!results.length) {
                    dropdown.innerHTML = '<div style="padding:10px;color:#9ca3af;font-size:13px;">No products found</div>';
                    dropdown.style.display = 'block';
                    return;
                }

                dropdown.innerHTML = results.map(p => {
                    const inInv = inventoryIds.has(p.id);
                    return `
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid #f3f4f6;cursor:pointer;${inInv ? 'background:#f0fdf4;' : ''}"
                            onmouseenter="this.style.background='${inInv ? '#dcfce7' : '#f9fafb'}'"
                            onmouseleave="this.style.background='${inInv ? '#f0fdf4' : 'white'}'">
                            <div style="min-width:0;flex:1;">
                                <div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(p.display_name)}</div>
                                <div style="font-size:11px;color:#6b7280;">${escapeHtml(p.brand || '')}</div>
                            </div>
                            ${inInv
                                ? '<span style="font-size:11px;color:#166534;font-weight:600;flex-shrink:0;margin-left:8px;">✓ Added</span>'
                                : `<button onmousedown="event.stopPropagation(); addInvProduct('${p.id.replace(/'/g, "\\'")}')"
                                    style="padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;cursor:pointer;flex-shrink:0;margin-left:8px;
                                    background:#1a4d2e;color:white;border:none;">+ Add</button>`
                            }
                        </div>
                    `;
                }).join('');
                dropdown.style.display = 'block';
            } catch (e) {
                dropdown.style.display = 'none';
            }
        }, 250);
    }

    async function addInvProduct(productId) {
        await addToInventory(productId);
        // Reload full inventory to get the product dict
        await loadInventoryProducts();
        // Re-render the add dropdown to show updated state
        onInvAddSearch();
    }
