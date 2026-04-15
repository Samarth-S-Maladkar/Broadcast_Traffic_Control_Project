"""
controller.py  –  POX Controller: Broadcast Traffic Control
============================================================
Project  : SDN Broadcast Traffic Control
Course   : Software Defined Networking (SDN)
Tools    : POX (NOX successor), OpenFlow 1.0

Description:
    A POX controller component that combines:
      1. Learning Switch  – learns MAC→port mappings and installs unicast
                            flow rules to avoid flooding known unicast traffic.
      2. Broadcast Guard  – tracks per-source broadcast packet counts; once
                            a host exceeds BROADCAST_THRESHOLD within
                            RATE_WINDOW seconds, a DROP flow rule is pushed
                            to the switch to suppress further broadcasts.

How to run (from the POX root directory):
    python pox.py log.level --DEBUG misc.broadcast_control

Copy this file to: <pox_root>/pox/misc/broadcast_control.py

OpenFlow Message Flow:
    Host sends ARP/broadcast
        ↓
    Switch → PacketIn → Controller
        ↓
    Controller checks broadcast counter
        ↓  (below threshold)        ↓  (above threshold)
    Flood + install unicast rule   Push DROP rule to switch
"""

from pox.core import core
from pox.lib.util import dpid_to_str, str_to_bool
from pox.lib.recoco import Timer
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import EthAddr
import time

# ─────────────────────────────────────────────
# Module logger
# ─────────────────────────────────────────────
log = core.getLogger()

# ─────────────────────────────────────────────
# Tuneable Parameters
# ─────────────────────────────────────────────
# After this many broadcasts in RATE_WINDOW seconds the source is blocked
BROADCAST_THRESHOLD = 10

# Sliding time window (seconds) for counting broadcasts
RATE_WINDOW = 5

# How long (seconds) to keep the DROP flow rule active on the switch
DROP_RULE_TIMEOUT = 30

# How long (seconds) to keep unicast forwarding rules on the switch
UNICAST_RULE_TIMEOUT = 60

# Ethernet broadcast address constant
BROADCAST_MAC = EthAddr("ff:ff:ff:ff:ff:ff")


