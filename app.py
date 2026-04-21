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
import base64
from supabase import create_client, Client

# ================= 1. 页面配置与全局 CSS =================
st.set_page_config(page_title="明清文学隐喻智能分析平台", layout="wide", page_icon="📚")

# 初始化页面路由状态
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# ================= 1.5 动态背景图加载逻辑 =================
bg_path = "bg.png" # 确保背景图已命名为 bg.jpg 并放在同级目录
if os.path.exists(bg_path):
    with open(bg_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    
    if st.session_state.page == 'home':
        # 首页：高清背景，隐藏自带标题
        bg_css = f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{encoded_string}") !important;
            background-size: cover !important;
            background-position: center center !important;
            background-attachment: fixed !important;
        }}
        .hero-title {{ display: none !important; }}
        </style>
        """
    else:
        # 其他页：加盖一层 85% 不透明度的纸张色渐变，变浅做背景，保证文本清晰可读
        bg_css = f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(250, 249, 246, 0.85), rgba(250, 249, 246, 0.85)), url("data:image/jpeg;base64,{encoded_string}") !important;
            background-size: cover !important;
            background-position: center center !important;
            background-attachment: fixed !important;
        }}
        </style>
        """
    st.markdown(bg_css, unsafe_allow_html=True)

# --- 全局极简 CSS ---
st.markdown("""
<style>
    /* ================= 0. 全端通用基础样式与您的原始设计 ================= */
    .stApp {
        background-color: #FAF9F6 !important;
    }
    [data-testid="collapsedControl"], header[data-testid="stHeader"] { display: none !important; }
    .main .block-container { padding-bottom: 5rem !important; }

    /* ================= 强力抗深色模式：解决白字白底隐形问题 ================= */
    h2, h3, .hero-title, .stMarkdown p, .stRadio label p, .stCheckbox label p { color: #1F2937 !important; }
    [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] div, .stTextInput label p, .stSelectbox label p, label p, label div { color: #1F2937 !important; }
    div[data-testid="stMarkdownContainer"] { color: #1F2937 !important; }
    div[data-testid="stMarkdownContainer"] p, div[data-testid="stMarkdownContainer"] div { color: #1F2937; }

    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {
        background-color: #FFFFFF !important; color: #111827 !important; border: 1px solid #D1D5DB !important; font-size: 18px !important; padding: 12px !important;
    }
    [data-testid="stExpander"] { background-color: #FFFFFF !important; border: 1px solid #E5E7EB !important; border-radius: 8px !important; }
    [data-testid="stExpander"] summary { background-color: #F8FAFC !important; }
    [data-testid="stExpander"] summary p { color: #1F2937 !important; font-size: 20px !important; }

    /* ================= 您的原始设计保留 ================= */
    div[role="radiogroup"] { gap: 20px !important; margin: 15px 0 !important; }
    .stRadio [data-baseweb="radio"] > div:first-child { height: 24px !important; width: 24px !important; }
    .stRadio [data-testid="stMarkdownContainer"] p { font-size: 22px !important; font-weight: 500 !important; letter-spacing: 1px !important; }
    .stMarkdown p, label p { font-size: 22px !important; font-weight: 600 !important; }
    .stButton>button { font-size: 22px !important; font-weight: bold !important; padding: 10px 24px !important; border-radius: 8px !important; transition: all 0.3s ease; }

    .card { background-color: #FFFFFF; padding: 26px; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 24px; border: 1px solid #E5E7EB; border-left: 6px solid #1F2937; }
    .tag-metaphor { background-color: #DEF7EC; color: #03543F; padding: 6px 14px; border-radius: 999px; font-size: 16px; font-weight: bold; }
    .tag-normal { background-color: #F3F4F6; color: #374151; padding: 6px 14px; border-radius: 999px; font-size: 16px; font-weight: bold; }
    .attr-badge { background-color: #F5F3FF; color: #5B21B6; padding: 6px 12px; border-radius: 6px; font-size: 16px; font-weight: 600; margin-right: 8px; display: inline-block; border: 1px solid #DDD6FE; }
    .sentence { font-size: 24px; font-weight: 600; color: #111827; margin: 20px 0; font-family: 'SimSun', serif; line-height: 1.6; }
    .analysis-box { background-color: #F9FAFB; padding: 18px; border-radius: 8px; font-size: 18px; color: #374151; border-left: 3px solid #D1D5DB; margin-top: 15px; line-height: 1.6; }
    
    .agent-box { padding: 20px; border-radius: 8px; margin-bottom: 12px; border: 1px solid #E5E7EB; font-size: 18px; line-height: 1.6; }
    .agent1 {background-color: #EFF6FF; border-left: 4px solid #3B82F6;}
    .agent2 {background-color: #FFF7ED; border-left: 4px solid #F97316;}
    .agent3 {background-color: #ECFDF5; border-left: 4px solid #10B981;}
    .agent4 {background-color: #F5F3FF; border-left: 4px solid #8B5CF6;}

    .floating-stats { position: fixed; bottom: 25px; left: 25px; background-color: rgba(255, 255, 255, 0.95); padding: 15px 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); border: 1px solid #E5E7EB; z-index: 1000; backdrop-filter: blur(4px); }

    /* ================= 1. 电脑端布局 (> 768px) ================= */
    @media (min-width: 769px) {
        .main .block-container { padding-top: 150px !important; }
        div[data-testid="stVerticalBlock"] > div:has(.sticky-nav-marker) + div {
            position: fixed !important; top: 0px !important; left: 0 !important; right: 0 !important; width: 100% !important;
            background-color: rgba(255, 255, 255, 0.98) !important; backdrop-filter: blur(12px) !important;
            z-index: 999999 !important; border-bottom: 2px solid #E5E7EB !important; box-shadow: 0 4px 20px rgba(0,0,0,0.08) !important; padding: 10px 0 !important;
        }
        div[data-testid="stVerticalBlock"] > div:has(.sticky-nav-marker) + div > div {
            max-width: 1200px !important; margin: 0 auto !important; display: flex !important; align-items: center !important;
        }
        div[data-testid="stElementContainer"]:has(.sticky-nav-marker) + div[data-testid="stHorizontalBlock"] button {
            border: none !important; background: transparent !important; font-size: 18px !important; box-shadow: none !important; color: #4B5563 !important;
        }
        div[data-testid="stElementContainer"]:has(.sticky-nav-marker) + div[data-testid="stHorizontalBlock"] button[kind="primary"] {
            color: #1F2937 !important; font-weight: bold !important; border-bottom: 3px solid #1F2937 !important; border-radius: 0 !important;
        }

        .hero-title { width: 100%; text-align: center !important; font-family: 'SimSun', 'STSong', serif; font-size: 5rem; color: #1F2937; margin-top: 15vh; margin-bottom: 8vh; font-weight: bold; letter-spacing: 15px; text-shadow: 2px 2px 4px rgba(0,0,0,0.05); }
        
        /* 电脑端正方形矩阵修复 */
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) { 
            width: 350px !important; margin: 40vh auto 12vh auto !important; padding: 0 !important; 
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) > div[data-testid="stHorizontalBlock"] { gap: 20px !important; }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) [data-testid="column"] { gap: 20px !important; display: flex !important; flex-direction: column !important; }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) button { 
            width: 160px !important; height: 160px !important; border-radius: 25px !important; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.08) !important; border: 2px solid #E5E7EB !important; background-color: rgba(255, 255, 255, 0.95) !important; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important; padding: 0 !important; 
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) button:hover { 
            transform: scale(1.05) !important; box-shadow: 0 15px 35px rgba(59,130,246,0.2) !important; border-color: #3B82F6 !important; background-color: #EFF6FF !important; 
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) button > div { 
            display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; 
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) button p { 
            font-size: 26px !important; font-weight: 900 !important; color: #1E3A8A !important; margin: 0 !important; line-height: 1.4 !important; 
        }
    }

    /* ================= 2. 手机端响应式适配 (<= 768px) ================= */
    @media (max-width: 768px) {
        .main .block-container { padding-top: 20px !important; padding-left: 10px !important; padding-right: 10px !important; }
        .hero-title { font-size: 2.5rem !important; margin-top: 5vh !important; letter-spacing: 5px !important; text-align: center !important; }
        .floating-stats { display: none !important; }

        div[data-testid="stVerticalBlock"] > div:has(.sticky-nav-marker) + div { position: relative !important; top: unset !important; padding: 5px !important; background-color: rgba(250, 249, 246, 0.95) !important; box-shadow: none !important; border-bottom: none !important; }
        div[data-testid="stVerticalBlock"] > div:has(.sticky-nav-marker) + div > div { flex-direction: column !important; max-width: 100% !important; }
        div[data-testid="stVerticalBlock"] > div:has(.sticky-nav-marker) + div h2 { text-align: center !important; font-size: 24px !important; margin-bottom: 10px !important; }
        div[data-testid="stVerticalBlock"] > div:has(.sticky-nav-marker) + div button { background-color: #FFFFFF !important; color: #1F2937 !important; border: 1px solid #E5E7EB !important; box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important; height: 50px !important; margin-bottom: 8px !important; }
        div[data-testid="stVerticalBlock"] > div:has(.sticky-nav-marker) + div button[kind="primary"] { background-color: #F8FAFC !important; border-bottom: 4px solid #1F2937 !important; font-weight: 800 !important; }

        /* 手机端正方形网格修复 (去除斜向旋转) */
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) {
            display: grid !important; grid-template-columns: 115px 115px !important; grid-template-rows: 115px 115px !important;    
            column-gap: 20px !important; row-gap: 20px !important;     
            width: 250px !important; height: 250px !important; 
            margin: 35vh auto 40px auto !important; padding: 0 !important;
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) div[data-testid="stHorizontalBlock"],
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) div[data-testid="column"],
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) div[data-testid="stVerticalBlock"],
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) div[data-testid="stElementContainer"] { display: contents !important; }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) > div[data-testid="stElementContainer"]:first-child { display: none !important; }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) button {
            width: 115px !important; height: 115px !important; border-radius: 20px !important; background-color: rgba(255, 255, 255, 0.95) !important; border: 2px solid #E5E7EB !important; box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important; padding: 0 !important; margin: 0 !important;
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) button > div {
            display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; width: 100% !important; height: 100% !important;
        }
        div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .square-menu-marker) button p { font-size: 18px !important; font-weight: 900 !important; color: #1F2937 !important; margin: 0 !important; }
    }
</style>
""", unsafe_allow_html=True)

