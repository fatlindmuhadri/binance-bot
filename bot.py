import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from datetime import datetime
from dotenv import load_dotenv

# Ngarko variablat e mjedisit nga skedari .env
load_dotenv()

# --- KONFIGURIMI I LLOGARISË ---
API_KEY = "vCVPFQecFIZVIin8MlfQENB4RtQ3LvJOEwswEBAeGcUuJx6CHu5AayJvqbvfD3dd"
API_SECRET = "5xSVmS1XGuMIoH0GxB3DUMgcYF49TEoscb6lBeEN1nlyB4ISCAVgwUcInPXeOOkl"
TELEGRAM_TOKEN = "8921013869:AAGPdghtjE8KCJWXX_CaGEthMcYODCeAFDc"
CHAT_ID = "5458100041"

BASE_URL = "https://testnet.binancefuture.com"  # Për Testnet/Demo (ndryshoje në live nëse kalon real)


CUSTOM_LEVERAGE_MAP = {
    "AAVEUSDT": 75, "ADAUSDT": 75, "ALGOUSDT": 50, "ANKRUSDT": 50, "APEUSDT": 50,
    "APTUSDT": 50, "ARBUSDT": 75, "ATOMUSDT": 75, "AVAXUSDT": 75, "AXSUSDT": 50,
    "BATUSDT": 50, "BNBUSDT": 100, "BOMEUSDT": 50, "BONKUSDT": 50, "BTCUSDT": 125,
    "CAKEUSDT": 50, "CELOUSDT": 50, "CHZUSDT": 50, "COMPUSDT": 50, "CRVUSDT": 50,
    "DASHUSDT": 50, "DOGEUSDT": 75, "DOTUSDT": 75, "EGLDUSDT": 50, "ENJUSDT": 50,
    "ENSUSDT": 50, "EOSUSDT": 50, "ETCUSDT": 75, "ETHUSDT": 125, "FETUSDT": 75,
    "FILUSDT": 75, "FLOKIUSDT": 50, "FLOWUSDT": 50, "FTMUSDT": 75, "FXSUSDT": 50,
    "GALAUSDT": 50, "GMTUSDT": 50, "GMXUSDT": 50, "GRTUSDT": 75, "HBARUSDT": 50,
    "ICPUSDT": 75, "IMXUSDT": 75, "INJUSDT": 75, "IOSTUSDT": 50, "IOTAUSDT": 50,
    "JASMYUSDT": 50, "JUPUSDT": 50, "KAVAUSDT": 50, "KSMUSDT": 50, "LDOUSDT": 75,
    "LINKUSDT": 75, "LTCUSDT": 75, "MANAUSDT": 50, "MASKUSDT": 50, "MATICUSDT": 75,
    "NEARUSDT": 75, "NEOUSDT": 50, "NOTUSDT": 50, "OGNUSDT": 50, "OMUSDT": 50,
    "ONDOUSDT": 50, "OPUSDT": 75, "PENDLEUSDT": 50, "PEPEUSDT": 75, "PERPUSDT": 50,
    "POLUSDT": 75, "POLYXUSDT": 50, "PYTHUSDT": 50, "QTUMUSDT": 50, "RAYUSDT": 50,
    "RENDERUSDT": 75, "RUNEUSDT": 75, "RVNUSDT": 50, "SANDUSDT": 50, "SEIUSDT": 75,
    "SHIBUSDT": 75, "SKLUSDT": 50, "SNXUSDT": 50, "SOLUSDT": 125, "SSVUSDT": 50,
    "STEEMUSDT": 50, "STXUSDT": 75, "SUIUSDT": 75, "SUSHIUSDT": 50, "THETAUSDT": 50,
    "TIAUSDT": 75, "TNSRUSDT": 50, "TRUMPUSDT": 50, "TRXUSDT": 75, "TURBOUSDT": 50,
    "UNIUSDT": 75, "WLDUSDT": 75, "WOOUSDT": 50, "XLMUSDT": 75, "XRPUSDT": 75,
    "XTZUSDT": 50, "ZECUSDT": 50, "ZENUSDT": 50, "ZROUSDT": 50
}

trades_executed_today = 0
active_symbols = set()
current_day = datetime.now().day
monitored_positions = {}

TP_FOLLOWUP_TEXT = {
    1: "*Move SL to breakeven price",
    2: "*Fix another 30% profit\n*Move SL to TP1",
    3: "*Fix another 50% profit\n*Move SL to breakeven price",
    4: "*Position fully closed\n*Well done!"
}

