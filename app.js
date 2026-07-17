const API = window.location.origin + '/api';

// ---- SECURITY UTILS ----
/**
 * Escape HTML để ngăn XSS — luôn dùng khi render dữ liệu từ API vào innerHTML
 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '--';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Hiển thị thông báo Toast nhanh trên màn hình
 */
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.position = 'fixed';
        container.style.bottom = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '10px';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast-message ${type}`;
    toast.style.minWidth = '280px';
    toast.style.padding = '12px 20px';
    toast.style.borderRadius = '8px';
    toast.style.color = '#ffffff';
    toast.style.fontFamily = "'Outfit', sans-serif";
    toast.style.fontSize = '0.88rem';
    toast.style.fontWeight = '500';
    toast.style.boxShadow = '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.1)';
    toast.style.display = 'flex';
    toast.style.alignItems = 'center';
    toast.style.gap = '10px';
    toast.style.transition = 'all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55)';
    toast.style.transform = 'translateX(120%)';
    toast.style.opacity = '0';
    
    let bgColor = '#1e293b'; 
    let borderCol = '#475569';
    let icon = '<i class="fa-solid fa-circle-info" style="color:#38bdf8"></i>';
    
    if (type === 'success') {
        bgColor = '#064e3b';
        borderCol = '#059669';
        icon = '<i class="fa-solid fa-circle-check" style="color:#34d399"></i>';
    } else if (type === 'error') {
        bgColor = '#7f1d1d';
        borderCol = '#dc2626';
        icon = '<i class="fa-solid fa-circle-exclamation" style="color:#f87171"></i>';
    } else if (type === 'warning') {
        bgColor = '#78350f';
        borderCol = '#d97706';
        icon = '<i class="fa-solid fa-triangle-exclamation" style="color:#fbbf24"></i>';
    }
    
    toast.style.backgroundColor = bgColor;
    toast.style.border = `1px solid ${borderCol}`;
    toast.innerHTML = `${icon} <span>${message}</span>`;
    
    container.appendChild(toast);
    
    // Force reflow and animate in
    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    }, 10);
    
    // Hide and remove after 4 seconds
    setTimeout(() => {
        toast.style.transform = 'translateX(120%)';
        toast.style.opacity = '0';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4000);
}


// ---- API TOKEN MANAGEMENT ----
const SESSION_KEY = 'ghn_session_token';

function getApiToken() {
    return sessionStorage.getItem(SESSION_KEY) || '';
}

function setApiToken(token) {
    sessionStorage.setItem(SESSION_KEY, token);
}

function clearApiToken() {
    sessionStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem('ghn_logged_in');
}

/**
 * Trả về headers chuẩn có Bearer token cho mọi fetch API
 */
function getAuthHeaders() {
    const token = getApiToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/**
 * Wrapper fetch có tự động gắi auth header
 */
async function apiFetch(url, opts = {}) {
    const headers = { ...getAuthHeaders(), ...(opts.headers || {}) };
    const resp = await fetch(url, { ...opts, headers });
    if (resp.status === 401 || resp.status === 403) {
        // Token hết hiệu lực — đăng xuất
        clearApiToken();
        localStorage.removeItem('ghn_logged_in');
        window.location.reload();
        return null;
    }
    return resp;
}

// GHN Brand Colors - Redefined for dark cyan neon theme
const C_ORANGE = '#FF6600';
const C_BLUE = '#00F0FF'; // Cyan
const C_GREEN = '#10B981'; // Emerald
const C_RED = '#EF4444'; // Red
const C_PURPLE = '#BC53FA'; // Purple
const C_YELLOW = '#F59E0B'; // Yellow

// Detect initial theme for Chart.js defaults
const initialTheme = localStorage.getItem('ghn_theme') || 'dark';
const isInitialLight = initialTheme === 'light';
const defaultTextColor = isInitialLight ? '#4B5563' : '#9CA3AF';
const defaultGridColor = isInitialLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.08)';

Chart.defaults.font.family = "'Outfit', sans-serif";
Chart.defaults.color = defaultTextColor;
Chart.defaults.borderColor = defaultGridColor;

if (Chart.defaults.plugins && Chart.defaults.plugins.legend && Chart.defaults.plugins.legend.labels) {
    Chart.defaults.plugins.legend.labels.color = defaultTextColor;
}

if (!Chart.defaults.scale) Chart.defaults.scale = {};
if (!Chart.defaults.scale.grid) Chart.defaults.scale.grid = {};
Chart.defaults.scale.grid.color = defaultGridColor;
if (!Chart.defaults.scale.ticks) Chart.defaults.scale.ticks = {};
Chart.defaults.scale.ticks.color = defaultTextColor;

// Ensure DataLabels plugin is registered for charts to show percentage
Chart.register(ChartDataLabels);

// ---- STATE ----
let state = {
    gtcData: [], ontimeData: [], returnsData: [],
    backlogData: [], b2bData: [], personnelData: [], nangSuatData: [],
    warningsData: [], returnsByClientData: [], xeGxtData: [],
    xeSuCoData: [], khoGxtData: [],
    overview: {},
    // Xe Vận Hành Daily
    xeDailyMeta: { kho_list: [], ncc_map: {}, ncc_all: [] },
    xeDailyRecords: [],
};
let charts = {};

// ---- UTILS ----
function pctClass(v) {
    const n = parseFloat((v || '0').replace('%', '').replace(',', '.'));
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
    const safe = escapeHtml(p);
    if (p.startsWith('1:')) return `<span class="badge p1">${safe}</span>`;
    if (p.startsWith('2:')) return `<span class="badge p2">${safe}</span>`;
    return `<span class="badge p3">${safe}</span>`;
}

function shortKho(k) {
    if (!k) return '--';
    return k.replace(/Kho Giao Hàng Nặng[\s\-]+/gi, '').trim();
}

function parsePct(str) {
    return parseFloat((str || '0').replace('%', '').replace(',', '.')) || 0;
}

function parseVN(s) {
    if (!s) return 0;
    if (typeof s !== 'string') s = s.toString();

    // Format: "2026-05-05 - Thứ 3" hoặc "2026-05-05"
    let m0 = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m0) return new Date(parseInt(m0[1]), parseInt(m0[2]) - 1, parseInt(m0[3])).getTime();

    // Format: "5 thg 5, 2026"
    let m = s.match(/(\d+) thg (\d+), (\d+)/);
    if (m) return new Date(parseInt(m[3]), parseInt(m[2]) - 1, parseInt(m[1])).getTime();

    // Format: "DD/MM/YYYY" hoặc "D/M/YYYY"
    let m2 = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (m2) return new Date(parseInt(m2[3]), parseInt(m2[2]) - 1, parseInt(m2[1])).getTime();

    const d = new Date(s);
    return isNaN(d.getTime()) ? 0 : d.getTime();
}

// ---- FETCH ALL ----
let nextSyncTime = Date.now() + 5 * 60 * 1000;
let syncTimerInterval = null;

/**
 * fetch có auth header + tự động logout nếu token hết hạn (401/403)
 */
async function authFetch(url, fallback = null) {
    try {
        const r = await fetch(url, { headers: getAuthHeaders() });
        if (r.status === 401 || r.status === 403) {
            // Token hết hạn hoặc không hợp lệ → buộc đăng nhập lại
            clearApiToken();
            localStorage.removeItem('ghn_logged_in');
            window.location.reload();
            return fallback;
        }
        return await r.json();
    } catch (e) {
        return fallback;
    }
}

/** authPost - POST JSON to an authenticated endpoint */
async function authPost(url, body, fallback = null) {
    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (r.status === 401 || r.status === 403) {
            clearApiToken();
            localStorage.removeItem('ghn_logged_in');
            window.location.reload();
            return fallback;
        }
        return await r.json();
    } catch (e) {
        console.error('[authPost] Error:', e);
        return fallback;
    }
}

async function fetchAll(force = false) {
    const btn = document.getElementById('refresh-btn');
    if (force) {
        btn.classList.add('loading');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang tải...';
    }

    try {
        const query = force ? '?force=true' : '';
        const [ov, gtc, ontime, ret, bl, b2b, pers, ns, warn, retC, xegxt, xesuco, khogxt, dontao, gtcB2b, donB2b] = await Promise.all([
            authFetch(`${API}/dashboard/overview${query}`, {}),
            authFetch(`${API}/kpi/gtc${query}`, { data: [] }),
            authFetch(`${API}/kpi/ontime${query}`, { data: [] }),
            authFetch(`${API}/returns${query}`, { data: [] }),
            authFetch(`${API}/backlog/critical${query}`, { data: [] }),
            authFetch(`${API}/backlog/b2b${query}`, { data: [] }),
            authFetch(`${API}/personnel${query}`, { data: [] }),
            authFetch(`${API}/nang-suat${query}`, { data: [] }),
            authFetch(`${API}/warnings${query}`, { data: [] }),
            authFetch(`${API}/returns/by-client${query}`, { data: [] }),
            authFetch(`${API}/xe-gxt${query}`, { data: [] }),
            authFetch(`${API}/xe-su-co${query}`, { data: [] }),
            authFetch(`${API}/kho-gxt${query}`, { data: [] }),
            authFetch(`${API}/don-tao${query}`, { data: [] }),
            authFetch(`${API}/kpi/gtc-b2b${query}`, { data: [] }),
            authFetch(`${API}/kpi/don-b2b${query}`, { data: [] }),
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
            donTaoData: dontao.data || [],
            gtcB2bData: gtcB2b.data || [],
            donB2bData: donB2b.data || []
        };
        filtersPopulated = false; // Reset filters on fresh data

        // Reset countdown
        nextSyncTime = Date.now() + 5 * 60 * 1000;
        renderAll();

        if (force) {
            btn.classList.remove('loading');
            btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Làm mới';
        }
    } catch (e) {
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
            // Auto refresh current active tab only to optimize load
            const activeSectionEl = document.querySelector('.section.active');
            const activeName = activeSectionEl ? activeSectionEl.id.replace('section-', '') : 'overview';
            if (activeName === 'xe-daily') {
                if (typeof window.loadXeDailyRecords === 'function') window.loadXeDailyRecords();
            } else if (activeName === 'login-logs') {
                if (typeof window.loadLoginLogs === 'function') window.loadLoginLogs();
            } else {
                ensureSectionData(activeName, true);
            }
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
        { name: 'OverviewB2bChart', fn: renderOverviewB2bChart },
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
        { name: 'NangSuatVungSection', fn: renderNangSuatVungSection },
        { name: 'WarningsSection', fn: renderWarningsSection },
        { name: 'XeGxtSection', fn: renderXeGxtSection },
        { name: 'XeSuCoSection', fn: renderXeSuCoSection },
        { name: 'KhoGxtSection', fn: renderKhoGxtSection },
        { name: 'DonTaoSection', fn: renderDonTaoSection },
        { name: 'ForecastSection', fn: renderForecastSection },
        { name: 'GtcB2bPrioSection', fn: renderGtcB2bPrioSection },
        { name: 'B2BMapSection', fn: renderB2BMapSection },
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
        now.toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' });
}

// ---- OVERVIEW CARDS ----
function renderOverviewCards() {
    const ov = state.overview;
    document.getElementById('val-gtc').textContent = (ov.avg_gtc || 0) + '%';
    const ontimeEl = document.getElementById('val-ontime');
    if (ontimeEl) {
        if (ov.avg_ontime === "Không sử dụng dữ liệu Ontime") {
            ontimeEl.textContent = "Không sử dụng dữ liệu Ontime";
        } else {
            ontimeEl.textContent = (ov.avg_ontime || 0) + '%';
        }
    }
    const backlogEl = document.getElementById('val-backlog');
    if (backlogEl) backlogEl.textContent = ov.total_backlog_7n || 0;
    
    const valB2b = document.getElementById('val-b2b');
    if (valB2b) valB2b.textContent = ov.total_b2b_priority || 0;
    
    // Calculate % GTC B2B Priority for overview card (latest day)
    const b2bData = state.gtcB2bData || [];
    const availableB2bDays = [...new Set(b2bData.map(r => parseDateToYmd(r['time_view'])).filter(Boolean))].sort();
    let b2bGtcPctText = 'Chưa có dữ liệu';
    let b2bGtcSubText = 'Ngày gần nhất';
    
    if (availableB2bDays.length > 0) {
        const latestDay = availableB2bDays[availableB2bDays.length - 1];
        const latestRows = b2bData.filter(r => parseDateToYmd(r['time_view']) === latestDay);
        
        let totalPriority = 0;
        let totalErrors = 0;
        latestRows.forEach(row => {
            totalPriority += parseInt(row['Số đơn ưu tiên']) || 0;
            totalErrors += parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
        });
        
        if (totalPriority > 0) {
            b2bGtcPctText = ((totalPriority - totalErrors) / totalPriority * 100).toFixed(2) + '%';
            b2bGtcSubText = 'Ngày ' + latestDay;
        }
    }
    
    const cardB2bVal = document.getElementById('val-gtc-b2b-prio-overview');
    if (cardB2bVal) cardB2bVal.textContent = b2bGtcPctText;
    const cardB2bSub = document.getElementById('sub-gtc-b2b-prio-overview');
    if (cardB2bSub) cardB2bSub.textContent = b2bGtcSubText;

    const valFd = document.getElementById('val-fd');
    if (valFd) valFd.textContent = (ov.avg_fd_return || 0) + '%';
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
            pCount = state.personnelData.filter(r => (r['Tên vị trí'] || '').trim().toLowerCase() === 'delivery staff').length;
        }
        xeTotalEl.textContent = `${ov.total_xe_gxt || 0}/${pCount}`;
    }

    const khoGxtTotalEl = document.getElementById('val-khogxt-total');
    if (khoGxtTotalEl) khoGxtTotalEl.textContent = (ov.total_kho_gxt || 0).toLocaleString();

    // Đơn Tạo N-1
    const donTaoEl = document.getElementById('val-dontao');
    if (donTaoEl) {
        const d = (ov.total_don_tao || 0).toLocaleString('vi-VN');
        const kg = (ov.total_kg_tao || 0).toLocaleString('vi-VN', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
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
    document.getElementById('sub-gtc').textContent = 'Đã đồng bộ: ' + syncTime;

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
    const warningCount = processedData.filter(r => r.sheetStatus === 'Bất ổn').length;
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

window.toggleDropdown = function (id) {
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
    const backlogBadge = document.getElementById('nav-backlog-count');
    if (backlogBadge) {
        backlogBadge.textContent = state.backlogData.length;
    }
    
    const critB2b = state.b2bData.filter(r => (r['Mức độ ưu tiên'] || '').startsWith('1:'));
    const b2bBadge = document.getElementById('nav-b2b-count');
    if (b2bBadge) {
        b2bBadge.textContent = critB2b.length;
    }

    const critWarn = state.warningsData.filter(r => r['Tình hình hiện tại'] === 'Nghiêm trọng');
    const warnBadge = document.getElementById('nav-warnings-count');
    if (warnBadge) {
        warnBadge.textContent = critWarn.length;
        warnBadge.style.display = critWarn.length > 0 ? 'inline-block' : 'none';
    }
}

let currentOverviewGtcPeriod = 'day';

window.switchOverviewGtcPeriod = function (p) {
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
        dateMap[key].gtc += parseInt(r['Số đơn GTC'] || 0);
    });

    const allKeys = Object.keys(dateMap).sort();
    const labels = allKeys.slice(-14);
    const values = labels.map(k => dateMap[k].total ? +(dateMap[k].gtc / dateMap[k].total * 100).toFixed(1) : 0);

    destroyChart('gtcTrend');
    const ctx = document.getElementById('chart-gtc-trend').getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 350);
    grad.addColorStop(0, 'rgba(255, 102, 0, 0.12)');
    grad.addColorStop(1, 'rgba(255, 102, 0, 0)');

    charts.gtcTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(l => l.replace(/^\d{4}-/, '')), // Shorten labels
            datasets: [{
                label: '% GTC',
                data: values,
                borderColor: C_ORANGE,
                backgroundColor: grad,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#fff',
                pointBorderColor: C_ORANGE,
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                datalabels: {
                    display: true,
                    align: 'top',
                    offset: 5,
                    color: () => document.documentElement.classList.contains('light-mode') ? '#1E2937' : '#FFFFFF',
                    font: { size: 9.5, weight: 'bold' },
                    formatter: v => v + '%'
                }
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                datalabels: { display: true },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#F3F4F6',
                    bodyColor: '#F3F4F6',
                    borderColor: 'rgba(0, 240, 255, 0.15)',
                    borderWidth: 1,
                    borderRadius: 8,
                    padding: 10,
                    displayColors: false,
                    callbacks: { label: c => ' ' + c.raw + '%' }
                }
            },
            scales: {
                y: { min: 60, max: 105, ticks: { callback: v => v + '%' } },
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
    const canvas = document.getElementById('chart-returns-pie');
    if (!canvas) return;
    
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
        reasonMap['Đổi ý không mua'] += Math.round(n * 0.25);
        reasonMap['Hẹn lại ngày giao'] += Math.round(n * 0.20);
        reasonMap['Sai địa chỉ'] += Math.round(n * 0.15);
        reasonMap['Khác'] += Math.round(n * 0.10);
    });

    destroyChart('returnsPie');
    const ctx = canvas.getContext('2d');
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

let currentOverviewB2bPeriod = 'day';

window.switchOverviewB2bPeriod = function (p) {
    currentOverviewB2bPeriod = p;
    document.querySelectorAll('#btn-ov-b2b-day, #btn-ov-b2b-month').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-ov-b2b-' + p)?.classList.add('active');
    renderOverviewB2bChart();
};

function renderOverviewB2bChart() {
    const canvas = document.getElementById('chart-overview-b2b-gtc-trend');
    if (!canvas) return;
    
    const b2bData = state.gtcB2bData || [];
    if (!b2bData.length) {
        destroyChart('overviewB2bGtcTrend');
        return;
    }
    
    const dateMap = {};
    b2bData.forEach(row => {
        const ymd = parseDateToYmd(row['time_view']);
        if (!ymd) return;
        const key = currentOverviewB2bPeriod === 'day' ? ymd : getMonthFromYmd(ymd);
        if (!dateMap[key]) {
            dateMap[key] = { total: 0, errors: 0 };
        }
        dateMap[key].total += parseInt(row['Số đơn ưu tiên']) || 0;
        dateMap[key].errors += parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
    });
    
    const allKeys = Object.keys(dateMap).sort();
    let labels = [];
    if (currentOverviewB2bPeriod === 'day') {
        labels = allKeys.slice(-10);
    } else {
        labels = allKeys.slice(-5);
    }
    
    const values = labels.map(k => {
        const item = dateMap[k];
        return item.total > 0 ? parseFloat(((item.total - item.errors) / item.total * 100).toFixed(1)) : 0;
    });
    
    destroyChart('overviewB2bGtcTrend');
    const ctx = canvas.getContext('2d');
    const grad = ctx.createLinearGradient(0, 0, 0, 350);
    grad.addColorStop(0, 'rgba(16, 185, 129, 0.12)');
    grad.addColorStop(1, 'rgba(16, 185, 129, 0)');

    charts.overviewB2bGtcTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels.map(l => currentOverviewB2bPeriod === 'day' ? l.replace(/^\d{4}-/, '') : l),
            datasets: [{
                label: '% GTC B2B',
                data: values,
                borderColor: C_GREEN,
                backgroundColor: grad,
                borderWidth: 4,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#fff',
                pointBorderColor: C_GREEN,
                pointBorderWidth: 2.5,
                pointRadius: 5,
                pointHoverRadius: 7,
                datalabels: {
                    display: true,
                    align: 'top',
                    offset: 5,
                    color: () => document.documentElement.classList.contains('light-mode') ? '#1E2937' : '#FFFFFF',
                    font: { size: 9.5, weight: 'bold' },
                    formatter: v => v + '%'
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                datalabels: { display: true },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#F3F4F6',
                    bodyColor: '#F3F4F6',
                    borderColor: 'rgba(0, 240, 255, 0.15)',
                    borderWidth: 1,
                    borderRadius: 8,
                    padding: 10,
                    displayColors: false,
                    callbacks: { label: c => ' ' + c.raw + '%' }
                }
            },
            scales: {
                y: {
                    min: 60,
                    max: 105,
                    ticks: { callback: v => v + '%' }
                },
                x: {
                    grid: { display: false }
                }
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
            <td style="font-weight:600">${escapeHtml(r.kho)}</td>
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
            <td style="font-weight:600">${escapeHtml(r.kho)}</td>
            <td style="text-align:right;font-weight:700;color:var(--orange)">${r.count.toLocaleString()}</td>
        </tr>
    `).join('');
}

// ---- CRITICAL WARNINGS OVERVIEW ----
function renderCriticalWarningsOverview() {
    const tbody = document.getElementById('tbody-critical-overview');
    if (!tbody) return;

    // Lọc và chuẩn bị dữ liệu
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

        const soNgay = parseFloat(getV(['Số ngày trở về ngày thường', 'Total ngày'], 0));
        const sheetStatus = getV(['Tình hình hiện tại'], 'Bình thường');
        const nextStatus = r['Tình hình sắp tới'] || 'Bình thường';
        return { ...r, soNgayVal: soNgay, sheetStatus: sheetStatus, nextStatus: nextStatus };
    });

    const critical = processedData.filter(r => r.soNgayVal > 5);

    if (critical.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--green);font-weight:600"><i class="fa-solid fa-circle-check"></i> Toàn mạng lưới bình thường</td></tr>';
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
        if (nextStatus === 'Nghiêm trọng') nextBadgeClass = 'p1';

        return `
            <tr>
                <td style="font-weight:600">${escapeHtml(shortKho(r['kho gxt'] || r['Kho'] || '--'))}</td>
                <td style="text-align:right;font-weight:700;color:var(--red)">${lm.toLocaleString()}</td>
                <td style="text-align:right">${ktc.toLocaleString()}</td>
                <td style="text-align:right;font-weight:700;color:var(--blue)">${total.toLocaleString()}</td>
                <td><span class="badge ${nextBadgeClass}" style="font-size:10px">${escapeHtml(nextStatus)}</span></td>
                <td style="text-align:right;font-weight:600">${r.soNgayVal}n</td>
                <td><span class="badge ${isCritical ? 'p1' : 'waiting'}">${escapeHtml(status)}</span></td>
            </tr>
        `;
    }).join('');
}

let gtcTimeMode = 'day';
let selectedGtcVals = [];
let selectedGtcKhos = [];
let vungTimeMode = 'day';
let selectedVungRegions = [];

window.toggleMultiselect = function (mode) {
    const allMenus = document.querySelectorAll('.ghn-filter-menu');
    let targetId = 'menu-gtc-' + mode;
    if (mode.startsWith('dt-') || mode.startsWith('ns-') || mode === 'vung-region') {
        targetId = 'menu-' + mode;
    }
    allMenus.forEach(m => {
        if (m.id === targetId) m.classList.toggle('show');
        else m.classList.remove('show');
    });
};

document.addEventListener('click', (e) => {
    if (!e.target.closest('.ghn-filter-container')) {
        document.querySelectorAll('.ghn-filter-menu').forEach(m => m.classList.remove('show'));
    }
});

window.updateGtcTimeMode = function (mode) {
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
        if (mode === 'kho') label.innerText = 'Chọn Kho...';
        else if (mode === 'day') label.innerText = 'Chọn Ngày...';
        else if (mode === 'week') label.innerText = 'Chọn Tuần...';
        else label.innerText = 'Chọn Tháng...';
    } else {
        label.innerText = `${checks.length} mục đã chọn`;
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

    const days = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    renderMultiselectItems('day', days);

    const weeks = [...new Set(state.gtcData.map(r => {
        const ts = parseVN(r['Ngày']);
        return ts ? getWeekNumber(new Date(ts)) : null;
    }).filter(Boolean))].sort((a, b) => b - a);
    renderMultiselectItems('week', weeks);

    const months = [...new Set(state.gtcData.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        return d.getFullYear() + '-' + ((d.getMonth() + 1) < 10 ? '0' : '') + (d.getMonth() + 1);
    }).filter(Boolean))].sort().reverse();
    renderMultiselectItems('month', months);

    const khos = [...new Set(state.gtcData.map(r => shortKho(r['Kho'])).filter(Boolean))].sort();
    renderMultiselectItems('kho', khos);
}

