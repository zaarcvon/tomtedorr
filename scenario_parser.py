"""Scenario parser for Tomten project.
Only YAML scenarios are supported in this implementation.
"""

import yaml
import os
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum


class SyncBase(Enum):
    """Timing synchronization base points."""
    DEFAULT = "default"  # Start after previous action ends
    START = "start"      # Relative to start of previous action
    FINISH = "finish"    # Relative to end of previous action
    ABSOLUTE = "absolute"  # Absolute time from scenario start


@dataclass
class Action:
    """Represents a single action in a scenario."""
    
    name: str
    sound: Optional[str] = None
    hardware: Optional[str] = None
    start_time: float = 0.0
    duration: float = 0.0
    duration_mode: str = "truncate"  # 'truncate' or 'stretch'
    parameters: Dict[str, Any] = None
    # Speed-based sound selection
    sounds_by_speed: Optional[Dict[str, str]] = None  # {slow, medium, fast} -> sound files
    creek_sound: Optional[str] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        # Validate duration_mode
        if self.duration_mode not in ("truncate", "stretch"):
            self.duration_mode = "truncate"


@dataclass
class TimingSpec:
    """Specifies when an action should occur."""
    
    base: SyncBase = SyncBase.DEFAULT
    offset: float = 0.0
    
    @classmethod
    def from_string(cls, sync_str: Optional[str]) -> 'TimingSpec':
        """
        Parse timing specification from string.
        
        Examples:
            "default" -> TimingSpec(DEFAULT, 0)
            "start+2" -> TimingSpec(START, 2)
            "finish-1" -> TimingSpec(FINISH, -1)
            "absolute:5.5" -> TimingSpec(ABSOLUTE, 5.5)
        """
        if not sync_str:
            return cls()

        # Support formats like "absolute:5.5", "start+2", "finish-1", "after+1"
        # and allow friendly aliases (e.g. 'after' -> DEFAULT, 'align_finish' -> FINISH)
        if ':' in sync_str:
            base_str, offset_str = sync_str.split(':', 1)
            base = SyncBase.ABSOLUTE
            offset = float(offset_str)
        else:
            # detect +/- offset
            base_part = sync_str
            offset = 0.0
            if '+' in sync_str:
                base_part, offset_str = sync_str.split('+', 1)
                offset = float(offset_str)
            elif '-' in sync_str and sync_str.index('-') > 0:  # Exclude leading minus
                parts = sync_str.rsplit('-', 1)
                base_part, offset_str = parts
                offset = -float(offset_str)

            base_key = base_part.strip().lower()
            # Map textual keys to SyncBase values with friendly aliases
            if base_key in ('default', 'after'):
                base = SyncBase.DEFAULT
            elif base_key == 'start':
                base = SyncBase.START
            elif base_key in ('finish', 'end', 'align_finish', 'finish_align'):
                base = SyncBase.FINISH
            elif base_key in ('absolute', 'abs'):
                base = SyncBase.ABSOLUTE
            else:
                # Fallback to enum lookup (supports direct names like 'START')
                try:
                    base = SyncBase[base_key.upper()]
                except Exception:
                    base = SyncBase.DEFAULT
        
        return cls(base, offset)


class ScenarioFormat:
    """Defines the action mappings for the scenario."""
    def __init__(self, actions_file: str = "actions.yaml"):
        """Initialize action mappings from a YAML file in the same folder.

        The file must exist and contain a mapping; otherwise a FileNotFoundError
        or ValueError is raised. The previous hardcoded fallback mapping has
        been removed.
        """
        file_path = os.path.join(os.path.dirname(__file__), actions_file)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Actions file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            raise ValueError(f"Actions file {file_path} must contain a mapping of actions")

        self.actions: Dict[str, Dict[str, Any]] = data
    
    def add_action(self, name: str, sound: Optional[str] = None, 
                   hardware: Optional[str] = None, params: Optional[Dict] = None) -> None:
        """Add or override an action definition."""
        self.actions[name] = {
            'sound': sound,
            'hardware': hardware,
            'params': params or {}
        }
    
    def get_action(self, name: str) -> Optional[Dict[str, Any]]:
        """Get action definition by name."""
        return self.actions.get(name)