# ------------------- TELEGRAM -------------------

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN.strip()}/sendMessage"
        payload = {"chat_id": str(CHAT_ID).strip(), "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            print(f"Telegram gabim: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Gabim në dërgimin e Telegram: {e}")

# ------------------- BINANCE REQUEST CORE -------------------

def binance_request(method, endpoint, params=None):
    if params is None:
        params = {}
    params['timestamp'] = int(time.time() * 1000)
    query_string = urlencode(params)
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = signature
    url = BASE_URL + endpoint
    headers = {"X-MBX-APIKEY": API_KEY}
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, params=params, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, params=params, timeout=10)
        else:
            raise ValueError(f"Metodë e panjohur: {method}")
        return response.json()
    except Exception as e:
        print(f"Gabim në binance_request({method}, {endpoint}): {e}")
        return {}

def set_cross_and_leverage(symbol, leverage):
    try:
        binance_request('POST', "/fapi/v1/marginType", {"symbol": symbol, "marginType": "CROSSED"})
    except Exception:
        pass
    try:
        binance_request('POST', "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
    except Exception:
        pass

def get_klines(symbol, interval, limit=50):
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"Gabim te get_klines për {symbol}: {e}")
    return []

def get_account_balance():
    account_info = binance_request('GET', "/fapi/v2/account")
    if not isinstance(account_info, dict):
        return 0.0
    for asset in account_info.get('assets', []):
        if asset.get('asset') == 'USDT':
            return float(asset.get('availableBalance', 0.0))
    return 0.0

def get_open_position_quantity(symbol):
    positions = binance_request('GET', "/fapi/v2/positionRisk", {"symbol": symbol})
    if isinstance(positions, list):
        for pos in positions:
            amt = float(pos.get('positionAmt', 0))
            if amt != 0:
                return abs(amt)
    return 0.0

def place_binance_order(symbol, side, quantity):
    return binance_request('POST', "/fapi/v1/order", {"symbol": symbol, "side": side, "type": "MARKET", "quantity": quantity})

def place_conditional_order(symbol, side, order_type, stop_price, quantity):
    if stop_price < 5:
        quantity = round(quantity, 0)
    else:
        quantity = round(quantity, 2)
    if quantity <= 0:
        quantity = 1.0
    params = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "stopPrice": round(stop_price, 4),
        "quantity": quantity,
        "reduceOnly": "true"
    }
    return binance_request('POST', "/fapi/v1/order", params)

def cancel_all_open_orders(symbol):
    try:
        binance_request('DELETE', "/fapi/v1/allOpenOrders", {"symbol": symbol})
    except Exception:
        pass

def get_order_status(symbol, order_id):
    if not order_id:
        return {}
    return binance_request('GET', "/fapi/v1/order", {"symbol": symbol, "orderId": order_id})

# ------------------- TEKNIKE & SMC / FVG INDICATORS -------------------

def calculate_ema(prices, period):
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i-1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100 - (100 / (1 + rs))

def check_fair_value_gap(candles):
    """Kërkon për FVG në 3 qirinjtë e fundit (Imbalance)"""
    if len(candles) < 3:
        return None
    try:
        c1_high = float(candles[-3][2])
        c1_low = float(candles[-3][3])
        c3_high = float(candles[-1][2])
        c3_low = float(candles[-1][3])

        # Bullish FVG: Low i qiririt të 3-të është më i lartë se High i qiririt të 1-rë
        if c3_low > c1_high:
            return "BULLISH_FVG"
        
        # Bearish FVG: High i qiririt të 3-të është më i ulët se Low i qiririt të 1-rë
        if c3_high < c1_low:
            return "BEARISH_FVG"
    except Exception:
        pass
    return None

def check_smc_structure(candles_1h):
    """SMC: Kontrollon për thyerje të strukturës së tregut (BOS bazuar në pikat e fundit)"""
    if len(candles_1h) < 10:
        return "NEUTRAL"
    try:
        highs = [float(c[2]) for c in candles_1h[-10:]]
        lows = [float(c[3]) for c in candles_1h[-10:]]
        
        # Nëse qiriu i fundit thyen nivelin më të lartë ose më të ulët të 5 qirinjve paraprakë
        if highs[-1] > max(highs[:-1]):
            return "BOS_BULLISH"
        elif lows[-1] < min(lows[:-1]):
            return "BOS_BEARISH"
    except Exception:
        pass
    return "NEUTRAL"

# ------------------- ANALIZA E PËRMIRËSUAR (4h -> 1h -> 15m + SMC + FVG) -------------------

