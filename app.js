const API = window.location.origin + '/api';

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
    warningsData: [],
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
    return k.replace('Kho Giao Hàng Nặng - ', '');
}

function parsePct(str) {
    return parseFloat((str||'0').replace('%','').replace(',','.')) || 0;
}

// ---- FETCH ALL ----
async function fetchAll() {
    try {
        const [ov, gtc, ontime, ret, bl, b2b, pers, ns, warn] = await Promise.all([
            fetch(`${API}/dashboard/overview`).then(r => r.json()),
            fetch(`${API}/kpi/gtc`).then(r => r.json()),
            fetch(`${API}/kpi/ontime`).then(r => r.json()),
            fetch(`${API}/returns`).then(r => r.json()),
            fetch(`${API}/backlog/critical`).then(r => r.json()),
            fetch(`${API}/backlog/b2b`).then(r => r.json()),
            fetch(`${API}/personnel`).then(r => r.json()),
            fetch(`${API}/nang-suat`).then(r => r.json()),
            fetch(`${API}/warnings`).then(r => r.json()),
        ]);
        state = { overview: ov, gtcData: gtc, ontimeData: ontime, returnsData: ret, backlogData: bl, b2bData: b2b, personnelData: pers, nangSuatData: ns, warningsData: warn };
        renderAll();
    } catch(e) {
        console.error('Fetch error:', e);
    }
}

// ---- RENDER ALL ----
function renderAll() {
    updateMeta();
    renderOverviewCards();
    renderGtcTrendChart();
    renderReturnsPieChart();
    renderBacklogOverviewTable();
    renderB2bOverviewTable();
    renderPersonnelOverview();
    renderGtcSection();
    renderGtcByKhoChart();
    renderGtcTopBottom();
    renderBacklogSection();
    renderBacklogByKhoChart();
    renderB2bSection();
    renderReturnsSection();
    renderReturnsFDChart();
    renderPersonnelSection();
    renderNangSuatSection();
    renderWarningsSection();
    updateNavBadges();
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
    document.getElementById('val-ontime').textContent = (ov.avg_ontime || 0) + '%';
    document.getElementById('val-backlog').textContent = ov.total_backlog_7n || 0;
    document.getElementById('val-b2b').textContent    = ov.total_b2b_priority || 0;
    document.getElementById('val-fd').textContent     = (ov.avg_fd_return || 0) + '%';
    const valNangSuatEl = document.getElementById('val-nangsuat');
    if (valNangSuatEl) valNangSuatEl.textContent = (ov.avg_nang_suat || 0);
    document.getElementById('sub-gtc').textContent    = 'Ngày: ' + (ov.latest_date || '--');
}

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

// ---- GTC TREND CHART (last 14 days) ----
function renderGtcTrendChart() {
    const dateMap = {};
    state.gtcData.forEach(r => {
        const d = (r['Ngày'] || '').split(' - ')[0];
        if (!d) return;
        if (!dateMap[d]) dateMap[d] = { total: 0, gtc: 0 };
        dateMap[d].total += parseInt(r['Số đơn gán'] || 0);
        dateMap[d].gtc   += parseInt(r['Số đơn GTC'] || 0);
    });
    // Only last 14 days, sorted oldest -> newest
    const allDates = Object.keys(dateMap).sort();
    const labels = allDates.slice(-14);
    const values = labels.map(d => dateMap[d].total
        ? +(dateMap[d].gtc / dateMap[d].total * 100).toFixed(2) : 0);

    destroyChart('gtcTrend');
    const ctx = document.getElementById('chart-gtc-trend').getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 180);
    grad.addColorStop(0, 'rgba(255,82,0,0.18)');
    grad.addColorStop(1, 'rgba(255,82,0,0)');

    charts.gtcTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '% GTC',
                data: values,
                borderColor: C_ORANGE,
                backgroundColor: grad,
                borderWidth: 2.5,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#fff',
                pointBorderColor: C_ORANGE,
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7,
                datalabels: {
                    align: 'top',
                    color: C_ORANGE,
                    font: { weight: 'bold', size: 10 },
                    formatter: function(value) {
                        return value + '%';
                    }
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
                y: {
                    min: 60, max: 100,
                    grid: { color: '#F0F3F8', drawBorder: false },
                    ticks: { callback: v => v + '%', font: { size: 11 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 11 } }
                }
            }
        }
    });
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
    const sorted = [...state.backlogData]
        .sort((a,b) => parseInt(b['backlog_aging']||0) - parseInt(a['backlog_aging']||0))
        .slice(0, 7);
    tbody.innerHTML = sorted.map(r => `
        <tr>
            <td class="order-code">${r['order_code'] || '--'}</td>
            <td>${shortKho(r['kho_giao'] || r['Kho'] || '--')}</td>
            <td>${agingChip(r['backlog_aging'] || r['Số ngày tồn'])}</td>
            <td>${r['client_type'] || '--'}</td>
            <td>${r['status'] || '--'}</td>
        </tr>
    `).join('');
}

