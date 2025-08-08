import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path

# 解决模块导入问题
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# 导入本地模块
import backtest.dv01_calc as dv01_calc  # 确保 dv01_calc.py 在同一目录

st.set_page_config(page_title="ETF对冲推荐工具", layout="wide")

st.title("📈 富国政金债ETF 对冲策略辅助工具")

# 数据读取 - 使用相对路径更安全
data_path = Path(__file__).parent.parent / "data" / "etf_futures_merged.csv"
df = pd.read_csv(data_path, parse_dates=["date"])

# 计算对冲指标
result_df = dv01_calc.calculate_dv01_metrics(df)

# 图表展示
st.subheader("ETF 与 国债期货 收盘价")
st.line_chart(result_df.set_index("date")[["close_etf", "close_fut"]])

st.subheader("推荐对冲仓位（每份ETF）")
st.line_chart(result_df.set_index("date")[["hedge_ratio"]])

st.dataframe(result_df.tail(10))