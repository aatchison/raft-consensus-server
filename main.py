#!/usr/bin/env python3
"""
Raft Server Main Entry Point

Author: OpenHands AI Assistant
Created: 2025

This script provides the main entry point for starting a Raft consensus server node.
It handles command-line argument parsing, configuration setup, and server lifecycle.

The script creates a test cluster configuration and starts the specified node,
making it easy to run multiple nodes for testing and development.

Usage:
    python main.py <node_id> [port]

Examples:
    # Start first node of a 3-node cluster
    python main.py node_0 12000
    
    # Start second node
    python main.py node_1 12001
    
    # Start third node
    python main.py node_2 12002

The script automatically configures a 3-node test cluster where all nodes
know about each other and can communicate for leader election and log replication.
"""

import asyncio
import sys
import logging
from config import create_test_cluster_config
from raft_server import run_server


async def main():
    """
    Main entry point for the Raft server.
    
    This function:
    1. Parses command-line arguments for node ID and port
    2. Creates a test cluster configuration
    3. Starts the Raft server with proper error handling
    4. Handles graceful shutdown on interruption
    """
    # Validate command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python main.py <node_id> [port]")
        print("Example: python main.py node_0 12000")
        print("\nNode ID should be one of: node_0, node_1, node_2")
        sys.exit(1)
    
    # Parse arguments
    node_id = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 12000
    
    # Create configuration for a 3-node test cluster
    # This sets up a cluster where all nodes know about each other
    config = create_test_cluster_config(node_id, base_port=12000)
    config.port = port  # Override port if specified
    
    # Display startup information
    print(f"🚀 Starting Raft node {node_id} on port {port}")
    print(f"📡 Cluster nodes: {[f'{node.node_id}:{node.port}' for node in config.cluster_nodes]}")
    print(f"⚙️  Election timeout: {config.election_timeout_min}-{config.election_timeout_max}ms")
    print(f"💓 Heartbeat interval: {config.heartbeat_interval}ms")
    print("Press Ctrl+C to stop the server\n")
    
    try:
        # Start the Raft server (this will run until interrupted)
        await run_server(config)
    except KeyboardInterrupt:
        print(f"\n🛑 Shutting down Raft node {node_id}")
    except Exception as e:
        print(f"❌ Error running server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())