// ---- B2B OVERVIEW TABLE ----
function renderB2bOverviewTable() {
    const tbody = document.getElementById('tbody-b2b-overview');
    const prio = ['1: trong hôm nay','2: trong ngày mai','3: trong ngày mốt'];
    const sorted = [...state.b2bData]
        .sort((a,b) => prio.indexOf(a['Mức độ ưu tiên']) - prio.indexOf(b['Mức độ ưu tiên']))
        .slice(0, 7);
    tbody.innerHTML = sorted.map(r => `
        <tr>
            <td class="order-code">${r['Order code'] || '--'}</td>
            <td>${shortKho(r['Kho hiện tại'])}</td>
            <td>${agingChip(r['Đã lưu kho (ngày)'])}</td>
            <td>${r['Khách'] || '--'}</td>
            <td>${priorityBadge(r['Mức độ ưu tiên'])}</td>
        </tr>
    `).join('');
}

// ---- GTC SECTION TABLE ----
function renderGtcSection(filter = '') {
    let data = state.gtcData;
    // Tự động lọc ngày gần nhất (latest date) nếu không có filter
    const dates = [...new Set(data.map(r => r['Ngày']||''))].sort().reverse();
    const latestDate = dates[0] || '';
    
    // Mặc định luôn show dữ liệu của ngày gần nhất
    data = data.filter(r => (r['Ngày']||'') === latestDate);

    if (filter) data = data.filter(r => shortKho(r['Kho']).toLowerCase().includes(filter.toLowerCase()));
    
    document.getElementById('tbody-gtc').innerHTML = data.map(r => `
        <tr>
            <td>${r['STT']||''}</td>
            <td>${shortKho(r['Kho'])}</td>
            <td>${r['Ngày']||''}</td>
            <td>${r['KL gán']||''}</td>
            <td>${r['Số đơn gán']||''}</td>
            <td>${r['Số đơn GTC']||''}</td>
            <td class="${pctClass(r['% GTC'])}">${r['% GTC']||''}</td>
        </tr>
    `).join('');
}

