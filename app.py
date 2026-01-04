
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
# 1. システム設定 & スタイル (スマホ対応強化)
# ==========================================
st.set_page_config(
    page_title="簿記学習 AIシステム", 
    layout="wide",
    initial_sidebar_state="expanded" # なるべくサイドバーを開いておく設定
)

# スマホで見やすくするためのCSS調整
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            /* スマホでの余白調整 */
            .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
            }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==========================================
# 2. 簿記データベース
# ==========================================
TEXTBOOK_DB = {
    "日商簿記 3級": {
        "1. 仕訳の基礎": {"grammar": "借方・貸方のルール", "vocab": ["現金", "当座預金", "資本金"], "topic": "簿記の循環"},
        "2. 商品売買": {"grammar": "三分法・分記法", "vocab": ["仕入", "売上", "繰越商品", "クレジット売掛金"], "topic": "商品の取引"},
        "3. 現金預金・手形": {"grammar": "小口現金・手形取引", "vocab": ["受取手形", "支払手形", "現金過不足"], "topic": "資金の管理"},
        "4. 固定資産(基礎)": {"grammar": "購入・売却・減価償却(定額法)", "vocab": ["建物", "備品", "車両運搬具", "減価償却費"], "topic": "固定資産の記帳"},
        "5. 債権債務(基礎)": {"grammar": "貸倒引当金・未収未払", "vocab": ["貸倒損失", "前払金", "前受金", "仮払金"], "topic": "経過勘定と引当金"},
        "6. 株式会社会計(基礎)": {"grammar": "株式発行・配当・税金", "vocab": ["繰越利益剰余金", "法人税等"], "topic": "純資産と税金"},
        "7. 精算表・決算": {"grammar": "B/SとP/L作成", "vocab": ["当期純利益", "損益"], "topic": "決算手続"},
    },
    "日商簿記 2級 (商業)": {
        "1. 現金預金・債権": {"grammar": "銀行勘定調整表・電子記録債権", "vocab": ["電子記録債権", "不渡手形", "営業外受取手形"], "topic": "債権の譲渡と評価"},
        "2. 有形固定資産": {"grammar": "定率法・生産高比例法・建設仮勘定", "vocab": ["減価償却累計額", "固定資産売却損益", "火災未決算"], "topic": "固定資産の取得と除却"},
        "3. 無形固定資産": {"grammar": "自社利用ソフト・償却", "vocab": ["ソフトウェア", "のれん", "特許権", "研究開発費"], "topic": "目に見えない資産"},
        "4. リース会計": {"grammar": "ファイナンス・リース", "vocab": ["リース資産", "リース債務", "利息相当額"], "topic": "賃貸借取引"},
        "5. 有価証券": {"grammar": "満期保有・その他・子会社", "vocab": ["その他有価証券評価差額金", "償却原価法"], "topic": "保有目的別の評価"},
        "6. 外貨建取引": {"grammar": "換算替え・為替予約", "vocab": ["為替差損益", "前受金(外貨)"], "topic": "海外取引"},
        "7. 連結会計": {"grammar": "資本連結・成果連結・アップストリーム", "vocab": ["非支配株主持分", "連結修正仕訳"], "topic": "グループ企業の決算"},
        "8. 税効果会計": {"grammar": "一時差異の調整", "vocab": ["繰延税金資産", "繰延税金負債", "法人税等調整額"], "topic": "会計と税務のズレ"},
    },
    "日商簿記 2級 (工業)": {
        "1. 費目別計算": {"grammar": "材料・労務・経費", "vocab": ["予定価格", "賃率差異", "間接費配賦"], "topic": "原価の分類と集計"},
        "2. 個別原価計算": {"grammar": "指図書別集計", "vocab": ["仕掛品", "製造間接費配賦差異"], "topic": "多品種少量生産"},
        "3. 総合原価計算": {"grammar": "月末仕掛品評価", "vocab": ["加工費", "先入先出法", "平均法", "工程別"], "topic": "大量生産"},
        "4. 標準原価計算": {"grammar": "差異分析（ボックス図）", "vocab": ["能率差異", "操業度差異", "予算差異"], "topic": "原価管理と分析"},
        "5. 直接原価計算": {"grammar": "CVP分析・損益分岐点", "vocab": ["変動費", "固定費", "貢献利益"], "topic": "利益管理"},
    },
    "日商簿記 1級 (商会)": {
        "1. 資産除去債務": {"grammar": "割引現在価値", "vocab": ["利息費用", "履行差額"], "topic": "固定資産の除去義務"},
        "2. デリバティブ": {"grammar": "ヘッジ会計（繰延・時価）", "vocab": ["繰延ヘッジ損益", "オプション料"], "topic": "金融商品会計"},
        "3. 退職給付会計": {"grammar": "数理計算上の差異", "vocab": ["勤務費用", "利息費用"], "topic": "年金資産と債務"},
        "4. 企業結合": {"grammar": "パーチェス法・持分プーリング", "vocab": ["のれん", "負ののれん発生益"], "topic": "M&Aの高度な会計"},
    },
    "日商簿記 1級 (工原)": {
        "1. 意思決定会計": {"grammar": "業務的・構造的意思決定", "vocab": ["埋没原価", "機会原価", "正味現在価値(NPV)"], "topic": "投資の判断"},
        "2. 予算管理": {"grammar": "予算実績差異分析", "vocab": ["セールス・ミックス", "市場占有率"], "topic": "経営計画と統制"},
        "3. 品質原価計算": {"grammar": "適合・不適合コスト", "vocab": ["予防原価", "評価原価", "失敗原価"], "topic": "品質コスト管理"},
    }
}

