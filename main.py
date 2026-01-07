"""
Main orchestrator for Tomten project.
Coordinates audio, hardware, and scenario execution.
"""

import sys
import time
import threading
from typing import List, Optional
from audio import SoundLibrary, SoundPlayer
from hardware import HardwareManager
from scenario_parser import ScenarioParser, Action


class ScenarioExecutor:
    """Executes scenario sequences with synchronized audio and hardware actions."""
    
    def __init__(self, sounds_dir: str = './sounds', use_hardware: bool = True):
        """
        Initialize executor.
        
        Args:
            sounds_dir: Directory containing sound files
            use_hardware: Whether to use real hardware (False for testing)
        """
        self.sounds_dir = sounds_dir
        self.use_hardware = use_hardware
        
        # Initialize components
        self.sound_library = SoundLibrary(sounds_dir)
        self.sound_player = SoundPlayer(self.sound_library)
        self.hardware = HardwareManager() if use_hardware else None
        self.parser = ScenarioParser()
        
        self.is_running = False
    
    def execute_scenario(self, scenario_path: str, verbose: bool = False) -> None:
        """
        Execute a scenario from file.
        
        Args:
            scenario_path: Path to scenario file
            verbose: Print debug information
        """
        try:
            # Parse scenario
            actions = self.parser.parse_file(scenario_path)
            
            if verbose:
                print(f"Loaded {len(actions)} actions from {scenario_path}")
                for i, action in enumerate(actions):
                    print(f"  {i+1}. {action.name} @ {action.start_time:.2f}s")
            
            # Execute
            self.execute_actions(actions, verbose=verbose)
            
        except Exception as e:
            print(f"Error executing scenario: {e}")
            raise
    
    def execute_actions(self, actions: List[Action], verbose: bool = False) -> None:
        """
        Execute a list of actions with synchronization.
        
        Args:
            actions: List of Action objects
            verbose: Print debug information
        """
        if not actions:
            print("No actions to execute.")
            return
        
        # Register hardware sounds with audio system for event-based playback
        for action in actions:
            if action.sounds_by_speed or action.creek_sound:
                self.sound_player.register_hardware_sounds(
                    action.hardware or action.name,
                    action.sounds_by_speed,
                    action.creek_sound
                )
        
        self.is_running = True
        
        # Normalize start times to begin at 0
        min_start = min(a.start_time for a in actions)
        for action in actions:
            action.start_time -= min_start
        
        # Sort by start time
        actions.sort(key=lambda a: a.start_time)
        
        # Calculate total duration
        max_end = max(a.start_time + a.duration for a in actions)
        
        if verbose:
            print(f"Scenario duration: {max_end:.2f}s")
            print("Starting execution...\n")
        
        # Execute actions
        start_time = time.time()
        current_time = 0.0
        action_threads = []
        
        try:
            for action in actions:
                # Wait until it's time for this action
                delay = action.start_time - current_time
                if delay > 0:
                    time.sleep(delay)
                    current_time = action.start_time
                
                if verbose:
                    elapsed = time.time() - start_time
                    print(f"[{elapsed:.2f}s] Executing: {action.name}")
                
                # Execute action in a thread
                thread = threading.Thread(
                    target=self._execute_single_action,
                    args=(action, verbose)
                )
                thread.daemon = False
                thread.start()
                action_threads.append(thread)
            
            # Wait for all actions to complete
            for thread in action_threads:
                thread.join()
            
            # Wait for remaining audio
            if max_end > current_time:
                time.sleep(max_end - current_time)
            
            if verbose:
                elapsed = time.time() - start_time
                print(f"\n[{elapsed:.2f}s] Scenario completed.")
        
        except KeyboardInterrupt:
            print("\nScenario interrupted by user.")
        finally:
            self.is_running = False
    
    def _execute_single_action(self, action: Action, verbose: bool = False) -> None:
        """
        Execute a single action.
        
        Args:
            action: Action to execute
            verbose: Print debug information
        """
        try:
            # Execute sound
            if action.sound:
                max_duration = action.duration if action.duration > 0 else None
                duration = self.sound_player.play(action.sound, max_duration=max_duration, 
                                                  duration_mode=action.duration_mode)
                action.duration = max(action.duration, duration)
                if verbose:
                    print(f"  -> Playing sound: {action.sound} ({duration:.2f}s, mode={action.duration_mode})")
            
            # Execute hardware action
            if action.hardware and self.use_hardware and self.hardware:
                if verbose:
                    print(f"  -> Executing hardware: {action.hardware}")
                self.hardware.execute_action(action.hardware, **action.parameters)
        
        except Exception as e:
            print(f"Error executing action {action.name}: {e}")
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if self.hardware:
            self.hardware.cleanup()
        self.sound_library.cleanup()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <scenario_file>")
        print("Supported formats: .yaml, .yml, .json, .txt")
        sys.exit(1)
    
    scenario_file = sys.argv[1]
    
    # Determine if hardware should be used
    use_hardware = '--hardware' in sys.argv
    
    # Create executor
    executor = ScenarioExecutor(use_hardware=use_hardware)
    
    try:
        executor.execute_scenario(scenario_file, verbose=True)
    finally:
        executor.cleanup()


if __name__ == "__main__":
    main()
