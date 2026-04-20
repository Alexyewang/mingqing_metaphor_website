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

# UI 配置
st.set_page_config(page_title="明清小说隐喻语料库与多智能体隐喻在线识别", layout="wide", page_icon="📚")

st.markdown("""
<style>
    .main {background-color: #F9FAFB;}
    .card {
        background-color: #ffffff; padding: 20px; border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 16px;
        border: 1px solid #E5E7EB; border-left: 5px solid #1E3A8A;
    }
    .tag-metaphor {
        background-color: #DEF7EC; color: #046C4E; padding: 4px 10px;
        border-radius: 999px; font-size: 12px; font-weight: bold; margin-right: 10px;
    }
    .tag-normal {
        background-color: #F3F4F6; color: #4B5563; padding: 4px 10px;
        border-radius: 999px; font-size: 12px; font-weight: bold; margin-right: 10px;
    }
    .sentence {font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 10px; font-family: 'SimSun', serif;}
    .analysis-box {
        background-color: #F8FAFC; padding: 12px; border-radius: 6px;
        font-size: 14px; color: #475569; border-left: 3px solid #94A3B8; margin-top: 10px;
    }
    .agent-box {
        padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #E2E8F0;
    }
    .agent1 {background-color: #EFF6FF; border-left: 4px solid #3B82F6;}
    .agent2 {background-color: #FFF7ED; border-left: 4px solid #F97316;}
    .agent3 {background-color: #ECFDF5; border-left: 4px solid #10B981;}
</style>
""", unsafe_allow_html=True)

# 访问量统计
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

# 模型与数据库配置
def get_model_configs():
    try:
        return {
            "Deepseek-V3.2": {
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
    "红楼梦": "./dataset/500.xml",         
    "西游记": "./dataset/xiyouji.csv",      
    "水浒传": "./dataset/shuihuzhuan.csv",  
    "三国演义": "./dataset/sanguo.csv",      
    "金瓶梅":"./dataset/jinpingmei.csv",
    "儒林外史": "./dataset/rulinwaishi.csv",
}

# 初始化 Supabase
@st.cache_resource
def init_supabase() -> Client:
    """初始化并缓存 Supabase 客户端，防止重复连接"""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ 无法连接到 Supabase 数据库。请检查 Secrets 里的配置: {e}")
        return None

# 云端存储
def save_feedback(book, sentence, orig_label, orig_analysis, new_label, new_analysis):
    """将反馈数据安全地插入到 Supabase 云数据库中"""
    supabase = init_supabase()
    if not supabase:
        return False
        
    now = datetime.datetime.now()
    
    # 构建要插入的数据字典 (键名需与 Supabase 表的列名完全一致)
    data = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "book": book,
        "sentence": sentence,
        "original_label": int(orig_label),
        "original_analysis": orig_analysis,
        "suggested_label": int(new_label),
        "suggested_analysis": new_analysis
    }
    
    try:
        supabase.table("feedback").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"写入云数据库失败: {e}")
        return False

@st.cache_data
def load_all_corpora():
    all_samples = []
    for book_name, file_path in CORPUS_CONFIG.items():
        if not os.path.exists(file_path):
            continue 
            
        try:
            if file_path.endswith('.xml'):
                tree = ET.parse(file_path)
                root = tree.getroot()
                for node in root.findall('metaphor'):
                    analysis_node = node.find('Analysis')
                    all_samples.append({
                        "Book": book_name,
                        "Sentence": node.find('Sentence').text.strip() if node.find('Sentence') is not None else "",
                        "Label": int(node.find('Label').text) if node.find('Label') is not None else 0,
                        "Analysis": analysis_node.text.strip() if analysis_node is not None else "暂无解析"
                    })
            elif file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                for _, row in df.iterrows():
                    all_samples.append({
                        "Book": book_name,
                        "Sentence": str(row.get('Sentence', '')).strip(),
                        "Label": int(row.get('Label', 0)),
                        "Analysis": str(row.get('Analysis', '暂无解析')).strip()
                    })
        except Exception as e:
            st.error(f"加载 {book_name} 语料库 ({file_path}) 时出错: {e}")
            
    return all_samples

