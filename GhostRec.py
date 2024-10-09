import argparse
import comtypes.client
import getpass
import os
import sounddevice as sd
import subprocess
import threading
import time
import win32pipe, win32file, pywintypes
from datetime import datetime
from pathlib import Path
from pycaw.pycaw import AudioUtilities

# Configuration initialization
def initialize():
    user = getpass.getuser()
    config = {
        "output_path": f"C:\\Users\\{user}\\Dropbox (University of Michigan)\\SRO\\Scripts\\AudioDevice Scripts\\GhostRec\\Recordings",
        "audio_levels": "default",
        "frame_rate": 15,
        "output_format": "mp4",
        "pipe_name": r"\\.\pipe\GhostRecPipe"  # Named pipe for IPC
    }

    # Check if the output path exists, and if not, create it
    if not os.path.exists(config["output_path"]):
        os.makedirs(config["output_path"])

    with open("log.txt", "a") as f:
        f.write(f"User is: {user}\n")

    return config

config = initialize()

comtypes.CoInitialize()
root_folder = Path(__file__).parent.resolve()
devices_file = root_folder / "devices.txt"
default_playback_index = sd.default.device[1]
default_device_info = sd.query_devices(default_playback_index)
default_device_friendly_name = default_device_info['name']

with open(devices_file, "w") as f:
    f.write(f"Default Device ID: {default_device_friendly_name}\n")
comtypes.CoUninitialize()

# Command handler for GhostRec
def command_handler(event_flags, project_name, interviewer_id, sid):
    file_name = create_file_name(project_name, interviewer_id, sid)
    ffmpeg_process = None

    while True:
        if event_flags['start'].is_set() and not ffmpeg_process:
            ffmpeg_process = start_recording(file_name, config)
            event_flags['start'].clear()

        if event_flags['pause'].is_set() and ffmpeg_process:
            pause_recording(ffmpeg_process)
            event_flags['pause'].clear()

        if event_flags['resume'].is_set() and ffmpeg_process:
            resume_recording(ffmpeg_process)
            event_flags['resume'].clear()

        if event_flags['stop'].is_set() and ffmpeg_process:
            stop_recording(ffmpeg_process)
            ffmpeg_process = None
            post_process(file_name)
            event_flags['stop'].clear()

        if event_flags['exit'].is_set():
            if ffmpeg_process:
                stop_recording(ffmpeg_process)
            break

        time.sleep(1)  # Polling interval

# Create unique file name
def create_file_name(project_name, interviewer_id, sid):
    now = datetime.now()
    date_str = now.strftime("%y%m%d-%H%M%S")
    computer_name = os.environ.get("COMPUTERNAME", "Unknown")
    file_name = f"{project_name}_{interviewer_id}_{sid}_{date_str}_{computer_name}.mp4"
    return os.path.join(config['output_path'], file_name)

# Start recording function
def start_recording(file_name, config):
    if not default_device_friendly_name:
        raise Exception("No default audio device found")

    ffmpeg_path = root_folder / "ffmpeg" / "bin" / "ffmpeg.exe"

    ffmpeg_cmd = [
        str(ffmpeg_path),
        '-f', 'gdigrab',  # Screen capture
        '-framerate', str(config['frame_rate']),
        '-i', 'desktop',  # Capture the desktop screen
        '-f', 'dshow',  # Audio capture
        f'-i', f'audio="{default_device_friendly_name}"',  # System audio device
        '-vcodec', 'libx264',  # Video codec
        '-acodec', 'aac',  # Audio codec
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',
        file_name
    ]
    process = subprocess.Popen(ffmpeg_cmd)
    return process

# Pause recording function
def pause_recording(process):
    if process:
        process.send_signal(subprocess.signal.SIGSTOP)  # POSIX only

# Resume recording function
def resume_recording(process):
    if process:
        process.send_signal(subprocess.signal.SIGCONT)  # POSIX only

# Stop recording function
def stop_recording(process):
    if process:
        process.terminate()
        process.wait()

# Post-process recording file
def post_process(file_name):
    final_path = os.path.join(config['output_path'], os.path.basename(file_name))
    os.rename(file_name, final_path)

# Named pipe listener function
def pipe_listener(pipe_name, commands, event_flags):
    while True:
        try:
            pipe = win32pipe.CreateNamedPipe(
                pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                1, 65536, 65536,
                0,
                None
            )

            # Wait for client to connect
            win32pipe.ConnectNamedPipe(pipe, None)

            while True:
                # Read the command from the pipe
                resp = win32file.ReadFile(pipe, 64*1024)
                command = resp[1].strip().decode('utf-8').lower()
                if command in commands:
                    commands[command](event_flags)

        except pywintypes.error as e:
            if e.args[0] == 2:  # ERROR_FILE_NOT_FOUND
                time.sleep(1)  # Wait until the pipe is available

# Main function
def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description='GhostRec Screen/Audio Recorder')
    parser.add_argument('--Project', type=str, required=False, default='UNKNOWN_PROJECT', help='Project name')
    parser.add_argument('--SID', type=str, required=False, default='UNKNOWN_SID', help='Sample ID')
    parser.add_argument('--InterviewerID', type=str, required=False, help='Interviewer ID (computer username if not provided)')
    args = parser.parse_args()

    project_name = args.Project
    sid = args.SID
    interviewer_id = args.InterviewerID if args.InterviewerID else getpass.getuser()

    event_flags = {
        'start': threading.Event(),
        'stop': threading.Event(),
        'pause': threading.Event(),
        'resume': threading.Event(),
        'exit': threading.Event()
    }

    commands = {
        'start': lambda flags: flags['start'].set(),
        'stop': lambda flags: flags['stop'].set(),
        'pause': lambda flags: flags['pause'].set(),
        'resume': lambda flags: flags['resume'].set(),
        'exit': lambda flags: flags['exit'].set()
    }

    # Start command handler thread as daemon
    handler_thread = threading.Thread(target=command_handler, args=(event_flags, project_name, interviewer_id, sid))
    handler_thread.daemon = True
    handler_thread.start()

    # Start named pipe listener thread as daemon
    listener_thread = threading.Thread(target=pipe_listener, args=(config['pipe_name'], commands, event_flags))
    listener_thread.daemon = True
    listener_thread.start()

    # Keep the main thread running, allow threads to operate
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        event_flags['exit'].set()

if __name__ == "__main__":
    main()