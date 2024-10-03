import subprocess
import sys
import os
from datetime import datetime

# Function for initializing configurations
def initialize():
    # Initialize configurations
    config = {
        "output_path": "C:\\blproj\\_DRI",
        "audio_levels": "default",
        "frame_rate": 15,
        "output_format": "mp4",
    }
    return config

config = initialize()

#Command Line Interface Parsing:
def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description='Screen/Audio Recorder')
    parser.add_argument('command', choices=['start', 'stop', 'pause', 'resume', 'exit'])
    args = parser.parse_args()
    return args.command

command = parse_args()

#Creating the File Name:
def create_file_name(project_name, interviewer_id, sid):
    now = datetime.now()
    date_str = now.strftime("%y%m%d-%H%M%S")
    computer_name = os.environ.get("COMPUTERNAME", "Unknown")
    file_name = f"{project_name}_{interviewer_id}_{sid}_{date_str}_{computer_name}.mp4"
    return os.path.join(config['output_path'], file_name)

#Setting Up Recording Parameters and Starting the FFmpeg Recording:
def start_recording(file_name, config):
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'gdigrab',  # Screen capture
        '-framerate', str(config['frame_rate']),
        '-i', 'desktop',  # Capture the desktop screen
        '-f', 'dshow',  # Audio capture
        '-i', 'audio="Microphone (Realtek Audio)"',
        '-vcodec', 'libx264',  # Video codec
        '-acodec', 'aac',  # Audio codec
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',
        file_name
    ]
    process = subprocess.Popen(ffmpeg_cmd)
    return process

if command == 'start':
    project_name = "SampleProject"
    interviewer_id = "12345"
    sid = "67890"
    file_name = create_file_name(project_name, interviewer_id, sid)
    ffmpeg_process = start_recording(file_name, config)

#Handling Pause, Resume, Stop, and Exit Operations:
def pause_recording(process):
    process.send_signal(subprocess.signal.SIGSTOP)  # POSIX only

def resume_recording(process):
    process.send_signal(subprocess.signal.SIGCONT)  # POSIX only

def stop_recording(process):
    process.terminate()
    process.wait()

if command == 'pause' and ffmpeg_process:
    pause_recording(ffmpeg_process)

if command == 'resume' and ffmpeg_process:
    resume_recording(ffmpeg_process)

if command == 'stop' and ffmpeg_process:
    stop_recording(ffmpeg_process)

if command == 'exit':
    if ffmpeg_process:
        stop_recording(ffmpeg_process)
    sys.exit(0)

#Post-Processing:
def post_process(file_name):
    # Convert or move the file if needed (assuming the recording was saved directly in mp4)
    final_path = os.path.join(config['output_path'], os.path.basename(file_name))
    os.rename(file_name, final_path)

if command == 'stop':
    post_process(file_name)