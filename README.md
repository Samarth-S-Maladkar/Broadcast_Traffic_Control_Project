# Broadcast Traffic Control using SDN

## Problem
Control excessive broadcast traffic in SDN network.

## Tools
- Mininet
- Ryu Controller

## Files
- topology.py
- broadcast_controller.py

## How to Run
1. ryu-manager broadcast_controller.py
2. sudo mn --custom topology.py --topo broadcasttopo --controller remote

## Test Cases
- Normal ping
- Broadcast flood test

## Expected Output
- Broadcast traffic limited after threshold
- Stable network performance
