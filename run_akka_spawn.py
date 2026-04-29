import enoslib as en
import time

en.init_logging(level=en.logging.INFO)

# Connect to your already reserved nodes
roles = {
    "n1":[en.Host("neowise-1.lyon.grid5000.fr", user="root")],
    "n2":[en.Host("neowise-2.lyon.grid5000.fr", user="root")]
}

print("Detecting numeric IPs...")
ip1 = en.run_command("hostname -I | awk '{print $1}'", roles=roles["n1"])[0].stdout.strip()
ip2 = en.run_command("hostname -I | awk '{print $1}'", roles=roles["n2"])[0].stdout.strip()

print(f"Seed (Node 1): {ip1} | Master (Node 2): {ip2}")

# --- CLEANUP ONLY (Skip Git to avoid the TLS error) ---
print("\n--- Cleaning up old processes ---")
en.run_command("pkill -9 java || true", roles=roles["n1"] + roles["n2"])

# --- START SEED (NODE 1) ---
print(f"\n--- Starting Akka Seed on {ip1} ---")
# We redirect output so we can check it if the master hangs
en.run_command(
    f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.AppRunner' "
    f"-Dexec.args='2551 {ip1} {ip1}' > /root/bench/akka_seed.log 2>&1", 
    roles=roles["n1"], 
    background=True
)

# Give Maven and Akka plenty of time to boot the cluster
print("Waiting 45 seconds for Akka to boot on Node 1...")
time.sleep(45)

# --- START MASTER (NODE 2) ---
print(f"--- Starting Akka Master on {ip2} ---")
master_cmd = (
    f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.AppRunner' "
    f"-Dexec.args='2552 {ip2} {ip1}'"
)

try:
    # 1,000,000 spawns takes ~2 minutes, so we set timeout to 5 minutes
    res = en.run_command(master_cmd, roles=roles["n2"], timeout=300)
    
    print("\n" + "="*40)
    print("AKKA BENCHMARK RESULT")
    print("="*40)
    print(res[0].stdout)
    
except Exception as e:
    print(f"\nAkka Master did not finish: {e}")
    print("\n--- LAST 20 LINES OF SEED LOG FROM NODE 1 ---")
    # This will tell us if Node 1 actually started or crashed
    logs = en.run_command("tail -n 20 /root/bench/akka_seed.log", roles=roles["n1"])
    print(logs[0].stdout)

# Clean up after test
en.run_command("pkill -9 java || true", roles=roles["n1"] + roles["n2"])