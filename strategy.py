import pandas as pd
import numpy as np
from datafetcher import DataFetcher
from datetime import datetime

ENABLE_DEBUG = True

class MeanReversionStrategy:
    """均值回归策略"""
    def __init__(self):
        pass
    def config(self, symbol='BTC/USDT', timeframe='5m', range='1y', start_time='2024-01-01 00:00:00', zscore_window=120, zscore_threshold=2.1, min_volatility=0.05, SPOT_FUTURE_PORTION=0.5):
        self.SYMBOL = symbol
        self.TIMEFRAME = timeframe
        self.RANGE = range
        self.START_TIME = start_time

        self.zscore_window = zscore_window        # 窗口
        self.zscore_threshold = zscore_threshold    # 阈值
        self.min_volatility = min_volatility    # 最小波动率
        SPOT_FUTURE_PORTION = SPOT_FUTURE_PORTION        # 现货和合约仓位比例

    def load_data(self):
        """导入数据"""

        fetcher = DataFetcher()
        spot = fetcher.fetch_data(symbol=self.SYMBOL, start_time=self.START_TIME, range=self.RANGE, timeframe=self.TIMEFRAME, contract_type='spot')[['close']].rename(
            columns={'close': 'spot'})
        future = fetcher.fetch_data(symbol=self.SYMBOL, start_time=self.START_TIME, range=self.RANGE, timeframe=self.TIMEFRAME, contract_type='future')[['close']].rename(
            columns={'close': 'future'})

        # 合并数据
        self.market_data = pd.merge(spot, future, left_index=True,
                           right_index=True, how='inner')
        # 调试
        if ENABLE_DEBUG:
            spot.to_csv('debug/spot.csv')
            future.to_csv('debug/future.csv')

    def generate_signals(self):
        """生成交易信号"""

        zscore_window = self.zscore_window
        zscore_threshold = self.zscore_threshold

        # 计算溢价
        self.market_data['premium'] = self.market_data['spot'] - self.market_data['future']

        # 计算溢价率
        self.market_data['premium_pct'] = (
            # (现货价格 - 合约价格) / 现货价格
            self.market_data['spot'] - self.market_data['future']) / self.market_data['spot'] * 100

        # 计算统计指标
        self.market_data['mean_premium_pct'] = self.market_data['premium_pct'].rolling(
            zscore_window).mean()
        self.market_data['std'] = self.market_data['premium_pct'].rolling(
            zscore_window).std()
        self.market_data['zscore'] = (self.market_data['premium_pct'] -
                             self.market_data['mean_premium_pct']) / self.market_data['std']

        # 生成原始信号
        self.market_data['raw_signal'] = 0
        self.market_data.loc[self.market_data['zscore'] > zscore_threshold,
                    'raw_signal'] = -1  # 溢价率高于阈值，做空溢价, 同时做空现货、做多合约
        self.market_data.loc[self.market_data['zscore'] < -zscore_threshold,
                    'raw_signal'] = 1  # 溢价率低于阈值，做多溢价, 同时做多现货、做空合约

        self.market_data['signal'] = self.market_data['raw_signal']

        # 计算 20 SMA
        self.market_data['SMA'] = self.market_data['premium_pct'].rolling(
            window=2*zscore_window).mean()

        # # 过滤连续同向信号
        # self.market_data['signal'] = self.market_data['raw_signal'].diff().ne(
        #     0).astype(int) * self.market_data['raw_signal']

        # 计算波动率
        self.market_data['volatility'] = self.market_data['premium_pct'].rolling(24).std()

        # 过滤低波动时段
        self.market_data.loc[self.market_data['volatility'] <
                    self.min_volatility, 'signal'] = 0

        # 调试
        if ENABLE_DEBUG:
            self.market_data[['signal']].to_csv('debug/signals.csv')

        return self.market_data


if __name__ == '__main__':
    engine = MeanReversionStrategy()
    engine.load_data()
    engine.generate_signals()

    from visualizer import Visualizer
    visualizer = Visualizer()
    visualizer.link_strategy(engine)
    visualizer.load_data(engine.market_data)
    visualizer.plot_signals(engine.market_data)

    # from backtest import run_backtest
    # trade_history, metrics = run_backtest(engine.market_data)    # 调用回测模块
    # print(f'[{datetime.now()}] 回测完成。')
    # if not trade_history.empty:
    #     print(f'[{datetime.now()}] 交易记录:')
    #     print(trade_history.head())
    #     if ENABLE_DEBUG:
    #         trade_history.to_csv('debug/trade_history.csv')
    # if metrics:
    #     print(f'[{datetime.now()}] 交易指标:')
    #     for k, v in metrics.items():
    #         print(f'{k}: {v}')