# ================= 2. 核心业务逻辑 =================

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
                "env_key": st.secrets.get("deepseek_api_key", "")
            },
            "Qwen": {
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model_name": "qwen-max",
                "env_key": st.secrets.get("qwen_api_key", "")
            },
            "GPT-4o": {
                "base_url": "https://openrouter.ai/api/v1",
                "model_name": "openai/gpt-4o-mini",
                "env_key": st.secrets.get("openrouter_api_key", "")
            }
        }
    except Exception as e:
        st.error(f"⚠️ 无法加载 API 密钥: {e}")
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

# ================= 3. 路由与全局顶栏功能 =================
def render_top_nav():
    st.markdown('<div class="sticky-nav-marker"></div>', unsafe_allow_html=True)
    _, col_title, c1, c2, c3, c4, _ = st.columns([0.5, 4, 1.2, 1.5, 1.5, 1.2, 0.5], gap="small")
    with col_title:
        st.markdown("<h2 style='margin:0; color:#1E3A8A; font-weight:900; font-size: 32px; letter-spacing: -1px;'>明清文学隐喻智能分析平台</h2>", unsafe_allow_html=True)

    pages = {"🏠 首页": "home", "ℹ️ 关于": "about", "🔍 语料库": "corpus", "🤖 在线识别": "online"}
    for col, (label, p) in zip([c4, c1, c2, c3], pages.items()):
        with col:
            is_active = st.session_state.page == p
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"nav_{p}", use_container_width=True, type=btn_type):
                st.session_state.page = p
                st.rerun()
    st.markdown("<div style='height:2px; background-color:#CBD5E1; margin: 10px auto; max-width:1200px;'></div>", unsafe_allow_html=True)

