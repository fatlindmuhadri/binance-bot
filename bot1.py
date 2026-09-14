import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode

# --- KONFIGURIMI I LLOGARISË ---
API_KEY = "vCVPFQecFIZVIin8MlfQENB4RtQ3LvJOEwswEBAeGcUuJx6CHu5AayJvqbvfD3dd"
API_SECRET = "5xSVmS1XGuMIoH0GxB3DUMgcYF49TEoscb6lBeEN1nlyB4ISCAVgwUcInPXeOOkl"
TELEGRAM_TOKEN = "8921013869:AAGPdghtjE8KCJWXX_CaGEthMcYODCeAFDc"
CHAT_ID = "5458100041"

BASE_URL = "https://testnet.binancefuture.com"  # Për Testnet/Demo (ndryshoje në live nëse kalon real)

trades_executed_today = 0
active_symbols = set()

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Gabim në dërgimin e Telegram: {e}")

def binance_request(method, endpoint, params=None):
    if params is None:
        params = {}
    params['timestamp'] = int(time.time() * 1000)
    query_string = urlencode(params)
    signature = hmac.new(API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    params['signature'] = signature
    
    url = BASE_URL + endpoint
    headers = {"X-MBX-APIKEY": API_KEY}
    
    if method == 'GET':
        response = requests.get(url, headers=headers, params=params)
    elif method == 'POST':
        response = requests.post(url, headers=headers, params=params)
    return response.json()

def get_exchange_info():
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    response = requests.get(url).json()
    symbols_data = []
    
    for s in response.get('symbols', []):
        if s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL':
            symbol = s['symbol']
            max_lev = 20
            for bracket in s.get('brackets', []):
                if 'initialLeverage' in bracket:
                    max_lev = max(max_lev, bracket['initialLeverage'])
            symbols_data.append({"symbol": symbol, "max_leverage": max_lev})
            
    return symbols_data

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
        response = requests.get(url, params=params)
        return response.json()
    except Exception:
        return []

def get_account_balance():
    account_info = binance_request('GET', "/fapi/v2/account")
    for asset in account_info.get('assets', []):
        if asset['asset'] == 'USDT':
            return float(asset['availableBalance'])
    return 5000.0

def place_binance_order(symbol, side, quantity):
    endpoint = "/fapi/v1/order"
    params = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": quantity
    }
    return binance_request('POST', endpoint, params)

def place_tp_sl_automatic_orders(symbol, side, quantity, tp1, tp2, tp3, tp4, sl):
    """Vendos automatikisht mbylljet e pjesshme (TP1-TP4) dhe Stop Loss në Binance"""
    close_side = "SELL" if side == "BUY" else "BUY"
    part_qty = round(quantity / 4, 3)  # Ndaj pozicionin në 4 pjesë të barabarta (25% secila)
    if part_qty <= 0:
        part_qty = quantity

    tps = [tp1, tp2, tp3, tp4]
    
    # Vendos 4 urdhërat Limit për Take Profit me reduceOnly
    for tp_price in tps:
        params = {
            "symbol": symbol,
            "side": close_side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": part_qty,
            "price": round(tp_price, 4),
            "reduceOnly": True
        }
        binance_request('POST', "/fapi/v1/order", params)

    # Vendos Stop Loss (STOP_MARKET) për të gjithë sasinë
    sl_params = {
        "symbol": symbol,
        "side": close_side,
        "type": "STOP_MARKET",
        "stopPrice": round(sl, 4),
        "quantity": quantity,
        "reduceOnly": True
    }
    binance_request('POST', "/fapi/v1/order", sl_params)

def analyze_high_probability_setup(symbol):
    candles_4h = get_klines(symbol, "4h", 10)
    candles_1h = get_klines(symbol, "1h", 10)
    candles_15m = get_klines(symbol, "15m", 15)
    
    if len(candles_4h) < 5 or len(candles_1h) < 5 or len(candles_15m) < 5:
        return None

    close_4h_latest = float(candles_4h[-1][4])
    close_4h_past = float(candles_4h[-4][4])
    trend_4h = "BULLISH" if close_4h_latest > close_4h_past else "BEARISH"

    price_now = float(candles_15m[-1][4])
    price_prev = float(candles_15m[-3][4])
    change_pct = abs((price_now - price_prev) / price_prev) * 100

    # Filtër: Kërkon lëvizje të fortë/momentum mbi 1.2%
    if change_pct < 1.2:
        return None

    if trend_4h == "BULLISH" and price_now > price_prev:
        return "LONG"
    elif trend_4h == "BEARISH" and price_now < price_prev:
        return "SHORT"
        
    return None

