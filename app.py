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

st.markdown("""
<style>
    /* 全局背景与纸张质感 */
    .stApp {
        background-color: #FAF9F6;
        background-image: radial-gradient(#E5E7EB 0.5px, transparent 0.5px);
        background-size: 24px 24px;
    }
    
    /* 彻底隐藏 Streamlit 默认的全局侧边栏切换按钮和顶部装饰 */
    [data-testid="collapsedControl"] { display: none !important; }
    header {visibility: hidden;}
    .main .block-container {padding-top: 0rem; padding-bottom: 5rem;} /* 底部留出空间给统计 */

    /* 首页大标题：绝对居中 */
    .hero-title {
        font-family: 'SimSun', 'STSong', serif;
        font-size: 5rem;
        color: #1F2937;
        text-align: center;
        margin-top: 30vh;
        font-weight: bold;
        letter-spacing: 15px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.05);
    }

    /* 选项卡样式大幅优化：大气、居中、加高、字号变大 */
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        justify-content: center;
        background-color: #FFFFFF;
        padding: 15px 0; /* 增加上下内边距 */
        border-bottom: 2px solid #E5E7EB; /* 加粗底边框 */
        position: sticky;
        top: 0;
        z-index: 999;
        gap: 40px; /* 增加选项卡之间的间距 */
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 20px !important; /* 显著放大字号 */
        font-weight: 600 !important;
        color: #4B5563 !important;
        padding: 10px 20px !important; /* 增加每个 Tab 的点击热区 */
        height: auto !important; /* 解除高度限制 */
    }
    .stTabs [aria-selected="true"] {
        color: #1D4ED8 !important; /* 选中时的高亮颜色更深 */
        border-bottom: 3px solid #1D4ED8 !important; /* 选中时的底边框更明显 */
    }

    /* “关于”页面自定义左侧导航容器样式 */
    .about-nav-container {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border-right: 1px solid #E5E7EB;
        height: calc(100vh - 150px); /* 撑满高度，模拟真实侧边栏 */
    }

    /* 保持原有的卡片与 Agent 样式 */
    .card {
        background-color: #FFFFFF; padding: 24px; border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 20px;
        border: 1px solid #F3F4F6; border-left: 6px solid #1E3A8A;
    }
    .tag-metaphor { background-color: #DEF7EC; color: #03543F; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: bold; }
    .tag-normal { background-color: #F3F4F6; color: #374151; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: bold; }
    .attr-badge { background-color: #F5F3FF; color: #5B21B6; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; margin-right: 8px; display: inline-block; border: 1px solid #DDD6FE; }
    .sentence { font-size: 20px; font-weight: 600; color: #111827; margin: 15px 0; font-family: 'SimSun', serif; }
    .analysis-box { background-color: #F9FAFB; padding: 15px; border-radius: 6px; font-size: 14px; color: #374151; border-left: 3px solid #D1D5DB; margin-top: 12px; }
    .agent-box { padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #E5E7EB; }
    .agent1 {background-color: #EFF6FF; border-left: 4px solid #3B82F6;}
    .agent2 {background-color: #FFF7ED; border-left: 4px solid #F97316;}
    .agent3 {background-color: #ECFDF5; border-left: 4px solid #10B981;}
    .agent4 {background-color: #F5F3FF; border-left: 4px solid #8B5CF6;}
    
    /* 左下角浮动访问量统计模块 */
    .floating-stats {
        position: fixed;
        bottom: 20px;
        left: 20px;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 10px 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #E5E7EB;
        z-index: 1000;
        font-size: 13px;
        color: #4B5563;
        backdrop-filter: blur(4px);
    }
</style>
""", unsafe_allow_html=True)

# ================= 2. 核心业务逻辑 (完全保留原样) =================

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

# ================= 3. UI 布局重构 (主入口) =================

# --- 隐藏原本基于 st.sidebar 的所有内容 ---
# Streamlit 会默认生成左侧边栏触发器。CSS 里已经将它 display: none 强制隐藏了。

# 顶部选项卡：主页面布局的核心，现在已经通过 CSS 放大并居中
main_tabs = st.tabs(["🏠 首页", "ℹ️ 关于", "🔍 明清典籍隐喻语料库", "🤖 在线隐喻识别"])

# --- Tab 0: 首页 (主界面) ---
with main_tabs[0]:
    st.markdown('<div class="hero-title">明清典籍隐喻计算平台</div>', unsafe_allow_html=True)

