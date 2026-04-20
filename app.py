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

# ================= 1. 页面配置与全局 CSS =================
st.set_page_config(page_title="明清典籍隐喻计算平台", layout="wide", page_icon="📚")

# 初始化页面路由状态
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# CSS 深度穿透，构建极简大气学术风
st.markdown("""
<style>
    /* 全局背景与纸张质感 */
    .stApp {
        background-color: #FAF9F6;
        background-image: radial-gradient(#E5E7EB 0.5px, transparent 0.5px);
        background-size: 24px 24px;
    }
    
    /* 隐藏顶部原生装饰条，优化顶部内边距 */
    header[data-testid="stHeader"] { display: none !important; }
    .main .block-container {padding-top: 0rem; padding-bottom: 6rem;}

    /* ================= 字体与排版大幅放大，告别拘谨 ================= */
    .stMarkdown p, .stRadio label, .stSelectbox label, .stCheckbox label, .stTextInput label {
        font-size: 18px !important;
        color: #374151;
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        font-size: 18px !important;
        padding: 12px !important;
    }
    .stButton>button {
        font-size: 20px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        border-radius: 8px !important;
    }

    /* ================= 定制吸顶选项卡 (非首页) ================= */
    div[data-testid="stVerticalBlock"]:has(#custom-top-bar) {
        position: -webkit-sticky;
        position: sticky;
        top: 0px;
        z-index: 99999;
        background-color: #FAF9F6; 
        padding: 15px 0;
        border-bottom: 2px solid #E5E7EB;
        margin-bottom: 30px;
    }
    /* 隐藏选项卡容器中按钮的边框，使其像文本链接 */
    div[data-testid="stVerticalBlock"]:has(#custom-top-bar) button {
        background: transparent !important;
        border: none !important;
        color: #6B7280 !important;
        box-shadow: none !important;
    }
    div[data-testid="stVerticalBlock"]:has(#custom-top-bar) button:hover {
        color: #1E3A8A !important;
    }

    /* ================= 首页大标题绝对居中 ================= */
    .hero-title {
        width: 100%;
        text-align: center !important;
        font-family: 'SimSun', 'STSong', serif;
        font-size: 5rem;
        color: #1F2937;
        margin-top: 15vh;
        font-weight: bold;
        letter-spacing: 15px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.05);
    }

    /* ================= 首页圆环浮动菜单 ================= */
    div[data-testid="stVerticalBlock"]:has(#ring-menu-anchor) {
        position: relative;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(10px);
        border-radius: 50%;
        width: 400px;
        height: 400px;
        margin: 5vh auto;
        padding: 60px 40px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        border: 1px solid rgba(255,255,255,0.5);
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 20px;
    }
    /* 圆环中间的镂空效果 */
    div[data-testid="stVerticalBlock"]:has(#ring-menu-anchor)::after {
        content: '';
        position: absolute;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 140px; height: 140px;
        background: #FAF9F6; 
        border-radius: 50%;
        box-shadow: inset 0 4px 10px rgba(0,0,0,0.05);
        pointer-events: none; 
        z-index: 10;
    }
    div[data-testid="stVerticalBlock"]:has(#ring-menu-anchor) button {
        height: 90px;
        border-radius: 15px !important;
        background: white !important;
        color: #4B5563 !important;
        border: 1px solid #E5E7EB !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        z-index: 20; 
    }
    div[data-testid="stVerticalBlock"]:has(#ring-menu-anchor) button:hover {
        background: #EFF6FF !important;
        color: #1E3A8A !important;
        border-color: #BFDBFE !important;
    }

    /* ================= 句子卡片优化 (缩短 1/5 宽度并居中) ================= */
    .card {
        background-color: #FFFFFF; padding: 26px; border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 24px;
        border: 1px solid #E5E7EB; border-left: 6px solid #1E3A8A;
        width: 80%; /* 核心缩短要求 */
        margin-left: auto;
        margin-right: auto;
    }
    
    .tag-metaphor { background-color: #DEF7EC; color: #03543F; padding: 6px 14px; border-radius: 999px; font-size: 14px; font-weight: bold; }
    .tag-normal { background-color: #F3F4F6; color: #374151; padding: 6px 14px; border-radius: 999px; font-size: 14px; font-weight: bold; }
    .attr-badge { background-color: #F5F3FF; color: #5B21B6; padding: 6px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; margin-right: 8px; display: inline-block; border: 1px solid #DDD6FE; }
    .sentence { font-size: 22px; font-weight: 600; color: #111827; margin: 20px 0; font-family: 'SimSun', serif; line-height: 1.6; }
    .analysis-box { background-color: #F9FAFB; padding: 18px; border-radius: 8px; font-size: 16px; color: #374151; border-left: 3px solid #D1D5DB; margin-top: 15px; line-height: 1.6; }
    .agent-box { padding: 18px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #E5E7EB; font-size: 16px; line-height: 1.6; }
    .agent1 {background-color: #EFF6FF; border-left: 4px solid #3B82F6;}
    .agent2 {background-color: #FFF7ED; border-left: 4px solid #F97316;}
    .agent3 {background-color: #ECFDF5; border-left: 4px solid #10B981;}
    .agent4 {background-color: #F5F3FF; border-left: 4px solid #8B5CF6;}
    
    /* ================= 左下角浮动访问量统计 ================= */
    .floating-stats {
        position: fixed;
        bottom: 25px;
        left: 25px;
        background-color: rgba(255, 255, 255, 0.95);
        padding: 15px 25px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        border: 1px solid #E5E7EB;
        z-index: 1000;
        backdrop-filter: blur(4px);
    }
</style>
""", unsafe_allow_html=True)

