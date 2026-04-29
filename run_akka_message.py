import enoslib as en
import time

en.init_logging(level=en.logging.INFO)

print("Connecting to neowise nodes...")

roles = {
    "n1":[en.Host("paradoxe-11.rennes.grid5000.fr", user="root")],
    "n2":[en.Host("paradoxe-12.rennes.grid5000.fr", user="root")],
    "n3":[en.Host("paradoxe-13.rennes.grid5000.fr", user="root")]
}

all_hosts = roles["n1"] + roles["n2"] + roles["n3"]

def get_ip(host_role):
    res = en.run_command("hostname -I | awk '{print $1}'", roles=host_role)
    return res[0].stdout.strip()

print("Detecting numeric IPs...")
ip1 = get_ip(roles["n1"])
ip2 = get_ip(roles["n2"])

# --- 1. PREPARE ---
print("\n--- Syncing and Pre-downloading Dependencies ---")
en.run_command("pkill -9 java || true", roles=all_hosts)
# Force reset and pull
en.run_command("cd /root/bench && git fetch --all && git reset --hard origin/main", roles=all_hosts)
# Resolve all dependencies now so they don't download during the benchmark
en.run_command("cd /root/bench && mvn dependency:go-offline", roles=all_hosts)
en.run_command("cd /root/bench && mvn compile", roles=all_hosts)

# --- 2. START PONGERS ---
print(f"\n--- Starting Ponger (Seed) on {ip1} ---")
en.run_command(
    f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.MessageRun' "
    f"-Dexec.args='2551 {ip1} {ip1}' > akka_ponger.log 2>&1", 
    roles=roles["n1"], 
    background=True
)

# Wait long enough for Maven to initialize and the port to open
print("Waiting 45 seconds for Akka to boot...")
time.sleep(45)

# --- 3. START PINGER ---
print(f"--- Starting Pinger (Master) on {ip2} ---")
master_cmd = (
    f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.MessageRun' "
    f"-Dexec.args='2552 {ip2} {ip1}'"
)

# REMOVED timeout=400 to fix the EnosLib error
res = en.run_command(master_cmd, roles=roles["n2"])

print("\n" + "="*40)
print("AKKA BENCHMARK RESULT")
print("="*40)
print(res[0].stdout)

# Cleanup
en.run_command("pkill -9 java || true", roles=all_hosts)