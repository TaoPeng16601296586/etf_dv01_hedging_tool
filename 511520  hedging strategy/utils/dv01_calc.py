
import pandas as pd
import numpy as np

def calculate_dv01_metrics(df, etf_duration=7.5, ctd_dv01=0.042, conversion_factor=0.85):
    '''
    给定合并后的 ETF + 国债期货 dataframe，计算：
    - ETF DV01（元/bp）
    - FUT DV01（元/bp）
    - 推荐对冲手数
    '''
    df = df.copy()
    df["etf_dv01"] = df["close_etf"] * etf_duration * 0.0001
    df["fut_dv01"] = (ctd_dv01 / conversion_factor) * 10000
    #四舍五入取整
    df["hedge_ratio"] = np.rint(df["etf_dv01"] / df["fut_dv01"]).astype(int)
  

    return df[["date", "close_etf", "close_fut", "etf_dv01", "fut_dv01", "hedge_ratio"]]
