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
# 1. システム設定 & プロ仕様スタイル
# ==========================================
st.set_page_config(page_title="簿記学習 AIシステム", layout="wide")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==========================================
# 2. 簿記データベース (大幅追加版)
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
    "日商簿記 2級 (商業・資産/負債)": {
        "1. 現金預金・債権": {"grammar": "銀行勘定調整表・電子記録債権", "vocab": ["電子記録債権", "不渡手形", "営業外受取手形"], "topic": "債権の譲渡と評価"},
        "2. 有形固定資産": {"grammar": "定率法・生産高比例法・建設仮勘定", "vocab": ["減価償却累計額", "固定資産売却損益", "火災未決算"], "topic": "固定資産の取得と除却"},
        "3. 無形固定資産・研究開発費": {"grammar": "自社利用ソフト・償却", "vocab": ["ソフトウェア", "のれん", "特許権", "研究開発費"], "topic": "目に見えない資産"},
        "4. リース会計": {"grammar": "ファイナンス・リース", "vocab": ["リース資産", "リース債務", "利息相当額"], "topic": "賃貸借取引のオンバランス"},
        "5. 有価証券": {"grammar": "満期保有・その他有価証券", "vocab": ["その他有価証券評価差額金", "償却原価法"], "topic": "保有目的別の評価"},
        "6. 引当金": {"grammar": "修繕引当金・退職給付引当金", "vocab": ["製品保証引当金", "賞与引当金"], "topic": "将来の費用の見積もり"},
    },
    "日商簿記 2級 (商業・純資産/その他)": {
        "1. 株式会社会計(応用)": {"grammar": "増資・減資・自己株式・合併", "vocab": ["資本準備金", "その他資本剰余金", "自己株式処分差益"], "topic": "資本取引とM&A"},
        "2. 税効果会計": {"grammar": "一時差異の調整", "vocab": ["繰延税金資産", "繰延税金負債", "法人税等調整額"], "topic": "会計と税務のズレ"},
        "3. 外貨建取引": {"grammar": "換算替え・為替予約（振当処理）", "vocab": ["為替差損益", "前受金(外貨)"], "topic": "海外取引"},
        "4. サービス業の会計": {"grammar": "役務収益・原価", "vocab": ["仕掛品(サービス)", "役務原価", "役務収益"], "topic": "サービス業の記帳"},
        "5. 本支店会計": {"grammar": "本支店合併財務諸表", "vocab": ["支店勘定", "本店勘定", "内部利益"], "topic": "支店がある場合の決算"},
        "6. 連結会計": {"grammar": "資本連結・成果連結・アップストリーム", "vocab": ["非支配株主持分", "連結修正仕訳"], "topic": "グループ企業の決算"},
    },
    "日商簿記 2級 (工業簿記)": {
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
        "4. 企業結合・事業分離": {"grammar": "パーチェス法・持分プーリング", "vocab": ["のれん", "負ののれん発生益"], "topic": "M&Aの高度な会計"},
    },
    "日商簿記 1級 (工原)": {
        "1. 意思決定会計": {"grammar": "業務的・構造的意思決定", "vocab": ["埋没原価", "機会原価", "正味現在価値(NPV)"], "topic": "投資の判断"},
        "2. 予算管理": {"grammar": "予算実績差異分析", "vocab": ["セールス・ミックス", "市場占有率"], "topic": "経営計画と統制"},
        "3. 品質原価計算": {"grammar": "適合・不適合コスト", "vocab": ["予防原価", "評価原価", "失敗原価"], "topic": "品質コスト管理"},
    }
}

# ==========================================
# 3. フォント設定 (ipaexg.ttf を使用)
# ==========================================
DB_FILE = "student_db.json"
GRADES = ["簿記3級 受験生", "簿記2級 受験生", "簿記1級 受験生", "合格者"]
FONT_FILE = "ipaexg.ttf"

def check_font_status():
    """フォント診断"""
    st.sidebar.markdown("### 🛠️ システム診断")
    if os.path.exists(FONT_FILE):
        file_size = os.path.getsize(FONT_FILE)
        st.sidebar.success(f"✅ フォントOK ({file_size/1024:.0f}KB)")
        try:
            pdfmetrics.registerFont(TTFont('IPAexGothic', FONT_FILE))
            return True
        except:
            st.sidebar.error("❌ 登録エラー")
            return False
    else:
        st.sidebar.error("❌ フォントなし")
        return False

font_is_ready = check_font_status()

# PDF作成エンジン
def create_pdf(student_name, title, content):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = 'IPAexGothic' if font_is_ready else 'Helvetica'
    
    # ヘッダー
    c.setFont(font_name, 16)
    c.drawString(20 * mm, height - 20 * mm, f"{title}")
    c.setFont(font_name, 10)
    c.drawString(20 * mm, height - 30 * mm, f"生徒名: {student_name} 様  |  作成日: {datetime.date.today()}")
    c.line(20 * mm, height - 32 * mm, width - 20 * mm, height - 32 * mm)
    
    # 本文
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

# 画像エンコード
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

# DB読み書き
def load_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 4. アプリ画面 (UI)
# ==========================================
st.title("🧮 簿記学習 AIシステム Pro")

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定・管理")
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
        st.success("🔑 APIキー認証済み")
    else:
        api_key = st.text_input("OpenAI APIキー", type="password")
    
    st.markdown("---")
    db = load_db()
    
    tab_reg, tab_admin = st.tabs(["➕ 登録", "🔧 管理"])
    with tab_reg:
        new_name = st.text_input("受講生 氏名")
        new_note = st.text_input("メモ")
        new_grade = st.selectbox("学習レベル", GRADES)
        if st.button("登録"):
            if new_name and new_name not in db:
                db[new_name] = {"school": new_note, "grade": new_grade, "history": []}
                save_db(db)
                st.success("登録完了")
                st.rerun()
    with tab_admin:
        del_student = st.selectbox("削除対象", ["--選択--"] + list(db.keys()))
        if st.button("削除実行"):
            if del_student in db:
                del db[del_student]
                save_db(db)
                st.success("削除しました")
                st.rerun()

    st.markdown("---")
    student_list = list(db.keys())
    selected_student = st.selectbox("受講生を選択", ["-- 選択してください --"] + student_list)

