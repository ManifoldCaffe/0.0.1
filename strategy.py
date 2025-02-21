import pandas as pd
import numpy as np
from config import CONFIG
from datafetcher import DataFetcher
from datetime import datetime


class MeanReversionStrategy:

    def __init__(self):
        self.df = None
        SPOT_FUTURE_PORTION = 0.5  # 现货和合约仓位比例

    def fetch_data(self):
        """获取数据"""

        fetcher = DataFetcher()
        spot = fetcher.fetch_data('spot')[['close']].rename(
            columns={'close': 'spot'})
        future = fetcher.fetch_data('future')[['close']].rename(
            columns={'close': 'future'})

        # 合并数据
        self.df = pd.merge(spot, future, left_index=True,
                           right_index=True, how='inner')
        # 调试
        if CONFIG['debug']:
            spot.to_csv('debug/spot.csv')
            future.to_csv('debug/future.csv')

    def generate_signals(self):
        """生成交易信号"""

        zscore_window = CONFIG['zscore_window']
        zscore_threshold = CONFIG['zscore_threshold']

        # 计算溢价
        self.df['premium'] = self.df['spot'] - self.df['future']

        # 计算溢价率
        self.df['premium_pct'] = (
            # (现货价格 - 合约价格) / 现货价格
            self.df['spot'] - self.df['future']) / self.df['spot'] * 100

        # 计算统计指标
        self.df['mean_premium_pct'] = self.df['premium_pct'].rolling(
            zscore_window).mean()
        self.df['std'] = self.df['premium_pct'].rolling(
            zscore_window).std()
        self.df['zscore'] = (self.df['premium_pct'] -
                             self.df['mean_premium_pct']) / self.df['std']

        # 生成原始信号
        self.df['raw_signal'] = 0
        self.df.loc[self.df['zscore'] > zscore_threshold,
                    'raw_signal'] = -1  # 溢价率高于阈值，做空溢价, 同时做空现货、做多合约
        self.df.loc[self.df['zscore'] < -zscore_threshold,
                    'raw_signal'] = 1  # 溢价率低于阈值，做多溢价, 同时做多现货、做空合约

        self.df['signal'] = self.df['raw_signal']

        # 计算 20 SMA
        self.df['SMA'] = self.df['premium_pct'].rolling(
            window=2*zscore_window).mean()

        # 过滤连续同向信号
        self.df['signal'] = self.df['raw_signal'].diff().ne(
            0).astype(int) * self.df['raw_signal']

        # 计算波动率
        self.df['volatility'] = self.df['premium_pct'].rolling(24).std()

        # 过滤低波动时段
        self.df.loc[self.df['volatility'] <
                    CONFIG['min_volatility'], 'signal'] = 0

        # 调试
        if CONFIG['debug']:
            self.df[['signal']].to_csv('debug/signals.csv')

        return self.df

    def backtest(self, initial_capital=CONFIG['initial_capital']):
        """策略回测"""
        df = self.df
        # 加入手续费和滑点的开关
        use_fee = CONFIG.get('enable_fee', True)
        use_slippage = CONFIG.get('enable_slippage', True)
        fee_spot = CONFIG['fee_rate']['spot'] if use_fee else 0
        fee_future = CONFIG['fee_rate']['future'] if use_fee else 0
        slippage = CONFIG['slippage'] if use_slippage else 0
        fraction = {'spot': fee_spot + slippage,
                    'future': fee_future + slippage}

        positions = []
        current_capital = initial_capital
        position_size = 0
        entry_premium = None
        exit_premium = None
        entry_time = None
        position_direction = 0  # 0:无仓位, 1:多仓, -1:空仓

        for time, row in df.iterrows():
            # 平仓
            if position_direction != 0:  # 有仓位
                exit_premium = row['premium']
                exit_spot_price = row['spot']
                exit_future_price = row['future']
                if position_direction == 1:  # 做多溢价，做多现货，做空合约
                    spot_pnl = (exit_spot_price / entry_spot_price) * \
                        (1 - fraction['spot'])**2 - 1
                    future_pnl = (1 - fraction['future']) - (
                        exit_future_price / entry_future_price) / (1 - fraction['future'])
                    pnl = spot_pnl * 0.5 + future_pnl * 0.5
                else:  # 做空溢价，做空现货，做多合约
                    spot_pnl = (
                        1 - fraction['spot']) - (exit_spot_price / entry_spot_price) / (1 - fraction['spot'])
                    future_pnl = (exit_future_price / entry_future_price) * \
                        (1 - fraction['future'])**2 - 1
                    pnl = spot_pnl * 0.5 + future_pnl * 0.5

                # 调试
                # if CONFIG['debug']:
                #     print(f'[{time}] pnl: {pnl}')

                # 止盈止损
                if pnl >= CONFIG['take_profit'] or pnl <= -CONFIG['stop_loss']:
                    current_capital += (1 + pnl) * position_size  # 平仓结算
                    positions.append({
                        'capital': current_capital,
                        'type': 'long' if position_direction == 1 else 'short',
                        'entry_premium': entry_premium,
                        'exit_premium': exit_premium,
                        'pnl': pnl,
                        'duration': (time - entry_time).total_seconds() / 3600,
                        'entry_time': entry_time,
                        'exit_time': time,
                        'status': '反向'
                    })
                    # 平仓后重置仓位状态
                    position_direction = 0
                    position_size = 0
                    entry_premium = None
                # 反向信号
                elif (row['signal'] == -position_direction) & (pnl > 0):
                    current_capital += (1 + pnl) * position_size  # 平仓结算
                    positions.append({
                        'capital': current_capital,
                        'type': 'long' if position_direction == 1 else 'short',
                        'entry_premium': entry_premium,
                        'exit_premium': exit_premium,
                        'pnl': pnl,
                        'duration': (time - entry_time).total_seconds() / 3600,
                        'entry_time': entry_time,
                        'exit_time': time,
                        'status': '反向'
                    })
                    position_direction = 0
                    position_size = 0
                    entry_premium = None

            # 开仓
            if position_direction == 0 and row['signal'] != 0:
                entry_premium = row['premium']
                entry_spot_price = row['spot']
                entry_future_price = row['future']
                entry_time = time
                position_direction = row['signal']
                position_size = current_capital * CONFIG['position_ratio']
                current_capital -= position_size

        # 统计，计算各种指标
        results = pd.DataFrame(positions)

