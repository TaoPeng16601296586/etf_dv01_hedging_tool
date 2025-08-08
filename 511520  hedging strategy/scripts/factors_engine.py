import pandas as pd

def add_factors(df):
    # 1. 10Y 国债利率
    df['factor_10y_gov'] = df['中国:国债收益率:10年']
    # 2. 1Y 国债利率
    df['factor_1y_gov'] = df['中国:国债收益率:1年']
    # 3. 30Y/5Y 国债利率及斜率
    df['factor_30y_gov'] = df['中债国债到期收益率:30年']
    df['factor_5y_gov'] = df['中债国债到期收益率:5年']
    df['factor_30y_5y_slope'] = df['中债国债到期收益率:30年'] - df['中债国债到期收益率:5年']
    df['factor_10y_1y_slope'] = df['中国:国债收益率:10年'] - df['中国:国债收益率:1年']
    df['factor_30y_10y_slope'] = df['中债国债到期收益率:30年'] - df['中国:国债收益率:10年']
    # 4. 10Y 国开债及风险溢价
    df['factor_10y_policy'] = df['中债国开债到期收益率:10年']
    df['factor_policy_spread'] = df['中债国开债到期收益率:10年'] - df['中国:国债收益率:10年']
    # 5. 资金面
    df['factor_shibor3m'] = df['SHIBOR:3个月']
    df['factor_r007'] = df['R007']
    # 6. 利率预期
    df['factor_fr007'] = df['利率互换:FR007:1年']
    # 7. 资金面利差
    df['factor_shibor3m_r007_spread'] = df['SHIBOR:3个月'] - df['R007']
    df['factor_fr007_shibor3m_spread'] = df['利率互换:FR007:1年'] - df['SHIBOR:3个月']
    # 8. 曲率
    df['factor_curve_curvature'] = df['中债国债到期收益率:30年'] + df['中国:国债收益率:1年'] - 2 * df['中国:国债收益率:10年']
    # 额外因子: 利率相对3%名义票息的偏离。
    # 国债期货合约通常以3%为名义票息。当市场利率高于3%时，高票息老券折算成本更低；
    # 当市场利率低于3%时，低票息新券折算成本更低。因此，以到期收益率减去3%衡量交割期权的“价内程度”。
    df['factor_rel_10y_coupon'] = df['中国:国债收益率:10年'] - 0.03
    df['factor_rel_30y_coupon'] = df['中债国债到期收益率:30年'] - 0.03

    # 新老券利差：利用长端与中短端国债收益率之差作为流动性溢价的Proxy。
    # 这里在已有的 factor_30y_10y_slope 基础上，额外记录30Y-10Y、30Y-5Y、10Y-5Y利差，便于后续模型挑选。
    df['factor_30y_10y_spread'] = df['中债国债到期收益率:30年'] - df['中国:国债收益率:10年']
    df['factor_30y_5y_spread'] = df['中债国债到期收益率:30年'] - df['中债国债到期收益率:5年']
    df['factor_10y_5y_spread'] = df['中国:国债收益率:10年'] - df['中债国债到期收益率:5年']

    # 税收利差（国开债与国债收益率差）：与因子 factor_policy_spread 相同，但以独立命名保留，
    # 用于衡量国开债与国债之间的税收或流动性溢价。
    df['factor_tax_spread'] = df['中债国开债到期收益率:10年'] - df['中国:国债收益率:10年']

    # 利率互换固定端与短期资金利率差额：反映 IRS swap spread，表示市场对利率预期与信用风险偏好的变化。
    df['factor_swap_spread'] = df['利率互换:FR007:1年'] - df['R007']

    # 期货基差：ETF与期货收盘价的差值，衡量基差的实时状态。
    df['factor_basis'] = df['close_etf'] - df['close_fut']
    # 9. ETF-期货价差
    df['spread'] = df['close_etf'] - df['close_fut']
    # 10. ETF/期货收益率
    df['etf_ret'] = df['close_etf'].pct_change()
    df['fut_ret'] = df['close_fut'].pct_change()
    # 11. ETF-期货相关性（20日滑动窗口）
    df['corr_20d'] = df['close_etf'].pct_change().rolling(20).corr(df['close_fut'].pct_change())
    # 12. ETF/期货波动率（20日滑动窗口）
    df['etf_vol_20d'] = df['close_etf'].pct_change().rolling(20).std()
    df['fut_vol_20d'] = df['close_fut'].pct_change().rolling(20).std()
    return df

if __name__ == "__main__":
    # 读取原始数据
    in_path = r"data/etf_futures_interest_merged.csv"
    out_path = r"data/etf_futures_interest_factors.csv"
    df = pd.read_csv(in_path, encoding="utf-8-sig")
    df = add_factors(df)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"因子数据已保存至: {out_path}")