class ScenarioParser:
    """Parses scenario files in various formats."""
    
    def __init__(self, format: ScenarioFormat = None):
        """
        Initialize parser.
        
        Args:
            format: ScenarioFormat instance with action definitions
        """
        self.format = format or ScenarioFormat()
    
    def parse_file(self, filepath: str) -> List[Action]:
        """
        Parse a scenario file.
        Auto-detects format based on file extension.
        
        Args:
            filepath: Path to scenario file
            
        Returns:
            List of Action objects
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Scenario file not found: {filepath}")
        
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        
        with open(filepath, 'r') as f:
            content = f.read()

        if ext in ['.yaml', '.yml']:
            return self._parse_yaml(content)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Only .yaml/.yml supported")
    
    def _parse_yaml(self, content: str) -> List[Action]:
        """Parse YAML scenario format."""
        data = yaml.safe_load(content)
        if not isinstance(data, list):
            data = [data]
        
        actions = []
        prev_action = None
        
        for item in data:
            if isinstance(item, str):
                # Simple string format: "action_name"
                action = self._create_action(item, None, prev_action)
            elif isinstance(item, dict):
                # Complex format with parameters
                action = self._parse_action_dict(item, prev_action)
            else:
                continue
            
            if action:
                actions.append(action)
                prev_action = action
        
        return actions
    
    
    def _parse_action_dict(self, item: Dict[str, Any], prev_action: Optional[Action]) -> Optional[Action]:
        """Parse an action from dictionary format."""
        action_name = item.get('action') or item.get('name')
        if not action_name:
            return None
        
        timing_spec = item.get('timing') or item.get('sync')
        # Merge nested params with top-level fields like duration, duration_mode
        nested_params = item.get('params') or item.get('parameters') or {}
        params = {**nested_params}
        
        # Extract duration and duration_mode from top-level if present
        if 'duration' in item:
            params['duration'] = item['duration']
        if 'duration_mode' in item:
            params['duration_mode'] = item['duration_mode']
        
        return self._create_action(action_name, timing_spec, prev_action, params)
    
    def _create_action(self, action_name: str, timing_spec: Optional[str],
                      prev_action: Optional[Action], 
                      params: Dict[str, Any] = None) -> Optional[Action]:
        """
        Create an Action object from name and timing spec.
        
        Args:
            action_name: Name of the action
            timing_spec: Timing specification string
            prev_action: Previous action for relative timing
            params: Additional parameters
            
        Returns:
            Action object or None if action not found
        """
        action_def = self.format.get_action(action_name)
        if not action_def:
            print(f"Warning: Unknown action: {action_name}")
            return None
        
        # Parse timing
        timing = TimingSpec.from_string(timing_spec)
        
        # Extract duration_mode if provided (default: 'truncate')
        duration_mode = (params or {}).get('duration_mode', 'truncate')
        if duration_mode not in ('truncate', 'stretch'):
            duration_mode = 'truncate'
        
        action = Action(
            name=action_name,
            sound=action_def.get('sound'),
            hardware=action_def.get('hardware'),
            duration_mode=duration_mode,
            sounds_by_speed=action_def.get('sounds_by_speed'),
            creek_sound=action_def.get('creek_sound'),
            parameters=params or action_def.get('params', {})
        )
        # If a duration is provided in parameters, use it for scheduling/visualization
        try:
            param_duration = (params or {}).get('duration')
            if param_duration is not None:
                action.duration = float(param_duration)
        except Exception:
            pass

        # If no duration from params, try to infer from the sound file length
        if (action.duration == 0 or action.duration is None) and action.sound:
            try:
                # Import lazily to avoid hard dependency at module import time
                from audio import SoundLibrary
                lib = SoundLibrary()
                sound_len = lib.get_duration(action.sound)
                if sound_len and sound_len > 0:
                    action.duration = float(sound_len)
            except Exception:
                # If anything goes wrong (missing pygame, file not found), leave duration as-is
                pass

        # If action still has no duration and it is a hardware-only action, give a default 1s duration
        if (action.duration == 0 or action.duration is None) and action.hardware and not action.sound:
            action.duration = 1.0
        
        # Calculate start time based on timing spec
        if timing.base == SyncBase.DEFAULT:
            if prev_action:
                action.start_time = prev_action.start_time + prev_action.duration + timing.offset
            else:
                action.start_time = timing.offset
        elif timing.base == SyncBase.START:
            if prev_action:
                action.start_time = prev_action.start_time + timing.offset
            else:
                action.start_time = timing.offset
        elif timing.base == SyncBase.FINISH:
            if prev_action:
                # Align this action's end with previous action's finish (subtract own duration)
                if action.duration and action.duration > 0:
                    action.start_time = prev_action.start_time + prev_action.duration + timing.offset - action.duration
                else:
                    action.start_time = prev_action.start_time + prev_action.duration + timing.offset
                # Prevent negative start times
                if action.start_time < 0:
                    action.start_time = 0.0
            else:
                action.start_time = timing.offset
        elif timing.base == SyncBase.ABSOLUTE:
            action.start_time = timing.offset
        
        return action
