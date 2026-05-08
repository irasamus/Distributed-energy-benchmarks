import enoslib as en
import time
import re

en.init_logging(level=en.logging.INFO)

roles = {
    "n1": [en.Host("paradoxe-11.rennes.grid5000.fr", user="root")],
    "n2": [en.Host("paradoxe-12.rennes.grid5000.fr", user="root")],
    "n3": [en.Host("paradoxe-13.rennes.grid5000.fr", user="root")]
}
all_hosts = roles["n1"] + roles["n2"] + roles["n3"]

def get_ip(role):
    res = en.run_command("hostname -I | awk '{print $1}'", roles=role)
    return res[0].stdout.strip()

ip1, ip2, ip3 = get_ip(roles["n1"]), get_ip(roles["n2"]), get_ip(roles["n3"])

# --- 1. PRE-BENCHMARK SETUP (Do this once) ---
print("\n--- Preparing Environment (Maven Offline Mode) ---")
en.run_command("pkill -9 java || true", roles=all_hosts)
en.run_command("cd /root/bench && git fetch --all && git reset --hard origin/main", roles=all_hosts)
# This command extracts all Akka JARs into a 'lib' folder so we don't need Maven later
en.run_command("cd /root/bench && mvn dependency:copy-dependencies -DoutputDirectory=lib && mvn compile", roles=all_hosts)

results = []

def run_akka_fast(name, main_class, master_port, extra_worker=False):
    print(f"\n>>> STARTING {name}...")
    en.run_command("pkill -9 java || true", roles=all_hosts)
    
    # Use raw Java with the classpath (target/classes + all JARs in lib)
    classpath = "target/classes:lib/*"
    
    # 1. Start Seed (Node 11)
    en.run_command(f"cd /root/bench && java -cp '{classpath}' {main_class} 2551 {ip1} {ip1} > seed.log 2>&1", 
                   roles=roles["n1"], background=True)
    
    if extra_worker:
        en.run_command(f"cd /root/bench && java -cp '{classpath}' {main_class} 2553 {ip3} {ip1} > worker2.log 2>&1", 
                       roles=roles["n3"], background=True)

    # 2. Wait for Cluster (JVM is faster without Maven, 20s is enough)
    time.sleep(20)

    # 3. Start Master (Node 12)
    print(f"Executing Master...")
    res = en.run_command(f"cd /root/bench && java -cp '{classpath}' {main_class} {master_port} {ip2} {ip1}", 
                         roles=roles["n2"])
    
    output = res[0].stdout
    print(output)
    
    start = re.search(r"LOG_START:(\d+)", output)
    end = re.search(r"LOG_END:(\d+)", output)
    results.append({"name": name, "start": start.group(1) if start else "N/A", "end": end.group(1) if end else "N/A"})
    time.sleep(10)

# --- 2. EXECUTION ---
# Change counts in your Java files to: 100k Spawn, 1M Message, 1B Trapezoid for a quick test
#run_akka_fast("SPAWN", "com.example.SpawnRunner", "2552")
run_akka_fast("MESSAGE", "com.example.MessageRun", "2552")
run_akka_fast("TRAPEZOID", "com.example.TrapezoidRun", "2552", extra_worker=True)

# --- FINAL TABLE ---
print("\n" + "="*60)
print(f"{'Akka Benchmark':<15} | {'LOG_START':<18} | {'LOG_END':<18}")
print("-" * 60)
for r in results:
    print(f"{r['name']:<15} | {r['start']:<18} | {r['end']:<18}")
print("="*60)