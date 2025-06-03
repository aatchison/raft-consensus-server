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
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class RequestVoteRequest:
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


@dataclass
class RequestVoteResponse:
    term: int
    vote_granted: bool


@dataclass
class AppendEntriesRequest:
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int


@dataclass
class AppendEntriesResponse:
    term: int
    success: bool
    match_index: int = 0


class RaftNode:
    """Implementation of a Raft consensus node."""
    
    def __init__(self, config: RaftConfig):
        self.config = config
        self.node_id = config.node_id
        
        # Persistent state
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log = RaftLog()
        
        # Volatile state
        self.commit_index = 0
        self.last_applied = 0
        self.state = NodeState.FOLLOWER
        
        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Timing
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()
        
        # Tasks
        self.election_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # State machine (simple key-value store for demo)
        self.state_machine: Dict[str, Any] = {}
        
        self.logger = logging.getLogger(f"raft.{self.node_id}")
        
    def _random_election_timeout(self) -> float:
        """Generate a random election timeout."""
        return random.uniform(
            self.config.election_timeout_min / 1000.0,
            self.config.election_timeout_max / 1000.0
        )
    
    async def start(self):
        """Start the Raft node."""
        self.logger.info(f"Starting Raft node {self.node_id}")
        self.election_task = asyncio.create_task(self._election_timer())
        
    async def stop(self):
        """Stop the Raft node."""
        self.logger.info(f"Stopping Raft node {self.node_id}")
        if self.election_task:
            self.election_task.cancel()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
    
    async def _election_timer(self):
        """Election timeout timer."""
        while True:
            try:
                await asyncio.sleep(0.01)  # Check every 10ms
                
                if self.state == NodeState.LEADER:
                    continue
                    
                if time.time() - self.last_heartbeat > self.election_timeout:
                    self.logger.info(f"Election timeout, starting election")
                    await self._start_election()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in election timer: {e}")
    
    async def _start_election(self):
        """Start a new election."""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        self.election_timeout = self._random_election_timeout()
        
        self.logger.info(f"Starting election for term {self.current_term}")
        
        # Vote for self
        votes = 1
        total_nodes = len(self.config.cluster_nodes)
        
        # Request votes from other nodes
        vote_tasks = []
        for node in self.config.get_other_nodes():
            task = asyncio.create_task(self._request_vote(node))
            vote_tasks.append(task)
        
        # Wait for vote responses
        if vote_tasks:
            responses = await asyncio.gather(*vote_tasks, return_exceptions=True)
            
            for response in responses:
                if isinstance(response, RequestVoteResponse):
                    if response.term > self.current_term:
                        await self._become_follower(response.term)
                        return
                    elif response.vote_granted:
                        votes += 1
        
        # Check if we won the election
        if votes > total_nodes // 2:
            await self._become_leader()
        else:
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
    
    # RPC Handlers
    
    async def handle_request_vote(self, request: RequestVoteRequest) -> RequestVoteResponse:
        """Handle RequestVote RPC."""
        # Update term if necessary
        if request.term > self.current_term:
            await self._become_follower(request.term)
        
        vote_granted = False
        
        if (request.term == self.current_term and 
            (self.voted_for is None or self.voted_for == request.candidate_id) and
            self._is_log_up_to_date(request.last_log_index, request.last_log_term)):
            
            self.voted_for = request.candidate_id
            self.last_heartbeat = time.time()
            vote_granted = True
            self.logger.info(f"Granted vote to {request.candidate_id} for term {request.term}")
        
        return RequestVoteResponse(term=self.current_term, vote_granted=vote_granted)
    
    async def handle_append_entries(self, request: AppendEntriesRequest) -> AppendEntriesResponse:
        """Handle AppendEntries RPC."""
        # Update term if necessary
        if request.term > self.current_term:
            await self._become_follower(request.term)
        
        success = False
        match_index = 0
        
        if request.term == self.current_term:
            self.last_heartbeat = time.time()
            
            # Check if we can append entries
            if (request.prev_log_index == 0 or 
                (request.prev_log_index <= self.log.last_log_index() and
                 self.log.get_term_at_index(request.prev_log_index) == request.prev_log_term)):
                
                success = True
                
                # Remove conflicting entries
                if request.entries:
                    self.log.truncate_from(request.prev_log_index + 1)
                    
                    # Append new entries
                    for entry in request.entries:
                        self.log.append(entry)
                
                match_index = request.prev_log_index + len(request.entries)
                
                # Update commit index
                if request.leader_commit > self.commit_index:
                    self.commit_index = min(request.leader_commit, self.log.last_log_index())
                    await self._apply_committed_entries()
        
        return AppendEntriesResponse(
            term=self.current_term,
            success=success,
            match_index=match_index
        )
    
    def _is_log_up_to_date(self, last_log_index: int, last_log_term: int) -> bool:
        """Check if the candidate's log is at least as up-to-date as ours."""
        our_last_term = self.log.last_log_term()
        our_last_index = self.log.last_log_index()
        
        if last_log_term > our_last_term:
            return True
        elif last_log_term == our_last_term:
            return last_log_index >= our_last_index
        else:
            return False
    
    # Client operations
    
    async def append_entry(self, command: Any, client_id: str = None) -> bool:
        """Append a new entry to the log (leader only)."""
        if self.state != NodeState.LEADER:
            return False
        
        entry = LogEntry(
            term=self.current_term,
            index=self.log.last_log_index() + 1,
            command=command,
            client_id=client_id
        )
        
        self.log.append(entry)
        self.logger.info(f"Appended entry {entry.index}: {command}")
        
        return True
    
    def get_state_machine_value(self, key: str) -> Any:
        """Get a value from the state machine."""
        return self.state_machine.get(key)
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the node."""
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