function renderMultiselectItems(mode, values) {
    const menu = document.getElementById('menu-gtc-' + mode);
    if (!menu) return;
    menu.innerHTML = '';
    values.forEach(v => {
        const item = document.createElement('div');
        item.className = 'ghn-filter-item';
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.id = `chk-${mode}-${v}`;
        chk.value = v;  // DOM property, không cần escape
        chk.setAttribute('onchange', `updateGtcTimeMode('${mode}')`);
        const lbl = document.createElement('label');
        lbl.htmlFor = chk.id;
        lbl.textContent = mode === 'day' ? v : (mode === 'week' ? 'Tuần ' + v : (mode === 'month' ? 'Tháng ' + v : v));
        item.appendChild(chk);
        item.appendChild(lbl);
        menu.appendChild(item);
    });
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
                const m = dObj.getFullYear() + '-' + ((dObj.getMonth() + 1) < 10 ? '0' : '') + (dObj.getMonth() + 1);
                return selectedGtcVals.includes(m);
            }
            return true;
        });
    } else {
        const allDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
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
                (dObj.getFullYear() + '-' + ((dObj.getMonth() + 1) < 10 ? '0' : '') + (dObj.getMonth() + 1));

            const groupKey = k + '|' + periodKey;
            if (!aggMap[groupKey]) {
                aggMap[groupKey] = { kho: k, period: (gtcTimeMode === 'week' ? 'Tuần ' : 'Tháng ') + periodKey, kl: 0, gan: 0, gtc: 0, ts: ts };
            }

            const parseVal = (v) => parseFloat((v || '0').toString().replace(/\./g, '').replace(',', '.')) || 0;
            const parseCount = (v) => parseInt((v || '0').toString().replace(/\./g, '')) || 0;

            aggMap[groupKey].kl += parseVal(r['KL gán']);
            aggMap[groupKey].gan += parseCount(r['Số đơn gán']);
            aggMap[groupKey].gtc += parseCount(r['Số đơn GTC']);
        });
        displayData = Object.values(aggMap)
            .sort((a, b) => b.ts - a.ts)
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
        displayData = filteredData.sort((a, b) => parseVN(b['Ngày']) - parseVN(a['Ngày'])).map((r, idx) => ({
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
            <td>${escapeHtml(r.kho)}</td>
            <td>${escapeHtml(r.ngay)}</td>
            <td>${escapeHtml(r.kl)}</td>
            <td>${escapeHtml(r.gan)}</td>
            <td>${escapeHtml(r.gtc)}</td>
            <td class="${pctClass(r.pct)}">${escapeHtml(r.pct)}</td>
        </tr>
    `).join('');

    renderGtcByKhoChart();
    renderGtcTopBottom();
}

function renderGtcByRegionChart() { /* Removed per user request */ }

// ---- GTC BY KHO BAR CHART ----
// ---- GTC BY KHO PERIOD MODE ----
let gtcByKhoPeriod = 'day';

// Helper: lay tuan ISO (bat dau Tu 2)
function _isoWeek(dateStr) {
    const part = dateStr ? dateStr.split(' - ')[0] : '';
    if (!part) return null;
    const d = new Date(part + 'T00:00:00');
    if (isNaN(d)) return null;
    const day = d.getDay() || 7;    // Thu 2 = 1, CN = 7
    d.setDate(d.getDate() + 4 - day);
    const jan1 = new Date(d.getFullYear(), 0, 1);
    return { week: Math.ceil(((d - jan1) / 86400000 + 1) / 7), year: d.getFullYear() };
}

// Helper: lay thang (YYYY-MM)
function _yearMonth(dateStr) {
    const part = dateStr ? dateStr.split(' - ')[0] : '';
    return part ? part.slice(0, 7) : null;  // "2026-06"
}

// Helper: ngay dau & cuoi tuan ISO
function _weekRange(dateStr) {
    const part = dateStr ? dateStr.split(' - ')[0] : '';
    if (!part) return '';
    const d = new Date(part + 'T00:00:00');
    const day = d.getDay() || 7;
    const mon = new Date(d); mon.setDate(d.getDate() - day + 1);
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    const fmt = dt => `${dt.getDate()}/${dt.getMonth()+1}`;
    return `${fmt(mon)} - ${fmt(sun)}`;
}

window.switchGtcByKhoPeriod = function(period) {
    gtcByKhoPeriod = period;
    ['day','week','month'].forEach(p => {
        const btn = document.getElementById('btn-kho-' + p);
        if (btn) btn.classList.toggle('active', p === period);
    });
    renderGtcByKhoChart();
};

function renderGtcByKhoChart() {
    const allDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));

    // =====================================================================
    // AGGREGATION THEO PERIOD
    // =====================================================================
    let chartRows = [];
    let periodLabel = '';

    if (gtcByKhoPeriod === 'day') {
        // --- CHẾ ĐỘ NGÀY: dùng ngày gần nhất (hoặc selected) ---
        let referenceDate = allDates[0];
        if (gtcTimeMode === 'day' && selectedGtcVals.length > 0) {
            referenceDate = [...selectedGtcVals].sort((a, b) => parseVN(b) - parseVN(a))[0];
        }
        const dayRows = state.gtcData.filter(r => r['Ngày'] === referenceDate);
        chartRows = selectedGtcKhos.length > 0
            ? dayRows.filter(r => selectedGtcKhos.includes(shortKho(r['Kho'])))
            : dayRows;
        // Label: "Dữ liệu ngày: 16/06/2026"
        const datePart = referenceDate ? referenceDate.split(' - ')[0] : '';
        if (datePart) {
            const [y,m,d] = datePart.split('-');
            periodLabel = `Dữ liệu ngày: ${d}/${m}/${y}`;
        }

    } else if (gtcByKhoPeriod === 'week') {
        // --- CHẾ ĐỘ TUẦN: gom thành tuần, lấy tuần gần nhất ---
        const latestDate = allDates[0];
        const latestWeekInfo = _isoWeek(latestDate);
        if (!latestWeekInfo) { chartRows = []; }
        else {
            const { week: latestWeek, year: latestYear } = latestWeekInfo;

            // Gom dữ liệu theo kho + tuần
            const khoMap = {};
            state.gtcData.forEach(r => {
                const wi = _isoWeek(r['Ngày']);
                if (!wi || wi.week !== latestWeek || wi.year !== latestYear) return;
                const khoFull = r['Kho'] || '';
                if (!khoMap[khoFull]) khoMap[khoFull] = { Kho: khoFull, gtc: 0, gan: 0 };
                khoMap[khoFull].gtc += parseInt((r['Số đơn GTC'] || '0').toString().replace(/\./g,'')) || 0;
                khoMap[khoFull].gan += parseInt((r['Số đơn gán'] || '0').toString().replace(/\./g,'')) || 0;
            });
            chartRows = Object.values(khoMap).map(x => ({
                'Kho': x.Kho,
                'Số đơn GTC': x.gtc,
                'Số đơn gán': x.gan,
                '% GTC': x.gan > 0 ? (x.gtc / x.gan * 100).toFixed(2) : '0'
            }));
            if (selectedGtcKhos.length > 0)
                chartRows = chartRows.filter(r => selectedGtcKhos.includes(shortKho(r['Kho'])));

            // Tính ngày đầu tuần (Thứ 2)
            const rangeStr = _weekRange(latestDate);
            periodLabel = `Tuần ${latestWeek}/${latestYear} (${rangeStr}) — tổng hợp toàn tuần`;
        }

    } else {
        // --- CHẾ ĐỘ THÁNG: gom thành tháng, lấy tháng gần nhất ---
        const latestDate = allDates[0];
        const latestYM = _yearMonth(latestDate);
        if (!latestYM) { chartRows = []; }
        else {
            const khoMap = {};
            state.gtcData.forEach(r => {
                if (_yearMonth(r['Ngày']) !== latestYM) return;
                const khoFull = r['Kho'] || '';
                if (!khoMap[khoFull]) khoMap[khoFull] = { Kho: khoFull, gtc: 0, gan: 0 };
                khoMap[khoFull].gtc += parseInt((r['Số đơn GTC'] || '0').toString().replace(/\./g,'')) || 0;
                khoMap[khoFull].gan += parseInt((r['Số đơn gán'] || '0').toString().replace(/\./g,'')) || 0;
            });
            chartRows = Object.values(khoMap).map(x => ({
                'Kho': x.Kho,
                'Số đơn GTC': x.gtc,
                'Số đơn gán': x.gan,
                '% GTC': x.gan > 0 ? (x.gtc / x.gan * 100).toFixed(2) : '0'
            }));
            if (selectedGtcKhos.length > 0)
                chartRows = chartRows.filter(r => selectedGtcKhos.includes(shortKho(r['Kho'])));

            const [yr, mo] = latestYM.split('-');
            periodLabel = `Tháng ${parseInt(mo)}/${yr} (tổng hợp từ ngày 1)`;
        }
    }

    // Hien thi period label
    const labelEl = document.getElementById('gtc-by-kho-period-label');
    if (labelEl) labelEl.textContent = periodLabel;

    // =====================================================================
    // RENDER CHART
    // =====================================================================
    const sorted = [...chartRows].sort((a, b) => parsePct(a['% GTC']) - parsePct(b['% GTC']));

    const labels = sorted.map(r => shortKho(r['Kho']));
    const values = sorted.map(r => {
        const v = parseFloat(String(r['% GTC']).replace(',','.').replace('%',''));
        return isNaN(v) ? 0 : parseFloat(v.toFixed(2));
    });
    const colors = values.map(v => v >= 90 ? C_GREEN : v >= 80 ? C_ORANGE : C_RED);

    // Calculate totals for Legend display
    let sumGtc = 0;
    let sumGan = 0;
    sorted.forEach(r => {
        sumGtc += parseInt((r['Số đơn GTC'] || '0').toString().replace(/\./g, '')) || 0;
        sumGan += parseInt((r['Số đơn gán'] || '0').toString().replace(/\./g, '')) || 0;
    });
    const totalPctStr = sumGan > 0 ? (sumGtc / sumGan * 100).toFixed(2) + '%' : '0%';

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
            datasets: [
                {
                    label: `GTC: ${sumGtc.toLocaleString('vi-VN')} (${totalPctStr})`,
                    data: values,
                    backgroundColor: colors,
                    borderRadius: 4,
                    datalabels: { anchor: 'end', align: 'right', color: ctx2 => colors[ctx2.dataIndex], font: { weight: 'bold' }, formatter: v => v + '%' }
                },
                {
                    label: `Gán: ${sumGan.toLocaleString('vi-VN')}`,
                    data: [], // Purely visual legend item supporting accessible Yellow palette
                    backgroundColor: '#FBC02D',
                    borderColor: '#FBC02D'
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: '#525F7F', padding: 12, font: { size: 11, weight: 'bold' }, boxWidth: 12 }
                },
                datalabels: { display: true }
            },
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

    const allDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    if (!allDates.length) return;

    const latestDate = allDates[0];
    const latestTs = parseVN(latestDate);

    // Calendar Week
    const d = new Date(latestTs);
    const day = d.getDay() || 7;
    const startOfWeek = new Date(d);
    startOfWeek.setHours(0, 0, 0, 0);
    startOfWeek.setDate(d.getDate() - day + 1);

    // Calendar Month
    const startOfMonth = new Date(d.getFullYear(), d.getMonth(), 1);
    startOfMonth.setHours(0, 0, 0, 0);

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
            .filter(([, v]) => v.gan >= 10)
            .map(([k, v]) => ({ kho: k, pct: +(v.gtc / v.gan * 100).toFixed(2), gtc: v.gtc, gan: v.gan }))
            .sort((a, b) => b.pct - a.pct);
    }

    const rowsDay = state.gtcData.filter(r => r['Ngày'] === latestDate);
    const rowsWeek = state.gtcData.filter(r => parseVN(r['Ngày']) >= startOfWeek.getTime());
    const rowsMonth = state.gtcData.filter(r => parseVN(r['Ngày']) >= startOfMonth.getTime());

    const rankDay = computeKhoRanking(rowsDay);
    const rankWeek = computeKhoRanking(rowsWeek);
    const rankMonth = computeKhoRanking(rowsMonth);

    function renderPanel(title, icon, ranking) {
        if (!ranking.length) return `<div class="table-card"><div class="table-header"><h3>${title}</h3></div><p style="padding:16px;color:var(--text3)">Không có dữ liệu</p></div>`;
        const top5 = ranking.slice(0, 5);
        const bottom5 = ranking.slice(-5);
        const renderRow = (r, isTop) => `
            <tr style="background:${isTop ? 'var(--green-bg)' : 'var(--red-bg)'}">
                <td><span class="badge ${isTop ? 'storing' : 'p1'}">${isTop ? '↑ Tốt' : '↓ Tệ'}</span></td>
                <td style="font-weight:600">${escapeHtml(r.kho)}</td>
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
        (r['order_code'] || '').toLowerCase().includes(khoFilter.toLowerCase())
    );
    if (luongFilter) data = data.filter(r => (r['client_type'] || '').toLowerCase().includes(luongFilter.toLowerCase()));
    data.sort((a, b) => getAging(b) - getAging(a));

    document.getElementById('backlog-count-label').textContent = data.length + ' đơn';
    window.backlogTableLimit = window.backlogTableLimit || 100;
    const sliced = data.slice(0, window.backlogTableLimit);
    let html = sliced.map(r => `
        <tr>
            <td>${escapeHtml(r['status'] || '--')}</td>
            <td>${escapeHtml(getRegionByDate(r['kho_giao'] || r['Kho'], r['time_nhap_kho_giao']))}</td>
            <td>${escapeHtml(shortKho(getKho(r)))}</td>
            <td>${escapeHtml(r['PIC'] || '--')}</td>
            <td class="order-code">${escapeHtml(r['order_code'] || '')}</td>
            <td>${escapeHtml(r['client_type'] || '')}</td>
            <td style="max-width:140px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(r['Lý do giao thất bại gần nhất'] || '')}</td>
            <td>${escapeHtml(r['time_nhap_kho_giao'] || '')}</td>
            <td>${agingChip(getAging(r))}</td>
        </tr>
    `).join('');
    
    if (data.length > window.backlogTableLimit) {
        html += `<tr><td colspan="9" style="text-align:center;padding:12px;"><button class="btn btn-secondary btn-sm" onclick="window.backlogTableLimit += 100; renderBacklogSection('${khoFilter.replace(/'/g, "\\'")}', '${luongFilter.replace(/'/g, "\\'")}');" style="cursor:pointer;padding:6px 12px;font-size:0.8rem;"><i class="fa-solid fa-angles-down"></i> Xem thêm (${data.length - window.backlogTableLimit} dòng còn lại)</button></td></tr>`;
    }
    document.getElementById('tbody-backlog').innerHTML = html;
}

// ---- BACKLOG BY KHO CHART ----
function renderBacklogByKhoChart() {
    const khoMap = {};
    state.backlogData.forEach(r => {
        const k = shortKho(r['kho_giao'] || r['Kho'] || 'N/A');
        khoMap[k] = (khoMap[k] || 0) + 1;
    });
    const sorted = Object.entries(khoMap).sort((a, b) => b[1] - a[1]);

    destroyChart('backlogByKho');
    const ctx = document.getElementById('chart-backlog-by-kho').getContext('2d');
    charts.backlogByKho = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(e => e[0]),
            datasets: [{
                label: 'Số đơn tồn',
                data: sorted.map(e => e[1]),
                backgroundColor: 'rgba(239, 68, 68, 0.75)',
                borderRadius: 5,
                datalabels: {
                    anchor: 'end',
                    align: 'right',
                    color: C_RED,
                    font: { weight: 'bold', size: 10 },
                    formatter: v => v.toLocaleString('vi-VN')
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                datalabels: { display: true }
            },
            scales: {
                x: { ticks: { font: { size: 11 } } },
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
        (shortKho(r['Kho hiện tại']) || '').toLowerCase().includes(khoFilter.toLowerCase()) ||
        (r['Order code'] || '').toLowerCase().includes(khoFilter.toLowerCase())
    );
    if (prioFilter) data = data.filter(r => (r['Mức độ ưu tiên'] || '') === prioFilter);
    if (clientFilter) data = data.filter(r => (r['Khách'] || '') === clientFilter);
    if (typeFilter) data = data.filter(r => (r['Loại'] || '') === typeFilter);

    const prio = ['1: trong hôm nay', '2: trong ngày mai', '3: trong ngày mốt'];
    data.sort((a, b) => prio.indexOf(a['Mức độ ưu tiên']) - prio.indexOf(b['Mức độ ưu tiên']));

    document.getElementById('b2b-count-label').textContent = data.length + ' đơn';
    document.getElementById('tbody-b2b').innerHTML = data.map(r => `
        <tr>
            <td>${priorityBadge(r['Mức độ ưu tiên'])}</td>
            <td>${escapeHtml(shortKho(r['Kho hiện tại']))}</td>
            <td>${escapeHtml(r['PIC'] || '')}</td>
            <td class="order-code">${escapeHtml(r['Order code'] || '')}</td>
            <td><span class="badge ${r['Loại'] === 'Giao' ? 'storing' : 'waiting'}">${escapeHtml(r['Loại'] || '')}</span></td>
            <td>${escapeHtml(r['Khách'] || '')}</td>
            <td>${escapeHtml(r['Ngày nhập kho'] || '')}</td>
            <td>${agingChip(r['Đã lưu kho (ngày)'] || 0)}</td>
            <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(r['Địa chỉ giao'] || '')}</td>
        </tr>
    `).join('');
}

// ---- RETURNS SECTION ----
function renderReturnsSection(clientFilter = '') {
    renderReturnsByClient(clientFilter);

    const sorted = [...state.returnsData].sort((a, b) => {
        const da = (a['Ngày'] || '').split(' - ')[0];
        const db = (b['Ngày'] || '').split(' - ')[0];
        return db.localeCompare(da);
    });
    document.getElementById('tbody-returns').innerHTML = sorted.map(r => `
        <tr>
            <td>${escapeHtml(shortKho(r['Kho']))}</td>
            <td>${escapeHtml(r['Ngày'] || '')}</td>
            <td style="text-align:center;font-weight:700">${escapeHtml(String(r['Số đơn trả'] || 0))}</td>
            <td style="text-align:right;font-weight:800;color:var(--red)">${escapeHtml(r['% FD'] || '')}</td>
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

    const sorted = [...data].sort((a, b) => {
        const da = (a['Thời gian'] || '').split(' - ')[0];
        const db = (b['Thời gian'] || '').split(' - ')[0];
        return db.localeCompare(da);
    });

    tbody.innerHTML = sorted.slice(0, 10).map(r => `
        <tr>
            <td style="font-weight:600;color:var(--text3);font-size:11px">${escapeHtml(r['Thời gian'] || '--')}</td>
            <td style="text-align:center;font-weight:700;color:var(--orange)">${escapeHtml(String(r['Tổng đơn trả'] || 0))}</td>
            <td style="text-align:right;font-weight:700;color:var(--red)">${escapeHtml(r['Trả hàng tổng'] || '0%')}</td>
            <td style="text-align:right">${escapeHtml(r['Trả hàng SHOPEE Bulky'] || '0%')}</td>
            <td style="text-align:right">${escapeHtml(r['Trả hàng TTS Bulky'] || '0%')}</td>
            <td style="text-align:right">${escapeHtml(r['Trả hàng SME'] || '0%')}</td>
            <td style="text-align:right">${escapeHtml(r['Trả hàng B2B'] || '0%')}</td>
            <td style="text-align:right">${escapeHtml(r['Trả hàng Ecommerce'] || '0%')}</td>
        </tr>
    `).join('');
}

// ---- RETURNS FD CHART ----
function renderReturnsFDChart() {
    const data = state.returnsByClientData;
    if (!data || !data.length) return;

    // Get last 20 days
    const sortedData = [...data].sort((a, b) => {
        const da = (a['Thời gian'] || '').split(' - ')[0];
        const db = (b['Thời gian'] || '').split(' - ')[0];
        return da.localeCompare(db); // Oldest to newest
    }).slice(-20);

    const labels = sortedData.map(r => (r['Thời gian'] || '').split(' - ')[0]);
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
                label: '% Trả hàng',
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
                pointHoverRadius: 6,
                datalabels: { display: false }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                datalabels: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#F3F4F6',
                    bodyColor: '#F3F4F6',
                    borderColor: 'rgba(0, 240, 255, 0.15)',
                    borderWidth: 1,
                    borderRadius: 8,
                    padding: 10,
                    displayColors: false,
                    callbacks: { label: c => ' ' + c.raw + '%' }
                }
            },
            scales: {
                y: { min: 0, max: 15, ticks: { callback: v => v + '%', font: { size: 10 } } },
                x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45, minRotation: 45 } }
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
    const posSorted = Object.entries(posMap).sort((a, b) => b[1] - a[1]);

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
        'Dưới 1 tháng', 'Trên 1 - 3 tháng', 'Trên 3 - 6 tháng',
        'Trên 6 tháng - 1 năm', 'Trên 1 - 1,5 năm', 'Trên 1,5 -2 năm',
        'Trên 2 - 3 năm', 'Trên 3 - 4 năm', 'Trên 4 - 5 năm', 'Trên 5 năm'
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
                        <td>${escapeHtml(pos)}</td>
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
                        <td>${escapeHtml(tn)}</td>
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
    
    // Render the main personnel list table
    window.personnelTableLimit = window.personnelTableLimit || 100;
    const sliced = data.slice(0, window.personnelTableLimit);
    let html = sliced.map((r, i) => {
        const loaiHD = r['Loại hợp đồng'] || r['Loại HĐ'] || '';
        return `
        <tr>
            <td>${i + 1}</td>
            <td style="font-family:monospace;font-size:12px;color:var(--text3)">${escapeHtml(r['ID'] || '')}</td>
            <td style="font-weight:600">${escapeHtml(r['Họ tên'] || '')}</td>
            <td>${escapeHtml(r['Vị trí công việc'] || r['Tên vị trí'] || '')}</td>
            <td><span class="badge ${loaiHD.includes('Xác định') || loaiHD.includes('chính thức') ? 'storing' : 'p3'}">${escapeHtml(loaiHD)}</span></td>
            <td>${escapeHtml(r['Thâm niên'] || '')}</td>
            <td>${escapeHtml(shortKho((r['Kho làm việc'] || r['Kho'] || '').trim() === 'Miền Trung 05' ? 'Miền Trung 02' : (r['Kho làm việc'] || r['Kho'] || '')) || '')}</td>
            <td>${escapeHtml(r['Phòng ban'] || '')}</td>
        </tr>
    `}).join('');
    
    if (data.length > window.personnelTableLimit) {
        html += `<tr><td colspan="8" style="text-align:center;padding:12px;"><button class="btn btn-secondary btn-sm" onclick="window.personnelTableLimit += 100; renderPersonnelSection('${filter.replace(/'/g, "\'")}', '${posFilter.replace(/'/g, "\'")}');" style="cursor:pointer;padding:6px 12px;font-size:0.8rem;"><i class="fa-solid fa-angles-down"></i> Xem thêm (${data.length - window.personnelTableLimit} dòng còn lại)</button></td></tr>`;
    }
    document.getElementById('tbody-personnel').innerHTML = html;

    // Render "Bảng tổng hợp nhân sự theo kho và vị trí" (Pivot Table)
    const pivotTable = document.getElementById('personnel-pivot-table');
    if (pivotTable) {
        if (data.length === 0) {
            pivotTable.innerHTML = `
                <thead>
                    <tr>
                        <th style="width: 50px;">STT</th>
                        <th style="width: 250px;">Tên Kho</th>
                        <th style="font-weight: 700; color: var(--blue);">Tổng</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td colspan="3" style="text-align: center; color: var(--text3); padding: 20px;">Không có dữ liệu</td>
                    </tr>
                </tbody>
            `;
        } else {
            // Find all unique positions in the filtered data dynamically
            const positionsSet = new Set();
            data.forEach(r => {
                const pos = (r['Vị trí công việc'] || r['Tên vị trí'] || '').trim();
                if (pos) positionsSet.add(pos);
            });
            const positions = Array.from(positionsSet).sort();
            
            // Group by warehouse name
            const pivot = {};
            data.forEach(r => {
                const rawKhoRaw = r['Kho làm việc'] || r['Kho'] || 'Chưa xác định';
                const rawKho = (rawKhoRaw.trim() === 'Miền Trung 05') ? 'Miền Trung 02' : rawKhoRaw;
                const kho = shortKho(rawKho).trim();
                const pos = (r['Vị trí công việc'] || r['Tên vị trí'] || 'Khác').trim();
                
                if (!pivot[kho]) {
                    pivot[kho] = {};
                }
                pivot[kho][pos] = (pivot[kho][pos] || 0) + 1;
            });
            
            // Format warehouse list with total counts
            const warehouses = Object.keys(pivot).map(kho => {
                let total = 0;
                positions.forEach(pos => {
                    total += (pivot[kho][pos] || 0);
                });
                return { name: kho, positions: pivot[kho], total: total };
            });
            
            // Sort warehouses by total personnel descending
            warehouses.sort((a, b) => b.total - a.total);
            
            console.log(`[PIVOT DEBUG] Found ${positions.length} unique positions and ${warehouses.length} warehouses.`);
            if (warehouses.length > 0) {
                console.log(`[PIVOT DEBUG] First warehouse: ${warehouses[0].name}, Total=${warehouses[0].total}`);
            }
            
            // Calculate totals for each position and grand total
            const positionTotals = {};
            let grandTotal = 0;
            positions.forEach(pos => {
                let sum = 0;
                warehouses.forEach(w => {
                    sum += (w.positions[pos] || 0);
                });
                positionTotals[pos] = sum;
                grandTotal += sum;
            });
            
            // Construct table header
            const theadHtml = `
                <thead>
                    <tr>
                        <th style="width: 50px;">STT</th>
                        <th style="width: 250px;">Tên Kho</th>
                        ${positions.map(pos => `<th>${escapeHtml(pos)}</th>`).join('')}
                        <th style="font-weight: 700; color: var(--blue);">Tổng</th>
                    </tr>
                </thead>
            `;
            
            // Construct table body
            const tbodyHtml = `
                <tbody>
                    ${warehouses.map((w, idx) => `
                        <tr>
                            <td>${idx + 1}</td>
                            <td style="font-weight: 600;">${escapeHtml(w.name)}</td>
                            ${positions.map(pos => `<td>${w.positions[pos] || 0}</td>`).join('')}
                            <td style="font-weight: 700; color: var(--blue);">${w.total}</td>
                        </tr>
                    `).join('')}
                    <tr style="border-top: 2px solid var(--border-card); font-weight: 700; background-color: var(--bg-card);">
                        <td style="font-weight: 700;">Tổng cộng</td>
                        <td></td>
                        ${positions.map(pos => `<td style="font-weight: 700; color: var(--orange);">${positionTotals[pos]}</td>`).join('')}
                        <td style="font-weight: 700; color: var(--blue);">${grandTotal}</td>
                    </tr>
                </tbody>
            `;
            
            pivotTable.innerHTML = theadHtml + tbodyHtml;
        }
    }
}
// ---- NĂNG SUẤT NV SECTION ----
let currentNsPeriod = 'day';

let currentProdDays = 7;
window.switchProdTab = function (btn, days) {
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
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:20px;color:#8898AA">Không có dữ liệu thỏa mãn điều kiện (Tổng đơn > 30 trong ${daysLimit} ngày)</td></tr>`;
        return;
    }

    tbody.innerHTML = list.slice(0, 10).map((r, idx) => `
        <tr>
            <td><span class="badge ${idx < 3 ? 'p1' : 'waiting'}">#${idx + 1}</span></td>
            <td style="font-weight:600">${escapeHtml(r.name)}</td>
            <td>${escapeHtml(r.province)}</td>
            <td style="text-align:right;font-weight:700">${r.totalVol.toLocaleString()} đơn</td>
            <td style="text-align:right;font-weight:700;color:var(--red)">${r.pctGtc.toFixed(2)}%</td>
        </tr>
    `).join('');
}

let nsTimeMode = 'day';
let selectedNsVals = [];
let selectedNsProvs = [];
let nsFiltersInit = false;

function renderNsMultiItems(mode, values) {
    const menu = document.getElementById('menu-ns-' + mode);
    if (!menu) return;
    menu.innerHTML = '';
    values.forEach(v => {
        const item = document.createElement('div');
        item.className = 'ghn-filter-item';
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.id = `chk-ns-${mode}-${v.replace(/[^a-z0-9]/gi, '-')}`;
        chk.value = v;  // DOM property, không cần escape
        chk.setAttribute('onchange', `updateNsTimeMode('${mode}')`);
        const lbl = document.createElement('label');
        lbl.htmlFor = chk.id;
        lbl.textContent = mode === 'day' ? v : mode === 'week' ? 'Tuần ' + v : mode === 'month' ? 'Tháng ' + v : v;
        item.appendChild(chk);
        item.appendChild(lbl);
        menu.appendChild(item);
    });
}

function updateNsLabel(mode) {
    const menu = document.getElementById('menu-ns-' + mode);
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const label = document.querySelector(`#multi-ns-${mode} .ghn-filter-selected`);
    if (!label) return;
    if (checks.length === 0) {
        const map = { day: 'Chọn Ngày...', week: 'Chọn Tuần...', month: 'Chọn Tháng...', prov: 'Chọn Khu vực...' };
        label.innerText = map[mode] || '...';
    } else {
        label.innerText = `${checks.length} mục đã chọn`;
    }
    const items = Array.from(menu.querySelectorAll('.ghn-filter-item'));
    items.sort((a, b) => { const ca = a.querySelector('input').checked, cb = b.querySelector('input').checked; return ca === cb ? 0 : ca ? -1 : 1; });
    items.forEach(item => menu.appendChild(item));
}

function clearNsOtherModes(modes) {
    modes.forEach(m => {
        const menu = document.getElementById('menu-ns-' + m);
        if (menu) {
            menu.querySelectorAll('input[type="checkbox"]').forEach(c => c.checked = false);
            updateNsLabel(m);
        }
    });
}

window.updateNsTimeMode = function (mode) {
    const menu = document.getElementById('menu-ns-' + mode);
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const vals = Array.from(checks).map(c => c.value);

    if (mode === 'prov') {
        selectedNsProvs = vals;
    } else {
        nsTimeMode = mode;
        selectedNsVals = vals;
        if (mode === 'day') clearNsOtherModes(['week', 'month']);
        else if (mode === 'week') clearNsOtherModes(['day', 'month']);
        else if (mode === 'month') clearNsOtherModes(['day', 'week']);
    }
    updateNsLabel(mode);
    renderNangSuatSection();
};

function populateNsSelects() {
    const dayMenu = document.getElementById('menu-ns-day');
    if (!dayMenu || dayMenu.children.length > 0) return;

    const allData = state.nangSuatData || [];
    const days = [...new Set(allData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    renderNsMultiItems('day', days);

    const weeks = [...new Set(allData.map(r => {
        const ts = parseVN(r['Ngày']);
        return ts ? String(getWeekNumber(new Date(ts))) : null;
    }).filter(Boolean))].sort((a, b) => parseInt(b) - parseInt(a));
    renderNsMultiItems('week', weeks);

    const months = [...new Set(allData.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    }).filter(Boolean))].sort().reverse();
    renderNsMultiItems('month', months);

    const provs = [...new Set(allData.map(r => r['to_province_name']).filter(Boolean))].sort();
    renderNsMultiItems('prov', provs);

    if (days.length > 0) {
        const safeId = days[0].replace(/[^a-z0-9]/gi, '-');
        const firstChk = document.getElementById('chk-ns-day-' + safeId);
        if (firstChk) firstChk.checked = true;
        selectedNsVals = [days[0]];
        updateNsLabel('day');
    }

    if (!nsFiltersInit) {
        const searchEl = document.getElementById('filter-ns-driver');
        if (searchEl) searchEl.addEventListener('input', () => renderNangSuatSection());
        nsFiltersInit = true;
    }
}

// ---- NĂNG SUẤT NV SECTION ----
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

    const allDates = [...new Set(state.nangSuatData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    if (!allDates.length) return;

    const latestDate = allDates[0];
    if (!latestDate) return;

    const latestTs = parseVN(latestDate);
    const d = new Date(latestTs);

    // Calendar Week
    const day = d.getDay() || 7;
    const startOfWeek = new Date(d);
    startOfWeek.setDate(d.getDate() - day + 1);
    startOfWeek.setHours(0, 0, 0, 0);

    // Calendar Month
    const startOfMonth = new Date(d.getFullYear(), d.getMonth(), 1);
    startOfMonth.setHours(0, 0, 0, 0);

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
        driverMap[idName].totalVol += parseInt(r['volume'] || 0);
        driverMap[idName].totalSuccess += (parsePct(r['Tỉ lệ GTC']) / 100) * parseInt(r['volume'] || 0);
        driverMap[idName].sumRate += parseFloat((r['avg_delivery_volume_per_hour'] || '0').toString().replace(',', '.'));
        driverMap[idName].daysCount += 1;
    });

    let drivers = Object.values(driverMap).map(d => ({
        ...d,
        avgRate: d.daysCount > 0 ? (d.sumRate / d.daysCount) : 0,
        pctGtc: d.totalVol > 0 ? (d.totalSuccess / d.totalVol * 100) : 0
    }));

    const minVol = 30;
    const listToSort = drivers.filter(d => d.totalVol >= minVol);
    listToSort.sort((a, b) => b.pctGtc - a.pctGtc);

    const formatRow = (r, idx, isTop) => `
        <tr>
            <td><span class="badge ${isTop ? 'storing' : 'p1'}">#${idx + 1}</span></td>
            <td style="font-weight:600">${escapeHtml(r.name)}</td>
            <td>${escapeHtml(r.province)}</td>
            <td style="text-align:right">${r.avgRate.toFixed(1)}</td>
            <td style="text-align:right">${r.totalVol.toLocaleString()}</td>
            <td style="text-align:right;font-weight:700;color:${isTop ? 'var(--green)' : 'var(--red)'}">${r.pctGtc.toFixed(1)}%</td>
        </tr>`;

    const top10 = listToSort.slice(0, 10).sort((a, b) => b.totalVol - a.totalVol);
    document.getElementById('tbody-ns-top').innerHTML = top10.map((r, i) => formatRow(r, i, true)).join('');

    const bottom10 = [...listToSort].sort((a, b) => a.pctGtc - b.pctGtc).slice(0, 10).sort((a, b) => b.totalVol - a.totalVol);
    document.getElementById('tbody-ns-bottom').innerHTML = bottom10.map((r, i) => formatRow(r, i, false)).join('');

    // RENDER ALL DRIVERS TABLE
    const allTbody = document.getElementById('tbody-ns-all');
    if (allTbody) {
        populateNsSelects();
        let allTableData = [...state.nangSuatData];
        const searchVal = ((document.getElementById('filter-ns-driver') || {}).value || '').toLowerCase();

        if (selectedNsVals.length > 0 && (nsTimeMode === 'week' || nsTimeMode === 'month')) {
            let filtered = allTableData.filter(r => {
                const ts = parseVN(r['Ngày']);
                if (!ts) return false;
                const d = new Date(ts);
                if (nsTimeMode === 'week') return selectedNsVals.includes(String(getWeekNumber(d)));
                if (nsTimeMode === 'month') {
                    const m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
                    return selectedNsVals.includes(m);
                }
                return true;
            });

            if (selectedNsProvs.length > 0) {
                filtered = filtered.filter(r => selectedNsProvs.includes(r['to_province_name']));
            }
            if (searchVal) {
                filtered = filtered.filter(r => (r['driver'] || '').toLowerCase().includes(searchVal));
            }

            const groupMap = {};
            filtered.forEach(r => {
                const driver = r['driver'] || '--';
                const prov = r['to_province_name'] || '--';
                const ts = parseVN(r['Ngày']);
                if (!ts) return;
                const d = new Date(ts);

                let tKey = '';
                let tLabel = '';
                if (nsTimeMode === 'week') {
                    const w = String(getWeekNumber(d));
                    tKey = 'W_' + w;
                    tLabel = 'Tuần ' + (w.includes('-W') ? w.split('-W')[1] : w);
                } else {
                    const m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
                    tKey = 'M_' + m;
                    tLabel = 'Tháng ' + m;
                }

                const compKey = driver + '###' + prov + '###' + tKey;
                if (!groupMap[compKey]) {
                    groupMap[compKey] = {
                        driver: driver,
                        province: prov,
                        tLabel: tLabel,
                        totalVol: 0,
                        totalSuccess: 0,
                        sumRate: 0,
                        daysCount: 0
                    };
                }
                const vol = parseInt(r['volume'] || 0);
                groupMap[compKey].totalVol += vol;
                groupMap[compKey].totalSuccess += (parsePct(r['Tỉ lệ GTC']) / 100) * vol;
                groupMap[compKey].sumRate += parseFloat((r['avg_delivery_volume_per_hour'] || '0').toString().replace(',', '.'));
                groupMap[compKey].daysCount += 1;
            });

            const aggregatedList = Object.values(groupMap).map(g => {
                const pctGtc = g.totalVol > 0 ? (g.totalSuccess / g.totalVol * 100) : 0;
                const avgRate = g.daysCount > 0 ? (g.sumRate / g.daysCount) : 0;
                return { ...g, pctGtc, avgRate };
            });

            aggregatedList.sort((a, b) => b.pctGtc - a.pctGtc || b.totalVol - a.totalVol);

            allTbody.innerHTML = aggregatedList.map(g => `
                <tr>
                    <td style="font-size:11px;font-weight:700;color:var(--blue)">${escapeHtml(g.tLabel)}</td>
                    <td style="font-weight:600">${escapeHtml(g.driver)}</td>
                    <td>${escapeHtml(g.province)}</td>
                    <td style="text-align:right">${g.avgRate.toFixed(1)}</td>
                    <td style="text-align:right;font-weight:600">${g.totalVol.toLocaleString()}</td>
                    <td style="text-align:right;font-weight:700;color:${g.pctGtc >= 90 ? 'var(--green)' : 'var(--red)'}">${g.pctGtc.toFixed(1)}%</td>
                    <td style="font-size:11px;color:var(--text3);text-align:center">Tổng hợp</td>
                    <td style="font-size:11px;color:var(--text3);text-align:center">Tổng hợp</td>
                </tr>
            `).join('');

        } else {
            if (selectedNsVals.length > 0) {
                allTableData = allTableData.filter(r => selectedNsVals.includes(r['Ngày']));
            }
            if (selectedNsProvs.length > 0) {
                allTableData = allTableData.filter(r => selectedNsProvs.includes(r['to_province_name']));
            }
            if (searchVal) {
                allTableData = allTableData.filter(r => (r['driver'] || '').toLowerCase().includes(searchVal));
            }

            allTbody.innerHTML = allTableData.sort((a, b) => { const rA = parsePct(a['Tỉ lệ GTC']), rB = parsePct(b['Tỉ lệ GTC']); if (rB !== rA) return rB - rA; return parseVN(b['Ngày']) - parseVN(a['Ngày']); }).map(r => `
                <tr>
                    <td style="font-size:11px;color:var(--text3)">${escapeHtml(r['Ngày'] || '--')}</td>
                    <td style="font-weight:600">${escapeHtml(r['driver'] || '--')}</td>
                    <td>${escapeHtml(r['to_province_name'] || '--')}</td>
                    <td style="text-align:right">${parseFloat(r['avg_delivery_volume_per_hour'] || 0).toFixed(1)}</td>
                    <td style="text-align:right;font-weight:600">${parseInt(r['volume'] || 0).toLocaleString()}</td>
                    <td style="text-align:right;font-weight:700;color:${parsePct(r['Tỉ lệ GTC']) >= 90 ? 'var(--green)' : 'var(--red)'}">${escapeHtml(r['Tỉ lệ GTC'] || '0%')}</td>
                    <td style="font-size:11px">${escapeHtml(r['first_3_delivery'] || '--')}</td>
                    <td style="font-size:11px">${escapeHtml(r['last_3_delivery'] || '--')}</td>
                </tr>
            `).join('');
        }
    }
}

// ---- WARNINGS SECTION ----
function renderWarningsSection(khoFilter = '', statusFilter = '') {
    let data = state.warningsData;
    if (!data) return;

    const ngayKey = 'Total ngày';

    // Xử lý dữ liệu
    const processedData = state.warningsData.map(r => {
        // Helper để lấy giá trị linh hoạt
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

        const soNgay = parseFloat(getV(['Số ngày trở về ngày thường', 'Total ngày', 'so ngay'], 0));
        const sheetStatus = getV(['Tình hình hiện tại', 'trạng thái hiện tại'], 'Bình thường');

        return {
            ...r,
            soNgayVal: soNgay,
            sheetStatus: sheetStatus
        };
    });

    // KPI Cards:
    // 1. Kho Nghiêm trọng: tính theo số ngày > 6
    const criticalList = processedData.filter(r => r.soNgayVal > 6);
    // 2. Kho Bất ổn: đếm theo cột trạng thái hiện tại của sheet
    const warningList = processedData.filter(r => r.sheetStatus === 'Bất ổn');

    const critEl = document.getElementById('warn-critical-count');
    if (critEl) critEl.textContent = criticalList.length;

    const warnEl = document.getElementById('warn-warning-count');
    if (warnEl) warnEl.textContent = warningList.length;

    const upcoming = processedData.filter(r => {
        const next = (r['Tình hình sắp tới'] || '').toLowerCase();
        return next.includes('cảnh báo') || next.includes('nghiêm trọng');
    });
    const upcomingEl = document.getElementById('warn-upcoming-count');
    if (upcomingEl) upcomingEl.textContent = upcoming.length;

    const totalNgay = processedData.reduce((sum, r) => sum + r.soNgayVal, 0);
    const avgDays = processedData.length ? totalNgay / processedData.length : 0;
    const avgDaysEl = document.getElementById('warn-avg-days');
    if (avgDaysEl) avgDaysEl.textContent = avgDays.toFixed(1);

    // Sync to Overview
    syncOverviewWarningCards();

    // Lọc dữ liệu theo filter người dùng
    let filtered = processedData;
    if (khoFilter) filtered = filtered.filter(r => shortKho(r['kho gxt'] || r['Kho'] || '').toLowerCase().includes(khoFilter.toLowerCase()));
    if (statusFilter) filtered = filtered.filter(r => r.sheetStatus === statusFilter);

    // Sắp xếp giảm dần theo số ngày
    filtered.sort((a, b) => b.soNgayVal - a.soNgayVal);

    // Render Table
    const tbody = document.getElementById('tbody-warnings');
    if (tbody) {
        // Tối ưu hóa: Nhóm dữ liệu GTC theo kho trước khi render
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
            if (status === 'Nghiêm trọng') badgeClass = 'p1';

            const nextStatus = r['Tình hình sắp tới'] || 'Bình thường';
            let nextBadgeClass = 'storing';
            if (nextStatus === 'Cảnh báo') nextBadgeClass = 'waiting';
            if (nextStatus === 'Nghiêm trọng') nextBadgeClass = 'p1';

            const backlogLM = parseInt(r['backlog last mile'] || r['backlog lastmile'] || 0);
            const backlogKTC = parseInt(r['backlog ktc'] || 0);
            const totalBL = backlogLM + backlogKTC;

            const donTao = r['đơn tạo N-1'] || r['??n t?o N-1'] || 0;
            const donGtc = r['đơn gtc N-1'] || r['??n gtc N-1'] || 0;

            // Truy xuất từ Map đã nhóm sẵn
            const warehouseName = shortKho(r['kho gxt'] || r['Kho'] || '');
            const warehouseGtcData = gtcMap.get(warehouseName) || [];

            // Sắp xếp ngày giảm dần và lấy 7 bản ghi gần nhất
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
                    <td style="font-weight:600">${escapeHtml(shortKho(r['kho gxt'] || r['Kho'] || '--'))}</td>
                    <td><span class="badge ${badgeClass}">${escapeHtml(status)}</span></td>
                    <td style="text-align:right;font-weight:700;color:var(--red)">${backlogLM.toLocaleString()}</td>
                    <td style="text-align:right">${backlogKTC.toLocaleString()}</td>
                    <td style="text-align:right;font-weight:700;color:var(--blue)">${totalBL.toLocaleString()}</td>
                    <td style="text-align:center;font-weight:600;color:var(--orange)">${escapeHtml(String(donTao))} / ${escapeHtml(String(donGtc))}</td>
                    <td style="text-align:right;font-weight:700;color:var(--green)">${Math.round(avgGtcVol).toLocaleString()}</td>
                    <td style="text-align:right;font-weight:700;color:var(--blue)">${maxGtcVol.toLocaleString()}</td>
                    <td style="text-align:right">
                        <span class="aging-chip ${r.soNgayVal > 6 ? 'aging-critical' : r.soNgayVal > 0 ? 'aging-high' : 'aging-normal'}">
                            ${r.soNgayVal} ngày
                        </span>
                    </td>
                    <td><span class="badge ${nextBadgeClass}">${escapeHtml(nextStatus)}</span></td>
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

    const f_kho = (document.getElementById('filter-xegxt-kho')?.value || '').toLowerCase();
    const f_tinh = (document.getElementById('filter-xegxt-tinh')?.value || '').toLowerCase();
    const f_ncc = (document.getElementById('filter-xegxt-ncc')?.value || '').toLowerCase();
    const f_loai = (document.getElementById('filter-xegxt-loai')?.value || '').toLowerCase();

    // Filter the raw data first
    const filteredRaw = state.xeGxtData.filter(r => {
        const matchKho = !f_kho || (r['Kho'] || '').toLowerCase().includes(f_kho);
        const matchTinh = !f_tinh || (r['Tỉnh'] || '').toLowerCase() === f_tinh;
        const matchNcc = !f_ncc || (r['Tên NCC'] || '').toLowerCase() === f_ncc;
        const matchLoai = !f_loai || (r['Loại xe'] || '').toLowerCase() === f_loai;
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

    let list = Object.values(summary).sort((a, b) => b.total - a.total);

    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center">Không tìm thấy kết quả</td></tr>';
        document.getElementById('tfoot-xegxt').innerHTML = '';
    } else {
        const grandTotal = list.reduce((sum, item) => sum + item.total, 0);
        tbody.innerHTML = list.map((item, index) => `
            <tr>
                <td style="color:var(--text3)">${index + 1}</td>
                <td>${escapeHtml(item.tinh)}</td>
                <td style="font-weight:600;color:var(--blue)">${escapeHtml(item.kho)}</td>
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
                    <td>${escapeHtml(r['Tỉnh'] || '--')}</td>
                    <td style="font-weight:600">${escapeHtml(r['Kho'] || '--')}</td>
                    <td>${escapeHtml(r['Tên NCC'] || '--')}</td>
                    <td><span class="badge" style="background:var(--bg2);color:var(--text1)">${escapeHtml(r['Loại xe'] || '--')}</span></td>
                    <td style="text-align:right;font-weight:700;color:var(--blue)">${parseInt(r['Tổng xe đang chạy'] || 0).toLocaleString()}</td>
                    <td style="font-size:0.85rem">${escapeHtml(r['Ca làm việc'] || '--')}</td>
                    <td style="text-align:right;font-weight:700;color:var(--orange)">${escapeHtml((r['Giá thuê xe'] || r['Gía thuê xe']) || '--')}</td>
                </tr>
            `).join('');
        }
    }
}

let filtersPopulated = false;
function populateXeGxtFilters() {
    if (filtersPopulated) return;

    const tinhSet = new Set();
    const nccSet = new Set();
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
        el.innerHTML = `<option value="">-- Tất cả ${id.split('-').pop()} --</option>` +
            Array.from(items).sort().map(i => `<option value="${i}">${i}</option>`).join('');
        el.value = currentVal;
    };

    populateSelect('filter-xegxt-tinh', tinhSet);
    populateSelect('filter-xegxt-ncc', nccSet);
    populateSelect('filter-xegxt-loai', loaiSet);

    filtersPopulated = true;
}