# ==========================================
# 3. フォント・PDF・DB関数
# ==========================================
DB_FILE = "student_db.json"
GRADES = ["簿記3級 受験生", "簿記2級 受験生", "簿記1級 受験生", "合格者"]
FONT_FILE = "ipaexg.ttf"

def check_font_status():
    if os.path.exists(FONT_FILE):
        try:
            pdfmetrics.registerFont(TTFont('IPAexGothic', FONT_FILE))
            return True
        except: return False
    return False

font_is_ready = check_font_status()

def create_pdf(student_name, title, content):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = 'IPAexGothic' if font_is_ready else 'Helvetica'
    c.setFont(font_name, 16)
    c.drawString(20 * mm, height - 20 * mm, f"{title}")
    c.setFont(font_name, 10)
    c.drawString(20 * mm, height - 30 * mm, f"生徒名: {student_name} 様  |  作成日: {datetime.date.today()}")
    c.line(20 * mm, height - 32 * mm, width - 20 * mm, height - 32 * mm)
    text_object = c.beginText(20 * mm, height - 45 * mm)
    text_object.setFont(font_name, 10)
    text_object.setLeading(14)
    max_width = 40 
    for paragraph in content.split('\n'):
        if paragraph.strip() == "":
            text_object.textLine("")
            continue
        while len(paragraph) > 0:
            line = paragraph[:max_width]
            text_object.textLine(line)
            paragraph = paragraph[max_width:]
            if text_object.getY() < 20 * mm:
                c.drawText(text_object)
                c.showPage()
                text_object = c.beginText(20 * mm, height - 20 * mm)
                text_object.setFont(font_name, 10)
                text_object.setLeading(14)
    c.drawText(text_object)
    c.save()
    buffer.seek(0)
    return buffer

def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 4. アプリ画面 (スマホ最適化UI)
# ==========================================
st.title("🧮 簿記学習 AIシステム Pro")

# --- APIキー管理 (メインとサイドバー両方に対応) ---
# Secretsにあればそれを使う
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
    # サイドバーにこっそり表示
    with st.sidebar:
        st.success("🔑 APIキー認証済み")
else:
    # Secretsになければ、メイン画面で入力を求める（スマホ対策）
    if "api_key_input" not in st.session_state:
        st.session_state.api_key_input = ""
        
    # サイドバーにもあるが、メイン画面にも出す
    with st.sidebar:
        st.header("⚙️ 設定")
        sidebar_api_input = st.text_input("OpenAI APIキー", type="password", key="sidebar_api")
    
    # メイン画面での入力
    if not sidebar_api_input:
        st.warning("⚠️ まずはAPIキーを入力してください")
        api_key = st.text_input("ここにOpenAI APIキーを入力", type="password", key="main_api")
    else:
        api_key = sidebar_api_input

