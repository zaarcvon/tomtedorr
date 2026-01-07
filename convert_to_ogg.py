"""
Convert MP3 files to OGG format using pydub
"""
import subprocess
import sys

# Try to install pydub if not available
try:
    from pydub import AudioSegment
except ImportError:
    print("Installing pydub...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pydub", "-q"])
    from pydub import AudioSegment

def convert_mp3_to_ogg(input_file, output_file):
    """Convert MP3 to OGG format"""
    try:
        print(f"Converting {input_file} to {output_file}...")
        sound = AudioSegment.from_mp3(input_file)
        sound.export(output_file, format="ogg", bitrate="192k")
        print(f"✓ {output_file} created successfully")
        return True
    except Exception as e:
        print(f"Error converting {input_file}: {e}")
        return False

if __name__ == "__main__":
    files_to_convert = [
        ("doorbell.mp3", "doorbell.ogg"),
        ("outside.snowwalk.mp3", "outside.snowwalk.ogg")
    ]
    
    for input_file, output_file in files_to_convert:
        convert_mp3_to_ogg(input_file, output_file)
