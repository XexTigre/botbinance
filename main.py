import os
import time
import logging
from datetime import datetime
from threading import Thread
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, EMAIndicator
from ta.volatility import BollingerBands
from binance.client import Client
from zoneinfo import ZoneInfo

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
USE_TESTNET = True  # Use False para real

if USE_TESTNET:
    client = Client(API_KEY, API_SECRET, testnet=True)
    client.API_URL = 'https://testnet.binance.vision/api'
else:
    client = Client(API_KEY, API_SECRET)

SYMBOL = "BTCUSDT"
INTERVAL = Client.KLINE_INTERVAL_5MINUTE
POSITION_SIZE_PERCENT = 0.10  # 10% do saldo disponível em USDT para cada operação
TIMEZONE = ZoneInfo('America/Sao_Paulo')

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def pegar_historico():
    try:
        klines = client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=100)
        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df['close'] = df['close'].astype(float)
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms').dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
        return df
    except Exception as e:
        logging.error(f"Erro pegar histórico: {e}")
        return None

def calcular_indicadores(df):
    df['sma20'] = SMAIndicator(df['close'], window=20).sma_indicator()
    df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
    df['rsi14'] = RSIIndicator(df['close'], window=14).rsi()
    bb = BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    return df

def pegar_saldo_usdt():
    try:
        balance = client.get_asset_balance(asset='USDT')
        return float(balance['free'])
    except Exception as e:
        logging.error(f"Erro pegar saldo USDT: {e}")
        return 0.0

def criar_ordem_mercado(lado, quantidade):
    try:
        if lado == 'BUY':
            ordem = client.create_order(
                symbol=SYMBOL,
                side=Client.SIDE_BUY,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantidade
            )
        else:
            ordem = client.create_order(
                symbol=SYMBOL,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantidade
            )
        logging.info(f"Ordem executada: {lado} {quantidade} {SYMBOL}")
        return ordem
    except Exception as e:
        logging.error(f"Erro executar ordem: {e}")
        return None

def decidir_acao(df):
    ultima = df.iloc[-1]
    close = ultima['close']
    rsi14 = ultima['rsi14']
    bb_high = ultima['bb_high']
    bb_low = ultima['bb_low']

    logging.info(f"Close: {close:.2f} | RSI14: {rsi14:.2f} | BB High: {bb_high:.2f} | BB Low: {bb_low:.2f}")

    # Estratégia simples com Bollinger e RSI:
    if close < bb_low and rsi14 < 30:
        return "BUY"
    elif close > bb_high and rsi14 > 70:
        return "SELL"
    else:
        return "HOLD"

def calcular_quantidade(preco, saldo_usdt):
    quantidade = (saldo_usdt * POSITION_SIZE_PERCENT) / preco
    return round(quantidade, 6)

def bot_ciclo():
    posicao_aberta = False
    lado_posicao = None

    while True:
        df = pegar_historico()
        if df is None:
            time.sleep(60)
            continue

        df = calcular_indicadores(df)
        acao = decidir_acao(df)
        preco_atual = df.iloc[-1]['close']
        saldo_usdt = pegar_saldo_usdt()

        logging.info(f"Ação decidida: {acao}, Saldo USDT: {saldo_usdt:.2f}")

        if acao == "BUY" and not posicao_aberta and saldo_usdt > 10:  # mínimo 10 USDT para operar
            quantidade = calcular_quantidade(preco_atual, saldo_usdt)
            ordem = criar_ordem_mercado('BUY', quantidade)
            if ordem:
                posicao_aberta = True
                lado_posicao = 'BUY'
        elif acao == "SELL" and posicao_aberta and lado_posicao == 'BUY':
            quantidade = calcular_quantidade(preco_atual, saldo_usdt)
            ordem = criar_ordem_mercado('SELL', quantidade)
            if ordem:
                posicao_aberta = False
                lado_posicao = None
        else:
            logging.info("Nenhuma ação executada neste ciclo.")

        time.sleep(300)  # 5 minutos entre ciclos

if __name__ == "__main__":
    logging.info("Bot iniciado.")
    Thread(target=bot_ciclo, daemon=True).start()

    from flask import Flask
    app = Flask(__name__)

    @app.route('/')
    def home():
        return "Bot Binance avançado rodando!", 200

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
