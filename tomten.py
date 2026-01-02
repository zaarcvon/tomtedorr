import pygame
import time
import os
import sys

# Initialize pygame mixer
pygame.mixer.init()
pygame.mixer.set_num_channels(10)  # Allow multiple sounds to play simultaneously

# Directory for sounds
SOUNDS_DIR = 'sounds'

# Mapping of commands to sounds and physical actions
ACTIONS = {
    'cat.run': {'sound': 'cat.run.mp3', 'physical': None},
    'cat.meaw': {'sound': 'cat.want_into.mp3', 'physical': None},
    'door.open': {'sound': 'door.open.mp3', 'physical': 'open'},
    'door.close': {'sound': 'door.close.mp3', 'physical': 'close'},
    'tomten.walk': {'sound': 'tomten.walk.mp3', 'physical': None},
    'guest.doorbell': {'sound': 'doorbell.mp3', 'physical': None},
    'guest.snowwalk': {'sound': 'outside.snowwalk.mp3', 'physical': None},
}

# Placeholder functions for physical door control
# Replace these with actual hardware control code, e.g., using RPi.GPIO for servo motor
def open_door():
    print("Opening physical door")  # Add hardware code here

def close_door():
    print("Closing physical door")  # Add hardware code here

def parse_sync(sync_str):
    """Parse the sync string like 'start+3', 'finish-3', etc."""
    if sync_str is None:
        return 'default', 0.0
    if '+' in sync_str:
        base, offset_str = sync_str.split('+')
        offset = float(offset_str)
    elif '-' in sync_str:
        base, offset_str = sync_str.split('-')
        offset = -float(offset_str)
    else:
        base = sync_str
        offset = 0.0
    return base, offset

def main(script_file):
    # Read the script file
    with open(script_file, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    # List to hold actions with their start times and details
    action_list = []

    prev_start = 0.0
    prev_dur = 0.0

    for line in lines:
        parts = line.split()
        if not parts:
            continue
        cmd = parts[0]
        if cmd not in ACTIONS:
            print(f"Unknown command: {cmd}")
            continue

        sync_str = None
        if len(parts) >= 3 and parts[1] == '-S':
            sync_str = parts[2]

        base, offset = parse_sync(sync_str)

        sound_file = os.path.join(SOUNDS_DIR, ACTIONS[cmd]['sound'])
        if not os.path.exists(sound_file):
            print(f"Sound file not found: {sound_file}")
            continue

        snd = pygame.mixer.Sound(sound_file)
        dur = snd.get_length()

        if base == 'default':
            # Default: start after previous ends
            this_start = prev_start + prev_dur
        elif base == 'start':
            this_start = prev_start + offset
        elif base == 'finish':
            this_start = prev_start + prev_dur + offset - dur
        else:
            print(f"Unknown sync base: {base}")
            continue

        # Append to list
        action_list.append({
            'start_time': this_start,
            'snd': snd,
            'physical': ACTIONS[cmd]['physical'],
            'dur': dur
        })

        # Update previous
        prev_start = this_start
        prev_dur = dur

    if not action_list:
        print("No actions to perform.")
        return

    # Normalize start times to start from 0
    min_start = min(a['start_time'] for a in action_list)
    for a in action_list:
        a['start_time'] -= min_start
        if a['start_time'] < 0:
            a['start_time'] = 0  # Clamp to 0 if negative

    # Sort by start_time
    action_list.sort(key=lambda a: a['start_time'])
    print(action_list)
    # Execute
    start_abs = time.time()
    current_rel = 0.0

    for action in action_list:
        delay = action['start_time'] - current_rel
        if delay > 0:
            time.sleep(delay)

        # Perform physical action if any
        if action['physical'] == 'open':
            open_door()
        elif action['physical'] == 'close':
            close_door()

        # Play sound
        action['snd'].play()

        current_rel = action['start_time']

    # Wait for the last sound to finish
    max_end = max(a['start_time'] + a['dur'] for a in action_list)
    remaining = max_end - current_rel
    if remaining > 0:
        time.sleep(remaining)

    print("Sequence completed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <txt_file>")
        sys.exit(1)
    main(sys.argv[1])