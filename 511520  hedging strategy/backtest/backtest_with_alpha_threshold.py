# modified backtest function to include DV01 metrics

"""
backtest.py
===============

此脚本实现了一个面向富国中债 7–10 年政金债 ETF 与 30 年国债期货（T2509）
价差策略的回测框架，包含以下改进特性：

1. **DV01 对冲比例嵌入**：调用 ``dv01_calc.calculate_dv01_metrics`` 按日计算
   ETF 的 DV01 和期货的 DV01，并据此生成 ``hedge_ratio``，表示每份 ETF
   需要对冲的期货合约手数。开仓时根据该比例动态确定 ETF 与期货持仓量，
   使组合对利率变化保持中性【263†L1-L8】。

2. **信号对齐与滑动持仓**：将预测列（如 5 日预测）向前平移相应期限，
   获得 ``pred_signal_today``。当 ``pred_signal_today`` 为正时建立或持有
   现券多头/期货空头仓位；当信号非正或触发止盈/止损条件时平仓【263†L1-L8】。

3. **止盈止损机制**：持仓期间动态计算浮动收益率，默认当累计收益率达到
   ±0.5% 时强制平仓锁定结果。用户可调整 ``stop_gain``、``stop_loss``
   参数控制阈值。

4. **交易盈亏记录**：在平仓时将每笔交易的盈亏率保存到 ``realized_pnls``
   列表，便于后续统计胜率和盈亏分布。

5. **完整绩效指标**：回测结束后计算年化收益率、最大回撤、Sharpe 比率、
   Calmar 比率和胜率等指标。

使用方式：

```
import pandas as pd
from backtest import backtest_spread_strategy

# 读取含有日期、开盘价、收盘价、预测列的数据
data = pd.read_csv("your_merged_data.csv")

# 假设预测列为 lars_bayes_pred_5d 表示预测 5 日后的价差变化
result_df, metrics, realized_pnls = backtest_spread_strategy(
    df=data,
    pred_col="lars_bayes_pred_5d",
    open_etf_col="open_etf",
    open_fut_col="open_fut",
    close_etf_col="close_etf",
    close_fut_col="close_fut",
    initial_capital=10000000,
    margin_rate=0.1,
    tick_etf=0.001,
    tick_fut=0.005,
    etf_duration=7.5,
    conversion_factor=0.925,
    stop_gain=0.005,
    stop_loss=0.005
)

# 查看回测结果
print(metrics)
print(result_df.tail())
```
"""

import math
from typing import Tuple, List

import numpy as np
import pandas as pd

from dv01_calc import calculate_dv01_metrics


