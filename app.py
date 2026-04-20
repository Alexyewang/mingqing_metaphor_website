# -*- coding: utf-8 -*-
import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from openai import OpenAI
import httpx
import json
import time
import re
import os
import datetime
from supabase import create_client, Client

# ================= 1. 页面配置与状态初始化 =================
st.set_page_config(page_title="明清小说隐喻计算平台", layout="wide", page_icon="📚")

# 初始化页面路由与搜索穿透状态
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'home_search' not in st.session_state:
    st.session_state.home_search = ""

# ================= 2. 纯净学术 UI 定制 (CSS) =================
# 动态注入 CSS：如果是在首页，彻底隐藏侧边栏控制按钮，保证极致留白
hide_sidebar_css = """
    <style>
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
    </style>
""" if st.session_state.page == 'home' else ""

st.markdown(hide_sidebar_css + """
<style>
    /* 全局背景：素雅纸张质感色调 */
    .stApp {
        background-color: #FAF9F6;
        background-image: radial-gradient(#E5E7EB 0.5px, transparent 0.5px);
        background-size: 24px 24px;
    }

    /* 隐藏默认页眉 */
    header {visibility: hidden;}
    .main .block-container {padding-top: 1rem;}

    /* 首页顶部微导航 */
    .top-nav { font-family: 'SimSun', serif; font-size: 18px; font-weight: bold; color: #4B5563; margin-top: 10px;}

    /* 首页大标题与副标题：复刻参考图的居中沉浸感 */
    .home-title {
        font-family: 'SimSun', 'STSong', serif;
        font-size: 4rem;
        color: #27272A;
        text-align: center;
        margin-top: 18vh;
        font-weight: 900;
        letter-spacing: 12px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.05);
    }
    .home-subtitle {
        text-align: center;
        color: #6B7280;
        font-size: 1.2rem;
        margin-bottom: 6vh;
        font-family: 'SimSun', serif;
        letter-spacing: 4px;
    }

    /* 首页搜索框容器美化，消除默认 input 的突兀感 */
    .hero-search div[data-baseweb="input"] {
        border-radius: 8px 0 0 8px !important;
        border: 1px solid #D1D5DB !important;
        border-right: none !important;
        background-color: white !important;
    }
    
    /* 系统内部卡片与组件样式 (保持原样) */
    .card {
        background-color: #FFFFFF; 
        padding: 24px; border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
        border: 1px solid #F3F4F6;
        border-left: 6px solid #1E3A8A;
    }
    .tag-metaphor { background-color: #DEF7EC; color: #03543F; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: bold; margin-right: 10px; }
    .tag-normal { background-color: #F3F4F6; color: #374151; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: bold; margin-right: 10px; }
    .attr-badge { background-color: #F5F3FF; color: #5B21B6; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; margin-right: 8px; margin-bottom: 8px; display: inline-block; border: 1px solid #DDD6FE; }
    .sentence { font-size: 20px; font-weight: 600; color: #111827; margin: 15px 0; font-family: 'SimSun', serif; }
    .analysis-box { background-color: #F9FAFB; padding: 15px; border-radius: 6px; font-size: 14px; color: #374151; border-left: 3px solid #D1D5DB; margin-top: 12px; }
    
    .agent-box { padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #E5E7EB; }
    .agent1 {background-color: #EFF6FF; border-left: 4px solid #3B82F6;}
    .agent2 {background-color: #FFF7ED; border-left: 4px solid #F97316;}
    .agent3 {background-color: #ECFDF5; border-left: 4px solid #10B981;}
    .agent4 {background-color: #F5F3FF; border-left: 4px solid #8B5CF6;}
</style>
""", unsafe_allow_html=True)

