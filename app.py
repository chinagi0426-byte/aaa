import streamlit as st
from openai import OpenAI
import json
import os
import datetime
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import io
import base64

# ==========================================
# 1. システム設定 & スマホ用スタイル
# ==========================================
st.set_page_config(
    page_title="簿記学習 AIシステム", 
    layout="wide",
    initial_sidebar_state="collapsed" # スマホでは邪魔なのであえて閉じておく
)

# スマホで見やすくするためのCSS
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {
                padding-top: 1rem;
                padding-bottom: 5rem;
            }
            /* スマホでボタンを押しやすく */
            div.stButton > button {
                width: 100%;
                height: 3em;
                font-weight: bold;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==========================================
# 2. 簿記データベース
# ==========================================
TEXTBOOK_DB = {
    "日商簿記 3級": {
        "1. 仕訳の基礎": {"grammar": "借方・貸方", "vocab": ["現金", "当座預金"], "topic": "簿記の循環"},
        "2. 商品売買": {"grammar": "三分法", "vocab": ["仕入", "売上"], "topic": "商品取引"},
        "3. 現金預金": {"grammar": "小口現金", "vocab": ["現金過不足"], "topic": "資金管理"},
        "4. 決算整理": {"grammar": "見越・繰延", "vocab": ["前払費用"], "topic": "経過勘定"},
        "5. 精算表": {"grammar": "B/S・P/L", "vocab": ["当期純利益"], "topic": "決算"},
    },
    "日商簿記 2級 (商業)": {
        "1. 連結会計": {"grammar": "資本連結", "vocab": ["非支配株主持分"], "topic": "グループ決算"},
        "2. 外貨建": {"grammar": "換算替え", "vocab": ["為替差損益"], "topic": "海外取引"},
        "3. 有価証券": {"grammar": "時価評価", "vocab": ["その他有価証券"], "topic": "金融資産"},
        "4. 税効果": {"grammar": "一時差異", "vocab": ["繰延税金資産"], "topic": "税金"},
    },
    "日商簿記 2級 (工業)": {
        "1. 費目別": {"grammar": "材料・労務・経費", "vocab": ["差異分析"], "topic": "原価分類"},
        "2. 標準原価": {"grammar": "ボックス図", "vocab": ["能率差異"], "topic": "原価管理"},
        "3. 直接原価": {"grammar": "CVP分析", "vocab": ["貢献利益"], "topic": "利益管理"},
    },
    "日商簿記 1級": {
        "1. 資産除去債務": {"grammar": "割引現在価値", "vocab": ["利息費用"], "topic": "固定資産"},
        "2. 退職給付": {"grammar": "数理計算差異", "vocab": ["勤務費用"], "topic": "年金"},
        "3. 意思決定": {"grammar": "NPV法", "vocab": ["埋没原価"], "topic": "投資判断"},
    }
}

# ==========================================
# 3. フォント・DB関数
# ==========================================
DB_FILE = "student_db.json"
GRADES = ["3級受験", "2級受験", "1級受験", "合格者"]
FONT_FILE = "ipaexg.ttf"

def check_font():
    return os.path.exists(FONT_FILE)

def create_pdf(name, title, content):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    font_name = 'IPAexGothic' if check_font() and (lambda: pdfmetrics.registerFont(TTFont('IPAexGothic', FONT_FILE)) or True)() else 'Helvetica'
    c.setFont(font_name, 16)
    c.drawString(20*mm, 280*mm, title)
    c.setFont(font_name, 10)
    c.drawString(20*mm, 270*mm, f"Name: {name} | Date: {datetime.date.today()}")
    text_obj = c.beginText(20*mm, 250*mm)
    text_obj.setFont(font_name, 10)
    text_obj.setLeading(14)
    for line in content.split('\n'):
        while len(line) > 0:
            text_obj.textLine(line[:40])
            line = line[40:]
            if text_obj.getY() < 20*mm:
                c.drawText(text_obj); c.showPage(); text_obj = c.beginText(20*mm, 280*mm); text_obj.setFont(font_name, 10)
    c.drawText(text_obj)
    c.save()
    buffer.seek(0)
    return buffer

def encode_image(file): return base64.b64encode(file.getvalue()).decode('utf-8')
def load_db(): return json.load(open(DB_FILE, encoding='utf-8')) if os.path.exists(DB_FILE) else {}
def save_db(d): json.dump(d, open(DB_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=4)

# ==========================================
# 4. アプリ画面 (スマホ特化レイアウト)
# ==========================================
st.title("🧮 簿記学習 AIシステム")

# --- 1. APIキー確認 (メイン画面で完結) ---
api_key = None
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    # スマホで見やすいように、アコーディオンではなく直接表示
    if "user_api_key" not in st.session_state:
        st.session_state.user_api_key = ""
    
    if not st.session_state.user_api_key:
        st.warning("👇 まずはAPIキーを入力してください")
        key_input = st.text_input("OpenAI APIキー", type="password", placeholder="sk-...")
        if key_input:
            st.session_state.user_api_key = key_input
            st.rerun()
        st.stop() # キーがないとここで止める
    else:
        api_key = st.session_state.user_api_key

# --- 2. 生徒選択 (メイン画面で完結) ---
db = load_db()
student_names = list(db.keys())

# 生徒がまだいない場合
if not student_names:
    st.info("👋 生徒データを登録しましょう")
    with st.container(border=True):
        st.write("###### 新規登録")
        n_name = st.text_input("氏名")
        n_grade = st.selectbox("目標レベル", GRADES)
        if st.button("登録して開始", type="primary"):
            if n_name:
                db[n_name] = {"school": "", "grade": n_grade, "history": []}
                save_db(db)
                st.rerun()
    st.stop()

# 生徒がいる場合
col1, col2 = st.columns([3, 1])
with col1:
    selected_student = st.selectbox("学習する生徒を選択", ["-- 選択してください --"] + student_names)
with col2:
    # 新規登録はポップオーバー（吹き出し）に隠す
    with st.popover("➕"):
        st.write("新規登録")
        n_name = st.text_input("氏名", key="new")
        n_grade = st.selectbox("レベル", GRADES, key="gr")
        if st.button("登録"):
            if n_name and n_name not in db:
                db[n_name] = {"grade": n_grade, "history": []}
                save_db(db)
                st.rerun()

# 生徒が選ばれていないと止める
if selected_student == "-- 選択してください --":
    st.info("👆 上のボックスから生徒を選んでください")
    st.stop()

# ==========================================
# 5. メイン機能 (タブで切り替え)
# ==========================================
s_data = db[selected_student]
history = s_data.get("history", [])

st.divider()
st.write(f"### 👤 {selected_student} <small>({s_data.get('grade')})</small>", unsafe_allow_html=True)

# アイコン付きで見やすく
tab1, tab2, tab3, tab4 = st.tabs(["📸 写真", "📚 演習", "⚡ 自由", "🔄 復習"])

# --- 写真解析 ---
with tab1:
    st.caption("スマホで撮った問題をアップロード")
    img_file = st.file_uploader("画像を選択", type=["jpg","png","jpeg"], label_visibility="collapsed")
    level = st.radio("難易度", ["類題", "簡単", "応用"], horizontal=True)
    
    if img_file and st.button("この問題の類題を作成", type="primary"):
        client = OpenAI(api_key=api_key)
        b64 = encode_image(img_file)
        with st.spinner("AIが画像を分析中..."):
            try:
                res = client.chat.completions.create(model="gpt-4o-mini", messages=[
                    {"role":"user", "content":[{"type":"text", "text":f"簿記の類題作成。難易度:{level}。1行分析を---ANALYSIS---の後に記述。"},
                    {"type":"image_url", "image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}
                ])
                raw = res.choices[0].message.content
                analysis = raw.split("---ANALYSIS---")[1].strip() if "---ANALYSIS---" in raw else "画像問題"
                content = raw.split("---ANALYSIS---")[0].strip() if "---ANALYSIS---" in raw else raw
                
                st.markdown(content)
                st.session_state.pdf = {'t': "画像問題", 'c': content}
                db[selected_student]["history"].append({"date":str(datetime.date.today()), "unit": analysis})
                save_db(db)
            except Exception as e: st.error(str(e))

# --- 論点演習 (マルチセレクト) ---
with tab2:
    book = st.selectbox("分野", list(TEXTBOOK_DB.keys()))
    units = st.multiselect("論点 (複数選択可)", list(TEXTBOOK_DB[book].keys()))
    
    if units and st.button("演習プリント作成", type="primary"):
        client = OpenAI(api_key=api_key)
        prompt = f"受講生:{selected_student} 論点:{','.join(units)} の簿記総合問題を作成。"
        with st.spinner("作成中..."):
            res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user", "content":prompt}])
            content = res.choices[0].message.content
            st.markdown(content)
            st.session_state.pdf = {'t': f"{book} 総合", 'c': content}
            db[selected_student]["history"].append({"date":str(datetime.date.today()), "unit": ",".join(units)})
            save_db(db)

# --- 自由作成 ---
with tab3:
    col_a, col_b = st.columns(2)
    with col_a: sub = st.selectbox("級", ["3級","2級","1級"])
    with col_b: lev = st.selectbox("難度", ["基礎","標準","難問"])
    theme = st.text_input("論点名 (例: リース会計)")
    
    if st.button("カスタム作成", type="primary"):
        client = OpenAI(api_key=api_key)
        with st.spinner("作成中..."):
            res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user", "content":f"簿記問題作成 {sub} {theme} {lev}"}])
            content = res.choices[0].message.content
            st.markdown(content)
            st.session_state.pdf = {'t': f"{theme}", 'c': content}
            db[selected_student]["history"].append({"date":str(datetime.date.today()), "unit": theme})
            save_db(db)

# --- 復習 ---
with tab4:
    if not history:
        st.warning("履歴がありません")
    else:
        if st.button("🔄 弱点克服テスト", type="primary"):
            client = OpenAI(api_key=api_key)
            hist = ",".join([h['unit'] for h in history[-5:]])
            with st.spinner("履歴を分析中..."):
                res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user", "content":f"履歴:{hist} を元に苦手克服テスト作成"}])
                content = res.choices[0].message.content
                st.markdown(content)
                st.session_state.pdf = {'t': "弱点克服", 'c': content}

# --- PDFボタン (画面下部に固定気味に配置) ---
if 'pdf' in st.session_state:
    st.markdown("---")
    data = create_pdf(selected_student, st.session_state.pdf['t'], st.session_state.pdf['c'])
    st.download_button("📄 PDFをダウンロード", data, "boki.pdf", "application/pdf", type="secondary", use_container_width=True)

# --- サイドバー (管理用) ---
with st.sidebar:
    st.write("🔧 管理者メニュー")
    if st.button("生徒削除画面へ"):
        del_target = st.selectbox("削除する生徒", student_names)
        if st.button("本当に削除"):
            del db[del_target]
            save_db(db)
            st.rerun()