def analyze_high_probability_setup(symbol):
    candles_4h = get_klines(symbol, "4h", 20)
    candles_1h = get_klines(symbol, "1h", 20)
    candles_15m = get_klines(symbol, "15m", 15)

    if not candles_4h or not candles_1h or not candles_15m or len(candles_4h) < 10 or len(candles_1h) < 10:
        return None

    try:
        closes_4h = [float(c[4]) for c in candles_4h]
        closes_1h = [float(c[4]) for c in candles_1h]
        closes_15m = [float(c[4]) for c in candles_15m]

        # 1. Trendi Makro (4h EMA 20)
        ema_4h = calculate_ema(closes_4h, 20)
        trend_4h = "BULLISH" if closes_4h[-1] > ema_4h else "BEARISH"

        # 2. Trendi i Mesëm (1h EMA 20 + SMC BOS)
        ema_1h = calculate_ema(closes_1h, 20)
        trend_1h = "BULLISH" if closes_1h[-1] > ema_1h else "BEARISH"
        smc_structure = check_smc_structure(candles_1h)

        # 3. Indikatorët Afatshkurtër (15m RSI + FVG)
        rsi_15m = calculate_rsi(closes_15m, 14)
        fvg_status = check_fair_value_gap(candles_15m)

        price_now = closes_15m[-1]
        price_prev = closes_15m[-3]
        change_pct = abs((price_now - price_prev) / price_prev) * 100

        if change_pct < 1.0:
            return None

        # Kushtet për LONG (Kërkon konfirmim nga 4h, 1h, SMC, FVG dhe RSI jo mbi 75)
        if (trend_4h == "BULLISH" and 
            trend_1h == "BULLISH" and 
            (smc_structure == "BOS_BULLISH" or fvg_status == "BULLISH_FVG") and 
            rsi_15m < 75 and 
            price_now > price_prev):
            return "LONG"

        # Kushtet për SHORT (Kërkon konfirmim nga 4h, 1h, SMC, FVG dhe RSI jo nën 25)
        if (trend_4h == "BEARISH" and 
            trend_1h == "BEARISH" and 
            (smc_structure == "BOS_BEARISH" or fvg_status == "BEARISH_FVG") and 
            rsi_15m > 25 and 
            price_now < price_prev):
            return "SHORT"

    except Exception as e:
        print(f"Gabim në analizën e avancuar për {symbol}: {e}")
        return None

    return None

# ------------------- FORMAT NDIHMËS -------------------

def format_duration(delta):
    total_minutes = int(delta.total_seconds() // 60)
    days = total_minutes // (24 * 60)
    hours = (total_minutes % (24 * 60)) // 60
    minutes = total_minutes % 60
    return f"{days}d:{hours:02d}h:{minutes:02d}m"

# ------------------- EKZEKUTIMI I TREGTISË -------------------

def execute_trade_workflow(symbol, setup, max_lev):
    global trades_executed_today

    klines_15m = get_klines(symbol, "15m", 10)
    if not klines_15m:
        return False

    entry_price = float(klines_15m[-1][4])
    set_cross_and_leverage(symbol, max_lev)

    available_balance = get_account_balance()
    if available_balance <= 0:
        return False

    initial_margin_usdt = available_balance * 0.02
    position_usdt = initial_margin_usdt * max_lev
    quantity = round(position_usdt / entry_price, 3)
    if quantity <= 0:
        return False

    target_quantity = quantity / 4
    side = "BUY" if setup == "LONG" else "SELL"
    algo_side = "SELL" if setup == "LONG" else "BUY"
    display_side = "LONG (buy)" if setup == "LONG" else "SHORT (sell)"

    if setup == "LONG":
        sl_price = entry_price * 0.975
        tp1 = entry_price * 1.012
        tp2 = entry_price * 1.020
        tp3 = entry_price * 1.030
        tp4 = entry_price * 1.045
    else:
        sl_price = entry_price * 1.025
        tp1 = entry_price * 0.988
        tp2 = entry_price * 0.980
        tp3 = entry_price * 0.970
        tp4 = entry_price * 0.955

    order_response = place_binance_order(symbol, side, quantity)
    if not isinstance(order_response, dict) or 'orderId' not in order_response:
        return False

    sl_resp = place_conditional_order(symbol, algo_side, "STOP_MARKET", sl_price, quantity)
    tp1_resp = place_conditional_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp1, target_quantity)
    tp2_resp = place_conditional_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp2, target_quantity)
    tp3_resp = place_conditional_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp3, target_quantity)
    tp4_resp = place_conditional_order(symbol, algo_side, "TAKE_PROFIT_MARKET", tp4, target_quantity)

    monitored_positions[symbol] = {
        "setup": setup,
        "entry_price": entry_price,
        "entry_time": datetime.now(),
        "leverage": max_lev,
        "tp_orders": {
            tp1_resp.get("orderId"): {"level": 1, "price": tp1},
            tp2_resp.get("orderId"): {"level": 2, "price": tp2},
            tp3_resp.get("orderId"): {"level": 3, "price": tp3},
            tp4_resp.get("orderId"): {"level": 4, "price": tp4},
        },
        "sl_order_id": sl_resp.get("orderId"),
        "filled_levels": set()
    }
    active_symbols.add(symbol)

    signal_message = (
        f"💎 **SMC + FVG SIGNAL ({trades_executed_today + 1}/10)** 💎\n"
        f"🟢 **{symbol} {display_side}**\n"
        f"Margin: **Cross, {max_lev}X**\n"
        f"ENTRY: `{entry_price:.5f}`\n"
        f"---------------------\n"
        f"🎯 TARGETS: `[{tp1:.4f}]` \\| `[{tp2:.4f}]` \\| `[{tp3:.4f}]` \\| `[{tp4:.4f}]`\n"
        f"❌ STOPLOSS (2.5%): `[{sl_price:.5f}]`"
    )
    send_telegram_message(signal_message)
    return True

