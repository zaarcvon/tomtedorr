"""
Event system for Tomten hardware-audio synchronization.
Provides pub-sub event bus for hardware state changes.
"""

from dataclasses import dataclass
from typing import Callable, List, Dict, Any
from enum import Enum


class HardwareEventType(Enum):
    """Types of hardware events."""
    MOVEMENT_START = "movement_start"    # Hardware began movement
    MOVEMENT_UPDATE = "movement_update"  # Position/velocity changed
    MOVEMENT_END = "movement_end"        # Hardware reached target
    STATE_CHANGE = "state_change"        # Generic state change


@dataclass
class HardwareEvent:
    """Event emitted by hardware module."""
    event_type: HardwareEventType
    hardware_id: str              # "door.open", "light.toggle", etc.
    state: Dict[str, Any]         # Current state: {angle, velocity, position, etc.}
    
    # Door-specific fields (optional, for backwards compatibility)
    angle: float = None
    velocity: float = None        # degrees/sec or other movement speed
    position: float = None        # 0-100 or normalized position


class EventBus:
    """Simple pub-sub event bus for hardware events."""
    
    def __init__(self):
        """Initialize event bus."""
        self.subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: HardwareEventType, callback: Callable[[HardwareEvent], None]) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Type of event to listen for
            callback: Function called with HardwareEvent when event fires
        """
        key = event_type.value
        if key not in self.subscribers:
            self.subscribers[key] = []
        self.subscribers[key].append(callback)
    
    def subscribe_hardware(self, hardware_id: str, callback: Callable[[HardwareEvent], None]) -> None:
        """
        Subscribe to all events from a specific hardware.
        
        Args:
            hardware_id: Hardware identifier (e.g., "door.open")
            callback: Function called with HardwareEvent
        """
        key = f"hw:{hardware_id}"
        if key not in self.subscribers:
            self.subscribers[key] = []
        self.subscribers[key].append(callback)
    
    def emit(self, event: HardwareEvent) -> None:
        """
        Emit an event to all subscribers.
        
        Args:
            event: HardwareEvent to emit
        """
        # Notify event-type subscribers
        key = event.event_type.value
        if key in self.subscribers:
            for callback in self.subscribers[key]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in event callback: {e}")
        
        # Notify hardware-specific subscribers
        hw_key = f"hw:{event.hardware_id}"
        if hw_key in self.subscribers:
            for callback in self.subscribers[hw_key]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in hardware event callback: {e}")


# Global event bus
_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus."""
    return _event_bus
