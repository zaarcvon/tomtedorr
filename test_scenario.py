"""
Testing utility for Tomten scenarios.
Provides visualization and playback testing without hardware.
"""

import sys
import time
import threading
from typing import List, Optional
from scenario_parser import ScenarioParser, Action
from audio import SoundLibrary, SoundPlayer


class SimpleVisualizer:
    """Provides simple text-based visualization of scenario execution."""
    
    def __init__(self, width: int = 120):
        """
        Initialize visualizer.
        
        Args:
            width: Width of visualization in characters
        """
        self.width = width
        self.name_col_width = 25  # Fixed width for action names column
    
    def draw_timeline(self, actions: List[Action], total_duration: float) -> None:
        """
        Draw a simple timeline of actions.
        
        Args:
            actions: List of actions
            total_duration: Total scenario duration
        """
        print("\n" + "="*self.width)
        print("SCENARIO TIMELINE")
        print("="*self.width)
        
        # Draw timeline header
        self._draw_time_scale(total_duration)
        
        # Draw each action sorted by start time
        sorted_actions = sorted(actions, key=lambda a: a.start_time)
        for i, action in enumerate(sorted_actions, 1):
            self._draw_action_bar(action, total_duration, i)
        
        print("="*self.width + "\n")
    
    def _draw_time_scale(self, total_duration: float) -> None:
        """Draw time scale at top of timeline."""
        timeline_width = self.width - self.name_col_width
        
        # Print name column header
        print("Action".ljust(self.name_col_width), end="")
        
        # Print time scale with proper coverage of full duration
        scale = ""
        step = max(1, int(total_duration / 10))
        
        # Calculate the max time to display - ensure we cover the full duration
        max_time = int(total_duration / step + 1) * step
        
        for i in range(0, max_time + 1, step):
            pos = int(i / total_duration * timeline_width)
            if pos <= timeline_width:  # Allow up to and including timeline_width
                scale = scale.ljust(pos) + f"{i:d}s"
        
        print(scale)
        print("-" * self.width)
    
    def _draw_action_bar(self, action: Action, total_duration: float, index: int) -> None:
        """Draw a single action as a bar on timeline."""
        timeline_width = self.width - self.name_col_width
        
        # Calculate positions in timeline
        start_pos = int(action.start_time / total_duration * timeline_width)
        
        # Duration bar
        if action.duration > 0:
            bar_width = max(1, int(action.duration / total_duration * timeline_width))
        else:
            bar_width = 1  # Instant action
        
        bar = "=" * bar_width
        
        # Determine icon
        if action.sound and action.hardware:
            icon = "*"  # Sound + Hardware
        elif action.sound:
            icon = "~"   # Sound only
        elif action.hardware:
            icon = "#"   # Hardware only
        else:
            icon = "."   # Other
        
        # Build timeline line
        timeline_line = " " * start_pos + icon + bar
        
        # Print name column and timeline
        print("{:<{}}{}".format(action.name, self.name_col_width, timeline_line))
    
    def print_action_details(self, actions: List[Action]) -> None:
        """Print detailed information about each action."""
        print("\n" + "="*self.width)
        print("ACTION DETAILS")
        print("="*self.width)
        
        for i, action in enumerate(actions, 1):
            print(f"\n{i}. {action.name}")
            print(f"   Start: {action.start_time:.2f}s")
            if action.sound:
                print(f"   Sound: {action.sound}")
            if action.hardware:
                print(f"   Hardware: {action.hardware}")
                if action.parameters:
                    for key, value in action.parameters.items():
                        print(f"     - {key}: {value}")
            if action.duration > 0:
                print(f"   Duration: {action.duration:.2f}s")


class MockHardwareDisplay:
    """Mock display for hardware actions without real GPIO."""
    
    def __init__(self, lock: threading.Lock = None):
        """Initialize mock display."""
        self.light_state = False
        self.door_state = "closed"  # closed, opening, open, closing
        self.lock = lock or threading.Lock()
    
    def execute_action(self, action_type: str, **kwargs) -> None:
        """
        Execute and display a hardware action.
        
        Args:
            action_type: Type of action
            **kwargs: Additional parameters
        """
        if action_type == 'door.open':
            duration = kwargs.get('duration', 2.0)
            self._show_door_opening(duration)
        elif action_type == 'door.close':
            duration = kwargs.get('duration', 0.33)
            self._show_door_closing(duration)
        elif action_type == 'light.on':
            self._show_light_on()
        elif action_type == 'light.off':
            self._show_light_off()
        elif action_type == 'light.toggle':
            self._show_light_toggle()
    
    def _show_door_opening(self, duration: float) -> None:
        """Simulate door opening."""
        # Don't show progress bars to avoid interfering with action output
        time.sleep(duration)
        with self.lock:
            print(f"    Door OPEN")
        self.door_state = "open"
    
    def _show_door_closing(self, duration: float) -> None:
        """Simulate door closing."""
        # Don't show progress bars to avoid interfering with action output
        time.sleep(duration)
        with self.lock:
            print(f"    Door CLOSED")
        self.door_state = "closed"
    
    def _show_light_on(self) -> None:
        """Simulate light on."""
        with self.lock:
            print("  Light ON")
        self.light_state = True
    
    def _show_light_off(self) -> None:
        """Simulate light OFF."""
        with self.lock:
            print("  Light OFF")
        self.light_state = False
    
    def _show_light_toggle(self) -> None:
        """Simulate light toggle."""
        if self.light_state:
            self._show_light_off()
        else:
            self._show_light_on()
    
    def print_status(self) -> None:
        """Print current hardware status."""
        light = "ON ✓" if self.light_state else "OFF ✗"
        print(f"\nStatus: Light={light}, Door={self.door_state.upper()}")