def get_similar_metaphors(target_analysis, target_sentence, samples_pool, top_k=3):
    metaphor_pool = [s for s in samples_pool if s['Label'] == 1 and s['Sentence'] != target_sentence]
    if not metaphor_pool or not target_analysis:
        return []
    
    stop_chars = set("的了和是就在也不有与为以对于这那，。！？：；“”‘’（）《》、 \n\t比喻修辞本体喻体")
    target_set = set(target_analysis) - stop_chars
    if not target_set: return metaphor_pool[:top_k] 
    
    scored_items = []
    for s in metaphor_pool:
        compare_set = set(s['Analysis']) - stop_chars
        if not compare_set:
            continue
        score = len(target_set & compare_set) / len(target_set | compare_set)
        scored_items.append((score, s))
        
    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_items[:top_k]]

def merge_debug_to_corpus():
    debug_path = "./dataset/debug.csv"
    if not os.path.exists(debug_path):
        st.sidebar.error("⚠️ 未找到 ./dataset/debug.csv 文件。")
        return
        
    try:
        df_debug = pd.read_csv(debug_path)
        required_cols = {'Book', 'Sentence', 'Suggested_Label', 'Suggested_Analysis'}
        if not required_cols.issubset(df_debug.columns):
            st.sidebar.error(f"debug.csv 缺少必要的列！请确保包含: {required_cols}")
            return
            
        success_count = 0
        for book_name, group in df_debug.groupby('Book'):
            if book_name not in CORPUS_CONFIG:
                st.sidebar.warning(f"未知书籍【{book_name}】，跳过合并。")
                continue
                
            target_file = CORPUS_CONFIG[book_name]
            
            if target_file.endswith('.csv'):
                df_target = pd.read_csv(target_file) if os.path.exists(target_file) else pd.DataFrame(columns=['Sentence', 'Label', 'Analysis'])
                for _, row in group.iterrows():
                    match_idx = df_target.index[df_target['Sentence'] == row['Sentence']].tolist()
                    if match_idx:
                        df_target.loc[match_idx[0], 'Label'] = int(row['Suggested_Label'])
                        df_target.loc[match_idx[0], 'Analysis'] = str(row['Suggested_Analysis'])
                    else:
                        new_row = pd.DataFrame([{'Sentence': row['Sentence'], 'Label': int(row['Suggested_Label']), 'Analysis': str(row['Suggested_Analysis'])}])
                        df_target = pd.concat([df_target, new_row], ignore_index=True)
                df_target.to_csv(target_file, index=False, encoding='utf-8-sig')
                success_count += len(group)
                
            elif target_file.endswith('.xml'):
                if not os.path.exists(target_file):
                    root = ET.Element("dataset")
                    tree = ET.ElementTree(root)
                else:
                    tree = ET.parse(target_file)
                    root = tree.getroot()
                    
                for _, row in group.iterrows():
                    found = False
                    for node in root.findall('metaphor'):
                        sent_node = node.find('Sentence')
                        if sent_node is not None and sent_node.text.strip() == row['Sentence']:
                            node.find('Label').text = str(int(row['Suggested_Label']))
                            ans_node = node.find('Analysis')
                            if ans_node is not None: ans_node.text = str(row['Suggested_Analysis'])
                            else: ET.SubElement(node, 'Analysis').text = str(row['Suggested_Analysis'])
                            found = True
                            break
                    if not found:
                        new_meta = ET.SubElement(root, 'metaphor')
                        ET.SubElement(new_meta, 'Sentence').text = row['Sentence']
                        ET.SubElement(new_meta, 'Label').text = str(int(row['Suggested_Label']))
                        ET.SubElement(new_meta, 'Analysis').text = str(row['Suggested_Analysis'])
                tree.write(target_file, encoding='utf-8', xml_declaration=True)
                success_count += len(group)

        backup_name = f"./dataset/debug_processed_{int(time.time())}.csv"
        os.rename(debug_path, backup_name)
        st.sidebar.success(f"合并成功！更新了 {success_count} 条语料。已将 debug.csv 备份为 {backup_name.split('/')[-1]}")
        load_all_corpora.clear()
    except Exception as e:
        st.sidebar.error(f"合并过程中发生错误: {e}")