# ================= 4. 各页面视图渲染 =================
if st.session_state.page == 'home':
    # 首页只有图片背景和底部菜单块，隐藏了原版文字标题
    st.markdown('<div class="hero-title">明清典籍隐喻计算平台</div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="square-menu-marker"></div>', unsafe_allow_html=True) # 改为了正方形 marker
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            if st.button("🏠\n首页", use_container_width=True): pass 
        with r1c2:
            if st.button("ℹ️\n关于", use_container_width=True): 
                st.session_state.page = 'about'
                st.rerun()
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            if st.button("🔍\n语料库", use_container_width=True): 
                st.session_state.page = 'corpus'
                st.rerun()
        with r2c2:
            if st.button("🤖\n在线识别", use_container_width=True): 
                st.session_state.page = 'online'
                st.rerun()

elif st.session_state.page == 'about':
    render_top_nav()
    col_left_nav, col_right_content = st.columns([1, 3], gap="large")
    with col_left_nav:
        with st.container(border=True):
            st.markdown("<h3 style='color:#1F2937; margin-bottom: 15px;'>📚 导航</h3>", unsafe_allow_html=True)
            about_nav = st.radio("关于导航", ["项目简介", "主要功能", "使用指南"], label_visibility="collapsed")
    with col_right_content:
        with st.container(border=True):
            st.markdown(f"<h2 style='color:#1E3A8A; margin-bottom: 20px;'>📘 {about_nav}</h2>", unsafe_allow_html=True)
            st.divider()
            if about_nav == "项目简介":
                st.markdown("<p style='font-size:20px; line-height:2.0; color:#374151;'>本项目旨在通过多智能体大模型技术，对明清经典文学作品中的隐喻修辞进行深度挖掘与语义计算，为数字人文研究提供基础设施。</p>", unsafe_allow_html=True)
            elif about_nav == "主要功能":
                st.markdown("<div style='font-size:20px; line-height:2.0; color:#374151;'><ul><li style='margin-bottom: 15px;'><b>细粒度隐喻语料检索</b>：支持多维度的隐喻特征交叉检索与展示。</li><li style='margin-bottom: 15px;'><b>多智能体三审制在线识别</b>：通过语义提取、深度推理、逻辑裁判三步完成自动识别。</li><li><b>自动特征分类与专家共创</b>：支持细粒度分类以及专家的在线反馈与纠错。</li></ul></div>", unsafe_allow_html=True)
            elif about_nav == "使用指南":
                st.markdown("<div style='font-size:20px; line-height:2.0; color:#374151;'><ol><li style='margin-bottom: 15px;'>点击顶端选项卡 <b>明清典籍隐喻语料库</b>，进行库内数据探索与检索。</li><li>点击顶端选项卡 <b>在线隐喻识别</b>，输入自定义句子，观察多智能体的协同推理分析。</li></ol></div>", unsafe_allow_html=True)

