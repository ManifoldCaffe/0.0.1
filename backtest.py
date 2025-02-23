import pandas as pd
import numpy as np
import math

# Configuration moved from external config.py
INITIAL_CAPITAL = 10000           # Example initial capital
FEE_RATE = {'spot': 0.001, 'future': 0.0001}  # Example fee rates
SLIPPAGE = 0.0005                  # Example slippage value
ENABLE_FEE = False
ENABLE_SLIPPAGE = False
LEVERAGE = 20                      # Example leverage
TAKE_PROFIT = 0.02                 # Example take profit threshold
STOP_LOSS = 0.03                   # Example stop loss threshold
POSITION_RATIO = 0.1               # Example position ratio
ENABLE_DEBUG = True


def run_backtest(df, initial_capital=INITIAL_CAPITAL) -> tuple:
    # Initialize parameters and state variables
    use_fee = ENABLE_FEE
    use_slippage = ENABLE_SLIPPAGE
    fee_spot = FEE_RATE['spot'] if use_fee else 0
    fee_future = FEE_RATE['future'] if use_fee else 0
    slippage = SLIPPAGE if use_slippage else 0
    fraction = {'spot': fee_spot + slippage, 'future': fee_future + slippage}
    position_history = []
    current_capital = initial_capital
    position_size = 0
    entry_spot_price = None
    entry_future_price = None
    entry_time = None
    position_direction = 0  # 0: no position, 1: long, -1: short
    current_position = {}

    for time, row in df.iterrows():
        # 持仓则计算盈亏
        if position_direction != 0:
            exit_spot_price = row['spot']
            exit_future_price = row['future']
            if position_direction == 1:
                spot_pnl = (exit_spot_price / entry_spot_price) * \
                    (1 - fraction['spot'])**2 - 1
                future_pnl = (1 - fraction['future']) - (exit_future_price /
                                                         entry_future_price) / (1 - fraction['future'])
                pnl = spot_pnl * 0.5 + future_pnl * 0.5 * leverage
            else:
                spot_pnl = (1 - fraction['spot']) - (exit_spot_price /
                                                     entry_spot_price) / (1 - fraction['spot'])
                future_pnl = (exit_future_price / entry_future_price) * \
                    (1 - fraction['future'])**2 - 1
                pnl = spot_pnl * 0.5 + future_pnl * 0.5 * leverage

            # 平仓
            if pnl < -1:
                current_capital += (1 + pnl) * position_size
                current_position['pnl'] = pnl * 100
                current_position['exit_time'] = time
                current_position['duration'] = (
                    time - entry_time).total_seconds() / 3600
                current_position['close_type'] = '爆仓'
                current_position['final_capital'] = current_capital
                position_history.append(current_position)

                position_direction = 0
            elif pnl >= TAKE_PROFIT or pnl <= -STOP_LOSS:  # 止盈止损
                current_capital += (1 + pnl) * position_size
                current_position['pnl'] = pnl * 100
                current_position['exit_time'] = time
                current_position['duration'] = (
                    time - entry_time).total_seconds() / 3600
                current_position['close_type'] = '止盈' if pnl >= TAKE_PROFIT else '止损'
                current_position['final_capital'] = current_capital
                position_history.append(current_position)

                position_direction = 0
            elif (row['signal'] == -position_direction) and (pnl > 0):  # 反向
                current_capital += (1 + pnl) * position_size
                current_position['pnl'] = pnl * 100
                current_position['exit_time'] = time
                current_position['duration'] = (
                    time - entry_time).total_seconds() / 3600
                current_position['close_type'] = '反向'
                current_position['final_capital'] = current_capital
                position_history.append(current_position)

                position_direction = 0
        # 开仓
        elif row['signal'] != 0:
            entry_spot_price = row['spot']
            entry_future_price = row['future']
            entry_time = time
            position_direction = row['signal']
            # leverage = math.atan(
            #     abs(df.loc[time, 'zscore'])/3)/(math.pi/2) * LEVERAGE
            leverage = LEVERAGE
            position_size = current_capital * POSITION_RATIO
            current_position = {
                'initial_capital': current_capital,
                'type': 'long' if position_direction == 1 else 'short',
                'entry_time': entry_time,
                'leverage': leverage
            }
            current_capital -= position_size
    
    # 交易结束，计算指标
    position_history = pd.DataFrame(position_history)
    if ENABLE_DEBUG:
        position_history.to_csv('debug/position_history.csv')

    if position_history.empty:
        print("没有交易执行。")
        metrics = {}
    else:
        initial_capital_value = initial_capital
        final_capital_value = position_history['final_capital'].iloc[-1]
        total_profit = final_capital_value - initial_capital_value
        total_trades = len(position_history)

        profitable_trades = position_history[position_history['pnl'] > 0]
        win_rate = len(profitable_trades) / total_trades * 100

        avg_duration = position_history['duration'].mean(
        ) if 'duration' in position_history.columns else 0

        start_time = df.index[0]
        end_time = df.index[-1]
        time_in_years = (end_time - start_time).total_seconds() / \
            (365.25 * 24 * 3600)
        annualized_return = ((final_capital_value / initial_capital_value)
                             ** (1 / time_in_years) - 1) * 100 if time_in_years > 0 else np.nan

        max_drawdown = (position_history['final_capital'] /
                         position_history['final_capital'].cummax() - 1).min() * 100

        cumpnl = position_history['pnl'].cumsum()
        drawdown_series = cumpnl - cumpnl.cummax()
        if drawdown_series.empty:
            max_drawdown_recovery_time = 0
        else:
            trough_idx = drawdown_series.idxmin()
            peak_value = cumpnl.cummax().iloc[trough_idx]
            trough_time = position_history['exit_time'].iloc[trough_idx]
            recovery_time = None
            for j in range(trough_idx, len(cumpnl)):
                if cumpnl.iloc[j] >= peak_value:
                    recovery_time = (
                        position_history['exit_time'].iloc[j] - trough_time).total_seconds() / 3600
                    break
            max_drawdown_recovery_time = recovery_time if recovery_time is not None else np.nan

        roi = (final_capital_value - initial_capital_value) / \
            initial_capital_value * 100
        avg_pnl = position_history['pnl'].mean() * 100
        pnl_std = position_history['pnl'].std()
        sharpe_ratio = avg_pnl / pnl_std if pnl_std != 0 else np.nan

        metrics = {
            "初始资金": f'{INITIAL_CAPITAL}',
            "最终资金": f'{final_capital_value}',
            "总收益": f'{total_profit}',
            "年化收益率": f'{annualized_return} %',
            "胜率": f'{win_rate} %',
            "交易次数": f'{total_trades}',
            "平均持仓时间": f'{avg_duration} h',
            "最大回撤": f'{max_drawdown} %',
            "最大回撤修复时间": f'{max_drawdown_recovery_time} h',
            "夏普比率": sharpe_ratio,
        }

        return position_history, metrics