# 动态隐藏侧边栏按钮（如果是在主页或语料库页，不需要显示任何侧边栏）
if st.session_state.page in ['home', 'corpus']:
    st.markdown("""
        <style>
            [data-testid="collapsedControl"] { display: none !important; }
            section[data-testid="stSidebar"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

# ================= 2. 核心业务逻辑 (绝对 0 改动) =================

VISIT_COUNTER_FILE = "./dataset/visit_count.json"

def get_and_update_visit_count():
    if 'has_visited' not in st.session_state:
        st.session_state.has_visited = True
        count = 0
        if os.path.exists(VISIT_COUNTER_FILE):
            try:
                with open(VISIT_COUNTER_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    count = data.get("total_visits", 0)
            except Exception:
                count = 0
        count += 1
        try:
            with open(VISIT_COUNTER_FILE, "w", encoding="utf-8") as f:
                json.dump({"total_visits": count}, f)
        except Exception:
            pass 
        return count
    else:
        if os.path.exists(VISIT_COUNTER_FILE):
            try:
                with open(VISIT_COUNTER_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("total_visits", 0)
            except Exception:
                return 0
        return 0

def get_model_configs():
    try:
        return {
            "Deepseek-V3.2(推荐)": {
                "base_url": "https://api.deepseek.com",
                "model_name": "deepseek-chat",
                "env_key": st.secrets["deepseek_api_key"]
            },
            "Qwen": {
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model_name": "qwen-max",
                "env_key": st.secrets["qwen_api_key"]
            },
            "GPT-4o": {
                "base_url": "https://openrouter.ai/api/v1",
                "model_name": "openai/gpt-4o-mini",
                "env_key": st.secrets["openrouter_api_key"]
            }
        }
    except Exception as e:
        st.error(f"⚠️ 无法加载 API 密钥。请检查 Streamlit Secrets 配置: {e}")
        st.stop()

MODEL_CONFIGS = get_model_configs()

CORPUS_CONFIG = {
    "红楼梦": "./dataset/hongloumeng.csv",         
    "西游记": "./dataset/xiyouji.csv",      
    "水浒传": "./dataset/shuihuzhuan.csv",  
    "三国演义": "./dataset/sanguo.csv",      
    "金瓶梅":"./dataset/jinpingmei.csv",
    "儒林外史": "./dataset/rulinwaishi.csv",
}

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

# ================= 3. 路由与自定义顶栏布局 =================

def render_top_bar():
    """渲染全局吸顶的选项卡导航"""
    with st.container():
        st.markdown('<div id="custom-top-bar"></div>', unsafe_allow_html=True)
        # 用列布局模拟绝对居中和宽距的选项卡
        _, c1, c2, c3, c4, _ = st.columns([1, 2, 2, 3, 3, 1])
        with c1: 
            if st.button("🏠 首页", use_container_width=True): st.session_state.page = 'home'; st.rerun()
        with c2: 
            if st.button("ℹ️ 关于", use_container_width=True): st.session_state.page = 'about'; st.rerun()
        with c3: 
            if st.button("🔍 明清典籍隐喻语料库", use_container_width=True): st.session_state.page = 'corpus'; st.rerun()
        with c4: 
            if st.button("🤖 在线隐喻识别", use_container_width=True): st.session_state.page = 'online'; st.rerun()
            
    # 高亮当前激活的选项卡 CSS 逻辑
    active_idx = {'home': 2, 'about': 3, 'corpus': 4, 'online': 5}.get(st.session_state.page, 2)
    st.markdown(f"""
    <style>
        div[data-testid="stVerticalBlock"]:has(#custom-top-bar) div[data-testid="column"]:nth-child({active_idx}) button {{
            color: #1E3A8A !important;
            border-bottom: 4px solid #1E3A8A !important;
        }}
    </style>
    """, unsafe_allow_html=True)


# ================= 4. 各页面内容渲染 =================

if st.session_state.page == 'home':
    # 首页没有顶栏，只有超大标题和圆环浮动选项卡
    st.markdown('<div class="hero-title">明清典籍隐喻计算平台</div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div id="ring-menu-anchor"></div>', unsafe_allow_html=True)
        r1c1, r1c2 = st.columns(2)
        with r1c1: 
            if st.button("🏠 首页", use_container_width=True): pass # 占位
        with r1c2: 
            if st.button("ℹ️ 关于平台", use_container_width=True): st.session_state.page = 'about'; st.rerun()
        
        r2c1, r2c2 = st.columns(2)
        with r2c1: 
            if st.button("🔍 语料检索", use_container_width=True): st.session_state.page = 'corpus'; st.rerun()
        with r2c2: 
            if st.button("🤖 在线识别", use_container_width=True): st.session_state.page = 'online'; st.rerun()

elif st.session_state.page == 'about':
    render_top_bar()
    
    # 真实全局侧边栏
    with st.sidebar:
        st.markdown("<h2 style='color:#1F2937; margin-bottom: 20px;'>📚 项目导航</h2>", unsafe_allow_html=True)
        about_nav = st.radio("", ["项目简介", "主要功能", "使用指南"], label_visibility="collapsed")
        
    st.markdown(f"<br><h2 style='color:#1E3A8A; text-align:center;'>📘 {about_nav}</h2>", unsafe_allow_html=True)
    st.divider()
    
    _, content_col, _ = st.columns([1, 8, 1])
    with content_col:
        if about_nav == "项目简介":
            st.markdown("<p style='font-size:20px; line-height:2.0; color:#374151;'>本项目旨在通过多智能体大模型技术，对明清经典文学作品中的隐喻修辞进行深度挖掘与语义计算，为数字人文研究提供基础设施。</p>", unsafe_allow_html=True)
        elif about_nav == "主要功能":
            st.markdown("""
            <div style='font-size:20px; line-height:2.0; color:#374151;'>
            <ul>
            <li style='margin-bottom: 15px;'><b>细粒度隐喻语料检索</b>：支持多维度的隐喻特征交叉检索与展示。</li>
            <li style='margin-bottom: 15px;'><b>多智能体三审制在线识别</b>：通过语义提取、深度推理、逻辑裁判三步完成自动识别。</li>
            <li><b>自动特征分类与专家共创</b>：支持细粒度分类以及专家的在线反馈与纠错。</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        elif about_nav == "使用指南":
            st.markdown("""
            <div style='font-size:20px; line-height:2.0; color:#374151;'>
            <ol>
            <li style='margin-bottom: 15px;'>点击顶端选项卡 <b>明清典籍隐喻语料库</b>，进行库内数据探索与检索。</li>
            <li>点击顶端选项卡 <b>在线隐喻识别</b>，输入自定义句子，观察多智能体的协同推理分析。</li>
            </ol>
            </div>
            """, unsafe_allow_html=True)

