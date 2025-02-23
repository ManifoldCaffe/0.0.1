import matplotlib
import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import logging
import shutup as shutthefxxkup
from datetime import datetime
from datafetcher import DataFetcher
from strategy import MeanReversionStrategy
from datafetcher import DataFetcher
from backtest import run_backtest
from logger import Logger
from visualizer import Visualizer

if __name__ == '__main__':
    logger = Logger(level=logging.DEBUG)
    datafethcer = DataFetcher()
    engine = MeanReversionStrategy()
    visualizer = Visualizer()

    engine.config()
    engine.load_data()
    engine.generate_signals()

    position_history, metrics = run_backtest(engine.market_data)

    if metrics:
        for key, value in metrics.items():
            print(f'{key}: {value}')

    visualizer.link_strategy(engine)
    # visualizer.load_data(engine.market_data, position_history)
    visualizer.plot(engine.market_data, position_history)
