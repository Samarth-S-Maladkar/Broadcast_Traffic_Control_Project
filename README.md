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
12. [Screenshots / Logs to Include](#14-screenshots--logs-to-include)
13. [Troubleshooting](#15-troubleshooting)

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


## 12. Screenshots / Logs to Include

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

## 13. Troubleshooting

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

*Project by: Samarth S Maladkar 
