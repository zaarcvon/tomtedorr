"""
Audio/Sound control module for Tomten project.
Handles sound playback with precise timing and synchronization.
"""

import os
import time
import threading
import tempfile
from typing import Dict, List, Optional
import pygame

# Try to import pydub for audio stretching/shrinking
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

from events import get_event_bus, HardwareEventType


class SoundLibrary:
    """Manages sound file loading and caching."""
    
    def __init__(self, sounds_dir: str = './sounds'):
        """
        Initialize sound library.
        
        Args:
            sounds_dir: Directory containing sound files
        """
        self.sounds_dir = sounds_dir
        self.cache: Dict[str, pygame.mixer.Sound] = {}
        pygame.mixer.init()
        pygame.mixer.set_num_channels(10)
    
    def load_sound(self, filename: str) -> Optional[pygame.mixer.Sound]:
        """
        Load a sound file from cache or disk.
        
        Args:
            filename: Name of the sound file
            
        Returns:
            pygame.mixer.Sound object or None if file not found
        """
        if filename in self.cache:
            return self.cache[filename]
        
        filepath = os.path.join(self.sounds_dir, filename)
        if not os.path.exists(filepath):
            print(f"Warning: Sound file not found: {filepath}")
            return None
        
        try:
            sound = pygame.mixer.Sound(filepath)
            self.cache[filename] = sound
            return sound
        except Exception as e:
            print(f"Error loading sound {filename}: {e}")
            return None
    
    def get_duration(self, filename: str) -> float:
        """
        Get duration of a sound file in seconds.
        
        Args:
            filename: Name of the sound file
            
        Returns:
            Duration in seconds
        """
        sound = self.load_sound(filename)
        if sound:
            return sound.get_length()
        return 0.0
    
    def cleanup(self) -> None:
        """Clean up pygame mixer."""
        pygame.mixer.quit()