// ---- SECTION: XE SỰ CỐ ----
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
    const weekCont = document.getElementById('filter-xesuco-week-container');
    const monthCont = document.getElementById('filter-xesuco-month-container');

    const days = [...new Set(data.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    if (dayCont && dayCont.children.length === 0) {
        days.forEach(d => {
            const lbl = document.createElement('label');
            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.value = d;  // textContent an toàn, không cần escape
            chk.className = 'filter-xesuco-day';
            lbl.appendChild(chk);
            lbl.appendChild(document.createTextNode(' ' + d));
            dayCont.appendChild(lbl);
        });
        dayCont.querySelectorAll('input').forEach(i => i.addEventListener('change', () => {
            renderXeSuCoSection();
            const checked = Array.from(document.querySelectorAll('.filter-xesuco-day:checked'));
            document.getElementById('label-xesuco-day').textContent = checked.length ? `Đã chọn (${checked.length})` : 'Chọn Ngày...';
        }));
    }

    const weeks = [...new Set(data.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        const w = getWeek(d);
        return `Tuần ${d.getFullYear()}-W${w < 10 ? '0' + w : w}`;
    }).filter(Boolean))].sort().reverse();

    if (weekCont && weekCont.children.length === 0) {
        weeks.forEach(w => {
            const lbl = document.createElement('label');
            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.value = w;
            chk.className = 'filter-xesuco-week';
            lbl.appendChild(chk);
            lbl.appendChild(document.createTextNode(' ' + w));
            weekCont.appendChild(lbl);
        });
        weekCont.querySelectorAll('input').forEach(i => i.addEventListener('change', () => {
            renderXeSuCoSection();
            const checked = Array.from(document.querySelectorAll('.filter-xesuco-week:checked'));
            document.getElementById('label-xesuco-week').textContent = checked.length ? `Đã chọn (${checked.length})` : 'Chọn Tuần...';
        }));
    }

    const months = [...new Set(data.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        return `${d.getMonth() + 1}/${d.getFullYear()}`;
    }).filter(Boolean))].sort((a, b) => {
        const [m1, y1] = a.split('/');
        const [m2, y2] = b.split('/');
        return y2 - y1 || m2 - m1;
    });

    if (monthCont && monthCont.children.length === 0) {
        months.forEach(m => {
            const lbl = document.createElement('label');
            const chk = document.createElement('input');
            chk.type = 'checkbox';
            chk.value = m;
            chk.className = 'filter-xesuco-month';
            lbl.appendChild(chk);
            lbl.appendChild(document.createTextNode(' Tháng ' + m));
            monthCont.appendChild(lbl);
        });
        monthCont.querySelectorAll('input').forEach(i => i.addEventListener('change', () => {
            renderXeSuCoSection();
            const checked = Array.from(document.querySelectorAll('.filter-xesuco-month:checked'));
            document.getElementById('label-xesuco-month').textContent = checked.length ? `Đã chọn (${checked.length})` : 'Chọn Tháng...';
        }));
    }

    // Apply Filters
    const f_search = (document.getElementById('filter-xesuco-search')?.value || '').toLowerCase();
    const f_days = Array.from(document.querySelectorAll('.filter-xesuco-day:checked')).map(i => i.value);
    const f_weeks = Array.from(document.querySelectorAll('.filter-xesuco-week:checked')).map(i => i.value);
    const f_months = Array.from(document.querySelectorAll('.filter-xesuco-month:checked')).map(i => i.value);
    const f_kho = (document.getElementById('filter-xesuco-kho')?.value || '').toLowerCase();

    const filtered = data.filter(r => {
        const ts = parseVN(r['Ngày']);
        const d_obj = new Date(ts);
        const w_str = `Tuần ${d_obj.getFullYear()}-W${String(getWeek(d_obj)).padStart(2, '0')}`;
        const m_str = `${d_obj.getMonth() + 1}/${d_obj.getFullYear()}`;

        const matchSearch = !f_search ||
            (r['Kho'] || '').toLowerCase().includes(f_search) ||
            (r['NCC'] || '').toLowerCase().includes(f_search) ||
            (r['Biển Số'] || '').toLowerCase().includes(f_search) ||
            (r['ID'] || '').toLowerCase().includes(f_search);

        const matchDay = f_days.length === 0 || f_days.includes(r['Ngày']);
        const matchWeek = f_weeks.length === 0 || f_weeks.includes(w_str);
        const matchMonth = f_months.length === 0 || f_months.includes(m_str);
        const matchKho = !f_kho || (r['Kho'] || '').toLowerCase().includes(f_kho);

        return matchSearch && matchDay && matchWeek && matchMonth && matchKho;
    });

    // Render Raw (Show all columns from sheet)
    // Tỉnh, ID, Kho, Ngày, Lỗi, Nội Dung Chi Tiết, Biển Số Xe, NCC
    tbodyRaw.innerHTML = filtered.map((r, i) => `
        <tr>
            <td style="color:var(--text3)">${i + 1}</td>
            <td>${escapeHtml(r['Tỉnh'] || '')}</td>
            <td>${escapeHtml(r['ID'] || '')}</td>
            <td style="font-weight:600">${escapeHtml(r['Kho'] || '')}</td>
            <td>${escapeHtml(r['Ngày'] || '')}</td>
            <td style="color:var(--red)">${escapeHtml(r['Lỗi'] || '')}</td>
            <td style="font-size:0.85rem; max-width:300px; white-space:normal">${escapeHtml(r['Nội Dung Chi Tiết'] || '')}</td>
            <td style="font-weight:600">${escapeHtml(r['Biển Số Xe'] || '')}</td>
            <td>${escapeHtml(r['NCC'] || '')}</td>
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

    const sorted = [...filtered].sort((a, b) => {
        const da = parseInt(a['Diện Tích']) || 0;
        const db = parseInt(b['Diện Tích']) || 0;
        return db - da;
    });

    tbody.innerHTML = sorted.map(r => `
        <tr>
            <td style="font-weight:600">${escapeHtml(r['Tên'] || '--')}</td>
            <td>${escapeHtml(r['Số điện thoại'] || '--')}</td>
            <td style="color:var(--text3)">${escapeHtml(r['ID Kho'] || '')}</td>
            <td style="font-weight:700; color:var(--blue)">${escapeHtml(r['Tên Kho GXT'] || '')}</td>
            <td>${escapeHtml(r['Tỉnh'] || '')}</td>
            <td>${escapeHtml(r['Diện Tích'] || '')}</td>
            <td><span class="badge" style="background:${r['Tình trạng'] === 'Active' ? '#E8F5E9' : '#FFEBEE'}; color:${r['Tình trạng'] === 'Active' ? '#2E7D32' : '#C62828'}">${escapeHtml(r['Tình trạng'] || '')}</span></td>
            <td style="font-size:0.85rem">${escapeHtml(r['Địa chỉ kho'] || '')}</td>
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

    let msg = `📢 *BÁO CÁO VẬN HÀNH MIỀN TRUNG*\n⏱ _${dateStr} ${timeStr}_\n\n`;

    // 1. KHO NGHIÊM TRỌNG (Lấy từ Hệ Thống Cảnh Báo)
    msg += `🚨 *1. KHO NGHIÊM TRỌNG (>5 NGÀY):*\n`;
    const warnRows = document.querySelectorAll('#tbody-warnings tr');
    let warnCount = 0;
    warnRows.forEach(tr => {
        if (warnCount >= 10) return;
        const tds = tr.querySelectorAll('td');
        if (tds.length < 9) return;

        const kho = tds[0].innerText.trim();
        const status = tds[1].innerText.trim();
        const days = tds[8].innerText.trim(); // Số ngày về bình thường

        if (parseInt(days) > 5 || status.includes('Nghiêm trọng')) {
            msg += `${warnCount + 1}. *${kho}*: ${status} (${days})\n`;
            warnCount++;
        }
    });
    if (warnCount === 0) msg += `_Không có kho nào_\n`;
    msg += `\n`;

    // 2. CẢNH BÁO BACKLOG > 7 NGÀY
    msg += `🔥 *2. CẢNH BÁO BACKLOG > 7 NGÀY:*\n`;

    // Tính từ state.backlogData — tập hợp theo kho, sắp xếp giảm dần
    const backlogByKho = {};
    (state.backlogData || []).forEach(r => {
        const kho = shortKho(r['kho_giao'] || r['Kho'] || '--');
        if (kho && kho !== '--') backlogByKho[kho] = (backlogByKho[kho] || 0) + 1;
    });
    const backlogEntries = Object.entries(backlogByKho).sort((a, b) => b[1] - a[1]);
    const totalBacklog = backlogEntries.reduce((s, [, v]) => s + v, 0);

    if (backlogEntries.length === 0) {
        msg += `Không có kho phát sinh backlog > 7 ngày.\n`;
    } else {
        msg += `*Tổng backlog > 7 ngày:* ${totalBacklog.toLocaleString('vi-VN')} đơn\n`;
        msg += `*Kho cần xử lý:*\n`;
        backlogEntries.forEach(([kho, count]) => {
            msg += `• ${kho}: *${count.toLocaleString('vi-VN')} đơn*\n`;
        });
        msg += `\n*Yêu cầu xử lý:*\n`;
        msg += `• Kho rà soát từng đơn backlog > 7 ngày.\n`;
        msg += `• Xác định lý do chưa xử lý: khách hẹn, thiếu xe, sai địa chỉ, hàng lưu kho, chưa liên hệ được khách.\n`;
        msg += `• Cập nhật hướng xử lý và cam kết thời gian clear trước 16h hôm nay.\n`;
    }
    msg += `\n`;


    // 3. HIỆU SUẤT KHO (GTC)
    msg += `🏢 *3. HIỆU SUẤT KHO (GTC):*\n`;
    const gtcPanels = document.querySelectorAll('#gtc-top-bottom .table-card');
    gtcPanels.forEach(panel => {
        const title = panel.querySelector('h3')?.innerText.trim() || 'GTC';
        msg += `*${title}:*\n`;
        const rows = Array.from(panel.querySelectorAll('tbody tr'));

        const tops = rows.filter(tr => tr.querySelector('.badge')?.innerText.includes('Tốt')).slice(0, 3);
        const bottoms = rows.filter(tr => tr.querySelector('.badge')?.innerText.includes('Tệ')).slice(-3).reverse();

        tops.forEach(tr => {
            const tds = tr.querySelectorAll('td');
            msg += ` ✅ ${tds[1].innerText}: *${tds[3].innerText}*\n`;
        });
        bottoms.forEach(tr => {
            const tds = tr.querySelectorAll('td');
            msg += ` ❌ ${tds[1].innerText}: *${tds[3].innerText}*\n`;
        });
    });

    msg += `\n🔗 [Mở Dashboard Chi Tiết](https://ai-ghn-gxt.up.railway.app/)`;
    return msg;
}

// ---- TELEGRAM BOT MODAL AND CHAT SYSTEM ----
function openTelegramModal() {
    const modal = document.getElementById('telegram-modal');
    const textarea = document.getElementById('telegram-custom-msg');
    if (modal) {
        modal.style.display = 'flex';
    }
    if (textarea) {
        textarea.value = '';
        textarea.focus();
    }
}

function closeTelegramModal() {
    const modal = document.getElementById('telegram-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function sendCustomTelegramMessage() {
    const textarea = document.getElementById('telegram-custom-msg');
    const sendBtn = document.getElementById('telegram-btn-send-custom');
    if (!textarea || !sendBtn) return;

    const message = textarea.value.trim();
    if (!message) {
        alert('⚠️ Vui lòng nhập nội dung tin nhắn!');
        return;
    }

    const originalText = sendBtn.innerHTML;
    sendBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang gửi...';
    sendBtn.disabled = true;

    try {
        const adminKey = sessionStorage.getItem('ghn_admin_key') || '';
        const resp = await fetch('/api/telegram/report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({ message: message, key: adminKey })
        });

        let result = {};
        try {
            result = await resp.json();
        } catch (_) {
            result = { status: 'error', message: `Server trả về HTTP ${resp.status}` };
        }

        if (resp.ok && result.status === 'success') {
            alert('✅ Tin nhắn đã được gửi thành công!');
            closeTelegramModal();
        } else {
            // FastAPI trả về {"detail": "..."}, các error tự viết trả về {"message": "..."}
            const errMsg = result.message || result.detail || `HTTP ${resp.status}`;
            if (resp.status === 401 || resp.status === 403) {
                alert('❌ Không có quyền gửi Telegram.\n\nKiểm tra:\n• Bạn đã truy cập ?key=<ADMIN_KEY> để bật chế độ admin chưa?\n• Admin Key trong Railway Variables có đúng không?');
            } else {
                alert('❌ Lỗi gửi Telegram: ' + errMsg);
            }
        }
    } catch (e) {
        alert('❌ Không thể kết nối với server.\n\nChi tiết: ' + e.message);
    } finally {
        sendBtn.innerHTML = originalText;
        sendBtn.disabled = false;
    }
}


function compileQuickReport() {
    const textarea = document.getElementById('telegram-custom-msg');
    if (textarea) {
        const report = assembleTelegramReport();
        textarea.value = report;
        textarea.focus();
    }
}

