import enoslib as en
import time
import re
import sys

en.init_logging(level=en.logging.INFO)

# --- CONFIGURATION ---
# Note: Since you are already reserved, we use the Host objects directly
roles = {
    "n1": [en.Host("paradoxe-11.rennes.grid5000.fr", user="root")],
    "n2": [en.Host("paradoxe-12.rennes.grid5000.fr", user="root")],
    "n3": [en.Host("paradoxe-13.rennes.grid5000.fr", user="root")]
}
all_hosts = roles["n1"] + roles["n2"] + roles["n3"]

# 1. Get Numeric IPs (Ensures distribution works over the network)
def get_ip(role):
    res = en.run_command("hostname -I | awk '{print $1}'", roles=role)
    return res[0].stdout.strip()

print("Detecting numeric IPs...")
ip1 = get_ip(roles["n1"])
ip2 = get_ip(roles["n2"])
ip3 = get_ip(roles["n3"])

print(f"IPs detected: n1={ip1} (Worker), n2={ip2} (Master), n3={ip3} (Worker 2)")

# 2. Sync Code
print("\n--- Updating Code from GitHub ---")
en.run_command("pkill -9 beam || true", roles=all_hosts)
en.run_command("cd /root/bench && git fetch --all && git reset --hard origin/main", roles=all_hosts)

results = []

def run_elixir_test(name, file_name, master_args):
    print(f"\n>>> STARTING {name} ({file_name})")
    # Ensure a clean state for every test
    en.run_command("pkill -9 beam || true", roles=all_hosts)
    
    # Start Worker on Node 1
    print(f"Starting Worker on Node 1 ({ip1})...")
    en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name worker@{ip1} --cookie monster {file_name} worker", 
                   roles=roles["n1"], background=True)
    
    # Trapezoid needs an extra worker on Node 3
    if "trapezoid" in file_name.lower():
        print(f"Starting Second Worker on Node 3 ({ip3})...")
        en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name worker@{ip3} --cookie monster {file_name} worker", 
                       roles=roles["n3"], background=True)
    
    time.sleep(5) # Give the BEAM VM time to initialize network

    # Start Master on Node 2 (Removed 'timeout' to fix the error)
    print(f"Executing Master on Node 2 ({ip2})...")
    res = en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name master@{ip2} --cookie monster {file_name} {master_args}", 
                         roles=roles["n2"])
    
    output = res[0].stdout
    print(output)
    
    # Extract timestamps using Regex
    start = re.search(r"LOG_START:(\d+)", output)
    end = re.search(r"LOG_END:(\d+)", output)
    
    results.append({
        "name": name,
        "start": start.group(1) if start else "N/A",
        "end": end.group(1) if end else "N/A"
    })
    
    print(f"<<< {name} FINISHED. Cooling down...")
    time.sleep(10)

# --- 3. RUN ALL TESTS ---

# Note: master_args for Spawn/Message use worker@{ip1}
# master_args for Trapezoid use worker@{ip1} worker@{ip3}

run_elixir_test("SPAWN", "DistSpawner.exs", f"master worker@{ip1}")
run_elixir_test("MESSAGE", "dist_message.exs", f"master worker@{ip1}")
run_elixir_test("TRAPEZOID", "dist_trapezoid.exs", f"master worker@{ip1} worker@{ip3}")

# --- FINAL SUMMARY TABLE ---
print("\n" + "="*60)
print(f"{'Benchmark':<15} | {'LOG_START':<18} | {'LOG_END':<18}")
print("-" * 60)
for r in results:
    print(f"{r['name']:<15} | {r['start']:<18} | {r['end']:<18}")
print("="*60)