class ScenarioTester:
    """Test scenario execution with visualization and mock hardware."""
    
    def __init__(self, sounds_dir: str = './sounds'):
        """
        Initialize tester.
        
        Args:
            sounds_dir: Directory containing sound files
        """
        self.sounds_dir = sounds_dir
        self.sound_library = SoundLibrary(sounds_dir)
        self.sound_player = SoundPlayer(self.sound_library)
        self.output_lock = threading.Lock()
        self.hardware = MockHardwareDisplay(self.output_lock)
        self.parser = ScenarioParser()
        self.visualizer = SimpleVisualizer()
    
    def test_scenario(self, scenario_path: str, show_visualization: bool = True,
                     play_audio: bool = True, simulate_hardware: bool = True) -> None:
        """
        Test a scenario with options for visualization and audio.
        
        Args:
            scenario_path: Path to scenario file
            show_visualization: Show timeline visualization
            play_audio: Play audio files
            simulate_hardware: Show mock hardware actions
        """
        try:
            # Parse scenario
            print(f"Loading scenario: {scenario_path}")
            actions = self.parser.parse_file(scenario_path)
            
            if not actions:
                print("No actions found in scenario.")
                return
            
            # Calculate total duration
            total_duration = max(a.start_time + a.duration for a in actions)
            
            # Show visualization
            if show_visualization:
                self.visualizer.draw_timeline(actions, total_duration)
                self.visualizer.print_action_details(actions)
            
            # Execute
            print("\n" + "="*80)
            print("EXECUTING SCENARIO")
            print("="*80 + "\n")
            
            self._execute_test(actions, play_audio, simulate_hardware)
            
            self.hardware.print_status()
            print("\n✓ Scenario test completed successfully.")
        
        except Exception as e:
            print(f"Error testing scenario: {e}")
            import traceback
            traceback.print_exc()
    
    def _execute_test(self, actions: List[Action], play_audio: bool = True,
                     simulate_hardware: bool = True) -> None:
        """Execute test scenario."""
        start_time = time.time()
        current_time = 0.0
        
        for action in actions:
            # Wait for action timing
            delay = action.start_time - current_time
            if delay > 0:
                time.sleep(delay)
                current_time = action.start_time
            
            elapsed = time.time() - start_time
            with self.output_lock:
                print(f"[{elapsed:.2f}s] {action.name}")
            
            # Play audio in thread
            if play_audio and action.sound:
                def play_sound():
                    # Use action duration and mode
                    max_duration = action.duration if action.duration > 0 else None
                    duration = self.sound_player.play(action.sound, max_duration=max_duration, 
                                                      duration_mode=action.duration_mode)
                    action.duration = max(action.duration, duration)
                
                thread = threading.Thread(target=play_sound)
                thread.daemon = True
                thread.start()
            
            # Execute hardware in thread
            if simulate_hardware and action.hardware:
                def execute_hw():
                    self.hardware.execute_action(action.hardware, **action.parameters)
                
                thread = threading.Thread(target=execute_hw)
                thread.daemon = False
                thread.start()
        
        # Wait for final actions
        max_end = max(a.start_time + a.duration for a in actions)
        remaining = max_end - current_time
        if remaining > 0:
            time.sleep(remaining)


def main():
    """Main entry point for testing."""
    if len(sys.argv) < 2:
        print("Usage: python test_scenario.py <scenario_file> [options]")
        print("\nOptions:")
        print("  --no-audio     Don't play audio")
        print("  --no-hardware  Don't show hardware simulation")
        print("  --no-vis       Don't show visualization")
        sys.exit(1)
    
    scenario_file = sys.argv[1]
    
    # Parse options
    play_audio = '--no-audio' not in sys.argv
    simulate_hardware = '--no-hardware' not in sys.argv
    show_visualization = '--no-vis' not in sys.argv
    
    # Create tester
    tester = ScenarioTester()
    
    # Run test
    tester.test_scenario(
        scenario_file,
        show_visualization=show_visualization,
        play_audio=play_audio,
        simulate_hardware=simulate_hardware
    )


if __name__ == "__main__":
    main()
