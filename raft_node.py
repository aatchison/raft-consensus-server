"""
Raft Consensus Algorithm Implementation

Author: OpenHands AI Assistant
Created: 2025

This module implements the core Raft consensus algorithm as described in the paper
"In Search of an Understandable Consensus Algorithm" by Diego Ongaro and John Ousterhout.

The Raft algorithm provides a way for a cluster of servers to agree on a sequence of
state machine commands, ensuring consistency even in the presence of failures.

Key components:
- Leader Election: Ensures exactly one leader at a time
- Log Replication: Leader replicates log entries to followers
- Safety: Ensures committed entries are never lost
"""

import asyncio
import random
import time
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import requests
from dataclasses import dataclass

from log_entry import LogEntry, RaftLog
from config import RaftConfig, NodeConfig


class NodeState(Enum):
    """
    Possible states for a Raft node.
    
    FOLLOWER: Default state, receives entries from leader
    CANDIDATE: Transitional state during leader election
    LEADER: Handles client requests and replicates log entries
    """
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class RequestVoteRequest:
    """
    RequestVote RPC request structure.
    
    Sent by candidates during leader election to request votes from other nodes.
    """
    term: int              # Candidate's current term
    candidate_id: str      # ID of the candidate requesting vote
    last_log_index: int    # Index of candidate's last log entry
    last_log_term: int     # Term of candidate's last log entry


@dataclass
class RequestVoteResponse:
    """
    RequestVote RPC response structure.
    
    Response to a vote request indicating whether the vote was granted.
    """
    term: int              # Current term, for candidate to update itself
    vote_granted: bool     # True if candidate received vote


@dataclass
class AppendEntriesRequest:
    """
    AppendEntries RPC request structure.
    
    Sent by leader to replicate log entries and provide heartbeat.
    """
    term: int                    # Leader's current term
    leader_id: str              # Leader's ID for followers to redirect clients
    prev_log_index: int         # Index of log entry immediately preceding new ones
    prev_log_term: int          # Term of prev_log_index entry
    entries: List[LogEntry]     # Log entries to store (empty for heartbeat)
    leader_commit: int          # Leader's commit index


@dataclass
class AppendEntriesResponse:
    """
    AppendEntries RPC response structure.
    
    Response indicating success/failure of log replication.
    """
    term: int              # Current term, for leader to update itself
    success: bool          # True if follower contained entry matching prev_log_index and prev_log_term
    match_index: int = 0   # Index of highest log entry known to be replicated


