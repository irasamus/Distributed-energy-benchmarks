import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import getpass
import numpy as np
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
USER = "isamus"
SITE = "rennes"
NODES = ["paradoxe-11", "paradoxe-12", "paradoxe-13"]
RESULTS_DIR = "/Users/Irinawork/projects/distributed_benchmarks/energy_results"

if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

# Data from your latest high-count logs
experiments = [
    ("Akka", "Spawn",     1778164206314, 1778164445731, ["paradoxe-11", "paradoxe-12"]),
    ("Akka", "Message",   1778166862870, 1778168968348, ["paradoxe-11", "paradoxe-12"]),
    ("Akka", "Trapezoid", 1778169010128, 1778169010893, ["paradoxe-11", "paradoxe-12", "paradoxe-13"]),
    
    ("Elixir", "Spawn",     1778163696412, 1778163745616, ["paradoxe-11", "paradoxe-12"]),
    ("Elixir", "Message",   1778163766165, 1778163933273, ["paradoxe-11", "paradoxe-12"]),
    ("Elixir", "Trapezoid", 1778163955429, 1778163956322, ["paradoxe-11", "paradoxe-12", "paradoxe-13"])
]

def fetch_and_save_data(pwd):
    """Downloads raw power data and converts timestamps to floats."""
    min_start = min([ex[2] for ex in experiments]) / 1000
    max_end = max([ex[3] for ex in experiments]) / 1000

    print(f"Requesting metrics from {SITE}...")
    nodes_str = ",".join(NODES)
    url = f"https://api.grid5000.fr/stable/sites/{SITE}/metrics"
    
    params = {
        "nodes": nodes_str,
        "metrics": "wattmetre_power_watt",
        "start_time": int(min_start) - 10,
        "end_time": int(max_end) + 10
    }
    
    try:
        res = requests.get(url, params=params, auth=(USER, pwd))
        res.raise_for_status()
        raw_data = res.json()
        
        # Save raw JSON
        json_path = os.path.join(RESULTS_DIR, "raw_kwollect_data.json")
        with open(json_path, "w") as f:
            json.dump(raw_data, f)
        
        all_points = []
        for point in raw_data:
            node_name = point.get("device_id", point.get("node_id", "unknown")).split('.')[0]
            
            # FIX: Convert ISO string timestamp to Unix Float
            # The API returns "2026-05-04T22:27:36Z", we need 1778163696.0
            ts_str = point["timestamp"].replace('Z', '+00:00')
            ts_float = datetime.fromisoformat(ts_str).timestamp()
            
            all_points.append({
                "node": node_name,
                "ts": ts_float,
                "val": point["value"]
            })
        
        df = pd.DataFrame(all_points)
        print(f"Successfully processed {len(df)} points.")
        return df
            
    except Exception as e:
        print(f"Error: {e}")
        return pd.DataFrame()

def analyze_and_plot(df):
    results = []
    plot_profiles = []

    # Calculate Average Idle Power per node to subtract (Scientific Baseline)
    # We take the first 5 seconds of the whole dataset as baseline
    baselines = df[df['ts'] < df['ts'].min() + 5].groupby('node')['val'].mean().to_dict()
    print(f"Node Idle Baselines (Watts): {baselines}")

    for lang, bench, start_ms, end_ms, involved in experiments:
        s_sec, e_sec = start_ms / 1000, end_ms / 1000
        
        mask = (df['ts'] >= s_sec) & (df['ts'] <= e_sec) & (df['node'].isin(involved))
        bench_df = df[mask].sort_values('ts')
        
        if bench_df.empty:
            continue

        # Group by timestamp and sum (Total Cluster Power)
        summed_power = bench_df.groupby('ts')['val'].sum().reset_index()
        
        # Calculate Energy (Joules)
        # We use the timestamps (ts) as the x-axis for integration
        joules = np.trapz(summed_power['val'], summed_power['ts'])
        
        results.append({
            "Language": lang, 
            "Benchmark": bench, 
            "Joules": round(joules, 2), 
            "Duration_Sec": round(e_sec - s_sec, 2)
        })

        summed_power['Benchmark'] = bench
        summed_power['Language'] = lang
        summed_power['Relative_Time'] = summed_power['ts'] - summed_power['ts'].min()
        plot_profiles.append(summed_power)

    df_results = pd.DataFrame(results)
    
    # --- PLOTTING ---
    sns.set_theme(style="whitegrid")
    
    # 1. Bar Chart
    plt.figure(figsize=(10, 6))
    g = sns.catplot(
        data=df_results, kind="bar", x="Language", y="Joules", col="Benchmark",
        palette={"Akka": "#0000FF", "Elixir": "#FF0000"}, sharey=False
    )
    plt.savefig(os.path.join(RESULTS_DIR, "distributed_joules.png"), bbox_inches='tight')

    # 2. Line Chart
    df_lines = pd.concat(plot_profiles)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    for i, name in enumerate(["Spawn", "Message", "Trapezoid"]):
        subset = df_lines[df_lines['Benchmark'] == name]
        sns.lineplot(ax=axes[i], data=subset, x="Relative_Time", y="val", hue="Language", palette={"Akka": "blue", "Elixir": "red"})
        axes[i].set_title(f"Cluster Power Profile: {name}")
        axes[i].set_ylabel("Watts (Summed)")

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "distributed_power_profiles.png"))
    
    print("\nFINAL ENERGY TABLE (CLUSTER SUM):")
    print(df_results.sort_values(["Benchmark", "Language"]))

if __name__ == "__main__":
    pwd = getpass.getpass(f"Enter Grid5000 password for {USER}: ")
    raw_df = fetch_and_save_data(pwd)
    if not raw_df.empty:
        analyze_and_plot(raw_df)