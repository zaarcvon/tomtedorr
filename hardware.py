"""
Hardware control module for Tomten project.
Handles GPIO, servo motors, and lights.
"""

import time
import math
from typing import Optional, Callable

try:
    import RPi.GPIO as GPIO
    import pigpio
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False

from events import get_event_bus, HardwareEvent, HardwareEventType


class EasingFunctions:
    """Collection of easing functions for smooth animations."""
    
    @staticmethod
    def linear(t: float) -> float:
        """Linear interpolation."""
        return t
    
    @staticmethod
    def ease_sine(t: float) -> float:
        """Sinusoidal easing (0 to 1)."""
        return 0.5 * (1 - math.cos(math.pi * t))
    
    @staticmethod
    def ease_in_out(t: float) -> float:
        """Ease in-out function."""
        if t > 0.5:
            return 2 * t * t
        else:
            return -1 + (4 - 2 * t) * t


class DoorController:
    """Controls door servo motor with configurable movement parameters."""
    
    def __init__(self, 
                 pin: int = 23,
                 closed_pulse: int = 1500,
                 open_pulse: int = 700,
                 easing_func: Callable = None,
                 hardware_id: str = "door.open"):
        """
        Initialize door controller.
        
        Args:
            pin: GPIO pin for servo
            closed_pulse: PWM pulse width when door is closed (microseconds)
            open_pulse: PWM pulse width when door is open (microseconds)
            easing_func: Function for smooth movement (default: sine)
            hardware_id: Identifier for this hardware (e.g., "door.open", "door.close")
        """
        self.pin = pin
        self.closed_pulse = closed_pulse
        self.open_pulse = open_pulse
        self.easing_func = easing_func or EasingFunctions.ease_sine
        self.pwm = None
        self.is_open = False
        self.hardware_id = hardware_id
        self.event_bus = get_event_bus()
        
        if HARDWARE_AVAILABLE:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT)
            self.pwm = pigpio.pi()
            self.pwm.set_mode(pin, pigpio.OUTPUT)
            self.pwm.set_PWM_frequency(pin, 50)
    
    def open(self, duration: float = 2.0, steps: int = 40) -> None:
        """
        Open the door smoothly.
        
        Args:
            duration: Time in seconds for door to open
            steps: Number of steps for smooth animation
        """
        self._move(self.closed_pulse, self.open_pulse, duration, steps)
        self.is_open = True
    
    def close(self, duration: float = 0.33, steps: int = 40) -> None:
        """
        Close the door smoothly.
        
        Args:
            duration: Time in seconds for door to close
            steps: Number of steps for smooth animation
        """
        self._move(self.open_pulse, self.closed_pulse, duration, steps)
        self.is_open = False
    
    def _move(self, start_pulse: int, end_pulse: int, duration: float, steps: int = 40) -> None:
        """
        Move servo from start to end position with easing.
        
        Args:
            start_pulse: Starting PWM pulse width
            end_pulse: Ending PWM pulse width
            duration: Time in seconds for movement
            steps: Number of interpolation steps
        """
        # Emit movement start event
        velocity = abs(end_pulse - start_pulse) / duration  # pulse units per second
        self.event_bus.emit(HardwareEvent(
            event_type=HardwareEventType.MOVEMENT_START,
            hardware_id=self.hardware_id,
            velocity=velocity,
            state={"pulse": start_pulse, "velocity": velocity, "duration": duration}
        ))
        
        if not HARDWARE_AVAILABLE or not self.pwm:
            # Simulate in test environment
            time.sleep(duration)
        else:
            time.sleep(0.8)  # Wait for servo to be ready
            
            for i in range(steps + 1):
                t = i / steps
                fraction = self.easing_func(t)
                pulse = start_pulse + fraction * (end_pulse - start_pulse)
                
                # Emit movement update event
                current_time = i / steps * duration
                self.event_bus.emit(HardwareEvent(
                    event_type=HardwareEventType.MOVEMENT_UPDATE,
                    hardware_id=self.hardware_id,
                    velocity=velocity,
                    state={"pulse": pulse, "progress": t, "time": current_time}
                ))
                
                if HARDWARE_AVAILABLE and self.pwm:
                    self.pwm.set_servo_pulsewidth(self.pin, pulse)
                    time.sleep(duration / steps)
                else:
                    time.sleep(duration / steps)
        
        if HARDWARE_AVAILABLE and self.pwm:
            self.pwm.set_servo_pulsewidth(self.pin, 0)
        
        # Emit movement end event
        self.event_bus.emit(HardwareEvent(
            event_type=HardwareEventType.MOVEMENT_END,
            hardware_id=self.hardware_id,
            velocity=velocity,
            state={"pulse": end_pulse, "velocity": velocity, "completed": True}
        ))
    
    def cleanup(self) -> None:
        """Clean up GPIO and PWM resources."""
        if self.pwm:
            self.pwm.stop()
        if HARDWARE_AVAILABLE:
            GPIO.cleanup()


class LightController:
    """Controls light via GPIO pin."""
    
    def __init__(self, pin: int = 17, invert_logic: bool = True):
        """
        Initialize light controller.
        
        Args:
            pin: GPIO pin for light
            invert_logic: If True, False = ON, True = OFF (default for pull-up)
        """
        self.pin = pin
        self.invert_logic = invert_logic
        self.is_on = False
        
        if HARDWARE_AVAILABLE:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT)
            self.off()  # Start with light off
    
    def on(self) -> None:
        """Turn light on."""
        if HARDWARE_AVAILABLE:
            GPIO.output(self.pin, not self.invert_logic)
        self.is_on = True
    
    def off(self) -> None:
        """Turn light off."""
        if HARDWARE_AVAILABLE:
            GPIO.output(self.pin, self.invert_logic)
        self.is_on = False
    
    def toggle(self) -> None:
        """Toggle light state."""
        if self.is_on:
            self.off()
        else:
            self.on()
    
    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if HARDWARE_AVAILABLE:
            GPIO.cleanup()


class HardwareManager:
    """Manages all hardware controllers."""
    
    def __init__(self):
        """Initialize all hardware controllers."""
        self.door = DoorController()
        self.light = LightController()
    
    def execute_action(self, action_type: str, **kwargs) -> None:
        """
        Execute a hardware action.
        
        Args:
            action_type: Type of action ('door.open', 'door.close', 'light.on', 'light.off')
            **kwargs: Additional parameters for the action
        """
        if action_type == 'door.open':
            duration = kwargs.get('duration', 2.0)
            self.door.open(duration=duration)
        elif action_type == 'door.close':
            duration = kwargs.get('duration', 0.33)
            self.door.close(duration=duration)
        elif action_type == 'light.on':
            self.light.on()
        elif action_type == 'light.off':
            self.light.off()
        elif action_type == 'light.toggle':
            self.light.toggle()
    
    def cleanup(self) -> None:
        """Clean up all hardware resources."""
        self.door.cleanup()
        self.light.cleanup()
