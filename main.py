#!/usr/bin/env python3
"""
Raft Server Main Entry Point

This script starts a Raft consensus server node.

Usage:
    python main.py <node_id> [port]

Examples:
    python main.py node_0 12000
    python main.py node_1 12001
    python main.py node_2 12002
"""

import asyncio
import sys
import logging
from config import create_test_cluster_config
from raft_server import run_server


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <node_id> [port]")
        print("Example: python main.py node_0 12000")
        sys.exit(1)
    
    node_id = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 12000
    
    # Create configuration for a 3-node test cluster
    config = create_test_cluster_config(node_id, base_port=12000)
    config.port = port
    
    print(f"Starting Raft node {node_id} on port {port}")
    print(f"Cluster nodes: {[f'{node.node_id}:{node.port}' for node in config.cluster_nodes]}")
    
    try:
        await run_server(config)
    except KeyboardInterrupt:
        print(f"\nShutting down Raft node {node_id}")
    except Exception as e:
        print(f"Error running server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())