# ================= 4. 侧边栏设计 =================
with st.sidebar:
    st.title("🏛️ 古籍隐喻计算平台")
    st.markdown("基于多智能体架构的明清小说隐喻识别系统。")
    st.divider()
    st.subheader("⚙️ 在线推理模型设置")
    selected_model = st.selectbox("选择底层大模型", list(MODEL_CONFIGS.keys()), index=2)
    use_proxy = st.checkbox("启用海外代理 (针对 ChatGPT)", value=False)
    st.divider()
    total_visits = get_and_update_visit_count()
    st.markdown(f"""
    <div style="background-color: #F8FAFC; padding: 10px; border-radius: 6px; text-align: center; border: 1px dashed #CBD5E1;">
        <span style="font-size: 14px; color: #475569;">👁️ 本站累计访问量</span><br/>
        <span style="font-size: 24px; font-weight: bold; color: #1E3A8A;">{total_visits}</span>
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
            search_query = st.text_input("搜索句子内容（可以使用关键词搜索）")
        with col2:
            available_books = sorted(list(set(s["Book"] for s in samples)))
            filter_book = st.selectbox("书籍筛选", ["全部"] + available_books)
        with col3:
            filter_label = st.selectbox("类型筛选", ["全部", "仅隐喻 (Label 1)", "非隐喻 (Label 0)"])
        
        filtered_samples = samples
        
        if search_query:
            filtered_samples = [s for s in filtered_samples if search_query in s["Sentence"]]
            
        if filter_book != "全部":
            filtered_samples = [s for s in filtered_samples if s["Book"] == filter_book]
            
        if filter_label == "仅隐喻 (Label 1)":
            filtered_samples = [s for s in filtered_samples if s["Label"] == 1]
        elif filter_label == "非隐喻 (Label 0)":
            filtered_samples = [s for s in filtered_samples if s["Label"] == 0]
            
        st.caption(f"为您检索到 **{len(filtered_samples)}** 条高质量语料。")
        
        for s in filtered_samples[:50]:
            tag_class = "tag-metaphor" if s["Label"] == 1 else "tag-normal"
            tag_text = "✨ 隐喻 (Metaphor)" if s["Label"] == 1 else "📝 非隐喻 (Literal)"
            
            st.markdown(f"""
            <div class="card">
                <span class="{tag_class}">{tag_text}</span>
                <span style="font-size: 12px; color: #64748B;">来源: 《{s['Book']}》</span>
                <div class="sentence">{s['Sentence']}</div>
                <details>
                    <summary style="cursor: pointer; color: #3B82F6; font-size: 14px; font-weight: 500;">展开查看专家解析详情</summary>
                    <div class="analysis-box">{s['Analysis']}</div>
                </details>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("✍️ 发现错误？提交更正意见"):
                with st.form(key=f"feedback_form_{s}"):
                    new_label = st.radio("正确的 Label 应该是：", options=[0, 1], index=s['Label'], horizontal=True)
                    new_analysis = st.text_area("您认为更合理的解析：", value=s['Analysis'])
                    submit_btn = st.form_submit_button("安全提交至云端")
                    
                    if submit_btn:
                        is_success = save_feedback(s['Book'], s['Sentence'], s['Label'], s['Analysis'], new_label, new_analysis)
                        if is_success:
                            st.success("✅ 提交成功！您的意见已安全送达 Supabase 云数据库。")
            
            st.write("") 

# ----------------- Tab 2: 算法靶场 -----------------
with tab2:
    st.header("多智能体隐喻在线识别")
    st.markdown("输入任意明清小说语句，观察 **语义提取 (Agent 1) ➔ 考证推理 (Agent 2) ➔ 逻辑审核 (Agent 3)** 的推理全过程。")
    
    col_text, col_book = st.columns([3, 1])
    with col_text:
        test_sentence = st.text_area("输入测试句子：", value="忽听山石之后有一人笑道：“且请留步”", height=100)
    with col_book:
        target_book = st.text_input("目标书籍 (选填)：", placeholder="例如：红楼梦")
        
    run_btn = st.button("🚀 运行交叉反射分析 (Run Analysis)", type="primary")
    
    if run_btn:
        book_context = target_book.strip() if target_book.strip() else "明清小说"
        
        config = MODEL_CONFIGS[selected_model]
        http_client = httpx.Client(proxy="http://127.0.0.1:7890") if use_proxy else None
        client = OpenAI(api_key=config["env_key"], base_url=config["base_url"], http_client=http_client)
        
        st.divider()
        
        with st.status("🕵️‍♂️ Agent 1 (语义提纯) 正在分析表层结构...", expanded=True) as status1:
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
                    <b>🎯 提纯结果：</b><br/>
                    <b>表层语义：</b> {analysis1} <br/>
                    <b>可疑修辞词：</b> {words1}
                </div>
                """, unsafe_allow_html=True)
                status1.update(label="✅ Agent 1 (语义提纯) 完成！", state="complete", expanded=False)
            except Exception as e:
                st.error(f"Agent 1 失败: {e}")
                st.stop()

        with st.status("⚖️ Agent 2 (跨域推理) 正在进行深度隐喻考证...", expanded=True) as status2:
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
                    <b>🔍 推理报告：</b><br/>
                    <b>逻辑分析：</b> {reason2} <br/>
                    <b>初步标签：</b> {"隐喻 (1)" if label2 == 1 else "非隐喻 (0)"}
                </div>
                """, unsafe_allow_html=True)
                status2.update(label="✅ Agent 2 (跨域推理) 完成！", state="complete", expanded=False)
            except Exception as e:
                st.error(f"Agent 2 失败: {e}")
                st.stop()

        with st.status("👨‍⚖️ Agent 3 (逻辑裁判) 正在生成最终决议...", expanded=True) as status3:
            prompt3 = f"""检查【报告】的分析和得到的结论是否矛盾。如果矛盾则根据【报告】的分析修正结果。如果句子中含有比喻输出label 1，否则输出0。报告: "{reason2}"
            请严格返回JSON格式：{{"label": 1或0, "analysis": "最终判决理由"}}"""
            
            try:
                res3 = client.chat.completions.create(model=config["model_name"], messages=[{"role": "user", "content": prompt3}], temperature=0, response_format={'type': 'json_object'})
                data3 = json.loads(res3.choices[0].message.content)
                final_label = int(data3.get("label", 0))
                final_reason = data3.get("analysis", "")
                
                st.markdown(f"""
                <div class="agent-box agent3">
                    <b>📌 最终定谳：</b><br/>
                    <b>终审逻辑：</b> {final_reason} <br/>
                    <h3 style="color: {'#10B981' if final_label==1 else '#64748B'}; margin-top: 10px;">
                        最终结论: {"🏷️ 这是一个隐喻句 (Label: 1)" if final_label == 1 else "📝 这是一个字面义句 (Label: 0)"}
                    </h3>
                </div>
                """, unsafe_allow_html=True)
                status3.update(label="✅ Agent 3 (逻辑裁判) 完成！", state="complete", expanded=True)
            except Exception as e:
                st.error(f"Agent 3 失败: {e}")
                
        if final_label == 1:
            st.subheader("💡 基于当前分析逻辑的关联推荐")
            st.caption("AI 自动将 **Agent 2 的深度考证结果** 与您的 **本地语料库** 进行特征碰撞，为您找到以下最相似的过往案例：")
            samples = load_all_corpora()
            if samples:
                sim_matches = get_similar_metaphors(reason2, test_sentence, samples, top_k=3)
                if sim_matches:
                    for sim in sim_matches:
                        st.markdown(f"""
                        <div class="sim-card">
                            <span class="tag-metaphor" style="float:right;">关联度极高</span>
                            <div style="font-size: 16px; font-weight: bold; color: #1E293B; margin-bottom: 5px;">《{sim['Book']}》</div>
                            <div style="font-size: 16px; font-family: 'SimSun', serif; margin-bottom: 8px;">{sim['Sentence']}</div>
                            <div style="font-size: 13px; color: #475569;"><b>库内专家解析:</b> {sim['Analysis']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("当前本地语料库中暂无相似度极高的案例。")
