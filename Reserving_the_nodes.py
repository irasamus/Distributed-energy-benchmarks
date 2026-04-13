import enoslib as en
import logging
import sys

# 1. Setup logging
en.init_logging(level=logging.INFO)

# --- CONFIGURATION ---
REPO_URL = "https://github.com/irasamus/Distributed-energy-benchmarks"
JOB_NAME = "energy_setup"

# Paradoxe Cluster Nodes 3, 4, and 5
conf = (
    en.G5kConf.from_settings(job_name=JOB_NAME, job_type=["deploy"], env_name="ubuntu2204-x64-min", walltime="05:00:00")
    .add_machine(roles=["n1"], servers=["neowise-1.lyon.grid5000.fr"])
    .add_machine(roles=["n2"], servers=["neowise-2.lyon.grid5000.fr"])
    .add_machine(roles=["n3"], servers=["neowise-3.lyon.grid5000.fr"])
)

provider = en.G5k(conf)
roles, _ = provider.init()

# Get IPs for networking
ip1 = roles["n1"][0].address
ip2 = roles["n2"][0].address
ip3 = roles["n3"][0].address

print(f"IPs: Node1={ip1}, Node2={ip2}, Node3={ip3}")

# --- STEP 2: INSTALLATION ---
print("Preparing nodes...")
en.run_command("apt-get update && apt-get install -y git openjdk-11-jdk maven elixir", roles=roles)
en.run_command(f"rm -rf /root/bench && git clone {REPO_URL} /root/bench", roles=roles)
en.run_command("cd /root/bench && mvn compile", roles=roles)
