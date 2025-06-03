#!/usr/bin/env python3
"""
Raft Client

Author: OpenHands AI Assistant
Created: 2025

This module provides a client library for interacting with a Raft cluster.
It handles leader discovery, request routing, and provides a simple interface
for key-value operations on the replicated state machine.

Key features:
- Automatic leader discovery and caching
- Transparent request routing to the current leader
- Retry logic for handling leader changes
- Support for all CRUD operations (GET, SET, DELETE)
- Cluster status monitoring and health checks

The client abstracts away the complexity of the Raft protocol and provides
a simple interface that automatically handles leader elections and failover.

Usage:
    client = RaftClient(['localhost:12000', 'localhost:12001', 'localhost:12002'])
    client.set('key1', 'value1')
    value = client.get('key1')
    client.delete('key1')
"""

import requests
import json
import time
import sys
from typing import Optional, Dict, Any


class RaftClient:
    """
    Client for interacting with a Raft cluster.
    
    This client provides a high-level interface for interacting with a Raft
    cluster. It automatically discovers the current leader and routes requests
    appropriately, handling leader changes and network failures gracefully.
    """
    
    def __init__(self, nodes: list[str]):
        """
        Initialize the client with a list of cluster nodes.
        
        Args:
            nodes: List of node addresses in format "host:port"
        """
        self.nodes = nodes
        self.current_leader: Optional[str] = None
    
    def _find_leader(self) -> Optional[str]:
        """Find the current leader by checking all nodes."""
        for node in self.nodes:
            try:
                response = requests.get(f"http://{node}/api/status", timeout=2)
                if response.status_code == 200:
                    status = response.json()
                    if status.get('state') == 'leader':
                        self.current_leader = node
                        return node
            except Exception:
                continue
        return None
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Make a request to the leader, finding it if necessary."""
        if not self.current_leader:
            self.current_leader = self._find_leader()
        
        if not self.current_leader:
            print("No leader found in the cluster")
            return None
        
        try:
            url = f"http://{self.current_leader}{endpoint}"
            if method.upper() == 'GET':
                response = requests.get(url, timeout=5)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, timeout=5)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400 and "Not the leader" in response.text:
                # Leader changed, try to find new leader
                self.current_leader = None
                return self._make_request(method, endpoint, data)
            else:
                print(f"Request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error making request to {self.current_leader}: {e}")
            # Try to find a new leader
            self.current_leader = None
            return None
    
    def set_value(self, key: str, value: Any) -> bool:
        """Set a key-value pair."""
        data = {"key": key, "value": value}
        result = self._make_request("POST", "/api/set", data)
        return result is not None and result.get("success", False)
    
    def get_value(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        result = self._make_request("GET", f"/api/get/{key}")
        if result and result.get("found", False):
            return result.get("value")
        return None
    
    def delete_value(self, key: str) -> bool:
        """Delete a key."""
        data = {"key": key}
        result = self._make_request("POST", "/api/delete", data)
        return result is not None and result.get("success", False)
    
    def get_status(self, node: str = None) -> Optional[Dict[str, Any]]:
        """Get status of a specific node or the leader."""
        if node:
            try:
                response = requests.get(f"http://{node}/api/status", timeout=2)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                print(f"Error getting status from {node}: {e}")
            return None
        else:
            return self._make_request("GET", "/api/status")
    
    def get_state_machine(self) -> Optional[Dict[str, Any]]:
        """Get the entire state machine."""
        result = self._make_request("GET", "/api/state_machine")
        if result:
            return result.get("state_machine", {})
        return None
    
    def show_cluster_status(self):
        """Show status of all nodes in the cluster."""
        print("\n=== Cluster Status ===")
        for node in self.nodes:
            status = self.get_status(node)
            if status:
                state = status.get('state', 'unknown')
                term = status.get('current_term', 0)
                log_size = status.get('log_size', 0)
                commit_index = status.get('commit_index', 0)
                print(f"{node}: {state} (term={term}, log={log_size}, commit={commit_index})")
            else:
                print(f"{node}: UNREACHABLE")
        print()


def interactive_mode(client: RaftClient):
    """Run interactive mode."""
    print("Raft Client Interactive Mode")
    print("Commands: set <key> <value>, get <key>, delete <key>, status, state, quit")
    print()
    
    while True:
        try:
            command = input("raft> ").strip().split()
            if not command:
                continue
            
            cmd = command[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "set" and len(command) >= 3:
                key = command[1]
                value = " ".join(command[2:])
                # Try to parse as JSON, otherwise treat as string
                try:
                    value = json.loads(value)
                except:
                    pass
                
                if client.set_value(key, value):
                    print(f"Set {key} = {value}")
                else:
                    print("Failed to set value")
            
            elif cmd == "get" and len(command) >= 2:
                key = command[1]
                value = client.get_value(key)
                if value is not None:
                    print(f"{key} = {value}")
                else:
                    print(f"Key '{key}' not found")
            
            elif cmd == "delete" and len(command) >= 2:
                key = command[1]
                if client.delete_value(key):
                    print(f"Deleted {key}")
                else:
                    print("Failed to delete key")
            
            elif cmd == "status":
                client.show_cluster_status()
            
            elif cmd == "state":
                state_machine = client.get_state_machine()
                if state_machine:
                    print("State Machine:")
                    for key, value in state_machine.items():
                        print(f"  {key} = {value}")
                else:
                    print("Could not retrieve state machine")
            
            else:
                print("Unknown command. Available: set, get, delete, status, state, quit")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Goodbye!")


def demo_mode(client: RaftClient):
    """Run a demonstration of the Raft cluster."""
    print("=== Raft Cluster Demo ===\n")
    
    # Show initial cluster status
    print("1. Initial cluster status:")
    client.show_cluster_status()
    
    # Wait for leader election
    print("2. Waiting for leader election...")
    for i in range(10):
        if client._find_leader():
            print(f"Leader found: {client.current_leader}")
            break
        time.sleep(1)
        print(f"  Waiting... ({i+1}/10)")
    
    if not client.current_leader:
        print("No leader elected. Demo cannot continue.")
        return
    
    # Demonstrate basic operations
    print("\n3. Demonstrating basic operations:")
    
    # Set some values
    print("Setting values...")
    client.set_value("name", "Raft Cluster")
    client.set_value("version", "1.0")
    client.set_value("nodes", 3)
    
    time.sleep(1)  # Allow replication
    
    # Get values
    print("Getting values...")
    print(f"name = {client.get_value('name')}")
    print(f"version = {client.get_value('version')}")
    print(f"nodes = {client.get_value('nodes')}")
    
    # Show state machine
    print("\n4. Current state machine:")
    state_machine = client.get_state_machine()
    if state_machine:
        for key, value in state_machine.items():
            print(f"  {key} = {value}")
    
    # Show final cluster status
    print("\n5. Final cluster status:")
    client.show_cluster_status()


def main():
    """Main entry point."""
    # Default cluster configuration
    nodes = ["localhost:12000", "localhost:12001", "localhost:12002"]
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("Usage: python client.py [demo|interactive] [node1:port node2:port ...]")
            print("Default nodes: localhost:12000 localhost:12001 localhost:12002")
            return
        
        mode = sys.argv[1]
        if len(sys.argv) > 2:
            nodes = sys.argv[2:]
    else:
        mode = "interactive"
    
    client = RaftClient(nodes)
    
    print(f"Connecting to Raft cluster: {nodes}")
    
    if mode == "demo":
        demo_mode(client)
    else:
        interactive_mode(client)


if __name__ == "__main__":
    main()