import enoslib as en
import time

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

ip1 = get_ip(roles["n1"])
ip2 = get_ip(roles["n2"])
ip3 = get_ip(roles["n3"])

print(f"IPs: n1={ip1}, n2={ip2}, n3={ip3}")

# ─────────────────────────────────────────
# CHECK 1: Java version
# ─────────────────────────────────────────
print("\n=== CHECK 1: Java Version ===")
res = en.run_command("java -version 2>&1", roles=all_hosts)
for r in res:
    print(f"{r.host}: {r.stdout.strip()}")

# ─────────────────────────────────────────
# CHECK 2: Maven version
# ─────────────────────────────────────────
print("\n=== CHECK 2: Maven Version ===")
res = en.run_command("mvn -version 2>&1", roles=all_hosts)
for r in res:
    print(f"{r.host}: {r.stdout.strip()}")

# ─────────────────────────────────────────
# CHECK 3: All network interfaces on each node
# ─────────────────────────────────────────
print("\n=== CHECK 3: All Network Interfaces ===")
res = en.run_command("ip addr show | grep 'inet ' | awk '{print $2}'", roles=all_hosts)
for r in res:
    print(f"{r.host}: {r.stdout.strip()}")

# ─────────────────────────────────────────
# CHECK 4: Port connectivity between nodes
# Akka needs 2551/2552/2553 open
# ─────────────────────────────────────────
print("\n=== CHECK 4: Port Connectivity ===")

# n2 → n1 on port 2551 (most critical — master must reach seed)
res = en.run_command(f"nc -zv -w5 {ip1} 2551 2>&1 || echo 'BLOCKED'", roles=roles["n2"])
print(f"n2 -> n1:2551 : {res[0].stdout.strip()}")

# n1 → n2 on port 2552
res = en.run_command(f"nc -zv -w5 {ip2} 2552 2>&1 || echo 'BLOCKED'", roles=roles["n1"])
print(f"n1 -> n2:2552 : {res[0].stdout.strip()}")

# n2 → n3 on port 2553
res = en.run_command(f"nc -zv -w5 {ip3} 2553 2>&1 || echo 'BLOCKED'", roles=roles["n2"])
print(f"n2 -> n3:2553 : {res[0].stdout.strip()}")

# EPMD port (Erlang port mapper — not needed for Akka but good baseline)
# Akka also uses random high ports for remoting — check if any firewall blocks them
res = en.run_command(f"iptables -L INPUT --line-numbers 2>&1 | head -30", roles=all_hosts)
for r in res:
    print(f"\nFirewall rules on {r.host}:\n{r.stdout.strip()}")

# ─────────────────────────────────────────
# CHECK 5: DNS resolution between nodes
# ─────────────────────────────────────────
print("\n=== CHECK 5: DNS / Hostname Resolution ===")
res = en.run_command("hostname -f 2>&1", roles=all_hosts)
for r in res:
    print(f"{r.host} full hostname: {r.stdout.strip()}")

res = en.run_command(f"ping -c 2 {ip1} 2>&1 | tail -3", roles=roles["n2"])
print(f"n2 ping n1: {res[0].stdout.strip()}")

res = en.run_command(f"ping -c 2 {ip2} 2>&1 | tail -3", roles=roles["n1"])
print(f"n1 ping n2: {res[0].stdout.strip()}")

# ─────────────────────────────────────────
# CHECK 6: Actually start seed and read its log
# ─────────────────────────────────────────
print("\n=== CHECK 6: Seed Node Startup Log ===")
en.run_command("pkill -9 java || true", roles=all_hosts)
time.sleep(3)

en.run_command(
    f"nohup sh -c 'cd /root/bench && mvn exec:java "
    f"-Dexec.mainClass=\"com.example.MessageRun\" "
    f"-Dexec.args=\"2551 {ip1} {ip1}\"' "
    f"> /root/bench/seed.log 2>&1 &",
    roles=roles["n1"]
)

print("Waiting 30s for seed to boot...")
time.sleep(30)

res = en.run_command("cat /root/bench/seed.log", roles=roles["n1"])
print(f"=== SEED LOG ===\n{res[0].stdout}")

# ─────────────────────────────────────────
# CHECK 7: Check if seed is listening on 2551
# ─────────────────────────────────────────
print("\n=== CHECK 7: Is Seed Actually Listening on 2551? ===")
res = en.run_command("ss -tlnp | grep 2551 || echo 'NOT LISTENING'", roles=roles["n1"])
print(f"n1 port 2551 status: {res[0].stdout.strip()}")

# Now test connectivity FROM n2 to the live seed
res = en.run_command(f"nc -zv -w5 {ip1} 2551 2>&1 || echo 'BLOCKED'", roles=roles["n2"])
print(f"n2 -> n1:2551 (live test): {res[0].stdout.strip()}")

# ─────────────────────────────────────────
# CHECK 8: Try starting master and capture
# what happens in the first 30 seconds
# ─────────────────────────────────────────
print("\n=== CHECK 8: Master Startup (30s timeout) ===")
en.run_command(
    f"nohup sh -c 'cd /root/bench && mvn exec:java "
    f"-Dexec.mainClass=\"com.example.MessageRun\" "
    f"-Dexec.args=\"2552 {ip2} {ip1}\"' "
    f"> /root/bench/master.log 2>&1 &",
    roles=roles["n2"]
)

time.sleep(30)

res = en.run_command("cat /root/bench/master.log", roles=roles["n2"])
print(f"=== MASTER LOG ===\n{res[0].stdout}")

# Final cleanup
en.run_command("pkill -9 java || true", roles=all_hosts)
print("\n=== DIAGNOSTICS COMPLETE ===")