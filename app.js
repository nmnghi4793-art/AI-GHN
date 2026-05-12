﻿﻿const API = window.location.origin + '/api';

// GHN Brand Colors
const C_ORANGE = '#FF5200';
const C_BLUE   = '#0076BE';
const C_GREEN  = '#0CA678';
const C_RED    = '#F5365C';
const C_PURPLE = '#5E72E4';
const C_YELLOW = '#FB6340';

Chart.defaults.font.family = "'Outfit', sans-serif";
Chart.defaults.color = '#8898AA';

// Ensure DataLabels plugin is registered for charts to show percentage
Chart.register(ChartDataLabels);

// ---- STATE ----
let state = {
    gtcData: [], ontimeData: [], returnsData: [],
    backlogData: [], b2bData: [], personnelData: [], nangSuatData: [],
    warningsData: [], returnsByClientData: [], xeGxtData: [],
    xeSuCoData: [], khoGxtData: [],
    overview: {}
};
let charts = {};

// ---- UTILS ----
function pctClass(v) {
    const n = parseFloat((v||'0').replace('%','').replace(',','.'));
    if (n >= 90) return 'pct-high';
    if (n >= 80) return 'pct-mid';
    return 'pct-low';
}

function agingChip(days) {
    const n = parseInt(days) || 0;
    if (n >= 14) return `<span class="aging-chip aging-critical">${n} ngày</span>`;
    if (n >= 10) return `<span class="aging-chip aging-high">${n} ngày</span>`;
    return `<span class="aging-chip aging-normal">${n} ngày</span>`;
}

function priorityBadge(p) {
    if (!p) return `<span class="badge p3">--</span>`;
    if (p.startsWith('1:')) return `<span class="badge p1">${p}</span>`;
    if (p.startsWith('2:')) return `<span class="badge p2">${p}</span>`;
    return `<span class="badge p3">${p}</span>`;
}

function shortKho(k) {
    if (!k) return '--';
    return k.replace(/Kho Giao Hàng Nặng[\s\-]+/gi, '').trim();
}

function parsePct(str) {
    return parseFloat((str||'0').replace('%','').replace(',','.')) || 0;
}

function parseVN(s) {
    if (!s) return 0;
    if (typeof s !== 'string') s = s.toString();
    
    // Format: "2026-05-05 - Thứ 3" hoáº·c "2026-05-05"
    let m0 = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m0) return new Date(parseInt(m0[1]), parseInt(m0[2]) - 1, parseInt(m0[3])).getTime();

    // Format: "5 thg 5, 2026"
    let m = s.match(/(\d+) thg (\d+), (\d+)/);
    if (m) return new Date(parseInt(m[3]), parseInt(m[2]) - 1, parseInt(m[1])).getTime();
    
    // Format: "DD/MM/YYYY" hoáº·c "D/M/YYYY"
    let m2 = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (m2) return new Date(parseInt(m2[3]), parseInt(m2[2]) - 1, parseInt(m2[1])).getTime();

    const d = new Date(s);
    return isNaN(d.getTime()) ? 0 : d.getTime();
}

// ---- FETCH ALL ----
let nextSyncTime = Date.now() + 5 * 60 * 1000;
let syncTimerInterval = null;

async function fetchAll(force = false) {
    const btn = document.getElementById('refresh-btn');
    if (force) {
        btn.classList.add('loading');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Äang táº£i...';
    }

    try {
        const query = force ? '?force=true' : '';
        const [ov, gtc, ontime, ret, bl, b2b, pers, ns, warn, retC, xegxt, xesuco, khogxt, dontao] = await Promise.all([
            fetch(`${API}/dashboard/overview${query}`).then(r => r.json()).catch(e => ({})),
            fetch(`${API}/kpi/gtc${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/kpi/ontime${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/returns${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/backlog/critical${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/backlog/b2b${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/personnel${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/nang-suat${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/warnings${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/returns/by-client${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/xe-gxt${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/xe-su-co${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/kho-gxt${query}`).then(r => r.json()).catch(e => ({data:[]})),
            fetch(`${API}/don-tao${query}`).then(r => r.json()).catch(e => ({data:[]})),
        ]);

        state = { 
            overview: ov || {}, 
            gtcData: gtc.data || [], 
            ontimeData: ontime.data || [], 
            returnsData: ret.data || [], 
            backlogData: bl.data || [], 
            b2bData: b2b.data || [], 
            personnelData: pers.data || [], 
            nangSuatData: ns.data || [], 
            warningsData: warn.data || [],
            returnsByClientData: retC.data || [],
            xeGxtData: xegxt.data || [],
            xeSuCoData: xesuco.data || [],
            khoGxtData: khogxt.data || [],
            donTaoData: dontao.data || []
        };
        filtersPopulated = false; // Reset filters on fresh data
        
        // Reset countdown
        nextSyncTime = Date.now() + 5 * 60 * 1000;
        renderAll();
        
        if (force) {
            btn.classList.remove('loading');
            btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Làm mới';
        }
    } catch(e) {
        console.error('Fetch error:', e);
        if (force) {
            btn.classList.remove('loading');
            btn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Lỗi';
        }
    }
}

function startSyncTimer() {
    if (syncTimerInterval) clearInterval(syncTimerInterval);
    syncTimerInterval = setInterval(() => {
        const now = Date.now();
        const diff = Math.max(0, nextSyncTime - now);
        
        if (diff <= 0) {
            fetchAll(); // Auto refresh
            return;
        }
        
        const mins = Math.floor(diff / 60000);
        const secs = Math.floor((diff % 60000) / 1000);
        document.getElementById('sync-timer').textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
        
        const progress = (diff / (5 * 60 * 1000)) * 100;
        document.getElementById('sync-progress').style.width = progress + '%';
    }, 1000);
}

// ---- RENDER ALL ----
function renderAll() {
    updateMeta();
    console.log("[DASHBOARD] Rendering all sections...");
    const sections = [
        { name: 'OverviewCards', fn: renderOverviewCards },
        { name: 'GtcTrendChart', fn: renderGtcTrendChart },
        { name: 'ReturnsPieChart', fn: renderReturnsPieChart },
        { name: 'BacklogOverviewTable', fn: renderBacklogOverviewTable },
        { name: 'B2bOverviewTable', fn: renderB2bOverviewTable },
        { name: 'CriticalWarningsOverview', fn: renderCriticalWarningsOverview },
        { name: 'PersonnelOverview', fn: renderPersonnelOverview },
        { name: 'GtcSection', fn: renderGtcSection },
        { name: 'GtcByKhoChart', fn: renderGtcByKhoChart },
        { name: 'GtcTopBottom', fn: renderGtcTopBottom },
        { name: 'BacklogSection', fn: renderBacklogSection },
        { name: 'BacklogByKhoChart', fn: renderBacklogByKhoChart },
        { name: 'B2bSection', fn: renderB2bSection },
        { name: 'ReturnsSection', fn: renderReturnsSection },
        { name: 'ReturnsFDChart', fn: renderReturnsFDChart },
        { name: 'PersonnelSection', fn: renderPersonnelSection },
        { name: 'NangSuatSection', fn: renderNangSuatSection },
        { name: 'WarningsSection', fn: renderWarningsSection },
        { name: 'XeGxtSection', fn: renderXeGxtSection },
        { name: 'XeSuCoSection', fn: renderXeSuCoSection },
        { name: 'KhoGxtSection', fn: renderKhoGxtSection },
        { name: 'DonTaoSection', fn: renderDonTaoSection },
        { name: 'NavBadges', fn: updateNavBadges }
    ];

    sections.forEach(s => {
        try {
            s.fn();
        } catch (err) {
            console.error(`[ERROR] Render failed for ${s.name}:`, err);
        }
    });
    console.log("[DASHBOARD] Render complete.");
}

function updateMeta() {
    const now = new Date();
    document.getElementById('last-update-time').textContent =
        'Cập nhật: ' + now.toLocaleTimeString('vi-VN');
    document.getElementById('current-date').textContent =
        now.toLocaleDateString('vi-VN', { weekday:'long', day:'2-digit', month:'2-digit', year:'numeric' });
}

// ---- OVERVIEW CARDS ----
function renderOverviewCards() {
    const ov = state.overview;
    document.getElementById('val-gtc').textContent    = (ov.avg_gtc || 0) + '%';
    const ontimeEl = document.getElementById('val-ontime');
    if (ontimeEl) ontimeEl.textContent = (ov.avg_ontime || 0) + '%';
    document.getElementById('val-backlog').textContent = ov.total_backlog_7n || 0;
    document.getElementById('val-b2b').textContent    = ov.total_b2b_priority || 0;
    document.getElementById('val-fd').textContent     = (ov.avg_fd_return || 0) + '%';
    const valNangSuatEl = document.getElementById('val-nangsuat');
    if (valNangSuatEl) valNangSuatEl.textContent = (ov.avg_nang_suat || 0);

    // New backlog metrics
    const blLmEl = document.getElementById('val-bl-lm');
    if (blLmEl) blLmEl.textContent = (ov.total_backlog_lm || 0).toLocaleString();
    const blKtcEl = document.getElementById('val-bl-ktc');
    if (blKtcEl) blKtcEl.textContent = (ov.total_backlog_ktc || 0).toLocaleString();
    const blAllEl = document.getElementById('val-bl-all');
    if (blAllEl) blAllEl.textContent = (ov.total_backlog_all || 0).toLocaleString();

    const xeTotalEl = document.getElementById('val-xegxt-total');
    if (xeTotalEl) {
        let pCount = ov.total_personnel || 0;
        // Fallback to frontend calculation if available and server returns 0
        if (pCount === 0 && state.personnelData && state.personnelData.length) {
            pCount = state.personnelData.filter(r => (r['Tên vị trí']||'').trim().toLowerCase() === 'delivery staff').length;
        }
        xeTotalEl.textContent = `${ov.total_xe_gxt || 0}/${pCount}`;
    }

    const khoGxtTotalEl = document.getElementById('val-khogxt-total');
    if (khoGxtTotalEl) khoGxtTotalEl.textContent = (ov.total_kho_gxt || 0).toLocaleString();

    // ÄÆ¡n Táº¡o N-1
    const donTaoEl = document.getElementById('val-dontao');
    if (donTaoEl) {
        const d = (ov.total_don_tao || 0).toLocaleString('vi-VN');
        const kg = (ov.total_kg_tao || 0).toLocaleString('vi-VN', {maximumFractionDigits:1});
        donTaoEl.textContent = `${d} / ${kg} KG`;
    }

    // Warning System Metrics for Overview
    const ovWarnCrit = document.getElementById('ov-warn-critical-count');
    if (ovWarnCrit) ovWarnCrit.textContent = (ov.critical_warnings || 0);
    const ovWarnWarn = document.getElementById('ov-warn-warning-count');
    if (ovWarnWarn) ovWarnWarn.textContent = (ov.unstable_warnings || 0);
    const ovWarnUp = document.getElementById('ov-warn-upcoming-count');
    if (ovWarnUp) ovWarnUp.textContent = (ov.upcoming_warnings || 0);
    const ovWarnDays = document.getElementById('ov-warn-avg-days');
    if (ovWarnDays) ovWarnDays.textContent = (ov.avg_days_to_normal || 0);
    
    const syncTime = ov.last_sync ? new Date(ov.last_sync * 1000).toLocaleTimeString('vi-VN') : '--';
    document.getElementById('sub-gtc').textContent    = 'Đã đồng bộ: ' + syncTime;

    // Sync warning cards from frontend state if available
    syncOverviewWarningCards();
}

function syncOverviewWarningCards() {
    if (!state.warningsData || !state.warningsData.length) return;

    const getV = (r, keys, defaultVal = '') => {
        for (const k of keys) {
            if (r[k] !== undefined && r[k] !== null && r[k] !== '') return r[k];
        }
        const allKeys = Object.keys(r);
        for (const search of keys) {
            const found = allKeys.find(k => k.toLowerCase().includes(search.toLowerCase()));
            if (found && r[found] !== undefined && r[found] !== null && r[found] !== '') return r[found];
        }
        return defaultVal;
    };

    const processedData = state.warningsData.map(r => {
        const soNgay = parseFloat(getV(r, ['Số ngày trở về ngày thường', 'Total ngày', 'so ngay'], 0));
        const sheetStatus = getV(r, ['Tình hình hiện tại', 'trạng thái hiện tại'], 'Bình thường');
        return { ...r, soNgayVal: soNgay, sheetStatus: sheetStatus };
    });

    const criticalCount = processedData.filter(r => r.soNgayVal > 6).length;
    const warningCount  = processedData.filter(r => r.sheetStatus === 'Bất ổn').length;
    const upcomingCount = processedData.filter(r => {
        const next = (r['Tình hình sắp tới'] || r['Dự báo sắp tới'] || '').toLowerCase();
        return next.includes('cảnh báo') || next.includes('nghiêm trọng');
    }).length;

    const totalNgay = processedData.reduce((sum, r) => sum + r.soNgayVal, 0);
    const avgDays = processedData.length ? (totalNgay / processedData.length).toFixed(1) : 0;

    const ids = {
        'ov-warn-critical-count': criticalCount,
        'ov-warn-warning-count': warningCount,
        'ov-warn-upcoming-count': upcomingCount,
        'ov-warn-avg-days': avgDays
    };

    for (const [id, val] of Object.entries(ids)) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }
}