elif st.session_state.page == 'corpus':
    render_top_bar()
    
    st.markdown("<br><h2 style='text-align:center; color:#1F2937; margin-bottom:40px;'>明清小说隐喻语料库</h2>", unsafe_allow_html=True)
    samples = load_all_corpora()
    
    if not samples:
        st.warning("⚠️ 找不到任何语料库文件，请检查 CORPUS_CONFIG 中的路径是否正确！")
    else:
        # 居中布局：左右留白，中间放搜索框与选项
        _, col_search_center, _ = st.columns([1, 6, 1])
        with col_search_center:
            search_query = st.text_input("🔍 搜索句子内容（支持关键词）")
            
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                available_books = sorted(list(set(s["Book"] for s in samples)))
                filter_book = st.selectbox("📚 书籍筛选", ["全部"] + available_books)
            with col_filter2:
                filter_label = st.selectbox("🏷️ 基础类型", ["全部", "仅隐喻 (Label 1)", "非隐喻 (Label 0)"])
            
            filter_syntax, filter_cog, filter_conv, filter_form = "全部", "全部", "全部", "全部"
            
            if filter_label in ["全部", "仅隐喻 (Label 1)"]:
                with st.expander("🔬 细粒度特征筛选 (高级搜索)"):
                    syn_opts = sorted(list(set(s.get("Syntax_Type", "") for s in samples if s.get("Label")==1 and s.get("Syntax_Type") not in ["", "未知"])))
                    cog_opts = sorted(list(set(s.get("Cognitive_Type", "") for s in samples if s.get("Label")==1 and s.get("Cognitive_Type") not in ["", "未知"])))
                    conv_opts = sorted(list(set(s.get("Conventionality", "") for s in samples if s.get("Label")==1 and s.get("Conventionality") not in ["", "未知"])))
                    form_opts = sorted(list(set(s.get("Form_Features", "") for s in samples if s.get("Label")==1 and s.get("Form_Features") not in ["", "未知"])))
                    
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: filter_syntax = st.selectbox("📌 句法类型", ["全部"] + syn_opts)
                    with c2: filter_cog = st.selectbox("🧠 认知视角", ["全部"] + cog_opts)
                    with c3: filter_conv = st.selectbox("⏳ 规约程度", ["全部"] + conv_opts)
                    with c4: filter_form = st.selectbox("🎭 表现形式", ["全部"] + form_opts)

        filtered_samples = samples
        if search_query:
            filtered_samples = [s for s in filtered_samples if search_query in s["Sentence"]]
        if filter_book != "全部":
            filtered_samples = [s for s in filtered_samples if s["Book"] == filter_book]
        if filter_label == "仅隐喻 (Label 1)":
            filtered_samples = [s for s in filtered_samples if s["Label"] == 1]
        elif filter_label == "非隐喻 (Label 0)":
            filtered_samples = [s for s in filtered_samples if s["Label"] == 0]
            
        if filter_syntax != "全部":
            filtered_samples = [s for s in filtered_samples if s.get("Syntax_Type") == filter_syntax]
        if filter_cog != "全部":
            filtered_samples = [s for s in filtered_samples if s.get("Cognitive_Type") == filter_cog]
        if filter_conv != "全部":
            filtered_samples = [s for s in filtered_samples if s.get("Conventionality") == filter_conv]
        if filter_form != "全部":
            filtered_samples = [s for s in filtered_samples if s.get("Form_Features") == filter_form]
            
        if filter_syntax == "全部" and filter_cog == "全部" and filter_conv == "全部" and filter_form == "全部":
            filtered_samples.sort(key=lambda x: 1 if x.get("Label") == 1 and x.get("Syntax_Type", "未知") != "未知" else 0, reverse=True)
            
        st.markdown(f"<br><div style='text-align:center; font-size:20px;'>为您检索到 <span style='color:#1D4ED8; font-weight:bold; font-size:28px;'>{len(filtered_samples)}</span> 条符合条件的语料。</div>", unsafe_allow_html=True)
        st.divider()

        # ========== 下方渲染卡片的逻辑 ==========
        for s in filtered_samples[:50]:
            tag_class = "tag-metaphor" if s["Label"] == 1 else "tag-normal"
            tag_text = "✨ 隐喻 (Metaphor)" if s["Label"] == 1 else "📝 非隐喻 (Literal)"
            
            badges_html = ""
            details_html = ""
            if s["Label"] == 1:
                badges_html = f"""<div style="margin-top: 15px;">
<span class="attr-badge">📌 句法: {s.get('Syntax_Type', '未知')}</span>
<span class="attr-badge">🧠 认知: {s.get('Cognitive_Type', '未知')}</span>
<span class="attr-badge">⏳ 规约: {s.get('Conventionality', '未知')}</span>
<span class="attr-badge">🎭 特征: {s.get('Form_Features', '未知')}</span>
</div>"""

                details_html = f"""<div style="margin-top: 18px; padding-top: 18px; border-top: 1px dashed #CBD5E1;">
<b style="color: #4C1D95; font-size: 18px;">🧬 Agent 4 细分类依据：</b><br/>
<ul style="margin-top: 10px; color: #4B5563; font-size: 16px; padding-left: 20px; line-height: 1.8;">
<li style="margin-bottom: 8px;"><b>句法：</b>{s.get('Syntax_Analysis', '暂无解析')}</li>
<li style="margin-bottom: 8px;"><b>认知：</b>{s.get('Cognitive_Analysis', '暂无解析')}</li>
<li style="margin-bottom: 8px;"><b>规约：</b>{s.get('Conventionality_Analysis', '暂无解析')}</li>
<li><b>综合：</b>{s.get('Form_Analysis', '暂无解析')}</li>
</ul>
</div>"""
                
            raw_analysis = s['Analysis']
            formatted_analysis = raw_analysis 
            
            if "【一审】" in raw_analysis and "【二审】" in raw_analysis and "【终审】" in raw_analysis:
                try:
                    p1 = raw_analysis.split("【一审】:")[1].split("| 【二审】:")[0].strip()
                    p2 = raw_analysis.split("【二审】:")[1].split("| 【终审】:")[0].strip()
                    p3 = raw_analysis.split("【终审】:")[1].strip()
                    
                    formatted_analysis = f"""<div style="margin-top: 12px;">
<div class="agent-box agent1">
<b style="color: #1E3A8A; font-size: 18px;">🕵️‍♂️ Agent 1 (语义)：</b> {p1}
</div>
<div class="agent-box agent2">
<b style="color: #9A3412; font-size: 18px;">⚖️ Agent 2 (推理)：</b> {p2}
</div>
<div class="agent-box agent3" style="margin-bottom: 0;">
<b style="color: #065F46; font-size: 18px;">👨‍⚖️ Agent 3 (裁判)：</b> {p3}
</div>
</div>"""
                except Exception:
                    pass 

            other_exp_html = ""
            if s.get("Other_Explanations"):
                items_html = "".join([f"<li style='margin-bottom: 8px;'>{exp}</li>" for exp in s["Other_Explanations"]])
                other_exp_html = f"""<div style="margin-top: 25px; background-color: #FEF3C7; padding: 20px; border-radius: 8px; border-left: 4px solid #F59E0B;">
<b style="color: #B45309; font-size: 18px;">💡 其他专家/视角的解析补充：</b><br/>
<ul style="margin-top: 12px; color: #92400E; font-size: 16px; padding-left: 20px; line-height: 1.7; margin-bottom: 0;">
{items_html}
</ul>
</div>"""
            
            # CSS 已限制 .card 宽度为 80% 并居中
            st.markdown(f"""<div class="card">
<span class="{tag_class}">{tag_text}</span>
<span style="font-size: 15px; color: #6B7280; margin-left: 10px;">来源: 《{s['Book']}》</span>
{badges_html}
<div class="sentence">{s['Sentence']}</div>
<details>
<summary style="cursor: pointer; color: #2563EB; font-size: 18px; font-weight: 600; padding: 5px 0;">展开查看多维专家解析 ▾</summary>
<div class="analysis-box">
<b style="font-size: 18px; color: #1F2937;">基础判决逻辑：</b>
{formatted_analysis}
{details_html}
{other_exp_html}
</div>
</details>
</div>""", unsafe_allow_html=True)
            
            # 由于 Streamlit 表单无法轻易受 CSS width: 80% 影响，将其包裹在列中强制对齐卡片宽度
            _, col_form_align, _ = st.columns([1, 8, 1])
            with col_form_align:
                with st.expander("✍️ 发现错误？提交更正意见"):
                    with st.form(key=f"feedback_form_{s['Sentence'][:10]}_{hash(s['Sentence'])}"):
                        new_label = st.radio("正确的大类标签：", options=[0, 1], index=s['Label'], horizontal=True)
                        new_analysis = st.text_area("整体解析意见：", value=raw_analysis, height=100) 
                        
                        new_syntax = s.get('Syntax_Type', '未知')
                        new_cog = s.get('Cognitive_Type', '未知')
                        new_conv = s.get('Conventionality', '未知')
                        new_form = s.get('Form_Features', '未知')
                        
                        if s['Label'] == 1:
                            st.caption("🔽 细粒度分类修正 (选填)")
                            col_f1, col_f2 = st.columns(2)
                            with col_f1:
                                new_syntax = st.text_input("句法类型", value=new_syntax)
                                new_cog = st.text_input("认知视角", value=new_cog)
                            with col_f2:
                                new_conv = st.text_input("规约程度", value=new_conv)
                                new_form = st.text_input("表现形式", value=new_form)
                                
                        submit_btn = st.form_submit_button("安全提交至云端", use_container_width=True)
                        
                        if submit_btn:
                            feedback_data = {
                                "book": s['Book'],
                                "sentence": s['Sentence'],
                                "original_label": int(s['Label']),
                                "original_analysis": raw_analysis,
                                "suggested_label": int(new_label),
                                "suggested_analysis": new_analysis,
                                "syntax_type": new_syntax,
                                "cognitive_type": new_cog,
                                "conventionality": new_conv,
                                "form_features": new_form
                            }
                            is_success = save_feedback(feedback_data)
                            if is_success:
                                st.success("✅ 提交成功！多维纠正意见已安全送达数据库。")
            st.write("") 

