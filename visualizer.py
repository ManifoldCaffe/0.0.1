import pandas as pd
import numpy as np
from config import CONFIG
from datetime import datetime
from matplotlib import pyplot as plt


class Visualizer:
    def __init__(self, config: dict = CONFIG):
        self.config = config
        # 图表注册字典，默认注册 premium/signals 图表和资金曲线图表
        self.charts = {}
        self.register_chart("premium_signals", self._plot_premium_signals)
        self.register_chart("capital", self._plot_capital)

    def register_chart(self, key: str, func):
        """注册新的图表绘制方法，便于后续扩展图表"""
        self.charts[key] = func

    def calculate_cumulative(self, trade_history: pd.DataFrame) -> pd.Series:
        returns = trade_history.set_index('entry_time')['pnl']
        cumulative = (1 + returns).cumprod() * self.config['initial_capital']
        return cumulative

    def _configure_plot(self):
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']

    def _plot_premium(self, ax, market_data: pd.DataFrame, premium_col: str):
        ax.plot(
            market_data[premium_col],
            label='溢价',
            color='#2ca02c',
            linewidth=1
        )
        ax.plot(
            market_data['mean_premium_pct'],
            '--',
            label='移动平均',
            color='#d62728',
            linewidth=1
        )
        premium_range = self.config['zscore_threshold'] * market_data['std']
        ax.fill_between(
            market_data.index,
            market_data['mean_premium_pct'] + premium_range,
            market_data['mean_premium_pct'] - premium_range,
            color='gray', alpha=0.2
        )
        ax.set_ylabel('现货价格-合约价格（USDT）')

    def _plot_signals(self, ax, market_data: pd.DataFrame, premium_col: str):
        long_signals = market_data[market_data['signal'] == 1]
        short_signals = market_data[market_data['signal'] == -1]
        ax.scatter(long_signals.index, long_signals[premium_col],
                   marker='^', color='g', s=30, label='做多信号')
        ax.scatter(short_signals.index, short_signals[premium_col],
                   marker='v', color='r', s=30, label='做空信号')

    def _plot_premium_signals(self, ax, market_data: pd.DataFrame, premium_col: str):
        """组合绘制 premium 和信号，方便后续扩展"""
        self._plot_premium(ax, market_data, premium_col)
        self._plot_signals(ax, market_data, premium_col)

    def _plot_capital(self, ax, trade_history: pd.DataFrame):
        cumulative = self.calculate_cumulative(trade_history)
        ax.plot(cumulative, label='资金', color='#9467bd', linewidth=1)
        ax.axhline(self.config['initial_capital'],
                   color='gray', linewidth=1, linestyle='--')
        ax.set_ylabel('资金')
        ax.set_xlabel('时间')

    def _save_if_debug(self):
        if self.config.get('debug'):
            plt.savefig(
                f"debug/plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

    def plot(self, market_data: pd.DataFrame, trade_history: pd.DataFrame, layout: str = 'stacked'):
        """
        统一绘图接口，根据 layout 参数选择布局，同时利用注册的图表方法便于后续扩展。

        参数:
            market_data: 市场数据 DataFrame
            trade_history: 交易记录 DataFrame
            layout: 
                'stacked' - 上下两块面板（上面绘制 premium/signals，下面绘制资金曲线）
                'twin'    - 单图双 y 轴（左侧绘制 premium/signals，右侧绘制资金曲线）
        """
        self._configure_plot()

        if layout == 'stacked':
            fig, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(16, 8))
            # premium/signals 面板使用 'premium_pct' 字段
            self.charts["premium_signals"](
                ax_top, market_data, premium_col='premium_pct')
            self.charts["capital"](ax_bottom, trade_history)
        elif layout == 'twin':
            fig, ax_left = plt.subplots(figsize=(16, 9))
            ax_right = ax_left.twinx()
            # premium/signals 面板使用 'premium' 字段
            self.charts["premium_signals"](
                ax_left, market_data, premium_col='premium')
            self.charts["capital"](ax_right, trade_history)
            ax_right.set_xlabel('时间')
        else:
            raise ValueError("无效的 layout 参数，请使用 'stacked' 或 'twin'。")

        plt.tight_layout()
        self._save_if_debug()
        plt.show()