// Wire up events
document.getElementById('telegram-btn')?.addEventListener('click', openTelegramModal);
document.getElementById('close-telegram-modal')?.addEventListener('click', closeTelegramModal);
document.getElementById('cancel-telegram-modal')?.addEventListener('click', closeTelegramModal);
window.switchVungChartPeriod = function(period) {
    vungTimeMode = period;
    ['day', 'week', 'month'].forEach(p => {
        const btn = document.getElementById('btn-vung-chart-' + p);
        if (btn) {
            if (p === period) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    });
    
    const dayWrap = document.getElementById('filter-vung-wrap-day');
    const weekWrap = document.getElementById('filter-vung-wrap-week');
    const monthWrap = document.getElementById('filter-vung-wrap-month');
    
    if (dayWrap) dayWrap.style.display = (period === 'day' ? 'flex' : 'none');
    if (weekWrap) weekWrap.style.display = (period === 'week' ? 'flex' : 'none');
    if (monthWrap) monthWrap.style.display = (period === 'month' ? 'flex' : 'none');
    
    renderNangSuatVungSection();
};

function checkHasOldDataForVungFilter() {
    const daySelect = document.getElementById('filter-vung-day');
    const weekSelect = document.getElementById('filter-vung-week');
    const monthSelect = document.getElementById('filter-vung-month');
    
    if (vungTimeMode === 'day' && daySelect && daySelect.value) {
        const ymd = parseDateToYmdSafe(daySelect.value);
        return ymd && ymd <= '2026-06-30';
    }
    if (vungTimeMode === 'week' && weekSelect && weekSelect.value) {
        const weekStr = weekSelect.value;
        const m = weekStr.match(/^(\d{4})-W(\d{2})$/);
        if (m) {
            const year = parseInt(m[1]);
            const week = parseInt(m[2]);
            if (year < 2026) return true;
            if (year === 2026 && week <= 27) return true;
        }
        return false;
    }
    if (vungTimeMode === 'month' && monthSelect && monthSelect.value) {
        const monthStr = monthSelect.value;
        return monthStr && monthStr <= '2026-06';
    }
    return true; 
}

function getAvailableRegionsForPeriod(hasOldData = true) {
    const baseRegions = [...new Set((state.khoGxtData || []).map(r => (r['Vùng'] || r['vung'] || '').trim()).filter(Boolean))];
    if (hasOldData) {
        if (!baseRegions.includes('Miền Trung 05')) {
            baseRegions.push('Miền Trung 05');
        }
    } else {
        return baseRegions.filter(r => r !== 'Miền Trung 05').sort();
    }
    return baseRegions.sort();
}

function populateVungRegionMultiselect() {
    const menu = document.getElementById('menu-vung-region');
    if (!menu) return;
    
    const currentlyChecked = Array.from(menu.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value);
    const hasOldData = checkHasOldDataForVungFilter();
    const regions = getAvailableRegionsForPeriod(hasOldData);
    
    menu.innerHTML = '';
    regions.forEach(r => {
        const item = document.createElement('div');
        item.className = 'ghn-filter-item';
        
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.id = `chk-vung-region-${r}`;
        chk.value = r;
        chk.checked = currentlyChecked.includes(r);
        chk.setAttribute('onchange', `window.updateVungRegionFilter()`);
        
        const lbl = document.createElement('label');
        lbl.htmlFor = chk.id;
        lbl.textContent = r;
        
        item.appendChild(chk);
        item.appendChild(lbl);
        menu.appendChild(item);
    });
    
    selectedVungRegions = selectedVungRegions.filter(r => regions.includes(r));
    const label = document.getElementById('label-vung-region');
    if (label) {
        if (selectedVungRegions.length === 0) {
            label.innerText = 'Chọn Vùng...';
        } else {
            label.innerText = `${selectedVungRegions.length} vùng đã chọn`;
        }
    }
}

window.updateVungRegionFilter = function() {
    const menu = document.getElementById('menu-vung-region');
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    selectedVungRegions = Array.from(checks).map(c => c.value);
    
    const label = document.getElementById('label-vung-region');
    if (label) {
        if (selectedVungRegions.length === 0) {
            label.innerText = 'Chọn Vùng...';
        } else {
            label.innerText = `${selectedVungRegions.length} vùng đã chọn`;
        }
    }
    
    const items = Array.from(menu.querySelectorAll('.ghn-filter-item'));
    items.sort((a, b) => {
        const chkA = a.querySelector('input').checked;
        const chkB = b.querySelector('input').checked;
        return (chkA === chkB) ? 0 : (chkA ? -1 : 1);
    });
    items.forEach(item => menu.appendChild(item));
    
    renderNangSuatVungSection();
};

function populateVungSelects() {
    const daySelect = document.getElementById('filter-vung-day');
    const weekSelect = document.getElementById('filter-vung-week');
    const monthSelect = document.getElementById('filter-vung-month');
    
    if (!daySelect) return;
    
    if (daySelect.options.length <= 1) {
        const days = [...new Set((state.gtcData || []).map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
        days.forEach(d => daySelect.add(new Option(d, d)));
    }
    
    if (weekSelect && weekSelect.options.length <= 1) {
        const weeks = [...new Set((state.gtcData || []).map(r => {
            const ts = parseVN(r['Ngày']);
            return ts ? getWeekNumber(new Date(ts)) : null;
        }).filter(Boolean))].sort((a, b) => b.localeCompare(a));
        weeks.forEach(w => weekSelect.add(new Option('Tuần ' + (w.includes('-W') ? w.split('-W')[1] : w) + ' (' + w.split('-W')[0] + ')', w)));
    }
    
    if (monthSelect && monthSelect.options.length <= 1) {
        const months = [...new Set((state.gtcData || []).map(r => {
            const ts = parseVN(r['Ngày']);
            if (!ts) return null;
            const d = new Date(ts);
            return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
        }).filter(Boolean))].sort((a, b) => b.localeCompare(a));
        months.forEach(m => monthSelect.add(new Option('Tháng ' + m, m)));
    }
    
    populateVungRegionMultiselect();
}

/**
 * Chuyển tab bên trong section GTC & Năng Suất
 * @param {'gtc'|'nangsuat'|'nangsuatvung'} tab
 */
function switchGtcTab(tab) {
    // Ẩn tất cả panels
    document.getElementById('gtc-panel-gtc').style.display = 'none';
    document.getElementById('gtc-panel-nangsuat').style.display = 'none';
    const vungPanel = document.getElementById('gtc-panel-nangsuatvung');
    if (vungPanel) vungPanel.style.display = 'none';
    // Bỏ active khỏi tất cả tab buttons
    document.getElementById('tab-btn-gtc').classList.remove('active');
    document.getElementById('tab-btn-nangsuat').classList.remove('active');
    const vungBtn = document.getElementById('tab-btn-nangsuatvung');
    if (vungBtn) vungBtn.classList.remove('active');
    // Hiển thị panel được chọn + đánh dấu active
    const panelEl = document.getElementById('gtc-panel-' + tab);
    if (panelEl) panelEl.style.display = 'block';
    const btnEl = document.getElementById('tab-btn-' + tab);
    if (btnEl) btnEl.classList.add('active');
    // Khi chuyển sang tab Năng Suất Vùng → render ngay
    if (tab === 'nangsuatvung') renderNangSuatVungSection();
}

function toYYYYMMDD(dateStr) {
    const ts = parseVN(dateStr);
    if (!ts) return '';
    const d = new Date(ts);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}



function getGtcAndGanForPeriod(vung, scope, periodKey) {
    if (!periodKey) return { gtc: 0, gan: 0 };
    const filtered = (state.gtcData || []).filter(r => {
        const rowVung = getRegionByDate(r['Kho'], r['Ngày']);
        if (rowVung !== vung) return false;
        
        const ts = parseVN(r['Ngày']);
        if (!ts) return false;
        const d = new Date(ts);
        
        if (scope === 'day') {
            return r['Ngày'] === periodKey;
        } else if (scope === 'week') {
            return getWeekNumber(d) === periodKey;
        } else if (scope === 'month') {
            const m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            return m === periodKey;
        }
        return false;
    });
    
    let sumGtc = 0;
    let sumGan = 0;
    filtered.forEach(r => {
        const donGtc = parseInt(String(r['Số Đơn GTC'] || r['Số đơn GTC'] || '0').replace(/[^0-9]/g, '')) || 0;
        const donGan = parseInt(String(r['Số đơn gán'] || r['Số Đơn Gán'] || '0').replace(/[^0-9]/g, '')) || 0;
        sumGtc += donGtc;
        sumGan += donGan;
    });
    return { gtc: sumGtc, gan: sumGan };
}

function renderVungGtcChart(renderedEntries) {
    destroyChart('vungGtc');
    const canvas = document.getElementById('chart-gtc-by-vung');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    const labels = renderedEntries.map(([vung]) => vung);
    const values = renderedEntries.map(([, v]) => v.activeRate !== null ? parseFloat(v.activeRate.toFixed(2)) : 0);
    
    const regionColors = {
        'Miền Trung': '#0288d1',
        'Miền Nam': '#e91e63',
        'Miền Bắc 1': '#4caf50',
        'Miền Bắc 2': '#ff9800',
        'Vùng 1': '#0288d1',
        'Vùng 2': '#4caf50',
        'Vùng 3': '#ff9800',
        'Vùng 4': '#e91e63'
    };
    const fallbackColors = ['#0288d1', '#e91e63', '#4caf50', '#ff9800', '#9c27b0', '#009688'];
    const colors = labels.map((l, i) => regionColors[l] || fallbackColors[i % fallbackColors.length]);
    
    charts.vungGtc = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Tỷ lệ GTC (%)',
                data: values,
                backgroundColor: colors,
                borderRadius: 6,
                barPercentage: 0.5,
                maxBarThickness: 50
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Tỷ lệ GTC: ${context.raw}%`;
                        }
                    }
                },
                datalabels: {
                    display: true,
                    anchor: 'end',
                    align: 'top',
                    color: '#333',
                    font: { weight: 'bold', size: 11 },
                    formatter: v => v + '%'
                }
            },
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    ticks: { callback: v => v + '%' }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
    });
}

function renderNangSuatVungSection() {
    const tbody = document.getElementById('tbody-ns-vung');
    if (!tbody) return;

    // Rebuild the multiselect checkboxes dynamic to current date filter
    populateVungRegionMultiselect();

    // Reset filters of other periods to prevent conflicts before reading values
    const daySelect = document.getElementById('filter-vung-day');
    const weekSelect = document.getElementById('filter-vung-week');
    const monthSelect = document.getElementById('filter-vung-month');
    if (daySelect && weekSelect && monthSelect) {
        if (vungTimeMode === 'day') {
            weekSelect.value = '';
            monthSelect.value = '';
        } else if (vungTimeMode === 'week') {
            daySelect.value = '';
            monthSelect.value = '';
        } else if (vungTimeMode === 'month') {
            daySelect.value = '';
            weekSelect.value = '';
        }
    }

    // Điền giá trị vào các dropdown filter
    populateVungSelects();

    // Đọc các giá trị filter đang chọn
    const selDay = daySelect?.value || '';
    const selWeek = weekSelect?.value || '';
    const selMonth = monthSelect?.value || '';

    // --- 2. Xác định các danh sách thời gian có sẵn ---
    const gtcData = state.gtcData || [];
    if (!gtcData.length) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:30px;color:var(--text3)">Chưa có dữ liệu GTC</td></tr>';
        return;
    }
    const allDays = [...new Set(gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    const latestDate = allDays[0];
    if (!latestDate) return;

    const allWeeks = [...new Set(gtcData.map(r => {
        const ts = parseVN(r['Ngày']);
        return ts ? getWeekNumber(new Date(ts)) : null;
    }).filter(Boolean))].sort((a, b) => b.localeCompare(a));

    const allMonths = [...new Set(gtcData.map(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts) return null;
        const d = new Date(ts);
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    }).filter(Boolean))].sort((a, b) => b.localeCompare(a));

    // --- 3. Xác định Kỳ đang hoạt động và Kỳ trước đó ---
    let activePeriod = vungTimeMode;
    let currPeriodKey = '';
    if (activePeriod === 'day') {
        currPeriodKey = selDay || latestDate;
    } else if (activePeriod === 'week') {
        currPeriodKey = selWeek || allWeeks[0] || '';
    } else if (activePeriod === 'month') {
        currPeriodKey = selMonth || allMonths[0] || '';
    }

    let prevPeriodKey = '';
    if (activePeriod === 'day') {
        const currIdx = allDays.indexOf(currPeriodKey);
        if (currIdx !== -1 && currIdx < allDays.length - 1) prevPeriodKey = allDays[currIdx + 1];
    } else if (activePeriod === 'week') {
        const currIdx = allWeeks.indexOf(currPeriodKey);
        if (currIdx !== -1 && currIdx < allWeeks.length - 1) prevPeriodKey = allWeeks[currIdx + 1];
    } else if (activePeriod === 'month') {
        const currIdx = allMonths.indexOf(currPeriodKey);
        if (currIdx !== -1 && currIdx < allMonths.length - 1) prevPeriodKey = allMonths[currIdx + 1];
    }

    // --- 4. Thiết lập các giá trị mốc cho Day, Week, Month hiện tại ---
    let targetDay_YYYYMMDD = '';
    let targetWeek = '';
    let targetMonth = '';

    if (activePeriod === 'day') {
        targetDay_YYYYMMDD = toYYYYMMDD(currPeriodKey);
        const ts = parseVN(currPeriodKey);
        targetWeek = ts ? getWeekNumber(new Date(ts)) : '';
        targetMonth = ts ? new Date(ts).getFullYear() + '-' + String(new Date(ts).getMonth() + 1).padStart(2, '0') : '';
    } else if (activePeriod === 'week') {
        targetWeek = currPeriodKey;
        const daysInWeek = allDays.filter(day => {
            const ts = parseVN(day);
            return ts ? getWeekNumber(new Date(ts)) === currPeriodKey : false;
        });
        const lastDayInWeek = daysInWeek[0] || latestDate;
        targetDay_YYYYMMDD = toYYYYMMDD(lastDayInWeek);
        const ts = parseVN(lastDayInWeek);
        targetMonth = ts ? new Date(ts).getFullYear() + '-' + String(new Date(ts).getMonth() + 1).padStart(2, '0') : '';
    } else if (activePeriod === 'month') {
        targetMonth = currPeriodKey;
        const daysInMonth = allDays.filter(day => {
            const ts = parseVN(day);
            if (!ts) return false;
            const d = new Date(ts);
            const m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            return m === currPeriodKey;
        });
        const lastDayInMonth = daysInMonth[0] || latestDate;
        targetDay_YYYYMMDD = toYYYYMMDD(lastDayInMonth);
        const ts = parseVN(lastDayInMonth);
        targetWeek = ts ? getWeekNumber(new Date(ts)) : '';
    }

    // Khởi tạo vungMap
    const vungMap = {};
    const allRegions = ['Miền Trung 01', 'Miền Trung 02', 'Miền Trung 03', 'Miền Trung 04', 'Miền Trung 05'];
    allRegions.forEach(v => {
        if (!vungMap[v]) {
            vungMap[v] = {
                vung: v,
                khoSet: new Set(),
                totalGtc: 0,
                totalGan: 0,
                totalStaff: 0,
                warehouseGtcMap: {},
                warehouseGanMap: {},
                khoList: [],
                
                // 3 Scopes
                gtc_day: 0, gan_day: 0, rate_day: null,
                gtc_week: 0, gan_week: 0, rate_week: null,
                gtc_month: 0, gan_month: 0, rate_month: null,
                
                activeRate: null
            };
        }
    });

    // --- 5. Tính toán GTC & Gán cho các khoảng thời gian ---
    gtcData.forEach(r => {
        const vung = getRegionByDate(r['Kho'], r['Ngày']);
        const ts = parseVN(r['Ngày']);
        if (!ts) return;
        const d = new Date(ts);
        const donGtc = parseInt(String(r['Số Đơn GTC'] || r['Số đơn GTC'] || '0').replace(/[^0-9]/g, '')) || 0;
        const donGan = parseInt(String(r['Số đơn gán'] || r['Số Đơn Gán'] || '0').replace(/[^0-9]/g, '')) || 0;

        const rowDay = toYYYYMMDD(r['Ngày']);
        const rowWeek = getWeekNumber(d);
        const rowMonth = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');

        if (vungMap[vung]) {
            // Tích lũy cho 3 khoảng thời gian
            if (rowDay === targetDay_YYYYMMDD) {
                vungMap[vung].gtc_day += donGtc;
                vungMap[vung].gan_day += donGan;
            }
            if (rowWeek === targetWeek) {
                vungMap[vung].gtc_week += donGtc;
                vungMap[vung].gan_week += donGan;
            }
            if (rowMonth === targetMonth) {
                vungMap[vung].gtc_month += donGtc;
                vungMap[vung].gan_month += donGan;
            }

            // Kiểm tra khớp với kỳ đang hoạt động
            let matchActive = false;
            if (activePeriod === 'day' && rowDay === targetDay_YYYYMMDD) matchActive = true;
            if (activePeriod === 'week' && rowWeek === currPeriodKey) matchActive = true;
            if (activePeriod === 'month' && rowMonth === currPeriodKey) matchActive = true;

            if (matchActive) {
                vungMap[vung].totalGtc += donGtc;
                vungMap[vung].totalGan += donGan;
                const whName = shortKho(r['Kho']);
                if (!vungMap[vung].warehouseGtcMap[whName]) vungMap[vung].warehouseGtcMap[whName] = 0;
                if (!vungMap[vung].warehouseGanMap[whName]) vungMap[vung].warehouseGanMap[whName] = 0;
                vungMap[vung].warehouseGtcMap[whName] += donGtc;
                vungMap[vung].warehouseGanMap[whName] += donGan;
                vungMap[vung].khoSet.add(whName);
            }
        }
    });

    // --- 6. Tính toán Nhân sự cho kỳ hoạt động ---
    const nsData = state.nangSuatData || [];
    nsData.forEach(r => {
        let vung = getRegionByDate((r['hub_id'] || '').trim(), r['Ngày']);
        if (!vung || vung === 'Chưa xác định') {
            const whFull = (r['kho gxt'] || r['Kho'] || '').trim();
            vung = getRegionByDate(whFull, r['Ngày']);
        }
        
        const ts = parseVN(r['Ngày']);
        if (!ts) return;
        const d = new Date(ts);
        const vol = parseFloat((r['avg_delivery_volume_per_hour'] || '0').toString().replace(',', '.'));
        if (vol <= 0) return;

        const rowDay = toYYYYMMDD(r['Ngày']);
        const rowWeek = getWeekNumber(d);
        const rowMonth = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');

        let matchActive = false;
        if (activePeriod === 'day' && rowDay === targetDay_YYYYMMDD) matchActive = true;
        if (activePeriod === 'week' && rowWeek === currPeriodKey) matchActive = true;
        if (activePeriod === 'month' && rowMonth === currPeriodKey) matchActive = true;

        if (matchActive && vungMap[vung]) {
            vungMap[vung].totalStaff += 1;
            const whShort = shortKho(r['kho gxt'] || r['Kho'] || '');
            if (whShort && whShort !== '--') {
                vungMap[vung].khoSet.add(whShort);
            }
        }
    });

    // --- 7. Tính Tỷ lệ GTC cho từng khoảng và gán activeRate ---
    Object.keys(vungMap).forEach(vung => {
        const v = vungMap[vung];
        v.rate_day   = v.gan_day   > 0 ? (v.gtc_day   / v.gan_day)   * 100 : null;
        v.rate_week  = v.gan_week  > 0 ? (v.gtc_week  / v.gan_week)  * 100 : null;
        v.rate_month = v.gan_month > 0 ? (v.gtc_month / v.gan_month) * 100 : null;

        if (activePeriod === 'day')   v.activeRate = v.rate_day;
        if (activePeriod === 'week')  v.activeRate = v.rate_week;
        if (activePeriod === 'month') v.activeRate = v.rate_month;

        v.khoList = Object.keys(v.warehouseGtcMap).map(whName => {
            const whGtc = v.warehouseGtcMap[whName] || 0;
            const whGan = v.warehouseGanMap[whName] || 0;
            const whRate = whGan > 0 ? (whGtc / whGan) * 100 : 0;
            return { kho: whName, gtc: whGtc, gan: whGan, rate: whRate };
        });
    });

    // Lọc các vùng active có dữ liệu GTC hoặc Gán
    const activeVungEntries = Object.entries(vungMap)
        .filter(([, v]) => v.totalGtc > 0 || v.totalGan > 0)
        .sort((a, b) => b[1].totalGtc - a[1].totalGtc);

    if (!activeVungEntries.length) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:30px;color:var(--text3)">Chưa có dữ liệu GTC cho kỳ được chọn.</td></tr>';
        return;
    }

    // --- 8. Áp dụng bộ lọc vùng đa chọn ---
    let renderedEntries = activeVungEntries;
    if (selectedVungRegions.length > 0) {
        renderedEntries = activeVungEntries.filter(([vung]) => selectedVungRegions.includes(vung));
    }

    if (!renderedEntries.length) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:30px;color:var(--text3)">Không tìm thấy dữ liệu vùng phù hợp với bộ lọc đang chọn.</td></tr>';
        return;
    }

    // --- 9. Vẽ biểu đồ so sánh vùng ---
    renderVungGtcChart(renderedEntries);

    // --- 10. Tính các thẻ Card Tổng quan (dựa trên các vùng hiển thị của kỳ đang chọn) ---
    const rateEntries = renderedEntries.filter(([, v]) => v.activeRate !== null);
    
    // Tỷ lệ GTC trung bình toàn vùng: weighted average
    const sumGtcAll = rateEntries.reduce((s, [, v]) => s + v.totalGtc, 0);
    const sumGanAll = rateEntries.reduce((s, [, v]) => s + v.totalGan, 0);
    const globalAvgRate = sumGanAll > 0 ? (sumGtcAll / sumGanAll) * 100 : null;

    const bestEntry   = rateEntries.length > 0 ? rateEntries.reduce((a, b) => b[1].activeRate > a[1].activeRate ? b : a) : null;
    const worstEntry  = rateEntries.length > 0 ? rateEntries.reduce((a, b) => b[1].activeRate < a[1].activeRate ? b : a) : null;

    const worstVungName = worstEntry ? worstEntry[0] : '';
    const bestVungName = bestEntry ? bestEntry[0] : '';

    const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setEl('ns-vung-total',     renderedEntries.length);
    setEl('ns-vung-best',      bestEntry ? bestEntry[0] : '--');
    setEl('ns-vung-best-val',  bestEntry ? bestEntry[1].activeRate.toFixed(2) + '%' : '--%');
    setEl('ns-vung-worst',     worstEntry ? worstEntry[0] : '--');
    setEl('ns-vung-worst-val', worstEntry ? worstEntry[1].activeRate.toFixed(2) + '%' : '--%');
    setEl('ns-vung-avg',       globalAvgRate !== null ? globalAvgRate.toFixed(2) + '%' : '--%');

    // --- 11. Render bảng dữ liệu ---
    function ratingBadge(rate) {
        if (rate === null || rate === undefined) return '<span style="color:var(--text3);font-size:12px">Chưa đủ dữ liệu</span>';
        if (rate >= 90.0) return '<span class="badge" style="background:#E8F5E9;color:#1B5E20">🟢 Tốt</span>';
        if (rate >= 80.0) return '<span class="badge" style="background:#FFFDE7;color:#F57F17">🟡 Trung bình</span>';
        return '<span class="badge" style="background:#FFEBEE;color:#B71C1C">🔴 Thấp</span>';
    }

    tbody.innerHTML = renderedEntries.map(([vung, v]) => {
        const khosSorted = [...v.khoList].sort((a, b) => b.rate - a.rate);
        const bestKho    = khosSorted[0];
        const worstKho   = khosSorted.length > 1 ? khosSorted[khosSorted.length - 1] : null;

        const rateDayStr   = v.rate_day !== null ? v.rate_day.toFixed(2) + '%' : '<span style="color:var(--text3)">Chưa đủ dữ liệu</span>';
        const rateWeekStr  = v.rate_week !== null ? v.rate_week.toFixed(2) + '%' : '<span style="color:var(--text3)">Chưa đủ dữ liệu</span>';
        const rateMonthStr = v.rate_month !== null ? v.rate_month.toFixed(2) + '%' : '<span style="color:var(--text3)">Chưa đủ dữ liệu</span>';

        const rateCurrent = v.activeRate;
        let evaluation = ratingBadge(rateCurrent);
        let warningText = '--';
        let actionText = '';

        const worstKhoName = worstKho ? worstKho.kho : 'kho thấp nhất';

        if (rateCurrent === null || rateCurrent === undefined) {
            actionText = 'Chưa đủ dữ liệu để đánh giá hành động.';
        } else {
            const isLowestInNetwork = (worstVungName && vung === worstVungName);
            const isHighestInNetwork = (bestVungName && vung === bestVungName);
            
            // Tính toán giảm tỷ lệ GTC so với kỳ trước
            const prevData = getGtcAndGanForPeriod(vung, activePeriod, prevPeriodKey);
            const ratePrevious = prevData.gan > 0 ? (prevData.gtc / prevData.gan) * 100 : null;
            
            let isRateDropped = false;
            let dropDiff = 0;
            if (ratePrevious !== null && rateCurrent < ratePrevious - 1.0) { // Giảm trên 1%
                isRateDropped = true;
                dropDiff = ratePrevious - rateCurrent;
            }

            if (isLowestInNetwork) {
                warningText = `⚠️ Vùng ${vung} có tỷ lệ GTC thấp nhất (${rateCurrent.toFixed(1)}%). Cần theo dõi.`;
            } else if (isRateDropped) {
                warningText = `📉 Hiệu suất giảm so với kỳ trước (-${dropDiff.toFixed(1)}%)`;
            } else if (rateCurrent < 80.0) {
                warningText = `⚠️ Tỷ lệ GTC thấp (<80%)`;
            }

            if (isLowestInNetwork) {
                actionText = `🚨 Vùng thấp nhất toàn mạng. Cần khẩn trương rà soát kho ${worstKhoName}, kiểm tra backlog, nhân sự giao nhận, điều phối đội xe GXT và năng lực giao hàng.`;
            } else if (isHighestInNetwork || rateCurrent >= 90.0) {
                actionText = `✅ Hiệu suất tốt. Duy trì tỷ lệ GTC hiện tại, rà soát kho ${worstKhoName} để chủ động phòng ngừa rủi ro backlog.`;
            } else if (rateCurrent >= 80.0) {
                actionText = `🟡 Hiệu suất trung bình. Cần rà soát kho ${worstKhoName}, kiểm tra backlog tồn đọng, tình trạng xe và khả năng giao.`;
            } else {
                actionText = `🔴 Hiệu suất thấp. Cần tập trung cải thiện kho ${worstKhoName}, giải phóng backlog, bổ sung nhân sự, điều phối xe và nâng cao năng lực giao hàng.`;
            }
        }

        const staffStr = v.totalStaff > 0 ? v.totalStaff.toLocaleString('vi-VN') : '<span style="color:var(--text3)">--</span>';
        
        let rowStyle = '';
        if (rateCurrent !== null) {
            if (bestVungName && vung === bestVungName) {
                rowStyle = 'background-color: rgba(232, 245, 233, 0.4);';
            } else if (worstVungName && vung === worstVungName) {
                rowStyle = 'background-color: rgba(254, 242, 242, 0.6);';
            }
        }

        const warningDisp = warningText !== '--' ? `<span style="font-weight:600;color:var(--red);font-size:11px;">${escapeHtml(warningText)}</span>` : '<span style="color:var(--text3)">--</span>';

        return `<tr style="${rowStyle}">
            <td style="font-weight:700;color:var(--blue)">${escapeHtml(vung)}</td>
            <td style="text-align:right">${v.khoSet.size}</td>
            <td style="text-align:right;font-weight:600">${v.totalGtc.toLocaleString('vi-VN')}</td>
            <td style="text-align:right">${staffStr}</td>
            <td style="text-align:right;font-weight:600">${rateDayStr}</td>
            <td style="text-align:right;font-weight:600">${rateWeekStr}</td>
            <td style="text-align:right;font-weight:600">${rateMonthStr}</td>
            <td style="color:var(--green);font-weight:600">${escapeHtml(bestKho ? bestKho.kho : '--')}<br><small style="color:var(--text3);font-weight:400">${bestKho ? bestKho.rate.toFixed(1) + '%' : ''}</small></td>
            <td style="color:var(--red)">${escapeHtml(worstKho ? worstKho.kho : '--')}<br><small style="color:var(--text3);font-weight:400">${worstKho ? worstKho.rate.toFixed(1) + '%' : ''}</small></td>
            <td style="text-align:center">${evaluation}</td>
            <td style="font-size:11px;max-width:200px;white-space:normal;word-break:break-word;">${warningDisp}</td>
            <td style="font-size:11px;max-width:240px;white-space:normal;word-break:break-word;font-weight:500;">${actionText}</td>
        </tr>`;
    }).join('');
}


function switchKhoXeTab(tab) {
    ['khogxt', 'xegxt', 'xesuco'].forEach(t => {
        document.getElementById('khoxe-panel-' + t).style.display = 'none';
        document.getElementById('khoxe-tab-btn-' + t).classList.remove('active');
    });
    document.getElementById('khoxe-panel-' + tab).style.display = 'block';
    document.getElementById('khoxe-tab-btn-' + tab).classList.add('active');
}

/**
 * Chuyển tab bên trong section Cảnh Báo Rủi Ro
 * @param {'warnings'|'forecast'|'overload'|'dontao'} tab
 */
function switchCbrTab(tab) {
    ['warnings', 'forecast', 'overload', 'dontao'].forEach(t => {
        document.getElementById('cbr-panel-' + t).style.display = 'none';
        document.getElementById('cbr-tab-btn-' + t).classList.remove('active');
    });
    document.getElementById('cbr-panel-' + tab).style.display = 'block';
    document.getElementById('cbr-tab-btn-' + tab).classList.add('active');
}

// ---- NAVIGATION ----
const SECTION_META = {
    'login-logs':   ['Log Đăng Nhập',            'Nhật ký đăng nhập hệ thống của nhân viên vận hành'],
    overview:       ['Báo Cáo Tổng Quan',      'Giám sát GTC, Ontime, Backlog và B2B toàn mạng Miền Trung'],
    cbr:            ['Cảnh Báo Rủi Ro',         'Tình trạng cảnh báo hiện tại và dự báo rủi ro vận hành'],
    warnings:       ['Cảnh Báo Rủi Ro',         'Tab Tình Trạng Hiện Tại'],
    forecast:       ['Cảnh Báo Rủi Ro',         'Tab Dự Báo Rủi Ro'],
    gtc:            ['GTC và Năng Suất',       'Theo dõi tỷ lệ giao thành công và năng suất nhân viên'],
    backlog:        ['Backlog > 7 Ngày',         'Đơn hàng tồn lâu trên 7 ngày cần ưu tiên xử lý'],
    b2b:            ['B2B & SLA',               'Theo dõi đơn B2B ưu tiên và cam kết SLA với đối tác'],
    returns:        ['Trả Hàng & FD',            'Phân tích lý do trả hàng và freeship đảo hàng'],
    personnel:      ['Nhân Sự',                  'Danh sách nhân viên và thông tin phân công'],
    nangsuat:       ['GTC và Năng Suất',       'Tab Năng Suất NV'],
    nangsuatvung:   ['GTC và Năng Suất',       'Tab Năng Suất Vùng'],
    khoxe:          ['Kho và Xe GXT',           'Danh sách kho, xe và xe sự cố GXT'],
    xegxt:          ['Kho và Xe GXT',           'Tab Xe GXT'],
    xesuco:         ['Kho và Xe GXT',           'Tab Xe Sự Cố'],
    khogxt:         ['Kho và Xe GXT',           'Tab Kho GXT'],
    dontao:         ['Đơn Tạo N-1',             'Thống kê đơn hàng tạo trong ngày N-1 theo từng kho'],
    'gtc-b2b-prio': ['GTC đơn B2B Ưu Tiên',     'Theo dõi tỷ lệ GTC đơn B2B ưu tiên theo vùng/kho và xử lý đơn lỗi'],
    'b2b-map':      ['Bản Đồ B2B Miền Trung',   'Bản đồ vị trí và thông tin chi tiết các kho Giao Hàng Nặng Miền Trung'],
    'xe-daily':     ['Xe Vận Hành Daily',        'Ghi nhận xe tăng cường và xe không hoạt động hằng ngày'],
};


function showSection(name) {
    // Alias: nangsuat → gtc + tab nangsuat
    if (name === 'nangsuat') {
        showSection('gtc');
        switchGtcTab('nangsuat');
        return;
    }
    // Alias: xegxt / xesuco / khogxt → khoxe + đúng tab
    if (name === 'xegxt' || name === 'xesuco' || name === 'khogxt') {
        showSection('khoxe');
        switchKhoXeTab(name);
        return;
    }
    // Mặc định khi vào gtc → reset tab về GTC
    if (name === 'gtc') switchGtcTab('gtc');
    // Mặc định khi vào khoxe → reset tab về Kho GXT
    if (name === 'khoxe') switchKhoXeTab('khogxt');
    
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const sectionEl = document.getElementById('section-' + name);
    const navEl = document.getElementById('nav-' + name);
    if (sectionEl) sectionEl.classList.add('active');
    if (navEl) navEl.classList.add('active');
    
    if (name === 'gtc-b2b-prio') window.switchGtcB2bPrioTab('vung');
    const [title, sub] = SECTION_META[name] || ['--', '--'];
    document.getElementById('page-title').textContent = title;
    document.getElementById('page-subtitle').textContent = sub;
    
    // Tự động kiểm tra và lazy load data cho section này
    if (name === 'xe-daily') {
        renderXeDailySection();
    } else if (name === 'login-logs') {
        loadLoginLogs();
    } else {
        ensureSectionData(name);
    }
}

// ---- EVENT LISTENERS ----
document.querySelectorAll('.nav-item[data-section]').forEach(item => {
    item.addEventListener('click', e => { e.preventDefault(); showSection(item.dataset.section); });
});

document.querySelectorAll('.view-all[data-section]').forEach(link => {
    link.addEventListener('click', e => { e.preventDefault(); showSection(e.currentTarget.dataset.section); });
});

document.getElementById('refresh-btn').addEventListener('click', async () => {
    const activeSectionEl = document.querySelector('.section.active');
    const activeName = activeSectionEl ? activeSectionEl.id.replace('section-', '') : 'overview';
    
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('loading');
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang tải...';
    
    try {
        if (activeName === 'xe-daily') {
            if (typeof window.loadXeDailyRecords === 'function') await window.loadXeDailyRecords();
        } else if (activeName === 'login-logs') {
            if (typeof window.loadLoginLogs === 'function') await window.loadLoginLogs();
        } else {
            await ensureSectionData(activeName, true);
        }
    } catch (e) {
        console.error('[REFRESH ERROR]', e);
    } finally {
        btn.classList.remove('loading');
        btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Làm mới';
    }
});

document.getElementById('sidebar-toggle').addEventListener('click', () => {
    const sb = document.getElementById('sidebar');
    sb.style.width = sb.style.width === '56px' ? '240px' : '56px';
});

// Theme Toggle Logic
const themeToggleBtn = document.getElementById('theme-toggle-btn');
if (themeToggleBtn) {
    const themeToggleIcon = document.getElementById('theme-toggle-icon');
    const isLight = document.documentElement.classList.contains('light-mode');
    if (themeToggleIcon) {
        themeToggleIcon.className = isLight ? 'fa-solid fa-moon' : 'fa-solid fa-sun';
    }

    themeToggleBtn.addEventListener('click', () => {
        const isCurrentLight = document.documentElement.classList.toggle('light-mode');
        const theme = isCurrentLight ? 'light' : 'dark';
        localStorage.setItem('ghn_theme', theme);
        
        if (themeToggleIcon) {
            themeToggleIcon.className = isCurrentLight ? 'fa-solid fa-moon' : 'fa-solid fa-sun';
        }
        
        updateChartTheme(theme);
    });
}

function updateChartTheme(theme) {
    const isLight = theme === 'light';
    const textColor = isLight ? '#4B5563' : '#9CA3AF';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.08)';

    Chart.defaults.color = textColor;
    Chart.defaults.borderColor = gridColor;

    if (Chart.defaults.plugins && Chart.defaults.plugins.legend && Chart.defaults.plugins.legend.labels) {
        Chart.defaults.plugins.legend.labels.color = textColor;
    }
    if (!Chart.defaults.scale) Chart.defaults.scale = {};
    if (!Chart.defaults.scale.grid) Chart.defaults.scale.grid = {};
    Chart.defaults.scale.grid.color = gridColor;
    if (!Chart.defaults.scale.ticks) Chart.defaults.scale.ticks = {};
    Chart.defaults.scale.ticks.color = textColor;

    Object.values(charts).forEach(chart => {
        if (!chart) return;
        
        if (chart.options.scales) {
            Object.values(chart.options.scales).forEach(scale => {
                if (scale.grid) {
                    scale.grid.color = gridColor;
                }
                if (scale.ticks) {
                    scale.ticks.color = textColor;
                }
            });
        }
        
        if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
            chart.options.plugins.legend.labels.color = textColor;
        }

        chart.update();
    });
}

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

window.switchNsPeriod = function (period, btnId) {
    document.querySelectorAll('#section-nangsuat .filter-tabs button').forEach(b => {
        b.classList.remove('active');
        b.style.cssText = '';
    });
    const btn = document.getElementById(btnId || ('btn-ns-' + period));
    if (btn) {
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
    // NOTE: Admin key không được hardcode ở đây.
    // Để bật admin mode: truy cập ?key=<ADMIN_KEY> (lấy từ biến Railway ADMIN_KEY)
    // Key sẽ được lưu vào localStorage để dùng cho các request sau
    if (urlKey) {
        // [SEC] Dùng sessionStorage thay vì localStorage:
        // - sessionStorage tự xóa khi đóng tab/trình duyệt
        // - An toàn hơn localStorage (không tồn tại vĩnh viễn)
        sessionStorage.setItem('ghn_admin_key', urlKey);
        // Xóa key cũ trong localStorage nếu có
        localStorage.removeItem('ghn_admin_key');
        // Xóa key khỏi URL sau khi lưu
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // [SEC] Ưu tiên sessionStorage; fallback localStorage (backward-compat)
    const savedKey = sessionStorage.getItem('ghn_admin_key')
                  || localStorage.getItem('ghn_admin_key') || '';
    // Nếu còn trong localStorage (cũ), migrate sang sessionStorage rồi xóa
    if (!sessionStorage.getItem('ghn_admin_key') && localStorage.getItem('ghn_admin_key')) {
        sessionStorage.setItem('ghn_admin_key', localStorage.getItem('ghn_admin_key'));
        localStorage.removeItem('ghn_admin_key');
    }
    const telegramBtn = document.getElementById('telegram-btn');
    const loginLogsBtn = document.getElementById('nav-login-logs');

    const ADMIN_KEY_REQUIRED = 'JnBjZUODMXhy7BCupcB5IMPwYOJfHuDkm1-OKR9Jklc';
    const isAdmin = savedKey === ADMIN_KEY_REQUIRED;

    if (telegramBtn) {
        // Hiển thị nút Telegram nếu có admin key hợp lệ (kiểm tra ở backend khi gửi)
        if (savedKey) {
            telegramBtn.style.display = 'flex';
        } else {
            telegramBtn.style.display = 'none';
        }
    }

    if (loginLogsBtn) {
        if (isAdmin) {
            loginLogsBtn.style.display = 'flex';
        } else {
            loginLogsBtn.style.display = 'none';
        }
    }
}


// ---- ĐƠN TẠO N-1 SECTION ----
let dtTimeMode = 'day';
let selectedDtVals = [];
let selectedDtKhos = [];
let dtFiltersInit = false;

window.updateDtTimeMode = function (mode) {
    const menu = document.getElementById('menu-dt-' + mode);
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const vals = Array.from(checks).map(c => c.value);

    if (mode === 'kho') {
        selectedDtKhos = vals;
    } else {
        dtTimeMode = mode;
        selectedDtVals = vals;
        if (mode === 'day') clearDtOtherModes(['week', 'month']);
        else if (mode === 'week') clearDtOtherModes(['day', 'month']);
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
}

function updateDtLabel(mode) {
    const menu = document.getElementById('menu-dt-' + mode);
    if (!menu) return;
    const checks = menu.querySelectorAll('input[type="checkbox"]:checked');
    const label = document.querySelector(`#multi-dt-${mode} .ghn-filter-selected`);
    if (!label) return;
    if (checks.length === 0) {
        const map = { day: 'Chọn Ngày...', week: 'Chọn Tuần...', month: 'Chọn Tháng...', kho: 'Chọn Kho...' };
        label.innerText = map[mode] || '...';
    } else {
        label.innerText = `${checks.length} mục đã chọn`;
    }
    const items = Array.from(menu.querySelectorAll('.ghn-filter-item'));
    items.sort((a, b) => { const ca = a.querySelector('input').checked, cb = b.querySelector('input').checked; return ca === cb ? 0 : ca ? -1 : 1; });
    items.forEach(item => menu.appendChild(item));
}

function renderDtMultiItems(mode, values) {
    const menu = document.getElementById('menu-dt-' + mode);
    if (!menu) return;
    menu.innerHTML = '';
    values.forEach(v => {
        const item = document.createElement('div');
        item.className = 'ghn-filter-item';
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.id = `chk-dt-${mode}-${v.replace(/[^a-z0-9]/gi, '-')}`;
        chk.value = v;  // DOM property, không cần escape
        chk.setAttribute('onchange', `updateDtTimeMode('${mode}')`);
        const lbl = document.createElement('label');
        lbl.htmlFor = chk.id;
        lbl.textContent = mode === 'day' ? v : mode === 'week' ? 'Tuần ' + v : mode === 'month' ? 'Tháng ' + v : v;
        item.appendChild(chk);
        item.appendChild(lbl);
        menu.appendChild(item);
    });
}

function populateDtSelects() {
    const dayMenu = document.getElementById('menu-dt-day');
    if (!dayMenu || dayMenu.children.length > 0) return;

    const allData = state.donTaoData;
    const days = [...new Set(allData.map(r => (r['Thời gian'] || r['time_view'] || '').split(' - ')[0]).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    renderDtMultiItems('day', days);

    const weeks = [...new Set(allData.map(r => {
        const dStr = (r['Thời gian'] || r['time_view'] || '').split(' - ')[0];
        if (!dStr) return null;
        const d = new Date(dStr);
        return isNaN(d) ? null : String(getWeekNumber(d));
    }).filter(Boolean))].sort((a, b) => parseInt(b) - parseInt(a));
    renderDtMultiItems('week', weeks);

    const months = [...new Set(allData.map(r => {
        const dStr = (r['Thời gian'] || r['time_view'] || '').split(' - ')[0];
        if (!dStr) return null;
        const d = new Date(dStr);
        if (isNaN(d)) return null;
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    }).filter(Boolean))].sort().reverse();
    renderDtMultiItems('month', months);

    const khos = [...new Set(allData.map(r => shortKho(r['Kho giao'] || r['kho_giao'] || '')).filter(Boolean))].sort();
    renderDtMultiItems('kho', khos);

    // Auto-select latest day
    if (days.length > 0) {
        const safeId = days[0].replace(/[^a-z0-9]/gi, '-');
        const firstChk = document.getElementById('chk-dt-day-' + safeId);
        if (firstChk) firstChk.checked = true;
        selectedDtVals = [days[0]];
        updateDtLabel('day');
    }

    // Attach search filter
    if (!dtFiltersInit) {
        const searchEl = document.getElementById('filter-kho-dontao');
        if (searchEl) searchEl.addEventListener('input', () => renderDonTaoSection());
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
            const fullT = r['Thời gian'] || r['time_view'] || '';
            const dateStr = fullT.split(' - ')[0];
            const d = new Date(dateStr);
            if (dtTimeMode === 'day') return selectedDtVals.includes(dateStr);
            if (dtTimeMode === 'week') return selectedDtVals.includes(String(getWeekNumber(d)));
            if (dtTimeMode === 'month') {
                if (isNaN(d)) return false;
                const m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
                return selectedDtVals.includes(m);
            }
            return true;
        });
    }

    // Kho multi-select
    if (selectedDtKhos.length > 0) {
        data = data.filter(r => selectedDtKhos.includes(shortKho(r['Kho giao'] || r['kho_giao'] || '')));
    }

    // Text search
    if (searchVal) {
        data = data.filter(r => shortKho(r['Kho giao'] || r['kho_giao'] || '').toLowerCase().includes(searchVal));
    }

    // Aggregate by kho (for chart)
    const khoMap = {};
    let totalDonChart = 0;
    let totalKgChart = 0;

    data.forEach(r => {
        const k = shortKho(r['Kho giao'] || r['kho_giao'] || '--');
        if (!khoMap[k]) khoMap[k] = { don: 0, kg: 0 };

        const dVal = parseInt(String(r['Tổng đơn tạo'] || '0').replace(/\./g, '').replace(/,/g, '')) || 0;
        const kgVal = parseFloat(String(r['Tổng khối lượng (KG)'] || '0').replace(/,/g, '.')) || 0;

        khoMap[k].don += dVal;
        khoMap[k].kg += kgVal;

        totalDonChart += dVal;
        totalKgChart += kgVal;
    });

    // Sort descending by number of orders (largest left)
    const khoEntries = Object.entries(khoMap).sort((a, b) => b[1].don - a[1].don);
    const khoNames = khoEntries.map(e => e[0]);
    const donVals = khoEntries.map(e => e[1].don);
    const kgVals = khoEntries.map(e => Math.round(e[1].kg));

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
                        label: `Tổng Đơn Tạo: ${totalDonChart.toLocaleString('vi-VN')}`, data: donVals,
                        backgroundColor: 'rgba(239, 68, 68, 0.75)', borderColor: C_RED, borderWidth: 1,
                        yAxisID: 'y',
                        datalabels: { display: true, anchor: 'end', align: 'end', color: C_RED, font: { size: 9, weight: 'bold' }, formatter: v => v.toLocaleString('vi-VN') }
                    },
                    {
                        label: `Tổng KG: ${totalKgChart.toLocaleString('vi-VN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}`, data: kgVals,
                        backgroundColor: 'rgba(251,192,45,0.75)', borderColor: '#FBC02D', borderWidth: 1,
                        yAxisID: 'y1',
                        datalabels: { display: true, anchor: 'end', align: 'end', color: '#FBC02D', font: { size: 9 }, formatter: v => v.toLocaleString('vi-VN') }
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { padding: 12, font: { size: 11, weight: 'bold' }, boxWidth: 12 } },
                    datalabels: { display: true }
                },
                scales: {
                    x: { ticks: { maxRotation: 45, font: { size: 10 } }, grid: { display: false } },
                    y: { type: 'linear', position: 'left', beginAtZero: true, grid: { borderDash: [2, 4] }, ticks: { color: C_RED, font: { size: 10 } }, title: { display: true, text: 'Tổng Đơn', color: C_RED, font: { size: 11 } } },
                    y1: { type: 'linear', position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, ticks: { color: '#FBC02D', font: { size: 10 } }, title: { display: true, text: 'Tổng KG', color: '#FBC02D', font: { size: 11 } } }
                }
            }
        });
    }

    // Table rendering logic — aggregated for week/month, granular for day
    const tbody = document.getElementById('tbody-dontao');
    if (!tbody) return;
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#999">Không có dữ liệu</td></tr>';
        return;
    }

    if (selectedDtVals.length > 0 && (dtTimeMode === 'week' || dtTimeMode === 'month')) {
        const tableMap = {};

        data.forEach(r => {
            const fullK = r['Kho giao'] || r['kho_giao'] || '--';
            const kKey = shortKho(fullK);
            const fullT = r['Thời gian'] || r['time_view'] || '';
            const dateStr = fullT.split(' - ')[0];
            const d = new Date(dateStr);

            let tKey = '';
            let tLabel = '';
            if (dtTimeMode === 'week') {
                const w = String(getWeekNumber(d));
                tKey = 'W_' + w;
                tLabel = 'Tuần ' + w;
            } else {
                if (isNaN(d)) return;
                const m = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
                tKey = 'M_' + m;
                tLabel = 'Tháng ' + m;
            }

            const compKey = kKey + '###' + tKey;
            if (!tableMap[compKey]) {
                tableMap[compKey] = { khoName: fullK, tLabel: tLabel, sortTime: tKey, don: 0, kg: 0 };
            }

            const donVal = parseInt(String(r['Tổng đơn tạo'] || '0').replace(/\./g, '').replace(/,/g, '')) || 0;
            const kgVal = parseFloat(String(r['Tổng khối lượng (KG)'] || '0').replace(/,/g, '.')) || 0;

            tableMap[compKey].don += donVal;
            tableMap[compKey].kg += kgVal;
        });

        const sortedGroup = Object.values(tableMap).sort((a, b) => {
            if (b.sortTime !== a.sortTime) return b.sortTime.localeCompare(a.sortTime);
            return b.don - a.don;
        });

        tbody.innerHTML = sortedGroup.map((g, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${escapeHtml(shortKho(g.khoName))}</td>
                <td style="font-weight:600;color:var(--blue)">${escapeHtml(g.tLabel)}</td>
                <td style="text-align:right;font-weight:600;color:#7B1FA2">${g.don.toLocaleString('vi-VN')}</td>
                <td style="text-align:right;font-weight:600;color:#0288D1">${g.kg.toLocaleString('vi-VN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}</td>
            </tr>
        `).join('');
    } else {
        const sorted = [...data].sort((a, b) => {
            const da = (a['Thời gian'] || a['time_view'] || '').split(' - ')[0];
            const db = (b['Thời gian'] || b['time_view'] || '').split(' - ')[0];
            if (db !== da) return db.localeCompare(da);
            const va = parseInt(String(a['Tổng đơn tạo'] || '0').replace(/[.,]/g, '')) || 0;
            const vb = parseInt(String(b['Tổng đơn tạo'] || '0').replace(/[.,]/g, '')) || 0;
            return vb - va;
        });

        tbody.innerHTML = sorted.map((r, i) => {
            const don = parseInt(String(r['Tổng đơn tạo'] || '0').replace(/\./g, '').replace(/,/g, '')) || 0;
            const kg = parseFloat(String(r['Tổng khối lượng (KG)'] || '0').replace(/,/g, '.')) || 0;
            const tStr = r['Thời gian'] || r['time_view'] || '--';

            return `<tr>
                <td>${i + 1}</td>
                <td>${escapeHtml(shortKho(r['Kho giao'] || r['kho_giao'] || '--'))}</td>
                <td>${escapeHtml(tStr)}</td>
                <td style="text-align:right;font-weight:600;color:#7B1FA2">${don.toLocaleString('vi-VN')}</td>
                <td style="text-align:right;font-weight:600;color:#0288D1">${kg.toLocaleString('vi-VN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}</td>
            </tr>`;
        }).join('');
    }
}

// ---- FORECAST / DỰ BÁO RỦI RO THEO KHO ----
function buildForecastData() {
    const now = Date.now();
    const cutoff7d = now - 7 * 86400000;

    // --- Bước 1: Lấy danh sách tất cả kho từ GTC data ---
    const khoSet = new Set();
    state.gtcData.forEach(r => { const k = shortKho(r['Kho']); if (k && k !== '--') khoSet.add(k); });

    // --- Bước 2: Tính GTC theo kho 7 ngày gần nhất ---
    const gtcByKho = {}; // { khoName: { days: [{date, pct, gan, gtc}], latest: pct, avg7d: pct, max7d: pct, maxGtcDon: số } }
    state.gtcData.forEach(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts || ts < cutoff7d) return;
        const kho = shortKho(r['Kho']);
        if (!kho) return;
        if (!gtcByKho[kho]) gtcByKho[kho] = { days: [] };
        gtcByKho[kho].days.push({ ts, pct: parsePct(r['% GTC']), gan: parseInt(r['Số đơn gán'] || 0), gtc: parseInt(r['Số đơn GTC'] || 0) });
    });

    // Tìm ngày mới nhất toàn mạng
    const allDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    const latestDate = allDates[0] || '';

    // Lấy đơn tạo N-1 theo kho (ngày mới nhất trong donTaoData) — dùng cho cảnh báo tồn hàng
    const donTaoN1ByKho = {};
    if (state.donTaoData && state.donTaoData.length) {
        const allDonDates = [...new Set(state.donTaoData.map(r =>
            (r['Thời gian'] || r['time_view'] || '').split(' - ')[0]
        ).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
        const latestDonDate = allDonDates[0];
        state.donTaoData.forEach(r => {
            const dStr = (r['Thời gian'] || r['time_view'] || '').split(' - ')[0];
            if (dStr !== latestDonDate) return;
            const kho = shortKho(r['Kho giao'] || r['kho_giao'] || '');
            if (!kho || kho === '--') return;
            const don = parseInt(String(r['Tổng đơn tạo'] || '0').replace(/\./g, '').replace(/,/g, '')) || 0;
            donTaoN1ByKho[kho] = (donTaoN1ByKho[kho] || 0) + don;
        });
    }

    Object.keys(gtcByKho).forEach(kho => {
        const days = gtcByKho[kho].days.sort((a, b) => b.ts - a.ts);
        const latest = days[0];
        const pcts = days.map(d => d.pct).filter(p => p > 0);
        const avg7d = pcts.length ? (pcts.reduce((a, b) => a + b, 0) / pcts.length) : 0;
        const max7d = pcts.length ? Math.max(...pcts) : 0;
        // Xu hướng: so sánh GTC ngày mới nhất vs TB 7 ngày
        const trend = latest ? (latest.pct - avg7d) : 0;
        // Tính lại GTC N-1 từ raw data
        const latestRow = state.gtcData.find(r => shortKho(r['Kho']) === kho && r['Ngày'] === latestDate);
        const gtcN1 = latestRow ? parsePct(latestRow['% GTC']) : (latest ? latest.pct : 0);
        // Số đơn GTC thực tế cao nhất trong 1 ngày (max GTC đơn/ngày tuần này)
        const gtcDons = days.map(d => d.gtc).filter(g => g > 0);
        const maxGtcDon = gtcDons.length ? Math.max(...gtcDons) : 0;

        gtcByKho[kho].latest = gtcN1;
        gtcByKho[kho].avg7d = avg7d;
        gtcByKho[kho].max7d = max7d;
        gtcByKho[kho].trend = trend;
        gtcByKho[kho].maxGtcDon = maxGtcDon;
        gtcByKho[kho].donTaoN1 = donTaoN1ByKho[kho] || 0;
    });

    // --- Bước 3: Tính backlog theo kho ---
    const backlogByKho = {}; // { kho: { lm, ktc } }
    state.warningsData.forEach(r => {
        const kho = shortKho(r['kho gxt'] || r['Kho'] || '');
        if (!kho || kho === '--') return;
        const lm = parseInt(r['backlog last mile'] || r['backlog lastmile'] || 0);
        const ktc = parseInt(r['backlog ktc'] || 0);
        backlogByKho[kho] = { lm, ktc };
    });

    // --- Bước 4: Trạng thái cảnh báo hiện tại ---
    const warnStatusByKho = {};
    state.warningsData.forEach(r => {
        const kho = shortKho(r['kho gxt'] || r['Kho'] || '');
        if (!kho || kho === '--') return;
        const soNgay = parseFloat(r['Số ngày trở về ngày thường'] || r['Total ngày'] || 0);
        const status = r['Tình hình hiện tại'] || 'Bình thường';
        warnStatusByKho[kho] = { soNgay, status };
    });

    // --- Bước 5: Năng suất trung bình 7 ngày theo kho ---
    const nsAvgByKho = {};
    state.nangSuatData.forEach(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts || ts < cutoff7d) return;
        const prov = r['to_province_name'] || '';
        if (!prov) return;
        if (!nsAvgByKho[prov]) nsAvgByKho[prov] = { sumPct: 0, count: 0, sumVol: 0 };
        const vol = parseInt(r['volume'] || 0);
        const pct = parsePct(r['Tỉ lệ GTC']);
        nsAvgByKho[prov].sumPct += pct;
        nsAvgByKho[prov].count += 1;
        nsAvgByKho[prov].sumVol += vol;
    });

    // --- Bước 6: Tổng hợp & tính điểm rủi ro ---
    const results = [];
    khoSet.forEach(kho => {
        const gtc = gtcByKho[kho] || { latest: 0, avg7d: 0, max7d: 0, trend: 0 };
        const bl = backlogByKho[kho] || { lm: 0, ktc: 0 };
        const ws = warnStatusByKho[kho] || { soNgay: 0, status: 'Bình thường' };

        let score = 0;
        const alerts = [];
        const recommendations = [];

        // --- Tính điểm từ GTC N-1 ---
        if (gtc.latest < 82 && gtc.latest > 0) {
            score += 40;
            alerts.push(`GTC N-1 thấp (${gtc.latest.toFixed(1)}%)`);
            recommendations.push('Tăng cường giám sát tuyến giao, kiểm tra lý do thất bại');
        } else if (gtc.latest < 87 && gtc.latest > 0) {
            score += 20;
            alerts.push(`GTC N-1 chưa đạt (${gtc.latest.toFixed(1)}%)`);
            recommendations.push('Rà soát NV có GTC thấp, hỗ trợ kỹ thuật giao nhận');
        }

        // --- Xu hướng GTC giảm ---
        if (gtc.trend < -3) {
            score += 25;
            alerts.push(`GTC đang giảm ${Math.abs(gtc.trend).toFixed(1)}% so với TB tuần`);
            recommendations.push('Điều tra nguyên nhân sụt giảm GTC trong 2-3 ngày gần đây');
        } else if (gtc.trend < -1) {
            score += 10;
            alerts.push(`GTC có xu hướng giảm nhẹ`);
        }

        // --- Backlog Last Mile ---
        if (bl.lm > 1000) {
            score += 30;
            alerts.push(`Backlog LM nghiêm trọng (${bl.lm.toLocaleString()})`);
            recommendations.push('Tăng ca giao, bổ sung NV hỗ trợ kho, liên hệ điều phối khu vực');
        } else if (bl.lm > 500) {
            score += 20;
            alerts.push(`Backlog LM cao (${bl.lm.toLocaleString()})`);
            recommendations.push('Ưu tiên xử lý đơn tồn lâu, phân phối lại tuyến giao');
        } else if (bl.lm > 200) {
            score += 8;
            alerts.push(`Backlog LM ở mức trung bình`);
        }

        // --- Backlog KTC ---
        if (bl.ktc > 500) {
            score += 25;
            alerts.push(`Backlog KTC rất cao (${bl.ktc.toLocaleString()})`);
            recommendations.push('Kết hợp kho phụ, đẩy nhanh xử lý KTC tồn đọng');
        } else if (bl.ktc > 200) {
            score += 15;
            alerts.push(`Backlog KTC cao (${bl.ktc.toLocaleString()})`);
            recommendations.push('Kiểm tra năng lực xử lý KTC, điều chỉnh lịch giao nhận');
        }

        // --- Cảnh báo từ sheet ---
        if (ws.status === 'Nghiêm trọng' || ws.soNgay > 6) {
            score += 30;
            alerts.push(`Đang ở trạng thái: ${ws.status} (${ws.soNgay}n)`);
            recommendations.push('Báo cáo quản lý khu vực, lập kế hoạch phục hồi gấp');
        } else if (ws.status === 'Bất ổn' || ws.status === 'Cảnh báo') {
            score += 15;
            alerts.push(`Trạng thái hiện tại: ${ws.status}`);
            recommendations.push('Theo dõi chặt chẽ hàng ngày, chuẩn bị phương án dự phòng');
        }

        // --- GTC TB 7 ngày quá thấp dù N-1 ổn ---
        if (gtc.avg7d > 0 && gtc.avg7d < 85) {
            score += 10;
            if (!alerts.some(a => a.includes('GTC'))) alerts.push(`GTC TB 7N thấp (${gtc.avg7d.toFixed(1)}%)`);
        }

        // --- Đơn Tạo N-1 vượt quá GTC Max 1 ngày × 1.5 → nguy cơ tồn hàng ---
        const maxGtcDon = gtc.maxGtcDon || 0;
        const donTaoN1kho = gtc.donTaoN1 || 0;
        if (maxGtcDon > 0 && donTaoN1kho > 0 && donTaoN1kho > maxGtcDon * 1.5) {
            const ratio = (donTaoN1kho / maxGtcDon).toFixed(1);
            score += 35;
            alerts.push(`⚠️ Hàng tạo cao gấp ${ratio}x đơn GTC. Nguy cơ tồn hàng cao`);
            recommendations.unshift(`🚛 Hàng tạo (${donTaoN1kho.toLocaleString()}) cao gấp ${ratio}x GTC max ngày (${maxGtcDon.toLocaleString()}). Kế hoạch chuẩn bị thêm xe tăng cường cho mấy ngày đến!`);
        } else if (maxGtcDon > 0 && donTaoN1kho > 0 && donTaoN1kho > maxGtcDon * 1.2) {
            const ratio = (donTaoN1kho / maxGtcDon).toFixed(1);
            score += 15;
            alerts.push(`⚠️ Hàng tạo cao gấp ${ratio}x đơn GTC. Theo dõi sát nguy cơ tồn`);
            recommendations.unshift(`📦 Hàng tạo (${donTaoN1kho.toLocaleString()}) cao gấp ${ratio}x GTC max ngày (${maxGtcDon.toLocaleString()}). Cần theo dõi sát, cân nhắc bổ sung xe nếu tiếp tục tăng.`);
        }

        // --- Phân loại rủi ro ---
        let riskLevel = 'good';
        let riskLabel = '🟢 Ổn định';
        let riskColor = 'var(--green)';
        let riskBg = '#E8F5E9';

        if (score >= 55) {
            riskLevel = 'critical';
            riskLabel = '🔴 Nghiêm trọng';
            riskColor = 'var(--red)';
            riskBg = '#FFEBEE';
        } else if (score >= 30) {
            riskLevel = 'warning';
            riskLabel = '🟠 Cảnh báo';
            riskColor = 'var(--orange)';
            riskBg = '#FFF3E0';
        } else if (score >= 15) {
            riskLevel = 'watch';
            riskLabel = '🟡 Theo dõi';
            riskColor = '#F08C00';
            riskBg = '#FFFDE7';
        }

        if (recommendations.length === 0) recommendations.push('Duy trì vận hành, tiếp tục giám sát định kỳ');

        results.push({
            kho, score, riskLevel, riskLabel, riskColor, riskBg,
            gtcN1: gtc.latest,
            gtcAvg7d: gtc.avg7d,
            gtcMax7d: gtc.max7d,
            gtcTrend: gtc.trend,
            blLm: bl.lm,
            blKtc: bl.ktc,
            alertsText: alerts.join(' | ') || '—',
            recText: recommendations[0] || '—'
        });
    });

    // Sắp xếp: rủi ro cao nhất trước
    results.sort((a, b) => b.score - a.score);
    return results;
}

function renderForecastSection() {
    const tbody = document.getElementById('tbody-forecast');
    if (!tbody) return;
    if (!state.gtcData || !state.gtcData.length) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--text3)">Đang tải dữ liệu phân tích...</td></tr>';
        return;
    }

    const data = buildForecastData();
    // DEBUG: kiểm tra maxGtcDon và donTaoN1
    console.log('[FORECAST DEBUG] Sample data:', data.slice(0, 3).map(r => ({
        kho: r.kho, score: r.score, donTaoN1: r.donTaoN1, maxGtcDon: r.maxGtcDon, alerts: r.alertsText
    })));

    // Cập nhật KPI cards
    const counts = { critical: 0, warning: 0, watch: 0, good: 0 };
    data.forEach(r => counts[r.riskLevel]++);
    ['critical', 'warning', 'watch', 'good'].forEach(lvl => {
        const el = document.getElementById(`fc-${lvl}-count`);
        if (el) el.textContent = counts[lvl];
    });

    // Cập nhật badge nav
    const badge = document.getElementById('nav-forecast-count');
    if (badge) {
        const urgent = counts.critical + counts.warning;
        badge.textContent = urgent;
        badge.style.display = urgent > 0 ? 'inline-block' : 'none';
    }

    // Lọc theo filter
    const khoFilter = ((document.getElementById('filter-forecast-kho') || {}).value || '').toLowerCase();
    const riskFilter = ((document.getElementById('filter-forecast-risk') || {}).value || '');

    let filtered = data;
    if (khoFilter) filtered = filtered.filter(r => r.kho.toLowerCase().includes(khoFilter));
    if (riskFilter) filtered = filtered.filter(r => r.riskLevel === riskFilter);

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:20px;color:var(--text3)">Không có dữ liệu phù hợp</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(r => {
        const trendArrow = r.gtcTrend > 1 ? `<span style="color:var(--green)">↑ ${r.gtcTrend.toFixed(1)}%</span>`
            : r.gtcTrend < -1 ? `<span style="color:var(--red)">↓ ${Math.abs(r.gtcTrend).toFixed(1)}%</span>`
                : `<span style="color:var(--text3)">→ Ổn</span>`;

        const gtcN1Color = r.gtcN1 < 82 ? 'var(--red)' : r.gtcN1 < 87 ? 'var(--orange)' : 'var(--green)';
        const blLmColor = r.blLm > 1000 ? 'var(--red)' : r.blLm > 500 ? 'var(--orange)' : 'inherit';
        const blKtcColor = r.blKtc > 500 ? 'var(--red)' : r.blKtc > 200 ? 'var(--orange)' : 'inherit';

        return `<tr style="background:${r.riskBg}20">
            <td style="font-weight:700">${r.kho}</td>
            <td style="text-align:center">
                <span style="font-size:13px;font-weight:700;color:${r.riskColor}">${r.riskLabel}</span>
            </td>
            <td style="text-align:center;font-weight:800;font-size:15px;color:${r.riskColor}">${r.score}</td>
            <td style="text-align:right;font-weight:700;color:${gtcN1Color}">${r.gtcN1 > 0 ? r.gtcN1.toFixed(1) + '%' : '--'}</td>
            <td style="text-align:right;color:var(--text2)">${r.gtcAvg7d > 0 ? r.gtcAvg7d.toFixed(1) + '%' : '--'}</td>
            <td style="text-align:right;color:var(--blue)">${r.gtcMax7d > 0 ? r.gtcMax7d.toFixed(1) + '%' : '--'}</td>
            <td style="text-align:center">${trendArrow}</td>
            <td style="text-align:right;font-weight:${r.blLm > 500 ? '700' : '400'};color:${blLmColor}">${r.blLm > 0 ? r.blLm.toLocaleString() : '0'}</td>
            <td style="text-align:right;font-weight:${r.blKtc > 200 ? '700' : '400'};color:${blKtcColor}">${r.blKtc > 0 ? r.blKtc.toLocaleString() : '0'}</td>
            <td style="font-size:11px;color:${r.riskLevel === 'good' ? 'var(--text3)' : 'var(--text2)'};max-width:200px">${r.alertsText}</td>
            <td style="font-size:11px;color:var(--text2);max-width:220px;font-style:italic">${r.recText}</td>
        </tr>`;
    }).join('');

    // Gắn events cho filter (chỉ lần đầu)
    if (!window._forecastFiltersInit) {
        const khoEl = document.getElementById('filter-forecast-kho');
        const riskEl = document.getElementById('filter-forecast-risk');
        if (khoEl) khoEl.addEventListener('input', renderForecastSection);
        if (riskEl) riskEl.addEventListener('change', renderForecastSection);
        window._forecastFiltersInit = true;
    }

    // Render bảng quá tải
    renderOverloadTable();

    // Render bảng cảnh báo hàng tạo vs GTC max
    renderDonTaoVsGtcTable();
}

// ---- BẢNG CẢNH BÁO HÀNG TẠO N-1 vs GTC MAX ----
function renderDonTaoVsGtcTable() {
    const tbody = document.getElementById('tbody-dontao-vs-gtc');
    if (!tbody) return;

    const now = Date.now();
    const cutoff7d = now - 7 * 86400000;

    // --- Lấy đơn tạo N-1 theo kho (ngày mới nhất) ---
    const donTaoByKho = {};
    let latestDonDate = '';
    if (state.donTaoData && state.donTaoData.length) {
        const allDonDates = [...new Set(state.donTaoData.map(r =>
            (r['Thời gian'] || r['time_view'] || '').split(' - ')[0]
        ).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
        latestDonDate = allDonDates[0] || '';
        state.donTaoData.forEach(r => {
            const dStr = (r['Thời gian'] || r['time_view'] || '').split(' - ')[0];
            if (dStr !== latestDonDate) return;
            const kho = shortKho(r['Kho giao'] || r['kho_giao'] || '');
            if (!kho || kho === '--') return;
            const don = parseInt(String(r['Tổng đơn tạo'] || '0').replace(/\./g, '').replace(/,/g, '')) || 0;
            donTaoByKho[kho] = (donTaoByKho[kho] || 0) + don;
        });
    }

    // --- Lấy GTC max số đơn/ngày theo kho trong 7 ngày ---
    const gtcMaxByKho = {};
    state.gtcData.forEach(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts || ts < cutoff7d) return;
        const kho = shortKho(r['Kho']);
        if (!kho || kho === '--') return;
        const gtcDon = parseInt(r['Số đơn GTC'] || 0);
        if (gtcDon > 0) {
            gtcMaxByKho[kho] = Math.max(gtcMaxByKho[kho] || 0, gtcDon);
        }
    });

    // --- Gộp kho từ 2 nguồn ---
    const allKhos = new Set([...Object.keys(donTaoByKho), ...Object.keys(gtcMaxByKho)]);
    const rows = [];
    allKhos.forEach(kho => {
        const donTao = donTaoByKho[kho] || 0;
        const gtcMax = gtcMaxByKho[kho] || 0;
        if (!donTao && !gtcMax) return;
        const ratio = gtcMax > 0 ? donTao / gtcMax : 0;
        rows.push({ kho, donTao, gtcMax, ratio });
    });

    // Sắp xếp: tỉ lệ cao nhất trước (nguy hiểm nhất lên trên)
    rows.sort((a, b) => b.ratio - a.ratio);

    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text3);padding:20px">Chưa có dữ liệu</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map((r, i) => {
        let levelLabel, levelBg, levelColor, message;
        if (r.gtcMax === 0) {
            levelLabel = '—';
            levelBg = '#f5f5f5';
            levelColor = 'var(--text3)';
            message = 'Chưa đủ dữ liệu GTC 7 ngày';
        } else if (r.ratio > 1.5) {
            levelLabel = '🚛 Cần tăng xe ngay';
            levelBg = '#FFEBEE';
            levelColor = 'var(--red)';
            message = `⚠️ Hàng tạo cao gấp <strong>${r.ratio.toFixed(1)}x</strong> đơn GTC max ngày (${r.gtcMax.toLocaleString()}đ). Nguy cơ tồn hàng cao — Kế hoạch chuẩn bị thêm xe tăng cường cho mấy ngày đến!`;
        } else if (r.ratio > 1.2) {
            levelLabel = '⚠️ Theo dõi sát';
            levelBg = '#FFF3E0';
            levelColor = 'var(--orange)';
            message = `Hàng tạo cao gấp <strong>${r.ratio.toFixed(1)}x</strong> GTC max ngày (${r.gtcMax.toLocaleString()}đ). Cần theo dõi sát, cân nhắc bổ sung xe nếu tiếp tục tăng.`;
        } else {
            levelLabel = '✅ An toàn';
            levelBg = '#F1F8F4';
            levelColor = 'var(--green)';
            message = `Hàng tạo nằm trong khả năng xử lý của kho (${r.ratio.toFixed(2)}x).`;
        }

        const ratioColor = r.ratio > 1.5 ? 'var(--red)' : r.ratio > 1.2 ? 'var(--orange)' : 'var(--green)';
        const donColor = r.ratio > 1.5 ? 'var(--red)' : r.ratio > 1.2 ? 'var(--orange)' : 'inherit';

        return `<tr style="background:${levelBg}20">
            <td style="font-weight:700">${r.kho}</td>
            <td style="text-align:right;font-weight:700;font-size:15px;color:${donColor}">${r.donTao > 0 ? r.donTao.toLocaleString() : '<span style="color:var(--text3)">--</span>'}</td>
            <td style="text-align:right;color:var(--blue);font-weight:600">${r.gtcMax > 0 ? r.gtcMax.toLocaleString() : '<span style="color:var(--text3)">--</span>'}</td>
            <td style="text-align:center;font-weight:800;font-size:15px;color:${ratioColor}">${r.gtcMax > 0 ? r.ratio.toFixed(2) + 'x' : '--'}</td>
            <td style="text-align:center">
                <span style="font-size:12px;font-weight:700;color:${levelColor};white-space:nowrap">${levelLabel}</span>
            </td>
            <td style="font-size:12px;color:var(--text2)">${message}</td>
        </tr>`;
    }).join('');
}

// ---- OVERLOAD FORECAST / DỰ BÁO QUÁ TẢI KHO ----
function buildOverloadData() {
    const now = Date.now();
    const cutoff7d = now - 7 * 86400000;

    // --- Bước 1: Lấy đơn tạo N-1 theo kho (ngày mới nhất trong donTaoData) ---
    const donTaoByKho = {};
    if (state.donTaoData && state.donTaoData.length) {
        const allDonDates = [...new Set(state.donTaoData.map(r => {
            return (r['Thời gian'] || r['time_view'] || '').split(' - ')[0];
        }).filter(Boolean))].sort().reverse();
        const latestDonDate = allDonDates[0];

        state.donTaoData.forEach(r => {
            const dStr = (r['Thời gian'] || r['time_view'] || '').split(' - ')[0];
            if (dStr !== latestDonDate) return;
            const kho = shortKho(r['Kho giao'] || r['kho_giao'] || '');
            if (!kho || kho === '--') return;
            const don = parseInt(String(r['Tổng đơn tạo'] || '0').replace(/\./g, '').replace(/,/g, '')) || 0;
            donTaoByKho[kho] = (donTaoByKho[kho] || 0) + don;
        });
    }

    // --- Bước 2: GTC stats theo kho 7 ngày ---
    const gtcByKho = {};
    const allGtcDates = [...new Set(state.gtcData.map(r => r['Ngày']).filter(Boolean))].sort((a, b) => parseVN(b) - parseVN(a));
    const latestGtcDate = allGtcDates[0] || '';

    state.gtcData.forEach(r => {
        const ts = parseVN(r['Ngày']);
        if (!ts || ts < cutoff7d) return;
        const kho = shortKho(r['Kho']);
        if (!kho || kho === '--') return;
        if (!gtcByKho[kho]) gtcByKho[kho] = { days: [] };
        gtcByKho[kho].days.push({ ts, pct: parsePct(r['% GTC']), gan: parseInt(r['Số đơn gán'] || 0), gtcDon: parseInt(r['Số đơn GTC'] || 0) });
    });

    Object.keys(gtcByKho).forEach(kho => {
        const days = gtcByKho[kho].days.sort((a, b) => b.ts - a.ts);
        const pcts = days.map(d => d.pct).filter(p => p > 0);
        const ganAll = days.map(d => d.gan).filter(g => g > 0);
        const avg7d = pcts.length ? pcts.reduce((a, b) => a + b, 0) / pcts.length : 0;
        const max7d = pcts.length ? Math.max(...pcts) : 0;
        const latestRow = state.gtcData.find(r => shortKho(r['Kho']) === kho && r['Ngày'] === latestGtcDate);
        const gtcN1 = latestRow ? parsePct(latestRow['% GTC']) : (pcts[0] || 0);
        // Số đơn GTC THỰC TỌ ngày N-1 (không phải %)
        const gtcN1Don = latestRow ? parseInt(latestRow['Số đơn GTC'] || 0) : (days[0]?.gtcDon || 0);
        const avgGan = ganAll.length ? Math.round(ganAll.reduce((a, b) => a + b, 0) / ganAll.length) : 0;
        gtcByKho[kho] = { avg7d, max7d, gtcN1, gtcN1Don, avgGan };
    });

    // --- Bước 3: Backlog theo kho từ warningsData ---
    const backlogByKho = {};
    state.warningsData.forEach(r => {
        const kho = shortKho(r['kho gxt'] || r['Kho'] || '');
        if (!kho || kho === '--') return;
        const lm = parseInt(r['backlog last mile'] || r['backlog lastmile'] || 0);
        const ktc = parseInt(r['backlog ktc'] || 0);
        backlogByKho[kho] = { lm, ktc };
    });

    // --- Bước 4: Gộp tất cả kho ---
    const khoSet = new Set([
        ...Object.keys(gtcByKho),
        ...Object.keys(donTaoByKho),
        ...Object.keys(backlogByKho)
    ]);

    const results = [];
    khoSet.forEach(kho => {
        const gtc = gtcByKho[kho] || { avg7d: 0, max7d: 0, gtcN1: 0, avgGan: 0 };
        const bl = backlogByKho[kho] || { lm: 0, ktc: 0 };

        // Đơn tạo N-1
        const donTaoN1 = donTaoByKho[kho] || gtc.avgGan || 0;
        const avgGan = gtc.avgGan || donTaoN1;
        const gtcN1Don = gtc.gtcN1Don || 0; // Số đơn GTC thực tế ngày N-1
        const tongApLuc = bl.lm + bl.ktc + donTaoN1;
        if (!tongApLuc && !gtc.avg7d) return;

        const nangLucTB = avgGan > 0 ? Math.round(avgGan * gtc.avg7d / 100) : 0;
        const nangLucMax = avgGan > 0 ? Math.round(avgGan * gtc.max7d / 100) : 0;

        // ---- ĐƠN CẦN CLEAR ----
        // = (Backlog LM + Backlog KTC) / 2 − GTC N-1 (đơn thực tế)
        // Nếu âm thì để 0
        const donCanClear = gtcN1Don > 0
            ? Math.max(0, Math.round((bl.lm + bl.ktc) / 2 - gtcN1Don))
            : Math.round((bl.lm + bl.ktc) / 2);

        // ---- PHÂN LOẠI TRẠNG THÁI ----
        let overloadStatus, statusLabel, statusColor, statusBg;
        if (donCanClear <= 50) {
            overloadStatus = 'stable'; statusLabel = '🟢 Ổn định';
            statusColor = 'var(--green)'; statusBg = '#E8F5E9';
        } else if (donCanClear <= 100) {
            overloadStatus = 'watch'; statusLabel = '🟡 Theo dõi';
            statusColor = '#F08C00'; statusBg = '#FFFDE7';
        } else if (donCanClear <= 300) {
            overloadStatus = 'risk'; statusLabel = '🟠 Nguy cơ';
            statusColor = 'var(--orange)'; statusBg = '#FFF3E0';
        } else {
            overloadStatus = 'overloaded'; statusLabel = '🔴 Quá tải';
            statusColor = 'var(--red)'; statusBg = '#FFEBEE';
        }

        // ---- ĐỀ XUẤT HÀNH ĐỘNG ----
        let action;
        if (overloadStatus === 'stable' || overloadStatus === 'watch') {
            action = '✅ Cần tiếp tục theo dõi và giữ vững năng suất hiện tại của Kho.';
        } else if (gtcN1Don > 0) {
            // HĐ1: (Backlog LM + Backlog KTC) / GTC N-1
            const soNgayKhongXe = ((bl.lm + bl.ktc) / gtcN1Don).toFixed(2);
            // HĐ2: Đơn cần clear / 50 đơn/xe (làm tròn xuống)
            const soXeTC = Math.floor(donCanClear / 50);
            const soXeTCDisplay = soXeTC > 0 ? soXeTC : '<1';
            action = `🕐 Hành động 1: Cần <strong>${soNgayKhongXe} ngày</strong> để kho trở về Ổn Định nếu không sử dụng thêm xe Tăng Cường.<br>`
                + `🚛 Hành động 2: Cần <strong>${soXeTCDisplay} xe</strong> tăng cường clear <strong>${donCanClear.toLocaleString()} đơn</strong> trong 1 ngày để kho trở về ngày thường (NS 50 đơn GTC/xe).`;
        } else {
            action = '✅ Cần tiếp tục theo dõi và giữ vững năng suất hiện tại của Kho.';
        }

        results.push({
            kho, overloadStatus, statusLabel, statusColor, statusBg,
            donTaoN1, blLm: bl.lm, blKtc: bl.ktc, tongApLuc,
            nangLucTB, nangLucMax,
            donCanClear,
            gtcN1Don,
            gtcN1: gtc.gtcN1, gtcAvg7d: gtc.avg7d, gtcMax7d: gtc.max7d,
            action
        });
    });

    // Sắp xếp: quá tải → nguy cơ → theo dõi → ổn định, rồi donCanClear giảm dần
    const order = { overloaded: 0, risk: 1, watch: 2, stable: 3 };
    results.sort((a, b) => {
        if (order[a.overloadStatus] !== order[b.overloadStatus])
            return order[a.overloadStatus] - order[b.overloadStatus];
        return b.donCanClear - a.donCanClear;
    });
    return results;
}

function renderOverloadTable() {
    const tbody = document.getElementById('tbody-overload');
    if (!tbody) return;

    const data = buildOverloadData();
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;color:var(--text3)">Chưa đủ dữ liệu để phân tích quá tải</td></tr>';
        return;
    }

    const khoFilter = ((document.getElementById('filter-forecast-kho') || {}).value || '').toLowerCase();
    const filtered = khoFilter ? data.filter(r => r.kho.toLowerCase().includes(khoFilter)) : data;

    tbody.innerHTML = filtered.map(r => {
        const donTaoColor = r.donTaoN1 > 0 ? 'var(--purple)' : 'var(--text3)';
        const clearColor = r.donCanClear > 200 ? 'var(--red)' : r.donCanClear > 100 ? 'var(--orange)' : r.donCanClear > 0 ? '#F08C00' : 'var(--green)';
        const clearDisplay = r.donCanClear > 0 ? `<strong style="color:${clearColor}">${r.donCanClear.toLocaleString()}</strong>` : `<span style="color:var(--green)">0 — Ổn</span>`;

        return `<tr style="background:${r.statusBg}15;border-left:3px solid ${r.statusColor}">
            <td style="font-weight:700;white-space:nowrap">${r.kho}</td>
            <td style="text-align:center;white-space:nowrap">
                <span style="font-size:12px;font-weight:700;color:${r.statusColor};padding:3px 8px;border-radius:12px;background:${r.statusBg}">${r.statusLabel}</span>
            </td>
            <td style="text-align:right;font-weight:600;color:${donTaoColor}">${r.donTaoN1 > 0 ? r.donTaoN1.toLocaleString() : '--'}</td>
            <td style="text-align:right;color:${r.blLm > 1000 ? 'var(--red)' : r.blLm > 500 ? 'var(--orange)' : 'inherit'}">${r.blLm.toLocaleString()}</td>
            <td style="text-align:right;color:${r.blKtc > 500 ? 'var(--red)' : r.blKtc > 200 ? 'var(--orange)' : 'inherit'}">${r.blKtc.toLocaleString()}</td>
            <td style="text-align:right;color:var(--blue);font-weight:600">${r.gtcN1Don > 0 ? r.gtcN1Don.toLocaleString() : '--'}</td>
            <td style="text-align:right">${clearDisplay}</td>
            <td style="font-size:11.5px;color:var(--text2);min-width:280px;line-height:1.7">${r.action}</td>
        </tr>`;
    }).join('');
}

// ---- LOGIN & LOGOUT SYSTEM ----
let allowedKhosList = []; // Danh sách kho tải từ API để validate thông tin cá nhân

async function initLogin() {
    const isAlreadyLoggedIn = localStorage.getItem('ghn_logged_in') === 'true';
    const isProfileCompleted = sessionStorage.getItem('ghn_profile_completed') === 'true';
    
    const loginWrapper = document.getElementById('login-wrapper');
    const profileWrapper = document.getElementById('profile-wrapper');
    const appContainer = document.getElementById('app-container');

    // Kiểm tra tính tương thích của HTML: nếu thiếu các phần tử profile, coi như tự động hoàn thành để tránh trắng trang
    const hasProfileElements = document.getElementById('profile-id-ghn') && 
                               document.getElementById('profile-ho-ten') && 
                               document.getElementById('profile-kho') && 
                               document.getElementById('profile-submit-btn');

    if (isAlreadyLoggedIn) {
        if (loginWrapper) loginWrapper.style.display = 'none';
        
        // Nếu đã hoàn thành thông tin cá nhân, hoặc file HTML cũ chưa cập nhật các thẻ profile -> cho vào thẳng dashboard
        if (isProfileCompleted || !hasProfileElements) {
            if (profileWrapper) profileWrapper.style.display = 'none';
            if (appContainer) appContainer.style.display = 'flex';
            // Khởi chạy dashboard
            showSection('overview');
            ensureSectionData('overview');
            startSyncTimer();
            checkAdminAccess();
            setupLogout();
        } else {
            if (appContainer) appContainer.style.display = 'none';
            if (profileWrapper) profileWrapper.style.display = 'flex';
            setupProfileForm();
        }
    } else {
        if (loginWrapper) loginWrapper.style.display = 'flex';
        if (profileWrapper) profileWrapper.style.display = 'none';
        if (appContainer) appContainer.style.display = 'none';
        setupLoginForm();
    }
}

function setupLoginForm() {
    const submitBtn = document.getElementById('login-submit-btn');
    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    const loginError = document.getElementById('login-error');
    const togglePasswordEye = document.getElementById('toggle-password-eye');

    if (togglePasswordEye && passwordInput) {
        togglePasswordEye.onclick = () => {
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                togglePasswordEye.classList.replace('fa-eye', 'fa-eye-slash');
            } else {
                passwordInput.type = 'password';
                togglePasswordEye.classList.replace('fa-eye-slash', 'fa-eye');
            }
        };
    }

    const handleLoginSubmit = async () => {
        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        try {
            const resp = await fetch(`${API}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (resp.ok) {
                const json = await resp.json();
                if (json.token) {
                    setApiToken(json.token);
                    localStorage.setItem('ghn_logged_in', 'true');
                }
                if (loginError) loginError.style.display = 'none';
                initLogin();
            } else {
                if (loginError) {
                    loginError.style.display = 'flex';
                    loginError.style.animation = 'none';
                    loginError.offsetHeight;
                    loginError.style.animation = null;
                }
            }
        } catch (err) {
            console.error('[AUTH] Login error:', err);
            if (loginError) loginError.style.display = 'flex';
        }
    };

    if (submitBtn) {
        submitBtn.onclick = handleLoginSubmit;
    }

    const inputs = [usernameInput, passwordInput];
    inputs.forEach(input => {
        if (input) {
            input.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    handleLoginSubmit();
                }
            };
        }
    });
}

async function setupProfileForm() {
    try {
        const idInput = document.getElementById('profile-id-ghn');
        const nameInput = document.getElementById('profile-ho-ten');
        const khoInput = document.getElementById('profile-kho');
        const datalist = document.getElementById('profile-kho-list');
        const submitBtn = document.getElementById('profile-submit-btn');
        const errorEl = document.getElementById('profile-error');
        const errorTextEl = document.getElementById('profile-error-text');

        if (!submitBtn) return;

        // Tự động điền dữ liệu cũ từ localStorage
        if (idInput && !idInput.value) idInput.value = localStorage.getItem('ghn_id_ghn') || '';
        if (nameInput && !nameInput.value) nameInput.value = localStorage.getItem('ghn_ho_ten') || '';
        if (khoInput && !khoInput.value) khoInput.value = localStorage.getItem('ghn_kho_phong') || '';

        // Load danh sách kho để hiển thị autocomplete
        try {
            const token = getApiToken();
            const resp = await fetch(`${API}/xe-van-hanh/meta`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (resp.status === 401 || resp.status === 403) {
                // Token hết hạn -> Buộc logout để đăng nhập lại
                console.warn('[PROFILE] Auth token expired, redirecting to login page');
                clearApiToken();
                localStorage.removeItem('ghn_logged_in');
                window.location.reload();
                return;
            }
            if (resp.ok) {
                const data = await resp.json();
                if (data && data.kho_list) {
                    allowedKhosList = data.kho_list;
                    if (datalist) {
                        datalist.innerHTML = data.kho_list.map(k => `<option value="${k}"></option>`).join('') + '<option value="Phòng ban khác"></option>';
                    }
                }
            } else {
                console.warn('[PROFILE] Failed to load warehouses, status:', resp.status);
            }
        } catch (e) {
            console.error('[PROFILE] Failed to load warehouses:', e);
        }

        // Chỉ cho phép nhập số ở ô ID GHN
        if (idInput) {
            idInput.oninput = () => {
                idInput.value = idInput.value.replace(/\D/g, '');
            };
        }

        submitBtn.onclick = async () => {
            const idVal = idInput.value.trim();
            const nameVal = nameInput.value.trim();
            const khoVal = khoInput.value.trim();

            if (errorEl) errorEl.style.display = 'none';

            if (!idVal || !/^\d+$/.test(idVal)) {
                showError('ID GHN bắt buộc nhập và chỉ gồm các chữ số.');
                idInput.focus();
                return;
            }

            if (!nameVal) {
                showError('Vui lòng nhập Họ và Tên.');
                nameInput.focus();
                return;
            }

            if (!khoVal) {
                showError('Vui lòng nhập Tên Kho hoặc "Phòng ban khác".');
                khoInput.focus();
                return;
            }

            const isProvinceOther = khoVal === 'Phòng ban khác';
            const isValidKho = allowedKhosList.includes(khoVal);
            
            // Nếu danh sách kho trống (do lỗi mạng), bỏ qua validation kho để không chặn người dùng
            const isKhoListEmpty = allowedKhosList.length === 0;

            if (!isProvinceOther && !isValidKho && !isKhoListEmpty) {
                showError('Tên Kho không hợp lệ hoặc không có trong danh sách. Vui lòng chọn từ gợi ý hoặc nhập chính xác: Phòng ban khác');
                khoInput.focus();
                return;
            }

            const adminKey = sessionStorage.getItem('ghn_admin_key') || '';
            const accessType = adminKey === 'JnBjZUODMXhy7BCupcB5IMPwYOJfHuDkm1-OKR9Jklc' ? 'admin' : 'normal';

            // Lấy thời gian hiện tại ở Việt Nam
            const now = new Date();
            const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
            const vnNow = new Date(utc + (3600000 * 7));
            const pad = n => String(n).padStart(2, '0');
            const loginTime = `${pad(vnNow.getHours())}:${pad(vnNow.getMinutes())}:${pad(vnNow.getSeconds())}`;
            const loginDate = _getTodayVN();

            // Dữ liệu tạm thời lưu trước để dự phòng
            const saveToLocalAndProceed = () => {
                localStorage.setItem('ghn_id_ghn', idVal);
                localStorage.setItem('ghn_ho_ten', nameVal);
                localStorage.setItem('ghn_kho_phong', khoVal);
                sessionStorage.setItem('ghn_profile_completed', 'true');
            };

            try {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang kết nối...';
                
                const token = getApiToken();
                const resp = await fetch(`${API}/login-logs`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        idGHN: idVal,
                        fullName: nameVal,
                        warehouseOrDepartment: khoVal,
                        loginDate: loginDate,
                        loginTime: loginTime,
                        accessType: accessType,
                        userAgent: navigator.userAgent
                    })
                });

                if (resp.ok) {
                    saveToLocalAndProceed();
                    showToast('✅ Đăng nhập ghi nhận thành công!', 'success');
                    initLogin();
                } else {
                    console.error('[PROFILE SUBMIT API ERROR] Status:', resp.status);
                    // Lỗi 404 hoặc lỗi API khác -> Không chặn người dùng
                    saveToLocalAndProceed();
                    showToast('⚠️ Không ghi nhận được log đăng nhập, hệ thống vẫn tiếp tục vào dashboard.', 'warning');
                    initLogin();
                }
            } catch (e) {
                console.error('[PROFILE SUBMIT NETWORK ERROR]', e);
                // Lỗi kết nối mạng -> Không chặn người dùng
                saveToLocalAndProceed();
                showToast('⚠️ Không ghi nhận được log đăng nhập (lỗi mạng), hệ thống vẫn tiếp tục vào dashboard.', 'warning');
                initLogin();
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Tiếp tục vào dashboard <i class="fa-solid fa-arrow-right"></i>';
            }
        };

        function showError(msg) {
            if (errorEl && errorTextEl) {
                errorTextEl.textContent = msg;
                errorEl.style.display = 'flex';
            }
        }
    } catch (err) {
        console.error('[PROFILE FORM CRASH]', err);
    }
}

