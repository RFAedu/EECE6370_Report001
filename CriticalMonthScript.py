import requests
import pandas as pd
import matplotlib.pyplot as plt
import os

# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------
API_KEY = "7C2hquSoT4uP5fYrCcQcqp5MJF17ivMGvPnEeOuF"  # Replace with your API key
BASE_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"

START_DATE = "2023-01-01T00"  
END_DATE   = "2023-12-31T23"  

CriticalNum = 0.94  # determines SORM -> SORM = 1 - CriticalNum

# Folder to save monthly plots
os.makedirs("monthly_plots", exist_ok=True)

# --------------------------------------------------------
# GET FUNCTION
# --------------------------------------------------------
def get_eia_data(series_type, start=START_DATE, end=END_DATE):
    all_data = []
    offset = 0
    page_size = 5000 #maximum length of data (lame)

    while True:
        params = [
            ("api_key", API_KEY),
            ("frequency", "hourly"),
            ("data[0]", "value"),
            ("facets[type][]", series_type),
            ("start", start),
            ("end", end),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
            ("offset", offset),
            ("length", page_size)
        ]
        r = requests.get(BASE_URL, params=params)
        r.raise_for_status()
        response_json = r.json()["response"]

        data = response_json.get("data", [])
        if not data:
            break

        all_data.extend(data)

        if len(data) < page_size:
            break

        offset += page_size

    df = pd.DataFrame(all_data)
    df["datetime"] = pd.to_datetime(df["period"])
    df = df[["datetime", "value"]].rename(columns={"value": series_type})
    df.set_index("datetime", inplace=True)
    df = df.astype(float)
    return df

# --------------------------------------------------------
# FETCH DATA
# --------------------------------------------------------
demand = get_eia_data("D")
gen    = get_eia_data("NG")

# Remove duplicate timestamps, it all gets messed up if you dont
demand = demand[~demand.index.duplicated(keep="first")]
gen    = gen[~gen.index.duplicated(keep="first")]

hourly_df = pd.concat([demand, gen], axis=1)
hourly_df["Diff"] = hourly_df["NG"] - hourly_df["D"]
hourly_df["Day"] = hourly_df.index.date
hourly_df["Hour"] = hourly_df.index.hour

# --------------------------------------------------------
# DAILY TOTALS
# --------------------------------------------------------
daily_totals = hourly_df.resample("D").sum(numeric_only=True)[["D", "NG", "Diff"]]

# --------------------------------------------------------
# CRITICAL EVENTS
# --------------------------------------------------------
hourly_df["CloseToLimit"] = hourly_df["D"] >= CriticalNum * hourly_df["NG"]
num = CriticalNum * 100

critical_events = hourly_df[hourly_df["CloseToLimit"]].copy()
critical_events["Month"] = critical_events.index.to_period("M")

# --------------------------------------------------------
# SAVE CSV FILES - good enough
# --------------------------------------------------------
hourly_df.to_csv("hourly_demand_generation.csv", index=True)
daily_totals.to_csv("daily_totals.csv", index=True)
print("Hourly and daily totals saved.")

# Save monthly critical events CSVs
for month, month_df in critical_events.groupby("Month"):
    filename = f"high_demand_events_{month}.csv"
    month_df.to_csv(filename, index=True)
    print(f"Saved {filename} with {len(month_df)} events")

# --------------------------------------------------------
# PLOT MONTHLY GRAPHS - doesnt work, not sure why
# --------------------------------------------------------
"""
for month_start, month_df in hourly_df.resample("M"):
    fig, ax = plt.subplots(figsize=(12,6))
    
    # Plot demand and generation
    ax.plot(month_df.index, month_df["D"], label="Demand (MW)", color="blue")
    ax.plot(month_df.index, month_df["NG"], label="Generation (MW)", color="orange")
    
    # Highlight critical events
    month_events = month_df[month_df["CloseToLimit"]]
    ax.scatter(month_events.index, month_events["D"], color="red", label=f"≥ {num}% of Gen", zorder=5)
    
    # Labels and title
    ax.set_xlabel("Time")
    ax.set_ylabel("MW")
    title_month = month_start.strftime("%Y-%m")
    ax.set_title(f"Hourly Demand vs Generation: {title_month}")
    ax.legend(loc="upper left")
    
    plt.tight_layout()
    
    # Save figure
    plot_filename = f"monthly_plots/hourly_demand_gen_{title_month}.png"
    fig.savefig(plot_filename)
    plt.close(fig)
    print(f"Saved plot: {plot_filename}")
"""