# ═══════════════════════════════════════════════════════════════════════════
# Per-Switch Handler
# ═══════════════════════════════════════════════════════════════════════════
class BroadcastController(object):
    """
    Handles all OpenFlow events for a single connected switch.

    Attributes:
        connection  : OpenFlow connection to the switch
        mac_to_port : dict mapping EthAddr → port number (learning switch table)
        bcast_log   : dict mapping EthAddr → list of timestamps (sliding window)
        blocked_macs: set of EthAddr whose broadcasts are currently blocked
    """

    def __init__(self, connection):
        self.connection  = connection
        self.mac_to_port = {}          # MAC address → egress port
        self.bcast_log   = {}          # MAC address → [timestamp, ...]
        self.blocked_macs = set()      # MACs currently under a DROP rule

        # Listen to PacketIn events from this switch
        connection.addListeners(self)

        # Periodic cleanup of stale broadcast windows (every RATE_WINDOW s)
        Timer(RATE_WINDOW, self._cleanup_broadcast_log, recurring=True)

        log.info("BroadcastController ready on switch %s",
                 dpid_to_str(connection.dpid))

    # ── Helpers ─────────────────────────────────────────────────────────

    def _is_broadcast(self, packet):
        """Return True if the Ethernet destination is the broadcast address."""
        return packet.dst == BROADCAST_MAC

    def _record_broadcast(self, src_mac):
        """
        Record a broadcast event for src_mac in the sliding window.
        Returns the current count within RATE_WINDOW.
        """
        now = time.time()
        if src_mac not in self.bcast_log:
            self.bcast_log[src_mac] = []

        # Append current timestamp
        self.bcast_log[src_mac].append(now)

        # Prune timestamps older than RATE_WINDOW
        cutoff = now - RATE_WINDOW
        self.bcast_log[src_mac] = [
            t for t in self.bcast_log[src_mac] if t >= cutoff
        ]

        count = len(self.bcast_log[src_mac])
        log.debug("Broadcast count for %s: %d / %d (window=%ds)",
                  src_mac, count, BROADCAST_THRESHOLD, RATE_WINDOW)
        return count

    def _cleanup_broadcast_log(self):
        """Remove expired entries from bcast_log to free memory."""
        now  = time.time()
        cutoff = now - RATE_WINDOW
        for mac in list(self.bcast_log.keys()):
            self.bcast_log[mac] = [
                t for t in self.bcast_log[mac] if t >= cutoff
            ]
            if not self.bcast_log[mac]:
                del self.bcast_log[mac]
        log.debug("Broadcast log cleaned. Tracked MACs: %d", len(self.bcast_log))

    # ── OpenFlow Actions ────────────────────────────────────────────────

    def _install_drop_rule(self, src_mac):
        """
        Push a flow rule to the switch that DROPs all broadcast packets
        originating from src_mac for DROP_RULE_TIMEOUT seconds.

        OpenFlow match: eth_src=src_mac AND eth_dst=ff:ff:ff:ff:ff:ff
        Action        : (empty action list) → DROP
        """
        if src_mac in self.blocked_macs:
            return  # Rule already installed; skip duplicate

        log.warning("⛔  BLOCKING broadcasts from %s (threshold exceeded)", src_mac)

        msg             = of.ofp_flow_mod()
        msg.match       = of.ofp_match()
        msg.match.dl_src = src_mac          # Source MAC
        msg.match.dl_dst = BROADCAST_MAC    # Broadcast destination
        msg.priority    = 100               # Higher than default (1)
        msg.idle_timeout = DROP_RULE_TIMEOUT
        msg.hard_timeout = DROP_RULE_TIMEOUT * 2
        # No msg.actions → default DROP
        self.connection.send(msg)

        self.blocked_macs.add(src_mac)

        # Automatically unblock after DROP_RULE_TIMEOUT + small buffer
        Timer(DROP_RULE_TIMEOUT + 2, self._unblock_mac, args=[src_mac])

    def _unblock_mac(self, src_mac):
        """Remove src_mac from the blocked set so it can be re-evaluated."""
        self.blocked_macs.discard(src_mac)
        log.info("✅  Unblocked broadcasts from %s (timeout expired)", src_mac)

    def _install_unicast_rule(self, src_mac, dst_mac, out_port, in_port):
        """
        Install a proactive unicast forwarding rule so subsequent packets
        between src_mac and dst_mac are forwarded by the switch without
        hitting the controller.

        OpenFlow match: eth_src=src_mac, eth_dst=dst_mac, in_port=in_port
        Action        : output to out_port
        """
        msg              = of.ofp_flow_mod()
        msg.match        = of.ofp_match()
        msg.match.dl_src = src_mac
        msg.match.dl_dst = dst_mac
        msg.match.in_port = in_port
        msg.idle_timeout  = UNICAST_RULE_TIMEOUT
        msg.hard_timeout  = UNICAST_RULE_TIMEOUT * 2
        msg.priority      = 10

        # Action: forward out the known port
        msg.actions.append(of.ofp_action_output(port=out_port))
        self.connection.send(msg)

        log.debug("Unicast rule: %s → %s via port %d", src_mac, dst_mac, out_port)

    def _flood_packet(self, packet_in_event):
        """Send the packet out ALL ports except the ingress port (flood)."""
        msg         = of.ofp_packet_out()
        msg.data    = packet_in_event.ofp
        msg.in_port = packet_in_event.port
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        self.connection.send(msg)

    def _forward_unicast(self, packet_in_event, out_port):
        """Forward this specific packet out a known port (unicast delivery)."""
        msg         = of.ofp_packet_out()
        msg.data    = packet_in_event.ofp
        msg.in_port = packet_in_event.port
        msg.actions.append(of.ofp_action_output(port=out_port))
        self.connection.send(msg)

    # ── Main Event Handler ───────────────────────────────────────────────

    def _handle_PacketIn(self, event):
        """
        Called by POX whenever the switch sends a PacketIn message.

        Processing pipeline:
          1. Parse incoming packet
          2. Learn the source MAC → ingress port mapping
          3. If broadcast:
               a. Record in sliding window
               b. If count > threshold → install DROP rule, return
               c. Else → flood the packet
          4. If unicast and destination known → forward + install flow rule
          5. If unicast and destination unknown → flood
        """
        packet   = event.parsed         # Parsed Ethernet frame
        in_port  = event.port           # Physical port it arrived on
        src_mac  = packet.src           # Source MAC address
        dst_mac  = packet.dst           # Destination MAC address
        dpid     = dpid_to_str(event.dpid)

        if not packet.parsed:
            log.warning("Ignoring incomplete/unparsed packet")
            return

        # ── Step 1: MAC Learning ─────────────────────────────────────────
        if src_mac not in self.mac_to_port:
            log.info("Learned: MAC %s → port %d on switch %s",
                     src_mac, in_port, dpid)
        self.mac_to_port[src_mac] = in_port

        # ── Step 2: Broadcast Handling ───────────────────────────────────
        if self._is_broadcast(packet):
            count = self._record_broadcast(src_mac)

            if count > BROADCAST_THRESHOLD:
                # BLOCK: push DROP rule to switch
                self._install_drop_rule(src_mac)
                log.warning(
                    "PacketIn DROPPED (broadcast storm) from %s [count=%d]",
                    src_mac, count
                )
                # Do NOT forward this packet
                return

            # Below threshold: flood the broadcast
            log.info(
                "📡  Broadcast from %s → flood (count=%d/%d)",
                src_mac, count, BROADCAST_THRESHOLD
            )
            self._flood_packet(event)
            return

        # ── Step 3: Unicast Handling ─────────────────────────────────────
        if dst_mac in self.mac_to_port:
            out_port = self.mac_to_port[dst_mac]

            # Install a flow rule so future packets bypass the controller
            self._install_unicast_rule(src_mac, dst_mac, out_port, in_port)

            # Forward this packet immediately
            log.debug("Unicast: %s → %s via port %d", src_mac, dst_mac, out_port)
            self._forward_unicast(event, out_port)
        else:
            # Unknown destination: flood (will learn the reply)
            log.debug("Unknown destination %s → flood", dst_mac)
            self._flood_packet(event)


