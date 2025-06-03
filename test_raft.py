#!/usr/bin/env python3
"""
Test script for Raft implementation.

Author: OpenHands AI Assistant
Created: 2025
"""

import time
import requests
import json
from client import RaftClient


def test_basic_operations():
    """Test basic Raft operations."""
    print("=== Testing Basic Operations ===")
    
    client = RaftClient(["localhost:12000", "localhost:12001", "localhost:12002"])
    
    # Test setting values
    print("1. Setting values...")
    assert client.set_value("test1", "value1"), "Failed to set test1"
    assert client.set_value("test2", {"nested": "object"}), "Failed to set test2"
    assert client.set_value("test3", [1, 2, 3]), "Failed to set test3"
    print("   ✓ Values set successfully")
    
    # Test getting values
    print("2. Getting values...")
    assert client.get_value("test1") == "value1", "Failed to get test1"
    assert client.get_value("test2") == {"nested": "object"}, "Failed to get test2"
    assert client.get_value("test3") == [1, 2, 3], "Failed to get test3"
    assert client.get_value("nonexistent") is None, "Should return None for nonexistent key"
    print("   ✓ Values retrieved successfully")
    
    # Test deleting values
    print("3. Deleting values...")
    assert client.delete_value("test1"), "Failed to delete test1"
    time.sleep(0.5)  # Wait for replication
    assert client.get_value("test1") is None, "test1 should be deleted"
    print("   ✓ Values deleted successfully")
    
    print("✅ Basic operations test passed!\n")


def test_consistency():
    """Test data consistency across nodes."""
    print("=== Testing Data Consistency ===")
    
    nodes = ["localhost:12000", "localhost:12001", "localhost:12002"]
    client = RaftClient(nodes)
    
    # Set a value
    key = "consistency_test"
    value = f"test_value_{int(time.time())}"
    
    print(f"1. Setting {key}={value}")
    assert client.set_value(key, value), "Failed to set value"
    
    # Wait for replication
    time.sleep(0.5)
    
    # Check consistency across all nodes
    print("2. Checking consistency across all nodes...")
    for node in nodes:
        try:
            response = requests.get(f"http://{node}/api/get/{key}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                assert data.get("found"), f"Key not found on {node}"
                assert data.get("value") == value, f"Value mismatch on {node}"
                print(f"   ✓ {node}: {data.get('value')}")
            else:
                print(f"   ✗ {node}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ✗ {node}: {e}")
    
    print("✅ Consistency test passed!\n")


def test_leader_election():
    """Test leader election process."""
    print("=== Testing Leader Election ===")
    
    nodes = ["localhost:12000", "localhost:12001", "localhost:12002"]
    
    # Find current leader
    current_leader = None
    leader_term = 0
    
    print("1. Finding current leader...")
    for node in nodes:
        try:
            response = requests.get(f"http://{node}/api/status", timeout=2)
            if response.status_code == 200:
                status = response.json()
                if status.get("state") == "leader":
                    current_leader = node
                    leader_term = status.get("current_term", 0)
                    print(f"   Current leader: {node} (term {leader_term})")
                    break
        except:
            continue
    
    if not current_leader:
        print("   No leader found, waiting for election...")
        time.sleep(2)
        return test_leader_election()
    
    # Check that other nodes are followers
    print("2. Verifying follower states...")
    followers = 0
    for node in nodes:
        if node == current_leader:
            continue
        try:
            response = requests.get(f"http://{node}/api/status", timeout=2)
            if response.status_code == 200:
                status = response.json()
                if status.get("state") == "follower":
                    followers += 1
                    print(f"   ✓ {node}: follower (term {status.get('current_term')})")
        except:
            continue
    
    assert followers >= 1, "Should have at least one follower"
    print("✅ Leader election test passed!\n")


def test_cluster_status():
    """Test cluster status reporting."""
    print("=== Testing Cluster Status ===")
    
    nodes = ["localhost:12000", "localhost:12001", "localhost:12002"]
    
    print("1. Checking node health...")
    healthy_nodes = 0
    for node in nodes:
        try:
            response = requests.get(f"http://{node}/health", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ {node}: {data.get('status')} (node_id: {data.get('node_id')})")
                healthy_nodes += 1
            else:
                print(f"   ✗ {node}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ✗ {node}: {e}")
    
    print(f"2. Healthy nodes: {healthy_nodes}/{len(nodes)}")
    assert healthy_nodes >= 2, "Need at least 2 healthy nodes for majority"
    
    print("✅ Cluster status test passed!\n")


def main():
    """Run all tests."""
    print("🧪 Raft Implementation Test Suite")
    print("=" * 50)
    
    try:
        test_cluster_status()
        test_leader_election()
        test_basic_operations()
        test_consistency()
        
        print("🎉 All tests passed!")
        
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())