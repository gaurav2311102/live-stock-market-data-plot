import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import datetime
import threading
import os
import pandas as pd
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from SmartApi import SmartConnect
from dotenv import load_dotenv
import pyotp
import requests
from logzero import logger

# Load Environment Variables
load_dotenv()
API_KEY = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
PASSWORD = os.getenv("PIN")
TOTP_SECRET = os.getenv("TOKEN")
totp = pyotp.TOTP(TOTP_SECRET).now()

# Authenticate AngelOne API
smart_connect = SmartConnect(api_key=API_KEY)
login_response = smart_connect.generateSession(CLIENT_ID, PASSWORD, totp)

if "data" not in login_response:
    raise Exception("Login failed! Check API credentials.")

AUTH_TOKEN = login_response["data"]["jwtToken"]
FEED_TOKEN = login_response["data"]["feedToken"]
correlation_id = "test"
mode = 1  # LTP Mode

# Fetch Nearest Expiry ATM Strike Price
try:
    NSE_URL = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)  # Establish session
    response = session.get(NSE_URL, headers=headers)

    if response.status_code == 200:
        nifty_price = response.json()["records"]["underlyingValue"]
    else:
        raise Exception("Failed to fetch NIFTY price from NSE.")

except Exception as e:
    logger.error(f"Error fetching NIFTY price: {e}")
    nifty_price = None

# Fetch ATM Strike Options
try:
    INSTRUMENTS_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    df = pd.read_json(INSTRUMENTS_URL)
    
    # Save CSV and Load Data
    csv_filename = "instruments_data.csv"
    if os.path.exists(csv_filename):
        os.remove(csv_filename)
        
    df.to_csv(csv_filename, index=False)
    
    # Filter NIFTY Option Contracts
    nifty_options = df[(df['name'] == 'NIFTY') & (df['instrumenttype'] == 'OPTIDX')]

    # Get Available Expiry Dates
    available_expiries = sorted(set(nifty_options["expiry"]))
    nearest_expiry = available_expiries[0] if available_expiries else None

    # Round ATM Strike Price
    atm_strike = 2230000  

    # Get Call & Put Option Tokens
    atm_call = nifty_options[(nifty_options["strike"] == atm_strike) & 
                             (nifty_options["expiry"] == nearest_expiry) & 
                             (nifty_options["symbol"].str.endswith("CE"))]

    atm_put = nifty_options[(nifty_options["strike"] == atm_strike) & 
                            (nifty_options["expiry"] == nearest_expiry) & 
                            (nifty_options["symbol"].str.endswith("PE"))]

    CALL_OPTION_TOKEN = str(atm_call["token"].values[0]) if not atm_call.empty else None
    PUT_OPTION_TOKEN = str(atm_put["token"].values[0]) if not atm_put.empty else None

except Exception as e:
    logger.error(f"Error fetching ATM Strike Options: {e}")
    CALL_OPTION_TOKEN, PUT_OPTION_TOKEN = None, None

# Print Token Info
print(f"Live NIFTY Price: {nifty_price}")
print(f"Nearest Expiry: {nearest_expiry}")
print(f"ATM Strike Price: {atm_strike}")
print(f"Call Option Token: {CALL_OPTION_TOKEN}")
print(f"Put Option Token: {PUT_OPTION_TOKEN}")

# WebSocket Connection if Tokens Found
if CALL_OPTION_TOKEN and PUT_OPTION_TOKEN:
    token_list = [{"exchangeType": 2, "tokens": [CALL_OPTION_TOKEN, PUT_OPTION_TOKEN]}]
    ws = SmartWebSocketV2(AUTH_TOKEN, API_KEY, CLIENT_ID, FEED_TOKEN, max_retry_attempt=0)

   

    # CSV for Live Data
    csv_filename = 'option_chain.csv'
    if os.path.exists(csv_filename):
        os.remove(csv_filename)
    pd.DataFrame(columns=["time_str", "token", "ltp"]).to_csv(csv_filename, index=False)

    # WebSocket Data Handler
    def on_data(wsapp, message):
        time_str = datetime.datetime.fromtimestamp(message.get('exchange_timestamp') / 1000).strftime('%H:%M:%S')
        token = str(message.get('token'))
        ltp = message.get('last_traded_price')

    

        with open(csv_filename, "a") as f:
            f.write(f"{time_str},{token},{ltp}\n")

        logger.info(f"Live Data: {message}")
      
    def on_open(wsapp):
        logger.info("WebSocket Opened. Subscribing to tokens...")
        ws.subscribe(correlation_id, mode, token_list)
        logger.info("Subscription complete")

    def on_error(wsapp, error):
        logger.error(f"WebSocket Error: {error}")

    def on_close(wsapp):
        logger.warning("WebSocket Connection Closed")

    ws.on_open = on_open
    ws.on_data = on_data
    ws.on_error = on_error
    ws.on_close = on_close


    ws_thread = threading.Thread(target=ws.connect)
    ws_thread.daemon = True
    ws_thread.start()

    # Create Two Subplots for Call & Put Prices
    fig, ax1 = plt.subplots()
    call_plot, = ax1.plot([], [], 'go-', label="Call Option Price")
    ax1.set_ylabel("Call Price")
    ax1.legend()
    ax1.grid()
    
    # Initialize Line Plots
    # call_plot, = ax1.plot([], [], 'go-', label="Call Option Price")
    # put_plot, = ax2.plot([], [], 'ro-', label="Put Option Price")
    
    
    

    # Animation Function
    def animate(i):
        
        df = pd.read_csv(csv_filename)
        if not df.empty:
           
            call_plot.set_data(df['time_str'],df['ltp'])
            
            
            ax1.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))  
            ax1.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            plt.tight_layout()

    # Run Animation
    ani = animation.FuncAnimation(fig, animate, interval=1000, cache_frame_data=False) 
   
    plt.show()

else:
    print("No valid option tokens found. WebSocket will not start.")
