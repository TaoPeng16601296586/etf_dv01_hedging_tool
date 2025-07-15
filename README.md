
# ETF DV01对冲（以富国中债7-10年政金债ETF为例）

基于 Streamlit 构建的轻量化可视化工具，旨在服务于中国利率债ETF的主动量化做市策略。该工具以富国中债7-10年政金债ETF（511520.SH）为核心研究对象，并使用10年期国债期货（T合约）进行DV01中性对冲建议。

---

## 项目目标

- 实时输入ETF价格、持仓份额，估算组合DV01利率敞口；
- 根据国债期货DV01自动匹配对冲手数；
- 可视化展示ETF走势、推荐对冲结构、净敞口变化；
- 可扩展预测模块（GPT情绪建议、技术指标等）；

---

## 文件夹结构建议

```
etf_dv01_hedging_tool/
├── app/                         # 主程序目录（Streamlit）
│   ├── app.py                   # 主页面入口
│   └── components/              # 子功能模块（如对冲算法、图表组件）
│
├── data/                        # 存储ETF和期货历史数据
│   ├── etf_511520.csv
│   ├── futures_T.csv
│
├── notebooks/                   # Jupyter Notebook用于模型原型验证
│   └── dv01_calculation.ipynb
│
├── scripts/                     # 拉取/清洗数据的脚本（如AkShare）
│   └── fetch_data_akshare.py
│
├── utils/                       # 公共函数模块（DV01计算、预测封装等）
│   └── dv01_calc.py
│
├── requirements.txt             # 项目所需依赖包列表
├── README.md                    # 项目说明文档（本文件）
└── ETF_DV01_Hedging_Tool_项目说明.md   
```

---

## 使用方式（本地运行）

1. 克隆项目：
```bash
git clone https://github.com/yourname/etf_dv01_hedging_tool.git
cd etf_dv01_hedging_tool
```

2. 创建虚拟环境（推荐）并安装依赖：
```bash
python -m venv venv
source venv/bin/activate  # Windows用户使用 venv\Scripts\activate
pip install -r requirements.txt
```

3. 运行主程序：
```bash
streamlit run app/app.py
```

---

## 技术模块简述

| 模块 | 描述 |
|------|------|
| DV01估算 | ETF价格 × 份额 × 久期 × 0.0001，支持自定义输入 |
| 期货DV01 | 默认设置为T合约每手约490元，可调整 |
| 对冲建议 | 自动计算推荐空头手数，展示敞口是否中性 |
| 可视化 | 支持图表（ETF走势、净敞口、预测建议等） |
| 预测模块 | 可对接GPT或技术指标辅助判断走势（可选） |

---

## 后续扩展方向

- Wind / Choice 实时行情接入
- 多ETF组合同时监控
- 添加止盈止损、自动调仓功能
- 对接交易接口实现交易闭环

---