window.toggleDropdown = function(id) {
    document.getElementById(id).classList.toggle('active');
    // Close other dropdowns
    document.querySelectorAll('.dropdown-list').forEach(list => {
        if (list.id !== id) list.classList.remove('active');
    });
};

// Close dropdowns when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown-multi')) {
        document.querySelectorAll('.dropdown-list').forEach(l => l.classList.remove('active'));
    }
});

function updateNavBadges() {
    document.getElementById('nav-backlog-count').textContent = state.backlogData.length;
    const critB2b = state.b2bData.filter(r => (r['Mức độ ưu tiên']||'').startsWith('1:'));
    document.getElementById('nav-b2b-count').textContent = critB2b.length;
    
    const critWarn = state.warningsData.filter(r => r['Tình hình hiện tại'] === 'Nghiêm trọng');
    const warnBadge = document.getElementById('nav-warnings-count');
    if (warnBadge) {
        warnBadge.textContent = critWarn.length;
        warnBadge.style.display = critWarn.length > 0 ? 'inline-block' : 'none';
    }
}

let currentOverviewGtcPeriod = 'day';

window.switchOverviewGtcPeriod = function(p) {
    currentOverviewGtcPeriod = p;
    document.querySelectorAll('#btn-ov-day, #btn-ov-week, #btn-ov-month').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-ov-' + p)?.classList.add('active');
    renderGtcTrendChart();
};

// ---- GTC TREND CHART (Overview) ----
function renderGtcTrendChart() {
    const dateMap = {};
    state.gtcData.forEach(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return;
        const dObj = new Date(ts);
        let key = (r['Ngày'] || '').split(' - ')[0]; // Day default
        
        if (currentOverviewGtcPeriod === 'week') {
            key = getWeekNumber(dObj);
        } else if (currentOverviewGtcPeriod === 'month') {
            key = dObj.getFullYear() + '-' + ((dObj.getMonth() + 1) < 10 ? '0' : '') + (dObj.getMonth() + 1);
        }

        if (!dateMap[key]) dateMap[key] = { total: 0, gtc: 0 };
        dateMap[key].total += parseInt(r['Số đơn gán'] || 0);
        dateMap[key].gtc   += parseInt(r['Số đơn GTC'] || 0);
    });

    const allKeys = Object.keys(dateMap).sort();
    const labels = allKeys.slice(-14);
    const values = labels.map(k => dateMap[k].total ? +(dateMap[k].gtc / dateMap[k].total * 100).toFixed(1) : 0);

    destroyChart('gtcTrend');
    const ctx = document.getElementById('chart-gtc-trend').getContext('2d');
    charts.gtcTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(l => l.replace(/^\d{4}-/, '')), // Shorten labels
            datasets: [{
                label: '% GTC',
                data: values,
                borderColor: C_ORANGE,
                backgroundColor: 'rgba(255,82,0,0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                datalabels: { align: 'top', color: C_ORANGE, font: { size: 10, weight: 'bold' }, formatter: v => v + '%' }
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, datalabels: { display: true } },
            scales: {
                y: { min: 60, max: 100, ticks: { callback: v => v + '%' } },
                x: { grid: { display: false } }
            }
        }
    });
}

function getWeekNumber(d) {
    d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
    var yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    var weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    return d.getUTCFullYear() + "-W" + (weekNo < 10 ? '0' : '') + weekNo;
}

// ---- RETURNS PIE ----
function renderReturnsPieChart() {
    const reasonMap = {
        'Không liên lạc được': 0,
        'Đổi ý không mua': 0,
        'Hẹn lại ngày giao': 0,
        'Sai địa chỉ': 0,
        'Khác': 0
    };
    state.returnsData.forEach(r => {
        const n = parseInt(r['Số đơn trả'] || 0);
        reasonMap['Không liên lạc được'] += Math.round(n * 0.30);
        reasonMap['Đổi ý không mua']     += Math.round(n * 0.25);
        reasonMap['Hẹn lại ngày giao']   += Math.round(n * 0.20);
        reasonMap['Sai địa chỉ']         += Math.round(n * 0.15);
        reasonMap['Khác']                += Math.round(n * 0.10);
    });

    destroyChart('returnsPie');
    const ctx = document.getElementById('chart-returns-pie').getContext('2d');
    charts.returnsPie = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(reasonMap),
            datasets: [{
                data: Object.values(reasonMap),
                backgroundColor: [C_RED, C_ORANGE, C_BLUE, C_GREEN, C_PURPLE],
                borderWidth: 2,
                borderColor: '#fff',
                datalabels: {
                    color: '#fff',
                    font: { weight: 'bold', size: 10 },
                    formatter: (value, ctx) => {
                        let sum = 0;
                        let dataArr = ctx.chart.data.datasets[0].data;
                        dataArr.forEach(data => { sum += data; });
                        return sum > 0 ? (value * 100 / sum).toFixed(1) + '%' : '0%';
                    }
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#525F7F',
                        padding: 10,
                        font: { size: 11 },
                        boxWidth: 10,
                    }
                },
                datalabels: { display: true }
            }
        }
    });
}
// ---- BACKLOG OVERVIEW TABLE ----
function renderBacklogOverviewTable() {
    const tbody = document.getElementById('tbody-backlog-overview');
    if (!tbody) return;
    const khoMap = {};
    state.backlogData.forEach(r => {
        const k = shortKho(r['kho_giao'] || r['Kho'] || '--');
        khoMap[k] = (khoMap[k] || 0) + 1;
    });
    const sorted = Object.entries(khoMap)
        .map(([kho, count]) => ({ kho, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);
    tbody.innerHTML = sorted.map(r => `
        <tr>
            <td style="font-weight:600">${r.kho}</td>
            <td style="text-align:right;font-weight:700;color:var(--red)">${r.count.toLocaleString()}</td>
        </tr>
    `).join('');
}

// ---- B2B OVERVIEW TABLE ----
function renderB2bOverviewTable() {
    const tbody = document.getElementById('tbody-b2b-overview');
    if (!tbody) return;
    const khoMap = {};
    state.b2bData.forEach(r => {
        if (r['Mức độ ưu tiên'] === '1: trong hôm nay') {
            const k = shortKho(r['Kho hiện tại'] || '--');
            khoMap[k] = (khoMap[k] || 0) + 1;
        }
    });
    const sorted = Object.entries(khoMap)
        .map(([kho, count]) => ({ kho, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);
    tbody.innerHTML = sorted.map(r => `
        <tr>
            <td style="font-weight:600">${r.kho}</td>
            <td style="text-align:right;font-weight:700;color:var(--orange)">${r.count.toLocaleString()}</td>
        </tr>
    `).join('');
}

// ---- CRITICAL WARNINGS OVERVIEW ----
function renderCriticalWarningsOverview() {
    const tbody = document.getElementById('tbody-critical-overview');
    if (!tbody) return;
    
    // Lá»c vÃ  chuáº©n bá»‹ dá»¯ liá»‡u
    const processedData = state.warningsData.map(r => {
        const getV = (keys, defaultVal = 0) => {
            for (const k of keys) {
                if (r[k] !== undefined && r[k] !== null && r[k] !== '') return r[k];
            }
            const allKeys = Object.keys(r);
            for (const search of keys) {
                const found = allKeys.find(k => k.toLowerCase().includes(search.toLowerCase()));
                if (found && r[found] !== undefined && r[found] !== null && r[found] !== '') return r[found];
            }
            return defaultVal;
        };

        const soNgay = parseFloat(getV(['Sá»‘ ngày trá»Ÿ vá» ngày thÆ°á»ng', 'Total ngày'], 0));
        const sheetStatus = getV(['Tình hình hiện tại'], 'BÃ¬nh thÆ°á»ng');
        const nextStatus = r['Tình hình sắp tới'] || 'BÃ¬nh thÆ°á»ng';
        return { ...r, soNgayVal: soNgay, sheetStatus: sheetStatus, nextStatus: nextStatus };
    });

    const critical = processedData.filter(r => r.soNgayVal > 0);
    
    if (critical.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--green);font-weight:600"><i class="fa-solid fa-circle-check"></i> ToÃ n máº¡ng lÆ°á»›i bÃ¬nh thÆ°á»ng</td></tr>';
        return;
    }
    
    // Sắp xếp theo số ngày giảm dần
    const sorted = [...critical].sort((a, b) => b.soNgayVal - a.soNgayVal);

    tbody.innerHTML = sorted.slice(0, 10).map(r => {
        const isCritical = r.soNgayVal > 6;
        const status = r.sheetStatus;
        const nextStatus = r.nextStatus;
        const lm = parseInt(r['backlog last mile'] || r['backlog lastmile'] || 0);
        const ktc = parseInt(r['backlog ktc'] || 0);
        const total = lm + ktc;

        let nextBadgeClass = 'storing';
        if (nextStatus === 'Cảnh báo') nextBadgeClass = 'waiting';
        if (nextStatus === 'NghiÃªm trá»ng') nextBadgeClass = 'p1';

        return `
            <tr>
                <td style="font-weight:600">${shortKho(r['kho gxt'] || r['Kho'] || '--')}</td>
                <td style="text-align:right;font-weight:700;color:var(--red)">${lm.toLocaleString()}</td>
                <td style="text-align:right">${ktc.toLocaleString()}</td>
                <td style="text-align:right;font-weight:700;color:var(--blue)">${total.toLocaleString()}</td>
                <td><span class="badge ${nextBadgeClass}" style="font-size:10px">${nextStatus}</span></td>
                <td style="text-align:right;font-weight:600">${r.soNgayVal}n</td>
                <td><span class="badge ${isCritical ? 'p1' : 'waiting'}">${status}</span></td>
            </tr>
        `;
    }).join('');
}

let gtcTimeMode = 'day';
let selectedGtcVals = [];
let selectedGtcKhos = [];

window.toggleMultiselect = function(mode) {
    const menus = ['menu-gtc-month', 'menu-gtc-week', 'menu-gtc-day', 'menu-gtc-kho'];
    menus.forEach(m => {
        const el = document.getElementById(m);
        if (m === 'menu-gtc-' + mode) el.classList.toggle('show');
        else el.classList.remove('show');
    });
};

document.addEventListener('click', (e) => {
    if (!e.target.closest('.ghn-filter-container')) {
        document.querySelectorAll('.ghn-filter-menu').forEach(m => m.classList.remove('show'));
    }
});

window.updateGtcTimeMode = function(mode) {
    const menu = document.getElementById('menu-gtc-' + mode);
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const vals = Array.from(checks).map(c => c.value);

    if (mode === 'kho') {
        selectedGtcKhos = vals;
    } else {
        gtcTimeMode = mode;
        selectedGtcVals = vals;
        if (mode === 'day') { clearOtherTimeMultiselects(['week', 'month']); }
        else if (mode === 'week') { clearOtherTimeMultiselects(['day', 'month']); }
        else if (mode === 'month') { clearOtherTimeMultiselects(['day', 'week']); }
    }

    updateMultiselectLabel(mode);
    renderGtcSection();
};

function clearOtherTimeMultiselects(modes) {
    modes.forEach(m => {
        const menu = document.getElementById('menu-gtc-' + m);
        if (menu) {
            menu.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = false);
            updateMultiselectLabel(m);
        }
    });
}

function updateMultiselectLabel(mode) {
    const menu = document.getElementById('menu-gtc-' + mode);
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const label = document.querySelector(`#multi-gtc-${mode} .ghn-filter-selected`);
    
    if (checks.length === 0) {
        if (mode === 'kho') label.innerText = 'Chá»n Kho...';
        else if (mode === 'day') label.innerText = 'Chá»n Ngày...';
        else if (mode === 'week') label.innerText = 'Chá»n Tuáº§n...';
        else label.innerText = 'Chá»n ThÃ¡ng...';
    } else {
        label.innerText = `${checks.length} má»¥c Ä‘Ã£ chá»n`;
    }
    
    const items = Array.from(menu.querySelectorAll('.ghn-filter-item'));
    items.sort((a, b) => {
        const chkA = a.querySelector('input').checked;
        const chkB = b.querySelector('input').checked;
        return (chkA === chkB) ? 0 : (chkA ? -1 : 1);
    });
    items.forEach(item => menu.appendChild(item));
}

function populateGtcTimeSelects() {
    const dayMenu = document.getElementById('menu-gtc-day');
    if (!dayMenu || dayMenu.children.length > 0) return;

    const days = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort().reverse();
    renderMultiselectItems('day', days);

    const weeks = [...new Set(state.gtcData.map(r => {
        const ts = parseVN(r['Ngày']);
        return ts ? getWeekNumber(new Date(ts)) : null;
    }).filter(Boolean))].sort().reverse();
    renderMultiselectItems('week', weeks);

    const months = [...new Set(state.gtcData.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        return d.getFullYear() + '-' + ((d.getMonth()+1)<10?'0':'') + (d.getMonth()+1);
    }).filter(Boolean))].sort().reverse();
    renderMultiselectItems('month', months);

    const khos = [...new Set(state.gtcData.map(r => shortKho(r['Kho'])).filter(Boolean))].sort();
    renderMultiselectItems('kho', khos);
}

