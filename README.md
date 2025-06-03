# Raft Consensus Algorithm Implementation

A complete implementation of the Raft consensus algorithm in Python, providing distributed consensus for replicated state machines with a web-based monitoring interface.

## 🎯 Overview

This implementation includes:
- **Leader Election**: Automatic leader selection with randomized timeouts
- **Log Replication**: Consistent log replication across all nodes
- **Safety**: Ensures consistency even during network partitions
- **HTTP API**: RESTful interface for client operations
- **Key-Value Store**: Example state machine implementation
- **Web Interface**: Real-time cluster monitoring dashboard
- **Fault Tolerance**: Automatic recovery from node failures

## 🏗️ Architecture

### Core Components

1. **RaftNode** (`raft_node.py`): Core Raft algorithm implementation
2. **RaftServer** (`raft_server.py`): HTTP server wrapper with FastAPI
3. **LogEntry** (`log_entry.py`): Log entry data structures
4. **Config** (`config.py`): Configuration management
5. **Client** (`client.py`): Client library and CLI
6. **Web Interface** (`web_interface.py`): Real-time monitoring dashboard

### Key Features

- ✅ **Fault Tolerance**: Handles node failures and network partitions
- ✅ **Consistency**: Guarantees strong consistency across the cluster
- ✅ **Performance**: Optimized for low-latency operations
- ✅ **Monitoring**: Built-in health checks and status reporting
- ✅ **Web Dashboard**: Real-time cluster visualization
- ✅ **Auto-Recovery**: Automatic leader election and log repair

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Starting a Cluster

Start three nodes in separate terminals:

```bash
# Terminal 1 - Start node_0
python main.py node_0 12000

# Terminal 2 - Start node_1
python main.py node_1 12001

# Terminal 3 - Start node_2
python main.py node_2 12002
```

Or start all nodes in background:

```bash
python main.py node_0 12000 > node_0.log 2>&1 &
python main.py node_1 12001 > node_1.log 2>&1 &
python main.py node_2 12002 > node_2.log 2>&1 &
```

### Web Dashboard

Start the web interface:

```bash
python web_interface.py
```

Then open http://localhost:8080 in your browser for real-time cluster monitoring.

### Using the Client

```bash
# Interactive CLI
python client.py

# Demo mode
python client.py demo

# Direct operations
python client.py set name "Raft Cluster"
python client.py get name
python client.py delete name
```

## 📡 API Reference

### Client Operations

- `POST /api/set` - Set a key-value pair
  ```json
  {"key": "name", "value": "Raft Cluster"}
  ```

- `GET /api/get/{key}` - Get value by key
  ```json
  {"key": "name", "value": "Raft Cluster", "found": true}
  ```

- `POST /api/delete` - Delete a key
  ```json
  {"key": "name"}
  ```

- `GET /api/state_machine` - Get entire state machine
  ```json
  {"state_machine": {"name": "Raft Cluster", "version": "1.0"}}
  ```

### Cluster Management

- `GET /health` - Node health check
- `GET /api/status` - Detailed node status
- `POST /api/vote` - Request vote (internal Raft RPC)
- `POST /api/append_entries` - Append entries (internal Raft RPC)

## ⚙️ Configuration

Edit `config.py` to customize timing parameters:

```python
ELECTION_TIMEOUT_MIN = 150  # ms - Minimum election timeout
ELECTION_TIMEOUT_MAX = 300  # ms - Maximum election timeout  
HEARTBEAT_INTERVAL = 50     # ms - Leader heartbeat interval
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
python test_raft.py
```

The test suite verifies:
- ✅ Cluster health and connectivity
- ✅ Leader election process
- ✅ Basic CRUD operations
- ✅ Data consistency across nodes
- ✅ Fault tolerance

## 🔬 Implementation Details

### Leader Election
- Uses randomized timeouts (150-300ms) to prevent split votes
- Candidates increment term and request votes from all nodes
- Majority vote (⌈n/2⌉ + 1) required to become leader
- Automatic re-election when leader fails

### Log Replication
- Leader appends entries to local log first
- Replicates to followers via AppendEntries RPC
- Commits when majority of nodes acknowledge
- Handles log inconsistencies automatically

### Safety Guarantees

The implementation ensures all Raft safety properties:

1. **Election Safety**: At most one leader per term
2. **Leader Append-Only**: Leaders never overwrite log entries
3. **Log Matching**: Logs are consistent across nodes
4. **Leader Completeness**: Committed entries appear in future leaders
5. **State Machine Safety**: Applied entries are consistent

### Fault Tolerance

- **Node Failures**: Cluster continues with majority (2/3 nodes)
- **Network Partitions**: Majority partition remains operational
- **Leader Failures**: New leader elected automatically
- **Log Inconsistencies**: Automatically repaired during normal operation

## 📊 Monitoring

### Web Dashboard Features

- **Real-time Status**: Live cluster state updates
- **Node Visualization**: Color-coded node states (leader/follower/unreachable)
- **Operations Interface**: Set/get/delete values through web UI
- **State Machine View**: Current key-value store contents
- **Detailed Metrics**: Term numbers, log sizes, commit indices

### Command Line Monitoring

```bash
# Check cluster status
curl http://localhost:12000/api/status

# View state machine
curl http://localhost:12001/api/state_machine

# Health check
curl http://localhost:12002/health
```

## 🎮 Demo Scenarios

### Basic Operations Demo
```bash
python client.py demo
```

### Fault Tolerance Demo
1. Start 3-node cluster
2. Perform some operations
3. Stop the leader node
4. Verify new leader election
5. Continue operations with new leader

### Consistency Demo
1. Set values through one node
2. Verify values appear on all nodes
3. Demonstrates strong consistency

## 📁 File Structure

```
raft-server/
├── raft_node.py          # Core Raft algorithm
├── raft_server.py        # HTTP server wrapper
├── log_entry.py          # Log entry structures
├── config.py             # Configuration
├── client.py             # Client library & CLI
├── main.py               # Server entry point
├── web_interface.py      # Web dashboard
├── test_raft.py          # Test suite
├── requirements.txt      # Dependencies
└── README.md             # This file
```

## 🔧 Development

### Adding New Operations

1. Add operation to `RaftNode.apply_entry()`
2. Add HTTP endpoint to `RaftServer`
3. Update client library
4. Add tests

### Extending State Machine

The key-value store is just an example. You can implement any deterministic state machine by modifying the `apply_entry()` method.

## 🐛 Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 12000-12002 and 8080 are available
2. **Network timeouts**: Check firewall settings
3. **Split brain**: Ensure odd number of nodes (3, 5, 7...)

### Debugging

- Check node logs: `tail -f node_*.log`
- Monitor web dashboard: http://localhost:8080
- Use client status commands: `python client.py status`

## 📈 Performance

- **Latency**: ~10-50ms for operations (depends on network)
- **Throughput**: Limited by leader capacity and network bandwidth
- **Scalability**: Tested with 3-7 nodes (odd numbers recommended)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Based on the Raft consensus algorithm by Diego Ongaro and John Ousterhout.
Paper: "In Search of an Understandable Consensus Algorithm"