# APIキーがないと先に進ませない
if not api_key:
    st.stop()

# --- データベース読み込み ---
db = load_db()

# --- 生徒選択 (メイン画面にも配置) ---
# サイドバーにもあるが、スマホでは見えないのでメインにも置く
student_names = list(db.keys())

if not student_names:
    st.info("👋 生徒がまだ登録されていません。まずは登録しましょう！")
    with st.expander("➕ 新規生徒登録", expanded=True):
        new_name = st.text_input("受講生 氏名")
        new_note = st.text_input("メモ（志望校など）")
        new_grade = st.selectbox("学習レベル", GRADES)
        if st.button("登録する"):
            if new_name and new_name not in db:
                db[new_name] = {"school": new_note, "grade": new_grade, "history": []}
                save_db(db)
                st.success("登録完了！画面が更新されます")
                st.rerun()
    st.stop() # 登録するまで下を表示しない

else:
    # 生徒がいる場合、メイン画面で選択させる
    col_sel1, col_sel2 = st.columns([3, 1])
    with col_sel1:
        selected_student = st.selectbox("学習する受講生を選択", ["-- 選択してください --"] + student_names)
    with col_sel2:
        # 新規登録ボタンを小さく配置
        with st.popover("➕ 追加"):
            new_name = st.text_input("氏名")
            new_note = st.text_input("メモ")
            new_grade = st.selectbox("レベル", GRADES)
            if st.button("登録"):
                if new_name and new_name not in db:
                    db[new_name] = {"school": new_note, "grade": new_grade, "history": []}
                    save_db(db)
                    st.rerun()

    # --- サイドバー (管理者用メニューとして残す) ---
    with st.sidebar:
        st.markdown("---")
        st.header("🔧 管理メニュー")
        del_student = st.selectbox("削除対象", ["--選択--"] + list(db.keys()))
        if st.button("削除実行"):
            if del_student in db:
                del db[del_student]
                save_db(db)
                st.success("削除しました")
                st.rerun()