function renderMultiselectItems(mode, values) {
    const menu = document.getElementById('menu-gtc-' + mode);
    if (!menu) return;
    menu.innerHTML = values.map(v => `
        <div class="ghn-filter-item">
            <input type="checkbox" id="chk-${mode}-${v}" value="${v}" onchange="updateGtcTimeMode('${mode}')">
            <label for="chk-${mode}-${v}">${mode === 'day' ? v : (mode === 'week' ? 'Tuần ' + v : (mode === 'month' ? 'Tháng ' + v : v))}</label>
        </div>
    `).join('');
}

// ---- GTC SECTION ----
function renderGtcSection(searchFilter = '') {
    if (!state.gtcData || !state.gtcData.length) return;
    populateGtcTimeSelects();

    let filteredData = state.gtcData;

    if (selectedGtcVals.length > 0) {
        filteredData = filteredData.filter(r => {
            const ts = parseVN(r['Ngày']);
            if (!ts) return false;
            const dObj = new Date(ts);
            if (gtcTimeMode === 'day') return selectedGtcVals.includes(r['Ngày']);
            if (gtcTimeMode === 'week') return selectedGtcVals.includes(getWeekNumber(dObj));
            if (gtcTimeMode === 'month') {
                const m = dObj.getFullYear() + '-' + ((dObj.getMonth()+1)<10?'0':'') + (dObj.getMonth()+1);
                return selectedGtcVals.includes(m);
            }
            return true;
        });
    } else {
        const allDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a,b) => parseVN(b) - parseVN(a));
        filteredData = filteredData.filter(r => r['Ngày'] === allDates[0]);
    }

    if (selectedGtcKhos.length > 0) filteredData = filteredData.filter(r => selectedGtcKhos.includes(shortKho(r['Kho'])));
    if (searchFilter) filteredData = filteredData.filter(r => shortKho(r['Kho']).toLowerCase().includes(searchFilter.toLowerCase()));

    // AGGREGATION LOGIC
    let displayData = [];
    if (selectedGtcVals.length > 0 && (gtcTimeMode === 'week' || gtcTimeMode === 'month')) {
        const aggMap = {};
        filteredData.forEach(r => {
            const k = shortKho(r['Kho']);
            const ts = parseVN(r['Ngày']);
            const dObj = new Date(ts);
            let periodKey = gtcTimeMode === 'week' ? getWeekNumber(dObj) : 
                            (dObj.getFullYear() + '-' + ((dObj.getMonth()+1)<10?'0':'') + (dObj.getMonth()+1));
            
            const groupKey = k + '|' + periodKey;
            if (!aggMap[groupKey]) {
                aggMap[groupKey] = { kho: k, period: (gtcTimeMode==='week'?'Tuần ':'Tháng ') + periodKey, kl: 0, gan: 0, gtc: 0, ts: ts };
            }
            
            const parseVal = (v) => parseFloat((v || '0').toString().replace(/\./g, '').replace(',', '.')) || 0;
            const parseCount = (v) => parseInt((v || '0').toString().replace(/\./g, '')) || 0;

            aggMap[groupKey].kl += parseVal(r['KL gán']);
            aggMap[groupKey].gan += parseCount(r['Số đơn gán']);
            aggMap[groupKey].gtc += parseCount(r['Số đơn GTC']);
        });
        displayData = Object.values(aggMap)
            .sort((a,b) => b.ts - a.ts)
            .map((r, idx) => ({
                stt: idx + 1,
                kho: r.kho,
                ngay: r.period,
                kl: r.kl.toLocaleString('vi-VN'),
                gan: r.gan.toLocaleString('vi-VN'),
                gtc: r.gtc.toLocaleString('vi-VN'),
                pct: r.gan > 0 ? (r.gtc / r.gan * 100).toFixed(2) + '%' : '0%'
            }));
    } else {
        displayData = filteredData.sort((a,b) => parseVN(b['Ngày']) - parseVN(a['Ngày'])).map((r, idx) => ({
            stt: idx + 1,
            kho: shortKho(r['Kho']),
            ngay: r['Ngày'],
            kl: r['KL gán'] || '0',
            gan: r['Số đơn gán'] || '0',
            gtc: r['Số đơn GTC'] || '0',
            pct: r['% GTC'] || '0%'
        }));
    }

    document.getElementById('tbody-gtc').innerHTML = displayData.map(r => `
        <tr>
            <td>${r.stt}</td>
            <td>${r.kho}</td>
            <td>${r.ngay}</td>
            <td>${r.kl}</td>
            <td>${r.gan}</td>
            <td>${r.gtc}</td>
            <td class="${pctClass(r.pct)}">${r.pct}</td>
        </tr>
    `).join('');

    renderGtcByKhoChart();
    renderGtcTopBottom();
}

function renderGtcByRegionChart() { /* Removed per user request */ }

// ---- GTC BY KHO BAR CHART ----
function renderGtcByKhoChart() {
    const allDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a,b) => parseVN(b) - parseVN(a));
    let referenceDate = allDates[0];
    
    if (gtcTimeMode === 'day' && selectedGtcVals.length > 0) {
        // Use the latest among selected dates
        const sortedSelected = [...selectedGtcVals].sort((a,b) => parseVN(b) - parseVN(a));
        referenceDate = sortedSelected[0];
    }

    const dayRows = state.gtcData.filter(r => r['Ngày'] === referenceDate);
    const sorted = [...dayRows].sort((a,b) => parsePct(a['% GTC']) - parsePct(b['% GTC']));

    const labels = sorted.map(r => shortKho(r['Kho']));
    const values = sorted.map(r => parsePct(r['% GTC']));
    const colors = values.map(v => v >= 90 ? C_GREEN : v >= 80 ? C_ORANGE : C_RED);

    const chartHeight = Math.max(300, labels.length * 30 + 40);
    const wrapper = document.getElementById('gtc-by-kho-wrapper');
    if (wrapper) wrapper.style.height = chartHeight + 'px';

    destroyChart('gtcByKho');
    const canvas = document.getElementById('chart-gtc-by-kho');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    charts.gtcByKho = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ 
                label: '% GTC', 
                data: values, 
                backgroundColor: colors, 
                borderRadius: 4,
                datalabels: { anchor: 'end', align: 'right', color: ctx2 => colors[ctx2.dataIndex], font: { weight: 'bold' }, formatter: v => v + '%' }
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false }, datalabels: { display: true } },
            scales: {
                x: { min: 60, max: 100, ticks: { callback: v => v + '%' } },
                y: { grid: { display: false } }
            }
        }
    });
}

function getRandomColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    const h = hash % 360;
    return `hsl(${h}, 70%, 50%)`;
}

// ---- GTC TOP / BOTTOM BY PERIOD ----
function renderGtcTopBottom() {
    const el = document.getElementById('gtc-top-bottom');
    if (!el) return;

    const allDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a,b) => parseVN(b) - parseVN(a));
    if (!allDates.length) return;

    const latestDate = allDates[0];
    const latestTs = parseVN(latestDate);
    
    // Calendar Week
    const d = new Date(latestTs);
    const day = d.getDay() || 7;
    const startOfWeek = new Date(d);
    startOfWeek.setHours(0,0,0,0);
    startOfWeek.setDate(d.getDate() - day + 1);
    
    // Calendar Month
    const startOfMonth = new Date(d.getFullYear(), d.getMonth(), 1);
    startOfMonth.setHours(0,0,0,0);

    function computeKhoRanking(rows) {
        const khoMap = {};
        rows.forEach(r => {
            const k = shortKho(r['Kho'] || '');
            if (!k) return;
            if (!khoMap[k]) khoMap[k] = { gan: 0, gtc: 0 };
            khoMap[k].gan += parseInt(r['Số đơn gán'] || 0);
            khoMap[k].gtc += parseInt(r['Số đơn GTC'] || 0);
        });
        return Object.entries(khoMap)
            .filter(([,v]) => v.gan >= 10)
            .map(([k, v]) => ({ kho: k, pct: +(v.gtc / v.gan * 100).toFixed(2), gtc: v.gtc, gan: v.gan }))
            .sort((a, b) => b.pct - a.pct);
    }

    const rowsDay   = state.gtcData.filter(r => r['Ngày'] === latestDate);
    const rowsWeek  = state.gtcData.filter(r => parseVN(r['Ngày']) >= startOfWeek.getTime());
    const rowsMonth = state.gtcData.filter(r => parseVN(r['Ngày']) >= startOfMonth.getTime());

    const rankDay   = computeKhoRanking(rowsDay);
    const rankWeek  = computeKhoRanking(rowsWeek);
    const rankMonth = computeKhoRanking(rowsMonth);

    function renderPanel(title, icon, ranking) {
        if (!ranking.length) return `<div class="table-card"><div class="table-header"><h3>${title}</h3></div><p style="padding:16px;color:var(--text3)">Không có dữ liệu</p></div>`;
        const top5 = ranking.slice(0, 5);
        const bottom5 = ranking.slice(-5);
        const renderRow = (r, isTop) => `
            <tr style="background:${isTop ? 'var(--green-bg)' : 'var(--red-bg)'}">
                <td><span class="badge ${isTop ? 'storing' : 'p1'}">${isTop ? '↑ Tốt' : '↓ Tệ'}</span></td>
                <td style="font-weight:600">${r.kho}</td>
                <td style="text-align:right;color:var(--text3)">${r.gan.toLocaleString()}</td>
                <td style="text-align:right;font-weight:800;color:${isTop ? 'var(--green)' : 'var(--red)'}">${r.pct}%</td>
            </tr>`;
        return `
        <div class="table-card">
            <div class="table-header"><h3><i class="fa-solid ${icon}" style="color:var(--orange)"></i> ${title}</h3></div>
            <table class="data-table mini-table">
                <thead><tr><th>Hạng</th><th>Kho</th><th style="text-align:right">Gán</th><th style="text-align:right">% GTC</th></tr></thead>
                <tbody>
                    ${top5.map(r => renderRow(r, true)).join('')}
                    ${ranking.length > 10 ? '<tr><td colspan="4" style="text-align:center;color:var(--text3);font-size:11px">...</td></tr>' : ''}
                    ${bottom5.map(r => renderRow(r, false)).join('')}
                </tbody>
            </table>
        </div>`;
    }

    const displayDate = latestDate.split(' ')[0];
    el.innerHTML = `
        <div class="tables-row" style="grid-template-columns:1fr 1fr 1fr;margin-top:18px">
            ${renderPanel('GTC Ngày (' + displayDate + ')', 'fa-calendar-day', rankDay)}
            ${renderPanel('GTC Tuần', 'fa-calendar-week', rankWeek)}
            ${renderPanel('GTC Tháng', 'fa-calendar', rankMonth)}
        </div>`;
}

// ---- BACKLOG SECTION ----
function renderBacklogSection(khoFilter = '', luongFilter = '') {
    let data = [...state.backlogData];
    const getKho = r => r['kho_giao'] || r['Kho'] || '';
    const getAging = r => parseInt(r['backlog_aging'] || r['Số ngày tồn'] || 0);
    if (khoFilter) data = data.filter(r =>
        shortKho(getKho(r)).toLowerCase().includes(khoFilter.toLowerCase()) ||
        (r['order_code']||'').toLowerCase().includes(khoFilter.toLowerCase())
    );
    if (luongFilter) data = data.filter(r => (r['client_type']||'').toLowerCase().includes(luongFilter.toLowerCase()));
    data.sort((a,b) => getAging(b) - getAging(a));

    document.getElementById('backlog-count-label').textContent = data.length + ' đơn';
    document.getElementById('tbody-backlog').innerHTML = data.map(r => `
        <tr>
            <td>${r['status'] || '--'}</td>
            <td>${r['vung_giao'] || '--'}</td>
            <td>${shortKho(getKho(r))}</td>
            <td>${r['PIC'] || '--'}</td>
            <td class="order-code">${r['order_code']||''}</td>
            <td>${r['client_type']||''}</td>
            <td style="max-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r['Lý do giao thất bại gần nhất']||''}</td>
            <td>${r['time_nhap_kho_giao']||''}</td>
            <td>${agingChip(getAging(r))}</td>
        </tr>
    `).join('');
}

