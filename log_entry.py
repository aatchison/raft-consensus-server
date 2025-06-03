from dataclasses import dataclass
from typing import Any, Optional
import json


@dataclass
class LogEntry:
    """Represents a single log entry in the Raft log."""
    term: int
    index: int
    command: Any
    client_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert log entry to dictionary for serialization."""
        return {
            'term': self.term,
            'index': self.index,
            'command': self.command,
            'client_id': self.client_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LogEntry':
        """Create log entry from dictionary."""
        return cls(
            term=data['term'],
            index=data['index'],
            command=data['command'],
            client_id=data.get('client_id')
        )
    
    def to_json(self) -> str:
        """Convert log entry to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LogEntry':
        """Create log entry from JSON string."""
        return cls.from_dict(json.loads(json_str))


class RaftLog:
    """Manages the Raft log entries."""
    
    def __init__(self):
        self.entries: list[LogEntry] = []
        self.commit_index = 0
        self.last_applied = 0
    
    def append(self, entry: LogEntry) -> None:
        """Append a new entry to the log."""
        self.entries.append(entry)
    
    def get_entry(self, index: int) -> Optional[LogEntry]:
        """Get entry at specific index (1-based)."""
        if index <= 0 or index > len(self.entries):
            return None
        return self.entries[index - 1]
    
    def get_entries_from(self, start_index: int) -> list[LogEntry]:
        """Get all entries starting from start_index (1-based)."""
        if start_index <= 0:
            return self.entries.copy()
        return self.entries[start_index - 1:]
    
    def truncate_from(self, index: int) -> None:
        """Remove all entries from index onwards (1-based)."""
        if index <= 0:
            self.entries = []
        else:
            self.entries = self.entries[:index - 1]
    
    def last_log_index(self) -> int:
        """Get the index of the last log entry."""
        return len(self.entries)
    
    def last_log_term(self) -> int:
        """Get the term of the last log entry."""
        if not self.entries:
            return 0
        return self.entries[-1].term
    
    def get_term_at_index(self, index: int) -> int:
        """Get the term of the entry at the given index."""
        entry = self.get_entry(index)
        return entry.term if entry else 0
    
    def size(self) -> int:
        """Get the number of entries in the log."""
        return len(self.entries)