function setupLogout() {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.onclick = (e) => {
            e.preventDefault();
            clearApiToken();
            localStorage.removeItem('ghn_logged_in');
            sessionStorage.removeItem('ghn_profile_completed');
            window.location.reload();
        };
    }
}

// ---- INIT ----
document.addEventListener('DOMContentLoaded', () => {
    initLogin();
});

// ============================================================================
// ---- GTC ĐƠN B2B ƯU TIÊN SECTION ----
// ============================================================================
let b2bActiveTab = 'vung';
let b2bFiltersPopulated = false;
let b2bChartTab = 'day';
let b2bKhoChartTab = 'day';

// Filter selections
let selectedB2bVungDays = [];
let selectedB2bVungMonths = [];
let selectedB2bVungRegions = [];

let selectedB2bKhoDays = [];
let selectedB2bKhoMonths = [];
let selectedB2bKhoRegions = [];
let selectedB2bKhoWarehouses = [];

let selectedB2bDetailDays = [];
let selectedB2bDetailMonths = [];
let selectedB2bDetailRegion = '';
let selectedB2bDetailWarehouse = '';
let selectedB2bDetailError = '';

// Helper to convert sheet date to YYYY-MM-DD
function parseDateToYmd(dateStr) {
    if (!dateStr) return '';
    dateStr = dateStr.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return dateStr;
    if (/^\d{4}-\d{2}-\d{2}/.test(dateStr)) return dateStr.substring(0, 10);
    
    // "1 thg 7, 2026"
    let m = dateStr.match(/^(\d+)\s+thg\s+(\d+),\s+(\d+)$/);
    if (m) {
        let d = m[1].padStart(2, '0');
        let mon = m[2].padStart(2, '0');
        let y = m[3];
        return `${y}-${mon}-${d}`;
    }
    
    // "01/07/2026"
    let m2 = dateStr.match(/^(\d+)\/(\d+)\/(\d+)$/);
    if (m2) {
        let d = m2[1].padStart(2, '0');
        let mon = m2[2].padStart(2, '0');
        let y = m2[3];
        return `${y}-${mon}-${d}`;
    }
    return dateStr;
}

// Get Month from Date String (YYYY-MM-DD -> YYYY-MM)
function getMonthFromYmd(ymd) {
    if (!ymd || ymd.length < 7) return '';
    return ymd.substring(0, 7);
}

// Helper to convert any date representation safely to YYYY-MM-DD
function parseDateToYmdSafe(dateVal) {
    if (!dateVal) return '';
    if (dateVal instanceof Date) {
        const y = dateVal.getFullYear();
        const m = String(dateVal.getMonth() + 1).padStart(2, '0');
        const d = String(dateVal.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }
    if (typeof dateVal === 'number') {
        const dObj = new Date(dateVal);
        if (!isNaN(dObj.getTime())) {
            const y = dObj.getFullYear();
            const m = String(dObj.getMonth() + 1).padStart(2, '0');
            const d = String(dObj.getDate()).padStart(2, '0');
            return `${y}-${m}-${d}`;
        }
    }
    let s = String(dateVal).trim();
    if (!s) return '';
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.substring(0, 10);

    // "1 thg 7, 2026"
    let m = s.match(/^(\d+)\s+thg\s+(\d+),\s+(\d+)$/);
    if (m) {
        return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
    }

    // "01/07/2026"
    let m2 = s.match(/^(\d+)\/(\d+)\/(\d+)$/);
    if (m2) {
        return `${m2[3]}-${m2[2].padStart(2, '0')}-${m2[1].padStart(2, '0')}`;
    }

    // Thử dùng Date.parse
    const ts = Date.parse(s);
    if (!isNaN(ts)) {
        const dObj = new Date(ts);
        const y = dObj.getFullYear();
        const m = String(dObj.getMonth() + 1).padStart(2, '0');
        const d = String(dObj.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }
    return s;
}

// Check if warehouse is Lien Chieu
function isLienChieu(val) {
    if (!val) return false;
    const s = String(val).trim().toLowerCase();
    if (s === '21089000' || s === '21089000.0') return true;
    if (s.includes('liên chiểu') || s.includes('lien chieu')) return true;
    return false;
}

// Get Region of a warehouse according to a date
function getRegionByDate(warehouseNameOrId, dateVal) {
    if (!warehouseNameOrId) return 'Chưa xác định';
    
    const ymd = parseDateToYmdSafe(dateVal);
    const isOldPeriod = ymd && ymd <= '2026-06-30';
    const isLc = isLienChieu(warehouseNameOrId);
    
    if (isOldPeriod) {
        if (isLc) return 'Miền Trung 05';
        if (String(warehouseNameOrId).trim() === 'Miền Trung 05') return 'Miền Trung 05';
    } else {
        if (String(warehouseNameOrId).trim() === 'Miền Trung 05') return 'Miền Trung 02';
    }
    
    if (state.khoGxtData) {
        const searchVal = String(warehouseNameOrId).trim();
        for (let row of state.khoGxtData) {
            const idKho = (row['ID Kho'] || '').trim();
            const name = (row['Tên Kho GXT'] || row['kho gxt'] || row['Tên'] || '').trim();
            if (idKho && idKho === searchVal) {
                const vung = (row['Vùng'] || row['vung'] || '').trim();
                return vung || 'Chưa xác định';
            }
            if (name && (name === searchVal || shortKho(name) === shortKho(searchVal))) {
                const vung = (row['Vùng'] || row['vung'] || '').trim();
                return vung || 'Chưa xác định';
            }
        }
    }
    
    const nameStr = String(warehouseNameOrId).trim();
    let parts = nameStr.split('-');
    if (parts.length >= 3) {
        return parts[parts.length - 1].trim();
    }
    return 'Chưa xác định';
}

// Map warehouse name to region (updated to support dynamic date)
function getRegionForWarehouse(warehouseName, dateStr) {
    return getRegionByDate(warehouseName, dateStr);
}

window.switchGtcB2bPrioTab = function(tab) {
    b2bActiveTab = tab;
    ['vung', 'kho', 'detail'].forEach(t => {
        const panel = document.getElementById('panel-b2b-' + t);
        const btn = document.getElementById('tab-btn-b2b-' + t);
        if (panel) panel.style.display = (t === tab) ? 'block' : 'none';
        if (btn) {
            if (t === tab) btn.classList.add('active');
            else btn.classList.remove('active');
        }
    });
    renderGtcB2bPrioSection();
};

window.switchB2bChartTab = function(tab) {
    b2bChartTab = tab;
    ['day', 'month'].forEach(t => {
        const btn = document.getElementById('btn-chart-tab-' + t);
        if (btn) {
            if (t === tab) {
                btn.classList.add('active');
                btn.style.background = 'white';
                btn.style.color = 'var(--text1)';
                btn.style.boxShadow = 'var(--shadow-sm)';
            } else {
                btn.classList.remove('active');
                btn.style.background = 'transparent';
                btn.style.color = 'var(--text2)';
                btn.style.boxShadow = 'none';
            }
        }
    });
    renderGtcB2bVung();
};

window.switchB2bKhoChartTab = function(tab) {
    b2bKhoChartTab = tab;
    ['day', 'month'].forEach(t => {
        const btn = document.getElementById('btn-kho-chart-tab-' + t);
        if (btn) {
            if (t === tab) {
                btn.classList.add('active');
                btn.style.background = 'white';
                btn.style.color = 'var(--text1)';
                btn.style.boxShadow = 'var(--shadow-sm)';
            } else {
                btn.classList.remove('active');
                btn.style.background = 'transparent';
                btn.style.color = 'var(--text2)';
                btn.style.boxShadow = 'none';
            }
        }
    });
    renderGtcB2bKho();
};

window.toggleB2bMultiselect = function(mode) {
    const allMenus = document.querySelectorAll('.ghn-filter-menu');
    const targetId = 'menu-gtc-b2b-' + mode;
    allMenus.forEach(m => {
        if (m.id === targetId) m.classList.toggle('show');
        else m.classList.remove('show');
    });
};

window.resetB2bFilters = function(tab) {
    if (tab === 'vung') {
        selectedB2bVungDays = [];
        selectedB2bVungMonths = [];
        selectedB2bVungRegions = [];
        document.querySelectorAll('#menu-gtc-b2b-vung-day input').forEach(c => c.checked = false);
        document.querySelectorAll('#menu-gtc-b2b-vung-month input').forEach(c => c.checked = false);
        document.querySelectorAll('#menu-gtc-b2b-vung-region input').forEach(c => c.checked = false);
        updateB2bLabels('vung-day', selectedB2bVungDays);
        updateB2bLabels('vung-month', selectedB2bVungMonths);
        updateB2bLabels('vung-region', selectedB2bVungRegions);
    } else if (tab === 'kho') {
        selectedB2bKhoDays = [];
        selectedB2bKhoMonths = [];
        selectedB2bKhoRegions = [];
        selectedB2bKhoWarehouses = [];
        document.querySelectorAll('#menu-gtc-b2b-kho-day input').forEach(c => c.checked = false);
        document.querySelectorAll('#menu-gtc-b2b-kho-month input').forEach(c => c.checked = false);
        document.querySelectorAll('#menu-gtc-b2b-kho-region input').forEach(c => c.checked = false);
        document.querySelectorAll('#menu-gtc-b2b-kho-warehouse input').forEach(c => c.checked = false);
        updateB2bLabels('kho-day', selectedB2bKhoDays);
        updateB2bLabels('kho-month', selectedB2bKhoMonths);
        updateB2bLabels('kho-region', selectedB2bKhoRegions);
        updateB2bLabels('kho-warehouse', selectedB2bKhoWarehouses);
    } else if (tab === 'detail') {
        selectedB2bDetailDays = [];
        selectedB2bDetailMonths = [];
        selectedB2bDetailRegion = '';
        selectedB2bDetailWarehouse = '';
        selectedB2bDetailError = '';
        document.querySelectorAll('#menu-gtc-b2b-detail-day input').forEach(c => c.checked = false);
        document.querySelectorAll('#menu-gtc-b2b-detail-month input').forEach(c => c.checked = false);
        document.getElementById('filter-b2b-detail-region').value = '';
        document.getElementById('filter-b2b-detail-warehouse').value = '';
        document.getElementById('filter-b2b-detail-error').value = '';
        updateB2bLabels('detail-day', selectedB2bDetailDays);
        updateB2bLabels('detail-month', selectedB2bDetailMonths);
    }
    renderGtcB2bPrioSection();
};

function updateB2bLabels(mode, list) {
    const el = document.getElementById('label-b2b-' + mode);
    if (!el) return;
    if (list.length === 0) {
        if (mode.endsWith('day')) el.innerText = 'Chọn Ngày...';
        else if (mode.endsWith('month')) el.innerText = 'Chọn Tháng...';
        else if (mode.endsWith('region')) el.innerText = 'Chọn Vùng...';
        else if (mode.endsWith('warehouse')) el.innerText = 'Chọn Kho...';
    } else {
        el.innerText = `${list.length} đã chọn`;
    }
}

window.updateB2bFilterSelection = function(mode, val, checked) {
    if (mode === 'vung-day') {
        if (checked) selectedB2bVungDays.push(val);
        else selectedB2bVungDays = selectedB2bVungDays.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bVungDays);
    } else if (mode === 'vung-month') {
        if (checked) selectedB2bVungMonths.push(val);
        else selectedB2bVungMonths = selectedB2bVungMonths.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bVungMonths);
    } else if (mode === 'vung-region') {
        if (checked) selectedB2bVungRegions.push(val);
        else selectedB2bVungRegions = selectedB2bVungRegions.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bVungRegions);
    } else if (mode === 'kho-day') {
        if (checked) selectedB2bKhoDays.push(val);
        else selectedB2bKhoDays = selectedB2bKhoDays.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bKhoDays);
    } else if (mode === 'kho-month') {
        if (checked) selectedB2bKhoMonths.push(val);
        else selectedB2bKhoMonths = selectedB2bKhoMonths.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bKhoMonths);
    } else if (mode === 'kho-region') {
        if (checked) selectedB2bKhoRegions.push(val);
        else selectedB2bKhoRegions = selectedB2bKhoRegions.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bKhoRegions);
    } else if (mode === 'kho-warehouse') {
        if (checked) selectedB2bKhoWarehouses.push(val);
        else selectedB2bKhoWarehouses = selectedB2bKhoWarehouses.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bKhoWarehouses);
    } else if (mode === 'detail-day') {
        if (checked) selectedB2bDetailDays.push(val);
        else selectedB2bDetailDays = selectedB2bDetailDays.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bDetailDays);
    } else if (mode === 'detail-month') {
        if (checked) selectedB2bDetailMonths.push(val);
        else selectedB2bDetailMonths = selectedB2bDetailMonths.filter(v => v !== val);
        updateB2bLabels(mode, selectedB2bDetailMonths);
    }
    rebuildB2bFilters();
    renderGtcB2bPrioSection();
};