# 调试
        if CONFIG['debug']:
            results.to_csv('debug/position_history.csv')

        if results.empty:
            print("没有交易执行。")
            return results
        else:
            initial_capital_value = initial_capital
            final_capital_value = results['capital'].iloc[-1]
            total_profit = final_capital_value - initial_capital_value
            total_trades = len(results)

            profitable_trades = results[results['pnl'] > 0]
            win_rate = len(profitable_trades) / total_trades * 100

            avg_duration = results['duration'].mean(
            ) if 'duration' in results.columns else 0

            start_time = df.index[0]
            end_time = df.index[-1]
            time_in_years = (
                end_time - start_time).total_seconds() / (365.25 * 24 * 3600)
            annualized_return = ((final_capital_value / initial_capital_value)
                                 ** (1 / time_in_years) - 1) * 100 if time_in_years > 0 else np.nan

            max_drawdown = -(results['pnl'].cumsum() -
                             results['pnl'].cumsum().cummax()).min() * 100

            cumpnl = results['pnl'].cumsum()
            drawdown_series = cumpnl - cumpnl.cummax()
            if drawdown_series.empty:
                max_drawdown_recovery_time = 0
            else:
                trough_idx = drawdown_series.idxmin()
                peak_value = cumpnl.cummax().iloc[trough_idx]
                trough_time = results['exit_time'].iloc[trough_idx]
                recovery_time = None
                for j in range(trough_idx, len(cumpnl)):
                    if cumpnl.iloc[j] >= peak_value:
                        recovery_time = (
                            results['exit_time'].iloc[j] - trough_time).total_seconds() / 3600
                        break
                max_drawdown_recovery_time = recovery_time if recovery_time is not None else np.nan

            roi = (final_capital_value - initial_capital_value) / \
                initial_capital_value * 100
            avg_pnl = results['pnl'].mean() * 100
            pnl_std = results['pnl'].std()
            sharpe_ratio = avg_pnl / pnl_std if pnl_std != 0 else np.nan

            metrics = {
                "初始资金": f'{initial_capital_value}',
                "最终资金": f'{final_capital_value}',
                "总收益": f'{total_profit}',
                "年化收益率": f'{annualized_return} %',
                "胜率": f'{win_rate} %',
                "交易次数": f'{total_trades}',
                "平均持仓时间": f'{avg_duration} h',
                "最大回撤": f'{max_drawdown} %',
                "最大回撤修复时间": f'{max_drawdown_recovery_time} h',
                "夏普比率": sharpe_ratio
            }

            return results, metrics


if __name__ == '__main__':
    engine = MeanReversionStrategy()
    engine.fetch_data()
    engine.generate_signals()
    trade_history, metrics = engine.backtest()
    print(f'[{datetime.now()}] 回测完成。')
    print(f'[{datetime.now()}] 交易记录:')
    print(trade_history.head())
    if CONFIG['debug']:
        trade_history.to_csv('debug/trade_history.csv')
    print(f'[{datetime.now()}] 交易指标:')
    for k, v in metrics.items():
        print(f'{k}: {v}')