elif st.session_state.page == 'corpus':
    render_top_nav()
    st.markdown("<h2 style='text-align:center; color:#1F2937; margin-bottom:40px;'>明清小说隐喻语料库</h2>", unsafe_allow_html=True)
    samples = load_all_corpora()
    
    if not samples:
        st.warning("⚠️ 找不到任何语料库文件，请检查 CORPUS_CONFIG 中的路径是否正确！")
    else:
        _, col_main_center, _ = st.columns([1, 6, 1])
        with col_main_center:
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
            if search_query: filtered_samples = [s for s in filtered_samples if search_query in s["Sentence"]]
            if filter_book != "全部": filtered_samples = [s for s in filtered_samples if s["Book"] == filter_book]
            if filter_label == "仅隐喻 (Label 1)": filtered_samples = [s for s in filtered_samples if s["Label"] == 1]
            elif filter_label == "非隐喻 (Label 0)": filtered_samples = [s for s in filtered_samples if s["Label"] == 0]
            if filter_syntax != "全部": filtered_samples = [s for s in filtered_samples if s.get("Syntax_Type") == filter_syntax]
            if filter_cog != "全部": filtered_samples = [s for s in filtered_samples if s.get("Cognitive_Type") == filter_cog]
            if filter_conv != "全部": filtered_samples = [s for s in filtered_samples if s.get("Conventionality") == filter_conv]
            if filter_form != "全部": filtered_samples = [s for s in filtered_samples if s.get("Form_Features") == filter_form]
                
            # if filter_syntax == "全部" and filter_cog == "全部" and filter_conv == "全部" and filter_form == "全部":
            #     filtered_samples.sort(key=lambda x: 1 if x.get("Label") == 1 and x.get("Syntax_Type", "未知") != "未知" else 0, reverse=True)
                
            st.markdown(f"<br><div style='text-align:center; font-size:20px; margin-bottom: 20px;'>为您检索到 <span style='color:#1D4ED8; font-weight:bold; font-size:28px;'>{len(filtered_samples)}</span> 条符合条件的语料。</div>", unsafe_allow_html=True)
            
            # ========== 渲染卡片 ==========
            for idx, s in enumerate(filtered_samples[:50]):
                tag_class = "tag-metaphor" if s["Label"] == 1 else "tag-normal"
                tag_text = "✨ 隐喻 (Metaphor)" if s["Label"] == 1 else "📝 非隐喻 (Literal)"
                
                badges_html, details_html, other_exp_html = "", "", ""
                if s["Label"] == 1:
                    badges_html = f"""<div style="margin-top: 15px;"><span class="attr-badge">📌 句法: {s.get('Syntax_Type', '未知')}</span><span class="attr-badge">🧠 认知: {s.get('Cognitive_Type', '未知')}</span><span class="attr-badge">⏳ 规约: {s.get('Conventionality', '未知')}</span><span class="attr-badge">🎭 特征: {s.get('Form_Features', '未知')}</span></div>"""
                    details_html = f"""<div style="margin-top: 18px; padding-top: 18px; border-top: 1px dashed #CBD5E1;"><b style="color: #4C1D95; font-size: 18px;">🧬 Agent 4 细分类依据：</b><br/><ul style="margin-top: 10px; color: #4B5563; font-size: 16px; padding-left: 20px; line-height: 1.8;"><li style="margin-bottom: 8px;"><b>句法：</b>{s.get('Syntax_Analysis', '暂无解析')}</li><li style="margin-bottom: 8px;"><b>认知：</b>{s.get('Cognitive_Analysis', '暂无解析')}</li><li style="margin-bottom: 8px;"><b>规约：</b>{s.get('Conventionality_Analysis', '暂无解析')}</li><li><b>综合：</b>{s.get('Form_Analysis', '暂无解析')}</li></ul></div>"""
                    
                raw_analysis = s['Analysis']
                formatted_analysis = raw_analysis 
                if "【一审】" in raw_analysis and "【二审】" in raw_analysis and "【终审】" in raw_analysis:
                    try:
                        p1 = raw_analysis.split("【一审】:")[1].split("| 【二审】:")[0].strip()
                        p2 = raw_analysis.split("【二审】:")[1].split("| 【终审】:")[0].strip()
                        p3 = raw_analysis.split("【终审】:")[1].strip()
                        formatted_analysis = f"""<div style="margin-top: 12px;"><div class="agent-box agent1"><b style="color: #1E3A8A; font-size: 18px;">🕵️‍♂️ Agent 1 (语义)：</b> {p1}</div><div class="agent-box agent2"><b style="color: #9A3412; font-size: 18px;">⚖️ Agent 2 (推理)：</b> {p2}</div><div class="agent-box agent3" style="margin-bottom: 0;"><b style="color: #065F46; font-size: 18px;">👨‍⚖️ Agent 3 (裁判)：</b> {p3}</div></div>"""
                    except: pass 

                if s.get("Other_Explanations"):
                    items_html = "".join([f"<li style='margin-bottom: 8px;'>{exp}</li>" for exp in s["Other_Explanations"]])
                    other_exp_html = f"""<div style="margin-top: 25px; background-color: #FEF3C7; padding: 20px; border-radius: 8px; border-left: 4px solid #F59E0B;"><b style="color: #B45309; font-size: 18px;">💡 其他专家/视角的解析补充：</b><br/><ul style="margin-top: 12px; color: #92400E; font-size: 16px; padding-left: 20px; line-height: 1.7; margin-bottom: 0;">{items_html}</ul></div>"""
                
                st.markdown(f"""<div class="card"><span class="{tag_class}">{tag_text}</span><span style="font-size: 15px; color: #6B7280; margin-left: 10px;">来源: 《{s['Book']}》</span>{badges_html}<div class="sentence">{s['Sentence']}</div><details><summary style="cursor: pointer; color: #2563EB; font-size: 18px; font-weight: 600; padding: 5px 0;">展开查看多维专家解析 ▾</summary><div class="analysis-box"><b style="font-size: 18px; color: #1F2937;">基础判决逻辑：</b>{formatted_analysis}{details_html}{other_exp_html}</div></details></div>""", unsafe_allow_html=True)
                
                with st.expander("✍️ 发现错误？提交更正意见"):
                    with st.form(key=f"feedback_form_{idx}"):
                        new_label = st.radio("正确的大类标签：", options=[0, 1], index=s['Label'], horizontal=True, key=f"rad_{idx}")
                        new_analysis = st.text_area("整体解析意见：", value=raw_analysis, height=100, key=f"txt_{idx}") 
                        
                        new_syntax, new_cog, new_conv, new_form = s.get('Syntax_Type', '未知'), s.get('Cognitive_Type', '未知'), s.get('Conventionality', '未知'), s.get('Form_Features', '未知')
                        if s['Label'] == 1:
                            st.caption("🔽 细粒度分类修正 (选填)")
                            col_f1, col_f2 = st.columns(2)
                            with col_f1:
                                new_syntax = st.text_input("句法类型", value=new_syntax, key=f"syn_{idx}")
                                new_cog = st.text_input("认知视角", value=new_cog, key=f"cog_{idx}")
                            with col_f2:
                                new_conv = st.text_input("规约程度", value=new_conv, key=f"conv_{idx}")
                                new_form = st.text_input("表现形式", value=new_form, key=f"frm_{idx}")
                                
                        if st.form_submit_button("安全提交至云端", use_container_width=True):
                            feedback_data = {
                                "book": s['Book'], "sentence": s['Sentence'], "original_label": int(s['Label']), "original_analysis": raw_analysis,
                                "suggested_label": int(new_label), "suggested_analysis": new_analysis,
                                "syntax_type": new_syntax, "cognitive_type": new_cog, "conventionality": new_conv, "form_features": new_form
                            }
                            if save_feedback(feedback_data): st.success("✅ 提交成功！")
                st.write("") 