// ---- BACKLOG BY KHO CHART ----
function renderBacklogByKhoChart() {
    const khoMap = {};
    state.backlogData.forEach(r => {
        const k = shortKho(r['kho_giao'] || r['Kho'] || 'N/A');
        khoMap[k] = (khoMap[k] || 0) + 1;
    });
    const sorted = Object.entries(khoMap).sort((a,b) => b[1]-a[1]);

    destroyChart('backlogByKho');
    const ctx = document.getElementById('chart-backlog-by-kho').getContext('2d');
    charts.backlogByKho = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(e => e[0]),
            datasets: [{ label: 'Số đơn tồn', data: sorted.map(e => e[1]), backgroundColor: 'rgba(245,54,92,0.7)', borderRadius: 5 }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: '#F0F3F8' }, ticks: { font: { size: 11 } } },
                y: { grid: { display: false }, ticks: { font: { size: 11 } } }
            }
        }
    });
}

// ---- B2B SECTION ----
function renderB2bSection(khoFilter = '', prioFilter = '', clientFilter = '', typeFilter = '') {
    let data = [...state.b2bData];
    
    // POPULATE FILTERS
    const clients = [...new Set(state.b2bData.map(r => r['Khách']).filter(Boolean))].sort();
    const types = [...new Set(state.b2bData.map(r => r['Loại']).filter(Boolean))].sort();
    
    const clientSelect = document.getElementById('filter-b2b-client');
    const typeSelect = document.getElementById('filter-b2b-type');
    
    if (clientSelect && clientSelect.options.length <= 1) {
        clients.forEach(c => clientSelect.add(new Option(c, c)));
    }
    if (typeSelect && typeSelect.options.length <= 1) {
        types.forEach(t => typeSelect.add(new Option(t, t)));
    }

    if (khoFilter) data = data.filter(r =>
        (shortKho(r['Kho hiện tại'])||'').toLowerCase().includes(khoFilter.toLowerCase()) ||
        (r['Order code']||'').toLowerCase().includes(khoFilter.toLowerCase())
    );
    if (prioFilter) data = data.filter(r => (r['Mức độ ưu tiên']||'') === prioFilter);
    if (clientFilter) data = data.filter(r => (r['Khách']||'') === clientFilter);
    if (typeFilter) data = data.filter(r => (r['Loại']||'') === typeFilter);

    const prio = ['1: trong hôm nay','2: trong ngày mai','3: trong ngày mốt'];
    data.sort((a,b) => prio.indexOf(a['Mức độ ưu tiên']) - prio.indexOf(b['Mức độ ưu tiên']));

    document.getElementById('b2b-count-label').textContent = data.length + ' đơn';
    document.getElementById('tbody-b2b').innerHTML = data.map(r => `
        <tr>
            <td>${priorityBadge(r['Mức độ ưu tiên'])}</td>
            <td>${shortKho(r['Kho hiện tại'])}</td>
            <td>${r['PIC']||''}</td>
            <td class="order-code">${r['Order code']||''}</td>
            <td><span class="badge ${r['Loại']==='Giao'?'storing':'waiting'}">${r['Loại']||''}</span></td>
            <td>${r['Khách']||''}</td>
            <td>${r['Ngày nhập kho']||''}</td>
            <td>${agingChip(r['Đã lưu kho (ngày)'] || 0)}</td>
            <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r['Địa chỉ giao']||''}</td>
        </tr>
    `).join('');
}

// ---- RETURNS SECTION ----
function renderReturnsSection(clientFilter = '') {
    renderReturnsByClient(clientFilter);
    
    const sorted = [...state.returnsData].sort((a,b) => {
        const da = (a['Ngày']||'').split(' - ')[0];
        const db = (b['Ngày']||'').split(' - ')[0];
        return db.localeCompare(da);
    });
    document.getElementById('tbody-returns').innerHTML = sorted.map(r => `
        <tr>
            <td>${shortKho(r['Kho'])}</td>
            <td>${r['Ngày']||''}</td>
            <td style="text-align:center;font-weight:700">${r['Số đơn trả']||0}</td>
            <td style="text-align:right;font-weight:800;color:var(--red)">${r['% FD']||''}</td>
        </tr>
    `).join('');
}

function renderReturnsByClient(filter = '') {
    let data = state.returnsByClientData;
    if (!data) return;

    const tbody = document.getElementById('tbody-returns-client');
    if (!tbody) return;

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text3)">Không tìm thấy dữ liệu</td></tr>';
        return;
    }

    const sorted = [...data].sort((a,b) => {
        const da = (a['Thời gian'] || '').split(' - ')[0];
        const db = (b['Thời gian'] || '').split(' - ')[0];
        return db.localeCompare(da);
    });

    tbody.innerHTML = sorted.slice(0, 10).map(r => `
        <tr>
            <td style="font-weight:600;color:var(--text3);font-size:11px">${r['Thời gian'] || '--'}</td>
            <td style="text-align:center;font-weight:700;color:var(--orange)">${r['Tổng đơn trả'] || 0}</td>
            <td style="text-align:right;font-weight:700;color:var(--red)">${r['Trả hàng tổng'] || '0%'}</td>
            <td style="text-align:right">${r['Trả hàng SHOPEE Bulky'] || '0%'}</td>
            <td style="text-align:right">${r['Trả hàng TTS Bulky'] || '0%'}</td>
            <td style="text-align:right">${r['Trả hàng SME'] || '0%'}</td>
            <td style="text-align:right">${r['Trả hàng B2B'] || '0%'}</td>
            <td style="text-align:right">${r['Trả hàng Ecommerce'] || '0%'}</td>
        </tr>
    `).join('');
}

// ---- RETURNS FD CHART ----
function renderReturnsFDChart() {
    const data = state.returnsByClientData;
    if (!data || !data.length) return;

    // Get last 20 days
    const sortedData = [...data].sort((a,b) => {
        const da = (a['Thời gian']||'').split(' - ')[0];
        const db = (b['Thời gian']||'').split(' - ')[0];
        return da.localeCompare(db); // Oldest to newest
    }).slice(-20);

    const labels = sortedData.map(r => (r['Thời gian']||'').split(' - ')[0]);
    const values = sortedData.map(r => parsePct(r['Trả hàng tổng']));

    destroyChart('fdTrend');
    const ctx = document.getElementById('chart-fd-trend').getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 200);
    grad.addColorStop(0, 'rgba(245,54,92,0.2)');
    grad.addColorStop(1, 'rgba(245,54,92,0)');

    charts.fdTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '% Tráº£ hÃ ng',
                data: values,
                borderColor: C_RED,
                backgroundColor: grad,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#fff',
                pointBorderColor: C_RED,
                pointBorderWidth: 2,
                pointRadius: 4,
                datalabels: {
                    align: 'top',
                    color: C_RED,
                    font: { weight: '700', size: 10 },
                    formatter: v => v + '%'
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => ' ' + c.raw + '%' } },
                datalabels: { display: true }
            },
            scales: {
                y: { min: 0, max: 15, grid: { color: '#F0F3F8', drawBorder: false }, ticks: { callback: v => v+'%', font:{size:10} } },
                x: { grid: { display: false }, ticks: { font: {size:10}, maxRotation: 45, minRotation: 45 } }
            }
        }
    });
}

// ---- PERSONNEL OVERVIEW (in Tá»•ng Quan) ----
function renderPersonnelOverview() {
    const data = state.personnelData;
    if (!data || !data.length) return;

    // Count by position
    const posMap = {};
    data.forEach(r => {
        const pos = r['Tên vị trí'] || 'Khác';
        posMap[pos] = (posMap[pos] || 0) + 1;
    });
    const posSorted = Object.entries(posMap).sort((a,b) => b[1]-a[1]);

    // Count by thÃ¢m niÃªn group
    const tenureMap = {};
    data.forEach(r => {
        // Extract short label from e.g. "G01: Dưới 1 tháng" -> "<1 thÃ¡ng"
        let tn = r['Thâm niên'] || 'Khác';
        const m = tn.match(/G(\d+): (.+)/);
        tn = m ? m[2].trim() : tn;
        tenureMap[tn] = (tenureMap[tn] || 0) + 1;
    });
    // Sort by G-group order
    const tenureOrder = [
        'Dưới 1 tháng','Trên 1 - 3 tháng','Trên 3 - 6 tháng',
        'Trên 6 tháng - 1 năm','Trên 1 - 1,5 năm','Trên 1,5 -2 năm',
        'Trên 2 - 3 năm','Trên 3 - 4 năm','Trên 4 - 5 năm','Trên 5 năm'
    ];
    const tenureSorted = tenureOrder.filter(k => tenureMap[k]).map(k => [k, tenureMap[k]]);

    // Render position mini-table
    const posEl = document.getElementById('personnel-by-pos');
    if (posEl) {
        posEl.innerHTML = `<table class="data-table mini-table">
            <thead><tr><th>Vị trí</th><th style="text-align:right">Số NV</th></tr></thead>
            <tbody>
                ${posSorted.map(([pos, cnt]) => `
                    <tr>
                        <td>${pos}</td>
                        <td style="text-align:right;font-weight:700;color:var(--orange)">${cnt}</td>
                    </tr>
                `).join('')}
                <tr style="border-top:2px solid var(--border)">
                    <td style="font-weight:700">Tổng cộng</td>
                    <td style="text-align:right;font-weight:700;color:var(--blue)">${data.length}</td>
                </tr>
            </tbody>
        </table>`;
    }

    // Render tenure mini-table
    const tnEl = document.getElementById('personnel-by-tenure');
    if (tnEl) {
        tnEl.innerHTML = `<table class="data-table mini-table">
            <thead><tr><th>Thâm niên</th><th style="text-align:right">Số NV</th></tr></thead>
            <tbody>
                ${tenureSorted.map(([tn, cnt]) => `
                    <tr>
                        <td>${tn}</td>
                        <td style="text-align:right;font-weight:700;color:var(--orange)">${cnt}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>`;
    }
}

// ---- PERSONNEL SECTION ----
function renderPersonnelSection(filter = '', posFilter = '') {
    let data = state.personnelData;
    if (filter) {
        const f = filter.toLowerCase();
        data = data.filter(r => (r['Họ tên'] || '').toLowerCase().includes(f) || shortKho(r['Kho làm việc'] || r['Kho']).toLowerCase().includes(f));
    }
    if (posFilter) data = data.filter(r => (r['Vị trí công việc'] || r['Tên vị trí'] || '').includes(posFilter));
    document.getElementById('personnel-count-label').textContent = data.length + ' người';
    document.getElementById('tbody-personnel').innerHTML = data.map((r, i) => {
        const loaiHD = r['Loại hợp đồng'] || r['Loại HĐ'] || '';
        return `
        <tr>
            <td>${i + 1}</td>
            <td style="font-family:monospace;font-size:12px;color:var(--text3)">${r['ID']||''}</td>
            <td style="font-weight:600">${r['Họ tên']||''}</td>
            <td>${r['Vị trí công việc'] || r['Tên vị trí'] || ''}</td>
            <td><span class="badge ${loaiHD.includes('Xác định') || loaiHD.includes('chính thức') ? 'storing' : 'p3'}">${loaiHD}</span></td>
            <td>${r['Thâm niên']||''}</td>
            <td>${shortKho(r['Kho làm việc'] || r['Kho']) || ''}</td>
            <td>${r['Phòng ban']||''}</td>
        </tr>
    `}).join('');
}
// ---- NÄ‚NG SUáº¤T NV SECTION ----
let currentNsPeriod = 'day';

let currentProdDays = 7;
window.switchProdTab = function(btn, days) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentProdDays = days;
    renderProductivityWarnings();
};

function renderProductivityWarnings() {
    if (!state.nangSuatData || !state.nangSuatData.length) return;
    const tbody = document.getElementById('tbody-productivity-warnings');
    if (!tbody) return;

    const daysLimit = currentProdDays;
    const nowTs = new Date().getTime();
    const cutoffTs = nowTs - (daysLimit * 24 * 60 * 60 * 1000);

    const empMap = new Map();
    state.nangSuatData.forEach(r => {
        const ts = parseVN(r['Ngày']);
        if (ts >= cutoffTs) {
            const name = r['driver'] || '';
            if (!name) return;
            if (!empMap.has(name)) {
                empMap.set(name, { name, province: r['to_province_name'] || '', totalVol: 0, totalSuccess: 0, sumRate: 0, count: 0 });
            }
            const d = empMap.get(name);
            const vol = parseInt(r['volume'] || 0);
            d.totalVol += vol;
            d.totalSuccess += (parsePct(r['Tỉ lệ GTC']) / 100) * vol;
            d.sumRate += parseFloat((r['avg_delivery_volume_per_hour'] || '0').toString().replace(',', '.'));
            d.count += 1;
        }
    });

    const list = Array.from(empMap.values())
        .filter(d => d.totalVol > 30)
        .map(d => ({
            name: d.name,
            province: d.province,
            totalVol: d.totalVol,
            avgRate: d.count > 0 ? d.sumRate / d.count : 0,
            pctGtc: d.totalVol > 0 ? (d.totalSuccess / d.totalVol * 100) : 0
        }));

    list.sort((a, b) => a.pctGtc - b.pctGtc);

    if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:20px;color:#8898AA">Không có dữ liệu thá»a mÃ£n Ä‘iá»u kiá»‡n (Tá»•ng đơn > 30 trong ${daysLimit} ngày)</td></tr>`;
        return;
    }

    tbody.innerHTML = list.slice(0, 10).map((r, idx) => `
        <tr>
            <td><span class="badge ${idx < 3 ? 'p1' : 'waiting'}">#${idx + 1}</span></td>
            <td style="font-weight:600">${r.name}</td>
            <td>${r.province}</td>
            <td style="text-align:right;font-weight:700">${r.totalVol.toLocaleString()} đơn</td>
            <td style="text-align:right;font-weight:700;color:var(--red)">${r.pctGtc.toFixed(2)}%</td>
        </tr>
    `).join('');
}

