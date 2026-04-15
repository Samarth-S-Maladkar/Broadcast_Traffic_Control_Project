#!/usr/bin/env python3
"""
topology.py - Mininet Topology for Broadcast Traffic Control
============================================================
Project  : SDN Broadcast Traffic Control
Course   : Software Defined Networking (SDN)
Tools    : Mininet, POX Controller, OpenFlow 1.0

Description:
    Creates a custom Mininet topology with 1 OpenFlow switch and 4 hosts.
    The topology connects to an external POX controller for centralized
    broadcast traffic management and learning-switch behavior.

Topology Layout:
                    POX Controller
                    (127.0.0.1:6633)
                          |
                       [s1] (OpenFlow Switch)
                      / | \ \
                    h1  h2  h3  h4
    IPs: 10.0.0.1  10.0.0.2  10.0.0.3  10.0.0.4

Usage:
    sudo python3 topology.py
    OR
    sudo mn --custom topology.py --topo mytopo --controller remote,ip=127.0.0.1,port=6633
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink
import time


# ─────────────────────────────────────────────
# Custom Topology Definition
# ─────────────────────────────────────────────
class BroadcastControlTopo(Topo):
    """
    Star topology with 1 switch and 4 hosts.
    Bandwidth and delay are set to simulate a realistic LAN environment.
    """

    def build(self):
        info("*** Building Broadcast Control Topology\n")

        # Add a single OpenFlow switch
        s1 = self.addSwitch(
            "s1",
            cls=OVSSwitch,
            protocols="OpenFlow10"  # Use OpenFlow 1.0 (compatible with POX)
        )

        # Add 4 hosts with static IP and MAC addresses for easy identification
        hosts = [
            ("h1", "10.0.0.1/24", "00:00:00:00:00:01"),
            ("h2", "10.0.0.2/24", "00:00:00:00:00:02"),
            ("h3", "10.0.0.3/24", "00:00:00:00:00:03"),
            ("h4", "10.0.0.4/24", "00:00:00:00:00:04"),
        ]

        for name, ip, mac in hosts:
            host = self.addHost(
                name,
                ip=ip,
                mac=mac,
                defaultRoute="via 10.0.0.254"  # Gateway placeholder
            )
            # Link each host to switch with 100Mbps bandwidth and 2ms delay
            self.addLink(
                host, s1,
                bw=100,      # 100 Mbps bandwidth
                delay="2ms", # 2 ms link delay
                loss=0,      # No packet loss
                use_htb=True # Use Hierarchical Token Bucket for QoS
            )
            info(f"    Added host {name} ({ip}, {mac}) linked to s1\n")


# ─────────────────────────────────────────────
# Network Runner
# ─────────────────────────────────────────────
def run():
    """
    Instantiate the topology, connect to POX controller,
    and open the Mininet CLI for testing.
    """
    setLogLevel("info")

    topo = BroadcastControlTopo()

    # Connect to the external POX controller
    controller = RemoteController(
        "c0",
        ip="127.0.0.1",
        port=6633
    )

    # Build the network
    net = Mininet(
        topo=topo,
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,         # Use Traffic Control Links (supports bw/delay)
        autoSetMacs=False,   # We set MACs manually in the topology
        waitConnected=True   # Wait until switch connects to controller
    )

    info("\n*** Starting Network\n")
    net.start()

    # Give the controller time to initialise and push flow rules
    info("*** Waiting 3 seconds for controller to initialise...\n")
    time.sleep(3)

    # ── Verify connectivity ──────────────────────────────────────────────
    info("\n*** Verifying host connectivity (pingAll)\n")
    net.pingAll()

    # ── Print switch flow table ──────────────────────────────────────────
    info("\n*** Dumping flow tables on s1\n")
    net.get("s1").cmdPrint("ovs-ofctl dump-flows s1")

    # ── Open interactive CLI ─────────────────────────────────────────────
    info("\n*** Opening Mininet CLI  (type 'exit' or Ctrl-D to quit)\n")
    CLI(net)

    # ── Clean up ─────────────────────────────────────────────────────────
    info("\n*** Stopping Network\n")
    net.stop()


# ─────────────────────────────────────────────
# Topology alias (for --custom / --topo flag)
# ─────────────────────────────────────────────
topos = {"mytopo": BroadcastControlTopo}

if __name__ == "__main__":
    run()