// ---- GTC BY KHO BAR CHART ----
function renderGtcByKhoChart() {
    const dates = [...new Set(state.gtcData.map(r => (r['Ngày']||'').split(' - ')[0]))].sort().reverse();
    const latest = dates[0] || '';
    const latestRows = state.gtcData.filter(r => (r['Ngày']||'').startsWith(latest));
    const sorted = [...latestRows].sort((a,b) => parsePct(a['% GTC']) - parsePct(b['% GTC']));

    const labels = sorted.map(r => shortKho(r['Kho']));
    const values = sorted.map(r => parsePct(r['% GTC']));
    const colors = values.map(v => v >= 90 ? C_GREEN : v >= 80 ? C_ORANGE : C_RED);

    // Auto-scale height: 32px per bar + 40px padding
    const chartHeight = Math.max(200, labels.length * 32 + 40);
    const wrapper = document.getElementById('gtc-by-kho-wrapper') || document.getElementById('chart-gtc-by-kho').parentElement;
    wrapper.style.height = chartHeight + 'px';

    destroyChart('gtcByKho');
    const ctx = document.getElementById('chart-gtc-by-kho').getContext('2d');
    charts.gtcByKho = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label: '% GTC', data: values, backgroundColor: colors, borderRadius: 5, borderSkipped: false,
                datalabels: {
                    anchor: 'end', align: 'right',
                    color: ctx2 => colors[ctx2.dataIndex],
                    font: { weight: 'bold', size: 11 },
                    formatter: v => v + '%'
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            layout: { padding: { right: 40 } },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => ' ' + c.raw + '%' } },
                datalabels: { display: true }
            },
            scales: {
                x: { min: 60, max: 100, grid: { color: '#F0F3F8' }, ticks: { callback: v => v+'%', font: {size:11} } },
                y: { grid: { display: false }, ticks: { font: { size: 11 } } }
            }
        }
    });
}

