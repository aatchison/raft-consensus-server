"""
Raft Log Entry Management

This module defines the data structures and operations for managing log entries
in the Raft consensus algorithm. The log is the core data structure that ensures
consistency across the cluster.

Key concepts:
- LogEntry: Individual commands with metadata (term, index, client info)
- RaftLog: Collection of log entries with operations for replication
- Serialization: Support for network transmission and persistence
"""

from dataclasses import dataclass
from typing import Any, Optional
import json


@dataclass
class LogEntry:
    """
    Represents a single log entry in the Raft log.
    
    Each log entry contains:
    - term: The leader term when the entry was created
    - index: The position of the entry in the log (1-based)
    - command: The actual command to be applied to the state machine
    - client_id: Optional identifier for the client that submitted the command
    
    Log entries are immutable once created and are replicated across all nodes
    in the cluster to ensure consistency.
    """
    term: int                           # Leader term when entry was created
    index: int                          # Position in log (1-based indexing)
    command: Any                        # Command to apply to state machine
    client_id: Optional[str] = None     # Client that submitted the command
    
    def to_dict(self) -> dict:
        """
        Convert log entry to dictionary for serialization.
        
        This is used for JSON serialization when sending entries over the network
        or persisting them to storage.
        
        Returns:
            Dictionary representation of the log entry
        """
        return {
            'term': self.term,
            'index': self.index,
            'command': self.command,
            'client_id': self.client_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LogEntry':
        """
        Create log entry from dictionary.
        
        This is used for deserializing log entries received from the network
        or loaded from persistent storage.
        
        Args:
            data: Dictionary containing log entry data
            
        Returns:
            LogEntry instance created from the dictionary
        """
        return cls(
            term=data['term'],
            index=data['index'],
            command=data['command'],
            client_id=data.get('client_id')
        )
    
    def to_json(self) -> str:
        """
        Convert log entry to JSON string.
        
        Convenience method for JSON serialization.
        
        Returns:
            JSON string representation of the log entry
        """
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LogEntry':
        """
        Create log entry from JSON string.
        
        Convenience method for JSON deserialization.
        
        Args:
            json_str: JSON string containing log entry data
            
        Returns:
            LogEntry instance created from the JSON string
        """
        return cls.from_dict(json.loads(json_str))


class RaftLog:
    """
    Manages the Raft log entries and provides operations for log replication.
    
    The log is a sequence of entries that must be kept consistent across all
    nodes in the cluster. This class provides operations for:
    - Appending new entries (leader only)
    - Retrieving entries for replication
    - Truncating conflicting entries
    - Querying log metadata (size, terms, indices)
    
    The log uses 1-based indexing to match the Raft paper specification.
    """
    
    def __init__(self):
        """
        Initialize an empty Raft log.
        
        The log starts empty with no committed or applied entries.
        """
        self.entries: list[LogEntry] = []    # List of log entries (0-based internally)
        self.commit_index = 0                # Highest index known to be committed
        self.last_applied = 0                # Highest index applied to state machine
    
    def append(self, entry: LogEntry) -> None:
        """
        Append a new entry to the log.
        
        This is typically called by the leader when adding new client commands
        to the log. The entry will be replicated to followers.
        
        Args:
            entry: The log entry to append
        """
        self.entries.append(entry)
    
    def get_entry(self, index: int) -> Optional[LogEntry]:
        """
        Get entry at specific index (1-based).
        
        Args:
            index: 1-based index of the entry to retrieve
            
        Returns:
            LogEntry at the specified index, or None if index is invalid
        """
        if index <= 0 or index > len(self.entries):
            return None
        return self.entries[index - 1]  # Convert to 0-based indexing
    
    def get_entries_from(self, start_index: int) -> list[LogEntry]:
        """
        Get all entries starting from start_index (1-based).
        
        This is used by leaders to get entries that need to be sent to followers
        during log replication.
        
        Args:
            start_index: 1-based index to start from
            
        Returns:
            List of log entries from start_index to the end
        """
        if start_index <= 0:
            return self.entries.copy()
        return self.entries[start_index - 1:]  # Convert to 0-based indexing
    
    def truncate_from(self, index: int) -> None:
        """
        Remove all entries from index onwards (1-based).
        
        This is used when a follower receives entries that conflict with its
        existing log. All conflicting entries must be removed before appending
        the new entries from the leader.
        
        Args:
            index: 1-based index from which to start truncating
        """
        if index <= 0:
            self.entries = []
        else:
            self.entries = self.entries[:index - 1]  # Convert to 0-based indexing
    
    def last_log_index(self) -> int:
        """
        Get the index of the last log entry.
        
        Returns:
            1-based index of the last entry, or 0 if log is empty
        """
        return len(self.entries)
    
    def last_log_term(self) -> int:
        """
        Get the term of the last log entry.
        
        This is used for log comparison during leader election to determine
        which candidate has the most up-to-date log.
        
        Returns:
            Term of the last entry, or 0 if log is empty
        """
        if not self.entries:
            return 0
        return self.entries[-1].term
    
    def get_term_at_index(self, index: int) -> int:
        """
        Get the term of the entry at the given index.
        
        This is used for log consistency checks during replication.
        
        Args:
            index: 1-based index of the entry
            
        Returns:
            Term of the entry at the index, or 0 if index is invalid
        """
        entry = self.get_entry(index)
        return entry.term if entry else 0
    
    def size(self) -> int:
        """
        Get the number of entries in the log.
        
        Returns:
            Total number of entries in the log
        """
        return len(self.entries)