"""
Momentum นำตลาด Scanner — Streamlit App v2.1
==============================================
สแกนหุ้นตามกลยุทธ์ "Momentum นำตลาด" 7 เงื่อนไข

  1. Universe: S&P 500 / SET100
  2. Price > EMA20
  3. EMA20 > EMA50
  4. EMA50 > EMA200
  5. ราคายืดจาก EMA20 ไม่เกิน X%  →  (Close - EMA20) / EMA20 <= X%
  6. RS = (Close ล่าสุด - Close N แท่งก่อน) / Close N แท่งก่อน × 100
  7. เลือก Top N ที่ RS สูงสุด

หมายเหตุ: เคยลองสลับไปเรียงด้วย Extension แทน (30 ก.ค. 2026) แล้วลองตัด RS
         ออกทั้งหมด แต่กลับมาใช้ RS เป็นตัวจัดอันดับหลักเหมือนเดิมแล้ว

สิ่งที่จงใจ "ไม่ทำ" (อย่าเพิ่มกลับเข้ามาโดยไม่ทดสอบ):
  - ไม่ใช้ ThreadPoolExecutor — yfinance ไม่ thread-safe บน Streamlit Cloud (segfault)
  - ไม่เรียก get_analyst_price_targets() — ยิง request เพิ่มเท่าตัวไปที่ endpoint
    quoteSummary ที่ต้องขอ cookie+crumb ทุกครั้ง เป็น code path หนักของ curl_cffi
    (ไลบรารีภาษา C) ยิงถี่หลายร้อยครั้งแล้วพังระดับ C = Segmentation fault

──────────────────────────────────────────────────────────────
บันทึกสาเหตุ: ทำไมต้องมี AsOfDate  (27 ก.ค. 2026)
──────────────────────────────────────────────────────────────
อาการ: ผลสแกนของแอปนี้ไม่ตรงกับฝั่ง Vercel (ต่างกัน 1 วันทำการ)

สาเหตุจริง — ไม่ใช่บั๊กของโค้ด:
  Yahoo Finance ส่งแท่งวันศุกร์ 24 ก.ค. มาให้ครบ (Open/High/Low/Volume ปกติ)
  แต่ Close และ Adj Close เป็น None แล้วบรรทัด dropna(subset=["Close"])
  ก็ลบแท่งนั้นทิ้งอย่างเงียบๆ → เหลือแท่งสุดท้ายเป็นพฤหัส 23 ก.ค.

  ที่ Vercel ได้ข้อมูลถูกเพราะมันสแกนตอน 26 ก.ค. 23:00 UTC ซึ่งตอนนั้น
  Yahoo ยังมี Close ครบ ต่อมาข้อมูลถูกแก้ย้อนหลังจนหาย
  = ตักน้ำบ่อเดียวกันคนละเวลา แล้วบ่อมันเปลี่ยนเอง

  (ยืนยันเพิ่มจาก Volume: วันอื่นปัดลงท้าย 00 แต่วันศุกร์เป็น 1,697,465
   ไม่ปัด = ลายเซ็นของแถวที่ Yahoo ยังไม่ปิดยอด)

บทเรียน: dropna เป็นสิ่งจำเป็น (คำนวณ EMA จาก NaN ไม่ได้) แต่ต้องไม่ลบเงียบๆ
        ทางแก้จึงไม่ใช่การเอา dropna ออก แต่คือ "บอกให้ชัดว่าใช้ข้อมูลวันไหน"
        → นั่นคือหน้าที่ของ AsOfDate ในไฟล์นี้

จุดที่เกี่ยวข้องกับ AsOfDate (ห้ามลบ):
  [1] เก็บ as_of ก่อน reset_index(drop=True) ที่โยน index วันที่ทิ้ง
  [2] ส่ง AsOfDate ออกไปกับผลลัพธ์ทุกแถว (ติดไปใน CSV ด้วย)
  [3] กดปุ่ม Scan = ล้าง session_state ผลเก่า (Clear cache / Rerun ไม่ล้างให้)
  [4] แสตมป์วันที่บนหน้าจอ + ตั้งชื่อไฟล์ CSV ตามวันที่ของข้อมูล
      ไม่ใช่วันที่กดปุ่ม (ของเดิมใช้ datetime.now() จนหลงทางมาหลายชั่วโมง)

──────────────────────────────────────────────────────────────
บันทึกสาเหตุ: ทำไมต้องตัดแท่งที่ยังไม่ปิดตลาดทิ้ง  (30 ก.ค. 2026)
──────────────────────────────────────────────────────────────
อาการ: กดปุ่ม Scan 2 ครั้งห่างกันไม่กี่นาทีตอนตลาดเปิดอยู่ ได้ Close/Extension
      ไม่ตรงกัน ทั้งที่เป็นสัญลักษณ์เดียวกันและวันเดียวกัน

สาเหตุ: yf.download(interval="1d") ระหว่างตลาดเปิด จะส่งแท่ง "วันนี้" มาด้วย
       โดย Close ของแท่งนั้นคือราคาล่าสุด ณ ขณะนั้น ไม่ใช่ราคาปิดจริง
       (Volume ก็ยังนับไม่ครบเช่นกัน) แท่งนี้จะขยับไปเรื่อยๆ จนกว่าตลาดจะปิด

ทางแก้: [5] is_bar_closed() เช็คว่าแท่งสุดท้ายเป็นของ "วันนี้" หรือไม่
       ถ้าใช่ ต้องเลยเวลาปิดตลาดของตลาดนั้นๆ ไปแล้วเท่านั้นถึงจะนับว่าปิด
       ไม่งั้นตัดทิ้งแล้วใช้แท่งของวันก่อนหน้าแทนเสมอ
       (สแกนกี่ครั้งใน 1 วันเดียวกัน ก่อนตลาดปิด ก็ได้ค่าเดิมทุกครั้ง)
         - หุ้น .BK (SET)  → เวลาไทย ปิด 16:30 น.
         - หุ้นอื่นๆ (US)  → เวลานิวยอร์ก ปิด 16:00 น. (รองรับ DST อัตโนมัติ)

หมายเหตุ HTML: ห้ามเว้นวรรคหน้าบรรทัดใน HTML ที่ส่งเข้า st.markdown()
              เพราะ Markdown มองย่อหน้า 4 ช่องขึ้นไปเป็น code block
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


# ══════════════════════════════════════════════════════
#  หา path ของไฟล์ CSV แบบทนทาน
#  รองรับทั้งกรณีรันจาก root ของรีโป และรันจากโฟลเดอร์ streamlit_app/
#  (Streamlit Cloud รันจาก root เสมอ แต่ตอนรัน local อาจ cd เข้ามาในโฟลเดอร์)
# ══════════════════════════════════════════════════════
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)


def find_csv(filename: str):
    """คืน path แรกที่เจอไฟล์จริง ไม่เจอเลยคืน None"""
    candidates = [
        os.path.join("data", filename),                  # รันจาก root ของรีโป (Streamlit Cloud)
        os.path.join(_REPO_ROOT, "data", filename),      # อ้างอิงจากตำแหน่งไฟล์ app.py
        os.path.join(_HERE, "data", filename),           # เผื่อ data/ อยู่ข้างๆ app.py
        filename,                                        # เผื่อวางไว้ที่เดียวกับ app.py เลย
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

st.set_page_config(page_title="Momentum นำตลาด Scanner", page_icon="🚩", layout="wide")

# ══════════════════════════════════════════════════════
#  THEME — Navy/Gold + ฟอนต์ Kanit + Hero Banner
#  (เป็นแค่ CSS/SVG ล้วน ไม่เพิ่ม dependency ใหม่เลย)
# ══════════════════════════════════════════════════════
st.markdown("""
<style>
/* หมายเหตุ: ฟอนต์ Kanit ประกาศไว้ใน .streamlit/config.toml แล้ว
   (ใช้ @import + selector [class*="css"] ที่นี่ไม่ได้ผลกับ Streamlit เวอร์ชั่นใหม่) */