# ------------------- MONITORIMI I TP-VE -------------------

def check_tp_fills():
    for symbol, pos in list(monitored_positions.items()):
        for order_id, tp_info in list(pos["tp_orders"].items()):
            level = tp_info["level"]
            if level in pos["filled_levels"]:
                continue

            order_status = get_order_status(symbol, order_id)
            if isinstance(order_status, dict) and order_status.get("status") == "FILLED":
                fill_price = float(order_status.get("avgPrice", tp_info["price"]) or tp_info["price"])
                entry_price = pos["entry_price"]
                lev = pos["leverage"]

                if pos["setup"] == "LONG":
                    raw_pct = (fill_price - entry_price) / entry_price
                else:
                    raw_pct = (entry_price - fill_price) / entry_price
                profit_pct = raw_pct * lev * 100

                elapsed = datetime.now() - pos["entry_time"]
                duration_str = format_duration(elapsed)

                base_symbol = symbol.replace("USDT", "") + "/USDT"
                followup = TP_FOLLOWUP_TEXT.get(level, "")

                message = (
                    f"💸{base_symbol}\n"
                    f"Price {fill_price:.5f}\n"
                    f"Profit: > {profit_pct:.0f}%\n"
                    f"✅ TARGET #{level} DONE\n"
                    f"🕒Spent: {duration_str}\n"
                    f"———\n"
                    f"{followup}"
                )
                send_telegram_message(message)
                pos["filled_levels"].add(level)

                if level == 4:
                    del monitored_positions[symbol]
                    active_symbols.discard(symbol)

# ------------------- REVERSE LOGIC -------------------

def monitor_and_reverse_logic():
    for symbol, pos in list(monitored_positions.items()):
        current_setup = pos["setup"]
        new_setup = analyze_high_probability_setup(symbol)
        if new_setup and new_setup != current_setup:
            max_lev = CUSTOM_LEVERAGE_MAP.get(symbol, 20)
            close_side = "SELL" if current_setup == "LONG" else "BUY"

            qty_to_close = get_open_position_quantity(symbol)
            if qty_to_close > 0:
                binance_request('POST', "/fapi/v1/order", {
                    "symbol": symbol, "side": close_side, "type": "MARKET",
                    "quantity": qty_to_close, "reduceOnly": "true"
                })
            cancel_all_open_orders(symbol)

            reverse_alert = (
                f"⚠️ **MARKET REVERSAL DETECTION ON {symbol}!**\n"
                f"Mbyllur {current_setup}. Duke kaluar në **{new_setup}**!"
            )
            send_telegram_message(reverse_alert)

            del monitored_positions[symbol]
            active_symbols.discard(symbol)

            success = execute_trade_workflow(symbol, new_setup, max_lev)
            if success:
                global trades_executed_today
                trades_executed_today += 1

# ------------------- CIKLI KRYESOR -------------------

def scan_and_execute_trades():
    global trades_executed_today, active_symbols, current_day

    now_day = datetime.now().day
    if now_day != current_day:
        current_day = now_day
        trades_executed_today = 0
        active_symbols.clear()
        monitored_positions.clear()

    check_tp_fills()

    if trades_executed_today >= 10:
        return

    monitor_and_reverse_logic()

    for symbol, max_lev in CUSTOM_LEVERAGE_MAP.items():
        if trades_executed_today >= 10:
            break
        if symbol in active_symbols:
            continue

        setup = analyze_high_probability_setup(symbol)
        if setup:
            success = execute_trade_workflow(symbol, setup, max_lev)
            if success:
                trades_executed_today += 1
            time.sleep(10)

if __name__ == "__main__":
    send_telegram_message("🤖 Boti SMC + FVG u ndez me sukses! (4h -> 1h -> 15m) aktiv.")
    while True:
        try:
            scan_and_execute_trades()
        except Exception as e:
            print(f"Gabim kritik në ciklin kryesor: {e}")
        time.sleep(10)