# メインエリア
if selected_student and selected_student != "-- 選択してください --":
    s_data = db[selected_student]
    history = s_data.get("history", [])
    st.markdown(f"## 👤 {selected_student} <small>（{s_data.get('grade')}）</small>", unsafe_allow_html=True)

    tab_vision, tab_text, tab_free, tab_review = st.tabs(["📸 写真解析", "📚 論点別演習", "⚡ 自由作成", "🔄 復習"])

    # 1. 写真解析
    with tab_vision:
        st.write("##### 過去問やテキストの写真をアップロード")
        uploaded_file = st.file_uploader("問題の画像をドラッグ＆ドロップ", type=["jpg", "png", "jpeg"])
        target_score_v = st.radio("難易度調整", ["類題（同じレベル）", "基礎に戻る", "応用にする"], horizontal=True)
        if uploaded_file and st.button("🖨️ 類題プリント作成"):
            if not api_key: st.error("APIキーが必要です")
            else:
                client = OpenAI(api_key=api_key)
                base64_image = encode_image(uploaded_file)
                prompt = f"""
                受講生:{selected_student} ({s_data.get('grade')}) 
                アップロードされた簿記の問題画像を分析し、同じ論点の「類題」を作成してください。
                分析結果（論点）を1行で ---ANALYSIS--- の後に記述。
                """
                with st.spinner("画像を分析＆保存中..."):
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
                        db[selected_student]["history"].append({"date": str(datetime.date.today()), "subject": "画像解析", "unit": analysis})
                        save_db(db)
                    except Exception as e: st.error(f"エラー: {e}")

    # 2. 論点別
    with tab_text:
        col_a, col_b = st.columns(2)
        with col_a: book_name = st.selectbox("級・分野", list(TEXTBOOK_DB.keys()))
        unit_options = list(TEXTBOOK_DB[book_name].keys())
        with col_b: unit_name = st.selectbox("論点（単元）", unit_options)
        unit_data = TEXTBOOK_DB[book_name][unit_name]
        st.info(f"会計処理: {unit_data['grammar']} | キーワード: {', '.join(unit_data['vocab'])}")
        if st.button("🖨️ 演習プリント作成"):
            if not api_key: st.error("APIキーが必要です")
            else:
                client = OpenAI(api_key=api_key)
                prompt = f"""
                受講生:{selected_student} ({s_data.get('grade')})
                テーマ:{unit_data['topic']} 会計処理:{unit_data['grammar']} 勘定科目:{', '.join(unit_data['vocab'])}
                上記の論点について、試験対策プリントを作成してください。
                【構成】1.ポイント解説 2.演習問題(5問) 3.応用 4.解答
                """
                with st.spinner("AIが作成中..."):
                    res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
                    content = res.choices[0].message.content
                    st.markdown(content)
                    st.session_state['pdf_content'] = content
                    st.session_state['pdf_title'] = f"{book_name} - {unit_name}"
                    db[selected_student]["history"].append({"date": str(datetime.date.today()), "subject": book_name, "unit": unit_name})
                    save_db(db)

    # 3. 自由作成
    with tab_free:
        st.write("##### ピンポイントで問題を作成")
        col_f1, col_f2 = st.columns(2)
        with col_f1: subject = st.selectbox("対象", ["簿記3級", "簿記2級 商業", "簿記2級 工業", "簿記1級 商会", "簿記1級 工原"])
        with col_f2: target_score_f = st.selectbox("難易度", ["基礎", "標準", "難問"])
        unit_free = st.text_input("論点名", placeholder="例：特殊商品売買")
        req_free = st.text_area("要望", placeholder="例：割賦販売の未実現利益の処理について")
        if st.button("🖨️ カスタム作成"):
            if not api_key: st.error("APIキーが必要です")
            else:
                client = OpenAI(api_key=api_key)
                prompt = f"受講生:{selected_student} 対象:{subject} 論点:{unit_free} 難易度:{target_score_f} 要望:{req_free} 簿記プリント作成"
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
        st.write("##### 🧠 学習履歴から復習プリントを作成")
        if len(history) == 0:
            st.warning("履歴がありません")
        else:
            recent_items = history[-3:] 
            for item in recent_items: st.caption(f"- {item['date']}: {item['subject']} / {item['unit']}")
            st.markdown("---")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if st.button("🔄 総合仕訳テスト"):
                    if not api_key: st.error("APIキーが必要です")
                    else:
                        client = OpenAI(api_key=api_key)
                        hist_str = ", ".join([h['unit'] for h in recent_items])
                        prompt = f"受講生:{selected_student} 履歴:{hist_str} ランダム仕訳テスト作成"
                        with st.spinner("作成中..."):
                            res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
                            content = res.choices[0].message.content
                            st.markdown(content)
                            st.session_state['pdf_content'] = content
                            st.session_state['pdf_title'] = "総合仕訳テスト"
            with col_r2:
                if st.button("📔 間違いノート"):
                    if not api_key: st.error("APIキーが必要です")
                    else:
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
        st.download_button("📄 PDFダウンロード", data=pdf_file, file_name=f"{selected_student}_boki.pdf", mime="application/pdf")

else:
    st.info("👈 左のサイドバーから受講生を選択してください")