// ---- GTC TOP / BOTTOM BY PERIOD ----
function renderGtcTopBottom() {
    const el = document.getElementById('gtc-top-bottom');
    if (!el) return;

    // Get all distinct dates sorted desc
    const allDates = [...new Set(state.gtcData.map(r => (r['Ngày']||'').split(' - ')[0]).filter(Boolean))].sort().reverse();
    if (!allDates.length) return;

    const latestDate = allDates[0];
    const cutoffWeek  = allDates[Math.min(6,  allDates.length - 1)];
    const cutoffMonth = allDates[Math.min(29, allDates.length - 1)];

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
            .filter(([,v]) => v.gan >= 10) // ignore kho with very few orders
            .map(([k, v]) => ({ kho: k, pct: +(v.gtc / v.gan * 100).toFixed(2), gtc: v.gtc, gan: v.gan }))
            .sort((a, b) => b.pct - a.pct);
    }

    const rowsDay   = state.gtcData.filter(r => (r['Ngày']||'').startsWith(latestDate));
    const rowsWeek  = state.gtcData.filter(r => (r['Ngày']||'').split(' - ')[0] >= cutoffWeek);
    const rowsMonth = state.gtcData.filter(r => (r['Ngày']||'').split(' - ')[0] >= cutoffMonth);

    const rankDay   = computeKhoRanking(rowsDay);
    const rankWeek  = computeKhoRanking(rowsWeek);
    const rankMonth = computeKhoRanking(rowsMonth);

    function renderPanel(title, icon, ranking, colorTop) {
        if (!ranking.length) return '<div class="table-card"><div class="table-header"><h3>' + title + '</h3></div><p style="padding:16px;color:var(--text3)">Không có dữ liệu</p></div>';
        const best  = ranking[0];
        const worst = ranking[ranking.length - 1];
        return `
        <div class="table-card">
            <div class="table-header">
                <h3><i class="fa-solid ${icon}" style="color:var(--orange)"></i> ${title}</h3>
                <span class="count-badge">${ranking.length} kho</span>
            </div>
            <table class="data-table mini-table">
                <thead><tr><th>Hạng</th><th>Kho</th><th style="text-align:right">Đơn Gán</th><th style="text-align:right">% GTC</th></tr></thead>
                <tbody>
                    <tr style="background:var(--green-bg)">
                        <td><span class="badge storing">↑ Tốt nhất</span></td>
                        <td style="font-weight:600">${best.kho}</td>
                        <td style="text-align:right;color:var(--text3)">${best.gan.toLocaleString()}</td>
                        <td style="text-align:right;font-weight:800;color:var(--green);font-size:15px">${best.pct}%</td>
                    </tr>
                    <tr style="background:var(--red-bg)">
                        <td><span class="badge p1">↓ Tệ nhất</span></td>
                        <td style="font-weight:600">${worst.kho}</td>
                        <td style="text-align:right;color:var(--text3)">${worst.gan.toLocaleString()}</td>
                        <td style="text-align:right;font-weight:800;color:var(--red);font-size:15px">${worst.pct}%</td>
                    </tr>
                </tbody>
            </table>
            <div style="padding:10px 14px;border-top:1px solid #F0F3F8">
                <details>
                    <summary style="cursor:pointer;font-size:12px;color:var(--blue);font-weight:600">Xem xếp hạng đầy đủ (${ranking.length} kho)</summary>
                    <table class="data-table mini-table" style="margin-top:8px">
                        <thead><tr><th>#</th><th>Kho</th><th style="text-align:right">% GTC</th></tr></thead>
                        <tbody>
                            ${ranking.map((r,i) => `
                            <tr>
                                <td style="font-weight:700;color:${i===0?'var(--green)':i===ranking.length-1?'var(--red)':'var(--text3)'}">${i+1}</td>
                                <td>${r.kho}</td>
                                <td style="text-align:right;font-weight:700;color:${r.pct>=90?'var(--green)':r.pct>=80?'var(--orange)':'var(--red)'}">${r.pct}%</td>
                            </tr>`).join('')}
                        </tbody>
                    </table>
                </details>
            </div>
        </div>`;
    }

    el.innerHTML = `
        <div class="tables-row" style="grid-template-columns:1fr 1fr 1fr;margin-top:18px">
            ${renderPanel('GTC Trong Ngày (' + latestDate + ')', 'fa-calendar-day', rankDay, C_GREEN)}
            ${renderPanel('GTC 7 Ngày Qua', 'fa-calendar-week', rankWeek, C_BLUE)}
            ${renderPanel('GTC 30 Ngày Qua', 'fa-calendar', rankMonth, C_PURPLE)}
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
            <td>${r['PIC'] || r['order_code']||''}</td>
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
function renderB2bSection(khoFilter = '', prioFilter = '') {
    let data = [...state.b2bData];
    if (khoFilter) data = data.filter(r =>
        (shortKho(r['Kho hiện tại'])||'').toLowerCase().includes(khoFilter.toLowerCase()) ||
        (r['Order code']||'').toLowerCase().includes(khoFilter.toLowerCase())
    );
    if (prioFilter) data = data.filter(r => (r['Mức độ ưu tiên']||'') === prioFilter);

    const prio = ['1: trong hôm nay','2: trong ngày mai','3: trong ngày mốt'];
    data.sort((a,b) => prio.indexOf(a['Mức độ ưu tiên']) - prio.indexOf(b['Mức độ ưu tiên']));

    document.getElementById('b2b-count-label').textContent = data.length + ' đơn';
    document.getElementById('tbody-b2b').innerHTML = data.map(r => `
        <tr>
            <td>${priorityBadge(r['Mức độ ưu tiên'])}</td>
            <td>${shortKho(r['Kho hiện tại'])}</td>
            <td>${r['PIC']||''}</td>
            <td class="order-code">${r['Order code']||''}</td>
            <td><span class="badge ${r['Cần làm gì']==='giao'?'storing':'waiting'}">${r['Cần làm gì']||''}</span></td>
            <td>${r['Khách']||''}</td>
            <td>${r['Ngày nhập kho']||''}</td>
            <td>${agingChip(r['Đã lưu kho (ngày)'])}</td>
            <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r['Địa chỉ giao']||''}</td>
        </tr>
    `).join('');
}

// ---- RETURNS SECTION ----
function renderReturnsSection() {
    const sorted = [...state.returnsData].sort((a,b) => {
        const da = (a['Ngày']||'').split(' - ')[0];
        const db = (b['Ngày']||'').split(' - ')[0];
        return db.localeCompare(da);
    });
    document.getElementById('tbody-returns').innerHTML = sorted.map(r => `
        <tr>
            <td>${shortKho(r['Kho'])}</td>
            <td>${r['Ngày']||''}</td>
            <td style="text-align:center">${r['Số đơn trả']||0}</td>
            <td class="${pctClass(r['% FD'])}">${r['% FD']||''}</td>
            <td>${r['Tổng đơn trả']||''}</td>
            <td>${r['SHOPEE Bulky %']||''}</td>
            <td>${r['SME %']||''}</td>
            <td>${r['B2B %']||''}</td>
            <td>${r['Ecommerce %']||''}</td>
        </tr>
    `).join('');
}

// ---- RETURNS FD CHART ----
function renderReturnsFDChart() {
    const dateMap = {};
    state.returnsData.forEach(r => {
        const d = (r['Ngày']||'').split(' - ')[0];
        if (!d) return;
        if (!dateMap[d]) dateMap[d] = { sum: 0, cnt: 0 };
        const v = parsePct(r['% FD']);
        dateMap[d].sum += v; dateMap[d].cnt++;
    });
    const labels = Object.keys(dateMap).sort();
    const values = labels.map(d => dateMap[d].cnt ? +(dateMap[d].sum / dateMap[d].cnt).toFixed(2) : 0);

    destroyChart('fdTrend');
    const ctx = document.getElementById('chart-fd-trend').getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 180);
    grad.addColorStop(0, 'rgba(245,54,92,0.15)');
    grad.addColorStop(1, 'rgba(245,54,92,0)');
    charts.fdTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '% FD',
                data: values,
                borderColor: C_RED,
                backgroundColor: grad,
                borderWidth: 2.5,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#fff',
                pointBorderColor: C_RED,
                pointBorderWidth: 2,
                pointRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => ' ' + c.raw + '%' } }
            },
            scales: {
                y: { min: 0, grid: { color: '#F0F3F8' }, ticks: { callback: v => v+'%', font:{size:11} } },
                x: { grid: { display: false }, ticks: { font: {size:11} } }
            }
        }
    });
}

// ---- PERSONNEL OVERVIEW (in Tổng Quan) ----
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

    // Count by thâm niên group
    const tenureMap = {};
    data.forEach(r => {
        // Extract short label from e.g. "G01: Dưới 1 tháng" -> "<1 tháng"
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
        data = data.filter(r => (r['Họ tên']||'').toLowerCase().includes(f) || shortKho(r['Kho']).toLowerCase().includes(f));
    }
    if (posFilter) data = data.filter(r => (r['Tên vị trí']||'').includes(posFilter));
    document.getElementById('personnel-count-label').textContent = data.length + ' người';
    document.getElementById('tbody-personnel').innerHTML = data.map((r, i) => `
        <tr>
            <td>${i + 1}</td>
            <td style="font-family:monospace;font-size:12px;color:var(--text3)">${r['ID']||''}</td>
            <td style="font-weight:600">${r['Họ tên']||''}</td>
            <td>${r['Tên vị trí']||''}</td>
            <td><span class="badge ${r['Loại HĐ']==='Nhân viên chính thức'?'storing':'p3'}">${r['Loại HĐ']||''}</span></td>
            <td>${r['Thâm niên']||''}</td>
            <td>${shortKho(r['Kho']) || ''}</td>
            <td>${r['Phòng ban']||''}</td>
        </tr>
    `).join('');
}

// ---- NĂNG SUẤT NV SECTION ----
let currentNsPeriod = 'day';

function renderNangSuatSection() {
    if (!state.nangSuatData || !state.nangSuatData.length) return;

    const allDates = [...new Set(state.nangSuatData.map(r => r['Ngày']||'').filter(Boolean))].sort((a,b) => {
        const parseDate = s => {
            const m = s.match(/(\d+) thg (\d+), (\d+)/);
            if(m) return new Date(parseInt(m[3]), parseInt(m[2])-1, parseInt(m[1])).getTime();
            return 0;
        };
        return parseDate(b) - parseDate(a);
    });

    if (!allDates.length) return;

    const latestDate = allDates[0];
    let filteredData = [];

    const provSelect = document.getElementById('filter-ns-province');
    if (provSelect && provSelect.options.length <= 1) {
        const provs = [...new Set(state.nangSuatData.map(r => r['to_province_name']).filter(Boolean))].sort();
        provs.forEach(p => {
            const o = document.createElement('option');
            o.value = p; o.textContent = p;
            provSelect.appendChild(o);
        });
    }
    const selProv = provSelect ? provSelect.value : '';

    if (currentNsPeriod === 'day') {
        filteredData = state.nangSuatData.filter(r => r['Ngày'] === latestDate);
    } else {
        const daysToInclude = currentNsPeriod === 'week' ? 7 : 30;
        const validDates = allDates.slice(0, daysToInclude);
        filteredData = state.nangSuatData.filter(r => validDates.includes(r['Ngày']));
    }

    if (selProv) {
        filteredData = filteredData.filter(r => r['to_province_name'] === selProv);
    }

    const driverMap = {};
    filteredData.forEach(r => {
        const idName = r['driver'] || '';
        if (!idName) return;
        if (!driverMap[idName]) {
            driverMap[idName] = { name: idName, province: r['to_province_name'] || '', totalVol: 0, totalSuccess: 0, sumRate: 0, daysCount: 0 };
        }
        driverMap[idName].totalVol += parseInt(r['volume']||0);
        driverMap[idName].totalSuccess += parseInt(r['success_volume']||0);
        driverMap[idName].sumRate += parseFloat((r['avg_delivery_volume_per_hour']||'0').toString().replace(',','.'));
        driverMap[idName].daysCount += 1;
    });

    let drivers = Object.values(driverMap).map(d => {
        const avgRate = d.daysCount > 0 ? (d.sumRate / d.daysCount) : 0;
        const pctGtc = d.totalVol > 0 ? (d.totalSuccess / d.totalVol * 100) : 0;
        return { ...d, avgRate, pctGtc };
    });

    const minVol = 30;
    const validDrivers = drivers.filter(d => d.totalVol > minVol);
    const listToSort = validDrivers.length >= 20 ? validDrivers : drivers;

    listToSort.sort((a,b) => {
        if (Math.abs(b.pctGtc - a.pctGtc) > 0.01) return b.pctGtc - a.pctGtc;
        return b.avgRate - a.avgRate;
    });
    const top10 = listToSort.slice(0, 10);
    
    const bottom10 = [...listToSort].sort((a,b) => {
        if (Math.abs(a.pctGtc - b.pctGtc) > 0.01) return a.pctGtc - b.pctGtc;
        return a.avgRate - b.avgRate;
    }).slice(0, 10);

    const parseDateStr = s => {
        const m = s.match(/(\d+) thg (\d+), (\d+)/);
        if(m) return new Date(parseInt(m[3]), parseInt(m[2])-1, parseInt(m[1])).getTime();
        return 0;
    };

    let detailData = state.nangSuatData;
    if (selProv) {
        detailData = detailData.filter(r => r['to_province_name'] === selProv);
    }

    const allDrivers = [...detailData].sort((a,b) => {
        const dateA = parseDateStr(a['Ngày']||'');
        const dateB = parseDateStr(b['Ngày']||'');
        if (dateA !== dateB) return dateB - dateA;
        
        const gtcA = parsePct(a['Tỉ lệ GTC']);
        const gtcB = parsePct(b['Tỉ lệ GTC']);
        if (Math.abs(gtcB - gtcA) > 0.01) return gtcB - gtcA;
        
        const volA = parseInt(a['volume']||0);
        const volB = parseInt(b['volume']||0);
        return volB - volA;
    });

    const formatRow = (r, idx, isTop) => `
        <tr>
            <td><span class="badge ${isTop ? (idx<3?'storing':'p3') : (idx<3?'p1':'waiting')}">#${idx+1}</span></td>
            <td style="font-weight:600">${r.name}</td>
            <td>${r.province}</td>
            <td style="text-align:right;font-weight:700;color:${isTop?'var(--green)':'var(--red)'}">${r.avgRate.toFixed(1)}</td>
            <td style="text-align:right">${r.totalVol.toLocaleString()}</td>
            <td style="text-align:right" class="${pctClass(r.pctGtc.toFixed(2)+'%')}">${r.pctGtc.toFixed(2)}%</td>
        </tr>
    `;

    const formatAllRow = (r, idx) => `
        <tr>
            <td><span class="badge storing">${r['Ngày']||''}</span></td>
            <td style="font-weight:600">${r['driver']||''}</td>
            <td>${r['to_province_name']||''}</td>
            <td style="text-align:right;font-weight:700">${parseFloat((r['avg_delivery_volume_per_hour']||'0').toString().replace(',','.')).toFixed(1)}</td>
            <td style="text-align:right">${parseInt(r['volume']||0).toLocaleString()}</td>
            <td style="text-align:right" class="${pctClass(r['Tỉ lệ GTC'])}">${r['Tỉ lệ GTC']||'0%'}</td>
            <td>${r['first_3_delivery']||'--'}</td>
            <td>${r['last_3_delivery']||'--'}</td>
        </tr>
    `;

    document.getElementById('tbody-ns-top').innerHTML = top10.map((r,i) => formatRow(r, i, true)).join('');
    document.getElementById('tbody-ns-bottom').innerHTML = bottom10.map((r,i) => formatRow(r, i, false)).join('');
    
    const tbodyAll = document.getElementById('tbody-ns-all');
    if (tbodyAll) tbodyAll.innerHTML = allDrivers.map((r,i) => formatAllRow(r, i)).join('');
}

// ---- WARNINGS SECTION ----
function renderWarningsSection() {
    const data = state.warningsData;
    if (!data) return;

    // KPI Cards
    const critical = data.filter(r => r['Tình hình hiện tại'] === 'Nghiêm trọng');
    const warning  = data.filter(r => r['Tình hình hiện tại'] === 'Cảnh báo');

    const critEl = document.getElementById('warn-critical-count');
    if (critEl) critEl.textContent = critical.length;

    const warnEl = document.getElementById('warn-warning-count');
    if (warnEl) warnEl.textContent = warning.length;

    // Cột N = "Số ngày trở về ngày thường"
    const ngayKey = 'Số ngày trở về ngày thường';
    const totalNgay = data.reduce((sum, r) => sum + (parseFloat(r[ngayKey]) || 0), 0);
    const avgDays = data.length ? totalNgay / data.length : 0;
    const avgDaysEl = document.getElementById('warn-avg-days');
    if (avgDaysEl) avgDaysEl.textContent = avgDays.toFixed(1);

    // Table — hiện tất cả kho, không giới hạn
    const tbody = document.getElementById('tbody-warnings');
    if (tbody) {
        tbody.innerHTML = data.map(r => {
            const status = r['Tình hình hiện tại'] || 'Bình thường';
            let badgeClass = 'storing';
            if (status === 'Cảnh báo') badgeClass = 'waiting';
            if (status === 'Nghiêm trọng') badgeClass = 'p1';

            const nextStatus = r['Tình hình sắp tới'] || 'Bình thường';
            let nextBadgeClass = 'storing';
            if (nextStatus === 'Cảnh báo') nextBadgeClass = 'waiting';
            if (nextStatus === 'Nghiêm trọng') nextBadgeClass = 'p1';

            // Backlog last mile — thử nhiều tên cột có thể có
            const backlogLM = r['backlog last mile'] || r['Backlog Last Mile'] || r['backlog_last_mile'] || 0;
            const backlogKTC = r['backlog ktc'] || r['Backlog KTC'] || r['backlog_ktc'] || 0;

            // Số ngày về bình thường (cột N)
            const soNgay = parseFloat(r[ngayKey]) || 0;

            return `
                <tr>
                    <td style="font-weight:600">${shortKho(r['kho gxt'] || r['Kho'] || '--')}</td>
                    <td><span class="badge ${badgeClass}">${status}</span></td>
                    <td style="text-align:right;font-weight:700;color:var(--red)">${backlogLM}</td>
                    <td style="text-align:right">${backlogKTC}</td>
                    <td>${r['đơn tạo N-1'] || 0} / ${r['đơn gtc N-1'] || 0}</td>
                    <td style="text-align:right">
                        <span class="aging-chip ${soNgay > 2 ? 'aging-critical' : soNgay > 0 ? 'aging-high' : 'aging-normal'}">
                            ${soNgay} ngày
                        </span>
                    </td>
                    <td><span class="badge ${nextBadgeClass}">${nextStatus}</span></td>
                    <td style="font-weight:800;color:var(--orange)">${r['Rank'] || '--'}</td>
                </tr>
            `;
        }).join('');
    }
}

// ---- HELPER: destroy chart safely ----
function destroyChart(key) {
    if (charts[key]) { charts[key].destroy(); charts[key] = null; }
}

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

document.getElementById('refresh-btn').addEventListener('click', async () => {
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('loading');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang tải...';
    await fetchAll();
    btn.classList.remove('loading');
    btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Làm mới';
});

document.getElementById('sidebar-toggle').addEventListener('click', () => {
    const sb = document.getElementById('sidebar');
    sb.style.width = sb.style.width === '56px' ? '240px' : '56px';
});

// Filters
document.getElementById('filter-kho-gtc').addEventListener('input', e => renderGtcSection(e.target.value));
document.getElementById('filter-kho-backlog').addEventListener('input', e =>
    renderBacklogSection(e.target.value, document.getElementById('filter-luong').value));
document.getElementById('filter-luong').addEventListener('change', e =>
    renderBacklogSection(document.getElementById('filter-kho-backlog').value, e.target.value));
document.getElementById('filter-b2b').addEventListener('input', e =>
    renderB2bSection(e.target.value, document.getElementById('filter-priority').value));
document.getElementById('filter-priority').addEventListener('change', e =>
    renderB2bSection(document.getElementById('filter-b2b').value, e.target.value));
document.getElementById('filter-personnel').addEventListener('input', e =>
    renderPersonnelSection(e.target.value, document.getElementById('filter-position').value));
document.getElementById('filter-position').addEventListener('change', e =>
    renderPersonnelSection(document.getElementById('filter-personnel').value, e.target.value));

function switchNsTab(period, btnId) {
    document.querySelectorAll('#section-nangsuat .filter-tabs button').forEach(b => {
        b.classList.remove('active');
        b.style.cssText = '';
    });
    const btn = document.getElementById(btnId);
    if(btn) {
        btn.classList.add('active');
        btn.style.cssText = 'background:var(--blue-bg);color:var(--blue);border-color:var(--blue-border);font-weight:700';
    }
    currentNsPeriod = period;
    renderNangSuatSection();
}

document.getElementById('btn-ns-day').addEventListener('click', () => switchNsTab('day', 'btn-ns-day'));
document.getElementById('btn-ns-week').addEventListener('click', () => switchNsTab('week', 'btn-ns-week'));
document.getElementById('btn-ns-month').addEventListener('click', () => switchNsTab('month', 'btn-ns-month'));

document.getElementById('filter-ns-province').addEventListener('change', () => {
    renderNangSuatSection();
});

// ---- INIT ----
fetchAll();
setInterval(fetchAll, 5 * 60 * 1000);