def backtest_spread_strategy(
    df: pd.DataFrame,
    pred_col: str = "lars_bayes_pred_5d",
    open_etf_col: str = "open_etf",
    open_fut_col: str = "open_fut",
    close_etf_col: str = "close_etf",
    close_fut_col: str = "close_fut",
    initial_capital: float = 10_000_000,
    margin_rate: float = 0.1,
    tick_etf: float = 0.001,
    tick_fut: float = 0.005,
    etf_duration: float = 7.5,
    conversion_factor: float = 0.925,
    stop_gain: float = 0.005,
    stop_loss: float = 0.005,
    alpha_entry_threshold: float = -0.3,
) -> Tuple[pd.DataFrame, dict, List[float]]:
    """基于预测信号和 DV01 对冲的 ETF–期货价差策略回测。

    参数说明：
    - df: 包含行情数据和预测列的数据，必须按日期升序排列，并包含如下列：
      ``date``、``open_etf_col``、``open_fut_col``、``close_etf_col``、``close_fut_col``、以及预测列 ``pred_col``。
    - pred_col: 预测列名称，假定预测的是未来 N 日后的价差变化。
    - open_etf_col/open_fut_col: ETF 和期货的开盘价列名，用于执行交易；
    - close_etf_col/close_fut_col: ETF 和期货的收盘价列名，用于计算 DV01 及评价持仓；
    - initial_capital: 初始账户资金；
    - margin_rate: 期货合约保证金率；
    - tick_etf/tick_fut: ETF 和期货最小跳动单位，用于估算滑点成本；
    - etf_duration: ETF 久期，用于 DV01 计算；
    - conversion_factor: 期货 CTD 债券的转换因子；
    - stop_gain/stop_loss: 止盈止损阈值，表示相对开仓权益的收益率。

    返回值：
    - result_df: 包含每日持仓、交易标记、账户权益等信息的 DataFrame。
    - metrics: 字典形式的绩效指标，包括年化收益率、最大回撤、Sharpe 比率、Calmar 比率和胜率。
    - realized_pnls: 平仓交易的盈亏比列表，用于进一步分析。
    """
    # 复制一份数据并按日期排序
    df = df.copy().reset_index(drop=True)
    if "date" not in df.columns:
        raise ValueError("DataFrame must contain a 'date' column with trading dates.")
    df.sort_values("date", inplace=True)

    # === 1. 按日计算 DV01 对冲比例并合并 ===
    # 使用收盘价来计算 DV01 指标，调用 utils.dv01_calc.calculate_dv01_metrics
    dv01_df = calculate_dv01_metrics(
        df[["date", close_etf_col, close_fut_col]].rename(columns={
            close_etf_col: "close_etf",
            close_fut_col: "close_fut",
        }),
        etf_duration=etf_duration,
        ctd_dv01=0.042,
        conversion_factor=conversion_factor,
    )
    # 合并 hedge_ratio 到主表
    df = df.merge(dv01_df[["date", "hedge_ratio"]], on="date", how="left")

    # === 2. 对齐预测信号：将 pred_col 向前平移 N 行作为当日交易信号 ===
    # 通过计算预测列的有效期数（例如列名以 '5d' 结尾表示预测5日后的变化）
    # 如果无法解析，默认不移位，即预测即时使用
    pred_shift = 0
    # 尝试解析末尾数字
    import re
    match = re.search(r"(\d+)d$", pred_col)
    if match:
        pred_shift = int(match.group(1))
    # 创建用于决策的信号列
    signal_col = "_signal_today"
    if pred_shift > 0:
        df[signal_col] = df[pred_col].shift(-pred_shift)
    else:
        df[signal_col] = df[pred_col]

    # === 3. 初始化账户和交易状态 ===
    base_built = False
    base_etf_units = 0
    base_fut_units = 0
    alpha_etf_units = 0
    alpha_fut_units = 0
    entry_equity_alpha = None

    cash: float = initial_capital  # 账户现金
    capital: float = initial_capital  # 账户总权益
    holding: bool = False  # 是否持仓
    n_etf: float = 0.0  # 当前持有 ETF 份额数
    n_fut: int = 0  # 当前持有期货手数
    entry_equity: float = 0.0  # 开仓时的账户权益
    entry_etf_price: float = 0.0  # 开仓时 ETF 价格
    entry_fut_price: float = 0.0  # 开仓时期货价格
    realized_pnls: List[float] = []  # 每笔交易盈亏率

    # 用于记录每日结果
    records: List[dict] = []

    # === 4. 遍历交易日 ===
    for idx in range(len(df)):
        row = df.loc[idx]
        date = row["date"]
        open_etf = row[open_etf_col]
        open_fut = row[open_fut_col]
        close_etf = row[close_etf_col]
        close_fut = row[close_fut_col]
        hedge_ratio = row["hedge_ratio"] if not pd.isna(row["hedge_ratio"]) else 0.0
        signal_today = row[signal_col]

        # === Alpha/Base 双仓逻辑 ===
        if not base_built and signal_today > 0 and hedge_ratio > 0 and open_etf > 0:
            base_etf_units = 1000
            base_fut_units = int(round(base_etf_units * hedge_ratio))
            base_built = True

        if signal_today < alpha_entry_threshold and hedge_ratio > 0:
            if alpha_etf_units < 2 * base_etf_units:
                alpha_etf_units += 100
                alpha_fut_units += int(round(100 * hedge_ratio))
                entry_equity_alpha = cash + (base_etf_units + alpha_etf_units) * open_etf - (base_fut_units + alpha_fut_units) * open_fut * 10000

        if alpha_etf_units > 0 and entry_equity_alpha:
            total_value_now = cash + (base_etf_units + alpha_etf_units) * open_etf - (base_fut_units + alpha_fut_units) * open_fut * 10000
            alpha_pnl = total_value_now - entry_equity_alpha
            alpha_pnl_rate = alpha_pnl / entry_equity_alpha
            if alpha_pnl_rate >= stop_gain or alpha_pnl_rate <= -stop_loss:
                realized_pnls.append(alpha_pnl_rate)
                alpha_etf_units = 0
                alpha_fut_units = 0
                entry_equity_alpha = None
        date = row["date"]
        open_etf = row[open_etf_col]
        open_fut = row[open_fut_col]
        close_etf = row[close_etf_col]
        close_fut = row[close_fut_col]
        hedge_ratio = row["hedge_ratio"] if not pd.isna(row["hedge_ratio"]) else 0.0
        signal_today = row[signal_col]

        trade_action = 0  # 1=开仓，-1=平仓，0=无交易

        # === 4.1 如果已经持仓，先判断是否止盈止损或信号翻转 ===
        if holding:
            # 按开盘价评估当前权益
            etf_value_open = n_etf * open_etf
            fut_pnl_open = (entry_fut_price - open_fut) * n_fut * 10000  # 期货空头盈亏
            current_equity_open = cash + etf_value_open + fut_pnl_open
            # 相对开仓权益的收益率
            pnl_rate = (current_equity_open - entry_equity) / entry_equity if entry_equity != 0 else 0.0
            # 止盈 / 止损 / 信号翻转
            if pnl_rate >= stop_gain or pnl_rate <= -stop_loss or not (signal_today > 0):
                # 平仓：以开盘价退出持仓
                cash = current_equity_open
                # 记录交易盈亏率
                realized_pnls.append(pnl_rate)
                # 重置持仓状态
                holding = False
                n_etf = 0.0
                n_fut = 0
                trade_action = -1
                # capital 更新为现金
                capital = cash

        # === 4.2 若空仓且信号为正，则尝试开仓 ===
        if not holding and (signal_today is not None and signal_today > 0):
            # 预留 90% 的资金用于开仓
            available_funds = capital * 0.90
            if open_etf <= 0 or hedge_ratio <= 0:
                # 价格或对冲比例非法，跳过
                pass
            else:
                # 初步按照资金确定 ETF 份额数（忽略期货保证金）
                max_etf = math.floor(available_funds / open_etf)
                # 根据 DV01 对冲比例计算期货手数（向最接近整数取整，至少为 1 手）
                n_fut = max(1, int(round(max_etf * hedge_ratio)))
                # 根据期货数量反推所需 ETF 份额数（即 n_etf = n_fut / hedge_ratio）
                # 使用四舍五入取整
                n_etf = n_fut / hedge_ratio
                # 保证 ETF 份额为整数
                n_etf = math.floor(n_etf)
                # 计算期货保证金
                margin_required = n_fut * margin_rate * open_fut * 10000
                # 计算ETF买入金额
                etf_cost = n_etf * open_etf
                # 总资金需求
                total_required = margin_required + etf_cost
                if total_required > available_funds and total_required > 0:
                    # 按资金比例缩减仓位
                    scale = available_funds / total_required
                    n_etf = math.floor(n_etf * scale)
                    n_fut = max(1, int(round(n_etf * hedge_ratio)))
                    margin_required = n_fut * margin_rate * open_fut * 10000
                    etf_cost = n_etf * open_etf
                    total_required = margin_required + etf_cost
                    # 若仍超出资金则跳过开仓
                    if total_required > available_funds:
                        n_etf = 0
                        n_fut = 0
                if n_etf > 0 and n_fut > 0:
                    # 计算交易成本（滑点）：ETF 买入按高 3 tick 成交，期货卖出按低 1 tick 成交
                    slip_etf_cost = n_etf * tick_etf * 3
                    slip_fut_cost = n_fut * tick_fut * 10000
                    # 扣除 ETF 买入成本、期货滑点成本
                    cash -= (etf_cost + slip_etf_cost + slip_fut_cost)
                    # 更新持仓状态和记录开仓时的基准数据
                    holding = True
                    trade_action = 1
                    entry_equity = cash + n_etf * open_etf  # 不计期货市值
                    entry_etf_price = open_etf
                    entry_fut_price = open_fut
                    capital = entry_equity

        # === 4.3 记录每日权益和仓位 ===
        if holding:
            # 持仓状态下，按当日开盘价计算当前权益（标记期货盈亏）
            etf_value_open = n_etf * open_etf
            fut_pnl_open = (entry_fut_price - open_fut) * n_fut * 10000
            current_equity = cash + (base_etf_units + alpha_etf_units) * open_etf + (entry_fut_price - open_fut) * (base_fut_units + alpha_fut_units) * 10000
            position_flag = 1
        else:
            current_equity = cash
            position_flag = 0
        # 记录数据
        cum_return = (current_equity / initial_capital) - 1
        records.append({
            "date": date,
            "position": position_flag,
            "trade": trade_action,
            "equity": current_equity,
            "cum_return": cum_return
        })

    # === 5. 构建结果 DataFrame ===
    result_df = pd.DataFrame(records)
    # 日收益率
    result_df["strategy_ret"] = result_df["equity"].pct_change().fillna(0)

    # === 6. 绩效指标计算 ===
    trade_days = len(result_df)
    final_equity = result_df["equity"].iloc[-1]
    total_return = (final_equity / initial_capital) - 1
    annual_return = (1 + total_return) ** (252 / trade_days) - 1 if trade_days > 0 else 0.0
    # 最大回撤
    cumulative_max = result_df["equity"].cummax()
    drawdown = result_df["equity"] / cumulative_max - 1
    max_drawdown = abs(drawdown.min()) if not drawdown.empty else 0.0
    # Sharpe 比率
    daily_returns = result_df["strategy_ret"]
    if daily_returns.std() != 0:
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0
    # Calmar 比率
    calmar_ratio = annual_return / max_drawdown if max_drawdown > 1e-8 else float('nan')
    # 胜率
    win_trades = sum(1 for pnl in realized_pnls if pnl > 0)
    total_trades = len(realized_pnls)
    win_rate = win_trades / total_trades if total_trades > 0 else float('nan')
    metrics = {
        "annual_return": annual_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "calmar_ratio": calmar_ratio,
        "win_rate": win_rate,
        "total_trades": total_trades,
    }
    return result_df, metrics, realized_pnls