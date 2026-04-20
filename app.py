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

# ================= 1. 页面与专业 UI 配置 =================
st.set_page_config(page_title="明清小说隐喻计算平台", layout="wide", page_icon="📚")

# 纯 CSS UI 优化，大幅提升学术质感与交互体验
st.markdown("""
<style>
    /* 全局背景色微调，更加护眼 */
    .stApp {background-color: #F8FAFC;}
    
    /* 现代化卡片：增加圆角、平滑阴影、以及鼠标悬浮上浮效果 */
    .card {
        background-color: #ffffff; padding: 25px; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03); 
        margin-bottom: 24px; border: 1px solid #F1F5F9; border-left: 6px solid #2563EB;
        transition: all 0.3s ease;
    }
    .card:hover {
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); 
        transform: translateY(-2px);
    }
    
    /* 渐变色高级标签 */
    .tag-metaphor {
        background: linear-gradient(135deg, #DEF7EC, #D1FAE5); color: #046C4E; 
        padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; 
        letter-spacing: 0.5px; border: 1px solid #A7F3D0; margin-right: 12px;
    }
    .tag-normal {
        background: linear-gradient(135deg, #F3F4F6, #E5E7EB); color: #4B5563; 
        padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; 
        letter-spacing: 0.5px; border: 1px solid #D1D5DB; margin-right: 12px;
    }
    
    /* 细粒度特征徽章 */
    .attr-badge {
        background-color: #EEF2FF; color: #4338CA; padding: 5px 12px;
        border-radius: 6px; font-size: 12px; font-weight: 500; 
        margin-right: 8px; margin-bottom: 8px; display: inline-block;
        border: 1px solid #C7D2FE;
    }
    
    /* 句子正文排版优化：字号放大，适配古籍衬线体 */
    .sentence {
        font-size: 20px; font-weight: 600; color: #111827; 
        margin: 18px 0; font-family: 'Noto Serif SC', 'STZhongsong', 'SimSun', serif; 
        line-height: 1.6; letter-spacing: 0.5px;
    }
    
    /* 专家解析下拉框优化 */
    .analysis-box {
        background-color: #F8FAFC; padding: 18px; border-radius: 8px;
        font-size: 14.5px; color: #334155; border-left: 4px solid #94A3B8; 
        margin-top: 15px; line-height: 1.6;
    }
    
    /* 多智能体独立对话框优化 */
    .agent-box {
        padding: 18px; border-radius: 10px; margin-bottom: 12px; 
        border: 1px solid #E2E8F0; box-shadow: 0 1px 2px rgba(0,0,0,0.02);
        font-size: 14px; line-height: 1.6;
    }
    .agent1 {background-color: #EFF6FF; border-left: 5px solid #3B82F6;}
    .agent2 {background-color: #FFF7ED; border-left: 5px solid #F97316;}
    .agent3 {background-color: #ECFDF5; border-left: 5px solid #10B981;}
    .agent4 {background-color: #F5F3FF; border-left: 5px solid #8B5CF6;}
    
    /* 侧边栏计数器美化 */
    .visit-counter {
        background: linear-gradient(135deg, #F8FAFC, #F1F5F9); padding: 15px; 
        border-radius: 8px; text-align: center; border: 1px solid #E2E8F0; 
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

# ================= 0. 访问量统计模块 =================
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
        except Exception as e:
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

# ================= 2. 模型与数据库配置 =================
def get_model_configs():
    try:
        return {
            "Deepseek-V3 (推荐)": {
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

# ================= 初始化 Supabase =================
@st.cache_resource
def init_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ 无法连接到 Supabase 数据库: {e}")
        return None

# ================= 3. 核心功能函数 =================
def save_feedback(data_dict):
    supabase = init_supabase()
    if not supabase: return False
    
    now = datetime.datetime.now()
    data_dict["date"] = now.strftime("%Y-%m-%d")
    data_dict["time"] = now.strftime("%H:%M:%S")
    
    try:
        supabase.table("feedback").insert(data_dict).execute()
        return True
    except Exception as e:
        st.error(f"写入云数据库失败: {e}")
        return False

@st.cache_data
def load_all_corpora():
    all_samples = []
    
    def safe_get(val, default="未知"):
        if pd.isna(val): return default
        s = str(val).strip()
        return s if s and s.lower() != 'nan' else default

    multi_exp_dict = {}
    multi_exp_path = "./dataset/multi_explanation.csv"
    if os.path.exists(multi_exp_path):
        try:
            df_multi = pd.read_csv(multi_exp_path)
            for _, row in df_multi.iterrows():
                m_sent = safe_get(row.get('Sentence'), "")
                m_exp = safe_get(row.get('Alternative_Analysis'), "")
                if not m_exp or m_exp == "未知": 
                    m_exp = safe_get(row.get('Explanation'), "")
                if m_sent and m_exp and m_exp != "未知":
                    if m_sent not in multi_exp_dict:
                        multi_exp_dict[m_sent] = []
                    multi_exp_dict[m_sent].append(m_exp)
        except Exception:
            pass 

    for book_name, file_path in CORPUS_CONFIG.items():
        if not os.path.exists(file_path):
            continue 
            
        try:
            if file_path.endswith('.xml'):
                tree = ET.parse(file_path)
                root = tree.getroot()
                for node in root.findall('metaphor'):
                    analysis_node = node.find('Analysis')
                    sent_text = node.find('Sentence').text.strip() if node.find('Sentence') is not None else ""
                    all_samples.append({
                        "Book": book_name,
                        "Sentence": sent_text,
                        "Label": int(node.find('Label').text) if node.find('Label') is not None else 0,
                        "Analysis": analysis_node.text.strip() if analysis_node is not None else "暂无解析",
                        "Syntax_Type": "未知", "Cognitive_Type": "未知", 
                        "Conventionality": "未知", "Form_Features": "未知",
                        "Syntax_Analysis": "暂无解析", "Cognitive_Analysis": "暂无解析",
                        "Conventionality_Analysis": "暂无解析", "Form_Analysis": "暂无解析",
                        "Other_Explanations": multi_exp_dict.get(sent_text, []) 
                    })
            elif file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                for _, row in df.iterrows():
                    sent_text = safe_get(row.get('Sentence', ''), "")
                    all_samples.append({
                        "Book": book_name,
                        "Sentence": sent_text,
                        "Label": int(row.get('Pred_Label', row.get('Label', 0))), 
                        "Analysis": safe_get(row.get('Analysis', ''), "暂无解析"),
                        "Syntax_Type": safe_get(row.get('syntax_type'), '未知'),
                        "Syntax_Analysis": safe_get(row.get('syntax_analysis'), '暂无解析'),
                        "Cognitive_Type": safe_get(row.get('cognitive_type'), '未知'),
                        "Cognitive_Analysis": safe_get(row.get('cognitive_analysis'), '暂无解析'),
                        "Conventionality": safe_get(row.get('conventionality'), '未知'),
                        "Conventionality_Analysis": safe_get(row.get('conventionality_analysis'), '暂无解析'),
                        "Form_Features": safe_get(row.get('form_features'), '未知'),
                        "Form_Analysis": safe_get(row.get('form_analysis'), '暂无解析'),
                        "Other_Explanations": multi_exp_dict.get(sent_text, []) 
                    })
        except Exception as e:
            st.error(f"加载 {book_name} 语料库 ({file_path}) 时出错: {e}")
            
    return all_samples

def get_similar_metaphors(target_analysis, target_sentence, samples_pool, top_k=3):
    metaphor_pool = [s for s in samples_pool if s['Label'] == 1 and s['Sentence'] != target_sentence]
    if not metaphor_pool or not target_analysis: return []
    stop_chars = set("的了和是就在也不有与为以对于这那，。！？：；“”‘’（）《》、 \n\t比喻修辞本体喻体")
    target_set = set(target_analysis) - stop_chars
    if not target_set: return metaphor_pool[:top_k] 
    
    scored_items = []
    for s in metaphor_pool:
        compare_set = set(s['Analysis']) - stop_chars
        if not compare_set: continue
        score = len(target_set & compare_set) / len(target_set | compare_set)
        scored_items.append((score, s))
    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_items[:top_k]]

# ================= 4. 侧边栏设计 =================
with st.sidebar:
    st.title("🏛️ 古籍隐喻计算平台")
    st.markdown("基于多智能体架构的明清小说隐喻识别系统。")
    st.divider()
    st.subheader("⚙️ 在线推理模型设置")
    selected_model = st.selectbox("选择底层大模型", list(MODEL_CONFIGS.keys()), index=0)
    use_proxy = st.checkbox("启用海外代理 (针对 ChatGPT)", value=False)
    st.divider()
    total_visits = get_and_update_visit_count()
    st.markdown(f"""
    <div class="visit-counter">
        <span style="font-size: 14px; color: #475569;">👁️ 本站累计访问量</span><br/>
        <span style="font-size: 26px; font-weight: bold; color: #1E3A8A;">{total_visits}</span>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.caption("© 多智能体隐喻在线识别")

# ================= 5. 主页面双 Tab 设计 =================
tab1, tab2 = st.tabs(["🔍 语料检索 (Corpus Explorer)", "🤖 在线识别 (Online Metaphor Recognition)"])

# ----------------- Tab 1: 语料检索 -----------------
with tab1:
    st.header("明清小说隐喻语料库 ")
    samples = load_all_corpora()
    
    if not samples:
        st.warning("⚠️ 找不到任何语料库文件，请检查 CORPUS_CONFIG 中的路径是否正确！")
    else:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search_query = st.text_input("🔍 搜索句子内容（支持关键词）")
        with col2:
            available_books = sorted(list(set(s["Book"] for s in samples)))
            filter_book = st.selectbox("📚 书籍筛选", ["全部"] + available_books)
        with col3:
            filter_label = st.selectbox("🏷️ 基础类型", ["全部", "仅隐喻 (Label 1)", "非隐喻 (Label 0)"])
        
        filter_syntax, filter_cog, filter_conv, filter_form = "全部", "全部", "全部", "全部"
        
        if filter_label in ["全部", "仅隐喻 (Label 1)"]:
            with st.expander("🔬 细粒度特征筛选 (高级搜索)"):
                st.caption("基于多智能体深度判定的特征进行交叉检索：")
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
            
        st.markdown(f"为您检索到 <span style='color:#3B82F6; font-weight:bold; font-size:16px;'>{len(filtered_samples)}</span> 条符合条件的语料。", unsafe_allow_html=True)
        st.divider()

        # ========== 下方渲染卡片的逻辑 ==========
        for s in filtered_samples[:50]:
            tag_class = "tag-metaphor" if s["Label"] == 1 else "tag-normal"
            tag_text = "✨ 隐喻 (Metaphor)" if s["Label"] == 1 else "📝 非隐喻 (Literal)"
            
            badges_html = ""
            details_html = ""
            if s["Label"] == 1:
                badges_html = f"""<div style="margin-top: 12px;">
<span class="attr-badge">📌 句法: {s.get('Syntax_Type', '未知')}</span>
<span class="attr-badge">🧠 认知: {s.get('Cognitive_Type', '未知')}</span>
<span class="attr-badge">⏳ 规约: {s.get('Conventionality', '未知')}</span>
<span class="attr-badge">🎭 特征: {s.get('Form_Features', '未知')}</span>
</div>"""

                details_html = f"""<div style="margin-top: 15px; padding-top: 15px; border-top: 1px dashed #CBD5E1;">
<b style="color:#4C1D95;">🧬 Agent 4 细分类依据：</b><br/>
<ul style="margin-top: 8px; color: #475569; font-size: 13.5px; padding-left: 20px; line-height: 1.7;">
<li style="margin-bottom: 6px;"><b>句法：</b>{s.get('Syntax_Analysis', '暂无解析')}</li>
<li style="margin-bottom: 6px;"><b>认知：</b>{s.get('Cognitive_Analysis', '暂无解析')}</li>
<li style="margin-bottom: 6px;"><b>规约：</b>{s.get('Conventionality_Analysis', '暂无解析')}</li>
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
                    
                    formatted_analysis = f"""<div style="margin-top: 10px;">
<div class="agent-box agent1">
<b style="color: #1E3A8A; font-size: 14.5px;">🕵️‍♂️ Agent 1 (语义)：</b> {p1}
</div>
<div class="agent-box agent2">
<b style="color: #9A3412; font-size: 14.5px;">⚖️ Agent 2 (推理)：</b> {p2}
</div>
<div class="agent-box agent3" style="margin-bottom:0;">
<b style="color: #065F46; font-size: 14.5px;">👨‍⚖️ Agent 3 (裁判)：</b> {p3}
</div>
</div>"""
                except Exception:
                    pass 

            other_exp_html = ""
            if s.get("Other_Explanations"):
                items_html = "".join([f"<li style='margin-bottom: 8px;'>{exp}</li>" for exp in s["Other_Explanations"]])
                other_exp_html = f"""<div style="margin-top: 18px; background-color: #FEF3C7; padding: 16px; border-radius: 8px; border-left: 4px solid #F59E0B;">
<b style="color: #B45309; font-size: 14.5px;">💡 其他专家/视角的解析补充：</b><br/>
<ul style="margin-top: 10px; color: #92400E; font-size: 14px; padding-left: 20px; line-height: 1.6; margin-bottom: 0;">
{items_html}
</ul>
</div>"""
            
            st.markdown(f"""<div class="card">
<span class="{tag_class}">{tag_text}</span>
<span style="font-size: 12px; color: #64748B;">来源: 《{s['Book']}》</span>
{badges_html}
<div class="sentence">{s['Sentence']}</div>
<details>
<summary style="cursor: pointer; color: #2563EB; font-size: 14.5px; font-weight: 600;">展开查看多维专家解析 ▾</summary>
<div class="analysis-box">
<b style="font-size: 15px; color: #334155;">基础判决逻辑：</b>
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

# ----------------- Tab 2: 在线识别 -----------------
with tab2:
    st.header("多智能体隐喻在线识别")
    st.markdown("输入任意明清小说语句，观察 **语义提取 ➔ 考证推理 ➔ 逻辑审核 ➔ 多维特征分类** 的全过程。")
    
    col_text, col_book = st.columns([3, 1])
    with col_text:
        test_sentence = st.text_area("输入测试句子：", value="忽听山石之后有一人笑道：“且请留步”", height=100)
    with col_book:
        target_book = st.text_input("目标书籍 (选填)：", placeholder="例如：红楼梦")
        
    run_btn = st.button("🚀 运行多智能体隐喻分析 (Run Analysis)", type="primary")
    
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
                    <b style="color: #1E3A8A; font-size: 15px;">🎯 提纯结果：</b><br/><br/>
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
                    <b style="color: #9A3412; font-size: 15px;">🔍 推理报告：</b><br/><br/>
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
                    <b style="color: #065F46; font-size: 15px;">📌 最终定谳：</b><br/><br/>
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
                st.markdown('<div class="agent-box agent4"><b style="color: #5B21B6; font-size: 15px;">📊 细粒度分类报告：</b><br/><br/>', unsafe_allow_html=True)
                
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
                        <div style="background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #8B5CF6; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
                            <b style="color: #4C1D95; font-size: 14.5px;">{task['task_name']}</b><br/><br/>
                            <span style="font-size: 13.5px;"><b>归类：</b> <span style="color: #D946EF; font-weight: bold; background-color: #FDF4FF; padding: 2px 6px; border-radius: 4px;">{res_json.get(task['keys'][0], '未知')}</span></span><br/><br/>
                            <span style="font-size: 13px; color: #475569; line-height: 1.6;"><b>解析：</b> {res_json.get(task['keys'][1], '')}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"分类任务 {task['task_name']} 失败: {e}")
                        
                st.markdown('</div>', unsafe_allow_html=True)
                status4.update(label="✅ Agent 4 (多维度分类) 完成！", state="complete", expanded=True)

            st.subheader("💡 基于当前分析逻辑的关联推荐")
            st.caption("将 **Agent 2 的深度考证结果** 与您的 **本地语料库** 进行特征碰撞，为您找到以下最相似的过往案例：")
            samples = load_all_corpora()
            if samples:
                sim_matches = get_similar_metaphors(reason2, test_sentence, samples, top_k=3)
                if sim_matches:
                    for sim in sim_matches:
                        st.markdown(f"""
                        <div class="card" style="padding: 20px; margin-top: 10px;">
                            <span class="tag-metaphor" style="float:right; margin:0;">关联度极高</span>
                            <div style="font-size: 15px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px;">《{sim['Book']}》</div>
                            <div class="sentence" style="font-size: 18px; margin: 10px 0;">{sim['Sentence']}</div>
                            <div class="analysis-box" style="margin-top: 10px; padding: 12px;"><b>库内专家解析:</b><br/>{sim['Analysis']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("当前本地语料库中暂无相似度极高的案例。")