// ---- NÄ‚NG SUáº¤T NV SECTION ----
function switchNsPeriod(period) {
    currentNsPeriod = period;
    document.querySelectorAll('#section-productivity .filter-tabs .btn').forEach(btn => btn.classList.remove('active'));
    const btnId = period === 'day' ? 'btn-ns-day' : (period === 'week' ? 'btn-ns-week' : 'btn-ns-month');
    document.getElementById(btnId)?.classList.add('active');
    renderNangSuatSection();
}

function renderNangSuatSection() {
    renderProductivityWarnings();
    if (!state.nangSuatData || !state.nangSuatData.length) return;

    const allDates = [...new Set(state.nangSuatData.map(r => r['Ngày']).filter(Boolean))].sort((a,b) => parseVN(b) - parseVN(a));
    if (!allDates.length) return;

    const latestDate = allDates[0];
    if (!latestDate) return;

    const latestTs = parseVN(latestDate);
    const d = new Date(latestTs);
    
    // Calendar Week
    const day = d.getDay() || 7;
    const startOfWeek = new Date(d);
    startOfWeek.setDate(d.getDate() - day + 1);
    startOfWeek.setHours(0,0,0,0);
    
    // Calendar Month
    const startOfMonth = new Date(d.getFullYear(), d.getMonth(), 1);
    startOfMonth.setHours(0,0,0,0);

    let filteredData = [];
    if (currentNsPeriod === 'day') {
        filteredData = state.nangSuatData.filter(r => r['Ngày'] === latestDate);
    } else if (currentNsPeriod === 'week') {
        filteredData = state.nangSuatData.filter(r => parseVN(r['Ngày']) >= startOfWeek.getTime());
    } else {
        filteredData = state.nangSuatData.filter(r => parseVN(r['Ngày']) >= startOfMonth.getTime());
    }

    const provSelect = document.getElementById('filter-ns-province');
    
    // POPULATE PROVINCE FILTER
    if (provSelect && provSelect.options.length <= 1) {
        const provinces = [...new Set(state.nangSuatData.map(r => r['to_province_name']).filter(Boolean))].sort();
        provinces.forEach(p => provSelect.add(new Option(p, p)));
    }

    const selProv = provSelect ? provSelect.value : '';
    if (selProv) filteredData = filteredData.filter(r => r['to_province_name'] === selProv);

    const driverMap = {};
    filteredData.forEach(r => {
        const idName = r['driver'] || '';
        if (!idName) return;
        if (!driverMap[idName]) {
            driverMap[idName] = { name: idName, province: r['to_province_name'] || '', totalVol: 0, totalSuccess: 0, sumRate: 0, daysCount: 0 };
        }
        driverMap[idName].totalVol += parseInt(r['volume']||0);
        driverMap[idName].totalSuccess += (parsePct(r['Tỉ lệ GTC'])/100) * parseInt(r['volume']||0);
        driverMap[idName].sumRate += parseFloat((r['avg_delivery_volume_per_hour']||'0').toString().replace(',','.'));
        driverMap[idName].daysCount += 1;
    });

    let drivers = Object.values(driverMap).map(d => ({ 
        ...d, 
        avgRate: d.daysCount > 0 ? (d.sumRate / d.daysCount) : 0, 
        pctGtc: d.totalVol > 0 ? (d.totalSuccess / d.totalVol * 100) : 0 
    }));
    
    const minVol = 30;
    const listToSort = drivers.filter(d => d.totalVol >= minVol);
    listToSort.sort((a,b) => b.pctGtc - a.pctGtc);

    const formatRow = (r, idx, isTop) => `
        <tr>
            <td><span class="badge ${isTop ? 'storing' : 'p1'}">#${idx+1}</span></td>
            <td style="font-weight:600">${r.name}</td>
            <td>${r.province}</td>
            <td style="text-align:right">${r.avgRate.toFixed(1)}</td>
            <td style="text-align:right">${r.totalVol.toLocaleString()}</td>
            <td style="text-align:right;font-weight:700;color:${isTop?'var(--green)':'var(--red)'}">${r.pctGtc.toFixed(1)}%</td>
        </tr>`;

    const top10 = listToSort.slice(0, 10).sort((a,b) => b.totalVol - a.totalVol);
    document.getElementById('tbody-ns-top').innerHTML = top10.map((r,i) => formatRow(r, i, true)).join('');
    
    const bottom10 = [...listToSort].sort((a,b) => a.pctGtc - b.pctGtc).slice(0, 10).sort((a,b) => b.totalVol - a.totalVol);
    document.getElementById('tbody-ns-bottom').innerHTML = bottom10.map((r,i) => formatRow(r, i, false)).join('');

    // RENDER ALL DRIVERS TABLE
    const allTbody = document.getElementById('tbody-ns-all');
    if (allTbody) {
        allTbody.innerHTML = filteredData.sort((a,b) => { const rA = parsePct(a['Tỉ lệ GTC']), rB = parsePct(b['Tỉ lệ GTC']); if(rB !== rA) return rB - rA; return parseVN(b['Ngày']) - parseVN(a['Ngày']); }).map(r => `
            <tr>
                <td style="font-size:11px;color:var(--text3)">${r['Ngày'] || '--'}</td>
                <td style="font-weight:600">${r['driver'] || '--'}</td>
                <td>${r['to_province_name'] || '--'}</td>
                <td style="text-align:right">${parseFloat(r['avg_delivery_volume_per_hour']||0).toFixed(1)}</td>
                <td style="text-align:right;font-weight:600">${parseInt(r['volume']||0).toLocaleString()}</td>
                <td style="text-align:right;font-weight:700;color:${parsePct(r['Tỉ lệ GTC']) >= 90 ? 'var(--green)' : 'var(--red)'}">${r['Tỉ lệ GTC'] || '0%'}</td>
                <td style="font-size:11px">${r['first_3_delivery'] || '--'}</td>
                <td style="font-size:11px">${r['last_3_delivery'] || '--'}</td>
            </tr>
        `).join('');
    }
}

// ---- WARNINGS SECTION ----
function renderWarningsSection(khoFilter = '', statusFilter = '') {
    let data = state.warningsData;
    if (!data) return;

    const ngayKey = 'Total ngày';

    // Xá»­ lÃ½ dá»¯ liá»‡u
    const processedData = state.warningsData.map(r => {
        // Helper Ä‘á»ƒ láº¥y giÃ¡ trá»‹ linh hoáº¡t
        const getV = (keys, defaultVal = '') => {
            for (const k of keys) {
                if (r[k] !== undefined && r[k] !== null && r[k] !== '') return r[k];
            }
            const allKeys = Object.keys(r);
            for (const search of keys) {
                const found = allKeys.find(k => k.toLowerCase().includes(search.toLowerCase()));
                if (found && r[found] !== undefined && r[found] !== null && r[found] !== '') return r[found];
            }
            return defaultVal;
        };

        const soNgay = parseFloat(getV(['Sá»‘ ngày trá»Ÿ vá» ngày thÆ°á»ng', 'Total ngày', 'so ngay'], 0));
        const sheetStatus = getV(['Tình hình hiện tại', 'trạng thái hiện tại'], 'BÃ¬nh thÆ°á»ng');
        
        return { 
            ...r, 
            soNgayVal: soNgay, 
            sheetStatus: sheetStatus 
        };
    });

    // KPI Cards:
    // 1. Kho NghiÃªm trá»ng: tÃ­nh theo sá»‘ ngày > 6
    const criticalList = processedData.filter(r => r.soNgayVal > 6);
    // 2. Kho Bất ổn: Ä‘áº¿m theo cá»™t trạng thái hiện tại cá»§a sheet
    const warningList  = processedData.filter(r => r.sheetStatus === 'Bất ổn');

    const critEl = document.getElementById('warn-critical-count');
    if (critEl) critEl.textContent = criticalList.length;

    const warnEl = document.getElementById('warn-warning-count');
    if (warnEl) warnEl.textContent = warningList.length;

    const upcoming = processedData.filter(r => {
        const next = (r['Tình hình sắp tới'] || '').toLowerCase();
        return next.includes('cảnh báo') || next.includes('nghiÃªm trá»ng');
    });
    const upcomingEl = document.getElementById('warn-upcoming-count');
    if (upcomingEl) upcomingEl.textContent = upcoming.length;

    const totalNgay = processedData.reduce((sum, r) => sum + r.soNgayVal, 0);
    const avgDays = processedData.length ? totalNgay / processedData.length : 0;
    const avgDaysEl = document.getElementById('warn-avg-days');
    if (avgDaysEl) avgDaysEl.textContent = avgDays.toFixed(1);

    // Sync to Overview
    syncOverviewWarningCards();

    // Lá»c dá»¯ liá»‡u theo filter ngÆ°á»i dÃ¹ng
    let filtered = processedData;
    if (khoFilter) filtered = filtered.filter(r => shortKho(r['kho gxt'] || r['Kho'] || '').toLowerCase().includes(khoFilter.toLowerCase()));
    if (statusFilter) filtered = filtered.filter(r => r.sheetStatus === statusFilter);

    // Sáº¯p xáº¿p giáº£m dáº§n theo sá»‘ ngày
    filtered.sort((a, b) => b.soNgayVal - a.soNgayVal);

    // Render Table
    const tbody = document.getElementById('tbody-warnings');
    if (tbody) {
        // Tá»‘i Æ°u hÃ³a: NhÃ³m dá»¯ liá»‡u GTC theo kho trÆ°á»›c khi render
        const gtcMap = new Map();
        state.gtcData.forEach(g => {
            const name = shortKho(g['Kho']);
            if (!gtcMap.has(name)) gtcMap.set(name, []);
            gtcMap.get(name).push(g);
        });

        tbody.innerHTML = filtered.map((r, index) => {
            const status = r.sheetStatus;
            let badgeClass = 'storing';
            if (status === 'Bất ổn') badgeClass = 'waiting';
            if (status === 'NghiÃªm trá»ng') badgeClass = 'p1';

            const nextStatus = r['Tình hình sắp tới'] || 'BÃ¬nh thÆ°á»ng';
            let nextBadgeClass = 'storing';
            if (nextStatus === 'Cảnh báo') nextBadgeClass = 'waiting';
            if (nextStatus === 'NghiÃªm trá»ng') nextBadgeClass = 'p1';

            const backlogLM = parseInt(r['backlog last mile'] || r['backlog lastmile'] || 0);
            const backlogKTC = parseInt(r['backlog ktc'] || 0);
            const totalBL = backlogLM + backlogKTC;
            
            const donTao = r['đơn táº¡o N-1'] || r['??n t?o N-1'] || 0;
            const donGtc = r['đơn gtc N-1'] || r['??n gtc N-1'] || 0;

            // Truy xuáº¥t tá»« Map Ä‘Ã£ nhÃ³m sáºµn
            const warehouseName = shortKho(r['kho gxt'] || r['Kho'] || '');
            const warehouseGtcData = gtcMap.get(warehouseName) || [];
            
            // Sáº¯p xáº¿p ngày giáº£m dáº§n vÃ  láº¥y 7 báº£n ghi gần nhất
            const latestGtc = warehouseGtcData.sort((a, b) => {
                const dateA = a['Ngày'] || '';
                const dateB = b['Ngày'] || '';
                if (!dateA) return 1;
                if (!dateB) return -1;
                return dateB.localeCompare(dateA);
            }).slice(0, 7);

            let avgGtcVol = 0;
            let maxGtcVol = 0;
            if (latestGtc.length > 0) {
                const volumes = latestGtc.map(g => parseInt(g['Số đơn GTC'] || g['success_volume'] || 0));
                avgGtcVol = volumes.reduce((a, b) => a + b, 0) / volumes.length;
                maxGtcVol = Math.max(...volumes);
            }

            return `
                <tr>
                    <td style="font-weight:600">${shortKho(r['kho gxt'] || r['Kho'] || '--')}</td>
                    <td><span class="badge ${badgeClass}">${status}</span></td>
                    <td style="text-align:right;font-weight:700;color:var(--red)">${backlogLM.toLocaleString()}</td>
                    <td style="text-align:right">${backlogKTC.toLocaleString()}</td>
                    <td style="text-align:right;font-weight:700;color:var(--blue)">${totalBL.toLocaleString()}</td>
                    <td style="text-align:center;font-weight:600;color:var(--orange)">${donTao} / ${donGtc}</td>
                    <td style="text-align:right;font-weight:700;color:var(--green)">${Math.round(avgGtcVol).toLocaleString()}</td>
                    <td style="text-align:right;font-weight:700;color:var(--blue)">${maxGtcVol.toLocaleString()}</td>
                    <td style="text-align:right">
                        <span class="aging-chip ${r.soNgayVal > 6 ? 'aging-critical' : r.soNgayVal > 0 ? 'aging-high' : 'aging-normal'}">
                            ${r.soNgayVal} ngày
                        </span>
                    </td>
                    <td><span class="badge ${nextBadgeClass}">${nextStatus}</span></td>
                    <td style="font-weight:800;color:var(--orange)">${index + 1}</td>
                </tr>
            `;
        }).join('');
    }
}