# --- メイン機能 ---
if selected_student and selected_student != "-- 選択してください --":
    s_data = db[selected_student]
    history = s_data.get("history", [])
    
    st.divider()
    st.markdown(f"### 👤 {selected_student} <small>（{s_data.get('grade')}）</small>", unsafe_allow_html=True)

    # 4つのモード
    tab_vision, tab_text, tab_free, tab_review = st.tabs(["📸 写真解析", "📚 論点演習", "⚡ 自由作成", "🔄 復習"])

    # 1. 写真解析
    with tab_vision:
        st.info("スマホで撮影した問題画像をアップロードしてください")
        uploaded_file = st.file_uploader("画像をタップして選択", type=["jpg", "png", "jpeg"])
        target_score_v = st.radio("難易度", ["類題", "基礎", "応用"], horizontal=True)
        if uploaded_file and st.button("🖨️ 類題作成", use_container_width=True):
            client = OpenAI(api_key=api_key)
            base64_image = encode_image(uploaded_file)
            prompt = f"受講生:{selected_student} 画像の問題の類題を作成。分析結果を1行で---ANALYSIS---の後に記述。"
            with st.spinner("画像を分析中..."):
                try:
                    res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": [{"type": "text", "text": prompt},{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}])
                    full_text = res.choices[0].message.content
                    if "---CONTENT---" in full_text:
                        parts = full_text.split("---CONTENT---")
                        analysis = parts[0].replace("---ANALYSIS---", "").strip()
                        content = parts[1].strip()
                    else:
                        analysis = "画像解析"
                        content = full_text.replace("---ANALYSIS---", "").strip()
                    st.markdown(content)
                    st.session_state['pdf_content'] = content
                    st.session_state['pdf_title'] = "画像解析問題"
                    db[selected_student]["history"].append({"date": str(datetime.date.today()), "subject": "画像", "unit": analysis})
                    save_db(db)
                except Exception as e: st.error(f"エラー: {e}")

    # 2. 論点別 (複数選択対応！)
    with tab_text:
        book_name = st.selectbox("級・分野", list(TEXTBOOK_DB.keys()))
        unit_options = list(TEXTBOOK_DB[book_name].keys())
        # ★ここをマルチセレクト（複数選択）に変更★
        selected_units = st.multiselect("論点を選択（複数可）", unit_options)
        
        if selected_units:
            # 選択された全論点の情報をまとめる
            topics = []
            grammars = []
            vocabs = []
            for u in selected_units:
                d = TEXTBOOK_DB[book_name][u]
                topics.append(d['topic'])
                grammars.append(d['grammar'])
                vocabs.extend(d['vocab'])
            
            st.caption(f"選択中: {', '.join(selected_units)}")
            
            if st.button("🖨️ 演習プリント作成", use_container_width=True):
                client = OpenAI(api_key=api_key)
                prompt = f"""
                受講生:{selected_student} ({s_data.get('grade')})
                以下の複数の論点を含む総合問題を作成してください。
                論点: {', '.join(selected_units)}
                テーマ: {', '.join(topics)}
                会計処理: {', '.join(grammars)}
                勘定科目: {', '.join(list(set(vocabs)))}
                【構成】1.ポイント解説 2.総合演習問題(仕訳・計算) 3.解答解説
                """
                with st.spinner("複合問題を作成中..."):
                    res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
                    content = res.choices[0].message.content
                    st.markdown(content)
                    st.session_state['pdf_content'] = content
                    st.session_state['pdf_title'] = f"総合演習 ({book_name})"
                    db[selected_student]["history"].append({"date": str(datetime.date.today()), "subject": book_name, "unit": ",".join(selected_units)})
                    save_db(db)

    # 3. 自由作成
    with tab_free:
        subject = st.selectbox("対象", ["簿記3級", "簿記2級", "簿記1級"])
        target_score_f = st.selectbox("難易度", ["基礎", "標準", "難問"])
        unit_free = st.text_input("論点名")
        req_free = st.text_area("要望")
        if st.button("🖨️ カスタム作成", use_container_width=True):
            client = OpenAI(api_key=api_key)
            prompt = f"受講生:{selected_student} 対象:{subject} 論点:{unit_free} 難易度:{target_score_f} 要望:{req_free} プリント作成"
            with st.spinner("作成中..."):
                res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
                content = res.choices[0].message.content
                st.markdown(content)
                st.session_state['pdf_content'] = content
                st.session_state['pdf_title'] = f"{subject} - {unit_free}"
                db[selected_student]["history"].append({"date": str(datetime.date.today()), "subject": subject, "unit": unit_free})
                save_db(db)

    # 4. 復習
    with tab_review:
        if st.button("🔄 総合仕訳テスト", use_container_width=True):
            client = OpenAI(api_key=api_key)
            hist_str = ", ".join([h['unit'] for h in history[-5:]])
            prompt = f"受講生:{selected_student} 履歴:{hist_str} ランダム仕訳テスト作成"
            with st.spinner("作成中..."):
                res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
                content = res.choices[0].message.content
                st.markdown(content)
                st.session_state['pdf_content'] = content
                st.session_state['pdf_title'] = "総合仕訳テスト"
        
        st.write("") # スペース
        if st.button("📔 間違いノート", use_container_width=True):
            client = OpenAI(api_key=api_key)
            all_history_str = ", ".join([f"{h['unit']}" for h in history])
            prompt = f"受講生:{selected_student} 全履歴:{all_history_str} 苦手まとめノート作成"
            with st.spinner("作成中..."):
                res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
                content = res.choices[0].message.content
                st.markdown(content)
                st.session_state['pdf_content'] = content
                st.session_state['pdf_title'] = "間違いノート"

    # PDFボタン
    if 'pdf_content' in st.session_state:
        st.markdown("---")
        pdf_file = create_pdf(selected_student, st.session_state['pdf_title'], st.session_state['pdf_content'])
        st.download_button("📄 PDFダウンロード", data=pdf_file, file_name=f"{selected_student}_boki.pdf", mime="application/pdf", type="primary", use_container_width=True)

else:
    # 生徒未選択時の案内
    st.info("👆 上のボックスから受講生を選んでください")