# ================= 3. 核心逻辑函数 (原封不动) =================
def get_and_update_visit_count():
    VISIT_FILE = "./dataset/visit_count.json"
    if 'has_visited' not in st.session_state:
        st.session_state.has_visited = True
        count = 0
        if os.path.exists(VISIT_FILE):
            try:
                with open(VISIT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    count = data.get("total_visits", 0)
            except: count = 0
        count += 1
        try:
            with open(VISIT_FILE, "w", encoding="utf-8") as f:
                json.dump({"total_visits": count}, f)
        except: pass
        return count
    else:
        if os.path.exists(VISIT_FILE):
            try:
                with open(VISIT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f).get("total_visits", 0)
            except: return 0
        return 0

def get_model_configs():
    try:
        return {
            "Deepseek-V3 (推荐)": {"base_url": "https://api.deepseek.com", "model_name": "deepseek-chat", "env_key": st.secrets["deepseek_api_key"]},
            "Qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model_name": "qwen-max", "env_key": st.secrets["qwen_api_key"]},
            "GPT-4o": {"base_url": "https://openrouter.ai/api/v1", "model_name": "openai/gpt-4o-mini", "env_key": st.secrets["openrouter_api_key"]}
        }
    except Exception as e: st.error(f"Secrets 加载失败: {e}"); st.stop()

MODEL_CONFIGS = get_model_configs()
CORPUS_CONFIG = {"红楼梦": "./dataset/hongloumeng.csv", "西游记": "./dataset/xiyouji.csv", "水浒传": "./dataset/shuihuzhuan.csv", "三国演义": "./dataset/sanguo.csv", "金瓶梅":"./dataset/jinpingmei.csv", "儒林外史": "./dataset/rulinwaishi.csv"}

@st.cache_resource
def init_supabase() -> Client:
    try: return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except: return None

def save_feedback(data_dict):
    supabase = init_supabase()
    if not supabase: return False
    data_dict.update({"date": datetime.datetime.now().strftime("%Y-%m-%d"), "time": datetime.datetime.now().strftime("%H:%M:%S")})
    try: supabase.table("feedback").insert(data_dict).execute(); return True
    except: return False

@st.cache_data
def load_all_corpora():
    all_samples = []
    def safe_get(val, default="未知"):
        if pd.isna(val): return default
        s = str(val).strip()
        return s if s and s.lower() != 'nan' else default
    multi_exp_dict = {}
    if os.path.exists("./dataset/multi_explanation.csv"):
        try:
            df_multi = pd.read_csv("./dataset/multi_explanation.csv")
            for _, row in df_multi.iterrows():
                m_sent = safe_get(row.get('Sentence'), "")
                m_exp = safe_get(row.get('Alternative_Analysis'), row.get('Explanation', ""))
                if m_sent and m_exp:
                    if m_sent not in multi_exp_dict: multi_exp_dict[m_sent] = []
                    multi_exp_dict[m_sent].append(m_exp)
        except: pass
    for book_name, file_path in CORPUS_CONFIG.items():
        if not os.path.exists(file_path): continue 
        try:
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                sent_text = safe_get(row.get('Sentence', ''), "")
                all_samples.append({
                    "Book": book_name, "Sentence": sent_text,
                    "Label": int(row.get('Pred_Label', row.get('Label', 0))), 
                    "Analysis": safe_get(row.get('Analysis', ''), "暂无解析"),
                    "Syntax_Type": safe_get(row.get('syntax_type'), '未知'), "Syntax_Analysis": safe_get(row.get('syntax_analysis'), '暂无解析'),
                    "Cognitive_Type": safe_get(row.get('cognitive_type'), '未知'), "Cognitive_Analysis": safe_get(row.get('cognitive_analysis'), '暂无解析'),
                    "Conventionality": safe_get(row.get('conventionality'), '未知'), "Conventionality_Analysis": safe_get(row.get('conventionality_analysis'), '暂无解析'),
                    "Form_Features": safe_get(row.get('form_features'), '未知'), "Form_Analysis": safe_get(row.get('form_analysis'), '暂无解析'),
                    "Other_Explanations": multi_exp_dict.get(sent_text, [])
                })
        except: pass
    return all_samples