window.updateB2bKhoFilters = function() {
    renderGtcB2bPrioSection();
};

window.updateB2bDetailFilters = function() {
    selectedB2bDetailRegion = document.getElementById('filter-b2b-detail-region').value;
    selectedB2bDetailWarehouse = document.getElementById('filter-b2b-detail-warehouse').value;
    selectedB2bDetailError = document.getElementById('filter-b2b-detail-error').value;
    renderGtcB2bPrioSection();
};

function checkHasOldDataForB2bFilter() {
    if (selectedB2bVungDays.length > 0) {
        return selectedB2bVungDays.some(d => d <= '2026-06-30');
    }
    if (selectedB2bVungMonths.length > 0) {
        return selectedB2bVungMonths.some(m => m <= '2026-06');
    }
    return true;
}

function checkHasOldDataForB2bKhoFilter() {
    if (selectedB2bKhoDays.length > 0) {
        return selectedB2bKhoDays.some(d => d <= '2026-06-30');
    }
    if (selectedB2bKhoMonths.length > 0) {
        return selectedB2bKhoMonths.some(m => m <= '2026-06');
    }
    return true;
}

function rebuildB2bFilters() {
    if (!state.khoGxtData || !state.gtcB2bData) return;
    
    // 1. Vùng Filter
    const hasOldData = checkHasOldDataForB2bFilter();
    const regions = getAvailableRegionsForPeriod(hasOldData);
    const menuVung = document.getElementById('menu-gtc-b2b-vung-region');
    if (menuVung) {
        const currentlyChecked = selectedB2bVungRegions;
        menuVung.innerHTML = regions.map(val => {
            const isChecked = currentlyChecked.includes(val);
            return `
                <div class="ghn-filter-item">
                    <input type="checkbox" id="chk-b2b-vung-region-${val}" value="${val}" ${isChecked ? 'checked' : ''} onchange="window.updateB2bFilterSelection('vung-region', '${val}', this.checked)">
                    <label for="chk-b2b-vung-region-${val}">${val}</label>
                </div>
            `;
        }).join('');
        selectedB2bVungRegions = selectedB2bVungRegions.filter(r => regions.includes(r));
        updateB2bLabels('vung-region', selectedB2bVungRegions);
    }
    
    // 2. Kho Region Filter
    const hasOldDataKho = checkHasOldDataForB2bKhoFilter();
    const regionsKho = getAvailableRegionsForPeriod(hasOldDataKho);
    const menuKho = document.getElementById('menu-gtc-b2b-kho-region');
    if (menuKho) {
        const currentlyChecked = selectedB2bKhoRegions;
        menuKho.innerHTML = regionsKho.map(val => {
            const isChecked = currentlyChecked.includes(val);
            return `
                <div class="ghn-filter-item">
                    <input type="checkbox" id="chk-b2b-kho-region-${val}" value="${val}" ${isChecked ? 'checked' : ''} onchange="window.updateB2bFilterSelection('kho-region', '${val}', this.checked)">
                    <label for="chk-b2b-kho-region-${val}">${val}</label>
                </div>
            `;
        }).join('');
        selectedB2bKhoRegions = selectedB2bKhoRegions.filter(r => regionsKho.includes(r));
        updateB2bLabels('kho-region', selectedB2bKhoRegions);
    }
    
    // 3. Detail Region Filter
    let hasOldDataDetail = true;
    if (selectedB2bDetailDays.length > 0) {
        hasOldDataDetail = selectedB2bDetailDays.some(d => d <= '2026-06-30');
    } else if (selectedB2bDetailMonths.length > 0) {
        hasOldDataDetail = selectedB2bDetailMonths.some(m => m <= '2026-06');
    }
    const regionsDetail = getAvailableRegionsForPeriod(hasOldDataDetail);
    const drSelect = document.getElementById('filter-b2b-detail-region');
    if (drSelect) {
        const currentVal = drSelect.value;
        drSelect.innerHTML = '<option value="">Tất cả Vùng</option>' + regionsDetail.map(r => `<option value="${r}">${r}</option>`).join('');
        if (regionsDetail.includes(currentVal)) {
            drSelect.value = currentVal;
        } else {
            selectedB2bDetailRegion = '';
            drSelect.value = '';
        }
    }
}

function populateGtcB2bPrioFilters() {
    if (b2bFiltersPopulated || !state.gtcB2bData || !state.gtcB2bData.length) return;
    
    // 1. Days and Months from Data GTC Kho B2B
    const days = [...new Set(state.gtcB2bData.map(r => parseDateToYmd(r['time_view'])).filter(Boolean))].sort().reverse();
    const months = [...new Set(days.map(d => getMonthFromYmd(d)).filter(Boolean))].sort().reverse();
    
    // Add checkboxes to dropdown menus
    buildMultiselectMenu('vung-day', days);
    buildMultiselectMenu('vung-month', months);
    buildMultiselectMenu('kho-day', days);
    buildMultiselectMenu('kho-month', months);
    
    // Detailed data Days and Months
    const detailDays = [...new Set((state.donB2bData || []).map(r => parseDateToYmd(r['Ngày ưu tiên'])).filter(Boolean))].sort().reverse();
    const detailMonths = [...new Set(detailDays.map(d => getMonthFromYmd(d)).filter(Boolean))].sort().reverse();
    buildMultiselectMenu('detail-day', detailDays);
    buildMultiselectMenu('detail-month', detailMonths);
    
    // 2. Regions & Warehouses
    const regions = [...new Set((state.khoGxtData || []).map(r => (r['Vùng'] || r['vung'] || '').trim()).filter(Boolean))].sort();
    const warehouses = [...new Set(state.gtcB2bData.map(r => r['warehouse_name']).filter(Boolean))].sort();
    
    // Populate Region checkbox dropdowns
    buildMultiselectMenu('vung-region', regions);
    buildMultiselectMenu('kho-region', regions);
    buildMultiselectMenu('kho-warehouse', warehouses);
    
    // Populate Detail Filters
    const drSelect = document.getElementById('filter-b2b-detail-region');
    const dwSelect = document.getElementById('filter-b2b-detail-warehouse');
    const deSelect = document.getElementById('filter-b2b-detail-error');
    if (drSelect) {
        drSelect.innerHTML = '<option value="">Tất cả Vùng</option>' + regions.map(r => `<option value="${r}">${r}</option>`).join('');
    }
    if (dwSelect) {
        dwSelect.innerHTML = '<option value="">Tất cả Kho</option>' + warehouses.map(w => `<option value="${w}">${w}</option>`).join('');
    }
    if (deSelect) {
        const errors = [...new Set((state.donB2bData || []).map(r => r['Nhóm lỗi']).filter(Boolean))].sort();
        deSelect.innerHTML = '<option value="">Tất cả Trạng thái/Lỗi</option>' + errors.map(e => `<option value="${e}">${e}</option>`).join('');
    }
    
    b2bFiltersPopulated = true;
}

function buildMultiselectMenu(mode, list) {
    const menu = document.getElementById('menu-gtc-b2b-' + mode);
    if (!menu) return;
    menu.innerHTML = list.map(val => {
        let labelText = val;
        if (mode.endsWith('month')) labelText = 'Tháng ' + val;
        else if (mode.endsWith('warehouse')) labelText = shortKho(val);
        return `
            <div class="ghn-filter-item">
                <input type="checkbox" id="chk-b2b-${mode}-${val}" value="${val}" onchange="window.updateB2bFilterSelection('${mode}', '${val}', this.checked)">
                <label for="chk-b2b-${mode}-${val}">${labelText}</label>
            </div>
        `;
    }).join('');
}

function renderGtcB2bPrioSection() {
    const sec = document.getElementById('section-gtc-b2b-prio');
    if (!sec || sec.classList.contains('active') === false) return;
    
    populateGtcB2bPrioFilters();
    
    if (b2bActiveTab === 'vung') {
        renderGtcB2bVung();
    } else if (b2bActiveTab === 'kho') {
        renderGtcB2bKho();
    } else if (b2bActiveTab === 'detail') {
        renderB2bDetailedTable();
    }
}

// ----------------------------------------------------
// TAB 1: GTC VÙNG
// ----------------------------------------------------
function renderGtcB2bVung() {
    let rawData = state.gtcB2bData || [];
    
    // Apply filters for the table
    if (selectedB2bVungDays.length > 0) {
        rawData = rawData.filter(r => selectedB2bVungDays.includes(parseDateToYmd(r['time_view'])));
    }
    if (selectedB2bVungMonths.length > 0) {
        rawData = rawData.filter(r => selectedB2bVungMonths.includes(getMonthFromYmd(parseDateToYmd(r['time_view']))));
    }
    if (selectedB2bVungRegions.length > 0) {
        rawData = rawData.filter(r => selectedB2bVungRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
    }
    
    // Group by Region + time_view for table
    const groups = {};
    rawData.forEach(row => {
        const warehouse = row['warehouse_name'] || '';
        const region = getRegionForWarehouse(warehouse, row['time_view']);
        const ymd = parseDateToYmd(row['time_view']);
        const timeKey = (selectedB2bVungMonths.length > 0 && selectedB2bVungDays.length === 0) ? getMonthFromYmd(ymd) : ymd;
        const key = `${region}|${timeKey}`;
        
        if (!groups[key]) {
            groups[key] = {
                region: region,
                timeLabel: timeKey,
                totalPriority: 0,
                totalErrors: 0
            };
        }
        
        const count = parseInt(row['Số đơn ưu tiên']) || 0;
        const errors = parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
        groups[key].totalPriority += count;
        groups[key].totalErrors += errors;
    });
    
    const rows = Object.values(groups).sort((a, b) => {
        if (a.region !== b.region) return a.region.localeCompare(b.region);
        return b.timeLabel.localeCompare(a.timeLabel);
    });
    
    // 1. Calculate overview statistics per region *FOR LATEST DAY*
    const availableDays = [...new Set((state.gtcB2bData || []).map(r => parseDateToYmd(r['time_view'])).filter(Boolean))].sort();
    const defaultLatestDay = availableDays[availableDays.length - 1] || '';
    
    let cardDay = defaultLatestDay;
    if (selectedB2bVungDays.length > 0) {
        cardDay = [...selectedB2bVungDays].sort().reverse()[0];
    } else if (selectedB2bVungMonths.length > 0) {
        const daysInMonths = availableDays.filter(d => selectedB2bVungMonths.includes(getMonthFromYmd(d)));
        if (daysInMonths.length > 0) {
            cardDay = daysInMonths.sort().reverse()[0];
        }
    }
    
    let cardData = (state.gtcB2bData || []).filter(r => parseDateToYmd(r['time_view']) === cardDay);
    if (selectedB2bVungRegions.length > 0) {
        cardData = cardData.filter(r => selectedB2bVungRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
    }
    
    const cardRegionStats = {};
    let cardTotalPriorityGlobal = 0;
    let cardTotalErrorsGlobal = 0;
    
    cardData.forEach(row => {
        const region = getRegionForWarehouse(row['warehouse_name'], row['time_view']);
        if (!cardRegionStats[region]) {
            cardRegionStats[region] = {
                totalPriority: 0,
                totalErrors: 0
            };
        }
        const count = parseInt(row['Số đơn ưu tiên']) || 0;
        const errors = parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
        
        cardRegionStats[region].totalPriority += count;
        cardRegionStats[region].totalErrors += errors;
        
        cardTotalPriorityGlobal += count;
        cardTotalErrorsGlobal += errors;
    });
    
    const cardRegionList = Object.keys(cardRegionStats).map(name => {
        const stats = cardRegionStats[name];
        const gtcRate = stats.totalPriority > 0 ? (stats.totalPriority - stats.totalErrors) / stats.totalPriority : 0;
        return {
            name: name,
            totalPriority: stats.totalPriority,
            totalErrors: stats.totalErrors,
            gtcRate: gtcRate
        };
    });
    
    const totalRegions = cardRegionList.length;
    let highestGtcRegion = '--';
    let highestGtcVal = -1;
    let lowestGtcRegion = '--';
    let lowestGtcVal = 999;
    let highestErrorRegion = '--';
    let highestErrorVal = -1;
    
    cardRegionList.forEach(r => {
        if (r.gtcRate > highestGtcVal) {
            highestGtcVal = r.gtcRate;
            highestGtcRegion = r.name;
        }
        if (r.gtcRate < lowestGtcVal) {
            lowestGtcVal = r.gtcRate;
            lowestGtcRegion = r.name;
        }
        if (r.totalErrors > highestErrorVal) {
            highestErrorVal = r.totalErrors;
            highestErrorRegion = r.name;
        }
    });
    
    const avgGtcGlobal = cardTotalPriorityGlobal > 0 ? ((cardTotalPriorityGlobal - cardTotalErrorsGlobal) / cardTotalPriorityGlobal * 100).toFixed(2) : '0.00';
    const displayDateStr = cardDay ? cardDay : 'Chưa có';
    
    const cardsContainer = document.getElementById('overview-b2b-vung-cards');
    if (cardsContainer) {
        cardsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon blue"><i class="fa-solid fa-map"></i></div>
                <div class="stat-details">
                    <h3>Tổng Vùng</h3>
                    <h2>${totalRegions} Vùng</h2>
                    <p class="stat-sub">Có dữ liệu (${displayDateStr})</p>
                </div>
            </div>
            <div class="stat-card green-card">
                <div class="stat-icon green"><i class="fa-solid fa-circle-check"></i></div>
                <div class="stat-details">
                    <h3>GTC Cao Nhất</h3>
                    <h2>${highestGtcRegion}</h2>
                    <p class="stat-sub text-green">${highestGtcVal >= 0 ? (highestGtcVal * 100).toFixed(1) + '%' : '--'} (${displayDateStr})</p>
                </div>
            </div>
            <div class="stat-card red-card">
                <div class="stat-icon red"><i class="fa-solid fa-triangle-exclamation"></i></div>
                <div class="stat-details">
                    <h3>GTC Thấp Nhất</h3>
                    <h2>${lowestGtcRegion}</h2>
                    <p class="stat-sub text-danger">${lowestGtcVal < 999 ? (lowestGtcVal * 100).toFixed(1) + '%' : '--'} (${displayDateStr})</p>
                </div>
            </div>
            <div class="stat-card orange-card">
                <div class="stat-icon orange"><i class="fa-solid fa-circle-xmark"></i></div>
                <div class="stat-details">
                    <h3>Lỗi Cao Nhất</h3>
                    <h2>${highestErrorRegion}</h2>
                    <p class="stat-sub text-warning">${highestErrorVal >= 0 ? highestErrorVal + ' lỗi' : '--'} (${displayDateStr})</p>
                </div>
            </div>
            <div class="stat-card purple-card">
                <div class="stat-icon purple"><i class="fa-solid fa-chart-line"></i></div>
                <div class="stat-details">
                    <h3>GTC Trung Bình</h3>
                    <h2 style="color:var(--purple);">${avgGtcGlobal}%</h2>
                    <p class="stat-sub">Toàn vùng (${displayDateStr})</p>
                </div>
            </div>
        `;
    }
    
    // 2. Alert Box
    const alertBox = document.getElementById('alert-b2b-vung');
    if (alertBox) {
        if (lowestGtcVal < 999 && highestErrorVal >= 0) {
            alertBox.style.display = 'block';
            alertBox.innerHTML = `
                <div style="background:#FFF9DB; border:1px solid #FFEC99; border-radius:12px; padding:18px 24px; color:var(--text1); font-size:0.9rem; line-height:1.6; box-shadow:var(--shadow-sm);">
                    <div style="display:flex; align-items:center; gap:8px; font-weight:700; margin-bottom:8px; color:#F08C00;">
                        <i class="fa-solid fa-triangle-exclamation" style="font-size:1.1rem;"></i> CẢNH BÁO & ĐỀ XUẤT HÀNH ĐỘNG VÙNG (${displayDateStr})
                    </div>
                    <div>
                        <strong>⚠️ Cảnh báo:</strong> Vùng <span style="color:var(--red); font-weight:700;">${lowestGtcRegion}</span> đang có tỷ lệ GTC B2B ưu tiên thấp nhất ngày ${displayDateStr}, đạt <span style="font-weight:700;">${(lowestGtcVal * 100).toFixed(1)}%</span>. Đồng thời phát sinh <span style="font-weight:700; color:var(--red);">${highestErrorVal}</span> lỗi B2B. Cần rà soát các kho kéo giảm GTC, kiểm tra backlog, lỗi xử lý đơn B2B và năng lực giao trong ngày.
                    </div>
                    <div style="margin-top:10px;">
                        <strong>🛠️ Đề xuất:</strong>
                        <ul style="margin:6px 0 0 18px; padding:0; list-style-type:disc;">
                            <li>Rà soát kho có tỷ lệ GTC thấp trong vùng.</li>
                            <li>Kiểm tra các lỗi B2B phát sinh.</li>
                            <li>Ưu tiên xử lý đơn B2B tồn, đơn gần SLA và đơn lỗi.</li>
                            <li>Yêu cầu Team Lead vùng cập nhật nguyên nhân và hướng xử lý.</li>
                        </ul>
                    </div>
                </div>
            `;
        } else {
            alertBox.style.display = 'none';
        }
    }
    
    // 3. Render Table
    const tbody = document.getElementById('tbody-b2b-vung');
    if (tbody) {
        if (rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--text3)">Không có dữ liệu phù hợp bộ lọc.</td></tr>';
        } else {
            tbody.innerHTML = rows.map(r => {
                const total = r.totalPriority;
                const errors = r.totalErrors;
                const gtc = total - errors;
                const gtcPct = total > 0 ? (gtc / total * 100) : 0;
                const errorPct = total > 0 ? (errors / total * 100) : 0;
                
                let evaluation = 'Tốt';
                let evalClass = 'badge green';
                if (gtcPct < 75) {
                    evaluation = 'Cảnh báo';
                    evalClass = 'badge red';
                } else if (gtcPct < 85) {
                    evaluation = 'Cần theo dõi';
                    evalClass = 'badge orange';
                }
                
                const alertText = gtcPct < 75 ? '⚠️ GTC thấp' : 'Ổn định';
                const actionText = gtcPct < 75 ? 'Tăng xe, ưu tiên giao' : (gtcPct < 85 ? 'Theo dõi backlog' : 'Duy trì');
                
                return `
                    <tr>
                        <td style="font-weight:600; color:var(--text1);">${escapeHtml(r.region)}</td>
                        <td>${escapeHtml(r.timeLabel)}</td>
                        <td style="text-align:right">${total}</td>
                        <td style="text-align:right">${gtc}</td>
                        <td style="text-align:right; font-weight:700; color:${gtcPct < 85 ? 'var(--red)' : 'var(--green)'}">${gtcPct.toFixed(2)}%</td>
                        <td style="text-align:right">${errors}</td>
                        <td style="text-align:right; color:${errors > 0 ? 'var(--red)' : 'inherit'}">${errorPct.toFixed(2)}%</td>
                        <td><span class="${evalClass}">${evaluation}</span></td>
                        <td>${alertText}</td>
                        <td>${actionText}</td>
                    </tr>
                `;
            }).join('');
        }
    }
    
    // 4. Extract data for chart
    let chartDataList = [];
    let latestTimeLabel = '';
    if (b2bChartTab === 'day') {
        if (availableDays.length > 0) {
            const latestDay = availableDays[availableDays.length - 1];
            let rawChart = (state.gtcB2bData || []).filter(r => parseDateToYmd(r['time_view']) === latestDay);
            if (selectedB2bVungRegions.length > 0) {
                rawChart = rawChart.filter(r => selectedB2bVungRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
            }
            latestTimeLabel = 'Ngày ' + latestDay;
            chartDataList = rawChart;
        }
    } else {
        const availableMonths = [...new Set(availableDays.map(getMonthFromYmd).filter(Boolean))].sort();
        if (availableMonths.length > 0) {
            const latestMonth = availableMonths[availableMonths.length - 1];
            let rawChart = (state.gtcB2bData || []).filter(r => getMonthFromYmd(parseDateToYmd(r['time_view'])) === latestMonth);
            if (selectedB2bVungRegions.length > 0) {
                rawChart = rawChart.filter(r => selectedB2bVungRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
            }
            latestTimeLabel = 'Tháng ' + latestMonth;
            chartDataList = rawChart;
        }
    }
    
    const chartGroups = {};
    chartDataList.forEach(row => {
        const region = getRegionForWarehouse(row['warehouse_name'], row['time_view']);
        if (!chartGroups[region]) {
            chartGroups[region] = {
                name: region,
                totalPriority: 0,
                totalErrors: 0
            };
        }
        chartGroups[region].totalPriority += parseInt(row['Số đơn ưu tiên']) || 0;
        chartGroups[region].totalErrors += parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
    });
    
    const finalChartData = Object.values(chartGroups).map(g => {
        g.gtcRate = g.totalPriority > 0 ? (g.totalPriority - g.totalErrors) / g.totalPriority : 0;
        return g;
    }).sort((a, b) => a.name.localeCompare(b.name));
    
    // Update chart headers
    const rateHeader = document.getElementById('title-b2b-vung-rate');
    if (rateHeader) rateHeader.innerHTML = `<i class="fa-solid fa-chart-pie"></i> % GTC theo Vùng - ${latestTimeLabel}`;
    
    const errHeader = document.getElementById('title-b2b-vung-errors');
    if (errHeader) errHeader.innerHTML = `<i class="fa-solid fa-circle-exclamation" style="color:var(--yellow)"></i> Đơn lỗi theo Vùng - ${latestTimeLabel}`;
    
    renderB2bRegionCharts(finalChartData);
}

function renderB2bRegionCharts(dataList) {
    destroyChart('gtcB2bVungRate');
    destroyChart('gtcB2bVungErrors');
    
    const canvasRate = document.getElementById('chart-gtc-b2b-vung-rate');
    const canvasErrors = document.getElementById('chart-gtc-b2b-vung-errors');
    if (!dataList.length) return;
    
    const labels = dataList.map(r => r.name);
    const gtcRates = dataList.map(r => parseFloat((r.gtcRate * 100).toFixed(1)));
    const errorCounts = dataList.map(r => r.totalErrors);
    
    const regionColorsList = [
        'rgba(12, 166, 120, 0.85)', // teal
        'rgba(34, 139, 230, 0.85)', // royal blue
        'rgba(26, 188, 156, 0.85)', // light green/teal
        'rgba(51, 154, 240, 0.85)', // light blue
        'rgba(20, 110, 120, 0.85)', // dark teal blue
        'rgba(18, 184, 134, 0.85)'  // minty green
    ];
    
    if (canvasRate) {
        const ctx = canvasRate.getContext('2d');
        charts.gtcB2bVungRate = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Tỷ lệ GTC B2B (%)',
                    data: gtcRates,
                    backgroundColor: labels.map((_, idx) => regionColorsList[idx % regionColorsList.length]),
                    borderColor: labels.map((_, idx) => regionColorsList[idx % regionColorsList.length].replace('0.85', '1.0')),
                    borderWidth: 1.5,
                    barThickness: 24,
                    maxBarThickness: 32,
                    datalabels: {
                        display: true,
                        anchor: 'end',
                        align: 'top',
                        color: () => document.documentElement.classList.contains('light-mode') ? '#1E2937' : '#FFFFFF',
                        font: { weight: 'bold', size: 10 },
                        formatter: v => v + '%'
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    datalabels: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const raw = dataList[context.dataIndex];
                                return [
                                    `Tỷ lệ GTC B2B: ${(raw.gtcRate * 100).toFixed(1)}%`,
                                    `Tổng đơn B2B: ${raw.totalPriority} đơn`,
                                    `Tổng GTC B2B: ${raw.totalPriority - raw.totalErrors} đơn`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'category',
                        ticks: { font: { size: 10 } }
                    },
                    y: {
                        min: 0,
                        max: 105,
                        title: { display: true, text: 'Tỷ lệ GTC (%)', font: { size: 11 } }
                    }
                }
            }
        });
    }
    
    if (canvasErrors) {
        const ctx = canvasErrors.getContext('2d');
        charts.gtcB2bVungErrors = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Đơn lỗi B2B (đơn)',
                    data: errorCounts,
                    backgroundColor: 'rgba(255, 193, 7, 0.85)', // màu vàng
                    borderColor: 'rgb(255, 193, 7)',
                    borderWidth: 1.5,
                    barThickness: 24,
                    maxBarThickness: 32,
                    datalabels: {
                        display: true,
                        anchor: 'end',
                        align: 'top',
                        color: () => document.documentElement.classList.contains('light-mode') ? '#C62828' : '#FF8F8F',
                        font: { weight: 'bold', size: 10 },
                        formatter: v => v
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    datalabels: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Số đơn lỗi: ${context.raw} đơn`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'category',
                        ticks: { font: { size: 10 } }
                    },
                    y: {
                        beginAtZero: true,
                        grace: '10%',
                        ticks: { stepSize: 1 },
                        title: { display: true, text: 'Đơn lỗi (đơn)', font: { size: 11 } }
                    }
                }
            }
        });
    }
}