elif st.session_state.page == 'online':
    render_top_nav()
    st.markdown("<h2 style='text-align:center; color:#1F2937; margin-bottom:30px;'>多智能体隐喻在线识别</h2>", unsafe_allow_html=True)
    col_model_select, col_main_action = st.columns([1, 3], gap="large")
    
    with col_model_select:
        with st.container(border=True):
            st.markdown("<h3 style='color:#1F2937; margin-bottom: 20px;'>⚙️ 引擎配置</h3>", unsafe_allow_html=True)
            selected_model = st.selectbox("核心大模型", list(MODEL_CONFIGS.keys()), index=0)
            use_proxy = st.checkbox("启用海外代理", value=False)

    with col_main_action:
        with st.container(border=True):
            st.markdown("<p style='font-size:20px; color:#4B5563; margin-bottom: 20px;'>输入任意明清小说语句，观察 <b>语义提取 ➔ 考证推理 ➔ 逻辑审核 ➔ 多维特征分类</b> 的全过程。</p>", unsafe_allow_html=True)
            col_t, col_b = st.columns([3, 1])
            with col_t: test_sentence = st.text_area("输入测试句子：", value="忽听山石之后有一人笑道：“且请留步”", height=150)
            with col_b: target_book = st.text_input("目标书籍 (选填)：", placeholder="例如：红楼梦")
                
            if st.button("🚀 启动多智能体分析", type="primary", use_container_width=True):
                book_context = target_book.strip() if target_book.strip() else "明清小说"
                config = MODEL_CONFIGS.get(selected_model, {})
                if not config:
                    st.error("模型配置缺失！")
                    st.stop()
                    
                http_client = httpx.Client(proxy="http://127.0.0.1:7890") if use_proxy else None
                client = OpenAI(api_key=config.get("env_key",""), base_url=config.get("base_url",""), http_client=http_client)
                st.divider()
                
                with st.status("🕵️‍♂️ Agent 1 (语义提取) 正在分析表层结构...", expanded=True) as status1:
                    prompt1 = f"""这是《{book_context}》中的句子。\n你是语言学的专家，你有两个任务：\n- 分析句子含义，不要过度解读。\n- 根据句子的意思提取出句子中可能用到比喻修辞的词,注意《{book_context}》中的特有专有名词或人物名字（如存在）不是比喻。\n请严格返回JSON格式：{{"meaning": "句子含义描述", "metaphor_words": ["词1", "词2"]}}\n\n句子内容: "{test_sentence}" """
                    try:
                        res1 = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": prompt1}], temperature=0, response_format={'type': 'json_object'})
                        data1 = json.loads(res1.choices[0].message.content)
                        analysis1, words1 = data1.get("meaning", ""), data1.get("metaphor_words", [])
                        st.markdown(f"""<div class="agent-box agent1"><b style="color: #1E3A8A; font-size: 18px;">🎯 提纯结果：</b><br/><br/><b>表层语义：</b> {analysis1} <br/><br/><b>可疑修辞词：</b> {words1}</div>""", unsafe_allow_html=True)
                        status1.update(label="✅ Agent 1 (语义提纯) 完成！", state="complete", expanded=False)
                    except Exception as e: st.error(f"Agent 1 失败: {e}"); st.stop()

                with st.status("⚖️ Agent 2 (推理) 正在进行深度隐喻考证...", expanded=True) as status2:
                    prompt2 = f"""这是《{book_context}》中的句子。\n参考我提供给你的句子含义，以及可能用到比喻修辞的词（不一定真的有比喻），判断句子是否包含比喻修辞。注意结合比喻的定义和《{book_context}》相关知识，不要过度解读。\n请严格返回JSON格式：{{ "label": 1, "analysis": "理由"}}\n\n句子内容: "{test_sentence}"\n句子含义分析: "{analysis1}"\n句子中可能用到比喻修辞的词: {words1}"""
                    try:
                        res2 = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": prompt2}], temperature=0, response_format={'type': 'json_object'})
                        data2 = json.loads(res2.choices[0].message.content)
                        label2, reason2 = int(data2.get("label", 0)), data2.get("analysis", "")
                        st.markdown(f"""<div class="agent-box agent2"><b style="color: #9A3412; font-size: 18px;">🔍 推理报告：</b><br/><br/><b>逻辑分析：</b> {reason2} <br/><br/><b>初步标签：</b> {"隐喻 (1)" if label2 == 1 else "非隐喻 (0)"}</div>""", unsafe_allow_html=True)
                        status2.update(label="✅ Agent 2 (跨域推理) 完成！", state="complete", expanded=False)
                    except Exception as e: st.error(f"Agent 2 失败: {e}"); st.stop()

                with st.status("👨‍⚖️ Agent 3 (逻辑审核) 正在生成最终决议...", expanded=True) as status3:
                    prompt3 = f"""检查【报告】的分析和得到的结论是否矛盾。如果矛盾则根据【报告】的分析修正结果。如果句子中含有比喻输出label 1，否则输出0。报告: "{reason2}"\n请严格返回JSON格式：{{"label": 1或0, "analysis": "最终判决理由"}}"""
                    try:
                        res3 = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": prompt3}], temperature=0, response_format={'type': 'json_object'})
                        data3 = json.loads(res3.choices[0].message.content)
                        final_label, final_reason = int(data3.get("label", 0)), data3.get("analysis", "")
                        st.markdown(f"""<div class="agent-box agent3"><b style="color: #065F46; font-size: 18px;">📌 最终定谳：</b><br/><br/><b>终审逻辑：</b> {final_reason} <br/><h3 style="color: {'#059669' if final_label==1 else '#64748B'}; margin-top: 15px;">最终结论: {"🏷️ 这是一个隐喻句 (Label: 1)" if final_label == 1 else "📝 这是一个字面义句 (Label: 0)"}</h3></div>""", unsafe_allow_html=True)
                        status3.update(label="✅ Agent 3 (逻辑裁判) 完成！", state="complete", expanded=True)
                    except Exception as e: st.error(f"Agent 3 失败: {e}")
                        
                if final_label == 1:
                    with st.status("🧬 Agent 4 (多维度分类) 独立专家团正在进行细粒度特征判定...", expanded=True) as status4:
                        category_tasks = [
                            {"task_name": "句法类型", "options": "名词性隐喻、动词性隐喻、形容词性/副词性隐喻、介词性隐喻", "keys": ["syntax_type", "syntax_analysis"]},
                            {"task_name": "认知视角分类", "options": "结构隐喻、方位隐喻、本体隐喻", "keys": ["cognitive_type", "cognitive_analysis"]},
                            {"task_name": "规约化角度", "options": "死喻、活喻", "keys": ["conventionality", "conventionality_analysis"]},
                            {"task_name": "表现形式与特征", "options": "单选或多选：显性隐喻/隐性隐喻、根隐喻/派生隐喻、以相似性为基础的隐喻/创造相似性的隐喻", "keys": ["form_features", "form_analysis"]}
                        ]
                        
                        # 🚀 核心修复：创建一个空占位符，用来装整个带紫框的 HTML
                        report_placeholder = st.empty()
                        
                        # 定义 HTML 的开头（包含紫框和 CSS Grid 两列布局）和结尾
                        html_start = '<div class="agent-box agent4"><b style="color: #5B21B6; font-size: 18px;">📊 细粒度分类报告：</b><br/><div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">'
                        html_end = '</div></div>'
                        current_cards = ""
                        
                        # 预先显示紫框和标题（这时候里面是空的）
                        report_placeholder.markdown(html_start + current_cards + html_end, unsafe_allow_html=True)
                        
                        for idx, task in enumerate(category_tasks):
                            agent_prompt = f"""作为语言学专家，请判定该《{book_context}》隐喻句的【{task['task_name']}】特征。\n【句子】: "{test_sentence}"\n【前期隐喻分析依据】: "{reason2}"\n\n请判断它属于以下哪些类别，并给出简要分析（必须严格从给定类别中选择）：\n{task['options']}\n\n请严格返回JSON格式：\n{{\n"{task['keys'][0]}": "识别出的类别",\n"{task['keys'][1]}": "分析依据"\n}}"""
                            try:
                                resp = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": agent_prompt}], temperature=0.0, response_format={'type': 'json_object'})
                                
                                # 强力剥离 Markdown 代码块符，防止 JSON 解析报错
                                raw_reply = resp.choices[0].message.content.strip()
                                if raw_reply.startswith("```"):
                                    raw_reply = raw_reply.lstrip("`").lstrip("json").strip()
                                    raw_reply = raw_reply.rstrip("`").strip()
                                res_json = json.loads(raw_reply)
                                
                                # 纯 HTML 格式生成一张小卡片
                                card_html = f"""
<div style="background-color: #ffffff; padding: 20px; border-radius: 8px; border-left: 4px solid #8B5CF6; box-shadow: 0 2px 4px rgba(0,0,0,0.02); height: 100%;">
    <b style="color: #4C1D95; font-size: 16px;">{task['task_name']}</b><br/><br/>
    <span style="font-size: 15px;"><b>归类：</b> <span style="color: #D946EF; font-weight: bold; background-color: #FDF4FF; padding: 2px 6px; border-radius: 4px;">{res_json.get(task['keys'][0], '未知')}</span></span><br/><br/>
    <span style="font-size: 15px; color: #475569; line-height: 1.6;"><b>解析：</b> {res_json.get(task['keys'][1], '')}</span>
</div>
                                """
                                current_cards += card_html
                                
                                # 每解析出一个卡片，就把带紫框的整个大包裹重新渲染一次，实现动态装填效果
                                report_placeholder.markdown(html_start + current_cards + html_end, unsafe_allow_html=True)
                                
                            except Exception as e: 
                                st.error(f"分类任务 {task['task_name']} 解析失败: {e}")
                                
                        status4.update(label="✅ Agent 4 (多维度分类) 完成！", state="complete", expanded=True)

                    st.markdown("<br><h3 style='color:#1F2937;'>💡 基于当前分析逻辑的关联推荐</h3>", unsafe_allow_html=True)
                    st.caption("将 **Agent 2 的深度考证结果** 与您的 **本地语料库** 进行特征碰撞，为您找到以下最相似的过往案例：")
                    samples = load_all_corpora()
                    if samples:
                        sim_matches = get_similar_metaphors(reason2, test_sentence, samples, top_k=3)
                        if sim_matches:
                            for sim in sim_matches:
                                st.markdown(f"""<div class="card" style="padding: 20px; margin-top: 10px; width: 100%;"><span class="tag-metaphor" style="float:right; margin:0;">关联度极高</span><div style="font-size: 16px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;">《{sim['Book']}》</div><div class="sentence" style="font-size: 20px; margin: 10px 0;">{sim['Sentence']}</div><div class="analysis-box" style="margin-top: 10px; padding: 15px; font-size: 16px;"><b>库内专家解析:</b><br/>{sim['Analysis']}</div></div>""", unsafe_allow_html=True)
                        else: st.info("当前本地语料库中暂无相似度极高的案例。")

# ================= 5. 左下角全局浮动访问量统计 =================
total_visits = get_and_update_visit_count()
st.markdown(f"""
    <div class="floating-stats">
        <div style="font-weight: bold; margin-bottom: 5px;">👁️ 累计科研访问</div>
        <div style="color: #1D4ED8; font-size: 20px; font-weight: 800;">{total_visits} <span style="font-size: 14px; color: #6B7280; font-weight: normal;">次</span></div>
    </div>
""", unsafe_allow_html=True)
