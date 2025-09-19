from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import time

@dataclass
class TouchEvent:
    type: str
    time: float
    u: Optional[float] = None
    v: Optional[float] = None
    u1: Optional[float] = None
    v1: Optional[float] = None
    u2: Optional[float] = None
    v2: Optional[float] = None
    duration: Optional[int] = None

@dataclass
class TransitionStats:
    attempts: int = 0
    success: int = 0
    avg_time: float = 0.0
    last_success_at: Optional[str] = None

@dataclass
class Transition:
    from_id: str
    to_id: str
    touch_events: List[TouchEvent] = field(default_factory=list)
    stats: TransitionStats = field(default_factory=TransitionStats)
    legacy: bool = False

@dataclass
class Screen:
    id: str
    name: str
    paths: List[str] = field(default_factory=list)
    signature: Optional[str] = None
    pos: Optional[Tuple[int, int]] = None
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FlowData:
    version: str = "2.0"
    created_at: str = ""
    screens: Dict[str, Screen] = field(default_factory=dict)
    transitions: List[Transition] = field(default_factory=list)

@dataclass
class SessionStats:
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    session_duration: float = 0.0
    screens_found: int = 0
    transitions_found: int = 0
    validation_avg_error: Optional[float] = None
    validation_max_error: Optional[float] = None
