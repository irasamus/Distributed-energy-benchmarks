import enoslib as en
import time
import re

# 1. Setup logging
en.init_logging(level=en.logging.INFO)

# --- CONFIGURATION ---
REPO_URL = "https://github.com/irasamus/Distributed-energy-benchmarks"
JOB_NAME = "energy_dist_all"

# Paradoxe Cluster Nodes 3, 4, and 5
conf = (
    en.G5kConf.from_settings(job_name=JOB_NAME, job_type=["deploy"], env_name="ubuntu2204-x64-min", walltime="05:00:00")
    .add_machine(roles=["n3"], servers=["paradoxe-16.rennes.grid5000.fr"])
    .add_machine(roles=["n4"], servers=["paradoxe-17.rennes.grid5000.fr"])
    .add_machine(roles=["n5"], servers=["paradoxe-18.rennes.grid5000.fr"])
)

provider = en.G5k(conf)
roles, _ = provider.init()

# Get IPs for networking
ip3 = roles["n3"][0].address
ip4 = roles["n4"][0].address
ip5 = roles["n5"][0].address

print(f"IPs: Node3={ip3}, Node4={ip4}, Node5={ip5}")

# --- STEP 2: INSTALLATION ---
print("Preparing nodes...")
en.run_command("apt-get update && apt-get install -y git openjdk-11-jdk maven elixir", roles=roles)
en.run_command(f"rm -rf /root/bench && git clone {REPO_URL} /root/bench", roles=roles)
en.run_command("cd /root/bench && mvn compile", roles=roles)

results_table = []

def record_result(bench_name, lang, output):
    """Parses LOG_START and LOG_END from stdout."""
    start = re.search(r"LOG_START:(\d+)", output)
    end = re.search(r"LOG_END:(\d+)", output)
    results_table.append({
        "name": bench_name,
        "lang": lang,
        "start": start.group(1) if start else "N/A",
        "end": end.group(1) if end else "N/A"
    })

# ==============================================================================
# AKKA RUNS
# ==============================================================================

# 1. Akka Spawn
print("Running Akka Spawn...")
en.run_command(f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.SpawnRunner' -Dexec.args='2551 {ip3} {ip3}'", roles=roles["n3"], background=True)
time.sleep(5)
res = en.run_command(f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.SpawnRunner' -Dexec.args='2552 {ip5} {ip3}'", roles=roles["n5"])
record_result("Spawn", "Akka", res[0].stdout)
en.run_command("pkill -9 java", roles=roles)
time.sleep(5)

# 2. Akka Message
print("Running Akka Message Passing...")
en.run_command(f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.MessageRun' -Dexec.args='2551 {ip3} {ip3}'", roles=roles["n3"], background=True)
time.sleep(5)
res = en.run_command(f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.MessageRun' -Dexec.args='2552 {ip5} {ip3}'", roles=roles["n5"])
record_result("Message", "Akka", res[0].stdout)
en.run_command("pkill -9 java", roles=roles)
time.sleep(5)

# 3. Akka Trapezoid
print("Running Akka Trapezoid...")
en.run_command(f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.TrapezoidRun' -Dexec.args='2551 {ip3} {ip3}'", roles=roles["n3"], background=True)
en.run_command(f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.TrapezoidRun' -Dexec.args='2553 {ip4} {ip3}'", roles=roles["n4"], background=True)
time.sleep(5)
res = en.run_command(f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.TrapezoidRun' -Dexec.args='2552 {ip5} {ip3}'", roles=roles["n5"])
record_result("Trapezoid", "Akka", res[0].stdout)
en.run_command("pkill -9 java", roles=roles)
time.sleep(5)

# ==============================================================================
# ELIXIR RUNS
# ==============================================================================

# 4. Elixir Spawn
print("Running Elixir Spawn...")
en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name worker@{ip3} --cookie monster DistSpawner.exs worker", roles=roles["n3"], background=True)
time.sleep(5)
res = en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name master@{ip5} --cookie monster DistSpawner.exs master worker@{ip3}", roles=roles["n5"])
record_result("Spawn", "Elixir", res[0].stdout)
en.run_command("pkill -9 beam", roles=roles)
time.sleep(5)

# 5. Elixir Message
print("Running Elixir Message Passing...")
en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name worker@{ip3} --cookie monster dist_message.exs worker", roles=roles["n3"], background=True)
time.sleep(5)
res = en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name master@{ip5} --cookie monster dist_message.exs master worker@{ip3}", roles=roles["n5"])
record_result("Message", "Elixir", res[0].stdout)
en.run_command("pkill -9 beam", roles=roles)
time.sleep(5)

# 6. Elixir Trapezoid
print("Running Elixir Trapezoid...")
en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name node_b@{ip3} --cookie monster dist_trapezoid.exs worker", roles=roles["n3"], background=True)
en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name node_c@{ip4} --cookie monster dist_trapezoid.exs worker", roles=roles["n4"], background=True)
time.sleep(5)
res = en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name master@{ip5} --cookie monster dist_trapezoid.exs master node_b@{ip3} node_c@{ip4}", roles=roles["n5"])
record_result("Trapezoid", "Elixir", res[0].stdout)
en.run_command("pkill -9 beam", roles=roles)

# --- FINAL SUMMARY TABLE ---
print("\n" + "="*80)
print(f"{'Benchmark':<15} | {'Lang':<10} | {'LOG_START':<15} | {'LOG_END':<15}")
print("-" * 80)
for r in results_table:
    print(f"{r['name']:<15} | {r['lang']:<10} | {r['start']:<15} | {r['end']:<15}")
print("="*80)