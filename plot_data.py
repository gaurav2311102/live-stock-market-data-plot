import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.ticker as mticker  


print("\nSelect Market Index:")
print("1. NIFTY 50")
print("2. SENSEX")
index_choice = input("Enter your choice (1 or 2): ").strip()

if index_choice == "1":
    title = "Market Data - NIFTY 50"
    ylabel = "Price (INR)"
elif index_choice == "2":
    title = "Market Data - SENSEX"
    ylabel = "Price (INR)"
else:
    print("Invalid choice! Please enter 1 or 2.")
    exit()


csv_filename = "live_data.csv"
df = pd.read_csv(csv_filename)


df["time"] = df["time"].astype(str)


# df = df.tail(50)

plt.figure(figsize=(10, 5))
plt.plot(df["time"], df["ltp"], marker=".", linestyle="-", color="blue", label=title)

plt.title(title)
plt.xlabel("Time")
plt.ylabel(ylabel)


plt.xticks(df["time"][::20], rotation=45)  



ax = plt.gca()  
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.2f}"))

# ax.set_xticks(df.index[::10])  # Set tick positions at every 10th entry
# ax.set_xticklabels(df["time"][::10], rotation=45)  # Set labels at those positions

plt.legend()
plt.grid(True)
plt.show()