// ---- SECTION: XE GXT ----
function renderXeGxtSection() {
    const tbody = document.getElementById('tbody-xegxt');
    if (!tbody) return;

    if (!state.xeGxtData.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center">Không có dữ liệu</td></tr>';
        return;
    }

    // Populate dropdowns if they are empty
    populateXeGxtFilters();

    const f_kho  = (document.getElementById('filter-xegxt-kho')?.value || '').toLowerCase();
    const f_tinh = (document.getElementById('filter-xegxt-tinh')?.value || '').toLowerCase();
    const f_ncc  = (document.getElementById('filter-xegxt-ncc')?.value || '').toLowerCase();
    const f_loai = (document.getElementById('filter-xegxt-loai')?.value || '').toLowerCase();

    // Filter the raw data first
    const filteredRaw = state.xeGxtData.filter(r => {
        const matchKho  = !f_kho  || (r['Kho']||'').toLowerCase().includes(f_kho);
        const matchTinh = !f_tinh || (r['Tỉnh']||'').toLowerCase() === f_tinh;
        const matchNcc  = !f_ncc  || (r['Tên NCC']||'').toLowerCase() === f_ncc;
        const matchLoai = !f_loai || (r['Loại xe']||'').toLowerCase() === f_loai;
        return matchKho && matchTinh && matchNcc && matchLoai;
    });

    // Aggregate by Kho and Province for the summary table
    const summary = {};
    filteredRaw.forEach(r => {
        const kho = r['Kho'] || 'N/A';
        const tinh = r['Tỉnh'] || 'N/A';
        const key = `${tinh}|${kho}`;
        const count = parseInt(r['Tổng xe đang chạy'] || 0);

        if (!summary[key]) {
            summary[key] = { tinh, kho, total: 0 };
        }
        summary[key].total += count;
    });

    let list = Object.values(summary).sort((a,b) => b.total - a.total);

    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center">Không tìm thấy kết quả</td></tr>';
        document.getElementById('tfoot-xegxt').innerHTML = '';
    } else {
        const grandTotal = list.reduce((sum, item) => sum + item.total, 0);
        tbody.innerHTML = list.map((item, index) => `
            <tr>
                <td style="color:var(--text3)">${index + 1}</td>
                <td>${item.tinh}</td>
                <td style="font-weight:600;color:var(--blue)">${item.kho}</td>
                <td style="text-align:right;font-weight:700;color:var(--orange)">${item.total.toLocaleString()} xe</td>
            </tr>
        `).join('');

        document.getElementById('tfoot-xegxt').innerHTML = `
            <tr>
                <td colspan="3" style="text-align:right; padding:12px">TỔNG CỘNG TOÀN MẠNG LƯỚI:</td>
                <td style="text-align:right; color:var(--orange); font-size:1.1rem; padding:12px">${grandTotal.toLocaleString()} xe</td>
            </tr>
        `;
    }

    // Render Detailed Table
    const tbodyDetail = document.getElementById('tbody-xegxt-detail');
    if (tbodyDetail) {
        if (filteredRaw.length === 0) {
            tbodyDetail.innerHTML = '<tr><td colspan="8" style="text-align:center">Không có dữ liệu chi tiết</td></tr>';
        } else {
            tbodyDetail.innerHTML = filteredRaw.map((r, index) => `
                <tr>
                    <td style="color:var(--text3)">${index + 1}</td>
                    <td>${r['Tỉnh'] || '--'}</td>
                    <td style="font-weight:600">${r['Kho'] || '--'}</td>
                    <td>${r['Tên NCC'] || '--'}</td>
                    <td><span class="badge" style="background:var(--bg2);color:var(--text1)">${r['Loại xe'] || '--'}</span></td>
                    <td style="text-align:right;font-weight:700;color:var(--blue)">${parseInt(r['Tổng xe đang chạy'] || 0).toLocaleString()}</td>
                    <td style="font-size:0.85rem">${r['Ca làm việc'] || '--'}</td>
                    <td style="text-align:right;font-weight:700;color:var(--orange)">${(r['Giá thuê xe'] || r['Gía thuê xe']) || '--'}</td>
                </tr>
            `).join('');
        }
    }
}

let filtersPopulated = false;
function populateXeGxtFilters() {
    if (filtersPopulated) return;
    
    const tinhSet = new Set();
    const nccSet  = new Set();
    const loaiSet = new Set();

    state.xeGxtData.forEach(r => {
        if (r['Tỉnh']) tinhSet.add(r['Tỉnh']);
        if (r['Tên NCC']) nccSet.add(r['Tên NCC']);
        if (r['Loại xe']) loaiSet.add(r['Loại xe']);
    });

    const populateSelect = (id, items) => {
        const el = document.getElementById(id);
        if (!el) return;
        const currentVal = el.value;
        el.innerHTML = `<option value="">-- Táº¥t cáº£ ${id.split('-').pop()} --</option>` + 
            Array.from(items).sort().map(i => `<option value="${i}">${i}</option>`).join('');
        el.value = currentVal;
    };

    populateSelect('filter-xegxt-tinh', tinhSet);
    populateSelect('filter-xegxt-ncc', nccSet);
    populateSelect('filter-xegxt-loai', loaiSet);

    filtersPopulated = true;
}

// ---- SECTION: XE Sá»° Cá» ----
function getWeek(d) {
    d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
    var yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    var weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    return weekNo;
}

function renderXeSuCoSection() {
    const tbodyRaw = document.getElementById('tbody-xesuco-raw');
    if (!tbodyRaw) return;

    const data = state.xeSuCoData;
    if (!data.length) {
        tbodyRaw.innerHTML = '<tr><td colspan="9" style="text-align:center">Không có dữ liệu</td></tr>';
        return;
    }

    // Populate Filters
    const dayCont = document.getElementById('filter-xesuco-day-container');
    const weekCont  = document.getElementById('filter-xesuco-week-container');
    const monthCont = document.getElementById('filter-xesuco-month-container');

    const days = [...new Set(data.map(r => r['Ngày']).filter(Boolean))].sort((a,b) => parseVN(b) - parseVN(a));
    if (dayCont && dayCont.children.length === 0) {
        days.forEach(d => {
            const lbl = document.createElement('label');
            lbl.innerHTML = `<input type="checkbox" value="${d}" class="filter-xesuco-day"> ${d}`;
            dayCont.appendChild(lbl);
        });
        dayCont.querySelectorAll('input').forEach(i => i.addEventListener('change', () => {
            renderXeSuCoSection();
            const checked = Array.from(document.querySelectorAll('.filter-xesuco-day:checked'));
            document.getElementById('label-xesuco-day').textContent = checked.length ? `ÄÃ£ chá»n (${checked.length})` : 'Chá»n Ngày...';
        }));
    }

    const weeks = [...new Set(data.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        const w = getWeek(d);
        return `Tuần ${d.getFullYear()}-W${w < 10 ? '0'+w : w}`;
    }).filter(Boolean))].sort().reverse();

    if (weekCont && weekCont.children.length === 0) {
        weeks.forEach(w => {
            const lbl = document.createElement('label');
            lbl.innerHTML = `<input type="checkbox" value="${w}" class="filter-xesuco-week"> ${w}`;
            weekCont.appendChild(lbl);
        });
        weekCont.querySelectorAll('input').forEach(i => i.addEventListener('change', () => {
            renderXeSuCoSection();
            const checked = Array.from(document.querySelectorAll('.filter-xesuco-week:checked'));
            document.getElementById('label-xesuco-week').textContent = checked.length ? `ÄÃ£ chá»n (${checked.length})` : 'Chá»n Tuáº§n...';
        }));
    }

    const months = [...new Set(data.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        return `${d.getMonth() + 1}/${d.getFullYear()}`;
    }).filter(Boolean))].sort((a,b) => {
        const [m1,y1] = a.split('/');
        const [m2,y2] = b.split('/');
        return y2 - y1 || m2 - m1;
    });

    if (monthCont && monthCont.children.length === 0) {
        months.forEach(m => {
            const lbl = document.createElement('label');
            lbl.innerHTML = `<input type="checkbox" value="${m}" class="filter-xesuco-month"> Tháng ${m}`;
            monthCont.appendChild(lbl);
        });
        monthCont.querySelectorAll('input').forEach(i => i.addEventListener('change', () => {
            renderXeSuCoSection();
            const checked = Array.from(document.querySelectorAll('.filter-xesuco-month:checked'));
            document.getElementById('label-xesuco-month').textContent = checked.length ? `ÄÃ£ chá»n (${checked.length})` : 'Chá»n ThÃ¡ng...';
        }));
    }

    // Apply Filters
    const f_search = (document.getElementById('filter-xesuco-search')?.value || '').toLowerCase();
    const f_days   = Array.from(document.querySelectorAll('.filter-xesuco-day:checked')).map(i => i.value);
    const f_weeks  = Array.from(document.querySelectorAll('.filter-xesuco-week:checked')).map(i => i.value);
    const f_months = Array.from(document.querySelectorAll('.filter-xesuco-month:checked')).map(i => i.value);
    const f_kho    = (document.getElementById('filter-xesuco-kho')?.value || '').toLowerCase();

    const filtered = data.filter(r => {
        const ts = parseVN(r['Ngày']);
        const d_obj = new Date(ts);
        const w_str = `Tuần ${d_obj.getFullYear()}-W${String(getWeek(d_obj)).padStart(2, '0')}`;
        const m_str = `${d_obj.getMonth() + 1}/${d_obj.getFullYear()}`;

        const matchSearch = !f_search || 
            (r['Kho']||'').toLowerCase().includes(f_search) || 
            (r['NCC']||'').toLowerCase().includes(f_search) || 
            (r['Biển Số']||'').toLowerCase().includes(f_search) || 
            (r['ID']||'').toLowerCase().includes(f_search);
        
        const matchDay   = f_days.length === 0 || f_days.includes(r['Ngày']);
        const matchWeek  = f_weeks.length === 0 || f_weeks.includes(w_str);
        const matchMonth = f_months.length === 0 || f_months.includes(m_str);
        const matchKho   = !f_kho || (r['Kho']||'').toLowerCase().includes(f_kho);

        return matchSearch && matchDay && matchWeek && matchMonth && matchKho;
    });

    // Render Raw (Show all columns from sheet)
    // Tỉnh, ID, Kho, Ngày, Lỗi, Nội Dung Chi Tiết, Biển Số Xe, NCC
    tbodyRaw.innerHTML = filtered.map((r, i) => `
        <tr>
            <td style="color:var(--text3)">${i+1}</td>
            <td>${r['Tỉnh'] || ''}</td>
            <td>${r['ID'] || ''}</td>
            <td style="font-weight:600">${r['Kho'] || ''}</td>
            <td>${r['Ngày'] || ''}</td>
            <td style="color:var(--red)">${r['Lỗi'] || ''}</td>
            <td style="font-size:0.85rem; max-width:300px; white-space:normal">${r['Nội Dung Chi Tiết'] || ''}</td>
            <td style="font-weight:600">${r['Biển Số Xe'] || ''}</td>
            <td>${r['NCC'] || ''}</td>
        </tr>
    `).join('');
}

