import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# ====== 配置区 ======
SERVICE_ACCOUNT_FILE = "service_account.json"   # 你的json文件名
# 注意：这里我们改用 ID 连接，所以 SPREADSHEET_NAME 变量不再需要了，但保留着也不影响
SHEET_ID = "15K5LDlpYZtIUoEFfsGMCSZEjgJ7J49F7GlgWThhd2QU"  # 你的 Google Sheet ID
WORKSHEET_NAME = "Sheet1"                       # 工作表名字

# 定义列名（顺序必须固定，与Google Sheet一致）
COLUMNS = [
    "序号", "姓名", "性别", "年龄（岁）", "工单号", "工单费用", "工种",
    "是否参加面试", "初试时间", "复试时间", "押金（元）", "备注"
]

# ---- 简单账号系统 ----
USERS = {
    "admin": "1234",
    "user1": "1111"
}

# ====== Google Sheets 连接函数 (已修复：使用 ID 连接) ======
@st.cache_resource
def get_worksheet():
    """连接到 Google Sheet 并返回工作表对象"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # 1. 认证
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 2. 【重点修改】直接通过 ID 锁定表格，解决 200 错误
        sh = client.open_by_key(SHEET_ID)
        
        # 3. 打开具体的工作表
        return sh.worksheet(WORKSHEET_NAME)
    except Exception as e:
        raise Exception(f"连接 Google Sheet 失败: {e}。请确认 JSON 文件存在且已分享给机器人邮箱。")

def read_data():
    """读取数据并返回 DataFrame"""
    try:
        ws = get_worksheet()
        values = ws.get_all_values()
        
        # 如果是空表，返回空 DataFrame
        if not values:
            return pd.DataFrame(columns=COLUMNS)
            
        header = values[0]
        rows = values[1:]
        
        # 如果表头不对，强行按我们定义的 COLUMNS 读取
        if header != COLUMNS:
            df = pd.DataFrame(rows, columns=header)
            # 补齐缺失列
            for c in COLUMNS:
                if c not in df.columns:
                    df[c] = ""
            return df[COLUMNS]
            
        return pd.DataFrame(rows, columns=COLUMNS)
    except Exception as e:
        st.error(f"读取数据失败: {e}")
        return pd.DataFrame(columns=COLUMNS)

def append_record(row_data):
    """【安全模式】直接追加一行数据到 Google Sheet 末尾"""
    ws = get_worksheet()
    ws.append_row(row_data)

def overwrite_sheet(df):
    """【全量覆盖】将 DataFrame 数据完整写回（用于批量编辑）"""
    ws = get_worksheet()
    ws.clear() # 先清空
    # 将 DataFrame 转为列表，并加上表头
    data = [COLUMNS] + df.fillna("").astype(str).values.tolist()
    ws.update(data)

def normalize_types(df):
    """统一数据类型，方便前端显示"""
    # 强制将这些列转为数字，无法转的变NaN
    for col in ["序号", "年龄（岁）", "工单费用", "押金（元）"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# ====== 登录界面 ======
def login_page():
    st.title("🔐 登录 Login")
    with st.form("login_form"):
        u = st.text_input("账号 (admin)")
        p = st.text_input("密码 (1234)", type="password")
        if st.form_submit_button("登录"):
            if u in USERS and USERS[u] == p:
                st.session_state["user"] = u
                st.rerun()
            else:
                st.error("账号或密码错误")

def logout_btn():
    with st.sidebar:
        st.write(f"当前用户: **{st.session_state['user']}**")
        if st.button("退出登录 (Logout)"):
            st.session_state["user"] = None
            st.rerun()

# ====== 主程序 ======
if __name__ == "__main__":
    st.set_page_config(page_title="Labour Tracking App", layout="wide")

    # 1. 检查登录状态
    if "user" not in st.session_state:
        st.session_state["user"] = None

    if st.session_state["user"] is None:
        login_page()
        st.stop() # 停止执行后续代码

    # 2. 已登录界面
    logout_btn()
    st.title("📋 工人信息追踪系统 (Tracking System)")

    # 读取最新数据
    df_current = read_data()
    df_current = normalize_types(df_current)

    # --- 模块 A: 新增记录 (使用 append_row) ---
    st.subheader("➕ 新增记录")
    with st.form("add_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        
        # 自动计算下一个序号
        next_serial = 1
        if not df_current.empty and df_current["序号"].notna().any():
            try:
                next_serial = int(df_current["序号"].max()) + 1
            except:
                pass

        with c1:
            serial = st.number_input("序号", min_value=1, step=1, value=next_serial)
            name = st.text_input("姓名")
            gender = st.selectbox("性别", ["男", "女", "其他", ""])
        with c2:
            age = st.number_input("年龄（岁）", min_value=0, step=1, value=30)
            order_no = st.text_input("工单号")
            fee = st.number_input("工单费用", min_value=0.0, step=100.0)
        with c3:
            job_type = st.text_input("工种")
            interview = st.selectbox("是否参加面试", ["是", "否", ""])
            first_time = st.text_input("初试时间", placeholder="2025-12-14 10:00")
        with c4:
            second_time = st.text_input("复试时间", placeholder="2025-12-15 10:00")
            deposit = st.number_input("押金（元）", min_value=0.0, step=100.0)
            remark = st.text_input("备注")

        submitted = st.form_submit_button("提交保存 (Save)")

        if submitted:
            # 构造要追加的列表，顺序必须严格对应 COLUMNS
            new_record_list = [
                serial, name, gender, age, order_no, fee, job_type, 
                interview, first_time, second_time, deposit, remark
            ]
            
            try:
                append_record(new_record_list)
                st.success(f"✅ 成功添加：{name}")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"保存失败: {e}")

    # --- 模块 B: 数据展示与批量编辑 ---
    st.divider()
    st.subheader("📝 数据列表与编辑")

    # 使用 data_editor 允许直接在网页表格里修改
    # 已修复：删除了过时的 use_container_width 参数警告
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic", # 允许在表格末尾添加行
        hide_index=True
    )

    # 保存修改按钮
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("💾 保存所有修改 (Save All Changes)", type="primary"):
            try:
                # 再次清洗数据类型
                final_df = normalize_types(edited_df)
                # 按序号排序
                if "序号" in final_df.columns and not final_df.empty:
                    final_df = final_df.sort_values("序号")
                
                # 全量写回
                overwrite_sheet(final_df)
                st.success("✅ 所有修改已同步到 Google Sheet！")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"同步失败: {e}")

    with col_btn2:
        if st.button("🔄 刷新数据"):
            st.rerun()