# --- Tab 1: 关于 (关于界面) ---
with main_tabs[1]:
    st.markdown("<br>", unsafe_allow_html=True)
    # 利用列布局模拟一个专属的、高度一致的“左边栏”
    col_left_nav, col_right_content = st.columns([1, 4])
    
    with col_left_nav:
        st.markdown('<div class="about-nav-container">', unsafe_allow_html=True)
        st.markdown("### 📚 平台导航")
        about_nav = st.radio("", ["项目简介", "主要功能", "使用指南"], label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_right_content:
        st.subheader(f"📘 {about_nav}")
        if about_nav == "项目简介":
            st.write("本项目旨在通过多智能体大模型技术，对明清经典文学作品中的隐喻修辞进行深度挖掘与语义计算，为数字人文研究提供基础设施。")
        elif about_nav == "主要功能":
            st.markdown("""
            - **细粒度隐喻语料检索**：支持多维度的隐喻特征交叉检索与展示。
            - **多智能体三审制在线识别**：通过语义提取、深度推理、逻辑裁判三步完成自动识别。
            - **自动特征分类与专家共创**：支持细粒度分类以及专家的在线反馈与纠错。
            """)
        elif about_nav == "使用指南":
            st.markdown("""
            1. 点击顶部选项卡 **明清典籍隐喻语料库**，进行库内数据探索与检索。
            2. 点击顶部选项卡 **在线隐喻识别**，输入自定义句子，观察多智能体的协同推理分析。
            """)

# --- Tab 2: 语料库 (保持原样) ---
with main_tabs[2]:
    st.header("明清小说隐喻语料库 ")
    samples = load_all_corpora()
    if not samples: st.warning("未找到语料文件")
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: search_query = st.text_input("🔍 搜索关键词", key="corpus_search")
        with c2: filter_book = st.selectbox("📚 书籍", ["全部"] + sorted(list(set(s["Book"] for s in samples))))
        with c3: filter_label = st.selectbox("🏷️ 类型", ["全部", "仅隐喻", "非隐喻"])
        
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

        if f_syntax == "全部" and f_cog == "全部" and f_conv == "全部" and f_form == "全部":
            filtered.sort(key=lambda x: 1 if x.get("Label") == 1 and x.get("Syntax_Type", "未知") != "未知" else 0, reverse=True)
            
        st.markdown(f"为您检索到 <span style='color:#3B82F6; font-weight:bold; font-size:16px;'>{len(filtered)}</span> 条符合条件的语料。", unsafe_allow_html=True)
        st.divider()

        for s in filtered[:50]:
            tag_class = "tag-metaphor" if s["Label"] == 1 else "tag-normal"
            tag_text = "✨ 隐喻 (Metaphor)" if s["Label"] == 1 else "📝 非隐喻 (Literal)"
            
            badges_html = ""
            details_html = ""
            if s["Label"] == 1:
                badges_html = f"""<div style="margin-top: 8px;">
<span class="attr-badge">📌 句法: {s.get('Syntax_Type', '未知')}</span>
<span class="attr-badge">🧠 认知: {s.get('Cognitive_Type', '未知')}</span>
<span class="attr-badge">⏳ 规约: {s.get('Conventionality', '未知')}</span>
<span class="attr-badge">🎭 特征: {s.get('Form_Features', '未知')}</span>
</div>"""
                details_html = f"""<div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #CBD5E1;">
<b>🧬 Agent 4 细分类依据：</b><br/>
<ul style="margin-top: 5px; color: #64748B; font-size: 13px;">
<li style="margin-bottom: 4px;"><b>句法：</b>{s.get('Syntax_Analysis', '暂无解析')}</li>
<li style="margin-bottom: 4px;"><b>认知：</b>{s.get('Cognitive_Analysis', '暂无解析')}</li>
<li style="margin-bottom: 4px;"><b>规约：</b>{s.get('Conventionality_Analysis', '暂无解析')}</li>
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
                    formatted_analysis = f"""<div style="margin-top: 5px;">
<div style="background-color: #EFF6FF; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #3B82F6; margin-bottom: 8px; font-size: 13px;">
<b style="color: #1E3A8A;">🕵️‍♂️ Agent 1 (语义)：</b> {p1}
</div>
<div style="background-color: #FFF7ED; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #F97316; margin-bottom: 8px; font-size: 13px;">
<b style="color: #9A3412;">⚖️ Agent 2 (推理)：</b> {p2}
</div>
<div style="background-color: #ECFDF5; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #10B981; font-size: 13px;">
<b style="color: #065F46;">👨‍⚖️ Agent 3 (裁判)：</b> {p3}
</div>
</div>"""
                except Exception:
                    pass 

            other_exp_html = ""
            if s.get("Other_Explanations"):
                items_html = "".join([f"<li style='margin-bottom: 6px;'>{exp}</li>" for exp in s["Other_Explanations"]])
                other_exp_html = f"""<div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #FCD34D; background-color: #FEF3C7; padding: 12px; border-radius: 6px;">
<b style="color: #D97706; font-size: 14px;">💡 其他专家/视角的解析补充：</b><br/>
<ul style="margin-top: 8px; color: #92400E; font-size: 13px; padding-left: 20px;">
{items_html}
</ul>
</div>"""
            
            st.markdown(f"""<div class="card">
<span class="{tag_class}">{tag_text}</span>
<span style="font-size: 12px; color: #64748B;">来源: 《{s['Book']}》</span>
{badges_html}
<div class="sentence" style="margin-top: 10px;">{s['Sentence']}</div>
<details>
<summary style="cursor: pointer; color: #3B82F6; font-size: 14px; font-weight: 500;">展开查看多维专家解析</summary>
<div class="analysis-box" style="padding-top: 10px;">
<b style="font-size: 14px; color: #475569;">基础判决逻辑：</b>
{formatted_analysis}
{details_html}
{other_exp_html}
</div>
</details>
</div>""", unsafe_allow_html=True)
            
            with st.expander("✍️ 发现错误？提交更正意见"):
                with st.form(key=f"feedback_form_{s['Sentence'][:10]}_{hash(s['Sentence'])}"):
                    new_label = st.radio("正确的大类标签：", options=[0, 1], index=s['Label'], horizontal=True)
                    new_analysis = st.text_area("整体解析意见：", value=raw_analysis, height=80) 
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
                    if st.form_submit_button("安全提交至云端"):
                        feedback_data = {
                            "book": s['Book'], "sentence": s['Sentence'], "original_label": int(s['Label']),
                            "original_analysis": raw_analysis, "suggested_label": int(new_label),
                            "suggested_analysis": new_analysis, "syntax_type": new_syntax,
                            "cognitive_type": new_cog, "conventionality": new_conv, "form_features": new_form
                        }
                        if save_feedback(feedback_data):
                            st.success("✅ 提交成功！多维纠正意见已安全送达数据库。")
            st.write("") 

# --- Tab 4: 在线识别 (原布局，新增左侧推理模型选择) ---
with main_tabs[3]:
    st.header("多智能体在线识别")
    
    # 构建左右两列布局，左侧较窄放置模型选择，右侧较宽放置主要功能
    col_model_select, col_main_action = st.columns([1, 4])
    
    with col_model_select:
        # 这里把原先全局侧栏的模型选择移了过来
        st.markdown('<div style="background-color: #FFFFFF; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #E5E7EB;">', unsafe_allow_html=True)
        st.subheader("⚙️ 引擎配置")
        selected_model = st.selectbox("选择大模型", list(MODEL_CONFIGS.keys()), index=0)
        use_proxy = st.checkbox("启用海外代理", value=False)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_main_action:
        st.markdown("输入任意明清小说语句，观察 **语义提取 ➔ 考证推理 ➔ 逻辑审核 ➔ 多维特征分类** 的全过程。")
        col_t, col_b = st.columns([3, 1])
        with col_t: ts = st.text_area("输入测试句子：", value="忽听山石之后有一人笑道：“且请留步”", height=100)
        with col_b: tb = st.text_input("目标书籍 (选填)：", placeholder="例如：红楼梦")
        
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
            for sim in sims: 
                st.markdown(f'<div class="card"><span class="tag-metaphor" style="float:right;">关联度高</span><div style="font-weight:bold;">《{sim["Book"]}》</div><div>{sim["Sentence"]}</div></div>', unsafe_allow_html=True)

# ================= 4. 全局浮动访问量统计 =================
# 置于代码末尾以确保其始终在左下角渲染
total_visits = get_and_update_visit_count()
st.markdown(f"""
    <div class="floating-stats">
        <div style="font-weight: bold; margin-bottom: 2px;">👁️ 累计科研访问</div>
        <div style="color: #1D4ED8; font-size: 16px; font-weight: 800;">{total_visits} <span style="font-size: 12px; color: #6B7280; font-weight: normal;">次</span></div>
    </div>
""", unsafe_allow_html=True)
