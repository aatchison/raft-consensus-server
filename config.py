"""
Raft Configuration Management

Author: OpenHands AI Assistant
Created: 2025

This module provides configuration classes for Raft nodes and clusters.
It handles node identification, network addresses, timing parameters,
and cluster topology.

Key features:
- Environment variable support for deployment flexibility
- Cluster topology management
- Timing parameter configuration for election and heartbeat intervals
- Test cluster creation utilities
"""

from dataclasses import dataclass
from typing import List
import os


@dataclass
class NodeConfig:
    """
    Configuration for a single Raft node.
    
    Contains the essential information needed to identify and communicate
    with a node in the Raft cluster.
    """
    node_id: str    # Unique identifier for the node
    host: str       # Hostname or IP address
    port: int       # Port number for HTTP communication
    
    @property
    def address(self) -> str:
        """
        Get the full HTTP address for this node.
        
        Returns:
            Complete HTTP URL for communicating with this node
        """
        return f"http://{self.host}:{self.port}"


@dataclass
class RaftConfig:
    """
    Configuration for the Raft cluster and individual node behavior.
    
    This class contains all the configuration parameters needed to run
    a Raft node, including:
    - Node identification and network settings
    - Cluster topology (list of all nodes)
    - Timing parameters for elections and heartbeats
    - Log management settings
    
    The configuration can be created from environment variables for
    deployment flexibility.
    """
    # Node identification and network configuration
    node_id: str                        # Unique ID for this node
    host: str = "0.0.0.0"              # Host to bind to (0.0.0.0 for all interfaces)
    port: int = 8000                    # Port to listen on
    
    # Cluster topology
    cluster_nodes: List[NodeConfig] = None  # List of all nodes in the cluster
    
    # Timing configuration (in milliseconds)
    # These values are critical for cluster stability and performance
    election_timeout_min: int = 150     # Minimum election timeout (prevents split votes)
    election_timeout_max: int = 300     # Maximum election timeout (ensures liveness)
    heartbeat_interval: int = 50        # How often leader sends heartbeats
    
    # Log management configuration
    max_log_entries: int = 10000        # Maximum entries before compaction
    snapshot_threshold: int = 1000      # Entries before snapshot creation
    
    def __post_init__(self):
        """Initialize cluster_nodes list if not provided."""
        if self.cluster_nodes is None:
            self.cluster_nodes = []
    
    @classmethod
    def from_env(cls, node_id: str) -> 'RaftConfig':
        """
        Create configuration from environment variables.
        
        This allows for flexible deployment by reading configuration from
        the environment. Useful for containerized deployments where
        configuration is injected via environment variables.
        
        Environment variables:
        - RAFT_HOST: Host to bind to (default: 0.0.0.0)
        - RAFT_PORT: Port to listen on (default: 8000)
        - RAFT_ELECTION_TIMEOUT_MIN: Minimum election timeout in ms (default: 150)
        - RAFT_ELECTION_TIMEOUT_MAX: Maximum election timeout in ms (default: 300)
        - RAFT_HEARTBEAT_INTERVAL: Heartbeat interval in ms (default: 50)
        
        Args:
            node_id: Unique identifier for this node
            
        Returns:
            RaftConfig instance with values from environment variables
        """
        return cls(
            node_id=node_id,
            host=os.getenv('RAFT_HOST', '0.0.0.0'),
            port=int(os.getenv('RAFT_PORT', '8000')),
            election_timeout_min=int(os.getenv('RAFT_ELECTION_TIMEOUT_MIN', '150')),
            election_timeout_max=int(os.getenv('RAFT_ELECTION_TIMEOUT_MAX', '300')),
            heartbeat_interval=int(os.getenv('RAFT_HEARTBEAT_INTERVAL', '50')),
        )
    
    def add_node(self, node_id: str, host: str, port: int) -> None:
        """
        Add a node to the cluster configuration.
        
        Args:
            node_id: Unique identifier for the node
            host: Hostname or IP address of the node
            port: Port number the node listens on
        """
        self.cluster_nodes.append(NodeConfig(node_id, host, port))
    
    def get_other_nodes(self) -> List[NodeConfig]:
        """
        Get all nodes except the current one.
        
        This is used when sending RPCs to other nodes in the cluster.
        
        Returns:
            List of NodeConfig objects for all other nodes in the cluster
        """
        return [node for node in self.cluster_nodes if node.node_id != self.node_id]
    
    def get_node_by_id(self, node_id: str) -> NodeConfig:
        """
        Get a specific node by ID.
        
        Args:
            node_id: ID of the node to find
            
        Returns:
            NodeConfig for the specified node
            
        Raises:
            ValueError: If the node ID is not found in the cluster
        """
        for node in self.cluster_nodes:
            if node.node_id == node_id:
                return node
        raise ValueError(f"Node {node_id} not found in cluster configuration")


def create_test_cluster_config(node_id: str, base_port: int = 12000) -> RaftConfig:
    """
    Create a test cluster configuration with 3 nodes.
    
    This is a convenience function for creating a test cluster with
    3 nodes running on localhost with sequential port numbers.
    
    Args:
        node_id: ID of the current node (should be "node_0", "node_1", or "node_2")
        base_port: Base port number (nodes will use base_port, base_port+1, base_port+2)
        
    Returns:
        RaftConfig configured for a 3-node test cluster
    """
    config = RaftConfig(node_id=node_id, port=base_port + int(node_id[-1]))
    
    # Add all nodes to the cluster configuration
    for i in range(3):
        config.add_node(f"node_{i}", "0.0.0.0", base_port + i)
    
    return config