# BY: DeepSeek R1
import matplotlib
import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import logging
import shutup as shutthefxxkup
from datetime import datetime
from config import CONFIG
from datafetcher import DataFetcher
from strategy import MeanReversionStrategy
from logger import Logger
from visualizer import Visualizer

if __name__ == '__main__':
    logger = Logger(level=logging.DEBUG)
    engine = MeanReversionStrategy()
    visualizer = Visualizer()
    engine.fetch_data()
    engine.generate_signals()
    positions, metrics = engine.backtest()
    for key, value in metrics.items():
        print(f'{key}: {value}')
    visualizer.plot(engine.df, positions)
