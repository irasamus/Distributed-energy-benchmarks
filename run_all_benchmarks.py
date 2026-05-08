import enoslib as en
import time
import re

en.init_logging(level=en.logging.INFO)

# --- 1. CONFIGURATION ---
# Connect to your already reserved Paradoxe nodes
roles = {
    "n1": [en.Host("paradoxe-11.rennes.grid5000.fr", user="root")], # Seed/Worker 1
    "n2": [en.Host("paradoxe-12.rennes.grid5000.fr", user="root")], # Master
    "n3": [en.Host("paradoxe-13.rennes.grid5000.fr", user="root")]  # Worker 2
}
all_hosts = roles["n1"] + roles["n2"] + roles["n3"]
SETTLE_TIME = 15  # Time between runs to see clear gaps in Kwollect

def get_ip(role):
    res = en.run_command("hostname -I | awk '{print $1}'", roles=role)
    return res[0].stdout.strip()

print("Detecting IPs and Syncing Code...")
ip1, ip2, ip3 = get_ip(roles["n1"]), get_ip(roles["n2"]), get_ip(roles["n3"])

# Initial Sync and Maven Prep (Online)
en.run_command("pkill -9 java || true; pkill -9 beam || true", roles=all_hosts)
en.run_command("cd /root/bench && git fetch --all && git reset --hard origin/main", roles=all_hosts)
# Pre-compile so Maven is "warm" and doesn't download during the test
en.run_command("cd /root/bench && mvn compile", roles=all_hosts)

results = []

def record(lang, bench, iteration, output):
    start = re.search(r"LOG_START:(\d+)", output)
    end = re.search(r"LOG_END:(\d+)", output)
    results.append({
        "lang": lang, "bench": bench, "iter": iteration,
        "start": start.group(1) if start else "N/A",
        "end": end.group(1) if end else "N/A"
    })

# --- BENCHMARK DEFINITIONS ---
# Note: Ensure these filenames match your GitHub exactly
akka_benchmarks = [
    {"name": "Spawn",     "class": "com.example.SpawnRunner", "extra": False},
    {"name": "Message",   "class": "com.example.MessageRun",  "extra": False},
    {"name": "Trapezoid", "class": "com.example.TrapezoidRun","extra": True}
]

elixir_benchmarks = [
    {"name": "Spawn",     "file": "DistSpawner.exs",   "args": f"master worker@{ip1}", "extra": False},
    {"name": "Message",   "file": "dist_message.exs",  "args": f"master worker@{ip1}", "extra": False},
    {"name": "Trapezoid", "file": "dist_trapezoid.exs", "args": f"master node_b@{ip1} node_c@{ip3}", "extra": True}
]

# --- 2. EXECUTION LOOP ---
for i in range(1, 4):
    print(f"\n####### STARTING ITERATION {i} #######")
    
    # A. AKKA RUNS
    for b in akka_benchmarks:
        print(f"Running Akka {b['name']} (Iter {i})...")
        en.run_command("pkill -9 java || true", roles=all_hosts)
        
        # Start Seed
        en.run_command(f"cd /root/bench && mvn exec:java --offline -Dexec.mainClass='{b['class']}' -Dexec.args='2551 {ip1} {ip1}' > s.log 2>&1", roles=roles["n1"], background=True)
        # Start Worker 2 for Trapezoid
        if b['extra']:
            en.run_command(f"cd /root/bench && mvn exec:java --offline -Dexec.mainClass='{b['class']}' -Dexec.args='2553 {ip3} {ip1}' > w.log 2>&1", roles=roles["n3"], background=True)
        
        time.sleep(45) # Akka cluster boot time
        res = en.run_command(f"cd /root/bench && mvn exec:java --offline -Dexec.mainClass='{b['class']}' -Dexec.args='2552 {ip2} {ip1}'", roles=roles["n2"])
        record("Akka", b['name'], i, res[0].stdout)
        time.sleep(SETTLE_TIME)

    # B. ELIXIR RUNS
    for b in elixir_benchmarks:
        print(f"Running Elixir {b['name']} (Iter {i})...")
        en.run_command("pkill -9 beam || true", roles=all_hosts)
        elx_path = "/root/bench/elixir_benchmarks"
        
        # Start Worker 1 (n1)
        # Use node_b for trapezoid consistency, worker for others
        name = "node_b" if b['name'] == "Trapezoid" else "worker"
        en.run_command(f"cd {elx_path} && elixir --name {name}@{ip1} --cookie monster {b['file']} worker", roles=roles["n1"], background=True)
        
        if b['extra']:
            en.run_command(f"cd {elx_path} && elixir --name node_c@{ip3} --cookie monster {b['file']} worker", roles=roles["n3"], background=True)
            
        time.sleep(5)
        res = en.run_command(f"cd {elx_path} && elixir --name master@{ip2} --cookie monster {b['file']} {b['args']}", roles=roles["n2"])
        record("Elixir", b['name'], i, res[0].stdout)
        time.sleep(SETTLE_TIME)

# --- 3. FINAL SUMMARY TABLE ---
print("\n" + "="*85)
print(f"{'Lang':<8} | {'Benchmark':<12} | {'Iter':<6} | {'LOG_START':<18} | {'LOG_END'}")
print("-" * 85)
for r in results:
    print(f"{r['lang']:<8} | {r['bench']:<12} | {r['iter']:<6} | {r['start']:<18} | {r['end']}")
print("="*85)