/* Hero banner */
.hero {
    position: relative;
    border-radius: 16px;
    padding: 2rem 2.2rem;
    margin-bottom: 1.5rem;
    background: linear-gradient(120deg, #0B1F3A 0%, #132A4E 55%, #1B3A63 100%);
    border: 1px solid rgba(212, 175, 55, 0.35);
    overflow: hidden;
}
.hero-title {
    font-size: 2rem;
    font-weight: 700;
    color: #F1D77A;
    margin: 0;
    letter-spacing: 0.5px;
}
.hero-sub {
    color: #F5F1E6;
    opacity: 0.82;
    font-size: 0.95rem;
    margin-top: 0.5rem;
    max-width: 620px;
    line-height: 1.7;
}
.hero-tag {
    display: inline-block;
    margin-top: 0.9rem;
    padding: 0.25rem 0.8rem;
    border: 1px solid #D4AF37;
    border-radius: 999px;
    color: #D4AF37;
    font-size: 0.75rem;
    letter-spacing: 0.8px;
}
.hero-svg {
    position: absolute;
    top: 0; right: 0;
    height: 100%;
    opacity: 0.85;
    pointer-events: none;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background-color: #132A4E;
    border: 1px solid rgba(212, 175, 55, 0.22);
    border-radius: 12px;
    padding: 0.75rem 1rem;
}
div[data-testid="stMetric"] label {
    color: #D4AF37 !important;
}

/* Primary button */
.stButton > button[kind="primary"] {
    background-color: #D4AF37;
    color: #0B1F3A;
    font-weight: 600;
    border: none;
}
.stButton > button[kind="primary"]:hover {
    background-color: #F1D77A;
    color: #0B1F3A;
}

/* Sidebar accent */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(212, 175, 55, 0.2);
}

