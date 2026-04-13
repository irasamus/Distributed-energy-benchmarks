import enoslib as en
import time
import sys

# --- CONFIGURATION ---
JOB_ID = 3670507
en.init_logging(level=en.logging.INFO)

# 1. Correct way to re-attach to an existing job to get the roles
print(f"Re-attaching to Job ID: {JOB_ID}...")
try:
    # This function fetches the roles directly from the G5K API for that job
    roles, networks = en.api.get_roles_and_networks(job_id=JOB_ID, provider_type="g5k")
except Exception as e:
    print(f"Failed to re-attach. Is the Job ID correct and still running? Error: {e}")
    sys.exit(1)

# 2. Get the addresses for Node 3 and Node 5
# In EnosLib, .address gives the hostname (e.g., paradoxe-3.rennes.grid5000.fr)
# Grid'5000 internal DNS handles these hostnames as IPs, which Akka accepts.
host3 = roles["n3"][0].address
host5 = roles["n5"][0].address

print(f"\n--- DEBUG INFO ---")
print(f"Node 3 (Seed) Hostname: {host3}")
print(f"Node 5 (Master) Hostname: {host5}")

# --- STEP 3: PRE-FLIGHT CHECK ---
print("\n--- Testing Network Path (Ping from Node 5 to Node 3) ---")
en.run_command(f"ping -c 3 {host3}", roles=roles["n5"])

# Kill any old java processes to start fresh
print("Cleaning up old Java processes...")
en.run_command("pkill -9 java", roles=roles)

# --- STEP 4: START SEED (NODE 3) ---
print("\n--- Starting Spawner (Seed) on Node 3 ---")
# We use background=True. We also use 'mvn compile' first just in case.
en.run_command(
    f"cd /root/bench && mvn compile && mvn exec:java -Dexec.mainClass='com.example.SpawnRunner' "
    f"-Dexec.args='2551 {host3} {host3}' > seed_output.log 2>&1", 
    roles=roles["n3"], 
    background=True
)

print("Waiting 20 seconds for Maven to build and port 2551 to open...")
time.sleep(20)

# --- STEP 5: PORT CHECK ---
print("\n--- Checking if Node 5 can see Node 3's port 2551 ---")
# nc (netcat) -z means scan, -v means verbose. 
port_check = en.run_command(f"nc -zv {host3} 2551", roles=roles["n5"])
# Note: nc prints its success message to stderr
print(f"Port check result: {port_check[0].stderr.strip()}")

# --- STEP 6: START MASTER (NODE 5) ---
print("\n--- Starting Master on Node 5 (LOOK HERE FOR OUTPUT) ---")
# We run this in the foreground so we see the logs live
res = en.run_command(
    f"cd /root/bench && mvn exec:java -Dexec.mainClass='com.example.SpawnRunner' "
    f"-Dexec.args='2552 {host5} {host3}'", 
    roles=roles["n5"]
)

# Print everything the Master said
print("\n--- MASTER STDOUT ---")
print(res[0].stdout)
print("\n--- MASTER STDERR ---")
print(res[0].stderr)

# --- STEP 7: INSPECT SEED IF HANGS ---
if "LOG_START" not in res[0].stdout:
    print("\n--- Master did not start work. Checking Seed Node Logs... ---")
    seed_logs = en.run_command("cat /root/bench/seed_output.log", roles=roles["n3"])
    print(seed_logs[0].stdout)