elif st.session_state.page == 'online':
    render_top_bar()
    
    # 真实全局侧边栏，用于引擎配置
    with st.sidebar:
        st.markdown("<h2 style='color:#1F2937; margin-bottom: 20px;'>⚙️ 引擎配置</h2>", unsafe_allow_html=True)
        selected_model = st.selectbox("核心大模型", list(MODEL_CONFIGS.keys()), index=0)
        use_proxy = st.checkbox("启用海外代理", value=False)
        st.divider()
        st.caption("© 多智能体隐喻计算")

    st.markdown("<br><h2 style='text-align:center; color:#1F2937; margin-bottom:20px;'>多智能体隐喻在线识别</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:20px; color:#4B5563; text-align:center; margin-bottom: 40px;'>输入任意明清小说语句，观察 <b>语义提取 ➔ 考证推理 ➔ 逻辑审核 ➔ 多维特征分类</b> 的全过程。</p>", unsafe_allow_html=True)
    
    # 将输入框也控制在合适的中央区域
    _, col_online_center, _ = st.columns([1, 6, 1])
    with col_online_center:
        col_t, col_b = st.columns([3, 1])
        with col_t:
            test_sentence = st.text_area("输入测试句子：", value="忽听山石之后有一人笑道：“且请留步”", height=120)
        with col_b:
            target_book = st.text_input("目标书籍 (选填)：", placeholder="例如：红楼梦")
            
        run_btn = st.button("🚀 启动多智能体分析", type="primary", use_container_width=True)
        
        if run_btn:
            book_context = target_book.strip() if target_book.strip() else "明清小说"
            config = MODEL_CONFIGS[selected_model]
            http_client = httpx.Client(proxy="http://127.0.0.1:7890") if use_proxy else None
            client = OpenAI(api_key=config["env_key"], base_url=config["base_url"], http_client=http_client)
            
            st.divider()
            
            with st.status("🕵️‍♂️ Agent 1 (语义提取) 正在分析表层结构...", expanded=True) as status1:
                prompt1 = f"""这是《{book_context}》中的句子。
                                你是语言学的专家，你有两个任务：
                                - 分析句子含义，不要过度解读。
                                - 根据句子的意思提取出句子中可能用到比喻修辞的词,注意《{book_context}》中的特有专有名词或人物名字（如存在）不是比喻。
                                请严格返回JSON格式：{{"meaning": "句子含义描述", "metaphor_words": ["词1", "词2"]}}

                                句子内容: "{test_sentence}" """
                
                try:
                    res1 = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": prompt1}], temperature=0, response_format={'type': 'json_object'})
                    data1 = json.loads(res1.choices[0].message.content)
                    analysis1 = data1.get("meaning", "")
                    words1 = data1.get("metaphor_words", [])
                    
                    st.markdown(f"""
                    <div class="agent-box agent1">
                        <b style="color: #1E3A8A; font-size: 18px;">🎯 提纯结果：</b><br/><br/>
                        <b>表层语义：</b> {analysis1} <br/><br/>
                        <b>可疑修辞词：</b> {words1}
                    </div>
                    """, unsafe_allow_html=True)
                    status1.update(label="✅ Agent 1 (语义提纯) 完成！", state="complete", expanded=False)
                except Exception as e:
                    st.error(f"Agent 1 失败: {e}")
                    st.stop()

            with st.status("⚖️ Agent 2 (推理) 正在进行深度隐喻考证...", expanded=True) as status2:
                prompt2 = f"""这是《{book_context}》中的句子。
参考我提供给你的句子含义，以及可能用到比喻修辞的词（不一定真的有比喻），判断句子是否包含比喻修辞。注意结合比喻的定义和《{book_context}》相关知识，不要过度解读。
请严格返回JSON格式：{{ "label": 1, "analysis": "理由"}}

句子内容: "{test_sentence}"
句子含义分析: "{analysis1}"
句子中可能用到比喻修辞的词: {words1}
 """
                
                try:
                    res2 = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": prompt2}], temperature=0, response_format={'type': 'json_object'})
                    data2 = json.loads(res2.choices[0].message.content)
                    label2 = int(data2.get("label", 0))
                    reason2 = data2.get("analysis", "")
                    
                    st.markdown(f"""
                    <div class="agent-box agent2">
                        <b style="color: #9A3412; font-size: 18px;">🔍 推理报告：</b><br/><br/>
                        <b>逻辑分析：</b> {reason2} <br/><br/>
                        <b>初步标签：</b> {"隐喻 (1)" if label2 == 1 else "非隐喻 (0)"}
                    </div>
                    """, unsafe_allow_html=True)
                    status2.update(label="✅ Agent 2 (跨域推理) 完成！", state="complete", expanded=False)
                except Exception as e:
                    st.error(f"Agent 2 失败: {e}")
                    st.stop()

            with st.status("👨‍⚖️ Agent 3 (逻辑审核) 正在生成最终决议...", expanded=True) as status3:
                prompt3 = f"""检查【报告】的分析和得到的结论是否矛盾。如果矛盾则根据【报告】的分析修正结果。如果句子中含有比喻输出label 1，否则输出0。报告: "{reason2}"
                请严格返回JSON格式：{{"label": 1或0, "analysis": "最终判决理由"}}"""
                
                try:
                    res3 = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": prompt3}], temperature=0, response_format={'type': 'json_object'})
                    data3 = json.loads(res3.choices[0].message.content)
                    final_label = int(data3.get("label", 0))
                    final_reason = data3.get("analysis", "")
                    
                    st.markdown(f"""
                    <div class="agent-box agent3">
                        <b style="color: #065F46; font-size: 18px;">📌 最终定谳：</b><br/><br/>
                        <b>终审逻辑：</b> {final_reason} <br/>
                        <h3 style="color: {'#059669' if final_label==1 else '#64748B'}; margin-top: 15px;">
                            最终结论: {"🏷️ 这是一个隐喻句 (Label: 1)" if final_label == 1 else "📝 这是一个字面义句 (Label: 0)"}
                        </h3>
                    </div>
                    """, unsafe_allow_html=True)
                    status3.update(label="✅ Agent 3 (逻辑裁判) 完成！", state="complete", expanded=True)
                except Exception as e:
                    st.error(f"Agent 3 失败: {e}")
                    
            if final_label == 1:
                with st.status("🧬 Agent 4 (多维度分类) 独立专家团正在进行细粒度特征判定...", expanded=True) as status4:
                    category_tasks = [
                        {"task_name": "句法类型", "options": "名词性隐喻、动词性隐喻、形容词性/副词性隐喻、介词性隐喻", "keys": ["syntax_type", "syntax_analysis"]},
                        {"task_name": "认知视角分类", "options": "结构隐喻、方位隐喻、本体隐喻", "keys": ["cognitive_type", "cognitive_analysis"]},
                        {"task_name": "规约化角度", "options": "死喻、活喻", "keys": ["conventionality", "conventionality_analysis"]},
                        {"task_name": "表现形式与特征", "options": "单选或多选：显性隐喻/隐性隐喻、根隐喻/派生隐喻、以相似性为基础的隐喻/创造相似性的隐喻", "keys": ["form_features", "form_analysis"]}
                    ]
                    
                    cols = st.columns(2)
                    st.markdown('<div class="agent-box agent4"><b style="color: #5B21B6; font-size: 18px;">📊 细粒度分类报告：</b><br/><br/>', unsafe_allow_html=True)
                    
                    for idx, task in enumerate(category_tasks):
                        agent_prompt = f"""作为语言学专家，请判定该《{book_context}》隐喻句的【{task['task_name']}】特征。
【句子】: "{test_sentence}"
【前期隐喻分析依据】: "{reason2}"

请判断它属于以下哪些类别，并给出简要分析（必须严格从给定类别中选择）：
{task['options']}

请严格返回JSON格式：
{{
    "{task['keys'][0]}": "识别出的类别",
    "{task['keys'][1]}": "分析依据"
}}"""
                        try:
                            resp = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": agent_prompt}], temperature=0.0, response_format={'type': 'json_object'})
                            res_json = json.loads(resp.choices[0].message.content.strip())
                            col = cols[idx % 2]
                            col.markdown(f"""
                            <div style="background-color: #ffffff; padding: 20px; border-radius: 8px; border-left: 4px solid #8B5CF6; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
                                <b style="color: #4C1D95; font-size: 16px;">{task['task_name']}</b><br/><br/>
                                <span style="font-size: 15px;"><b>归类：</b> <span style="color: #D946EF; font-weight: bold; background-color: #FDF4FF; padding: 2px 6px; border-radius: 4px;">{res_json.get(task['keys'][0], '未知')}</span></span><br/><br/>
                                <span style="font-size: 15px; color: #475569; line-height: 1.6;"><b>解析：</b> {res_json.get(task['keys'][1], '')}</span>
                            </div>
                            """, unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"分类任务 {task['task_name']} 失败: {e}")
                            
                    st.markdown('</div>', unsafe_allow_html=True)
                    status4.update(label="✅ Agent 4 (多维度分类) 完成！", state="complete", expanded=True)

                st.markdown("<br><h3 style='color:#1F2937;'>💡 基于当前分析逻辑的关联推荐</h3>", unsafe_allow_html=True)
                st.caption("将 **Agent 2 的深度考证结果** 与您的 **本地语料库** 进行特征碰撞，为您找到以下最相似的过往案例：")
                samples = load_all_corpora()
                if samples:
                    sim_matches = get_similar_metaphors(reason2, test_sentence, samples, top_k=3)
                    if sim_matches:
                        for sim in sim_matches:
                            st.markdown(f"""
                            <div class="card" style="padding: 20px; margin-top: 10px; width: 100%;">
                                <span class="tag-metaphor" style="float:right; margin:0;">关联度极高</span>
                                <div style="font-size: 16px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;">《{sim['Book']}》</div>
                                <div class="sentence" style="font-size: 20px; margin: 10px 0;">{sim['Sentence']}</div>
                                <div class="analysis-box" style="margin-top: 10px; padding: 15px; font-size: 16px;"><b>库内专家解析:</b><br/>{sim['Analysis']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("当前本地语料库中暂无相似度极高的案例。")

# ================= 5. 全局浮动访问量统计 =================
total_visits = get_and_update_visit_count()
st.markdown(f"""
    <div class="floating-stats">
        <div style="font-weight: bold; margin-bottom: 2px;">👁️ 累计科研访问</div>
        <div style="color: #1D4ED8; font-size: 20px; font-weight: 800;">{total_visits} <span style="font-size: 14px; color: #6B7280; font-weight: normal;">次</span></div>
    </div>
""", unsafe_allow_html=True)
