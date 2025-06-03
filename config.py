from dataclasses import dataclass
from typing import List
import os


@dataclass
class NodeConfig:
    """Configuration for a single Raft node."""
    node_id: str
    host: str
    port: int
    
    @property
    def address(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class RaftConfig:
    """Configuration for the Raft cluster."""
    # Node identification
    node_id: str
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Cluster configuration
    cluster_nodes: List[NodeConfig] = None
    
    # Timing configuration (in milliseconds)
    election_timeout_min: int = 150
    election_timeout_max: int = 300
    heartbeat_interval: int = 50
    
    # Log configuration
    max_log_entries: int = 10000
    snapshot_threshold: int = 1000
    
    def __post_init__(self):
        if self.cluster_nodes is None:
            self.cluster_nodes = []
    
    @classmethod
    def from_env(cls, node_id: str) -> 'RaftConfig':
        """Create configuration from environment variables."""
        return cls(
            node_id=node_id,
            host=os.getenv('RAFT_HOST', '0.0.0.0'),
            port=int(os.getenv('RAFT_PORT', '8000')),
            election_timeout_min=int(os.getenv('RAFT_ELECTION_TIMEOUT_MIN', '150')),
            election_timeout_max=int(os.getenv('RAFT_ELECTION_TIMEOUT_MAX', '300')),
            heartbeat_interval=int(os.getenv('RAFT_HEARTBEAT_INTERVAL', '50')),
        )
    
    def add_node(self, node_id: str, host: str, port: int) -> None:
        """Add a node to the cluster configuration."""
        self.cluster_nodes.append(NodeConfig(node_id, host, port))
    
    def get_other_nodes(self) -> List[NodeConfig]:
        """Get all nodes except the current one."""
        return [node for node in self.cluster_nodes if node.node_id != self.node_id]
    
    def get_node_by_id(self, node_id: str) -> NodeConfig:
        """Get a specific node by ID."""
        for node in self.cluster_nodes:
            if node.node_id == node_id:
                return node
        raise ValueError(f"Node {node_id} not found in cluster configuration")


def create_test_cluster_config(node_id: str, base_port: int = 12000) -> RaftConfig:
    """Create a test cluster configuration with 3 nodes."""
    config = RaftConfig(node_id=node_id, port=base_port + int(node_id[-1]))
    
    # Add all nodes to the cluster
    for i in range(3):
        config.add_node(f"node_{i}", "0.0.0.0", base_port + i)
    
    return config