def scan_and_execute_trades():
    global trades_executed_today, active_symbols
    
    # Kufiri max 10 tregti në ditë
    if trades_executed_today >= 10:
        print("U arrit limiti prej 10 tregtimesh për sot. Boti po pret...")
        return

    print(f"Duke kërkuar sinjale me cilësi të lartë (Tregtia {trades_executed_today + 1}/10)...")
    coins = get_exchange_info()
    
    for coin in coins:
        if trades_executed_today >= 10:
            break
            
        symbol = coin["symbol"]
        if symbol in active_symbols:
            continue
            
        max_lev = coin["max_leverage"]
        chosen_lev = min(max_lev, 75)  # Përdor leverage max deri në 75x
        
        setup = analyze_high_probability_setup(symbol)
        
        if setup:
            klines_15m = get_klines(symbol, "15m", 10)
            if not klines_15m:
                continue
                
            entry_price = float(klines_15m[-1][4])
            set_cross_and_leverage(symbol, chosen_lev)
            
            # Llogaritja e sasisë (5% e balancës totale me leverage)
            available_balance = get_account_balance()
            position_usdt = (available_balance * 0.05) * chosen_lev
            quantity = round(position_usdt / entry_price, 3)
            
            if quantity <= 0:
                continue

            # Targetet e fitimit në bazë të leverage-it: TP1=75%, TP2=150%, TP3=225%, TP4=300%
            target_pct_1 = 0.75 / chosen_lev
            target_pct_2 = 1.50 / chosen_lev
            target_pct_3 = 2.25 / chosen_lev
            target_pct_4 = 3.00 / chosen_lev
            
            # Stop Loss në bazë të leverage-it: 150% humbje në llogari
            sl_pct = 1.50 / chosen_lev  

            if setup == "LONG":
                side = "BUY"
                display_side = "LONG (buy)"
                tp1 = entry_price * (1 + target_pct_1)
                tp2 = entry_price * (1 + target_pct_2)
                tp3 = entry_price * (1 + target_pct_3)
                tp4 = entry_price * (1 + target_pct_4)
                sl = entry_price * (1 - sl_pct)
            else:
                side = "SELL"
                display_side = "SHORT (sell)"
                tp1 = entry_price * (1 - target_pct_1)
                tp2 = entry_price * (1 - target_pct_2)
                tp3 = entry_price * (1 - target_pct_3)
                tp4 = entry_price * (1 - target_pct_4)
                sl = entry_price * (1 + sl_pct)

            # 1. Hap pozicionin kryesor në Binance
            order_response = place_binance_order(symbol, side, quantity)
            
            if 'orderId' in order_response:
                trades_executed_today += 1
                active_symbols.add(symbol)
                
                # 2. Vendos automatikisht TP1-TP4 dhe Stop Loss në Binance
                place_tp_sl_automatic_orders(symbol, side, quantity, tp1, tp2, tp3, tp4, sl)
                
                # 3. Dërgo njoftimin në Telegram
                signal_message = (
                    f"🚨 **PREMIUM EXECUTED SIGNAL ({trades_executed_today}/10)** 🚨\n"
                    f"🟢 **{symbol} {display_side}**\n"
                    f"⚙️ Margin: **Cross, {chosen_lev}X**\n"
                    f"📍 ENTRY: `{entry_price:.4f}`\n\n"
                    f"🎯 **TARGETS (Automated Scaling):**\n"
                    f"1. [`{tp1:.4f}`] (75% fitim)\n"
                    f"2. [`{tp2:.4f}`] (150% fitim)\n"
                    f"3. [`{tp3:.4f}`] (225% fitim)\n"
                    f"4. [`{tp4:.4f}`] (300% fitim)\n\n"
                    f"❌ **STOPLOSS:** [`{sl:.4f}`] (Risk ~150%)"
                )
                send_telegram_message(signal_message)
                print(f"Pozicioni u hap dhe TP/SL u vendosën në Binance për {symbol}")
                
                time.sleep(10)

# --- NISJA E BOTIT ---
if __name__ == "__main__":
    send_telegram_message("🤖 Boti u nis! Duke kërkuar max 10 tregti cilësore në ditë me Cross, Max Lev, TP (75%-300%) dhe SL automatik.")
    
    while True:
        scan_and_execute_trades()
        # Kontrollon tregun çdo 10 minuta
        time.sleep(600)