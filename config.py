from datetime import datetime


CONFIG = {
    # 数据配置
    'initial_capital': 10000,    # 初始资金
    'symbol': 'BTC/USDT',        # 交易对
    'timeframe': '5m',          # 时间粒度
    'since': int(datetime.strptime("2024-01-01 00:00:00",
                                   "%Y-%m-%d %H:%M:%S").timestamp())*1000,      # 起始时间戳
    # 'since': 1704067200000,      # 起始时间戳
    'limit': 100000,               # 数据点数
    'proxy_url': 'http://127.0.0.1:7890',
    'timezone': 'Asia/Shanghai',
    # 绘图参数
    'save_csv': True,
    'chart_ma_window': 24,
    # 策略参数
    'zscore_window': 6,        # 窗口
    'zscore_threshold': 1.8,    # 阈值
    'stop_loss': 0.002,          # 止损
    'take_profit': 0.001,        # 止盈
    'position_ratio': 0.5,      # 仓位比例
    'min_volatility': 0.0,     # 最小波动率
    # 费用设置
    'fee_rate': {'spot':0.001, 'future': 0.0001},         # 手续费
    'slippage': 0.001,         # 滑点
    'enable_fee': False,        # 开启手续费
    'enable_slippage': False,   # 开启
    # 调试
    'debug': True
}