# ═══════════════════════════════════════════════════════════════════════════
# POX Component Launcher
# ═══════════════════════════════════════════════════════════════════════════
class BroadcastControlApp(object):
    """
    Top-level POX application component.
    Listens for new switch connections and spawns a BroadcastController
    for each connected switch.
    """

    def __init__(self):
        log.info("BroadcastControlApp starting…")
        log.info(
            "  Threshold : %d broadcasts per %d seconds",
            BROADCAST_THRESHOLD, RATE_WINDOW
        )
        log.info("  DROP rule timeout : %d seconds", DROP_RULE_TIMEOUT)
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        """Called when a new switch connects to the controller."""
        log.info("Switch connected: %s", dpid_to_str(event.dpid))
        BroadcastController(event.connection)

    def _handle_ConnectionDown(self, event):
        """Called when a switch disconnects."""
        log.warning("Switch disconnected: %s", dpid_to_str(event.dpid))


def launch(threshold=BROADCAST_THRESHOLD,
           window=RATE_WINDOW,
           drop_timeout=DROP_RULE_TIMEOUT):
    """
    POX entry point.  Called when the component is loaded:
        python pox.py misc.broadcast_control
        python pox.py misc.broadcast_control --threshold=5 --window=3
    """
    global BROADCAST_THRESHOLD, RATE_WINDOW, DROP_RULE_TIMEOUT

    # Allow CLI overrides
    BROADCAST_THRESHOLD = int(threshold)
    RATE_WINDOW         = int(window)
    DROP_RULE_TIMEOUT   = int(drop_timeout)

    core.registerNew(BroadcastControlApp)
    log.info("Broadcast Traffic Control component launched.")
