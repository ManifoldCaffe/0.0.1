import ccxt
import pandas as pd
import pickle
import time
import logging
from tqdm import tqdm
from datetime import datetime, timezone

ENABLE_DEBUG = True

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


class DataFetcher:
    def __init__(self, exchange_name='binance'):
        # 初始化时不再强制使用默认交易所逻辑，fetch_data中会根据参数创建交易所实例
        self.default_exchange_name = exchange_name
        self.proxy_url = 'http://127.0.0.1:7890'
        self.timezone = 'Asia/Shanghai'

    def fetch_data(self, symbol='BTC/USDT',start_time = "2024-01-01 00:00:00", range = '30d', timeframe='5m', contract_type='spot', data_source='binance'):
        """获取指定数据来源的现货或合约数据"""
        # 根据CONFIG计算时间范围
        start_time_ms = int(datetime.strptime(start_time,
                                   # 起始时间戳
                                   "%Y-%m-%d %H:%M:%S").timestamp())*1000
        range_ms = self._parse_range(range)
        end_time = start_time_ms + range_ms
        file_year = datetime.fromtimestamp(
            start_time_ms/1000, tz=timezone.utc).strftime('%Y-%m-%d-%H:%M:%S')
        file_base = f'{data_source}_{contract_type}_{symbol.replace("/", "")}_{timeframe}_{file_year}_{range}'
        cache_pkl = f'database/{file_base}.pkl'
        cache_csv = f'database/{file_base}.csv'

        # 尝试加载缓存数据
        try:
            with open(cache_pkl, 'rb') as f:
                all_ohlcv = pickle.load(f)
            df = self._process_data(all_ohlcv)
            logging.info("加载缓存数据成功")
            return df
        except FileNotFoundError:
            logging.info("未找到缓存数据，开始从交易所获取数据...")

        # 根据 data_source 创建交易所实例
        exchange = getattr(ccxt, data_source)({
            'enableRateLimit': True,
            'options': {'adjustForTimeDifference': True},
            'proxies': {'http': self.proxy_url, 'https': self.proxy_url},
            'timeout': 30000
        })

        # 设置市场类型
        exchange.options['defaultType'] = contract_type
        if contract_type == 'future':
            exchange.options['defaultSettle'] = 'usdt'

        all_ohlcv = []
        since = start_time_ms
        total_range = end_time - start_time_ms
        progress_bar = tqdm(total=total_range, desc="下载进度", unit="ms")
        while since < end_time:
            batch_limit = 1000
            try:
                batch = exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=batch_limit
                )
                if not batch:
                    logging.info("无更多数据可获取，退出循环")
                    break
                all_ohlcv.extend(batch)
                new_since = batch[-1][0] + \
                    self._timeframe_to_ms(timeframe)
                if new_since <= since:
                    logging.warning("时间戳未更新，退出循环以避免无限循环")
                    break
                update_amount = min(new_since, end_time) - since
                progress_bar.update(update_amount)
                since = new_since
                time.sleep(exchange.rateLimit / 1000)
            except ccxt.RequestTimeout as e:
                logging.error(f"请求超时: {e}")
                time.sleep(30)
                continue
            except ccxt.ExchangeError as e:
                logging.error(f"交易所错误: {e}")
                break
            except Exception as e:
                logging.exception("未知错误:")
                break
        progress_bar.close()

        # 保存下载数据到缓存，并在文件名中包含数据来源信息
        try:
            with open(cache_pkl, 'wb') as f:
                pickle.dump(all_ohlcv, f)
            df = self._process_data(all_ohlcv)
            with open(cache_csv, 'w') as f:
                f.write(df.to_csv())
            logging.info(f"数据保存成功，保存文件: {cache_csv}")
        except Exception as e:
            logging.error(f"缓存数据保存失败: {e}")
        return df

    def _process_data(self, data):
        df = pd.DataFrame(
            data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    def _timeframe_to_ms(self, timeframe):
        """将 timeframe 字符串转换为毫秒值，仅支持 '5m'，可扩展支持更多"""
        if timeframe == '5m':
            return 5 * 60 * 1000
        else:
            raise ValueError(f"不支持的时间周期: {timeframe}")

    def _parse_range(self, range_str):
        """将 range 字符串转换为毫秒值，支持格式 '1d'、'1M'、'1y'"""
        unit = range_str[-1]
        try:
            num = int(range_str[:-1])
        except ValueError:
            raise ValueError(f"range 格式错误: {range_str}")
        if unit.lower() == 'd':
            return num * 24 * 60 * 60 * 1000
        elif unit.lower() == 'm':
            return num * 30 * 24 * 60 * 60 * 1000  # 近似1个月按30天计算
        elif unit.lower() == 'y':
            return num * 365 * 24 * 60 * 60 * 1000  # 按365天计算
        else:
            raise ValueError(f"不支持的 range 单位: {unit}")


if __name__ == '__main__':
    fetcher = DataFetcher()
    logging.info('正在获取数据...')
    spot = fetcher.fetch_data(symbol='ETH/USDT', start_time='2025-01-01 00:00:00', range='30d', timeframe='5m', data_source='binance')
    logging.info('数据获取完成')
    logging.info(f'数据量: {len(spot)}')
    logging.info('数据预览:')
    logging.info(spot.head())
