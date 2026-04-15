# SDN Broadcast Traffic Control
### Using Mininet + POX Controller | OpenFlow 1.0

---

## Table of Contents
1. [Problem Statement](#1-problem-statement)
2. [Objectives](#2-objectives)
3. [Tools & Technologies](#3-tools--technologies)
4. [Architecture & Topology](#4-architecture--topology)
5. [File Structure](#5-file-structure)
6. [Setup & Installation](#6-setup--installation)
7. [Running the Project](#7-running-the-project)
8. [Test Scenarios](#8-test-scenarios)
9. [Performance Analysis](#9-performance-analysis)
10. [Expected Outputs](#10-expected-outputs)
11. [Observations & Results](#11-observations--results)
12. [GitHub Commands](#12-github-commands)
13. [Viva Questions & Answers](#13-viva-questions--answers)
14. [Screenshots / Logs to Include](#14-screenshots--logs-to-include)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Problem Statement

In traditional Ethernet networks — and even in SDN environments running naive forwarding — **broadcast traffic** is a persistent performance bottleneck. Every host on a segment receives every broadcast frame (ARP requests, DHCP discovers, etc.), regardless of whether the frame is intended for them.

### Why is this a problem in SDN?

| Issue | Impact |
|---|---|
| **ARP Flooding** | A single host can issue thousands of ARP requests/sec, flooding all switch ports |
| **Broadcast Storms** | Loops or misbehaving hosts amplify broadcasts exponentially |
| **Controller Overload** | In SDN, every unknown frame triggers a PacketIn to the controller — broadcast storms can DoS the control plane |
| **Wasted Bandwidth** | All hosts process frames not destined for them, consuming CPU cycles |
| **Scalability** | In large SDN deployments, uncontrolled broadcasts prevent the network from scaling |

**This project solves the problem** by implementing a POX controller that detects excessive broadcast traffic, installs OpenFlow DROP rules at the switch level, and maintains normal unicast learning-switch behavior.

---

## 2. Objectives

- ✅ **Detect** broadcast packets (destination MAC = `ff:ff:ff:ff:ff:ff`) at the controller
- ✅ **Count** broadcasts per source MAC in a sliding time window
- ✅ **Block** sources that exceed a configurable threshold by pushing DROP flow rules
- ✅ **Maintain** normal unicast forwarding via a learning switch
- ✅ **Analyse** network performance before and after broadcast control

---

## 3. Tools & Technologies

| Tool | Version | Purpose |
|---|---|---|
| **Mininet** | 2.3.x | Network emulation (hosts, switches, links) |
| **POX** | `dart` / `eel` branch | SDN controller framework (Python) |
| **Open vSwitch (OVS)** | 2.x | Software OpenFlow switch |
| **OpenFlow** | 1.0 | Controller–switch communication protocol |
| **Python** | 3.x / 2.7 | Controller and topology scripting |
| **iperf** | 2.x | Throughput measurement |
| **arping** | any | Broadcast (ARP) traffic generation |
| **dpctl / ovs-ofctl** | any | Flow table inspection |

---

## 4. Architecture & Topology

```
                    ┌─────────────────────┐
                    │   POX Controller    │
                    │   (127.0.0.1:6633)  │
                    │  broadcast_control  │
                    └─────────┬───────────┘
                              │ OpenFlow 1.0
                    ┌─────────▼───────────┐
                    │     Switch s1       │
                    │  (Open vSwitch)     │
                    └──┬────┬────┬────┬──┘
                       │    │    │    │
                  ┌────▼─┐ ┌▼──┐ ┌▼──┐ ┌▼────┐
                  │  h1  │ │h2 │ │h3 │ │ h4  │
                  │.0.0.1│ │.2 │ │.3 │ │ .4  │
                  └──────┘ └───┘ └───┘ └─────┘
                         10.0.0.0/24

Link specs: 100 Mbps, 2 ms delay, 0% loss
```

### Controller Logic Flow

```
PacketIn received
       │
       ├─ Learn src_mac → in_port
       │
       ├─ Is dst == ff:ff:ff:ff:ff:ff?
       │     YES ──► Increment bcast counter for src_mac
       │              │
       │              ├─ counter > THRESHOLD?
       │              │        YES ──► Push DROP flow rule → STOP
       │              │        NO  ──► Flood packet → STOP
       │
       └─ Unicast:
             ├─ dst_mac in table? YES ──► Install unicast rule + forward
             └─ NO ──► Flood (will learn from reply)
```

---

## 5. File Structure

```
sdn_broadcast_control/
├── topology.py       # Mininet topology (1 switch, 4 hosts, TCLinks)
├── controller.py     # POX controller component (copy to pox/misc/)
└── README.md         # This file
```

---

## 6. Setup & Installation

### 6.1 Install Mininet

```bash
# Option A: Package manager (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y mininet

# Option B: From source (recommended for latest features)
git clone https://github.com/mininet/mininet.git
cd mininet
sudo util/install.sh -a      # Full install (OVS, wireshark, etc.)
cd ..
```

### 6.2 Install POX Controller

```bash
git clone https://github.com/noxrepo/pox.git
cd pox
# Verify Python is available
python --version              # Python 2.7 or Python 3.x
```

### 6.3 Install the Controller Component

```bash
# Copy controller.py into the POX misc module directory
cp /path/to/sdn_broadcast_control/controller.py  pox/pox/misc/broadcast_control.py
```

### 6.4 Install Test Tools

```bash
sudo apt-get install -y iperf arping iproute2
```

---

## 7. Running the Project

> **Important:** Always start the POX controller **before** Mininet.

### Terminal 1 — Start POX Controller

```bash
cd ~/pox

# Basic run (default threshold=10, window=5s)
python pox.py log.level --DEBUG misc.broadcast_control

# Custom threshold and window
python pox.py log.level --DEBUG misc.broadcast_control \
    --threshold=5 --window=3 --drop_timeout=20
```

Expected output:
```
POX 0.x.x / Copyright 2011-2023 James McCauley, et al.
INFO:misc.broadcast_control:BroadcastControlApp starting…
INFO:misc.broadcast_control:  Threshold : 10 broadcasts per 5 seconds
INFO:misc.broadcast_control:  DROP rule timeout : 30 seconds
INFO:openflow.of_01:Listening on 0.0.0.0:6633
```

### Terminal 2 — Start Mininet Topology

```bash
# Option A: Run directly (opens CLI automatically)
sudo python3 topology.py

# Option B: Use mn command with custom topology
sudo mn --custom topology.py \
        --topo mytopo \
        --controller remote,ip=127.0.0.1,port=6633 \
        --switch ovsk,protocols=OpenFlow10 \
        --link tc
```

Expected output:
```
*** Building Broadcast Control Topology
*** Starting Network
*** Waiting 3 seconds for controller to initialise...
mininet> 
```

---

## 8. Test Scenarios

### Scenario 1: Normal Unicast Communication (ping)

Tests that the learning switch correctly forwards unicast packets and installs flow rules.

```bash
# Inside Mininet CLI:
mininet> h1 ping -c 5 h2
mininet> h1 ping -c 5 h3
mininet> pingall
```

**Expected behavior:**
- First ping triggers PacketIn → controller floods → learns MACs
- Subsequent pings hit the installed flow rule directly at the switch (no PacketIn)
- All hosts reachable

---

### Scenario 2: Broadcast Flooding Attack (arping)

Tests that the broadcast guard detects and suppresses excessive ARP broadcasts.

```bash
# Open an xterm for h1
mininet> xterm h1

# In the h1 xterm – send rapid ARP broadcasts (simulates ARP flood)
arping -b -c 50 -i h1-eth0 10.0.0.255

# OR using ping broadcast
h1 ping -b -c 50 -i 0.1 10.0.0.255
```

**Watch the POX controller terminal for:**
```
WARNING:misc.broadcast_control:⛔  BLOCKING broadcasts from 00:00:00:00:00:01
```

**Verify the DROP rule was installed on the switch:**
```bash
mininet> sh ovs-ofctl dump-flows s1
```

---

### Scenario 3: Throughput Test (iperf)

```bash
# Start iperf server on h2
mininet> h2 iperf -s &

# Run iperf client from h1 for 10 seconds
mininet> h1 iperf -c 10.0.0.2 -t 10

# UDP throughput test
mininet> h2 iperf -s -u &
mininet> h1 iperf -c 10.0.0.2 -u -b 50M -t 10
```

---

### Scenario 4: Flow Table Inspection

```bash
# View all flows on switch s1
mininet> sh ovs-ofctl dump-flows s1

# Verbose flow details
mininet> sh ovs-ofctl dump-flows s1 --rsort

# Switch statistics
mininet> sh ovs-ofctl dump-ports s1

# Using dpctl (if available)
mininet> dpctl dump-flows
```

---

## 9. Performance Analysis

### 9.1 Latency (ping)

```bash
# Basic RTT latency
mininet> h1 ping -c 20 h3

# Expected output (after flow rules installed):
# rtt min/avg/max/mdev = 4.1/4.3/4.8/0.2 ms
```

**Interpretation:**
- First ping RTT is higher (~10-15 ms) because it goes to the controller
- Subsequent pings are lower (~4 ms) because the flow rule handles them at the switch
- This difference demonstrates the benefit of proactive flow installation

### 9.2 Throughput (iperf)

```bash
# TCP throughput
mininet> iperf h1 h2

# Expected output:
# [ ID] Interval       Transfer     Bandwidth
# [  3]  0.0-10.0 sec  1.10 GBytes   944 Mbits/sec
```

**Interpretation:**
- Throughput close to the 100 Mbps link capacity = minimal overhead
- Without broadcast control, broadcast storms would saturate the link and reduce measurable throughput

### 9.3 Flow Table Inspection

```bash
mininet> sh ovs-ofctl dump-flows s1
```

**Sample output:**
```
NXST_FLOW reply:
 cookie=0x0, duration=45.3s, table=0, n_packets=120, n_bytes=8640,
   idle_timeout=60, dl_src=00:00:00:00:00:01, dl_dst=00:00:00:00:00:02,
   actions=output:2

 cookie=0x0, duration=8.1s, table=0, n_packets=55, n_bytes=3300,
   idle_timeout=30, dl_src=00:00:00:00:00:01, dl_dst=ff:ff:ff:ff:ff:ff,
   priority=100, actions=drop
```

**Interpretation:**
- First rule: unicast forwarding installed by learning switch (priority 10)
- Second rule: broadcast DROP rule for h1 (priority 100, overrides default)

### 9.4 Comparison Table

| Metric | Without Broadcast Control | With Broadcast Control |
|---|---|---|
| Controller PacketIn rate | Very high (every broadcast) | Low (only new unicasts) |
| Switch CPU usage | High (flooding all ports) | Low (DROP at hardware) |
| End-host CPU | High (processing all broadcasts) | Low (only unicast received) |
| Unicast latency | Variable (controller-dependent) | Stable (flow-based) |
| Network throughput | Degraded during storms | Maintained near line-rate |

---

## 10. Expected Outputs

### POX Controller (normal operation)
```
INFO:misc.broadcast_control:Switch connected: 00-00-00-00-00-01
INFO:misc.broadcast_control:Learned: MAC 00:00:00:00:00:01 → port 1
INFO:misc.broadcast_control:📡  Broadcast from 00:00:00:00:00:01 → flood (count=1/10)
INFO:misc.broadcast_control:Learned: MAC 00:00:00:00:00:02 → port 2
INFO:misc.broadcast_control:Unicast rule: 00:00:00:00:00:01 → 00:00:00:00:00:02 via port 2
```

### POX Controller (blocking a flooder)
```
WARNING:misc.broadcast_control:⛔  BLOCKING broadcasts from 00:00:00:00:00:01 (threshold exceeded)
INFO:misc.broadcast_control:PacketIn DROPPED (broadcast storm) from 00:00:00:00:00:01 [count=11]
INFO:misc.broadcast_control:✅  Unblocked broadcasts from 00:00:00:00:00:01 (timeout expired)
```

### Mininet pingAll
```
*** Ping: testing ping reachability
h1 -> h2 h3 h4
h2 -> h1 h3 h4
h3 -> h1 h2 h4
h4 -> h1 h2 h3
*** Results: 0% dropped (12/12 received)
```

### Flow Table (after broadcast block)
```
NXST_FLOW reply (ofp_version=0x01):
 cookie=0x0, duration=10.5s, table=0, n_packets=200, n_bytes=15600,
   idle_timeout=60, hard_timeout=120, priority=10,
   dl_src=00:00:00:00:00:02,dl_dst=00:00:00:00:00:01,
   actions=output:1

 cookie=0x0, duration=3.2s, table=0, n_packets=12, n_bytes=720,
   idle_timeout=30, hard_timeout=60, priority=100,
   dl_src=00:00:00:00:00:01,dl_dst=ff:ff:ff:ff:ff:ff,
   actions=drop
```

---

## 11. Observations & Results

1. **Learning Switch** — The controller correctly learns MAC→port mappings from the first packet and installs flow rules that bypass the controller for subsequent packets, reducing latency.

2. **Broadcast Detection** — Every broadcast packet (ARP, etc.) increments a per-source counter. The sliding window prevents a single burst from permanently blocking a legitimate host.

3. **Threshold-Based Blocking** — When a host exceeds 10 broadcasts in 5 seconds, a DROP rule is pushed to the switch. The switch enforces the rule in hardware/dataplane, removing load from the controller entirely.

4. **Automatic Unblocking** — After 30 seconds, the DROP rule expires (both idle_timeout and hard_timeout enforce this), allowing the host to resume normal operation.

5. **Unicast Unaffected** — The DROP rule only matches `dl_dst=ff:ff:ff:ff:ff:ff`. All unicast traffic continues normally even during a broadcast block.

---

## 12. GitHub Commands

### Initialize and Push

```bash
# Navigate to project directory
cd ~/sdn_broadcast_control

# Initialize git repository
git init

# Set your identity (first time only)
git config --global user.email "you@example.com"
git config --global user.name "Your Name"

# Stage all files
git add topology.py controller.py README.md

# Commit
git commit -m "Initial commit: SDN Broadcast Traffic Control project"

# Create repository on GitHub first (via web UI), then:
git remote add origin https://github.com/YOUR_USERNAME/sdn-broadcast-control.git

# Push to GitHub
git push -u origin main
# OR if default branch is master:
git push -u origin master
```

### Troubleshooting Push Rejections

```bash
# Error: "Updates were rejected because the remote contains work"
git pull --rebase origin main
git push origin main

# Error: "src refspec main does not match any"
git branch -M main
git push -u origin main

# Force push (use only on fresh repos — overwrites remote)
git push -f origin main

# Check current branches
git branch -a

# Check remote URL
git remote -v
```

### Subsequent Updates

```bash
git add .
git commit -m "Add performance analysis results"
git push
```

---

## 13. Viva Questions & Answers

### Q1. What is Software Defined Networking (SDN)?

**A:** SDN is a network architecture that decouples the **control plane** (routing decisions) from the **data plane** (packet forwarding). A centralized controller programs forwarding rules into switches using a standard protocol like OpenFlow. This enables programmable, application-aware network management without modifying hardware.

---

### Q2. What is OpenFlow and how does it work?

**A:** OpenFlow is a communications protocol between the SDN controller and network switches. The controller sends **flow rules** (match + action pairs) to the switch's flow table. When a packet arrives at the switch, it is matched against the flow table; if a match is found, the associated action (forward, drop, modify) is executed. If no match is found, the packet is sent to the controller as a **PacketIn** message.

---

### Q3. What is a PacketIn event in POX?

**A:** A PacketIn event is triggered when a switch receives a packet that does not match any existing flow rule and forwards it to the controller. In POX, registering for `_handle_PacketIn` allows the controller to inspect the packet, make a forwarding decision, and optionally install a flow rule to handle similar packets in the future without controller involvement.

---

### Q4. What is ARP flooding and why is it a problem?

**A:** ARP (Address Resolution Protocol) uses broadcast messages (`ff:ff:ff:ff:ff:ff`) to resolve IP→MAC mappings. A misbehaving host or a loop can generate thousands of ARP requests per second. In SDN, each broadcast triggers a PacketIn to the controller, potentially overwhelming the control plane. Additionally, the switch floods broadcasts to all ports, wasting bandwidth and CPU on all hosts.

---

### Q5. How does your broadcast control mechanism work?

**A:** The controller maintains a per-source sliding-window counter. Every broadcast packet increments the counter for its source MAC. Entries older than `RATE_WINDOW` seconds are pruned. If the count exceeds `BROADCAST_THRESHOLD`, the controller sends an `ofp_flow_mod` with:
- **Match:** `dl_src=<offending_mac>`, `dl_dst=ff:ff:ff:ff:ff:ff`
- **Action:** (empty — DROP)
- **Priority:** 100 (overrides default)
- **Timeout:** 30 seconds

The switch then drops all matching broadcasts at line rate, without controller involvement.

---

### Q6. What is a flow rule and what does it consist of?

**A:** A flow rule in OpenFlow 1.0 consists of:
- **Match fields** — header fields to match (MAC src/dst, IP src/dst, port, VLAN, etc.)
- **Priority** — higher priority rules are matched first
- **Counters** — packet and byte counts for statistics
- **Actions** — what to do with matching packets (output port, drop, modify headers)
- **Timeouts** — idle_timeout (inactivity expiry) and hard_timeout (absolute expiry)

---

### Q7. What is the difference between idle_timeout and hard_timeout?

**A:**
- `idle_timeout`: Rule is removed if no matching packets arrive for N seconds (resets on each match)
- `hard_timeout`: Rule is unconditionally removed after N seconds regardless of traffic

In this project, DROP rules use both: `idle_timeout=30, hard_timeout=60`. This ensures blocked hosts are eventually unblocked even if they keep sending (hard_timeout) or stop sending (idle_timeout).

---

### Q8. What is a learning switch and how does it differ from a hub?

**A:** A **hub** forwards every packet out every port (blind flooding). A **learning switch** builds a MAC address table by observing which port each source MAC arrives on. When a packet arrives for a known destination MAC, it is forwarded only to the correct port, reducing unnecessary traffic. In SDN, the controller implements this logic and installs flow rules so the switch itself handles forwarding for known pairs.

---

### Q9. Why is priority 100 used for the DROP rule?

**A:** OpenFlow matches rules in priority order (highest first). The default forwarding or flood rules have priority 1 (or the controller's default). Setting the DROP rule to priority 100 ensures it is matched **before** any lower-priority flood or forward rule. Without this, the broadcast packet might still be forwarded by a lower-priority rule.

---

### Q10. How would you extend this project for production use?

**A:** Several enhancements for production:
1. **Per-port rate limiting** using OpenFlow meters (OpenFlow 1.3+)
2. **ARP proxying** — the controller answers ARP requests on behalf of hosts, eliminating broadcasts entirely
3. **VLAN-aware broadcast domains** to isolate segments
4. **Integration with Ryu or ONOS** for better scalability and REST APIs
5. **Persistent blocked-MAC database** using Redis or SQLite
6. **SNMP/syslog alerts** when thresholds are exceeded

---

## 14. Screenshots / Logs to Include

For a complete academic submission, capture and include:

| Screenshot | Command | What to Show |
|---|---|---|
| POX controller startup | Terminal | Component loaded, listening on 6633 |
| Switch connection | POX terminal | "Switch connected: 00-00-00-00-00-01" |
| MAC learning | POX terminal | "Learned: MAC ... → port ..." |
| Broadcast counter | POX terminal | "Broadcast count: 8/10" |
| Broadcast block | POX terminal | "BLOCKING broadcasts from ..." |
| pingAll success | Mininet CLI | 0% dropped |
| Flow table (normal) | `ovs-ofctl dump-flows s1` | Unicast forwarding rules |
| Flow table (after block) | `ovs-ofctl dump-flows s1` | DROP rule with priority=100 |
| iperf throughput | Mininet CLI | Bandwidth near 100 Mbps |
| arping output | h1 xterm | Broadcast packets sent |
| Topology diagram | Mininet | `net` or `dump` command output |

---

## 15. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Connection refused` on port 6633 | POX not running | Start POX first, then Mininet |
| `RTNETLINK answers: File exists` | Old Mininet state | Run `sudo mn -c` to clean up |
| `ImportError: No module named pox` | Wrong directory | Run POX from its root directory |
| `ovs-vsctl: not found` | OVS not installed | `sudo apt-get install openvswitch-switch` |
| Hosts can't ping after flood | DROP rule too aggressive | Reduce threshold or increase window |
| `git push` rejected | Branch mismatch | `git branch -M main && git push -u origin main` |
| POX shows no PacketIn | Mininet not connected | Check controller IP/port in topology.py |
| `arping: command not found` | Tool missing | `sudo apt-get install arping` |

---

*Project by: [Your Name] | [Roll Number] | [Course Name] | [Institution]*