def get_similar_metaphors(target_analysis, target_sentence, samples_pool, top_k=3):
    metaphor_pool = [s for s in samples_pool if s['Label'] == 1 and s['Sentence'] != target_sentence]
    if not metaphor_pool or not target_analysis: return []
    stop_chars = set("的了和是就在也不有与为以对于这那，。！？：；“”‘’（）《》、 \n\t比喻修辞本体喻体")
    target_set = set(target_analysis) - stop_chars
    scored_items = []
    for s in metaphor_pool:
        compare_set = set(s['Analysis']) - stop_chars
        if not compare_set: continue
        score = len(target_set & compare_set) / len(target_set | compare_set)
        scored_items.append((score, s))
    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_items[:top_k]]

# ================= 4. 路由逻辑 (入口页 vs 系统页) =================

# --- A. 纯净入口首页 (Splash Page) ---
if st.session_state.page == 'home':
    # 顶部模拟参考图的左上/右上布局
    nav_cols = st.columns([10, 1, 1])
    with nav_cols[0]: 
        st.markdown('<div class="top-nav">✍️ 明清古籍计算</div>', unsafe_allow_html=True)
    with nav_cols[1]: 
        st.button("关于", key="home_about")
    with nav_cols[2]: 
        st.button("登录", key="home_login")

    # 居中超大标题
    st.markdown('<div class="home-title">隐喻计算平台</div>', unsafe_allow_html=True)
    st.markdown('<div class="home-subtitle">数字文献核心基础设施 · 开放集成集成体系</div>', unsafe_allow_html=True)

    # 居中组合：搜索框 + 进入系统按钮
    # 利用 columns 控制宽度，使其居中且紧凑
    c1, c2, c3, c4 = st.columns([2, 4, 1, 2])
    with c2:
        st.markdown('<div class="hero-search">', unsafe_allow_html=True)
        search_kw = st.text_input("hero_search", placeholder="输入书名、作者或句子关键词...", label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        # 为了视觉上和输入框齐平，通过 CSS 去除按钮圆角并加高
        st.markdown("""
            <style>
                div.stButton > button:first-child {
                    height: 42px; border-radius: 0 8px 8px 0; margin-top: 0; border-left: none;
                }
            </style>
        """, unsafe_allow_html=True)
        if st.button("进入系统", type="primary", use_container_width=True):
            st.session_state.home_search = search_kw
            st.session_state.page = 'app'
            st.rerun()
    
    # 底部访问统计
    total_visits = get_and_update_visit_count()
    st.markdown(f'<div style="position:fixed; bottom:30px; width:100%; text-align:center; color:#9CA3AF; font-size:0.9rem;">👁️ 平台访问量: {total_visits} · © 2026 隐喻计算课题组</div>', unsafe_allow_html=True)

# --- B. 主系统内部 (App Workspace) ---
else:
    with st.sidebar:
        st.title("🏛️ 平台设置")
        if st.button("🏠 返回首页", use_container_width=True):
            st.session_state.page = 'home'
            st.session_state.home_search = "" # 退出时清空搜索态
            st.rerun()
        st.divider()
        selected_model = st.selectbox("选择大模型", list(MODEL_CONFIGS.keys()), index=0)
        use_proxy = st.checkbox("启用代理", value=False)
        st.divider()
        st.caption("© 多智能体隐喻计算")

    # 双 Tab 无缝切换，不再使用“按钮切换页面”的生硬方式
    tab1, tab2 = st.tabs(["🔍 语料检索", "🤖 在线识别"])
    
    # ----------------- Tab 1: 语料检索 -----------------
    with tab1:
        st.header("语料探索")
        samples = load_all_corpora()
        if not samples: st.warning("未找到语料文件")
        else:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: 
                # 如果首页输入了关键词，这里会自动填充
                search_query = st.text_input("🔍 搜索句子内容", value=st.session_state.home_search)
            with c2: filter_book = st.selectbox("📚 书籍筛选", ["全部"] + sorted(list(set(s["Book"] for s in samples))))
            with c3: filter_label = st.selectbox("🏷️ 基础类型", ["全部", "仅隐喻", "非隐喻"])
            
            f_syntax, f_cog, f_conv, f_form = "全部", "全部", "全部", "全部"
            if filter_label != "非隐喻":
                with st.expander("🔬 细粒度高级筛选"):
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    with sc1: f_syntax = st.selectbox("📌 句法", ["全部"] + sorted(list(set(s.get("Syntax_Type", "") for s in samples if s.get("Label")==1 and s.get("Syntax_Type") != "未知"))))
                    with sc2: f_cog = st.selectbox("🧠 认知", ["全部"] + sorted(list(set(s.get("Cognitive_Type", "") for s in samples if s.get("Label")==1 and s.get("Cognitive_Type") != "未知"))))
                    with sc3: f_conv = st.selectbox("⏳ 规约", ["全部"] + sorted(list(set(s.get("Conventionality", "") for s in samples if s.get("Label")==1 and s.get("Conventionality") != "未知"))))
                    with sc4: f_form = st.selectbox("🎭 特征", ["全部"] + sorted(list(set(s.get("Form_Features", "") for s in samples if s.get("Label")==1 and s.get("Form_Features") != "未知"))))

            filtered = [s for s in samples if (not search_query or search_query in s["Sentence"]) and (filter_book == "全部" or s["Book"] == filter_book) and (filter_label == "全部" or (filter_label == "仅隐喻" and s["Label"] == 1) or (filter_label == "非隐喻" and s["Label"] == 0))]
            if f_syntax != "全部": filtered = [s for s in filtered if s.get("Syntax_Type") == f_syntax]
            if f_cog != "全部": filtered = [s for s in filtered if s.get("Cognitive_Type") == f_cog]
            if f_conv != "全部": filtered = [s for s in filtered if s.get("Conventionality") == f_conv]
            if f_form != "全部": filtered = [s for s in filtered if s.get("Form_Features") == f_form]

            if f_syntax == "全部" and f_cog == "全部" and not search_query:
                filtered.sort(key=lambda x: 1 if x.get("Label") == 1 and x.get("Syntax_Type", "未知") != "未知" else 0, reverse=True)
            st.markdown(f"为您检索到 **{len(filtered)}** 条符合条件的语料。")
            st.divider()

            for s in filtered[:50]:
                tag_c, tag_t = ("tag-metaphor", "✨ 隐喻") if s["Label"] == 1 else ("tag-normal", "📝 非隐喻")
                b_html, d_html = "", ""
                if s["Label"] == 1:
                    b_html = f"""<div style="margin-top: 8px;">
<span class="attr-badge">📌 句法: {s['Syntax_Type']}</span>
<span class="attr-badge">🧠 认知: {s['Cognitive_Type']}</span>
<span class="attr-badge">⏳ 规约: {s['Conventionality']}</span>
<span class="attr-badge">🎭 特征: {s['Form_Features']}</span>
</div>"""
                    d_html = f"""<div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #CBD5E1;">
<b>🧬 Agent 4 细分类依据：</b><br/>
<ul style="margin-top: 5px; color: #4B5563; font-size: 13px;">
<li><b>句法：</b>{s['Syntax_Analysis']}</li>
<li><b>认知：</b>{s['Cognitive_Analysis']}</li>
<li><b>规约：</b>{s['Conventionality_Analysis']}</li>
<li><b>综合：</b>{s['Form_Analysis']}</li>
</ul>
</div>"""
                
                raw_a = s['Analysis']
                form_a = raw_a 
                if "【一审】" in raw_a and "【终审】" in raw_a:
                    try:
                        p1 = raw_a.split("【一审】:")[1].split("| 【二审】:")[0].strip()
                        p2 = raw_a.split("【二审】:")[1].split("| 【终审】:")[0].strip()
                        p3 = raw_a.split("【终审】:")[1].strip()
                        form_a = f"""<div style="margin-top: 5px;">
<div class="agent-box agent1"><b style="color: #1E3A8A;">🕵️‍♂️ Agent 1:</b> {p1}</div>
<div class="agent-box agent2"><b style="color: #9A3412;">⚖️ Agent 2:</b> {p2}</div>
<div class="agent-box agent3"><b style="color: #065F46;">👨‍⚖️ Agent 3:</b> {p3}</div>
</div>"""
                    except: pass 

                o_html = ""
                if s.get("Other_Explanations"):
                    its = "".join([f"<li style='margin-bottom: 6px;'>{exp}</li>" for exp in s["Other_Explanations"]])
                    o_html = f"""<div style="margin-top: 15px; background-color: #FEF3C7; padding: 12px; border-radius: 6px;">
<b style="color: #D97706; font-size: 14px;">💡 其他专家解析补充：</b>
<ul style="margin-top: 8px; color: #92400E; font-size: 13px; padding-left: 20px;">{its}</ul>
</div>"""
                
                st.markdown(f"""<div class="card">
<span class="{tag_c}">{tag_t}</span><span style="font-size: 12px; color: #64748B;"> 来源: 《{s['Book']}》</span>
{b_html}
<div class="sentence">{s['Sentence']}</div>
<details>
<summary style="cursor: pointer; color: #3B82F6; font-size: 14px;">展开多维解析</summary>
<div class="analysis-box">
<b style="font-size: 14px; color: #475569;">基础判决逻辑：</b>
{form_a}
{d_html}
{o_html}
</div>
</details>
</div>""", unsafe_allow_html=True)
                
                with st.expander("✍️ 提交更正意见"):
                    with st.form(key=f"f_{s['Sentence'][:10]}_{hash(s['Sentence'])}"):
                        nl = st.radio("正确标签：", [0, 1], index=s['Label'], horizontal=True)
                        na = st.text_area("意见：", value=raw_a, height=80) 
                        ns, nc, nv, nf = s.get('Syntax_Type', '未知'), s.get('Cognitive_Type', '未知'), s.get('Conventionality', '未知'), s.get('Form_Features', '未知')
                        if s['Label'] == 1:
                            cf1, cf2 = st.columns(2)
                            with cf1: ns, nc = st.text_input("句法", value=ns), st.text_input("认知", value=nc)
                            with cf2: nv, nf = st.text_input("规约", value=nv), st.text_input("特征", value=nf)
                        if st.form_submit_button("安全提交"):
                            if save_feedback({"book": s['Book'], "sentence": s['Sentence'], "original_label": int(s['Label']), "original_analysis": raw_a, "suggested_label": int(nl), "suggested_analysis": na, "syntax_type": ns, "cognitive_type": nc, "conventionality": nv, "form_features": nf}): st.success("✅ 提交成功")

    # ----------------- Tab 2: 在线识别 -----------------
    with tab2:
        st.header("多智能体在线识别")
        st.markdown("观察 **语义提取 ➔ 考证推理 ➔ 逻辑审核 ➔ 多维分类** 的全过程。")
        col_t, col_b = st.columns([3, 1])
        with col_t: ts = st.text_area("输入测试句子：", value="忽听山石之后有一人笑道：“且请留步”", height=100)
        with col_b: tb = st.text_input("目标书籍 (选填)：", placeholder="红楼梦")
        if st.button("🚀 启动多智能体分析", type="primary"):
            ctx = tb.strip() if tb.strip() else "明清小说"
            cfg = MODEL_CONFIGS[selected_model]
            clt = OpenAI(api_key=cfg["env_key"], base_url=cfg["base_url"], http_client=httpx.Client(proxy="http://127.0.0.1:7890") if use_proxy else None)
            st.divider()
            with st.status("🕵️‍♂️ Agent 1 (语义)...") as s1:
                p1 = f'这是《{ctx}》中的句子。判定含义并提取可疑词。严格JSON：{{"meaning": "...", "metaphor_words": ["..."]}} 内容: "{ts}"'
                r1 = clt.chat.completions.create(model=cfg["model_name"], messages=[{"role": "user", "content": p1}], temperature=0, response_format={'type': 'json_object'})
                d1 = json.loads(r1.choices[0].message.content); a1, w1 = d1.get("meaning", ""), d1.get("metaphor_words", [])
                st.markdown(f'<div class="agent-box agent1"><b>🕵️‍♂️ Agent 1:</b><br/>语义: {a1} <br/>词: {w1}</div>', unsafe_allow_html=True)
                s1.update(label="✅ Agent 1 完成", state="complete")
            with st.status("⚖️ Agent 2 (推理)...") as s2:
                p2 = f'参考含义分析判断是否包含比喻。严格JSON：{{"label": 1, "analysis": "理由"}} 内容: "{ts}" 含义: "{a1}" 词: {w1}'
                r2 = clt.chat.completions.create(model=cfg["model_name"], messages=[{"role": "user", "content": p2}], temperature=0, response_format={'type': 'json_object'})
                d2 = json.loads(r2.choices[0].message.content); l2, re2 = int(d2.get("label", 0)), d2.get("analysis", "")
                st.markdown(f'<div class="agent-box agent2"><b>⚖️ Agent 2:</b><br/>逻辑: {re2} <br/>标签: {l2}</div>', unsafe_allow_html=True)
                s2.update(label="✅ Agent 2 完成", state="complete")
            with st.status("👨‍⚖️ Agent 3 (裁判)...") as s3:
                p3 = f'检查报告是否矛盾。报告: "{re2}"。严格JSON：{{"label": 1或0, "analysis": "理由"}}'
                r3 = clt.chat.completions.create(model=cfg["model_name"], messages=[{"role": "user", "content": p3}], temperature=0, response_format={'type': 'json_object'})
                d3 = json.loads(r3.choices[0].message.content); fl, fr = int(d3.get("label", 0)), d3.get("analysis", "")
                st.markdown(f'<div class="agent-box agent3"><b>📌 Agent 3:</b><br/>终审: {fr} <br/><h3>最终: {"🏷️ 隐喻" if fl==1 else "📝 字面"}</h3></div>', unsafe_allow_html=True)
                s3.update(label="✅ Agent 3 完成", state="complete", expanded=True)
            if fl == 1:
                with st.status("🧬 Agent 4 (分类)...") as s4:
                    tasks = [{"t": "句法", "o": "名词性、动词性、形容词/副词性、介词性", "k": ["syntax_type", "syntax_analysis"]}, {"t": "认知", "o": "结构、方位、本体", "k": ["cognitive_type", "cognitive_analysis"]}, {"t": "规约", "o": "死喻、活喻", "k": ["conventionality", "conventionality_analysis"]}, {"t": "特征", "o": "显性/隐性、根/派生、相似性基础/创造相似性", "k": ["form_features", "form_analysis"]}]
                    cols = st.columns(2)
                    for idx, t in enumerate(tasks):
                        ap = f'分析《{ctx}》特征。内容: "{ts}" 依据: "{re2}"。选自：{t["o"]}。严格JSON。'
                        dj = json.loads(clt.chat.completions.create(model=cfg["model_name"], messages=[{"role": "user", "content": ap}], temperature=0, response_format={'type': 'json_object'}).choices[0].message.content)
                        with cols[idx%2]: st.markdown(f'<div class="agent-box agent4"><b>{t["t"]}</b><br/>归类: {dj.get(t["k"][0], "未知")}<br/>依据: {dj.get(t["k"][1], "")}</div>', unsafe_allow_html=True)
                    s4.update(label="✅ Agent 4 完成", state="complete")
            st.subheader("💡 关联推荐")
            sims = get_similar_metaphors(re2, ts, load_all_corpora())
            for sim in sims: st.markdown(f'<div class="card"><span class="tag-metaphor" style="float:right;">关联度高</span><div style="font-weight:bold;">《{sim["Book"]}》</div><div>{sim["Sentence"]}</div></div>', unsafe_allow_html=True)
