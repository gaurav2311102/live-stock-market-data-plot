import threading
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from SmartApi import SmartConnect
from logzero import logger
import pyotp
from dotenv import load_dotenv
import os
import matplotlib.ticker as mticker


load_dotenv()


API_KEY = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
PASSWORD = os.getenv("PIN")
TOTP_SECRET = os.getenv("TOKEN")


totp = pyotp.TOTP(TOTP_SECRET).now()


smart_connect = SmartConnect(api_key=API_KEY)
login_response = smart_connect.generateSession(CLIENT_ID, PASSWORD, totp)

AUTH_TOKEN = login_response["data"]["jwtToken"]
CLIENT_CODE = CLIENT_ID
FEED_TOKEN = login_response["data"]["feedToken"]
correlation_id = "test"
action = 1
mode = 1


def select_token():
    print("\nSelect Market Index:")
    print("1. NIFTY 50")
    print("2. SENSEX")
    
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == "1":
        return "99926000", "NIFTY 50","1"
    elif choice == "2":
        return "99919000", "SENSEX","3"
    

selected_token, index_name,exchangeType = select_token()


token_list = [{"exchangeType": exchangeType, "tokens": [selected_token]}]


sws = SmartWebSocketV2(AUTH_TOKEN, API_KEY, CLIENT_CODE, FEED_TOKEN, max_retry_attempt=0)


csv_filename = "live_data.csv"


if os.path.exists(csv_filename):
    os.remove(csv_filename)


pd.DataFrame(columns=["time", "ltp"]).to_csv(csv_filename, index=False)


live_data = {"time": [], "ltp": []}
stop_websocket = False 


def on_data(wsapp, message):
    global live_data
    token = message.get('token')
    last_traded_price = message.get('last_traded_price')

    if token is not None and last_traded_price is not None:
        timestamp = datetime.now().strftime('%H:%M:%S')
        price = last_traded_price / 100  

     
        live_data["time"].append(timestamp)
        live_data["ltp"].append(price)

     
        with open(csv_filename, "a") as f:
            f.write(f"{timestamp},{price}\n")

        print(f"Updated Data: {timestamp} -> {price}")
        
        

def on_open(wsapp):
    logger.info("WebSocket Opened")
    sws.subscribe(correlation_id, mode, token_list)
    

def on_error(wsapp, error):
    logger.error(error)

def on_close(wsapp):
    logger.info("WebSocket Closed")


sws.on_open = on_open
sws.on_data = on_data
sws.on_error = on_error
sws.on_close = on_close


def stop_websocket_stream():
    global stop_websocket
    stop_websocket = True
    sws.close_connection()
    print("\n[INFO] WebSocket Stopped.")


def start_websocket():
    global stop_websocket
    stop_websocket = False
    try:
        sws.connect()
    except KeyboardInterrupt:
        stop_websocket_stream()


ws_thread = threading.Thread(target=start_websocket)
ws_thread.start()


fig, ax = plt.subplots()
plt.title(f"Live Market Data - {index_name}")


def animate(i):
    df = pd.read_csv(csv_filename)

    if not df.empty:
        ax.clear()
        
        df = df.tail(20)
        ax.plot(df["time"], df["ltp"], marker="o", linestyle="-", color="blue", label=f"{index_name} Price")
        ax.set_xlabel("Time")  
        ax.set_ylabel("Price (INR)")  
        ax.legend()

        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))  
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        plt.tight_layout()

ani = animation.FuncAnimation(fig, animate, interval=1000, cache_frame_data=False, save_count=100)



plt.show()

try:
    while True:
        time.sleep(1) 
except KeyboardInterrupt:
    print(" Ctrl + C Pressed! Stopping WebSocket...")
    stop_websocket_stream()
    ws_thread.join()
    print(" WebSocket connection closed.")

