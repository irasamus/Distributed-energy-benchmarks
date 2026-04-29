import enoslib as en
import time

en.init_logging(level=en.logging.INFO)

# 1. Connect to your already reserved nodes
roles = {
    "n1": [en.Host("paradoxe-11.rennes.grid5000.fr", user="root")],
    "n2": [en.Host("paradoxe-12.rennes.grid5000.fr", user="root")],
    "n3": [en.Host("paradoxe-13.rennes.grid5000.fr", user="root")]
}
all_hosts = roles["n1"] + roles["n2"] + roles["n3"]

# 2. Get the physical Numeric IPs (BEAM distribution works best with these)
print("Detecting numeric IPs...")
ip1 = en.run_command("hostname -I | awk '{print $1}'", roles=roles["n1"])[0].stdout.strip()
ip2 = en.run_command("hostname -I | awk '{print $1}'", roles=roles["n2"])[0].stdout.strip()

print(f"Worker Node IP: {ip1}")
print(f"Master Node IP: {ip2}")

# 3. Clean up and Update code
print("\n--- Cleaning up and updating code ---")
en.run_command("pkill -9 beam || true", roles=all_hosts)
en.run_command("cd /root/bench && git fetch --all && git reset --hard origin/main", roles=all_hosts)

# 4. Start the Worker (Node 1)
print(f"\n--- Starting Elixir Worker on {ip1} ---")
# Path assumes your file is in elixir_benchmarks folder inside the repo
worker_cmd = (
    f"elixir --name worker@{ip1} --cookie monster "
    f"/root/bench/elixir_benchmarks/DistSpawner.exs worker"
)
en.run_command(worker_cmd, roles=roles["n1"], background=True)

# Give the BEAM VM 5 seconds to start up its network interface
time.sleep(5)

# 5. Start the Master (Node 2)
print(f"--- Starting Elixir Master on {ip2} ---")
master_cmd = (
    f"elixir --name master@{ip2} --cookie monster "
    f"/root/bench/elixir_benchmarks/DistSpawner.exs master worker@{ip1}"
)

# We run the master in the foreground to see the LOG_START/LOG_END directly
res = en.run_command(master_cmd, roles=roles["n2"])

print("\n" + "="*40)
print("ELIXIR BENCHMARK RESULT")
print("="*40)
print(res[0].stdout)