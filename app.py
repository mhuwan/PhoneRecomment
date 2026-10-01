from __future__ import annotations

import base64
import hashlib
import io
from html import escape
from urllib.parse import quote

import pandas as pd
import streamlit as st
from PIL import Image

import neo4j_service as db

st.set_page_config(page_title="PhoneGraph", page_icon="📱", layout="wide", initial_sidebar_state="expanded")

# =============================================================== THEME (CSS)
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1200px;}
      .hero {
        padding: 1.6rem 1.8rem; border-radius: 24px; margin-bottom: 1.2rem;
        background: radial-gradient(circle at 85% 20%, rgba(236,72,153,.55), transparent 45%),
                    linear-gradient(120deg, #1e1b4b 0%, #4c1d95 55%, #7c3aed 100%);
        border: 1px solid rgba(255,255,255,.12);
      }
      .hero h1 {margin: 0; font-size: 2.1rem; color: #fff;}
      .hero p {margin: .4rem 0 0 0; color: rgba(255,255,255,.82);}
      .card {
        border-radius: 20px; overflow: hidden; margin-bottom: .6rem;
        background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.02));
        border: 1px solid rgba(255,255,255,.10);
        transition: transform .18s ease, border-color .18s ease;
      }
      .card:hover {transform: translateY(-4px); border-color: rgba(139,92,246,.7);}
      .pimg {height: 210px; display:flex; align-items:center; justify-content:center;
             background: radial-gradient(circle at 50% 30%, rgba(139,92,246,.25), rgba(0,0,0,0) 70%);}
      .pimg img {max-height: 100%; max-width: 100%; object-fit: contain;}
      .cbody {padding: .85rem 1rem 1rem 1rem;}
      .cbody h4 {margin: .35rem 0 .1rem 0; font-size: 1.05rem;}
      .muted {opacity: .7; font-size: .85rem;}
      .reason {font-size: .84rem; margin: .5rem 0 0 0; opacity: .92; line-height: 1.45;}
      .pill {display:inline-block; padding:.15rem .6rem; border-radius:999px; font-size:.75rem;
             font-weight:700; background: linear-gradient(90deg,#8b5cf6,#ec4899); color:#fff;}
      .pill.alt {background: rgba(255,255,255,.12);}
      div[data-testid="stMetric"] {
        background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08);
        padding: .9rem 1rem; border-radius: 16px;
      }
      .stButton > button, .stFormSubmitButton > button {border-radius: 12px; font-weight: 600;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ======================================================== IMAGE / CARD HELPERS
BRAND_COLORS = {
    "Apple": ("#9ca3af", "#374151"), "Samsung": ("#3b82f6", "#1e3a8a"),
    "Xiaomi": ("#fb923c", "#9a3412"), "Google": ("#34d399", "#065f46"),
    "OPPO": ("#4ade80", "#166534"), "Vivo": ("#60a5fa", "#1d4ed8"),
    "Huawei": ("#f87171", "#991b1b"), "OnePlus": ("#f43f5e", "#881337"),
}


def _colors(brand: str) -> tuple[str, str]:
    if brand in BRAND_COLORS:
        return BRAND_COLORS[brand]
    h = int(hashlib.md5((brand or "?").encode()).hexdigest(), 16) % 360
    return f"hsl({h},70%,60%)", f"hsl({h},60%,25%)"


def phone_svg(name: str, brand: str) -> str:
    """ภาพสมาร์ทโฟนที่สร้างอัตโนมัติ (ใช้เมื่อยังไม่ได้ใส่รูปจริง)"""
    c1, c2 = _colors(brand or "")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 260">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
        '<rect x="50" y="10" width="100" height="240" rx="18" fill="#0f172a" stroke="#475569" stroke-width="3"/>'
        '<rect x="57" y="22" width="86" height="216" rx="11" fill="url(#g)"/>'
        '<rect x="82" y="28" width="36" height="7" rx="3.5" fill="#0f172a"/>'
        '<circle cx="76" cy="52" r="7" fill="#0f172a" opacity=".55"/>'
        '<circle cx="76" cy="70" r="7" fill="#0f172a" opacity=".55"/>'
        f'<text x="100" y="170" text-anchor="middle" font-family="Arial" font-size="11" fill="#fff" font-weight="700">{escape(brand or "")}</text>'
        f'<text x="100" y="187" text-anchor="middle" font-family="Arial" font-size="9" fill="#fff" opacity=".9">{escape(name[:16])}</text>'
        "</svg>"
    )
    return "data:image/svg+xml;utf8," + quote(svg)


def img_src(p: dict) -> str:
    return p.get("image") or phone_svg(p["name"], p.get("brand") or "")


def phone_card(p: dict, badge: str = "", reason: str = "") -> str:
    price = f" · ฿{int(p['price']):,}" if p.get("price") else ""
    return (
        '<div class="card">'
        f'<div class="pimg"><img src="{escape(img_src(p), quote=True)}" alt="{escape(p["name"])}"></div>'
        '<div class="cbody">'
        + (f'<span class="pill">{badge}</span>' if badge else "")
        + f'<h4>{escape(p["name"])}</h4>'
        f'<div class="muted">{escape(p.get("brand") or "ไม่ระบุยี่ห้อ")}{price}</div>'
        + (f'<p class="reason">{reason}</p>' if reason else "")
        + "</div></div>"
    )


def process_upload(file) -> str:
    """ย่อรูปที่อัปโหลดแล้วแปลงเป็น data URI เก็บใน Neo4j (ไม่ต้องใช้ที่เก็บไฟล์ภายนอก)"""
    img = Image.open(file).convert("RGB")
    img.thumbnail((480, 480))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def show_grid(cards: list[str], cols: int = 3, buttons=None) -> None:
    """วางการ์ดเป็นตาราง; buttons(i) คือฟังก์ชันวาดปุ่มใต้การ์ดแต่ละใบ"""
    for start in range(0, len(cards), cols):
        columns = st.columns(cols)
        for offset, html in enumerate(cards[start:start + cols]):
            with columns[offset]:
                st.markdown(html, unsafe_allow_html=True)
                if buttons:
                    buttons(start + offset)


# ============================================================ DATA HELPERS
def require_connection() -> None:
    try:
        if not db.ping():
            raise RuntimeError("Neo4j ไม่ตอบสนอง")
    except Exception as exc:
        st.error("ยังเชื่อมต่อ Neo4j Aura ไม่สำเร็จ")
        st.code(
            '[neo4j]\nuri = "neo4j+s://YOUR_INSTANCE.databases.neo4j.io"\n'
            'username = "YOUR_USERNAME"\npassword = "YOUR_PASSWORD"',
            language="toml",
        )
        st.caption("ใส่ค่าด้านบนใน Streamlit Secrets (ห้าม commit password ลง GitHub)")
        st.exception(exc)
        st.stop()


def user_selector(key: str, label: str = "เลือกผู้ใช้") -> str:
    users = db.list_users()
    if not users:
        st.info("ยังไม่มีผู้ใช้ ไปที่หน้า 👥 ผู้ใช้ เพื่อเพิ่ม หรือหน้า ⚙️ Setup เพื่อโหลดข้อมูลตัวอย่าง")
        st.stop()
    return st.selectbox(label, [u["name"] for u in users], key=key)


def phone_names() -> list[str]:
    return [p["name"] for p in db.list_phones()]


def brand_names() -> list[str]:
    return [b["name"] for b in db.list_brands()]


def explain(r: dict) -> str:
    parts = []
    if r.get("cf_score"):
        who = ", ".join(escape(x) for x in r["similar_users"])
        parts.append(f"👥 คนที่ชอบเหมือนคุณ ({who}) ชอบรุ่นนี้ · {r['cf_score']} เส้นทาง")
    if r.get("brand_score"):
        parts.append(f"🏷️ ยี่ห้อเดียวกับที่คุณชอบ · {r['brand_score']} เส้นทาง")
    return "<br>".join(parts)


def render_recommendations(user: str, limit: int, key: str) -> None:
    rows = db.recommend_phones(user, limit)
    if rows:
        st.caption("คะแนน = (คนชอบเหมือนกัน × 2) + (ยี่ห้อเดียวกัน × 1)")
        cards = [phone_card(r, f"#{i} · คะแนน {r['score']}", explain(r)) for i, r in enumerate(rows, 1)]
    else:
        st.info("ยังไม่มีข้อมูลความชอบมากพอ จึงแสดง **รุ่นยอดนิยม** แทน (เลือกมือถือที่ชอบเพิ่มเพื่อให้แนะนำแม่นขึ้น)")
        rows = db.popular_phones(user, limit)
        cards = [phone_card(r, "ยอดนิยม", f"❤️ มีคนชอบ {r['likes']} คน") for r in rows]
    if not rows:
        st.warning("ไม่มีมือถือให้แนะนำ")
        return

    def like_button(i: int) -> None:
        if st.button("❤️ ชอบรุ่นนี้", key=f"{key}_like_{i}"):
            db.like_phone(user, rows[i]["name"])
            st.rerun()

    show_grid(cards, 3, like_button)


# ================================================================== SIDEBAR
require_connection()

with st.sidebar:
    st.markdown("## 📱 PhoneGraph")
    st.caption("Smartphone Recommendation · Neo4j Aura + Streamlit")
    page = st.radio(
        "เมนู",
        ["🏠 Dashboard", "✨ แนะนำมือถือ", "👥 ผู้ใช้", "📱 มือถือ", "🏷️ ยี่ห้อ", "🕸️ Graph Explorer", "⚙️ Setup"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Graph Database Project")

st.markdown(
    '<div class="hero"><h1>📱 PhoneGraph Recommendation</h1>'
    "<p>ระบบแนะนำสมาร์ทโฟนด้วย Graph Database — บอกได้ว่าแนะนำเพราะอะไร</p></div>",
    unsafe_allow_html=True,
)

# ================================================================ DASHBOARD
if page == "🏠 Dashboard":
    m = db.get_metrics()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 ผู้ใช้", m["users"])
    c2.metric("📱 มือถือ", m["phones"])
    c3.metric("🏷️ ยี่ห้อ", m["brands"])
    c4.metric("❤️ ความชอบ (LIKES)", m["likes"])

    st.subheader("🔥 มือถือยอดนิยม")
    phones = sorted(db.list_phones(), key=lambda p: -p["likes"])[:6]
    if phones:
        show_grid([phone_card(p, f"❤️ {p['likes']}") for p in phones])
    else:
        st.info("ยังไม่มีข้อมูล ไปที่หน้า ⚙️ Setup เพื่อโหลดข้อมูลตัวอย่าง")

# ======================================================== RECOMMENDATIONS
elif page == "✨ แนะนำมือถือ":
    st.subheader("✨ มือถือที่แนะนำสำหรับคุณ")
    c1, c2 = st.columns([2, 1])
    with c1:
        user = user_selector("rec_user")
    with c2:
        top_n = st.slider("จำนวน", 3, 12, 6)
    liked = db.get_likes(user)
    st.markdown("**ที่ชอบอยู่แล้ว:** " + (", ".join(liked) if liked else "_ยังไม่มี_"))
    render_recommendations(user, top_n, "rec")

# ==================================================================== USERS
elif page == "👥 ผู้ใช้":
    st.subheader("👥 จัดการผู้ใช้")
    tab_add, tab_edit, tab_like = st.tabs(["➕ เพิ่มผู้ใช้ (แล้วรับคำแนะนำ)", "✏️ แก้ไข / ลบ", "❤️ แก้ความชอบ"])

    with tab_add:
        st.caption("พิมพ์ชื่อ เลือกมือถือที่ชอบ แล้วระบบจะแนะนำรุ่นอื่นให้ทันที")
        name = st.text_input("ชื่อของคุณ", key="new_user_name", placeholder="เช่น Mint")
        picks = st.multiselect("มือถือที่คุณชอบ", phone_names(), key="new_user_picks")
        if picks:
            allp = {p["name"]: p for p in db.list_phones()}
            show_grid([phone_card(allp[n]) for n in picks if n in allp], 4)
        if st.button("บันทึกและดูคำแนะนำ", type="primary", key="add_user_btn"):
            if not name.strip():
                st.error("กรุณาใส่ชื่อ")
            else:
                try:
                    db.add_user(name.strip(), picks)
                    st.session_state["just_added"] = name.strip()
                except ValueError as e:
                    st.error(str(e))
        if st.session_state.get("just_added"):
            u = st.session_state["just_added"]
            if db.user_exists(u):
                st.success(f"เพิ่ม {u} แล้ว 🎉 นี่คือรุ่นที่แนะนำสำหรับ {u}")
                render_recommendations(u, 6, "newrec")

    with tab_edit:
        user = user_selector("edit_user", "เลือกผู้ใช้ที่จะแก้ไข")
        new_name = st.text_input("ชื่อใหม่", value=user, key=f"rename_{user}")
        if st.button("💾 บันทึกชื่อ", key="rename_btn"):
            if not new_name.strip():
                st.error("ชื่อห้ามว่าง")
            else:
                try:
                    db.rename_user(user, new_name.strip())
                    st.success("แก้ไขแล้ว")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        st.divider()
        confirm = st.checkbox(f"ยืนยันลบ '{user}' (ความชอบของผู้ใช้นี้จะถูกลบด้วย)", key=f"confirm_del_{user}")
        if st.button("🗑️ ลบผู้ใช้", disabled=not confirm, key="del_user_btn"):
            db.delete_user(user)
            st.session_state.pop("just_added", None)
            st.success("ลบแล้ว")
            st.rerun()
        st.divider()
        st.dataframe(pd.DataFrame(db.list_users()).rename(columns={"name": "ชื่อ", "likes": "จำนวนที่ชอบ"}), hide_index=True)

    with tab_like:
        user = user_selector("like_user", "เลือกผู้ใช้")
        current = db.get_likes(user)
        chosen = st.multiselect("มือถือที่ชอบ", phone_names(), default=current, key=f"likes_{user}")
        if st.button("💾 บันทึกความชอบ", key="save_likes_btn"):
            db.set_likes(user, chosen)
            st.success("บันทึกแล้ว")
            st.rerun()

# =================================================================== PHONES
elif page == "📱 มือถือ":
    st.subheader("📱 จัดการมือถือ")
    tab_list, tab_add, tab_edit = st.tabs(["🖼️ แกลเลอรี", "➕ เพิ่มรุ่น", "✏️ แก้ไข / ลบ"])

    with tab_list:
        c1, c2 = st.columns([2, 1])
        kw = c1.text_input("ค้นหาชื่อรุ่น", placeholder="เช่น iPhone, Pixel")
        brand_f = c2.selectbox("ยี่ห้อ", [""] + brand_names(), format_func=lambda x: "ทุกยี่ห้อ" if x == "" else x)
        rows = db.list_phones(kw, brand_f)
        st.caption(f"พบ {len(rows)} รุ่น")
        show_grid([phone_card(p, f"❤️ {p['likes']}") for p in rows], 4)

    with tab_add:
        with st.form("add_phone_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_name = c1.text_input("ชื่อรุ่น *", placeholder="เช่น Pixel 10")
            p_price = c2.number_input("ราคา (บาท) 0 = ไม่ระบุ", min_value=0, step=500, value=0)
            c3, c4 = st.columns(2)
            existing = brand_names()
            p_brand = c3.selectbox("ยี่ห้อ", existing) if existing else None
            p_brand_new = c4.text_input("หรือพิมพ์ยี่ห้อใหม่", placeholder="เว้นว่างถ้าเลือกจากรายการ")
            p_url = st.text_input("ลิงก์รูปภาพ (URL)", placeholder="https://...jpg/png")
            p_file = st.file_uploader("หรืออัปโหลดรูป", type=["png", "jpg", "jpeg", "webp"])
            st.caption("ถ้าไม่ใส่รูป ระบบจะสร้างภาพสมาร์ทโฟนตามสียี่ห้อให้อัตโนมัติ")
            ok = st.form_submit_button("เพิ่มมือถือ", type="primary")
        if ok:
            brand = p_brand_new.strip() or p_brand
            if not p_name.strip() or not brand:
                st.error("กรุณาใส่ชื่อรุ่นและยี่ห้อ")
            else:
                try:
                    image = process_upload(p_file) if p_file else p_url.strip()
                    db.add_phone(p_name.strip(), brand, int(p_price) or None, image)
                    st.success(f"เพิ่ม {p_name.strip()} แล้ว")
                except ValueError as e:
                    st.error(str(e))

    with tab_edit:
        names = phone_names()
        if not names:
            st.info("ยังไม่มีมือถือ")
        else:
            sel = st.selectbox("เลือกรุ่น", names, key="edit_phone_sel")
            cur = next(p for p in db.list_phones() if p["name"] == sel)
            cur_img = cur.get("image") or ""
            is_data = cur_img.startswith("data:")
            st.markdown(phone_card(cur), unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            e_name = c1.text_input("ชื่อรุ่น", value=cur["name"], key=f"e_name_{sel}")
            e_price = c2.number_input("ราคา (บาท)", min_value=0, step=500, value=int(cur["price"] or 0), key=f"e_price_{sel}")
            brands = brand_names()
            idx = brands.index(cur["brand"]) if cur["brand"] in brands else 0
            c3, c4 = st.columns(2)
            e_brand = c3.selectbox("ยี่ห้อ", brands, index=idx, key=f"e_brand_{sel}")
            e_brand_new = c4.text_input("หรือยี่ห้อใหม่", key=f"e_brandnew_{sel}")
            e_url = st.text_input("ลิงก์รูปภาพ", value="" if is_data else cur_img, key=f"e_url_{sel}")
            e_file = st.file_uploader("อัปโหลดรูปใหม่", type=["png", "jpg", "jpeg", "webp"], key=f"e_file_{sel}")
            e_clear = st.checkbox("ลบรูป (ใช้ภาพอัตโนมัติ)", key=f"e_clear_{sel}")
            if is_data:
                st.caption("รุ่นนี้ใช้รูปที่อัปโหลดไว้ ถ้าไม่เลือกอะไรจะคงรูปเดิม")
            if st.button("💾 บันทึกการแก้ไข", type="primary", key="save_phone_btn"):
                brand = e_brand_new.strip() or e_brand
                if not e_name.strip() or not brand:
                    st.error("ชื่อรุ่นและยี่ห้อห้ามว่าง")
                else:
                    if e_file:
                        image = process_upload(e_file)
                    elif e_clear:
                        image = ""
                    elif e_url.strip():
                        image = e_url.strip()
                    else:
                        image = cur_img if is_data else ""
                    try:
                        db.update_phone(sel, e_name.strip(), brand, int(e_price) or None, image)
                        st.success("บันทึกแล้ว")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            st.divider()
            confirm = st.checkbox(f"ยืนยันลบ '{sel}'", key=f"confirm_phone_{sel}")
            if st.button("🗑️ ลบมือถือรุ่นนี้", disabled=not confirm, key="del_phone_btn"):
                db.delete_phone(sel)
                st.success("ลบแล้ว")
                st.rerun()

# =================================================================== BRANDS
elif page == "🏷️ ยี่ห้อ":
    st.subheader("🏷️ จัดการยี่ห้อ")
    brands = db.list_brands()
    if brands:
        st.dataframe(pd.DataFrame(brands).rename(columns={"name": "ยี่ห้อ", "phones": "จำนวนรุ่น"}), hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### ➕ เพิ่มยี่ห้อ")
        nb = st.text_input("ชื่อยี่ห้อ", key="new_brand")
        if st.button("เพิ่ม", type="primary", key="add_brand_btn"):
            if not nb.strip():
                st.error("กรุณาใส่ชื่อ")
            else:
                try:
                    db.add_brand(nb.strip())
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    with c2:
        st.markdown("##### ✏️ แก้ไข / 🗑️ ลบ")
        if brands:
            sel = st.selectbox("เลือกยี่ห้อ", [b["name"] for b in brands], key="brand_sel")
            nn = st.text_input("ชื่อใหม่", value=sel, key=f"brand_rename_{sel}")
            b1, b2 = st.columns(2)
            if b1.button("💾 บันทึกชื่อ", key="rename_brand_btn"):
                try:
                    db.rename_brand(sel, nn.strip())
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if b2.button("🗑️ ลบยี่ห้อ", key="del_brand_btn"):
                try:
                    db.delete_brand(sel)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

# ================================================================== GRAPH
elif page == "🕸️ Graph Explorer":
    st.subheader("🕸️ Graph Explorer")
    users = [""] + [u["name"] for u in db.list_users()]
    who = st.selectbox("มุมมอง", users, format_func=lambda x: "ทั้งระบบ" if x == "" else f"รอบ ๆ {x}")
    edges = db.graph_edges(who)
    if not edges:
        st.info("ยังไม่มีข้อมูลกราฟ")
    else:
        fill = {"PhoneUser": "#38bdf8", "Smartphone": "#fbbf24", "Brand": "#4ade80"}
        dot = ["digraph G {", 'rankdir="LR"; bgcolor="transparent";',
               'node [shape=box, style="rounded,filled", fontname="Helvetica", color="#ffffff55"];',
               'edge [color="#a78bfa", fontcolor="#cbd5e1", fontsize=10];']
        seen = set()
        for e in edges:
            for nm, lb in [(e["source"], e["source_label"]), (e["target"], e["target_label"])]:
                nid = f"{lb}:{nm}"
                if nid not in seen:
                    seen.add(nid)
                    safe = str(nm).replace('"', "'")
                    dot.append(f'"{nid}" [label="{safe}", fillcolor="{fill.get(lb, "#ddd")}", fontcolor="#0f172a"];')
            dot.append(f'"{e["source_label"]}:{e["source"]}" -> "{e["target_label"]}:{e["target"]}" [label="{e["rel"]}"];')
        dot.append("}")
        st.graphviz_chart("\n".join(dot))
        st.caption("🟦 ผู้ใช้  🟨 มือถือ  🟩 ยี่ห้อ")
        with st.expander("ดูข้อมูล edge"):
            st.dataframe(pd.DataFrame(edges), hide_index=True)

# =================================================================== SETUP
elif page == "⚙️ Setup":
    st.subheader("⚙️ Setup ข้อมูล")
    st.markdown(
        """
        **Graph schema**
        - `(:PhoneUser)-[:LIKES]->(:Smartphone)`
        - `(:Smartphone)-[:MADE_BY]->(:Brand)`
        """
    )
    st.warning("โหลดข้อมูลตัวอย่างใช้ MERGE จึงกดซ้ำได้ ไม่ลบข้อมูลเดิม")
    if st.button("สร้าง Constraint + ข้อมูลตัวอย่าง (5 คน / 8 รุ่น / 4 ยี่ห้อ)", type="primary"):
        with st.spinner("กำลังสร้างข้อมูล..."):
            db.seed_demo_data()
        st.success("เรียบร้อย")
        st.rerun()
    st.divider()
    st.markdown("##### 🧨 ล้างข้อมูลทั้งหมด")
    st.caption("ลบเฉพาะ PhoneUser, Smartphone, Brand")
    if st.checkbox("ฉันเข้าใจว่าข้อมูลจะหายทั้งหมด") and st.button("ล้างข้อมูล"):
        db.clear_all()
        st.session_state.pop("just_added", None)
        st.success("ล้างแล้ว")
        st.rerun()