/* ═══════════ DATA STAMP ═══════════ */
.data-stamp {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    background: rgba(212, 175, 55, 0.07);
    border: 1px solid rgba(212, 175, 55, 0.28);
    border-left: 3px solid #D4AF37;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    margin: 0.4rem 0 0.9rem 0;
    font-size: 0.82rem;
    color: #F5F1E6;
}
.stamp-key {
    color: #D4AF37;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-size: 0.68rem;
}
.stamp-val { font-weight: 600; color: #F1D77A; font-size: 0.95rem; }
.stamp-sep { width: 1px; height: 18px; background: rgba(212, 175, 55, 0.25); }
.stamp-dim { opacity: 0.6; }
.stamp-warn {
    background: rgba(224, 122, 95, 0.16);
    color: #E89B84;
    border-radius: 999px;
    padding: 0.1rem 0.55rem;
    font-size: 0.7rem;
    font-weight: 500;
}

/* ═══════════ SUMMARY STRIP ═══════════ */
.summary-strip {
    display: flex;
    align-items: center;
    gap: 0;
    background: #132A4E;
    border: 1px solid rgba(212, 175, 55, 0.22);
    border-radius: 12px;
    padding: 1rem 1.4rem;
    margin: 0.5rem 0 1.6rem 0;
    flex-wrap: wrap;
}
.sum-item { flex: 1; min-width: 130px; padding: 0 0.6rem; }
.sum-div {
    width: 1px; height: 34px;
    background: rgba(212, 175, 55, 0.18);
}
.sum-label {
    font-size: 0.7rem;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #F5F1E6;
    opacity: 0.55;
    margin-bottom: 0.25rem;
}
.sum-value {
    font-size: 1.5rem;
    font-weight: 600;
    color: #F5F1E6;
    line-height: 1.2;
}
.sum-gold { color: #F1D77A; }
.sum-unit {
    font-size: 0.85rem;
    font-weight: 400;
    opacity: 0.6;
    margin-left: 0.25rem;
}

/* ═══════════ BOARD HEADER ═══════════ */
.board-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0 0.4rem 0.6rem 0.4rem;
    font-size: 0.8rem;
    letter-spacing: 0.6px;
    color: #D4AF37;
    text-transform: uppercase;
    border-bottom: 1px solid rgba(212, 175, 55, 0.18);
    margin-bottom: 0.3rem;
}
.board-hint {
    color: #F5F1E6;
    opacity: 0.4;
    text-transform: none;
    letter-spacing: 0;
    font-size: 0.72rem;
}

/* ═══════════ LEADERBOARD ROWS ═══════════ */
.board { display: flex; flex-direction: column; }

.row {
    display: grid;
    grid-template-columns: 42px 88px 190px 1fr 78px 26px;
    align-items: center;
    gap: 0.7rem;
    padding: 0.7rem 0.6rem;
    border-bottom: 1px solid rgba(245, 241, 230, 0.06);
    text-decoration: none !important;
    transition: background 0.15s ease, transform 0.15s ease;
}
.row:hover {
    background: rgba(212, 175, 55, 0.07);
    transform: translateX(3px);
}
.row.is-leader {
    background: rgba(212, 175, 55, 0.09);
    border-left: 2px solid #D4AF37;
    border-radius: 6px 0 0 6px;
}

.r-rank {
    font-size: 0.95rem;
    font-weight: 500;
    color: #F5F1E6;
    opacity: 0.42;
    text-align: center;
}
.is-leader .r-rank { opacity: 1; font-size: 1.1rem; }

.r-sym {
    font-size: 1.15rem;
    font-weight: 600;
    color: #F5F1E6;
    letter-spacing: 0.4px;
}
.is-leader .r-sym { color: #F1D77A; }

.r-price {
    font-size: 0.95rem;
    color: #F5F1E6;
    opacity: 0.9;
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
}

.ext-chip {
    font-size: 0.66rem;
    padding: 0.1rem 0.42rem;
    border-radius: 999px;
    white-space: nowrap;
    font-weight: 500;
}
.ext-cool { background: rgba(93, 191, 137, 0.15); color: #7FD6A4; }
.ext-mid  { background: rgba(212, 175, 55, 0.15); color: #E3C55F; }
.ext-hot  { background: rgba(224, 122, 95, 0.16); color: #E89B84; }

/* ── SIGNATURE: แถบวัดพลังโมเมนตัม ── */
.r-bar-wrap {
    height: 7px;
    background: rgba(245, 241, 230, 0.06);
    border-radius: 999px;
    overflow: hidden;
    min-width: 60px;
}
.r-bar {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #8A6D1F 0%, #D4AF37 65%, #F1D77A 100%);
}
.is-leader .r-bar {
    background: linear-gradient(90deg, #D4AF37 0%, #F1D77A 100%);
    box-shadow: 0 0 10px rgba(241, 215, 122, 0.45);
}

.r-rs {
    font-size: 1rem;
    font-weight: 600;
    color: #F1D77A;
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.r-go {
    color: #D4AF37;
    opacity: 0;
    text-align: center;
    font-size: 0.9rem;
    transition: opacity 0.15s ease;
}
.row:hover .r-go { opacity: 1; }

/* มือถือ: ยุบแถบ RS ทิ้ง ให้เหลือข้อมูลที่จำเป็น */
@media (max-width: 640px) {
    .row { grid-template-columns: 34px 70px 1fr 66px; }
    .r-bar-wrap, .r-go { display: none; }
}

@media (prefers-reduced-motion: reduce) {
    .row, .r-go { transition: none; }
    .row:hover { transform: none; }
}
</style>

<div class="hero">
  <svg class="hero-svg" viewBox="0 0 260 150" xmlns="http://www.w3.org/2000/svg">
    <circle cx="185" cy="78" r="46" fill="#F1D77A" opacity="0.92"/>
    <circle cx="168" cy="62" r="5"  fill="#0B1F3A" opacity="0.28"/>
    <circle cx="199" cy="88" r="7"  fill="#0B1F3A" opacity="0.22"/>
    <circle cx="178" cy="98" r="4"  fill="#0B1F3A" opacity="0.26"/>
    <circle cx="205" cy="60" r="3"  fill="#0B1F3A" opacity="0.24"/>
    <line x1="185" y1="46" x2="185" y2="12" stroke="#D4AF37" stroke-width="2.5"/>
    <path d="M185 12 L214 21 L185 30 Z" fill="#D4AF37"/>
    <circle cx="42"  cy="26" r="1.6" fill="#F5F1E6" opacity="0.55"/>
    <circle cx="95"  cy="15" r="1.2" fill="#F5F1E6" opacity="0.4"/>
    <circle cx="128" cy="40" r="1.4" fill="#F5F1E6" opacity="0.45"/>
    <circle cx="70"  cy="58" r="1.1" fill="#F5F1E6" opacity="0.35"/>
  </svg>
  <div class="hero-title">🚩 Momentum นำตลาด</div>
  <div class="hero-sub">
    โลกจำนีล อาร์มสตรองได้ แต่จำคนที่สองไม่ได้ —
    สปอตไลท์ของตลาดก็ส่องไปที่ผู้นำก่อนเสมอ<br/>
    ระบบนี้ตามหาหุ้นที่เทรนด์แข็งแรง วิ่งนำตลาด และยังไม่ยืดจนไล่ไม่ทัน
  </div>
  <div class="hero-tag">SCAN ON DEMAND · LIVE DATA</div>
</div>
""", unsafe_allow_html=True)

# ── Session State ─────────────────────────────────────
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "scan_done" not in st.session_state:
    st.session_state.scan_done = False
# จำเวลาที่ "กดสแกนจริง" ไว้ เพื่อแยกจากเวลาที่ rerun หน้าจอ
if "scan_run_at" not in st.session_state:
    st.session_state.scan_run_at = None

# ══════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ ตั้งค่า")

    # ── รายชื่อหุ้น ──────────────────────────────────
    st.subheader("📁 รายชื่อหุ้น")
    market_mode = st.radio(
        "เลือก Market",
        options=["อัพโหลด CSV", "S&P 500 (preset)", "SET100 (preset)", "พิมพ์เอง"],
    )

    symbols = []

    if market_mode == "อัพโหลด CSV":
        uploaded_file = st.file_uploader(
            "อัพโหลดไฟล์ CSV (ต้องมีคอลัมน์ Symbol)", type=["csv"]
        )
        if uploaded_file:
            df_sym = pd.read_csv(uploaded_file)
            if "Symbol" in df_sym.columns:
                symbols = df_sym["Symbol"].dropna().astype(str).str.strip().tolist()
                st.success(f"โหลดได้ {len(symbols)} หุ้น ✅")
            else:
                st.error("❌ ไม่พบคอลัมน์ 'Symbol'")

    elif market_mode == "S&P 500 (preset)":
        path = find_csv("sp500_symbols.csv")
        if path is None:
            st.error("❌ ไม่พบไฟล์ data/sp500_symbols.csv")
        else:
            df_sym = pd.read_csv(path)
            if "Symbol" in df_sym.columns:
                symbols = df_sym["Symbol"].dropna().astype(str).str.strip().tolist()
                st.success(f"โหลด S&P 500 ได้ {len(symbols)} หุ้น ✅")
                st.caption(f"ไฟล์: `{path}`")
            else:
                st.error("❌ ไม่พบคอลัมน์ 'Symbol' ใน sp500_symbols.csv")

    elif market_mode == "SET100 (preset)":
        path = find_csv("set100_symbols.csv")
        if path is None:
            st.error("❌ ไม่พบไฟล์ data/set100_symbols.csv")
        else:
            df_sym = pd.read_csv(path)
            if "Symbol" in df_sym.columns:
                symbols = df_sym["Symbol"].dropna().astype(str).str.strip().tolist()
                st.success(f"โหลด SET100 ได้ {len(symbols)} หุ้น ✅")
                st.caption(f"ไฟล์: `{path}`")
            else:
                st.error("❌ ไม่พบคอลัมน์ 'Symbol' ใน set100_symbols.csv")

    elif market_mode == "พิมพ์เอง":
        st.caption("พิมพ์ symbol คั่นด้วย comma หรือ newline")
        manual_input = st.text_area("Symbol", placeholder="เช่น AAPL, MSFT\nหรือแต่ละบรรทัด")
        if manual_input.strip():
            raw = manual_input.replace(",", "\n")
            symbols = [s.strip() for s in raw.splitlines() if s.strip()]
            st.success(f"โหลดได้ {len(symbols)} หุ้น ✅")

    # ── Parameters ───────────────────────────────────
    st.divider()
    st.subheader("🔧 Parameters")

    st.markdown("**เงื่อนไขที่ 2-4 — โครงสร้างเทรนด์ (Price > EMA เร็ว > กลาง > ช้า)**")
    ema_fast = st.number_input("EMA เร็ว", min_value=5, max_value=100, value=20, step=5)
    ema_mid = st.number_input("EMA กลาง", min_value=10, max_value=200, value=50, step=10)
    ema_slow = st.number_input("EMA ช้า", min_value=50, max_value=400, value=200, step=10)

    st.markdown("**เงื่อนไขที่ 5 — ห้ามไล่ราคาแพงเกินไป**")
    max_extension_pct = st.slider(
        "ราคายืดจาก EMA เร็วได้ไม่เกิน (%)",
        min_value=2.0, max_value=25.0, value=10.0, step=0.5,
        help="ยิ่งน้อย = จับได้ Early มาก (ยังไม่วิ่งไปไกล)"
    )

    st.markdown("**เงื่อนไขที่ 6-7 — จัดอันดับด้วย Relative Strength**")
    rs_bars = st.number_input(
        "นับ RS ย้อนหลังกี่ bars",
        min_value=5, max_value=60, value=20, step=5,
        help="20 bars = ~1 เดือน"
    )
    top_n = st.number_input(
        "แสดง Top N ตัวที่ RS สูงสุด",
        min_value=5, max_value=100, value=20, step=5
    )

    st.divider()
    scan_btn = st.button("🔍 เริ่ม Scan", type="primary", use_container_width=True)

# ══════════════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════════════
def to_tv_format(symbol):
    if symbol.endswith(".BK"):
        return f"SET:{symbol[:-3]}"
    return symbol


def is_bar_closed(bar_date, symbol: str) -> bool:
    """
    เช็คว่า "แท่งราคาล่าสุด" ของ symbol นี้ปิดตลาดแล้วจริงหรือยัง

    ป้องกันปัญหา: กดสแกนตอนตลาดเปิด → yfinance ส่ง Close ของแท่งวันนี้มา
    ทั้งที่ราคายังขยับอยู่ (ไม่ใช่ราคาปิดจริง) → สแกนซ้ำแต่ละครั้งได้ค่าไม่ตรงกัน

    หลักการ: แท่งของวันเก่ากว่าวันนี้ (ตามเวลาตลาดนั้นๆ) = ปิดแน่นอน
             แท่งของ "วันนี้" ต้องเช็คว่าเลยเวลาปิดตลาดไปแล้วหรือยัง
    """
    if symbol.endswith(".BK"):
        tz = ZoneInfo("Asia/Bangkok")
        close_hour, close_min = 16, 30   # SET ปิด 16:30 น. เวลาไทย
    else:
        tz = ZoneInfo("America/New_York")
        close_hour, close_min = 16, 0    # NYSE/Nasdaq ปิด 16:00 น. เวลานิวยอร์ก (รองรับ DST)

    now_local = datetime.now(tz)
    bar_day = pd.Timestamp(bar_date).date()

    if bar_day < now_local.date():
        return True   # แท่งวันเก่ากว่าวันนี้ ปิดตลาดแน่นอน
    if bar_day > now_local.date():
        return False  # ผิดปกติ (วันที่ในอนาคต) กันไว้ก่อน ไม่นับ

    # แท่งของ "วันนี้" พอดี → นับว่าปิดแล้วก็ต่อเมื่อเลยเวลาปิดตลาดไปแล้ว
    market_close_today = now_local.replace(
        hour=close_hour, minute=close_min, second=0, microsecond=0
    )
    return now_local >= market_close_today

# ══════════════════════════════════════════════════════
#  SCAN FUNCTION — เงื่อนไข Momentum นำตลาด
# ══════════════════════════════════════════════════════
def scan_symbol(symbol, ema_f, ema_m, ema_s, max_ext, rs_n):
    try:
        df = yf.download(symbol, period="2y", interval="1d",
                         progress=False, auto_adjust=False, actions=False)
        min_len = ema_s + rs_n + 10
        if df is None or len(df) < min_len:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # ── FIX (จาก tonrob v3.1): ตัดแท่งที่ราคาปิดเป็น nan ทิ้ง ──
        df = df.dropna(subset=["Close"])

        # ══ [5] ตัดแท่งวันนี้ทิ้งถ้ายังไม่ปิดตลาด (30 ก.ค. 2026) ══════════
        # กันปัญหา "กดสแกนตอนตลาดเปิด 2 ครั้งได้ค่าไม่ตรงกัน" — รายละเอียด
        # เหตุผลเต็มๆ อยู่ที่หัวไฟล์ (บันทึกสาเหตุ: ทำไมต้องตัดแท่งที่ยังไม่ปิดตลาดทิ้ง)
        # ═════════════════════════════════════════════════════════════════
        if len(df) > 0 and not is_bar_closed(df.index[-1], symbol):
            df = df.iloc[:-1]

        if len(df) < min_len:
            return None

        # ══ [1] เก็บวันที่ของแท่งสุดท้าย ═════════════════════════
        # เก็บ "วันที่ของแท่งสุดท้าย" ไว้ตรงนี้ เพราะบรรทัดล่างๆ มี
        # reset_index(drop=True) ที่จะโยน index วันที่ทิ้งไปเลย
        # ถ้าไม่เก็บไว้ก่อน จะไม่มีทางรู้ว่าตัวเลขที่โชว์เป็นของวันไหน
        # (นี่คือสาเหตุที่ปัญหา "ผลไม่ตรงกับ Vercel" มองไม่เห็นมาตลอด)
        # ═════════════════════════════════════════════════════════
        as_of = pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d")

        df["EMA_F"] = df["Close"].ewm(span=ema_f, adjust=False).mean()
        df["EMA_M"] = df["Close"].ewm(span=ema_m, adjust=False).mean()
        df["EMA_S"] = df["Close"].ewm(span=ema_s, adjust=False).mean()
        # หมายเหตุ: reset_index(drop=True) ทิ้งวันที่ — แต่โค้ดข้างล่างใช้
        # .iloc[] ซึ่งอ้างตำแหน่งอยู่แล้ว จึงคงบรรทัดนี้ไว้ตามเดิม (diff น้อยสุด)
        df = df.dropna(subset=["EMA_S"]).reset_index(drop=True)

        if len(df) < rs_n + 1:
            return None

        close_now = float(df["Close"].iloc[-1])
        ema_f_now = float(df["EMA_F"].iloc[-1])
        ema_m_now = float(df["EMA_M"].iloc[-1])
        ema_s_now = float(df["EMA_S"].iloc[-1])

        # ── เงื่อนไขที่ 2: Price > EMA เร็ว ──
        if not (close_now > ema_f_now):
            return None

        # ── เงื่อนไขที่ 3: EMA เร็ว > EMA กลาง ──
        if not (ema_f_now > ema_m_now):
            return None

        # ── เงื่อนไขที่ 4: EMA กลาง > EMA ช้า ──
        if not (ema_m_now > ema_s_now):
            return None

        # ── เงื่อนไขที่ 5: ราคายืดจาก EMA เร็วไม่เกิน X% ──
        extension_pct = (close_now - ema_f_now) / ema_f_now * 100
        if extension_pct > max_ext:
            return None

        # ── เงื่อนไขที่ 6: Relative Strength N แท่ง ──
        close_n_ago = float(df["Close"].iloc[-(rs_n + 1)])
        rs_pct = (close_now - close_n_ago) / close_n_ago * 100

        return {
            "Symbol"          : symbol,
            # ══ [2] ส่งวันที่ของข้อมูลออกไปกับทุกแถว ══
            "AsOfDate"        : as_of,
            "Close"           : round(close_now, 2),
            "EMA เร็ว"        : round(ema_f_now, 2),
            "Extension (%)"   : round(extension_pct, 1),
            "RS (%)"          : round(rs_pct, 1),
            "EMA กลาง"        : round(ema_m_now, 2),
            "EMA ช้า"         : round(ema_s_now, 2),
            "TradingView"     : f"https://www.tradingview.com/chart/?symbol={to_tv_format(symbol)}",
        }

    except Exception:
        return None

# ══ [3] ล้างผลเก่าเมื่อกดปุ่ม Scan ════════════════════════════
# กดปุ่ม Scan = ล้างผลเก่าใน session_state ทิ้งทันที
# เหตุผล: session_state ไม่ถูกล้างด้วย Clear cache หรือ Rerun
# ถ้าเปิดแท็บค้างข้ามวัน ผลเก่าจะยังโชว์อยู่และดาวน์โหลดออกไปได้
# ═════════════════════════════════════════════════════════════
if scan_btn:
    st.session_state.scan_done = False
    st.session_state.scan_results = []
    st.session_state.scan_run_at = None

# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════
if not symbols and not scan_btn:
    st.info("👈 เริ่มต้นด้วยการเลือกรายชื่อหุ้นที่ Sidebar ครับ")

elif scan_btn and symbols:
    st.divider()
    progress_bar = st.progress(0, text="กำลังเริ่ม scan...")
    status_text = st.empty()
    results = []

    for i, symbol in enumerate(symbols):
        pct = (i + 1) / len(symbols)
        progress_bar.progress(pct, text=f"กำลัง scan {symbol} [{i+1}/{len(symbols)}]")
        status_text.text(f"⏳ {symbol}...")
        result = scan_symbol(
            symbol, ema_fast, ema_mid, ema_slow,
            max_extension_pct, rs_bars
        )
        if result:
            results.append(result)

    progress_bar.progress(1.0, text="✅ Scan เสร็จแล้ว!")
    status_text.empty()

    st.session_state.scan_results = results
    st.session_state.scan_done = True
    # บันทึกเวลาที่ยิงข้อมูลจริง (UTC) ไว้ใช้แสดง/ตรวจสอบภายหลัง
    st.session_state.scan_run_at = datetime.now(timezone.utc).isoformat()

elif scan_btn and not symbols:
    st.error("กรุณาเลือกรายชื่อหุ้นก่อนครับ")

# ── แสดงผล ───────────────────────────────────────────
if st.session_state.scan_done and st.session_state.scan_results:
    results = st.session_state.scan_results
    st.divider()
    df_all = pd.DataFrame(results)

    # ══ [4] แสตมป์วันที่ของข้อมูล ══════════════════════════════
    # แสดงเป็น "รายการวันที่ทั้งหมด" โดยเจตนา — ถ้าขึ้นมาเกิน 1 วัน
    # แปลว่าหุ้นแต่ละตัวได้ข้อมูลไม่พร้อมกัน ซึ่งเป็นปัญหาอีกแบบที่ต้องรู้
    # ═════════════════════════════════════════════════════════
    _dates = sorted(df_all["AsOfDate"].dropna().unique().tolist())
    _as_of_tag = _dates[-1].replace("-", "") if _dates else "unknown"

    if st.session_state.scan_run_at:
        _run_utc = datetime.fromisoformat(st.session_state.scan_run_at)
        _run_th = _run_utc + timedelta(hours=7)
        _run_txt = _run_th.strftime("%Y-%m-%d %H:%M") + " (เวลาไทย)"
    else:
        _run_txt = "ไม่ทราบ"

    _mixed_html = (
        f'<span class="stamp-warn">⚠️ ข้อมูลคาบ {len(_dates)} วัน — หุ้นได้ข้อมูลไม่พร้อมกัน</span>'
        if len(_dates) > 1 else ""
    )

    st.markdown(
        '<div class="data-stamp">'
        '<span class="stamp-key">ข้อมูล ณ แท่งปิด</span>'
        f'<span class="stamp-val">{", ".join(_dates) if _dates else "—"}</span>'
        '<span class="stamp-sep"></span>'
        '<span class="stamp-key">สแกนเมื่อ</span>'
        f'<span class="stamp-dim">{_run_txt}</span>'
        '<span class="stamp-sep"></span>'
        '<span class="stamp-dim">แหล่งข้อมูล: Yahoo Finance (yfinance)</span>'
        f'{_mixed_html}'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── เงื่อนไขที่ 7: เรียงตาม RS มากไปน้อย เอา Top N ──
    df_result = df_all.sort_values("RS (%)", ascending=False).head(int(top_n))

    avg_rs = df_all["RS (%)"].mean()
    avg_ext = df_all["Extension (%)"].mean()
    leader = df_result.iloc[0]
    leader_sym = leader["Symbol"].replace(".BK", "")

    # ── สรุปผลแบบแถบเดียว (แทน st.metric ที่กินที่) ──
    # (เขียนติดกันไม่เว้นวรรคหน้าบรรทัด กัน Markdown มองเป็น code block)
    st.markdown(
        '<div class="summary-strip">'
        '<div class="sum-item">'
        '<div class="sum-label">ผ่านเงื่อนไขครบ</div>'
        f'<div class="sum-value">{len(results)}<span class="sum-unit">ตัว</span></div>'
        '</div>'
        '<div class="sum-div"></div>'
        '<div class="sum-item">'
        '<div class="sum-label">ผู้นำตลาด</div>'
        f'<div class="sum-value sum-gold">🚩 {leader_sym}</div>'
        '</div>'
        '<div class="sum-div"></div>'
        '<div class="sum-item">'
        '<div class="sum-label">RS เฉลี่ย</div>'
        f'<div class="sum-value">{avg_rs:+.1f}<span class="sum-unit">%</span></div>'
        '</div>'
        '<div class="sum-div"></div>'
        '<div class="sum-item">'
        '<div class="sum-label">Extension เฉลี่ย</div>'
        f'<div class="sum-value">{avg_ext:+.1f}<span class="sum-unit">%</span></div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="board-head">'
        f'<span>Top {len(df_result)} · เรียงตาม RS</span>'
        f'<span class="board-hint">ความยาวแถบ = พลังโมเมนตัมเทียบกับผู้นำ</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Leaderboard: หนึ่งแถวต่อหนึ่งหุ้น + แถบวัดพลัง RS ──
    max_rs = float(df_result["RS (%)"].max())
    if max_rs <= 0:
        max_rs = 1.0

    rows_html = []
    for rank, (_, row) in enumerate(df_result.iterrows(), start=1):
        sym = row["Symbol"]
        sym_display = sym.replace(".BK", "") if sym.endswith(".BK") else sym
        rs = float(row["RS (%)"])
        ext = float(row["Extension (%)"])

        bar_pct = max(2.0, min(100.0, rs / max_rs * 100))

        # ยิ่งใกล้เพดาน extension ยิ่งเตือน (ไล่ราคามาเยอะแล้ว)
        ext_ratio = ext / float(max_extension_pct) if max_extension_pct else 0
        if ext_ratio >= 0.75:
            ext_class = "ext-hot"      # ใกล้เพดาน = ไล่แพงแล้ว
        elif ext_ratio >= 0.4:
            ext_class = "ext-mid"
        else:
            ext_class = "ext-cool"     # ยังใกล้ EMA = เข้าได้สบาย

        lead_class = " is-leader" if rank == 1 else ""
        rank_mark = "🚩" if rank == 1 else f"{rank}"

        # หมายเหตุ: ห้ามเว้นวรรคหน้าบรรทัดใน HTML ที่ส่งเข้า st.markdown()
        # เพราะ Markdown จะมองว่าบรรทัดที่ย่อหน้า 4 ช่องขึ้นไป = code block
        # แล้วโชว์เป็นตัวหนังสือแทนที่จะ render เป็น HTML
        rows_html.append(
            f'<a class="row{lead_class}" href="{row["TradingView"]}" target="_blank" rel="noopener">'
            f'<div class="r-rank">{rank_mark}</div>'
            f'<div class="r-sym">{sym_display}</div>'
            f'<div class="r-price">{row["Close"]}'
            f'<span class="ext-chip {ext_class}">{ext:+.1f}% จาก EMA</span>'
            f'</div>'
            f'<div class="r-bar-wrap"><div class="r-bar" style="width:{bar_pct:.1f}%"></div></div>'
            f'<div class="r-rs">{rs:+.1f}%</div>'
            f'<div class="r-go">↗</div>'
            f'</a>'
        )

    st.markdown(
        '<div class="board">' + "".join(rows_html) + "</div>",
        unsafe_allow_html=True,
    )

    # ── Download buttons ──────────────────────────────
    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        csv = df_result.drop(columns=["TradingView"]).to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            # ชื่อไฟล์ใช้ "วันที่ของข้อมูล" ไม่ใช่วันที่กดปุ่ม
            label="💾 ดาวน์โหลด CSV",
            data=csv,
            file_name=f"momentum_{_as_of_tag}_streamlit.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_dl2:
        tv_list = "\n".join([to_tv_format(row["Symbol"]) for _, row in df_result.iterrows()])
        st.download_button(
            label="📺 ดาวน์โหลด TradingView Watchlist",
            data=tv_list,
            file_name=f"momentum_watchlist_{_as_of_tag}.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.caption("💡 นำไฟล์ .txt ไป Import ใน TradingView → Watchlist → Import symbols")
    st.caption(
        "⚠️ เครื่องมือนี้เป็นการคัดกรองหุ้นตามเงื่อนไขทางเทคนิคเท่านั้น "
        "ไม่ใช่คำแนะนำการลงทุน โปรดศึกษาข้อมูลและตัดสินใจด้วยตนเอง"
    )

elif st.session_state.scan_done and not st.session_state.scan_results:
    st.warning("ไม่พบหุ้นที่ผ่านเงื่อนไข ลองปรับ parameters ใน Sidebar ครับ")