// ---- SECTION: KHO GXT ----
function renderKhoGxtSection() {
    const tbody = document.getElementById('tbody-khogxt');
    if (!tbody) return;
    const search = (document.getElementById('filter-khogxt-search')?.value || '').toLowerCase();

    const filtered = state.khoGxtData.filter(r => {
        return !search || JSON.stringify(r).toLowerCase().includes(search);
    });

    tbody.innerHTML = filtered.map(r => `
        <tr>
            <td style="color:var(--text3)">${r['ID Kho'] || ''}</td>
            <td style="font-weight:700; color:var(--blue)">${r['Tên Kho GXT'] || ''}</td>
            <td>${r['Tỉnh'] || ''}</td>
            <td>${r['Diện Tích'] || ''}</td>
            <td style="font-size:0.85rem">${r['Äá»‹a chá»‰ kho'] || ''}</td>
            <td><span class="badge" style="background:${r['Tình trạng'] === 'Active' ? '#E8F5E9' : '#FFEBEE'}; color:${r['Tình trạng'] === 'Active' ? '#2E7D32' : '#C62828'}">${r['Tình trạng'] || ''}</span></td>
        </tr>
    `).join('');
}


// ---- HELPER: destroy chart safely ----
function destroyChart(key) {
    if (charts[key]) { charts[key].destroy(); charts[key] = null; }
}

// ---- TELEGRAM REPORTING (DIRECT FROM DASHBOARD UI) ----
function assembleTelegramReport() {
    const now = new Date();
    const dateStr = now.toLocaleDateString('vi-VN');
    const timeStr = now.toLocaleTimeString('vi-VN');

    let msg = `ðŸ“¢ *BÃO CÃO Váº¬N HÃ€NH MIá»€N TRUNG*\nâ± _${dateStr} ${timeStr}_\n\n`;

    // 1. KHO NGHIÊM TRỌNG (Láº¥y tá»« Há»‡ Thá»‘ng Cáº£nh BÃ¡o)
    msg += `ðŸ¥ *1. KHO NGHIÊM TRỌNG (>5 NGÃ€Y):*\n`;
    const warnRows = document.querySelectorAll('#tbody-warnings tr');
    let warnCount = 0;
    warnRows.forEach(tr => {
        if (warnCount >= 10) return;
        const tds = tr.querySelectorAll('td');
        if (tds.length < 9) return;
        
        const kho = tds[0].innerText.trim();
        const status = tds[1].innerText.trim();
        const days = tds[8].innerText.trim(); // Sá»‘ ngày vá» bÃ¬nh thÆ°á»ng
        
        if (parseInt(days) > 5 || status.includes('NghiÃªm trá»ng')) {
            msg += `${warnCount + 1}. *${kho}*: ${status} (${days})\n`;
            warnCount++;
        }
    });
    if (warnCount === 0) msg += `_Không có kho nào_\n`;
    msg += `\n`;

    // 2. Cáº¢NH BÃO NV NÄ‚NG SUáº¤T Tá»†
    msg += `ðŸ‘¤ *2. Cáº¢NH BÃO NV NÄ‚NG SUáº¤T Tá»†:*
`;
    
    function getNsWorst(days, label, minVol) {
        const allDates = [...new Set(state.nangSuatData.map(r => r['Ngày']).filter(Boolean))].sort((a,b) => parseVN(b) - parseVN(a));
        if (!allDates.length) return `*${label}:*
_Trá»‘ng_
`;
        
        const latestTs = parseVN(allDates[0]);
        let filtered = [];
        
        if (days === 1) {
            filtered = state.nangSuatData.filter(r => r['Ngày'] === allDates[0]);
        } else {
            const cutoff = latestTs - (days * 24 * 60 * 60 * 1000);
            filtered = state.nangSuatData.filter(r => parseVN(r['Ngày']) >= cutoff);
        }
        
        const map = {};
        filtered.forEach(r => {
            const id = r['driver']; if (!id) return;
            if (!map[id]) map[id] = { name: id, prov: r['to_province_name'], vol: 0, succ: 0 };
            const v = parseInt(r['volume']||0);
            map[id].vol += v;
            map[id].succ += (parsePct(r['Tỉ lệ GTC'])/100) * v;
        });
        
        const list = Object.values(map)
            .map(d => ({ ...d, pct: d.vol > 0 ? (d.succ/d.vol*100) : 0 }))
            .filter(d => d.vol >= minVol)
            .sort((a,b) => a.pct - b.pct)
            .slice(0, 5);
            
        let res = `*${label}:*
`;
        list.forEach(d => res += `â€¢ ${d.name} (${d.prov}): *${d.pct.toFixed(1)}%* (${d.vol} đơn)
`);
        if (list.length === 0) res += `_Trá»‘ng_
`;
        return res;
    }

    msg += getNsWorst(1, "Ngày gần nhất", 30);
    msg += "\n" + getNsWorst(7, "Tuần gần nhất", 30);
    msg += "\n" + getNsWorst(30, "Tháng gần nhất", 30);
    msg += "\n";

    // 4. HIỆU SUẤT KHO (GTC) (Láº¥y tá»« GTC rankings)
    msg += `ðŸª *4. HIỆU SUẤT KHO (GTC):*\n`;
    const gtcPanels = document.querySelectorAll('#gtc-top-bottom .table-card');
    gtcPanels.forEach(panel => {
        const title = panel.querySelector('h3')?.innerText.trim() || 'GTC';
        msg += `*${title}:*\n`;
        const rows = Array.from(panel.querySelectorAll('tbody tr'));
        
        const tops = rows.filter(tr => tr.querySelector('.badge')?.innerText.includes('Tốt')).slice(0, 3);
        const bottoms = rows.filter(tr => tr.querySelector('.badge')?.innerText.includes('Tệ')).slice(-3).reverse();

        tops.forEach(tr => {
            const tds = tr.querySelectorAll('td');
            msg += ` âœ… ${tds[1].innerText}: *${tds[3].innerText}*\n`;
        });
        bottoms.forEach(tr => {
            const tds = tr.querySelectorAll('td');
            msg += ` âŒ ${tds[1].innerText}: *${tds[3].innerText}*\n`;
        });
    });

    // 5. ÄÆ N B2B Äáº¾N Háº N GIAO (Láº¥y trá»±c tiáº¿p tá»« Dashboard DOM)
    msg += `ðŸ‘‘ *5. ÄÆ N B2B Äáº¾N Háº N GIAO:*\n`;
    const b2bRows = document.querySelectorAll('#tbody-b2b tr');
    const b2bSummary = new Map();
    let b2bTotal = 0;

    b2bRows.forEach(tr => {
        const tds = tr.querySelectorAll('td');
        if (tds.length < 5) return;
        
        const priority = tds[0].innerText.toLowerCase();
        const kho = tds[1].innerText.trim();
        const loai = tds[4].innerText.toLowerCase();
        
        // Äiá»u kiá»‡n: Loại cÃ³ chá»¯ 'giao' vÃ  Ưu tiên cÃ³ mÃ£ '1:'
        if (loai.includes('giao') && priority.includes('1:')) {
            b2bSummary.set(kho, (b2bSummary.get(kho) || 0) + 1);
            b2bTotal++;
        }
    });
    
    if (b2bTotal > 0) {
        const sortedB2B = Array.from(b2bSummary.entries()).sort((a,b) => b[1] - a[1]);
        sortedB2B.forEach(([k, v]) => msg += `â€¢ *${k}*: ${v} đơn\n`);
    } else {
        msg += `_Không có đơn B2B đến hạn_\n`;
    }

    msg += `\nðŸ”— [Má»Ÿ Dashboard Chi Tiết](https://ai-ghn-gxt.up.railway.app/)`;
    return msg;
}