// ----------------------------------------------------
// TAB 2: GTC KHO
// ----------------------------------------------------
function renderGtcB2bKho() {
    let rawData = state.gtcB2bData || [];
    
    // Apply filters
    if (selectedB2bKhoDays.length > 0) {
        rawData = rawData.filter(r => selectedB2bKhoDays.includes(parseDateToYmd(r['time_view'])));
    }
    if (selectedB2bKhoMonths.length > 0) {
        rawData = rawData.filter(r => selectedB2bKhoMonths.includes(getMonthFromYmd(parseDateToYmd(r['time_view']))));
    }
    if (selectedB2bKhoRegions.length > 0) {
        rawData = rawData.filter(r => selectedB2bKhoRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
    }
    if (selectedB2bKhoWarehouses.length > 0) {
        rawData = rawData.filter(r => selectedB2bKhoWarehouses.includes(r['warehouse_name']));
    }
    
    const groups = {};
    rawData.forEach(row => {
        const warehouse = row['warehouse_name'] || '';
        const region = getRegionForWarehouse(warehouse, row['time_view']);
        const ymd = parseDateToYmd(row['time_view']);
        const timeKey = (selectedB2bKhoMonths.length > 0 && selectedB2bKhoDays.length === 0) ? getMonthFromYmd(ymd) : ymd;
        const key = `${warehouse}|${timeKey}`;
        
        if (!groups[key]) {
            groups[key] = {
                warehouse: warehouse,
                region: region,
                timeLabel: timeKey,
                totalPriority: 0,
                totalErrors: 0
            };
        }
        
        const count = parseInt(row['Số đơn ưu tiên']) || 0;
        const errors = parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
        groups[key].totalPriority += count;
        groups[key].totalErrors += errors;
    });
    
    // Sort primarily by timeLabel descending, secondarily by warehouse alphabetical ascending
    const rows = Object.values(groups).sort((a, b) => {
        const timeCompare = b.timeLabel.localeCompare(a.timeLabel);
        if (timeCompare !== 0) return timeCompare;
        return a.warehouse.localeCompare(b.warehouse);
    });
    
    // 1. Calculate overview statistics per warehouse *FOR LATEST DAY* (or filtered day)
    const availableDays = [...new Set((state.gtcB2bData || []).map(r => parseDateToYmd(r['time_view'])).filter(Boolean))].sort();
    const defaultLatestDay = availableDays[availableDays.length - 1] || '';
    
    let cardDay = defaultLatestDay;
    if (selectedB2bKhoDays.length > 0) {
        cardDay = [...selectedB2bKhoDays].sort().reverse()[0];
    } else if (selectedB2bKhoMonths.length > 0) {
        const daysInMonths = availableDays.filter(d => selectedB2bKhoMonths.includes(getMonthFromYmd(d)));
        if (daysInMonths.length > 0) {
            cardDay = daysInMonths.sort().reverse()[0];
        }
    }
    
    let cardData = (state.gtcB2bData || []).filter(r => parseDateToYmd(r['time_view']) === cardDay);
    if (selectedB2bKhoRegions.length > 0) {
        cardData = cardData.filter(r => selectedB2bKhoRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
    }
    if (selectedB2bKhoWarehouses.length > 0) {
        cardData = cardData.filter(r => selectedB2bKhoWarehouses.includes(r['warehouse_name']));
    }
    
    const warehouseStats = {};
    let totalPriorityGlobal = 0;
    let totalErrorsGlobal = 0;
    
    cardData.forEach(row => {
        const warehouse = row['warehouse_name'] || '';
        const region = getRegionForWarehouse(warehouse, row['time_view']);
        if (!warehouseStats[warehouse]) {
            warehouseStats[warehouse] = {
                name: warehouse,
                region: region,
                totalPriority: 0,
                totalErrors: 0
            };
        }
        const count = parseInt(row['Số đơn ưu tiên']) || 0;
        const errors = parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
        
        warehouseStats[warehouse].totalPriority += count;
        warehouseStats[warehouse].totalErrors += errors;
        
        totalPriorityGlobal += count;
        totalErrorsGlobal += errors;
    });
    
    const warehouseList = Object.values(warehouseStats).map(w => {
        w.gtcRate = w.totalPriority > 0 ? (w.totalPriority - w.totalErrors) / w.totalPriority : 0;
        return w;
    });
    
    // 1. Update Cards
    const totalWarehouses = warehouseList.length;
    let highestGtcKho = '--';
    let highestGtcVal = -1;
    let lowestGtcKho = '--';
    let lowestGtcVal = 999;
    let highestErrorKho = '--';
    let highestErrorVal = -1;
    
    warehouseList.forEach(w => {
        if (w.gtcRate > highestGtcVal) {
            highestGtcVal = w.gtcRate;
            highestGtcKho = w.name;
        }
        if (w.gtcRate < lowestGtcVal) {
            lowestGtcVal = w.gtcRate;
            lowestGtcKho = w.name;
        }
        if (w.totalErrors > highestErrorVal) {
            highestErrorVal = w.totalErrors;
            highestErrorKho = w.name;
        }
    });
    
    const avgGtcGlobal = totalPriorityGlobal > 0 ? ((totalPriorityGlobal - totalErrorsGlobal) / totalPriorityGlobal * 100).toFixed(2) : '0.00';
    
    const cardsContainer = document.getElementById('overview-b2b-kho-cards');
    if (cardsContainer) {
        cardsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon blue"><i class="fa-solid fa-warehouse"></i></div>
                <div class="stat-details">
                    <h3>Tổng Kho</h3>
                    <h2>${totalWarehouses} Kho</h2>
                    <p class="stat-sub">Ngày ${cardDay}</p>
                </div>
            </div>
            <div class="stat-card green-card">
                <div class="stat-icon green"><i class="fa-solid fa-circle-check"></i></div>
                <div class="stat-details">
                    <h3>GTC Cao Nhất</h3>
                    <h2>${shortKho(highestGtcKho)}</h2>
                    <p class="stat-sub text-green">${highestGtcVal >= 0 ? (highestGtcVal * 100).toFixed(1) + '%' : '--'} (Ngày ${cardDay})</p>
                </div>
            </div>
            <div class="stat-card red-card">
                <div class="stat-icon red"><i class="fa-solid fa-triangle-exclamation"></i></div>
                <div class="stat-details">
                    <h3>GTC Thấp Nhất</h3>
                    <h2>${shortKho(lowestGtcKho)}</h2>
                    <p class="stat-sub text-danger">${lowestGtcVal < 999 ? (lowestGtcVal * 100).toFixed(1) + '%' : '--'} (Ngày ${cardDay})</p>
                </div>
            </div>
            <div class="stat-card orange-card">
                <div class="stat-icon orange"><i class="fa-solid fa-circle-xmark"></i></div>
                <div class="stat-details">
                    <h3>Lỗi Cao Nhất</h3>
                    <h2>${shortKho(highestErrorKho)}</h2>
                    <p class="stat-sub text-warning">${highestErrorVal >= 0 ? highestErrorVal + ' lỗi' : '--'} (Ngày ${cardDay})</p>
                </div>
            </div>
            <div class="stat-card purple-card">
                <div class="stat-icon purple"><i class="fa-solid fa-chart-line"></i></div>
                <div class="stat-details">
                    <h3>GTC Trung Bình</h3>
                    <h2 style="color:var(--purple);">${avgGtcGlobal}%</h2>
                    <p class="stat-sub">Ngày ${cardDay}</p>
                </div>
            </div>
        `;
    }
    
    // 2. Alert Box GTC Kho
    const alertBox = document.getElementById('alert-b2b-kho');
    if (alertBox) {
        if (lowestGtcVal < 999 && highestErrorVal >= 0) {
            alertBox.style.display = 'block';
            alertBox.innerHTML = `
                <div style="background:#FFF9DB; border:1px solid #FFEC99; border-radius:12px; padding:18px 24px; color:var(--text1); font-size:0.9rem; line-height:1.6; box-shadow:var(--shadow-sm);">
                    <div style="display:flex; align-items:center; gap:8px; font-weight:700; margin-bottom:8px; color:#F08C00;">
                        <i class="fa-solid fa-triangle-exclamation" style="font-size:1.1rem;"></i> CẢNH BÁO & ĐỀ XUẤT HÀNH ĐỘNG KHO
                    </div>
                    <div>
                        <strong>⚠️ Cảnh báo:</strong> Kho <span style="color:var(--red); font-weight:700;">${escapeHtml(lowestGtcKho)}</span> đang có tỷ lệ GTC B2B ưu tiên thấp, đạt <span style="font-weight:700;">${(lowestGtcVal * 100).toFixed(1)}%</span>. Kho phát sinh <span style="font-weight:700; color:var(--red);">${highestErrorVal}</span> lỗi đơn B2B, cao nhất trong danh sách. Cần kiểm tra nguyên nhân, rà soát đơn lỗi và xử lý các đơn B2B ưu tiên trong ngày.
                    </div>
                    <div style="margin-top:10px;">
                        <strong>🛠️ Đề xuất:</strong>
                        <ul style="margin:6px 0 0 18px; padding:0; list-style-type:disc;">
                            <li>Rà soát danh sách đơn B2B lỗi.</li>
                            <li>Kiểm tra đơn tồn, đơn chưa giao, đơn trả/hẹn nếu có.</li>
                            <li>Ưu tiên xử lý đơn B2B còn khả năng giao trong ngày.</li>
                            <li>Nếu kho thiếu xe hoặc nhân sự, báo Vận Hành Vùng để hỗ trợ.</li>
                            <li>Cập nhật nguyên nhân và hướng xử lý trước 16h.</li>
                        </ul>
                    </div>
                </div>
            `;
        } else {
            alertBox.style.display = 'none';
        }
    }
    
    // 3. Render Table
    const tbody = document.getElementById('tbody-b2b-kho');
    if (tbody) {
        if (rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:30px;color:var(--text3)">Không có dữ liệu phù hợp bộ lọc.</td></tr>';
        } else {
            tbody.innerHTML = rows.map(r => {
                const total = r.totalPriority;
                const errors = r.totalErrors;
                const gtc = total - errors;
                const gtcPct = total > 0 ? (gtc / total * 100) : 0;
                const errorPct = total > 0 ? (errors / total * 100) : 0;
                
                let evaluation = 'Tốt';
                let evalClass = 'badge green';
                if (gtcPct < 75) {
                    evaluation = 'Cảnh báo';
                    evalClass = 'badge red';
                } else if (gtcPct < 85) {
                    evaluation = 'Cần theo dõi';
                    evalClass = 'badge orange';
                }
                
                const alertText = gtcPct < 75 ? '⚠️ GTC thấp' : 'Ổn định';
                const actionText = gtcPct < 75 ? 'Báo động đỏ, tăng cường xe' : (gtcPct < 85 ? 'Xem chi tiết đơn B2B' : 'Duy trì');
                
                return `
                    <tr>
                        <td style="font-weight:600; color:var(--text1);">${escapeHtml(shortKho(r.warehouse))}</td>
                        <td>${escapeHtml(r.region)}</td>
                        <td>${escapeHtml(r.timeLabel)}</td>
                        <td style="text-align:right">${total}</td>
                        <td style="text-align:right">${gtc}</td>
                        <td style="text-align:right; font-weight:700; color:${gtcPct < 85 ? 'var(--red)' : 'var(--green)'}">${gtcPct.toFixed(2)}%</td>
                        <td style="text-align:right">${errors}</td>
                        <td style="text-align:right; color:${errors > 0 ? 'var(--red)' : 'inherit'}">${errorPct.toFixed(2)}%</td>
                        <td><span class="${evalClass}">${evaluation}</span></td>
                        <td>${alertText}</td>
                        <td>${actionText}</td>
                    </tr>
                `;
            }).join('');
        }
    }
    
    // 4. Extract data for Kho charts
    let chartDataList = [];
    let latestTimeLabel = '';
    
    if (b2bKhoChartTab === 'day') {
        if (availableDays.length > 0) {
            const latestDay = availableDays[availableDays.length - 1];
            let rawChart = (state.gtcB2bData || []).filter(r => parseDateToYmd(r['time_view']) === latestDay);
            if (selectedB2bKhoRegions.length > 0) {
                rawChart = rawChart.filter(r => selectedB2bKhoRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
            }
            if (selectedB2bKhoWarehouses.length > 0) {
                rawChart = rawChart.filter(r => selectedB2bKhoWarehouses.includes(r['warehouse_name']));
            }
            latestTimeLabel = 'Ngày ' + latestDay;
            chartDataList = rawChart;
        }
    } else {
        const availableMonths = [...new Set(availableDays.map(getMonthFromYmd).filter(Boolean))].sort();
        if (availableMonths.length > 0) {
            const latestMonth = availableMonths[availableMonths.length - 1];
            let rawChart = (state.gtcB2bData || []).filter(r => getMonthFromYmd(parseDateToYmd(r['time_view'])) === latestMonth);
            if (selectedB2bKhoRegions.length > 0) {
                rawChart = rawChart.filter(r => selectedB2bKhoRegions.includes(getRegionForWarehouse(r['warehouse_name'], r['time_view'])));
            }
            if (selectedB2bKhoWarehouses.length > 0) {
                rawChart = rawChart.filter(r => selectedB2bKhoWarehouses.includes(r['warehouse_name']));
            }
            latestTimeLabel = 'Tháng ' + latestMonth;
            chartDataList = rawChart;
        }
    }
    
    const chartGroups = {};
    chartDataList.forEach(row => {
        const warehouse = row['warehouse_name'] || '';
        const region = getRegionForWarehouse(warehouse, row['time_view']);
        if (!chartGroups[warehouse]) {
            chartGroups[warehouse] = {
                name: warehouse,
                region: region,
                totalPriority: 0,
                totalErrors: 0
            };
        }
        chartGroups[warehouse].totalPriority += parseInt(row['Số đơn ưu tiên']) || 0;
        chartGroups[warehouse].totalErrors += parseInt(row['Đơn ưu tiên chưa giao (lỗi vận hành )']) || 0;
    });
    
    const finalChartData = Object.values(chartGroups).map(w => {
        w.gtcRate = w.totalPriority > 0 ? (w.totalPriority - w.totalErrors) / w.totalPriority : 0;
        return w;
    });
    
    // Update GTC Kho chart headers
    const rateHeader = document.getElementById('title-b2b-kho-rate');
    if (rateHeader) rateHeader.innerHTML = `<i class="fa-solid fa-chart-bar"></i> % GTC theo Kho - ${latestTimeLabel}`;
    
    const errHeader = document.getElementById('title-b2b-kho-errors');
    if (errHeader) errHeader.innerHTML = `<i class="fa-solid fa-circle-exclamation" style="color:var(--yellow)"></i> Đơn lỗi theo Kho - ${latestTimeLabel}`;
    
    renderB2bWarehouseCharts(finalChartData);
}

function renderB2bWarehouseCharts(dataList) {
    destroyChart('gtcB2bKhoRate');
    destroyChart('gtcB2bKhoErrors');
    
    const canvasRate = document.getElementById('chart-gtc-b2b-kho-rate');
    const canvasErrors = document.getElementById('chart-gtc-b2b-kho-errors');
    if (!dataList.length) return;
    
    // Sort data for Rate chart (lowest GTC rate first)
    const sortedForRate = [...dataList].sort((a, b) => a.gtcRate - b.gtcRate);
    const labelsRate = sortedForRate.map(r => shortKho(r.name));
    const rates = sortedForRate.map(r => parseFloat((r.gtcRate * 100).toFixed(1)));
    
    // Sort data for Errors chart (highest error counts first)
    const sortedForErrors = [...dataList].sort((a, b) => b.totalErrors - a.totalErrors);
    const labelsErrors = sortedForErrors.map(r => shortKho(r.name));
    const errors = sortedForErrors.map(r => r.totalErrors);
    
    if (canvasRate) {
        const ctx = canvasRate.getContext('2d');
        charts.gtcB2bKhoRate = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labelsRate,
                datasets: [{
                    label: 'Tỷ lệ GTC B2B (%)',
                    data: rates,
                    backgroundColor: sortedForRate.map(r => r.gtcRate < 0.90 ? 'rgba(245, 54, 92, 0.85)' : 'rgba(12, 166, 120, 0.85)'),
                    borderColor: sortedForRate.map(r => r.gtcRate < 0.90 ? 'rgb(245, 54, 92)' : 'rgb(12, 166, 120)'),
                    borderWidth: 1.5,
                    barThickness: 14,
                    maxBarThickness: 20,
                    datalabels: {
                        display: true,
                        anchor: 'end',
                        align: 'right',
                        color: () => document.documentElement.classList.contains('light-mode') ? '#1E2937' : '#FFFFFF',
                        font: { weight: 'bold', size: 9 },
                        formatter: v => v + '%'
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y', // Horizontal bars
                plugins: {
                    legend: { display: false },
                    datalabels: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const raw = sortedForRate[context.dataIndex];
                                return [
                                    `Tỷ lệ GTC B2B: ${(raw.gtcRate * 100).toFixed(1)}%`,
                                    `Tổng đơn: ${raw.totalPriority} đơn`,
                                    `Tổng GTC: ${raw.totalPriority - raw.totalErrors} đơn`,
                                    `Đơn lỗi: ${raw.totalErrors} đơn`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        min: 0,
                        max: 105,
                        title: { display: true, text: 'Tỷ lệ GTC (%)', font: { size: 11 } }
                    },
                    y: {
                        type: 'category',
                        ticks: { font: { size: 10 } }
                    }
                }
            }
        });
    }
    
    if (canvasErrors) {
        const ctx = canvasErrors.getContext('2d');
        charts.gtcB2bKhoErrors = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labelsErrors,
                datasets: [{
                    label: 'Đơn lỗi B2B (đơn)',
                    data: errors,
                    backgroundColor: 'rgba(255, 193, 7, 0.85)', // màu vàng
                    borderColor: 'rgb(255, 193, 7)',
                    borderWidth: 1.5,
                    barThickness: 14,
                    maxBarThickness: 20,
                    datalabels: {
                        display: true,
                        anchor: 'end',
                        align: 'right',
                        color: () => document.documentElement.classList.contains('light-mode') ? '#C62828' : '#FF8F8F',
                        font: { weight: 'bold', size: 9 },
                        formatter: v => v
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y', // Horizontal bars
                plugins: {
                    legend: { display: false },
                    datalabels: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const raw = sortedForErrors[context.dataIndex];
                                return [
                                    `Đơn lỗi B2B: ${raw.totalErrors} đơn`,
                                    `Tổng đơn: ${raw.totalPriority} đơn`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grace: '10%',
                        ticks: { stepSize: 1 },
                        title: { display: true, text: 'Đơn lỗi (đơn)', font: { size: 11 } }
                    },
                    y: {
                        type: 'category',
                        ticks: { font: { size: 10 } }
                    }
                }
            }
        });
    }
}

// ----------------------------------------------------
// TAB 3: CHI TIẾT ĐƠN HÀNG B2B
// ----------------------------------------------------
function renderB2bDetailedTable() {
    let rawOrders = state.donB2bData || [];
    
    // Apply filters
    if (selectedB2bDetailDays.length > 0) {
        rawOrders = rawOrders.filter(r => selectedB2bDetailDays.includes(parseDateToYmd(r['Ngày ưu tiên'])));
    }
    if (selectedB2bDetailMonths.length > 0) {
        rawOrders = rawOrders.filter(r => selectedB2bDetailMonths.includes(getMonthFromYmd(parseDateToYmd(r['Ngày ưu tiên']))));
    }
    if (selectedB2bDetailRegion) {
        rawOrders = rawOrders.filter(r => getRegionForWarehouse(r['Kho hiện tại'], r['Ngày ưu tiên']) === selectedB2bDetailRegion);
    }
    if (selectedB2bDetailWarehouse) {
        rawOrders = rawOrders.filter(r => r['Kho hiện tại'] === selectedB2bDetailWarehouse);
    }
    if (selectedB2bDetailError) {
        rawOrders = rawOrders.filter(r => r['Nhóm lỗi'] === selectedB2bDetailError);
    }
    
    const errorCountByKho = {};
    const errorTypeCount = {};
    
    rawOrders.forEach(ord => {
        const kho = ord['Kho hiện tại'] || 'Chưa xác định';
        const errorType = ord['Nhóm lỗi'] || 'Chưa xác định';
        
        errorCountByKho[kho] = (errorCountByKho[kho] || 0) + 1;
        errorTypeCount[errorType] = (errorTypeCount[errorType] || 0) + 1;
    });
    
    let maxErrorKho = '--';
    let maxErrorKhoVal = 0;
    for (let k in errorCountByKho) {
        if (errorCountByKho[k] > maxErrorKhoVal) {
            maxErrorKhoVal = errorCountByKho[k];
            maxErrorKho = k;
        }
    }
    
    let maxErrorType = '--';
    let maxErrorTypeVal = 0;
    for (let t in errorTypeCount) {
        if (errorTypeCount[t] > maxErrorTypeVal) {
            maxErrorTypeVal = errorTypeCount[t];
            maxErrorType = t;
        }
    }
    
    const detailAlert = document.getElementById('alert-b2b-detail');
    if (detailAlert) {
        if (maxErrorKhoVal > 0) {
            detailAlert.style.display = 'block';
            detailAlert.innerHTML = `
                <div style="background:#FFF0F6; border:1px solid #FFD8E6; border-radius:12px; padding:18px 24px; color:var(--text1); font-size:0.9rem; line-height:1.6; box-shadow:var(--shadow-sm);">
                    <div style="display:flex; align-items:center; gap:8px; font-weight:700; margin-bottom:8px; color:var(--red);">
                        <i class="fa-solid fa-circle-exclamation" style="font-size:1.1rem;"></i> PHÂN TÍCH RỦI RO CHI TIẾT ĐƠN HÀNG B2B
                    </div>
                    <div>
                        <strong>🚨 Cảnh báo:</strong> Kho <span style="font-weight:700; color:var(--red);">${escapeHtml(maxErrorKho)}</span> đang có số lỗi đơn B2B cao nhất với <span style="font-weight:700; color:var(--red);">${maxErrorKhoVal}</span> đơn lỗi. Lỗi chính: <span style="font-weight:700;">${escapeHtml(maxErrorType)}</span> (phát sinh ${maxErrorTypeVal} lần). Cần rà soát chi tiết trong bảng Data đơn B2B và cập nhật phương án xử lý.
                    </div>
                    <div style="margin-top:10px;">
                        <strong>🛠️ Đề xuất xử lý:</strong>
                        <ul style="margin:6px 0 0 18px; padding:0; list-style-type:disc;">
                            <li>Tập trung xử lý kho có số lỗi cao nhất.</li>
                            <li>Phân loại lỗi theo nguyên nhân: khách hẹn, không liên hệ được, thiếu xe, sai địa chỉ, tồn kho, lỗi vận hành.</li>
                            <li>Gửi danh sách đơn lỗi cho kho phụ trách.</li>
                            <li>Yêu cầu phản hồi tình trạng xử lý trong ngày.</li>
                        </ul>
                    </div>
                </div>
            `;
        } else {
            detailAlert.style.display = 'none';
        }
    }
    
    const countLabel = document.getElementById('b2b-detail-count-label');
    if (countLabel) countLabel.textContent = rawOrders.length + ' đơn';
    
    const tbody = document.getElementById('tbody-b2b-detail');
    if (tbody) {
        if (rawOrders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--text3)">Không có đơn lỗi/chưa giao phù hợp bộ lọc.</td></tr>';
        } else {
            window.b2bDetailedTableLimit = window.b2bDetailedTableLimit || 100;
            const sliced = rawOrders.slice(0, window.b2bDetailedTableLimit);
            let html = sliced.map(r => `
                <tr>
                    <td>${escapeHtml(r['Ngày ưu tiên'])}</td>
                    <td>${escapeHtml(getRegionForWarehouse(r['Kho hiện tại'], r['Ngày ưu tiên']))}</td>
                    <td style="font-weight:600;">${escapeHtml(shortKho(r['Kho hiện tại']))}</td>
                    <td><span class="badge secondary" style="font-size:11px; font-family:monospace; cursor:pointer;" onclick="navigator.clipboard.writeText('${r['Mã đơn']}'); showToast('Đã copy mã đơn!')">${escapeHtml(r['Mã đơn'])}</span></td>
                    <td>${escapeHtml(r['Tên khách'])}</td>
                    <td><span class="badge red">${escapeHtml(r['Nhóm lỗi'])}</span></td>
                    <td>${escapeHtml(r['PIC'] || '--')}</td>
                </tr>
            `).join('');
            
            if (rawOrders.length > window.b2bDetailedTableLimit) {
                html += `<tr><td colspan="7" style="text-align:center;padding:12px;"><button class="btn btn-secondary btn-sm" onclick="window.b2bDetailedTableLimit += 100; renderB2bDetailedTable();" style="cursor:pointer;padding:6px 12px;font-size:0.8rem;"><i class="fa-solid fa-angles-down"></i> Xem thêm (${rawOrders.length - window.b2bDetailedTableLimit} dòng còn lại)</button></td></tr>`;
            }
            tbody.innerHTML = html;
        }
    }
}

// =====================================================================
// BẢN ĐỒ B2B MIỀN TRUNG SECTION
// =====================================================================
let b2bMapInitialized = false;
window.b2bLeafletMap = null;
window.b2bMapMarkersGroup = null;
// Track if a data fetch is in progress to prevent duplicate fetches
let b2bMapFetchInProgress = false;

// Show loading state in the map container and table body
function showB2BMapLoading() {
    const tbody = document.getElementById('tbody-b2b-map');
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:40px; color:var(--text3);"><i class="fa-solid fa-spinner fa-spin" style="margin-right:8px;"></i>Đang tải dữ liệu kho...</td></tr>`;
    }
    // Show loading overlay on map if possible
    const mapContainer = document.getElementById('b2b-leaflet-map');
    if (mapContainer) {
        let overlay = document.getElementById('b2b-map-loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'b2b-map-loading-overlay';
            overlay.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:var(--bg-card,rgba(0,0,0,0.5));z-index:1000;border-radius:12px;color:var(--text,#fff);font-size:1rem;gap:10px;';
            overlay.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Đang tải dữ liệu kho...</span>';
            const parent = mapContainer.parentElement;
            if (parent) { parent.style.position = 'relative'; parent.appendChild(overlay); }
        }
        overlay.style.display = 'flex';
    }
}

function hideB2BMapLoading() {
    const overlay = document.getElementById('b2b-map-loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

function showB2BMapError(message) {
    const tbody = document.getElementById('tbody-b2b-map');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align:center; padding:40px; color:var(--red,#ef4444);">
                    <i class="fa-solid fa-triangle-exclamation" style="margin-right:8px;"></i>
                    ${message}<br/>
                    <button onclick="window.b2bMapRetryLoad()" style="margin-top:12px; padding:8px 20px; background:var(--blue,#3b82f6); color:white; border:none; border-radius:8px; cursor:pointer; font-size:0.85rem;">
                        <i class="fa-solid fa-rotate-right"></i> Tải lại dữ liệu
                    </button>
                </td>
            </tr>`;
    }
    const overlay = document.getElementById('b2b-map-loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

// Retry button handler
window.b2bMapRetryLoad = async function() {
    showB2BMapLoading();
    await b2bMapFetchData();
};

// Dedicated fetch function for B2B map data only (used when khoGxtData is empty on first click)
async function b2bMapFetchData() {
    if (b2bMapFetchInProgress) return;
    b2bMapFetchInProgress = true;
    try {
        const result = await authFetch(`${API}/kho-gxt`, { data: [] });
        state.khoGxtData = result.data || [];
        console.log(`[B2B MAP] Fetched ${state.khoGxtData.length} warehouse records.`);
        hideB2BMapLoading();
        if (state.khoGxtData.length === 0) {
            showB2BMapError('Không có dữ liệu kho. Vui lòng thử lại.');
        } else {
            // Give Leaflet a moment to settle, then render
            setTimeout(() => {
                if (window.b2bLeafletMap) window.b2bLeafletMap.invalidateSize();
                filterB2BMapData();
            }, 200);
        }
    } catch (err) {
        console.error('[B2B MAP] Failed to fetch warehouse data:', err);
        showB2BMapError('Lỗi khi tải dữ liệu kho. Vui lòng thử lại.');
    } finally {
        b2bMapFetchInProgress = false;
    }
}

window.renderB2BMapSection = function() {
    const mapContainer = document.getElementById('b2b-leaflet-map');
    if (!mapContainer) return;
    
    // Initialize Leaflet map once
    if (!b2bMapInitialized) {
        window.b2bLeafletMap = L.map('b2b-leaflet-map', {
            minZoom: 5,
            maxZoom: 15
        }).setView([16.0544, 108.2021], 6);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '\u00a9 OpenStreetMap contributors'
        }).addTo(window.b2bLeafletMap);
        
        window.b2bMapMarkersGroup = L.layerGroup().addTo(window.b2bLeafletMap);
        
        // Bind search and filter events once
        const searchInput = document.getElementById('b2b-map-search');
        const statusFilter = document.getElementById('b2b-map-status-filter');
        if (searchInput) searchInput.addEventListener('input', () => filterB2BMapData());
        if (statusFilter) statusFilter.addEventListener('change', () => filterB2BMapData());
        
        b2bMapInitialized = true;
        console.log('[B2B MAP] Leaflet map initialized.');
    }
    
    // Check if data is already available in state
    const hasData = state.khoGxtData && state.khoGxtData.length > 0;
    
    if (!hasData) {
        // Data not yet loaded - show loading state and trigger async fetch
        console.log('[B2B MAP] khoGxtData is empty on first open — triggering fetch...');
        showB2BMapLoading();
        b2bMapFetchData();
        return;
    }
    
    // Data is available: invalidate size, then filter/render markers
    setTimeout(() => {
        if (window.b2bLeafletMap) window.b2bLeafletMap.invalidateSize();
        filterB2BMapData();
    }, 150);
};

function filterB2BMapData() {
    if (!window.b2bLeafletMap || !window.b2bMapMarkersGroup) return;
    
    const rawList = state.khoGxtData || [];
    
    // If no data available at all, show loading
    if (rawList.length === 0) {
        console.warn('[B2B MAP] filterB2BMapData called but khoGxtData is empty.');
        return;
    }
    
    const searchVal = (document.getElementById('b2b-map-search')?.value || "").trim().toLowerCase();
    const statusVal = document.getElementById('b2b-map-status-filter')?.value || "all";
    
    // Clear existing markers before re-render
    window.b2bMapMarkersGroup.clearLayers();
    
    const tbody = document.getElementById('tbody-b2b-map');
    if (!tbody) return;
    
    // Filter list by search and status
    const filtered = rawList.filter(item => {
        const id = String(item.id_kho || item['ID Kho'] || '').toLowerCase();
        const name = String(item.ten_kho || item['Tên Kho GXT'] || '').toLowerCase();
        const matchesSearch = !searchVal || id.includes(searchVal) || name.includes(searchVal);
        
        const hasCoords = !!(item.coords && item.coords.length === 2);
        let matchesStatus = true;
        if (statusVal === 'mapped') matchesStatus = hasCoords;
        else if (statusVal === 'unmapped') matchesStatus = !hasCoords;
        
        return matchesSearch && matchesStatus;
    });
    
    // Render table rows
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:30px; color:var(--text3)">Không tìm thấy kho phù hợp.</td></tr>`;
    } else {
        tbody.innerHTML = filtered.map(item => {
            const id = item.idKho || item.id_kho || item['ID Kho'] || '--';
            const name = item.tenKho || item.ten_kho || item['Tên Kho GXT'] || '--';
            const address = item.diaChi || item.dia_chi || item['\u0110\u1ecba ch\u1ec9 kho'] || 'Ch\u01b0a c\u00f3 \u0111\u1ecba ch\u1ec9';
            const link = (item.linkGGM || item.googleMapsLink || item.link_ggm || item['Link GGM'] || '').trim();
            const hasCoords = !!(item.coords && item.coords.length === 2);
            const hasLink = link && link !== '#' && link.toLowerCase() !== 'link';
            
            const linkHtml = hasLink
                ? `<a href="${link}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan); font-weight:600;"><i class="fa-solid fa-arrow-up-right-from-square"></i> M\u1edf b\u1ea3n \u0111\u1ed3</a>`
                : `<span style="color:var(--text3)">Kh\u00f4ng c\u00f3 link</span>`;
                
            let statusHtml = '';
            const mapStatus = item.mapStatus || item.map_status || '';
            if (mapStatus === '\u0110\u00e3 hi\u1ec3n th\u1ecb tr\u00ean b\u1ea3n \u0111\u1ed3' || (hasLink && hasCoords)) {
                statusHtml = `<span class="badge storing">\u0110\u00e3 hi\u1ec3n th\u1ecb tr\u00ean b\u1ea3n \u0111\u1ed3</span>`;
            } else if (mapStatus === 'C\u00f3 link, ch\u01b0a l\u1ea5y \u0111\u01b0\u1ee3c v\u1ecb tr\u00ed' || (hasLink && !hasCoords)) {
                statusHtml = `<span class="badge p2">C\u00f3 link, ch\u01b0a l\u1ea5y \u0111\u01b0\u1ee3c v\u1ecb tr\u00ed</span>`;
            } else {
                statusHtml = `<span class="badge p1">Ch\u01b0a c\u00f3 link</span>`;
            }
                
            return `
                <tr>
                    <td style="font-weight:600; color:var(--text1);">${id}</td>
                    <td style="font-weight:600; color:var(--text2);">${name}</td>
                    <td>${address}</td>
                    <td>${linkHtml}</td>
                    <td>${statusHtml}</td>
                </tr>
            `;
        }).join('');
    }
    
    // Add markers to map
    let validCoords = [];
    filtered.forEach(item => {
        const name = item.tenKho || item.ten_kho || item['Tên Kho GXT'] || '--';
        const id = item.idKho || item.id_kho || item['ID Kho'] || '--';
        const address = item.diaChi || item.dia_chi || item['\u0110\u1ecba ch\u1ec9 kho'] || 'Ch\u01b0a c\u00f3 \u0111\u1ecba ch\u1ec9';
        const link = (item.linkGGM || item.googleMapsLink || item.link_ggm || item['Link GGM'] || '').trim();
        const hasLink = link && link !== '#' && link.toLowerCase() !== 'link';
        const area = item.dienTich || item.dien_tich || '--';
        
        if (item.coords && item.coords.length === 2) {
            const [lat, lng] = item.coords;
            validCoords.push([lat, lng]);
            
            const labelName = name.replace('Kho Giao H\u00e0ng N\u1eb7ng - ', '').replace('Kho Giao H\u00e0ng N\u1eb7ng ', '').trim();
            
            const customIcon = L.divIcon({
                html: `
                    <div class="map-marker-warehouse" title="${name}">
                        <i class="fa-solid fa-warehouse"></i>
                        <span class="marker-label">${labelName}</span>
                    </div>
                `,
                className: 'custom-warehouse-marker',
                iconSize: [60, 45],
                iconAnchor: [30, 22],
                popupAnchor: [0, -20]
            });
            
            const marker = L.marker([lat, lng], { icon: customIcon }).addTo(window.b2bMapMarkersGroup);
            
            const popupContent = `
                <div style="font-family:'Outfit', sans-serif; font-size:0.85rem; color:var(--text); padding:4px;">
                    <h4 style="margin:0 0 4px; font-weight:700; color:var(--green);">${name}</h4>
                    <p style="margin:0 0 4px; color:var(--text2);"><strong>ID:</strong> ${id}</p>
                    <p style="margin:0 0 4px; color:var(--text2);"><strong>Di\u1ec7n t\u00edch:</strong> ${area} m\u00b2</p>
                    <p style="margin:0 0 6px; line-height:1.4; color:var(--text2);"><strong>\u0110\u1ecba ch\u1ec9:</strong> ${address}</p>
                    ${hasLink ? `<a href="${link}" target="_blank" rel="noopener noreferrer" style="display:inline-block; background:var(--green); color:white; padding:6px 12px; border-radius:6px; text-decoration:none; font-weight:600; font-size:0.75rem;"><i class="fa-solid fa-map-pin"></i> Xem tr\u00ean Google Maps</a>` : ''}
                </div>
            `;
            marker.bindPopup(popupContent);
            
            const tooltipContent = `
                <div style="text-align: left; line-height: 1.4;">
                    <strong>${name}</strong><br/>
                    <span style="color:var(--text3); font-size: 0.75rem;">Di\u1ec7n t\u00edch: ${area} m\u00b2</span>
                </div>
            `;
            marker.bindTooltip(tooltipContent, {
                permanent: false,
                direction: 'top',
                className: 'ghn-map-tooltip'
            });
        }
    });
    
    console.log(`[B2B MAP] Rendered ${validCoords.length} markers out of ${filtered.length} filtered warehouses.`);
    
    // Fit map to visible markers
    if (validCoords.length === 1) {
        window.b2bLeafletMap.setView(validCoords[0], 12);
    } else if (validCoords.length > 1) {
        const bounds = L.latLngBounds(validCoords);
        window.b2bLeafletMap.fitBounds(bounds, { padding: [60, 60] });
    } else {
        // No markers: default to central Vietnam view
        window.b2bLeafletMap.setView([16.0544, 108.2021], 6);
    }
}



// =====================================================================
// XE VẬN HÀNH DAILY — MODULE
// =====================================================================

// ---- State riêng cho Xe Daily ----
let xeDailyMetaLoaded = false;
let xeDailyRowCount = 0; // counter for unique row IDs

// ---- Helpers ----
function _getTodayVN() {
    const now = new Date();
    const d = String(now.getDate()).padStart(2, '0');
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const y = now.getFullYear();
    return `${d}/${m}/${y}`;
}

function _getLast10Days() {
    const days = [];
    const now = new Date();
    for (let i = 0; i < 10; i++) {
        const d = new Date(now);
        d.setDate(now.getDate() - i);
        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const yy = d.getFullYear();
        days.push(`${dd}/${mm}/${yy}`);
    }
    return days;
}

// Trả về tất cả ngày từ 01/07/2026 đến hôm nay (giờ VN), format dd/mm/yyyy, sắp xếp mới nhất trước
function _getDaysFromStart() {
    const days = [];
    // Today in Vietnam time (UTC+7)
    const nowUtc = new Date();
    const nowVn = new Date(nowUtc.getTime() + 7 * 3600 * 1000);
    const todayY = nowVn.getUTCFullYear();
    const todayM = nowVn.getUTCMonth(); // 0-indexed
    const todayD = nowVn.getUTCDate();

    // Start date: 01/07/2026
    const start = new Date(Date.UTC(2026, 6, 1)); // month 6 = July
    const end   = new Date(Date.UTC(todayY, todayM, todayD));

    // Safety: if today is before 01/07/2026, fall back to today only
    if (end < start) {
        const dd = String(todayD).padStart(2, '0');
        const mm = String(todayM + 1).padStart(2, '0');
        return [`${dd}/${mm}/${todayY}`];
    }

    // Iterate from end down to start
    const cur = new Date(end);
    while (cur >= start) {
        const dd = String(cur.getUTCDate()).padStart(2, '0');
        const mm = String(cur.getUTCMonth() + 1).padStart(2, '0');
        const yy = cur.getUTCFullYear();
        days.push(`${dd}/${mm}/${yy}`);
        cur.setUTCDate(cur.getUTCDate() - 1);
    }
    return days; // newest first
}

function _formatTimestamp(iso) {
    if (!iso) return '--';
    try {
        const d = new Date(iso);
        // Convert UTC to Vietnam time (UTC+7)
        const vn = new Date(d.getTime() + 7 * 3600 * 1000);
        const dd = String(vn.getUTCDate()).padStart(2, '0');
        const mm = String(vn.getUTCMonth() + 1).padStart(2, '0');
        const yy = vn.getUTCFullYear();
        const hh = String(vn.getUTCHours()).padStart(2, '0');
        const mi = String(vn.getUTCMinutes()).padStart(2, '0');
        return `${dd}/${mm}/${yy} ${hh}:${mi}`;
    } catch {
        return iso;
    }
}

function _trongTaiLabel(val) {
    const n = parseInt(val);
    if (!n) return '';
    if (n >= 1000) return `${(n / 1000).toFixed(1).replace('.0', '')} tấn`;
    return `${n} kg`;
}

// ---- Render main section ----
function renderXeDailySection() {
    // Load meta (kho/NCC) once
    if (!xeDailyMetaLoaded) {
        loadXeDailyMeta();
    }

    // Init form with 1 default row if empty
    const container = document.getElementById('xe-daily-rows-container');
    if (container && container.children.length === 0) {
        addXeDailyRow();
    }

    // Load history records
    loadXeDailyRecords();
}

// ---- Load kho/NCC metadata ----
async function loadXeDailyMeta() {
    try {
        const result = await authFetch(`${API}/xe-van-hanh/meta`, { kho_list: [], ncc_map: {}, ncc_all: [] });
        state.xeDailyMeta = result;
        xeDailyMetaLoaded = true;
        console.log(`[XE DAILY] Meta loaded: ${result.kho_list?.length || 0} kho, ${result.ncc_all?.length || 0} NCC`);
        // Refresh all existing rows' dropdowns
        document.querySelectorAll('.xe-daily-row').forEach(row => {
            const rowId = row.dataset.rowId;
            _populateKhoDropdown(rowId);
            _populateNccDropdown(rowId, '');
        });
        // Populate filter dropdowns
        _populateFilterDropdowns();
    } catch (err) {
        console.error('[XE DAILY] Failed to load meta:', err);
    }
}

function _populateKhoDropdown(rowId) {
    const sel = document.getElementById(`xed-kho-${rowId}`);
    if (!sel) return;
    const khoList = state.xeDailyMeta?.kho_list || [];
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">-- Chọn kho --</option>' +
        khoList.map(k => `<option value="${escapeHtml(k)}"${currentVal === k ? ' selected' : ''}>${escapeHtml(k)}</option>`).join('');
}

function _populateNccDropdown(rowId, selectedKho) {
    const sel = document.getElementById(`xed-ncc-${rowId}`);
    if (!sel) return;
    const meta = state.xeDailyMeta || { ncc_map: {}, ncc_all: [] };
    const currentVal = sel.value;
    let nccList = [];
    if (selectedKho && meta.ncc_map?.[selectedKho]?.length > 0) {
        nccList = meta.ncc_map[selectedKho];
    } else {
        nccList = meta.ncc_all || [];
    }
    sel.innerHTML = '<option value="">-- Chọn NCC --</option>' +
        nccList.map(n => `<option value="${escapeHtml(n)}"${currentVal === n ? ' selected' : ''}>${escapeHtml(n)}</option>`).join('');
}

// ---- Add a form row ----
function addXeDailyRow() {
    const container = document.getElementById('xe-daily-rows-container');
    if (!container) return;

    xeDailyRowCount++;
    const rowId = `r${xeDailyRowCount}`;
    const today = _getTodayVN();
    const days = _getDaysFromStart();

    const rowEl = document.createElement('div');
    rowEl.className = 'xe-daily-row';
    rowEl.dataset.rowId = rowId;

    rowEl.innerHTML = `
        <div class="xe-daily-row-header">
            <span><i class="fa-solid fa-truck-moving"></i> Dòng xe ${xeDailyRowCount}</span>
            <button class="xe-daily-row-delete" onclick="removeXeDailyRow('${rowId}')" title="Xóa dòng này">
                <i class="fa-solid fa-trash-can"></i> Xóa
            </button>
        </div>
        <div class="xe-daily-grid">
            <div class="xe-daily-field">
                <label for="xed-ngay-${rowId}">Ngày <span class="req">*</span></label>
                <select id="xed-ngay-${rowId}">
                    ${days.map(d => `<option value="${d}"${d === today ? ' selected' : ''}>${d}</option>`).join('')}
                </select>
            </div>
            <div class="xe-daily-field">
                <label for="xed-kho-${rowId}">Tên kho <span class="req">*</span></label>
                <select id="xed-kho-${rowId}" onchange="onXedKhoChange('${rowId}')">
                    <option value="">-- Chọn kho --</option>
                </select>
            </div>
            <div class="xe-daily-field">
                <label for="xed-loai-${rowId}">Loại ghi nhận <span class="req">*</span></label>
                <select id="xed-loai-${rowId}">
                    <option value="">-- Chọn loại --</option>
                    <option value="Xe tăng cường">🟢 Xe tăng cường</option>
                    <option value="Xe không hoạt động">🔴 Xe không hoạt động</option>
                </select>
            </div>
            <div class="xe-daily-field">
                <label for="xed-sl-${rowId}">Số lượng xe <span class="req">*</span></label>
                <select id="xed-sl-${rowId}">
                    <option value="1">1 xe</option>
                    <option value="2">2 xe</option>
                    <option value="3">3 xe</option>
                    <option value="4">4 xe</option>
                    <option value="5">5 xe</option>
                </select>
            </div>
            <div class="xe-daily-field" style="grid-column: span 2;">
                <label for="xed-bien-${rowId}">Biển số xe <span class="req">*</span></label>
                <input type="text" id="xed-bien-${rowId}" placeholder="VD: 50H-806.25" autocomplete="off">
            </div>
            <div class="xe-daily-field">
                <label for="xed-ncc-${rowId}">Tên NCC <span class="req">*</span></label>
                <select id="xed-ncc-${rowId}">
                    <option value="">-- Chọn NCC --</option>
                </select>
            </div>
            <div class="xe-daily-field">
                <label for="xed-tt-${rowId}">Trọng tải (kg) <span class="req">*</span></label>
                <input type="number" id="xed-tt-${rowId}" placeholder="VD: 1400, 1900, 2500" min="0" step="100"
                    oninput="updateTrongTaiHint('${rowId}')">
                <span class="trong-tai-hint" id="xed-tt-hint-${rowId}"></span>
            </div>
        </div>
    `;

    container.appendChild(rowEl);

    // Populate kho dropdown
    _populateKhoDropdown(rowId);
    _populateNccDropdown(rowId, '');
}

// Called when kho is changed — update NCC dropdown
function onXedKhoChange(rowId) {
    const khoSel = document.getElementById(`xed-kho-${rowId}`);
    if (khoSel) {
        _populateNccDropdown(rowId, khoSel.value);
    }
}

// Update trong-tai hint label
function updateTrongTaiHint(rowId) {
    const inp = document.getElementById(`xed-tt-${rowId}`);
    const hint = document.getElementById(`xed-tt-hint-${rowId}`);
    if (!inp || !hint) return;
    const label = _trongTaiLabel(inp.value);
    hint.textContent = label ? `≈ ${label}` : '';
}

// ---- Remove a form row ----
function removeXeDailyRow(rowId) {
    const container = document.getElementById('xe-daily-rows-container');
    if (!container) return;
    const row = container.querySelector(`.xe-daily-row[data-row-id="${rowId}"]`);
    if (row) {
        // Don't remove if it's the only row
        if (container.children.length <= 1) {
            showToast('Cần ít nhất 1 dòng xe trong form.', 'warning');
            return;
        }
        row.remove();
    }
}

// ---- Validate and Save ----
async function saveXeDaily() {
    const container = document.getElementById('xe-daily-rows-container');
    if (!container) return;

    const rows = container.querySelectorAll('.xe-daily-row');
    if (!rows.length) {
        showToast('Chưa có dòng xe nào để lưu.', 'warning');
        return;
    }

    const records = [];
    let hasError = false;

    rows.forEach(rowEl => {
        const rowId = rowEl.dataset.rowId;

        // Clear previous error state
        rowEl.querySelectorAll('.error').forEach(el => el.classList.remove('error'));

        const ngay   = document.getElementById(`xed-ngay-${rowId}`)?.value?.trim() || '';
        const tenKho = document.getElementById(`xed-kho-${rowId}`)?.value?.trim() || '';
        const loai   = document.getElementById(`xed-loai-${rowId}`)?.value?.trim() || '';
        const slXe   = document.getElementById(`xed-sl-${rowId}`)?.value || '1';
        const bien   = document.getElementById(`xed-bien-${rowId}`)?.value?.trim() || '';
        const tenNcc = document.getElementById(`xed-ncc-${rowId}`)?.value?.trim() || '';
        const tt     = document.getElementById(`xed-tt-${rowId}`)?.value?.trim() || '';

        let rowOk = true;

        if (!ngay) { rowOk = false; hasError = true; }
        if (!tenKho) { rowOk = false; hasError = true; document.getElementById(`xed-kho-${rowId}`)?.classList.add('error'); }
        if (!loai)  { rowOk = false; hasError = true; document.getElementById(`xed-loai-${rowId}`)?.classList.add('error'); }
        if (!bien)  { rowOk = false; hasError = true; document.getElementById(`xed-bien-${rowId}`)?.classList.add('error'); }
        if (!tenNcc){ rowOk = false; hasError = true; document.getElementById(`xed-ncc-${rowId}`)?.classList.add('error'); }
        if (!tt)    { rowOk = false; hasError = true; document.getElementById(`xed-tt-${rowId}`)?.classList.add('error'); }

        if (rowOk) {
            records.push({
                ngay: ngay,
                ten_kho: tenKho,
                loai: loai,
                so_luong_xe: parseInt(slXe) || 1,
                bien_so_xe: bien,
                ten_ncc: tenNcc,
                trong_tai: parseInt(tt) || 0,
            });
        }
    });

    if (hasError) {
        showToast('Vui lòng điền đầy đủ các trường bắt buộc (được đánh dấu *).', 'error');
        return;
    }

    if (!records.length) {
        showToast('Không có dữ liệu hợp lệ để lưu.', 'warning');
        return;
    }

    // Disable save button
    const saveBtn = document.getElementById('btn-save-xe-daily');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...';
    }

    try {
        const resp = await authPost(`${API}/xe-van-hanh/records`, { records }, { status: 'error', message: 'Network error' });

        if (resp.status === 'ok') {
            showToast(`✅ Đã lưu ghi nhận ${resp.saved} xe vận hành daily.`, 'success');
            // Reset form
            const c = document.getElementById('xe-daily-rows-container');
            if (c) c.innerHTML = '';
            xeDailyRowCount = 0;
            addXeDailyRow();
            // Reload history
            await loadXeDailyRecords();
        } else {
            showToast(`❌ Lỗi: ${resp.message || 'Không thể lưu.'}`, 'error');
        }
    } catch (err) {
        console.error('[XE DAILY] Save error:', err);
        showToast('Lỗi kết nối. Vui lòng thử lại.', 'error');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Lưu ghi nhận';
        }
    }
}

// ---- Load history records ----
async function loadXeDailyRecords() {
    const tbody = document.getElementById('tbody-xed-history');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--text3)"><i class="fa-solid fa-spinner fa-spin"></i> Đang tải...</td></tr>`;

    try {
        // Build query params from current filter values
        const dateVal = document.getElementById('xed-filter-date')?.value || '';
        const khoVal  = document.getElementById('xed-filter-kho')?.value || '';
        const nccVal  = document.getElementById('xed-filter-ncc')?.value || '';
        const loaiVal = document.getElementById('xed-filter-loai')?.value || '';

        let url = `${API}/xe-van-hanh/records`;
        const params = [];
        if (dateVal) params.push(`date=${encodeURIComponent(dateVal)}`);
        if (khoVal)  params.push(`kho=${encodeURIComponent(khoVal)}`);
        if (nccVal)  params.push(`ncc=${encodeURIComponent(nccVal)}`);
        if (loaiVal) params.push(`loai=${encodeURIComponent(loaiVal)}`);
        if (params.length) url += '?' + params.join('&');

        const resp = await authFetch(url, { data: [], total: 0 });
        state.xeDailyRecords = resp.data || [];
        renderXeDailyHistoryTable(state.xeDailyRecords);
        updateXeDailyCards();
        _populateFilterDropdowns();
    } catch (err) {
        console.error('[XE DAILY] Load records error:', err);
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--red)">Lỗi khi tải dữ liệu. Vui lòng thử lại.</td></tr>`;
    }
}

// ---- Render history table ----
function renderXeDailyHistoryTable(records) {
    const tbody = document.getElementById('tbody-xed-history');
    const countEl = document.getElementById('xed-history-count');
    if (!tbody) return;

    if (countEl) countEl.textContent = `${records.length} bản ghi`;

    if (!records.length) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--text3)">Chưa có ghi nhận nào. Hãy thêm ở form bên trên.</td></tr>`;
        return;
    }

    window.xeDailyHistoryTableLimit = window.xeDailyHistoryTableLimit || 100;
    const sliced = records.slice(0, window.xeDailyHistoryTableLimit);
    let html = sliced.map(r => {
        const loaiBadge = r.loai === 'Xe tăng cường'
            ? `<span class="badge-tang-cuong"><i class="fa-solid fa-circle-plus"></i> Xe tăng cường</span>`
            : `<span class="badge-off-xe"><i class="fa-solid fa-circle-xmark"></i> Xe không hoạt động</span>`;

        const ttLabel = _trongTaiLabel(r.trong_tai) || `${r.trong_tai || '--'} kg`;

        return `<tr>
            <td style="font-weight:600;color:var(--cyan);white-space:nowrap">${escapeHtml(r.ngay || '--')}</td>
            <td style="font-size:0.82rem;color:var(--text2)">${escapeHtml(r.ten_kho || '--')}</td>
            <td>${loaiBadge}</td>
            <td style="text-align:center;font-weight:700">${r.so_luong_xe || 1}</td>
            <td style="font-family:monospace;font-size:0.82rem;color:var(--text)">${escapeHtml(r.bien_so_xe || '--')}</td>
            <td style="font-size:0.82rem">${escapeHtml(r.ten_ncc || '--')}</td>
            <td style="font-size:0.82rem;color:var(--text2)">${escapeHtml(ttLabel)}</td>
            <td style="font-size:0.8rem;color:var(--text3)">${escapeHtml(r.nguoi_nhap || '--')}</td>
            <td style="font-size:0.78rem;color:var(--text3);white-space:nowrap">${_formatTimestamp(r.thoi_gian_ghi_nhan)}</td>
            <td>
                <button class="btn-xed-delete" onclick="deleteXeDailyRecord('${r.id}')">
                    <i class="fa-solid fa-trash-can"></i> Xóa
                </button>
            </td>
        </tr>`;
    }).join('');
    
    if (records.length > window.xeDailyHistoryTableLimit) {
        html += `<tr><td colspan="10" style="text-align:center;padding:12px;"><button class="btn btn-secondary btn-sm" onclick="window.xeDailyHistoryTableLimit += 100; renderXeDailyHistoryTable(state.xeDailyRecords);" style="cursor:pointer;padding:6px 12px;font-size:0.8rem;"><i class="fa-solid fa-angles-down"></i> Xem thêm (${records.length - window.xeDailyHistoryTableLimit} dòng còn lại)</button></td></tr>`;
    }
    tbody.innerHTML = html;
}

