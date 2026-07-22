import re

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Hide nav-odo-monitor in sidebar if not already hidden
content = content.replace(
    '<a href="#" class="nav-item" data-section="odo-monitor" id="nav-odo-monitor">',
    '<a href="#" class="nav-item" data-section="odo-monitor" id="nav-odo-monitor" style="display: none;">'
)

# Extract ODO section content (between <section class="section" id="section-odo-monitor"...> and </section>)
odo_pattern = r'(<!-- ===== SECTION: THEO DÕI ODO XE ===== -->\s*<section class="section" id="section-odo-monitor"[^>]*>)(.*?)(</section>)'
match = re.search(odo_pattern, content, re.DOTALL)

if match:
    odo_html_inner = match.group(2)
    # Remove standalone <section id="section-odo-monitor">
    content = re.sub(odo_pattern, '', content, flags=re.DOTALL)
else:
    print("WARNING: ODO section not matched!")
    odo_html_inner = ""

# Now find <section class="section" id="section-xe-daily"> and replace its inner HTML with tab bar + 2 subtab divs
xe_daily_start_pattern = r'(<!-- ===== SECTION: XE VẬN HÀNH DAILY ===== -->\s*<section class="section" id="section-xe-daily">)'
xe_daily_end_pattern = r'(\s*</section>\s*<!-- ===== SECTION: LOG ĐĂNG NHẬP ===== -->)'

m_start = re.search(xe_daily_start_pattern, content)
m_end = re.search(xe_daily_end_pattern, content)

if m_start and m_end:
    start_pos = m_start.end()
    end_pos = m_end.start()
    
    offtc_html_inner = content[start_pos:end_pos]
    
    new_xe_daily_inner = f"""
            <!-- THANH TAB NGANG CHUYỂN ĐỔI 2 SUB-TAB -->
            <div class="xe-daily-tabs-container" style="display:flex;gap:12px;margin-bottom:20px;border-bottom:1px solid var(--border-card);padding-bottom:12px">
                <button class="xe-daily-tab-btn active" id="tab-btn-odo" onclick="switchXeDailySubTab('odo')">
                    <i class="fa-solid fa-gauge-high"></i> Theo Dõi ODO Xe
                </button>
                <button class="xe-daily-tab-btn" id="tab-btn-offtc" onclick="switchXeDailySubTab('offtc')">
                    <i class="fa-solid fa-truck-moving"></i> Theo Dõi Xe Off / Tăng Cường
                </button>
            </div>

            <!-- SUB-TAB 1: THEO DÕI ODO XE (MẶC ĐỊNH) -->
            <div id="subtab-xe-daily-odo" class="xe-daily-subtab-content">
                {odo_html_inner.strip()}
            </div>

            <!-- SUB-TAB 2: THEO DÕI XE OFF / TĂNG CƯỜNG -->
            <div id="subtab-xe-daily-offtc" class="xe-daily-subtab-content" style="display:none">
                {offtc_html_inner.strip()}
            </div>
    """
    
    content = content[:start_pos] + new_xe_daily_inner + content[end_pos:]
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully merged index.html sections!")
else:
    print("ERROR: xe-daily section bounds not found!")
