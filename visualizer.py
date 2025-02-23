import pandas as pd
import numpy as np
from datetime import datetime
from matplotlib import pyplot as plt

ENABLE_DEBUG = True

class Visualizer:
    """图表绘制类"""

    def __init__(self):
        # 图表注册字典，默认注册 premium/signals 图表和资金曲线图表
        self.charts = {}
        self.register_chart("premium_signals", self._plot_premium_signals)
        self.register_chart("capital", self._plot_capital)

    def link_strategy(self, strategy):
        """关联策略类，方便获取配置参数"""
        self.strategy = strategy

    def load_data(self, *data):
        """导入数据"""
        self.data = data

    def register_chart(self, key: str, func):
        """注册新的图表绘制方法，便于后续扩展图表"""
        self.charts[key] = func

    def _configure_plot(self):
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']

    def _plot_premium(self, ax, market_data: pd.DataFrame, premium_col: str):
        """绘制 premium 和移动平均"""
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
        # premium_range = self.strategy.zscore_threshold * market_data['std']
        # ax.fill_between(
        #     market_data.index,
        #     market_data['mean_premium_pct'] + premium_range,
        #     market_data['mean_premium_pct'] - premium_range,
        #     color='gray', alpha=0.2
        # )
        ax.set_ylabel(f'{self.strategy.SYMBOL}' + '溢价（USDT）' if premium_col == 'premium' else '溢价率（%）')

    def _plot_signals(self, ax, market_data: pd.DataFrame, premium_col: str):
        """绘制交易信号"""
        long_signals = market_data[market_data['signal'] == 1]
        short_signals = market_data[market_data['signal'] == -1]
        ax.scatter(long_signals.index, long_signals[premium_col],
                   marker='^', color='g', s=30, label='做多信号')
        ax.scatter(short_signals.index, short_signals[premium_col],
                   marker='v', color='r', s=30, label='做空信号')

    def _plot_premium_signals(self, ax, market_data: pd.DataFrame, premium_col: str):
        """组合绘制 premium 和信号"""
        self._plot_premium(ax, market_data, premium_col)
        self._plot_signals(ax, market_data, premium_col)

    def _plot_capital(self, ax, market_data, position_history: pd.DataFrame):
        """绘制资金曲线"""
        ax.plot(
            position_history.set_index('exit_time')['final_capital'].copy().reindex(market_data.index, method='ffill'),
            label='资金曲线',
            color='#1f77b4',
            linewidth=1
        )
        ax.set_ylabel('资金')
        ax.set_xlabel('时间')
        ax.legend()

    def _save_if_debug(self):
        if ENABLE_DEBUG:
            plt.savefig(
                f"debug/plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

    def plot_signals(self, market_data: pd.DataFrame, premium_col: str = 'premium_pct'):
        """绘制 premium 和信号"""
        self._configure_plot()
        fig, ax = plt.subplots(figsize=(15, 8))
        self.charts["premium_signals"](
            ax, market_data, premium_col=premium_col)
        plt.tight_layout()
        self._save_if_debug()
        plt.show()

    def plot(self, market_data: pd.DataFrame, position_history: pd.DataFrame, layout: str = 'stacked'):
        """
        统一绘图接口，根据 layout 参数选择布局，同时利用注册的图表方法便于后续扩展。

        参数:
            market_data: 市场数据 DataFrame
            position_history: 交易记录 DataFrame
            layout: 
                'stacked' - 上下两块面板（上面绘制 premium/signals，下面绘制资金曲线）
                'twin'    - 单图双 y 轴（左侧绘制 premium/signals，右侧绘制资金曲线）
        """
        self._configure_plot()

        if layout == 'stacked':
            fig, (ax_top, ax_bottom) = plt.subplots(2, 1, figsize=(15, 8))
            # premium/signals 面板使用 'premium_pct' 字段
            self.charts["premium_signals"](
                ax_top, market_data, premium_col='premium_pct')
            self.charts["capital"](ax_bottom, market_data, position_history)
        elif layout == 'twin':
            fig, ax_left = plt.subplots(figsize=(15, 8))
            ax_right = ax_left.twinx()
            # premium/signals 面板使用 'premium' 字段
            self.charts["premium_signals"](
                ax_left, market_data, premium_col='premium')
            self.charts["capital"](ax_right, market_data, position_history)
            ax_right.set_xlabel('时间')
        else:
            raise ValueError("无效的 layout 参数，请使用 'stacked' 或 'twin'。")

        plt.tight_layout()
        self._save_if_debug()
        plt.show()