// ---- Filter table ----
function filterXeDailyTable() {
    loadXeDailyRecords();
}

// ---- Update overview cards ----
function updateXeDailyCards() {
    const dateFilter = document.getElementById('xed-filter-date')?.value || '';
    // Filter records for the selected date (or today if no filter)
    const targetDate = dateFilter || _getTodayVN();
    const dayRecords = state.xeDailyRecords;

    // If filter is active, use all loaded records; otherwise recalculate for today
    const forToday = dateFilter
        ? dayRecords
        : dayRecords.filter(r => r.ngay === targetDate);

    const tangCuong  = forToday.filter(r => r.loai === 'Xe tăng cường').reduce((s, r) => s + (r.so_luong_xe || 1), 0);
    const offXe      = forToday.filter(r => r.loai === 'Xe không hoạt động').reduce((s, r) => s + (r.so_luong_xe || 1), 0);
    const khoSet     = new Set(forToday.map(r => r.ten_kho).filter(Boolean));
    const nccSet     = new Set(forToday.map(r => r.ten_ncc).filter(Boolean));

    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };
    setVal('xed-val-tang-cuong', tangCuong || '0');
    setVal('xed-val-off', offXe || '0');
    setVal('xed-val-kho', khoSet.size || '0');
    setVal('xed-val-ncc', nccSet.size || '0');
}

// ---- Populate filter dropdowns ----
function _populateFilterDropdowns() {
    const allRecords = state.xeDailyRecords || [];

    // Date filter
    const dateSel = document.getElementById('xed-filter-date');
    if (dateSel) {
        const currentDate = dateSel.value;
        const daysFromStart = _getDaysFromStart();
        // Merge with any record dates that might be outside the range
        const recordDates = [...new Set(allRecords.map(r => r.ngay).filter(Boolean))];
        const allDates = [...new Set([...daysFromStart, ...recordDates])].sort((a, b) => {
            // Sort dd/mm/yyyy desc
            const toNum = s => {
                const [d, m, y] = (s || '').split('/');
                return parseInt(y || 0) * 10000 + parseInt(m || 0) * 100 + parseInt(d || 0);
            };
            return toNum(b) - toNum(a);
        });
        dateSel.innerHTML = '<option value="">Tất cả ngày</option>' +
            allDates.map(d => `<option value="${d}"${d === currentDate ? ' selected' : ''}>${d}</option>`).join('');
    }

    // Kho filter
    const khoSel = document.getElementById('xed-filter-kho');
    if (khoSel) {
        const currentKho = khoSel.value;
        const khoList = state.xeDailyMeta?.kho_list || [...new Set(allRecords.map(r => r.ten_kho).filter(Boolean))];
        khoSel.innerHTML = '<option value="">Tất cả kho</option>' +
            khoList.map(k => `<option value="${k}"${k === currentKho ? ' selected' : ''}>${escapeHtml(k)}</option>`).join('');
    }

    // NCC filter
    const nccSel = document.getElementById('xed-filter-ncc');
    if (nccSel) {
        const currentNcc = nccSel.value;
        const nccList = state.xeDailyMeta?.ncc_all || [...new Set(allRecords.map(r => r.ten_ncc).filter(Boolean))];
        nccSel.innerHTML = '<option value="">Tất cả NCC</option>' +
            nccList.map(n => `<option value="${n}"${n === currentNcc ? ' selected' : ''}>${escapeHtml(n)}</option>`).join('');
    }
}

// ---- Delete a record ----
async function deleteXeDailyRecord(recordId) {
    if (!confirm('Bạn có chắc muốn xóa bản ghi này không?\nThao tác này không thể hoàn tác.')) return;

    try {
        const resp = await authPost(`${API}/xe-van-hanh/records/${recordId}/delete`, {}, { status: 'error', message: '' });
        if (resp.status === 'ok') {
            showToast('✅ Đã xóa bản ghi thành công.', 'success');
            await loadXeDailyRecords();
        } else {
            showToast(`❌ Lỗi: ${resp.message || 'Không thể xóa.'}`, 'error');
        }
    } catch (err) {
        console.error('[XE DAILY] Delete error:', err);
        showToast('Lỗi kết nối. Vui lòng thử lại.', 'error');
    }
}

// ---- Export history table to Excel ----
function exportXeDailyExcel() {
    const records = state.xeDailyRecords || [];
    if (!records.length) {
        showToast('Không có dữ liệu để xuất.', 'warning');
        return;
    }

    // Build rows
    const header = ['Ngày', 'Tên kho', 'Loại ghi nhận', 'Số lượng xe', 'Biển số xe', 'Tên NCC', 'Trọng tải', 'Người nhập', 'Thời gian ghi nhận'];
    const dataRows = records.map(r => [
        r.ngay || '',
        r.ten_kho || '',
        r.loai || '',
        r.so_luong_xe || 1,
        r.bien_so_xe || '',
        r.ten_ncc || '',
        _trongTaiLabel(r.trong_tai) || (r.trong_tai ? `${r.trong_tai} kg` : ''),
        r.nguoi_nhap || '',
        _formatTimestamp(r.thoi_gian_ghi_nhan)
    ]);

    // Build CSV content with BOM for UTF-8 Vietnamese
    const BOM = '\uFEFF';
    const escape = v => {
        const s = String(v ?? '');
        if (s.includes(',') || s.includes('"') || s.includes('\n')) {
            return '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
    };
    const csvLines = [header, ...dataRows].map(row => row.map(escape).join(','));
    const csvContent = BOM + csvLines.join('\n');

    // Generate filename with today's date
    const today = _getTodayVN().split('/').join(''); // ddmmyyyy
    const filename = `xe-van-hanh-daily-${today}.csv`;

    // Trigger download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast(`✅ Đã xuất ${records.length} bản ghi ra file ${filename}`, 'success');
}

// =====================================================================
// XE DAILY — IMPORT FILE FUNCTIONS
// =====================================================================

// Called when user selects a file in the import input
function onXedImportFileChange() {
    const input = document.getElementById('xed-import-file');
    const nameEl = document.getElementById('xed-import-filename');
    const btn = document.getElementById('btn-xed-import');
    const resultEl = document.getElementById('xed-import-result');

    if (input && input.files && input.files[0]) {
        const f = input.files[0];
        if (nameEl) nameEl.textContent = f.name;
        if (btn) btn.disabled = false;
    } else {
        if (nameEl) nameEl.textContent = 'Chưa chọn file';
        if (btn) btn.disabled = true;
    }
    if (resultEl) { resultEl.style.display = 'none'; resultEl.innerHTML = ''; }
}

// Download a sample CSV file with correct headers and one example row
function downloadXeDailySampleFile() {
    const headers = ['Ngày', 'Tên kho', 'Loại ghi nhận', 'Số lượng xe', 'Biển số xe', 'Tên NCC', 'Trọng tải'];
    const exampleRow = [
        '17/07/2026',
        'Kho Giao Hàng Nặng - Hòa Xuân - Đà Nẵng',
        'Xe không hoạt động',
        '1',
        '43C-251.12',
        'Trần Xuân Phúc',
        '1400'
    ];
    
    if (typeof XLSX === 'undefined') {
        showToast('❌ Chưa tải được thư viện xuất Excel (SheetJS). Vui lòng tải lại trang.', 'error');
        return;
    }
    
    const wb = XLSX.utils.book_new();
    const ws_data = [
        headers,
        exampleRow
    ];
    const ws = XLSX.utils.aoa_to_sheet(ws_data);
    XLSX.utils.book_append_sheet(wb, ws, "Sample");
    XLSX.writeFile(wb, "mau-import-xe-van-hanh-daily.xlsx");
    showToast('✅ Đã tải file mẫu import xe vận hành (.xlsx).', 'success');
}

// Import file: read, send to backend, show result
async function importXeDailyFile() {
    const input = document.getElementById('xed-import-file');
    const resultEl = document.getElementById('xed-import-result');
    const btn = document.getElementById('btn-xed-import');

    if (!input || !input.files || !input.files[0]) {
        showToast('Vui lòng chọn file trước.', 'warning');
        return;
    }

    const file = input.files[0];
    const allowedExts = ['.csv', '.xlsx', '.xls'];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    if (!allowedExts.includes(ext)) {
        showToast('Chỉ hỗ trợ file .csv, .xlsx, .xls', 'error');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang import...';
    }
    if (resultEl) { resultEl.style.display = 'none'; resultEl.innerHTML = ''; }

    try {
        const formData = new FormData();
        formData.append('file', file);

        const token = getApiToken();
        const resp = await fetch(API + '/xe-van-hanh/import', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + token },
            body: formData
        });

        let data;
        try { data = await resp.json(); } catch(e) { data = { status: 'error', message: 'Phản hồi không hợp lệ từ server.' }; }

        if (!resp.ok || data.status === 'error') {
            const msg = (data && (data.message || data.detail)) || 'Lỗi không xác định từ server.';
            _showImportResult(resultEl, 'error', 'Lỗi: ' + msg, []);
            showToast('Import thất bại: ' + msg, 'error');
            return;
        }

        const saved = data.saved || 0;
        const errors = data.errors || 0;
        const dups = data.duplicates || 0;
        const total = data.total_read || 0;
        const errDetails = data.error_details || [];

        let summary = 'Import hoàn tất: <strong>' + saved + ' dòng thành công</strong>';
        if (errors > 0) summary += ', <span style="color:#ef4444">' + errors + ' dòng lỗi</span>';
        if (dups > 0) summary += ', <span style="color:#f59e0b">' + dups + ' dòng trùng (bỏ qua)</span>';
        summary += '. Tổng đọc: ' + total + ' dòng.';

        _showImportResult(resultEl, saved > 0 ? 'success' : (errors > 0 ? 'error' : 'warning'), summary, errDetails);

        if (saved > 0) {
            showToast('Import thành công ' + saved + '/' + total + ' bản ghi xe.', 'success');
            input.value = '';
            const nameEl = document.getElementById('xed-import-filename');
            if (nameEl) nameEl.textContent = 'Chưa chọn file';
            if (btn) btn.disabled = true;
            await loadXeDailyRecords();
        } else if (errors === 0 && dups > 0) {
            showToast('Tất cả ' + dups + ' dòng đã tồn tại trong hệ thống.', 'warning');
        } else {
            showToast('Không có dòng nào được lưu. Kiểm tra lại dữ liệu file.', 'warning');
        }

    } catch (err) {
        console.error('[XE DAILY IMPORT]', err);
        _showImportResult(resultEl, 'error', 'Lỗi kết nối: ' + err.message, []);
        showToast('Lỗi kết nối. Vui lòng thử lại.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-file-import"></i> Import Excel';
        }
    }
}

// Helper: show import result panel
function _showImportResult(el, type, html, errorDetails) {
    if (!el) return;
    const colors = {
        success: { bg: 'rgba(16,185,129,0.1)', border: '#10b981' },
        error:   { bg: 'rgba(239,68,68,0.1)',  border: '#ef4444' },
        warning: { bg: 'rgba(245,158,11,0.1)', border: '#f59e0b' },
    };
    const c = colors[type] || colors.warning;
    el.style.display = 'block';
    el.style.background = c.bg;
    el.style.border = '1px solid ' + c.border;
    el.style.borderRadius = '8px';

    let inner = '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">' + html;
    // Add download error button if there are errors
    if (errorDetails && errorDetails.length > 0) {
        inner += '<button onclick="_downloadXedImportErrors()" style="font-size:0.78rem;padding:4px 10px;border-radius:6px;border:1px solid #ef4444;background:rgba(239,68,68,0.15);color:#ef4444;cursor:pointer;display:inline-flex;align-items:center;gap:5px;white-space:nowrap;">'
             + '<i class="fa-solid fa-file-circle-exclamation"></i> Tải báo lỗi (.csv)</button>';
    }
    inner += '</div>';

    if (errorDetails && errorDetails.length > 0) {
        const MAX_SHOW = 10;
        const shown = errorDetails.slice(0, MAX_SHOW);
        inner += '<details style="margin-top:8px"><summary style="cursor:pointer;font-weight:600;color:#ef4444">Chi tiết ' + errorDetails.length + ' dòng lỗi ▾</summary>';
        inner += '<ul style="margin:6px 0 0 16px;padding:0;list-style:disc;">';
        shown.forEach(d => {
            inner += '<li><strong>Dòng ' + d.row + ':</strong> ' + escapeHtml(d.errors.join('; ')) + '</li>';
        });
        if (errorDetails.length > MAX_SHOW) {
            inner += '<li style="opacity:0.6">... và ' + (errorDetails.length - MAX_SHOW) + ' dòng lỗi khác.</li>';
        }
        inner += '</ul></details>';
    }
    el.innerHTML = inner;

    // Store error details for download
    el._errorDetails = errorDetails || [];
}

// Download error report CSV
function _downloadXedImportErrors() {
    const el = document.getElementById('xed-import-result');
    const errors = (el && el._errorDetails) ? el._errorDetails : [];
    if (!errors.length) {
        showToast('Không có lỗi nào để tải.', 'warning');
        return;
    }

    const BOM = '\uFEFF';
    const escape = v => {
        const s = String(v ?? '');
        if (s.includes(',') || s.includes('"') || s.includes('\n')) {
            return '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
    };

    const header = ['Số dòng trong file', 'Lỗi cần chỉnh sửa'];
    const rows = errors.map(d => [
        d.row,
        d.errors.join(' | ')
    ]);

    const lines = [header, ...rows].map(r => r.map(escape).join(','));
    const csvContent = BOM + lines.join('\n');

    const today = _getTodayVN().split('/').join('');
    const filename = 'bao-loi-import-xe-' + today + '.csv';

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Đã tải file báo lỗi: ' + filename, 'success');
}


// =====================================================================
// LOGIN LOGS — FRONTEND MANAGEMENT
// =====================================================================

let allLoginLogsData = []; // Lưu toàn bộ dữ liệu log đăng nhập để filter ở client

async function loadLoginLogs() {
    const tbody = document.getElementById('tbody-login-logs');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--text3)"><i class="fa-solid fa-spinner fa-spin"></i> Đang tải dữ liệu...</td></tr>`;

    try {
        const savedKey = sessionStorage.getItem('ghn_admin_key')
                      || localStorage.getItem('ghn_admin_key') || '';
        
        const resp = await fetch(`${API}/login-logs`, {
            method: 'GET',
            headers: {
                'X-Admin-Key': savedKey
            }
        });

        if (!resp.ok) {
            const err = await resp.json();
            tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--red)">Lỗi: ${err.detail || 'Không có quyền truy cập.'}</td></tr>`;
            return;
        }

        const res = await resp.json();
        allLoginLogsData = res.data || [];
        
        // Populate filter options
        _populateLogFilters(allLoginLogsData);
        
        // Render table
        renderLoginLogsTable(allLoginLogsData);
        
        // Render overview cards
        _renderLoginLogsOverview(allLoginLogsData);

    } catch (err) {
        console.error('[LOGIN LOG] Load error:', err);
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--red)">Lỗi kết nối. Vui lòng tải lại.</td></tr>`;
    }
}

function renderLoginLogsTable(records) {
    const tbody = document.getElementById('tbody-login-logs');
    const countEl = document.getElementById('log-history-count');
    if (!tbody) return;

    if (countEl) countEl.textContent = `${records.length} bản ghi`;

    if (!records.length) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:30px;color:var(--text3)">Không tìm thấy log đăng nhập nào phù hợp.</td></tr>`;
        return;
    }

    window.loginLogsTableLimit = window.loginLogsTableLimit || 100;
    const sliced = records.slice(0, window.loginLogsTableLimit);
    let html = sliced.map((r, idx) => {
        const loaiBadge = r.loai_truy_cap === 'Truy cập admin bằng key'
            ? `<span class="badge-tang-cuong" style="background:rgba(139,92,246,0.15);color:#8b5cf6;border:1px solid #8b5cf6;"><i class="fa-solid fa-user-shield"></i> Admin (Key)</span>`
            : `<span class="badge-off-xe" style="background:rgba(59,130,246,0.15);color:#3b82f6;border:1px solid #3b82f6;"><i class="fa-solid fa-user"></i> User</span>`;

        return `<tr>
            <td style="text-align:center;font-weight:700;color:var(--text3)">${idx + 1}</td>
            <td style="font-weight:600;color:var(--cyan);white-space:nowrap">${escapeHtml(r.ngay || '--')}</td>
            <td style="color:var(--text2);white-space:nowrap">${escapeHtml(r.thoi_gian || '--')}</td>
            <td style="font-family:monospace;font-weight:700">${escapeHtml(r.id_ghn || '--')}</td>
            <td style="font-weight:600;color:var(--text)">${escapeHtml(r.ho_ten || '--')}</td>
            <td style="font-size:0.82rem;color:var(--text2)">${escapeHtml(r.kho_phong_ban || '--')}</td>
            <td style="text-align:center;font-weight:700">${r.so_lan_trong_ngay || 1}</td>
            <td>${loaiBadge}</td>
            <td style="font-family:monospace;font-size:0.82rem;color:var(--text3)">${escapeHtml(r.ip || '--')}</td>
            <td style="font-size:0.75rem;color:var(--text3);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(r.user_agent || '')}">${escapeHtml(r.user_agent || '--')}</td>
        </tr>`;
    }).join('');
    
    if (records.length > window.loginLogsTableLimit) {
        html += `<tr><td colspan="10" style="text-align:center;padding:12px;"><button class="btn btn-secondary btn-sm" onclick="window.loginLogsTableLimit += 100; renderLoginLogsTable(allLoginLogsData);" style="cursor:pointer;padding:6px 12px;font-size:0.8rem;"><i class="fa-solid fa-angles-down"></i> Xem thêm (${records.length - window.loginLogsTableLimit} dòng còn lại)</button></td></tr>`;
    }
    tbody.innerHTML = html;
}

function _renderLoginLogsOverview(records) {
    const today = _getTodayVN();
    const todayLogs = records.filter(r => r.ngay === today);
    
    const totalToday = todayLogs.length;
    const uniqueIds = new Set(todayLogs.map(r => r.id_ghn)).size;
    
    const deptMap = {};
    todayLogs.forEach(r => {
        if (r.kho_phong_ban) {
            deptMap[r.kho_phong_ban] = (deptMap[r.kho_phong_ban] || 0) + 1;
        }
    });
    let topDept = '--';
    let topDeptVal = 0;
    for (const [dept, val] of Object.entries(deptMap)) {
        if (val > topDeptVal) {
            topDeptVal = val;
            topDept = dept;
        }
    }
    const cleanTopDept = topDept.replace(/Kho Giao Hàng Nặng[\\s\\-]+/gi, '').trim();
    
    const userMap = {};
    todayLogs.forEach(r => {
        if (r.id_ghn) {
            const key = `${r.ho_ten} (${r.id_ghn})`;
            userMap[key] = (userMap[key] || 0) + 1;
        }
    });
    let topUser = '--';
    let topUserVal = 0;
    for (const [user, val] of Object.entries(userMap)) {
        if (val > topUserVal) {
            topUserVal = val;
            topUser = user;
        }
    }

    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    setVal('log-val-total-today', totalToday);
    setVal('log-val-unique-today', uniqueIds);
    setVal('log-val-top-dept', topDeptVal > 0 ? `${cleanTopDept} (${topDeptVal} lượt)` : '--');
    setVal('log-val-top-user', topUserVal > 0 ? `${topUser} (${topUserVal} lần)` : '--');
}

function _populateLogFilters(records) {
    const dateSel = document.getElementById('log-filter-date');
    const deptSel = document.getElementById('log-filter-dept');

    if (dateSel) {
        const currVal = dateSel.value;
        const dates = [...new Set(records.map(r => r.ngay).filter(Boolean))].sort((a, b) => {
            const toNum = s => {
                const [d, m, y] = (s || '').split('/');
                return parseInt(y || 0) * 10000 + parseInt(m || 0) * 100 + parseInt(d || 0);
            };
            return toNum(b) - toNum(a);
        });
        dateSel.innerHTML = '<option value="">Tất cả ngày</option>' + 
            dates.map(d => `<option value="${d}"${d === currVal ? ' selected' : ''}>${d}</option>`).join('');
    }

    if (deptSel) {
        const currVal = deptSel.value;
        const depts = [...new Set(records.map(r => r.kho_phong_ban).filter(Boolean))].sort();
        deptSel.innerHTML = '<option value="">Tất cả Kho / Phòng ban</option>' +
            depts.map(d => `<option value="${d}"${d === currVal ? ' selected' : ''}>${escapeHtml(d)}</option>`).join('');
    }
}

function filterLoginLogs() {
    const dateVal = document.getElementById('log-filter-date')?.value || '';
    const idVal = document.getElementById('log-filter-id')?.value.trim() || '';
    const nameVal = document.getElementById('log-filter-name')?.value.trim().toLowerCase() || '';
    const deptVal = document.getElementById('log-filter-dept')?.value || '';

    let filtered = allLoginLogsData;

    if (dateVal) {
        filtered = filtered.filter(r => r.ngay === dateVal);
    }
    if (idVal) {
        filtered = filtered.filter(r => String(r.id_ghn).includes(idVal));
    }
    if (nameVal) {
        filtered = filtered.filter(r => String(r.ho_ten).toLowerCase().includes(nameVal));
    }
    if (deptVal) {
        filtered = filtered.filter(r => r.kho_phong_ban === deptVal);
    }

    renderLoginLogsTable(filtered);
}

function exportLoginLogsExcel() {
    if (typeof XLSX === 'undefined') {
        showToast('❌ Thư viện SheetJS chưa được tải.', 'error');
        return;
    }

    const tableRows = document.querySelectorAll('#tbody-login-logs tr');
    if (!tableRows.length || tableRows[0].textContent.includes('Không tìm thấy') || tableRows[0].textContent.includes('Đang tải')) {
        showToast('Không có dữ liệu để xuất.', 'warning');
        return;
    }

    const headers = ['STT', 'Ngày', 'Thời gian', 'ID GHN', 'Họ và Tên', 'Tên Kho / Phòng ban', 'Số lần đăng nhập trong ngày', 'Loại truy cập', 'IP', 'User Agent'];
    const data = [headers];

    tableRows.forEach(row => {
        const cols = row.querySelectorAll('td');
        if (cols.length >= 10) {
            data.push(Array.from(cols).map(c => c.textContent.trim()));
        }
    });

    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(data);
    XLSX.utils.book_append_sheet(wb, ws, "Login Logs");

    const today = _getTodayVN().split('/').join('');
    const filename = `log-dang-nhap-${today}.xlsx`;

    XLSX.writeFile(wb, filename);
    showToast(`✅ Đã xuất dữ liệu log đăng nhập ra file ${filename}`, 'success');
}

// =====================================================================
// GLOBAL ERROR BOUNDARY HANDLER
// =====================================================================
window.addEventListener('error', function(event) {
    console.error('Global Error Boundary caught error:', event.error || event.message);
    const boundary = document.getElementById('app-error-boundary');
    const msgEl = document.getElementById('app-error-msg');
    if (boundary) {
        boundary.style.display = 'flex';
        // Hide standard containers to clean viewport
        const loginWrapper = document.getElementById('login-wrapper');
        const profileWrapper = document.getElementById('profile-wrapper');
        const appContainer = document.getElementById('app-container');
        if (loginWrapper) loginWrapper.style.display = 'none';
        if (profileWrapper) profileWrapper.style.display = 'none';
        if (appContainer) appContainer.style.display = 'none';

        if (msgEl) {
            const detailMsg = (event.error && event.error.message) ? event.error.message : event.message;
            msgEl.innerHTML = `Không tải được bước nhập thông tin cá nhân hoặc ứng dụng.<br>` +
                              `<small style="opacity:0.6;font-family:monospace;font-size:0.75rem;">Chi tiết: ${detailMsg}</small>`;
        }
    }
});

// =====================================================================
// LAZY LOADING CORE & SKELETONS
// =====================================================================
const sectionLoadingStates = {};

async function ensureSectionData(name, force = false) {
    const query = force ? '?force=true' : '';
    if (sectionLoadingStates[name]) return;

    let endpoints = [];
    let needsLoad = false;

    if (name === 'overview') {
        endpoints = [
            { key: 'overview', url: `/api/dashboard/overview${query}` },
            { key: 'warningsData', url: `/api/warnings${query}` }
        ];
        if (force || !state.overview || Object.keys(state.overview).length === 0) needsLoad = true;
    } else if (name === 'gtc') {
        endpoints = [
            { key: 'gtcData', url: `/api/kpi/gtc${query}` },
            { key: 'nangSuatData', url: `/api/nang-suat${query}` }
        ];
        if (force || !state.gtcData || state.gtcData.length === 0) needsLoad = true;
    } else if (name === 'returns') {
        endpoints = [
            { key: 'returnsData', url: `/api/returns${query}` },
            { key: 'returnsByClientData', url: `/api/returns/by-client${query}` }
        ];
        if (force || !state.returnsData || state.returnsData.length === 0) needsLoad = true;
    } else if (name === 'dontao') {
        endpoints = [
            { key: 'donTaoData', url: `/api/don-tao${query}` }
        ];
        if (force || !state.donTaoData || state.donTaoData.length === 0) needsLoad = true;
    } else if (name === 'backlog') {
        endpoints = [
            { key: 'backlogData', url: `/api/backlog/critical${query}` },
            { key: 'b2bData', url: `/api/backlog/b2b${query}` }
        ];
        if (force || !state.backlogData || state.backlogData.length === 0) needsLoad = true;
    } else if (name === 'personnel') {
        endpoints = [
            { key: 'personnelData', url: `/api/personnel${query}` }
        ];
        if (force || !state.personnelData || state.personnelData.length === 0) needsLoad = true;
    } else if (name === 'khoxe' || name === 'b2b-map') {
        endpoints = [
            { key: 'xeGxtData', url: `/api/xe-gxt${query}` },
            { key: 'xeSuCoData', url: `/api/xe-su-co${query}` },
            { key: 'khoGxtData', url: `/api/kho-gxt${query}` }
        ];
        if (force || !state.khoGxtData || state.khoGxtData.length === 0) needsLoad = true;
    } else if (name === 'gtc-b2b-prio') {
        endpoints = [
            { key: 'gtcB2bData', url: `/api/kpi/gtc-b2b${query}` },
            { key: 'donB2bData', url: `/api/kpi/don-b2b${query}` }
        ];
        if (force || !state.gtcB2bData || state.gtcB2bData.length === 0) needsLoad = true;
    }

    if (!needsLoad) {
        renderSection(name);
        return;
    }

    showSectionSkeleton(name);

    try {
        sectionLoadingStates[name] = true;
        const startTime = Date.now();
        
        // Fetch concurrently
        const promises = endpoints.map(e => {
            const isOverview = e.key.includes('overview') || e.key.includes('warnings');
            return authFetch(`${API}${e.url.replace('/api', '')}`, isOverview ? {} : { data: [] });
        });
        const results = await Promise.all(promises);
        
        const duration = ((Date.now() - startTime) / 1000).toFixed(2);
        console.log(`[PERFORMANCE LOG] Lazy load for tab '${name}' finished in ${duration}s.`);

        endpoints.forEach((e, idx) => {
            const res = results[idx];
            if (e.key === 'overview') {
                state[e.key] = res || {};
            } else {
                if (res && Array.isArray(res.data)) {
                    state[e.key] = res.data;
                } else if (Array.isArray(res)) {
                    state[e.key] = res;
                } else {
                    state[e.key] = [];
                }
            }
        });

        renderSection(name);
    } catch (err) {
        console.error(`[LAZY LOAD ERROR] Failed to load data for ${name}:`, err);
        showSectionError(name);
    } finally {
        sectionLoadingStates[name] = false;
        hideSectionSkeleton(name);
    }
}

function retryLoadSection(name) {
    ensureSectionData(name, true);
}
window.retryLoadSection = retryLoadSection;

function renderSection(name) {
    updateMeta();
    if (name === 'overview') {
        renderOverviewCards();
        renderGtcTrendChart();
        renderReturnsPieChart();
        renderOverviewB2bChart();
        renderBacklogOverviewTable();
        renderB2bOverviewTable();
        renderCriticalWarningsOverview();
        renderPersonnelOverview();
    } else if (name === 'gtc') {
        renderGtcSection();
        renderGtcByKhoChart();
        renderGtcTopBottom();
        renderNangSuatSection();
        renderNangSuatVungSection();
    } else if (name === 'returns') {
        renderReturnsSection();
        renderReturnsFDChart();
    } else if (name === 'dontao') {
        renderDonTaoSection();
        renderForecastSection();
    } else if (name === 'backlog') {
        renderBacklogSection();
        renderBacklogByKhoChart();
    } else if (name === 'personnel') {
        renderPersonnelSection();
    } else if (name === 'khoxe') {
        renderXeGxtSection();
        renderXeSuCoSection();
        renderKhoGxtSection();
    } else if (name === 'b2b-map') {
        if (typeof window.renderB2BMapSection === 'function') {
            window.renderB2BMapSection();
        }
        setTimeout(() => {
            if (window.b2bLeafletMap) {
                window.b2bLeafletMap.invalidateSize();
            }
            if (typeof filterB2BMapData === 'function') {
                filterB2BMapData();
            }
        }, 100);
    } else if (name === 'gtc-b2b-prio') {
        renderGtcB2bPrioSection();
    }
    updateNavBadges();
}

function showSectionSkeleton(name) {
    const sectionEl = document.getElementById('section-' + name);
    if (!sectionEl) return;
    
    const existing = sectionEl.querySelector('.section-loading-overlay');
    if (existing) existing.remove();
    
    const overlay = document.createElement('div');
    overlay.className = 'section-loading-overlay';
    overlay.innerHTML = `
        <div class="spinner-container" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:350px;gap:16px;color:var(--text2, #94a3b8);background:rgba(15,23,42,0.15);backdrop-filter:blur(4px);border-radius:12px;">
            <i class="fa-solid fa-spinner fa-spin-pulse" style="font-size:42px;color:var(--blue, #3b82f6);"></i>
            <span style="font-size:0.95rem;font-weight:500;">Đang tải dữ liệu... Vui lòng chờ</span>
        </div>
    `;
    sectionEl.prepend(overlay);
    
    Array.from(sectionEl.children).forEach(child => {
        if (child !== overlay) {
            child.style.opacity = '0.05';
            child.style.pointerEvents = 'none';
        }
    });
}

function hideSectionSkeleton(name) {
    const sectionEl = document.getElementById('section-' + name);
    if (!sectionEl) return;
    const overlay = sectionEl.querySelector('.section-loading-overlay');
    if (overlay) overlay.remove();
    
    Array.from(sectionEl.children).forEach(child => {
        child.style.opacity = '';
        child.style.pointerEvents = '';
    });
}

function showSectionError(name) {
    const sectionEl = document.getElementById('section-' + name);
    if (!sectionEl) return;
    
    const overlay = sectionEl.querySelector('.section-loading-overlay');
    if (overlay) overlay.remove();
    
    const errDiv = document.createElement('div');
    errDiv.className = 'section-loading-overlay';
    errDiv.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:350px;gap:16px;color:#ef4444;text-align:center;padding:24px;background:rgba(15,23,42,0.25);backdrop-filter:blur(4px);border-radius:12px;">
            <i class="fa-solid fa-triangle-exclamation" style="font-size:42px;"></i>
            <span style="font-size:1rem;font-weight:600;color:var(--text, #f8fafc);">Không tải được dữ liệu</span>
            <span style="font-size:0.85rem;color:var(--text3, #94a3b8);max-width:380px;">Đã xảy ra sự cố kết nối máy chủ hoặc Google Sheets đang cập nhật.</span>
            <button onclick="window.retryLoadSection('${name}')" class="btn btn-secondary" style="margin-top:12px;padding:8px 20px;display:inline-flex;align-items:center;gap:8px;">
                <i class="fa-solid fa-rotate-right"></i> Thử lại
            </button>
        </div>
    `;
    sectionEl.prepend(errDiv);
    
    Array.from(sectionEl.children).forEach(child => {
        if (child !== errDiv) {
            child.style.opacity = '0.05';
            child.style.pointerEvents = 'none';
        }
    });
}
