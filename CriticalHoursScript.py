import requests
import pandas as pd
import matplotlib.pyplot as plt

# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------
API_KEY = "7C2hquSoT4uP5fYrCcQcqp5MJF17ivMGvPnEeOuF"   # Replace with personal API key
BASE_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"

START_DATE = "2025-09-01T00"  
END_DATE   = "2025-09-27T23"  

CriticalNum = 0.94  #determines SORM -> SORM = 1 - CriticalNum

# --------------------------------------------------------
# GET FUNCTION
# --------------------------------------------------------
def get_eia_data(series_type, start=START_DATE, end=END_DATE):
    all_data = []
    offset = 0
    page_size = 5000  # maximum rows per request (EIA cap kinda lame ;[ ))

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

        # grab this page of data
        data = response_json.get("data", [])
        if not data:
            break  # stop when no more rows

        all_data.extend(data)

        # if we got less than a full page, we're done
        if len(data) < page_size:
            break

        # move offset forward
        offset += page_size

    # convert to DataFrame
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

# --------------------------------------------------------
# PER-HOUR TABLE WITH DIFFERENCE
# --------------------------------------------------------

# Drop duplicate timestamps to avoid concat error
demand = demand[~demand.index.duplicated(keep="first")]
gen    = gen[~gen.index.duplicated(keep="first")]

hourly_df = pd.concat([demand, gen], axis=1)
hourly_df["Diff"] = hourly_df["NG"] - hourly_df["D"]

# Add day and hour columns for clarity
hourly_df["Day"] = hourly_df.index.date
hourly_df["Hour"] = hourly_df.index.hour

print("\nHourly Demand, Generation, and Difference:")
print(hourly_df.head(48))  # preview first day

# --------------------------------------------------------
# DAILY SUMMARIES
# --------------------------------------------------------
daily_totals = hourly_df.resample("D").sum(numeric_only=True)[["D", "NG", "Diff"]]

print("\nDaily Totals (MWh):")
print(daily_totals)

# --------------------------------------------------------
# CRITICAL EVENTS: Demand >= num% of Generation
# --------------------------------------------------------
hourly_df["CloseToLimit"] = hourly_df["D"] >= CriticalNum * hourly_df["NG"]
num = CriticalNum * 100
count_events = hourly_df["CloseToLimit"].sum()
print(f"\nNumber of hours where demand >= {num}% of generation: {count_events}")

# (Optional) show the times it happens
events_df = hourly_df[hourly_df["CloseToLimit"]]
print(f"\nOccurrences where demand >= {num}% of generation:")
print(events_df[["D", "NG", "Diff"]].head(10))  # show first 10 matches

# --------------------------------------------------------
# SAVE DATA TO CSV
# --------------------------------------------------------

# Save hourly data
hourly_df.to_csv("hourly_demand_generation.csv", index=True)
print("Hourly data saved to hourly_demand_generation.csv")

# Save daily totals
daily_totals.to_csv("daily_totals.csv", index=True)
print("Daily totals saved to daily_totals.csv")

# (Optional) Save the events where demand >= 95% of generation
events_df = hourly_df[hourly_df["CloseToLimit"]]
events_df.to_csv("high_demand_events.csv", index=True)
print("High demand events saved to high_demand_events.csv")

# --------------------------------------------------------
# PLOT: Hourly Demand vs Generation with Highlighted Events
# --------------------------------------------------------
fig, ax1 = plt.subplots(figsize=(12,6))

# Plot demand and generation
ax1.plot(hourly_df.index, hourly_df["D"], label="Demand (MW)", color="blue")
ax1.plot(hourly_df.index, hourly_df["NG"], label="Generation (MW)", color="orange")

# Highlight points where demand >= 95% of generation
events = hourly_df[hourly_df["CloseToLimit"]]
label = (f"≥ {num}% of Gen")
ax1.scatter(events.index, events["D"], color="red", label=label, zorder=5)

ax1.set_xlabel("Time")
ax1.set_ylabel("MW")
ax1.legend(loc="upper left")

plt.title("Hourly Demand vs Generation (US48)")
plt.tight_layout()
plt.show()