class RaftNode:
    """
    Implementation of a Raft consensus node.
    
    This class implements the complete Raft consensus algorithm including:
    - Leader election with randomized timeouts
    - Log replication with consistency guarantees
    - State machine application of committed entries
    - RPC handling for RequestVote and AppendEntries
    
    The node maintains both persistent state (survives restarts) and volatile state
    (lost on restart), following the Raft specification.
    """
    
    def __init__(self, config: RaftConfig):
        """
        Initialize a new Raft node.
        
        Args:
            config: Configuration containing node ID, cluster information, and timing parameters
        """
        self.config = config
        self.node_id = config.node_id
        
        # Persistent state on all servers (updated on stable storage before responding to RPCs)
        self.current_term = 0                    # Latest term server has seen (initialized to 0)
        self.voted_for: Optional[str] = None     # CandidateId that received vote in current term
        self.log = RaftLog()                     # Log entries; each entry contains command and term
        
        # Volatile state on all servers
        self.commit_index = 0                    # Index of highest log entry known to be committed
        self.last_applied = 0                    # Index of highest log entry applied to state machine
        self.state = NodeState.FOLLOWER         # Current node state (follower, candidate, or leader)
        
        # Volatile state on leaders (reinitialized after election)
        self.next_index: Dict[str, int] = {}     # For each server, index of next log entry to send
        self.match_index: Dict[str, int] = {}    # For each server, index of highest log entry known to be replicated
        
        # Timing and election management
        self.last_heartbeat = time.time()        # Timestamp of last received heartbeat/vote grant
        self.election_timeout = self._random_election_timeout()  # Randomized election timeout
        
        # Async task management
        self.election_task: Optional[asyncio.Task] = None    # Task for election timeout monitoring
        self.heartbeat_task: Optional[asyncio.Task] = None   # Task for sending heartbeats (leader only)
        
        # State machine (simple key-value store for demonstration)
        # In production, this would be replaced with the actual application state machine
        self.state_machine: Dict[str, Any] = {}
        
        # Logging for debugging and monitoring
        self.logger = logging.getLogger(f"raft.{self.node_id}")
        
    def _random_election_timeout(self) -> float:
        """
        Generate a randomized election timeout.
        
        Randomization prevents split votes by ensuring nodes don't start elections
        simultaneously. The timeout is chosen randomly from the configured range.
        
        Returns:
            Random timeout value in seconds
        """
        return random.uniform(
            self.config.election_timeout_min / 1000.0,
            self.config.election_timeout_max / 1000.0
        )
    
    async def start(self):
        """
        Start the Raft node and begin election timeout monitoring.
        
        This initializes the node as a follower and starts the election timer
        that will trigger leader election if no heartbeats are received.
        """
        self.logger.info(f"Starting Raft node {self.node_id}")
        self.election_task = asyncio.create_task(self._election_timer())
        
    async def stop(self):
        """
        Stop the Raft node and cancel all running tasks.
        
        This gracefully shuts down the node by cancelling the election timer
        and heartbeat tasks if they are running.
        """
        self.logger.info(f"Stopping Raft node {self.node_id}")
        if self.election_task:
            self.election_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
    
    async def _election_timer(self):
        """
        Monitor election timeout and trigger elections when necessary.
        
        This runs continuously and checks if enough time has passed since the last
        heartbeat. If the election timeout expires and the node is not a leader,
        it starts a new election.
        
        The timer uses a small sleep interval for responsiveness while avoiding
        excessive CPU usage.
        """
        while True:
            try:
                await asyncio.sleep(0.01)  # Check every 10ms for responsiveness
                
                # Leaders don't participate in elections
                if self.state == NodeState.LEADER:
                    continue
                    
                # Check if election timeout has expired
                if time.time() - self.last_heartbeat > self.election_timeout:
                    self.logger.info(f"Election timeout expired, starting election")
                    await self._start_election()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in election timer: {e}")
    
    async def _start_election(self):
        """
        Start a new leader election.
        
        This implements the leader election algorithm:
        1. Increment current term
        2. Vote for self
        3. Reset election timer
        4. Send RequestVote RPCs to all other servers
        5. If majority of votes received, become leader
        6. Otherwise, remain follower
        
        The election process is designed to ensure at most one leader per term.
        """
        # Transition to candidate state and increment term
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id  # Vote for ourselves
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()
        
        self.logger.info(f"Starting election for term {self.current_term}")
        
        # Start with our own vote
        votes = 1
        total_nodes = len(self.config.cluster_nodes)
        
        # Send RequestVote RPCs to all other nodes in parallel
        vote_tasks = []
        for node in self.config.get_other_nodes():
            task = asyncio.create_task(self._request_vote(node))
            vote_tasks.append(task)
        
        # Wait for all vote responses (with timeout handling)
        if vote_tasks:
            responses = await asyncio.gather(*vote_tasks, return_exceptions=True)
            
            # Process each response
            for response in responses:
                if isinstance(response, RequestVoteResponse):
                    # If we discover a higher term, step down immediately
                    if response.term > self.current_term:
                        await self._become_follower(response.term)
                        return
                    elif response.vote_granted:
                        votes += 1
        
        # Check if we won the election (majority of votes)
        if votes > total_nodes // 2:
            await self._become_leader()
        else:
            # Election failed, remain as follower
            await self._become_follower(self.current_term)
    
    async def _request_vote(self, node: NodeConfig) -> Optional[RequestVoteResponse]:
        """Request vote from a specific node."""
        try:
            request = RequestVoteRequest(
                term=self.current_term,
                candidate_id=self.node_id,
                last_log_index=self.log.last_log_index(),
                last_log_term=self.log.last_log_term()
            )
            
            response = requests.post(
                f"{node.address}/raft/request_vote",
                json=request.__dict__,
                timeout=1.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return RequestVoteResponse(**data)
                
        except Exception as e:
            self.logger.warning(f"Failed to request vote from {node.node_id}: {e}")
        
        return None
    
    async def _become_leader(self):
        """Become the leader."""
        self.logger.info(f"Became leader for term {self.current_term}")
        self.state = NodeState.LEADER
        
        # Initialize leader state
        for node in self.config.get_other_nodes():
            self.next_index[node.node_id] = self.log.last_log_index() + 1
            self.match_index[node.node_id] = 0
        
        # Start sending heartbeats
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        self.heartbeat_task = asyncio.create_task(self._send_heartbeats())
    
    async def _become_follower(self, term: int):
        """Become a follower."""
        self.logger.info(f"Became follower for term {term}")
        self.state = NodeState.FOLLOWER
        self.current_term = term
        self.voted_for = None
        self.last_heartbeat = time.time()
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
    
    async def _send_heartbeats(self):
        """Send heartbeats to all followers."""
        while self.state == NodeState.LEADER:
            try:
                tasks = []
                for node in self.config.get_other_nodes():
                    task = asyncio.create_task(self._send_append_entries(node))
                    tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(self.config.heartbeat_interval / 1000.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error sending heartbeats: {e}")
    
    async def _send_append_entries(self, node: NodeConfig):
        """Send append entries to a specific node."""
        try:
            next_index = self.next_index.get(node.node_id, 1)
            prev_log_index = next_index - 1
            prev_log_term = self.log.get_term_at_index(prev_log_index)
            
            entries = self.log.get_entries_from(next_index)
            
            request = AppendEntriesRequest(
                term=self.current_term,
                leader_id=self.node_id,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=entries,
                leader_commit=self.commit_index
            )
            
            # Convert entries to dict for JSON serialization
            request_data = {
                'term': request.term,
                'leader_id': request.leader_id,
                'prev_log_index': request.prev_log_index,
                'prev_log_term': request.prev_log_term,
                'entries': [entry.to_dict() for entry in request.entries],
                'leader_commit': request.leader_commit
            }
            
            response = requests.post(
                f"{node.address}/raft/append_entries",
                json=request_data,
                timeout=1.0
            )
            
            if response.status_code == 200:
                data = response.json()
                append_response = AppendEntriesResponse(**data)
                await self._handle_append_entries_response(node.node_id, append_response, len(entries))
                
        except Exception as e:
            self.logger.warning(f"Failed to send append entries to {node.node_id}: {e}")
    
    async def _handle_append_entries_response(self, node_id: str, response: AppendEntriesResponse, entries_sent: int):
        """Handle append entries response."""
        if response.term > self.current_term:
            await self._become_follower(response.term)
            return
        
        if response.success:
            self.match_index[node_id] = response.match_index
            self.next_index[node_id] = response.match_index + 1
            await self._update_commit_index()
        else:
            # Decrement next_index and retry
            self.next_index[node_id] = max(1, self.next_index[node_id] - 1)
    
    async def _update_commit_index(self):
        """Update commit index based on majority replication."""
        if self.state != NodeState.LEADER:
            return
        
        # Find the highest index that is replicated on a majority of servers
        for index in range(self.commit_index + 1, self.log.last_log_index() + 1):
            replicated_count = 1  # Count self
            
            for node_id in self.match_index:
                if self.match_index[node_id] >= index:
                    replicated_count += 1
            
            if replicated_count > len(self.config.cluster_nodes) // 2:
                if self.log.get_term_at_index(index) == self.current_term:
                    self.commit_index = index
                    await self._apply_committed_entries()
    
    async def _apply_committed_entries(self):
        """Apply committed entries to the state machine."""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log.get_entry(self.last_applied)
            if entry:
                await self._apply_to_state_machine(entry)
    
    async def _apply_to_state_machine(self, entry: LogEntry):
        """Apply a log entry to the state machine."""
        try:
            command = entry.command
            if isinstance(command, dict):
                if command.get('type') == 'set':
                    key = command.get('key')
                    value = command.get('value')
                    if key is not None:
                        self.state_machine[key] = value
                        self.logger.info(f"Applied SET {key}={value}")
                elif command.get('type') == 'delete':
                    key = command.get('key')
                    if key is not None and key in self.state_machine:
                        del self.state_machine[key]
                        self.logger.info(f"Applied DELETE {key}")
        except Exception as e:
            self.logger.error(f"Error applying entry to state machine: {e}")
    
    # RPC Handlers - These implement the core Raft RPC protocols
    
    async def handle_request_vote(self, request: RequestVoteRequest) -> RequestVoteResponse:
        """
        Handle RequestVote RPC from candidates.
        
        This implements the RequestVote RPC receiver logic:
        1. Reply false if term < currentTerm
        2. If votedFor is null or candidateId, and candidate's log is at least
           as up-to-date as receiver's log, grant vote
        
        Args:
            request: RequestVote RPC request containing candidate information
            
        Returns:
            RequestVoteResponse indicating whether vote was granted
        """
        # If candidate's term is higher, update our term and become follower
        if request.term > self.current_term:
            await self._become_follower(request.term)
        
        vote_granted = False
        
        # Grant vote if:
        # 1. Request is for current term
        # 2. We haven't voted yet OR we already voted for this candidate
        # 3. Candidate's log is at least as up-to-date as ours
        if (request.term == self.current_term and 
            (self.voted_for is None or self.voted_for == request.candidate_id) and
            self._is_log_up_to_date(request.last_log_index, request.last_log_term)):
            
            self.voted_for = request.candidate_id
            self.last_heartbeat = time.time()  # Reset election timer
            vote_granted = True
            self.logger.info(f"Granted vote to {request.candidate_id} for term {request.term}")
        else:
            self.logger.info(f"Denied vote to {request.candidate_id} for term {request.term}")
        
        return RequestVoteResponse(term=self.current_term, vote_granted=vote_granted)
    
    async def handle_append_entries(self, request: AppendEntriesRequest) -> AppendEntriesResponse:
        """
        Handle AppendEntries RPC from leader.
        
        This implements the AppendEntries RPC receiver logic:
        1. Reply false if term < currentTerm
        2. Reply false if log doesn't contain an entry at prevLogIndex whose term matches prevLogTerm
        3. If an existing entry conflicts with a new one, delete the existing entry and all that follow it
        4. Append any new entries not already in the log
        5. If leaderCommit > commitIndex, set commitIndex = min(leaderCommit, index of last new entry)
        
        Args:
            request: AppendEntries RPC request containing log entries and metadata
            
        Returns:
            AppendEntriesResponse indicating success/failure and match index
        """
        # If leader's term is higher, update our term and become follower
        if request.term > self.current_term:
            await self._become_follower(request.term)
        
        success = False
        match_index = 0
        
        # Only process if request is for current term
        if request.term == self.current_term:
            self.last_heartbeat = time.time()  # Reset election timer (heartbeat received)
            
            # Check log consistency: verify that we have the previous log entry
            # This ensures log consistency across the cluster
            if (request.prev_log_index == 0 or  # First entry (no previous)
                (request.prev_log_index <= self.log.last_log_index() and
                 self.log.get_term_at_index(request.prev_log_index) == request.prev_log_term)):
                
                success = True
                
                # If there are new entries to append
                if request.entries:
                    # Remove any conflicting entries (safety property)
                    self.log.truncate_from(request.prev_log_index + 1)
                    
                    # Append new entries to log
                    for entry in request.entries:
                        self.log.append(entry)
                
                # Calculate the index of the last entry we now have
                match_index = request.prev_log_index + len(request.entries)
                
                # Update commit index if leader has committed more entries
                if request.leader_commit > self.commit_index:
                    self.commit_index = min(request.leader_commit, self.log.last_log_index())
                    await self._apply_committed_entries()
        
        return AppendEntriesResponse(
            term=self.current_term,
            success=success,
            match_index=match_index
        )
    
    def _is_log_up_to_date(self, last_log_index: int, last_log_term: int) -> bool:
        """
        Check if the candidate's log is at least as up-to-date as ours.
        
        This implements the log comparison logic for voting:
        - If the logs have last entries with different terms, then the log with
          the later term is more up-to-date
        - If the logs end with the same term, then whichever log is longer is
          more up-to-date
        
        Args:
            last_log_index: Index of candidate's last log entry
            last_log_term: Term of candidate's last log entry
            
        Returns:
            True if candidate's log is at least as up-to-date as ours
        """
        our_last_term = self.log.last_log_term()
        our_last_index = self.log.last_log_index()
        
        # Candidate's log is more up-to-date if it has a higher last term
        if last_log_term > our_last_term:
            return True
        # If terms are equal, candidate's log is more up-to-date if it's longer
        elif last_log_term == our_last_term:
            return last_log_index >= our_last_index
        # Candidate's log is less up-to-date if it has a lower last term
        else:
            return False
    
    # Client Operations - These provide the interface for client interactions
    
    async def append_entry(self, command: Any, client_id: str = None) -> bool:
        """
        Append a new entry to the log (leader only).
        
        This is the main interface for clients to submit commands to the Raft cluster.
        Only the leader can accept new entries. Followers will reject this operation.
        
        Args:
            command: The command to be replicated across the cluster
            client_id: Optional identifier for the client making the request
            
        Returns:
            True if entry was successfully appended (leader only), False otherwise
        """
        # Only leaders can accept new entries
        if self.state != NodeState.LEADER:
            return False
        
        # Create new log entry with current term and next index
        entry = LogEntry(
            term=self.current_term,
            index=self.log.last_log_index() + 1,
            command=command,
            client_id=client_id
        )
        
        # Append to our log (will be replicated to followers via heartbeats)
        self.log.append(entry)
        self.logger.info(f"Appended entry {entry.index}: {command}")
        
        return True
    
    def get_state_machine_value(self, key: str) -> Any:
        """
        Get a value from the state machine.
        
        This provides read access to the replicated state machine.
        In this implementation, the state machine is a simple key-value store.
        
        Args:
            key: The key to look up in the state machine
            
        Returns:
            The value associated with the key, or None if not found
        """
        return self.state_machine.get(key)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the node.
        
        This provides a comprehensive view of the node's current state,
        useful for monitoring and debugging.
        
        Returns:
            Dictionary containing node status information
        """
        return {
            'node_id': self.node_id,
            'state': self.state.value,
            'current_term': self.current_term,
            'voted_for': self.voted_for,
            'commit_index': self.commit_index,
            'last_applied': self.last_applied,
            'log_size': self.log.size(),
            'state_machine': self.state_machine.copy()
        }