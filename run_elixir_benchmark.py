import enoslib as en
import time

en.init_logging(level=en.logging.INFO)

print("Connecting to existing Paradoxe nodes (11, 12, 13)...")

# We define the roles manually. 'user="root"' is MANDATORY for deploy jobs.
roles = {
    "n1": [en.Host("paradoxe-11.rennes.grid5000.fr", user="root")],
    "n2": [en.Host("paradoxe-12.rennes.grid5000.fr", user="root")],
    "n3": [en.Host("paradoxe-13.rennes.grid5000.fr", user="root")]
}

all_hosts = roles["n1"] + roles["n2"] + roles["n3"]

# 1. Get physical IPs (Required for stable distribution)
def get_ip(role):
    res = en.run_command("hostname -I | awk '{print $1}'", roles=role)
    return res[0].stdout.strip()

ip1 = get_ip(roles["n1"]) # Worker 1
ip2 = get_ip(roles["n2"]) # Master
ip3 = get_ip(roles["n3"]) # Worker 2

print(f"IPs detected: n1={ip1}, n2={ip2}, n3={ip3}")

# 2. Update code from GitHub
print("\n--- Syncing Code ---")
en.run_command("pkill -9 beam || true", roles=all_hosts)
# reset --hard ensures the code matches GitHub exactly
en.run_command("cd /root/bench && git fetch --all && git reset --hard origin/main", roles=all_hosts)

def run_elixir_bench(name, file_name, master_args):
    print(f"\n>>> STARTING {name} ({file_name})")
    en.run_command("pkill -9 beam || true", roles=all_hosts)
    
    # Start Worker on Node 1
    en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name worker@{ip1} --cookie monster {file_name} worker", 
                   roles=roles["n1"], background=True)
    
    # If it is Trapezoid, start a second worker on Node 3
    if "trapezoid" in file_name.lower():
        en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name worker@{ip3} --cookie monster {file_name} worker", 
                       roles=roles["n3"], background=True)
    
    time.sleep(5) # Let BEAM start up

    # Start Master on Node 2
    res = en.run_command(f"cd /root/bench/elixir_benchmarks && elixir --name master@{ip2} --cookie monster {file_name} master {master_args}", 
                         roles=roles["n2"])
    print(res[0].stdout)
    print(f"<<< FINISHED {name}")
    time.sleep(10)

# 3. RUN ALL TESTS
# Note: Check your GitHub for the exact capitalization of filenames!
run_elixir_bench("SPAWN", "DistSpawner.exs", f"worker@{ip1}")
run_elixir_bench("MESSAGE", "dist_message.exs", f"worker@{ip1}")
run_elixir_bench("TRAPEZOID", "dist_trapezoid.exs", f"worker@{ip1} worker@{ip3}")

print("\n--- ALL ELIXIR BENCHMARKS COMPLETE ---")