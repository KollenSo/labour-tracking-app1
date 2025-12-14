import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# ====== 配置区 ======
# 如果本地运行，请确保有 service_account.json
# 如果在 Streamlit Cloud 运行，请确保配置了 Secrets
SERVICE_ACCOUNT_FILE = "service_account.json"
SHEET_ID = "15K5LDlpYZtIUoEFfsGMCSZEjgJ7J49F7GlgWThhd2QU"  # 你的 Google Sheet ID
WORKSHEET_NAME = "Sheet1"                       # 工作表名字

# 定义列名
COLUMNS = [
    "序号", "姓名", "性别", "年龄（岁）", "工单号", "工单费用", "工种",
    "是否参加面试", "初试时间", "复试时间", "押金（元）", "备注"
]

# ---- 简单账号系统 ----
USERS = {
    "admin": "1234",
    "user1": "1111"
}

# ====== Google Sheets 连接函数 (双模：支持本地文件 & 云端 Secrets) ======
@st.cache_resource
def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        # 优先尝试从 Secrets 读取 (云端模式)
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=scopes
            )
        else:
            # 否则尝试从本地文件读取 (本地模式)
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
            
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        # 直接获取第一张表
        return sh.get_worksheet(0)
        
    except FileNotFoundError:
        raise Exception("找不到 service_account.json 文件，也未配置 Secrets。请检查部署设置。")
    except Exception as e:
        raise Exception(f"连接失败: {e}")

# ... (剩下的代码不用变，和之前一样) ...

def read_data():
    try:
        ws = get_worksheet()
        values = ws.get_all_values()
        if not values: return pd.DataFrame(columns=COLUMNS)
        header = values[0]
        rows = values[1:]
        if header != COLUMNS:
            df = pd.DataFrame(rows, columns=header)
            for c in COLUMNS:
                if c not in df.columns: df[c] = ""
            return df[COLUMNS]
        return pd.DataFrame(rows, columns=COLUMNS)
    except Exception as e:
        st.error(f"读取数据失败: {e}")
        return pd.DataFrame(columns=COLUMNS)

def append_record(row_data):
    ws = get_worksheet()
    ws.append_row(row_data)

def overwrite_sheet(df):
    ws = get_worksheet()
    ws.clear()
    data = [COLUMNS] + df.fillna("").astype(str).values.tolist()
    ws.update(data)

def normalize_types(df):
    for col in ["序号", "年龄（岁）", "工单费用", "押金（元）"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# ====== 主程序 ======
if __name__ == "__main__":
    st.set_page_config(page_title="Labour Tracking App", layout="wide")

    if "user" not in st.session_state: st.session_state["user"] = None
    if st.session_state["user"] is None:
        st.title("🔐 登录 Login")
        with st.form("login_form"):
            u = st.text_input("账号 (admin)")
            p = st.text_input("密码 (1234)", type="password")
            if st.form_submit_button("登录"):
                if u in USERS and USERS[u] == p:
                    st.session_state["user"] = u
                    st.rerun()
                else: st.error("账号或密码错误")
        st.stop()

    with st.sidebar:
        st.write(f"当前用户: **{st.session_state['user']}**")
        if st.button("退出登录"):
            st.session_state["user"] = None
            st.rerun()

    st.title("📋 工人信息追踪系统 (Tracking System)")
    df_current = normalize_types(read_data())

    st.subheader("➕ 新增记录")
    with st.form("add_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        next_serial = 1
        if not df_current.empty and df_current["序号"].notna().any():
            try: next_serial = int(df_current["序号"].max()) + 1
            except: pass

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

        if st.form_submit_button("提交保存 (Save)"):
            try:
                append_record([serial, name, gender, age, order_no, fee, job_type, interview, first_time, second_time, deposit, remark])
                st.success(f"✅ 成功添加：{name}")
                time.sleep(1)
                st.rerun()
            except Exception as e: st.error(f"保存失败: {e}")

    st.divider()
    st.subheader("📝 数据列表与编辑")
    edited_df = st.data_editor(df_current, num_rows="dynamic", hide_index=True)
    
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("💾 保存所有修改", type="primary"):
            try:
                final_df = normalize_types(edited_df)
                if "序号" in final_df.columns and not final_df.empty:
                    final_df = final_df.sort_values("序号")
                overwrite_sheet(final_df)
                st.success("✅ 已同步！")
                time.sleep(1)
                st.rerun()
            except Exception as e: st.error(f"同步失败: {e}")
    with col_btn2:
        if st.button("🔄 刷新"): st.rerun()