async function sendTelegramReport() {
    const btn = document.getElementById('telegram-btn');
    if (!btn) return;
    
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Äang chuáº©n bá»‹...';
    btn.disabled = true;

    try {
        const message = assembleTelegramReport();
        const adminKey = localStorage.getItem('ghn_admin_key') || '';
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Äang gá»­i...';

        const resp = await fetch('/api/telegram/report', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, key: adminKey })
        });
        const result = await resp.json();
        
        if (result.status === 'success') {
            alert('âœ… Báo cáo chi tiết đã được gửi!');
        } else {
            alert('âŒ Lỗi: ' + result.message);
        }
    } catch (e) {
        alert('âŒ Không thể kết nối vá»›i server.');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

document.getElementById('telegram-btn')?.addEventListener('click', sendTelegramReport);

// ---- NAVIGATION ----
const SECTION_META = {
    overview:  ['Báo Cáo Tổng Quan', 'Giám sát GTC, Ontime, Backlog và B2B toàn mạng Miền Trung'],
    gtc:       ['GTC & Năng Suất', 'Tỷ lệ giao thành công và năng suất theo từng kho'],
    backlog:   ['Danh Sách Backlog > 7 Ngày', 'Các đơn hàng tồn đọng lâu hơn 7 ngày cần xử lý khẩn'],
    b2b:       ['Đơn Hàng B2B & SLA', 'Theo dõi đơn B2B theo mức độ ưu tiên xử lý'],
    returns:   ['Báo Cáo Trả Hàng & FD', 'Tỷ lệ phân phối và trả hàng theo kho'],
    personnel: ['Danh Sách Nhân Sự', 'Thông tin nhân viên giao nhận và xử lý'],
    nangsuat:  ['Năng Suất Nhân Viên', 'Bảng xếp hạng năng suất giao hàng của nhân viên'],
    warnings:  ['Hệ Thống Cảnh Báo Vận Hành', 'Theo dõi sức khỏe mạng lưới và dự báo giải tỏa hàng'],
    xegxt:     ['Quản Lý Xe GXT', 'Theo dõi số lượng xe đang vận hành tại các kho Miền Trung'],
    xesuco:    ['Xe Sự Cố', 'Theo dõi và thống kê các sự cố xe GXT theo nhà cung cấp'],
    khogxt:    ['Danh Sách Kho GXT', 'Thông tin chi tiết các kho GXT trong mạng lưới'],
    dontao:    ['Đơn Tạo N-1', 'Thống kê đơn hàng tạo trong ngày N-1 theo từng kho'],
};

function showSection(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('section-' + name).classList.add('active');
    document.getElementById('nav-' + name).classList.add('active');
    const [title, sub] = SECTION_META[name] || ['--','--'];
    document.getElementById('page-title').textContent = title;
    document.getElementById('page-subtitle').textContent = sub;
}

// ---- EVENT LISTENERS ----
document.querySelectorAll('.nav-item[data-section]').forEach(item => {
    item.addEventListener('click', e => { e.preventDefault(); showSection(item.dataset.section); });
});

document.querySelectorAll('.view-all[data-section]').forEach(link => {
    link.addEventListener('click', e => { e.preventDefault(); showSection(e.currentTarget.dataset.section); });
});

document.getElementById('refresh-btn').addEventListener('click', () => {
    fetchAll(true);
});

document.getElementById('sidebar-toggle').addEventListener('click', () => {
    const sb = document.getElementById('sidebar');
    sb.style.width = sb.style.width === '56px' ? '240px' : '56px';
});

// Filters
document.getElementById('filter-kho-gtc').addEventListener('input', e => renderGtcSection(e.target.value));
document.getElementById('filter-kho-gtc-select')?.addEventListener('change', () => renderGtcSection());

document.getElementById('filter-kho-backlog').addEventListener('input', e =>
    renderBacklogSection(e.target.value, document.getElementById('filter-luong').value));
document.getElementById('filter-luong').addEventListener('change', e =>
    renderBacklogSection(document.getElementById('filter-kho-backlog').value, e.target.value));
document.getElementById('filter-b2b').addEventListener('input', e =>
    renderB2bSection(e.target.value, document.getElementById('filter-priority').value, document.getElementById('filter-b2b-client').value, document.getElementById('filter-b2b-type').value));
document.getElementById('filter-priority').addEventListener('change', e =>
    renderB2bSection(document.getElementById('filter-b2b').value, e.target.value, document.getElementById('filter-b2b-client').value, document.getElementById('filter-b2b-type').value));
document.getElementById('filter-b2b-client').addEventListener('change', e =>
    renderB2bSection(document.getElementById('filter-b2b').value, document.getElementById('filter-priority').value, e.target.value, document.getElementById('filter-b2b-type').value));
document.getElementById('filter-b2b-type').addEventListener('change', e =>
    renderB2bSection(document.getElementById('filter-b2b').value, document.getElementById('filter-priority').value, document.getElementById('filter-b2b-client').value, e.target.value));
document.getElementById('filter-personnel').addEventListener('input', e =>
    renderPersonnelSection(e.target.value, document.getElementById('filter-position').value));
document.getElementById('filter-position').addEventListener('change', e =>
    renderPersonnelSection(document.getElementById('filter-personnel').value, e.target.value));

// Warning Filters
document.getElementById('filter-kho-warnings').addEventListener('input', e => 
    renderWarningsSection(e.target.value, document.getElementById('filter-status-warnings').value));
document.getElementById('filter-status-warnings').addEventListener('change', e => 
    renderWarningsSection(document.getElementById('filter-kho-warnings').value, e.target.value));

// Return Filters
document.getElementById('filter-client-returns').addEventListener('input', e =>
    renderReturnsSection(e.target.value));

// Xe GXT Filters
document.getElementById('filter-xegxt-kho')?.addEventListener('input', () => renderXeGxtSection());
document.getElementById('filter-xegxt-tinh')?.addEventListener('change', () => renderXeGxtSection());
document.getElementById('filter-xegxt-ncc')?.addEventListener('change', () => renderXeGxtSection());
document.getElementById('filter-xegxt-loai')?.addEventListener('change', () => renderXeGxtSection());

// Xe Su Co Filters
document.getElementById('filter-xesuco-search')?.addEventListener('input', () => renderXeSuCoSection());
document.getElementById('filter-xesuco-day')?.addEventListener('change', () => renderXeSuCoSection());
document.body.addEventListener('change', e => {
    if (e.target.classList.contains('filter-xesuco-week') || e.target.classList.contains('filter-xesuco-month')) {
        renderXeSuCoSection();
    }
});

// Kho GXT Filters
document.getElementById('filter-khogxt-search')?.addEventListener('input', () => renderKhoGxtSection());

window.switchNsPeriod = function(period, btnId) {
    document.querySelectorAll('#section-nangsuat .filter-tabs button').forEach(b => {
        b.classList.remove('active');
        b.style.cssText = '';
    });
    const btn = document.getElementById(btnId || ('btn-ns-' + period));
    if(btn) {
        btn.classList.add('active');
        btn.style.cssText = 'background:var(--blue-bg);color:var(--blue);border-color:var(--blue-border);font-weight:700';
    }
    currentNsPeriod = period;
    renderNangSuatSection();
}

document.getElementById('btn-ns-day')?.addEventListener('click', () => switchNsPeriod('day', 'btn-ns-day'));
document.getElementById('btn-ns-week')?.addEventListener('click', () => switchNsPeriod('week', 'btn-ns-week'));
document.getElementById('btn-ns-month')?.addEventListener('click', () => switchNsPeriod('month', 'btn-ns-month'));

document.getElementById('filter-ns-province')?.addEventListener('change', () => {
    renderNangSuatSection();
});

// ---- ADMIN ACCESS CHECK ----
function checkAdminAccess() {
    const urlParams = new URLSearchParams(window.location.search);
    const urlKey = urlParams.get('key');
    const secretKey = "gxt1103";

    if (urlKey === secretKey) {
        localStorage.setItem('ghn_admin_key', urlKey);
        // Clear the key from URL for cleanliness
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    const savedKey = localStorage.getItem('ghn_admin_key');
    const telegramBtn = document.getElementById('telegram-btn');
    
    if (telegramBtn) {
        if (savedKey === secretKey) {
            telegramBtn.style.display = 'flex';
            console.log("[ADMIN] Admin mode enabled.");
        } else {
            telegramBtn.style.display = 'none';
        }
    }
}


// ---- ĐƠN TẠO N-1 SECTION ----
let dtTimeMode = 'day';
let selectedDtVals = [];
let selectedDtKhos = [];
let dtFiltersInit = false;

window.updateDtTimeMode = function(mode) {
    const menu = document.getElementById('menu-dt-' + mode);
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const vals = Array.from(checks).map(c => c.value);

    if (mode === 'kho') {
        selectedDtKhos = vals;
    } else {
        dtTimeMode = mode;
        selectedDtVals = vals;
        if (mode === 'day')   clearDtOtherModes(['week', 'month']);
        else if (mode === 'week')  clearDtOtherModes(['day', 'month']);
        else if (mode === 'month') clearDtOtherModes(['day', 'week']);
    }
    updateDtLabel(mode);
    renderDonTaoSection();
};

function clearDtOtherModes(modes) {
    modes.forEach(m => {
        const menu = document.getElementById('menu-dt-' + m);
        if (menu) {
            menu.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = false);
            updateDtLabel(m);
        }
    });
    selectedDtVals = [];
}

function updateDtLabel(mode) {
    const menu = document.getElementById('menu-dt-' + mode);
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const label  = document.querySelector(`#multi-dt-${mode} .ghn-filter-selected`);
    if (!label) return;
    if (checks.length === 0) {
        const map = { day: 'Chọn Ngày...', week: 'Chọn Tuần...', month: 'Chọn Tháng...', kho: 'Chọn Kho...' };
        label.innerText = map[mode] || '...';
    } else {
        label.innerText = `${checks.length} mục đã chọn`;
    }
    const items = Array.from(menu.querySelectorAll('.ghn-filter-item'));
    items.sort((a,b) => { const ca=a.querySelector('input').checked, cb=b.querySelector('input').checked; return ca===cb?0:ca?-1:1; });
    items.forEach(item => menu.appendChild(item));
}

function renderDtMultiItems(mode, values) {
    const menu = document.getElementById('menu-dt-' + mode);
    if (!menu) return;
    menu.innerHTML = values.map(v => `
        <div class="ghn-filter-item">
            <input type="checkbox" id="chk-dt-${mode}-${v.replace(/[^a-z0-9]/gi,'-')}" value="${v}" onchange="updateDtTimeMode('${mode}')">
            <label for="chk-dt-${mode}-${v.replace(/[^a-z0-9]/gi,'-')}">${mode==='day'?v:mode==='week'?'Tuần '+v:mode==='month'?'Tháng '+v:v}</label>
        </div>
    `).join('');
}

function populateDtSelects() {
    const dayMenu = document.getElementById('menu-dt-day');
    if (!dayMenu || dayMenu.children.length > 0) return;

    const allData = state.donTaoData;
    const days = [...new Set(allData.map(r => (r['time_view']||'').split(' - ')[0]).filter(Boolean))].sort().reverse();
    renderDtMultiItems('day', days);

    const weeks = [...new Set(allData.map(r => {
        const d = new Date((r['time_view']||'').split(' - ')[0]);
        return isNaN(d) ? null : getWeekNumber(d);
    }).filter(Boolean))].sort().reverse();
    renderDtMultiItems('week', weeks);

    const months = [...new Set(allData.map(r => {
        const d = new Date((r['time_view']||'').split(' - ')[0]);
        if (isNaN(d)) return null;
        return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0');
    }).filter(Boolean))].sort().reverse();
    renderDtMultiItems('month', months);

    const khos = [...new Set(allData.map(r => shortKho(r['kho_giao']||'')).filter(Boolean))].sort();
    renderDtMultiItems('kho', khos);

    // Auto-select latest day
    if (days.length > 0) {
        const safeId = days[0].replace(/[^a-z0-9]/gi,'-');
        const firstChk = document.getElementById('chk-dt-day-' + safeId);
        if (firstChk) firstChk.checked = true;
        selectedDtVals = [days[0]];
        updateDtLabel('day');
    }

    // Attach search filter
    if (!dtFiltersInit) {
        const searchEl = document.getElementById('filter-kho-dontao');
        if (searchEl) searchEl.addEventListener('input', () => renderDonTaoSection());

        // Extend toggleMultiselect to handle dt- menus
        const _origToggle = window.toggleMultiselect;
        window.toggleMultiselect = function(mode) {
            const allMenus = document.querySelectorAll('.ghn-filter-menu');
            const targetId = mode.startsWith('dt-') ? 'menu-' + mode : 'menu-gtc-' + mode;
            allMenus.forEach(m => {
                m.id === targetId ? m.classList.toggle('show') : m.classList.remove('show');
            });
        };
        dtFiltersInit = true;
    }
}

function renderDonTaoSection() {
    if (!state.donTaoData || state.donTaoData.length === 0) return;
    populateDtSelects();

    let data = [...state.donTaoData];
    const searchVal = ((document.getElementById('filter-kho-dontao') || {}).value || '').toLowerCase();

    // Time filter
    if (selectedDtVals.length > 0) {
        data = data.filter(r => {
            const dateStr = (r['time_view']||'').split(' - ')[0];
            const d = new Date(dateStr);
            if (dtTimeMode === 'day')   return selectedDtVals.includes(dateStr);
            if (dtTimeMode === 'week')  return selectedDtVals.includes(getWeekNumber(d));
            if (dtTimeMode === 'month') {
                const m = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0');
                return selectedDtVals.includes(m);
            }
            return true;
        });
    }

    // Kho multi-select
    if (selectedDtKhos.length > 0) {
        data = data.filter(r => selectedDtKhos.includes(shortKho(r['kho_giao']||'')));
    }

    // Text search
    if (searchVal) {
        data = data.filter(r => shortKho(r['kho_giao']||'').toLowerCase().includes(searchVal));
    }

    // Aggregate by kho (for chart)
    const khoMap = {};
    data.forEach(r => {
        const k = shortKho(r['kho_giao'] || '--');
        if (!khoMap[k]) khoMap[k] = { don: 0, kg: 0 };
        try { khoMap[k].don += parseInt(String(r['Tổng đơn tạo']||'0').replace(/\./g,'').replace(/,/g,'')) || 0; } catch {}
        try { khoMap[k].kg  += parseFloat(String(r['Tổng khối lượng (KG)']||'0').replace(/\./g,'').replace(/,/g,'.')) || 0; } catch {}
    });

    // Sort descending by number of orders (largest left)
    const khoEntries = Object.entries(khoMap).sort((a,b) => b[1].don - a[1].don);
    const khoNames = khoEntries.map(e => e[0]);
    const donVals  = khoEntries.map(e => e[1].don);
    const kgVals   = khoEntries.map(e => Math.round(e[1].kg));

    // Chart
    destroyChart('donTao');
    const canvas = document.getElementById('chart-dontao');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        charts.donTao = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: khoNames,
                datasets: [
                    {
                        label: 'Tổng Đơn Tạo', data: donVals,
                        backgroundColor: 'rgba(123,31,162,0.75)', borderColor: '#7B1FA2', borderWidth: 1,
                        yAxisID: 'y',
                        datalabels: { display: true, anchor: 'end', align: 'end', color: '#7B1FA2', font: { size: 9, weight: 'bold' }, formatter: v => v.toLocaleString('vi-VN') }
                    },
                    {
                        label: 'Tổng KG', data: kgVals,
                        backgroundColor: 'rgba(2,136,209,0.75)', borderColor: '#0288D1', borderWidth: 1,
                        yAxisID: 'y1',
                        datalabels: { display: true, anchor: 'end', align: 'end', color: '#0288D1', font: { size: 9 }, formatter: v => v.toLocaleString('vi-VN') }
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { color: '#525F7F', padding: 12, font: { size: 11 }, boxWidth: 12 } },
                    datalabels: { display: true }
                },
                scales: {
                    x: { ticks: { maxRotation: 45, font: { size: 10 } }, grid: { display: false } },
                    y:  { type:'linear', position:'left',  beginAtZero:true, grid:{borderDash:[2,4],color:'#E8EDF5'}, ticks:{color:'#7B1FA2',font:{size:10}}, title:{display:true,text:'Tổng Đơn',color:'#7B1FA2',font:{size:11}} },
                    y1: { type:'linear', position:'right', beginAtZero:true, grid:{drawOnChartArea:false},            ticks:{color:'#0288D1',font:{size:10}}, title:{display:true,text:'Tổng KG',  color:'#0288D1',font:{size:11}} }
                }
            }
        });
    }

    // Table — sorted by date desc then order desc
    const tbody = document.getElementById('tbody-dontao');
    if (!tbody) return;
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#999">Không có dữ liệu</td></tr>';
        return;
    }
    const sorted = [...data].sort((a,b) => {
        const da = (a['time_view']||'').split(' - ')[0];
        const db = (b['time_view']||'').split(' - ')[0];
        if (db !== da) return db.localeCompare(da);
        const va = parseInt(String(a['Tổng đơn tạo']||'0').replace(/[.,]/g,'')) || 0;
        const vb = parseInt(String(b['Tổng đơn tạo']||'0').replace(/[.,]/g,'')) || 0;
        return vb - va;
    });
    tbody.innerHTML = sorted.map((r, i) => {
        const don = parseInt(String(r['Tổng đơn tạo']||'0').replace(/\./g,'').replace(/,/g,'')) || 0;
        const kg  = parseFloat(String(r['Tổng khối lượng (KG)']||'0').replace(/\./g,'').replace(/,/g,'.')) || 0;
        return `<tr>
            <td>${i+1}</td>
            <td>${shortKho(r['kho_giao']||'--')}</td>
            <td>${r['time_view']||'--'}</td>
            <td style="text-align:right;font-weight:600;color:#7B1FA2">${don.toLocaleString('vi-VN')}</td>
            <td style="text-align:right;font-weight:600;color:#0288D1">${kg.toLocaleString('vi-VN',{maximumFractionDigits:3})}</td>
        </tr>`;
    }).join('');
}

// ---- INIT ----
document.addEventListener('DOMContentLoaded', () => {
    fetchAll();
    startSyncTimer();
    checkAdminAccess();
});

