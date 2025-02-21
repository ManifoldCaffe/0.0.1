import ccxt
import pandas as pd
import pickle
from config import CONFIG
from datetime import datetime, timezone


class DataFetcher:
    def __init__(self):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            # 'rateLimit': 10000,  # 统一的交易所属性
            'options': {
                'adjustForTimeDifference': True,  # 特定交易所的属性
            },
            'proxies': {'http': CONFIG['proxy_url'], 'https': CONFIG['proxy_url']},
            'timeout': 30000
        })

    def fetch_data(self, contract_type='spot'):
        """获取现货或合约数据"""
        df = None
        # 如果数据存在已经, 读取并返回
        try:
            with open(f'data/{CONFIG["symbol"].replace("/", "_")}_{contract_type}_{CONFIG["timeframe"]}_{datetime.fromtimestamp(CONFIG["since"]/1000, tz=timezone.utc)}_{CONFIG["limit"]}.pkl', 'rb') as f:
                all_ohlcv = pickle.load(f)
                df = self._process_data(all_ohlcv)
        except FileNotFoundError:
            # 如果数据不存在, 从交易所获取
            try:
                # 设置市场类型
                self.exchange.options['defaultType'] = contract_type
                if contract_type == 'future':
                    self.exchange.options['defaultSettle'] = 'usdt'

                # 分页获取数据
                all_ohlcv = []
                since = CONFIG['since']  # 起始时间戳
                while len(all_ohlcv) < CONFIG['limit']:
                    batch = self.exchange.fetch_ohlcv(
                        symbol=CONFIG['symbol'],
                        timeframe=CONFIG['timeframe'],
                        since=since,
                        limit=CONFIG['limit'] - len(all_ohlcv)
                    )
                    if not batch:
                        break
                    all_ohlcv.extend(batch)
                    since = batch[-1][0] - batch[-2][0] + \
                        batch[-1][0]  # 下一次请求的起始时间戳

                # 保存数据
                with open(f'data/{CONFIG["symbol"].replace("/", "_")}_{contract_type}_{CONFIG["timeframe"]}_{datetime.fromtimestamp(CONFIG["since"]/1000, tz=timezone.utc)}_{CONFIG["limit"]}.pkl', 'wb') as f:
                    pickle.dump(all_ohlcv, f)

                df = self._process_data(all_ohlcv)

                with open(f'data/{CONFIG["symbol"].replace("/", "_")}_{contract_type}_{CONFIG["timeframe"]}_{datetime.fromtimestamp(CONFIG["since"]/1000, tz=timezone.utc)}_{CONFIG["limit"]}.csv', 'w') as f:
                    f.write(df.to_csv())    # 保存处理后的数据方便调试
            except Exception as e:
                print(f"数据获取失败: {str(e)}")

        return df

    def _process_data(self, data):
        """处理原始数据"""
        df = pd.DataFrame(
            data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df


if __name__ == '__main__':
    fetcher = DataFetcher()
    print('正在获取现货数据...')
    spot = fetcher.fetch_data('spot')
    print('数据获取完成')
    print(f'数据量: {len(spot)}')
    print('数据预览:')
    print(spot.head())
    print('正在获取合约数据...')
    future = fetcher.fetch_data('future')
    print('数据获取完成')
    print(f'数据量: {len(future)}')
    print('数据预览:')
    print(future.head())