class SoundPlayer:
    """Manages synchronized playback of sounds."""
    
    def __init__(self, sound_library: SoundLibrary):
        """
        Initialize sound player.
        
        Args:
            sound_library: SoundLibrary instance
        """
        self.library = sound_library
        self.playing_threads: List[threading.Thread] = []
        self.event_bus = get_event_bus()
        self.hardware_sounds: Dict[str, Dict] = {}  # Cache for hardware sound configs
        self.playing_hardware_sounds: Dict[str, Optional[threading.Thread]] = {}  # Track active hardware sounds
    
    def register_hardware_sounds(self, hardware_id: str, sounds_by_speed: Optional[Dict[str, str]], 
                                 creek_sound: Optional[str]) -> None:
        """
        Register speed-based sounds for a hardware component.
        
        Args:
            hardware_id: Hardware identifier (e.g., "door.open")
            sounds_by_speed: Dict mapping speed categories to sound filenames
            creek_sound: Optional creek/creak sound to play during movement
        """
        self.hardware_sounds[hardware_id] = {
            'sounds_by_speed': sounds_by_speed or {},
            'creek_sound': creek_sound
        }
        # Subscribe to hardware events for this component
        self.event_bus.subscribe_hardware(hardware_id, self._on_hardware_event)
    
    def _on_hardware_event(self, event) -> None:
        """Handle hardware events and select sounds based on velocity."""
        hardware_id = event.hardware_id
        config = self.hardware_sounds.get(hardware_id)
        if not config:
            return
        
        if event.event_type == HardwareEventType.MOVEMENT_START:

            
            # Play creek sound during movement
            if config['creek_sound']:
                self.playing_hardware_sounds[hardware_id] = self._play_creek_start(config['creek_sound'])
        
        elif event.event_type == HardwareEventType.MOVEMENT_END:
            # Select sound based on velocity
            velocity = event.velocity or 0.0
            sound_file = self._select_sound_by_velocity(config['sounds_by_speed'], velocity)
            
            if sound_file:
                # Start playing selected sound
                self.play(sound_file)
                
            # Stop creek sound
            if hardware_id in self.playing_hardware_sounds:
                thread = self.playing_hardware_sounds[hardware_id]
                # Signal thread to stop (via exception or flag)
                self.playing_hardware_sounds[hardware_id] = None


    
    def _select_sound_by_velocity(self, sounds_by_speed: Dict[str, str], velocity: float) -> Optional[str]:
        """
        Select a sound file based on velocity.
        
        Args:
            sounds_by_speed: Dict with 'slow', 'medium', 'fast' keys
            velocity: Velocity value
            
        Returns:
            Sound filename or None
        """
        if not sounds_by_speed:
            return None
        
        # Velocity thresholds (adjustable)
        if velocity < 0.3:
            return sounds_by_speed.get('slow')
        elif velocity < 0.7:
            return sounds_by_speed.get('medium')
        else:
            return sounds_by_speed.get('fast')
    
    def _play_creek_start(self, creek_sound: str) -> Optional[threading.Thread]:
        """
        Start playing a creek sound in a thread (for continuous playback during movement).
        Returns the thread so it can be stopped later.
        """
        def play_creek():
            sound = self.library.load_sound(creek_sound)
            if sound:
                sound.play()
        
        thread = threading.Thread(target=play_creek)
        thread.daemon = True
        thread.start()
        return thread
    
    def play(self, filename: str, max_duration: Optional[float] = None, 
             duration_mode: str = "truncate") -> float:
        """
        Play a sound file with optional duration control and speed adjustment.
        
        Args:
            filename: Name of the sound file
            max_duration: Target duration in seconds (None = full length)
            duration_mode: How to handle max_duration:
                - "truncate": Play only first max_duration seconds, then stop
                - "stretch": Speed up/slow down to fit entire sound into max_duration seconds
            
        Returns:
            Duration of the sound that will be played in seconds
        """
        sound = self.library.load_sound(filename)
        if not sound:
            return 0.0
        
        actual_duration = sound.get_length()
        
        if not max_duration or max_duration <= 0:
            # No duration limit, play full sound
            sound.play()
            return actual_duration
        
        if duration_mode == "stretch":
            # Try to speed up/slow down with pydub
            if HAS_PYDUB:
                return self._play_stretched(filename, actual_duration, max_duration)
            else:
                # Fallback: just truncate if pydub not available
                print("Warning: pydub not available, falling back to truncate mode. Install pydub for stretch support.")
                play_duration = min(actual_duration, max_duration)
                
                def play_with_stop():
                    channel = sound.play()
                    time.sleep(max_duration)
                    if channel and channel.get_busy():
                        channel.stop()
                
                thread = threading.Thread(target=play_with_stop)
                thread.daemon = True
                thread.start()
                self.playing_threads.append(thread)
                return play_duration
        
        # Default: truncate mode - play only first max_duration seconds
        play_duration = min(actual_duration, max_duration)
        
        def play_with_stop():
            channel = sound.play()
            time.sleep(max_duration)
            if channel and channel.get_busy():
                channel.stop()
        
        thread = threading.Thread(target=play_with_stop)
        thread.daemon = True
        thread.start()
        self.playing_threads.append(thread)
        return play_duration
    
    def _play_stretched(self, filename: str, actual_duration: float, target_duration: float) -> float:
        """
        Play audio with speed adjustment to fit target duration.
        
        Args:
            filename: Sound filename
            actual_duration: Original sound duration in seconds
            target_duration: Target duration to fit sound into
            
        Returns:
            Target duration
        """
        try:
            filepath = os.path.join(self.library.sounds_dir, filename)
            audio = AudioSegment.from_file(filepath)
            
            # Calculate speed factor: how much faster to play
            # speed_factor > 1 = faster, speed_factor < 1 = slower
            speed_factor = actual_duration / target_duration
            
            # Use pydub's speedup to adjust playback speed
            stretched = audio.speedup(playback_speed=speed_factor)
            
            # Export to temporary wav file and play
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
                stretched.export(tmp_path, format='wav')
            
            try:
                stretched_sound = pygame.mixer.Sound(tmp_path)
                
                def play_stretched_audio():
                    channel = stretched_sound.play()
                    time.sleep(target_duration)
                    if channel and channel.get_busy():
                        channel.stop()
                    # Clean up temp file after playback
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
                
                thread = threading.Thread(target=play_stretched_audio)
                thread.daemon = True
                thread.start()
                self.playing_threads.append(thread)
                return target_duration
            except Exception as e:
                print(f"Error playing stretched audio: {e}")
                os.unlink(tmp_path)
                raise
        
        except Exception as e:
            print(f"Error stretching {filename}: {e}. Make sure ffmpeg is installed.")
            # Fallback to truncate
            sound = self.library.load_sound(filename)
            play_duration = min(actual_duration, target_duration)
            
            def play_fallback():
                channel = sound.play()
                time.sleep(target_duration)
                if channel and channel.get_busy():
                    channel.stop()
            
            thread = threading.Thread(target=play_fallback)
            thread.daemon = True
            thread.start()
            self.playing_threads.append(thread)
            return play_duration
    
    def wait_for_all(self) -> None:
        """Wait for all playing sounds to finish."""
        for thread in self.playing_threads:
            thread.join()
        self.playing_threads.clear()
