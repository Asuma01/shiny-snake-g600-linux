#!/usr/bin/env python3

import serial
import sys
import os
import time
import json
from serial.tools import list_ports

G600_USB_ID = (0x0525, 0xA4A7)
LEGACY_PORT = "/dev/serial/by-id/usb-Linux_5.4.61_with_sunxi_usb_udc_Gadget_Serial_v2.4-if00"


def device_port(required=True):
    override = os.environ.get("G600_SERIAL_PORT")
    if override:
        if os.path.exists(override):
            return override
        if required:
            raise SystemExit(f"Configured display port is unavailable: {override}")
        return None
    matches = sorted({port.device for port in list_ports.comports()
                      if (port.vid, port.pid) == G600_USB_ID})
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit("More than one G600 USB serial port was found. Select one with G600_SERIAL_PORT.")
    if os.path.exists(LEGACY_PORT):
        return LEGACY_PORT
    if required:
        raise SystemExit("G600 display not detected. Check its USB connection and serial-port permission.")
    return None

def command_packet(command, path, flag=0, size=None):
    path = path.encode("ascii")
    packet = bytearray(250)
    packet[:10] = bytes([
        command, 0xef, 0x69, 0, 0, 0,
        len(path), flag, 0, 0
    ])
    packet[10:10+len(path)] = path

    if size is not None:
        start = 10 + len(path)
        packet[start:start+4] = size.to_bytes(4, "little")

    return packet

def read_response(ser, amount=1024):
    return ser.read(amount).rstrip(b"\0")

VIDEO_DIR = "/mnt/UDISK/video/"
LAST_PLAYED = os.path.expanduser("~/.local/state/shinysnake/last-played-video")
PLAYBACK_STATE = os.path.expanduser("~/.local/state/shinysnake/playback-state")
BRIGHTNESS_STATE = os.path.expanduser("~/.local/state/shinysnake/brightness-level")
STARTUP_PLAYER = os.path.expanduser("~/.local/bin/shinysnake-play")
STARTUP_LOG = os.path.expanduser("~/.local/share/shinysnake-play.log")


def simple_packet(command):
    packet = bytearray(250)
    packet[:11] = bytes([command, 0xef, 0x69, 0, 0, 0, 1, 0, 0, 0, 0])
    return packet


def brightness_packet(level):
    if not 1 <= level <= 100:
        raise SystemExit("Brightness must be between 1 and 100")
    packet = simple_packet(0x7b)
    packet[10] = level
    return packet


def brightness_level():
    try:
        with open(BRIGHTNESS_STATE, encoding="ascii") as saved:
            level = int(saved.read().strip())
        if 1 <= level <= 100:
            return level
    except (OSError, ValueError):
        pass
    return 76


def remember_brightness(level):
    os.makedirs(os.path.dirname(BRIGHTNESS_STATE), exist_ok=True)
    temporary = f"{BRIGHTNESS_STATE}.{os.getpid()}.tmp"
    try:
        with open(temporary, "w", encoding="ascii") as output:
            output.write(f"{level}\n")
        os.replace(temporary, BRIGHTNESS_STATE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def brightness_stream():
    with serial.Serial(device_port(), 115200, timeout=0.2) as ser:
        firmware_check(ser)
        print("READY", flush=True)
        for line in sys.stdin:
            try:
                level = int(line.strip())
                packet = brightness_packet(level)
            except (ValueError, SystemExit):
                print("ERROR: Brightness must be between 1 and 100", flush=True)
                continue
            ser.write(packet)
            ser.flush()
            remember_brightness(level)
            print(f"SET {level}", flush=True)


def video_path(filename):
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise SystemExit("Invalid video filename")
    if not filename.lower().endswith(".mp4"):
        raise SystemExit("Select an MP4 video")
    try:
        path = (VIDEO_DIR + filename).encode("ascii")
    except UnicodeEncodeError:
        raise SystemExit("Controller filenames must be ASCII")
    if len(path) > 240:
        raise SystemExit("Video filename is too long for the controller")
    return path.decode("ascii")


def remember_video(filename):
    video_path(filename)
    os.makedirs(os.path.dirname(LAST_PLAYED), exist_ok=True)
    temporary = f"{LAST_PLAYED}.{os.getpid()}.tmp"
    try:
        with open(temporary, "w", encoding="ascii") as state:
            state.write(filename + "\n")
        os.replace(temporary, LAST_PLAYED)
        save_playback_state("playing")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def last_played_video():
    try:
        with open(LAST_PLAYED, encoding="ascii") as state:
            filename = state.read().strip()
        video_path(filename)
        if not os.path.exists(STARTUP_LOG) or os.path.getmtime(LAST_PLAYED) >= os.path.getmtime(STARTUP_LOG):
            return filename
    except (OSError, UnicodeError, SystemExit):
        pass

    try:
        with open(STARTUP_PLAYER, encoding="utf-8") as player:
            for line in player:
                line = line.strip()
                if line.startswith('VIDEO="') and line.endswith('"'):
                    path = line[len('VIDEO="'):-1]
                    if path.startswith(VIDEO_DIR):
                        filename = path[len(VIDEO_DIR):]
                        video_path(filename)
                        return filename
    except (OSError, UnicodeError, SystemExit):
        pass
    return None


def save_playback_state(state):
    os.makedirs(os.path.dirname(PLAYBACK_STATE), exist_ok=True)
    temporary = f"{PLAYBACK_STATE}.{os.getpid()}.tmp"
    try:
        with open(temporary, "w", encoding="ascii") as output:
            output.write(state + "\n")
        os.replace(temporary, PLAYBACK_STATE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def playback_status():
    filename = last_played_video()
    try:
        with open(PLAYBACK_STATE, encoding="ascii") as saved:
            state = saved.read().strip()
    except OSError:
        state = "playing"
    try:
        if os.path.getmtime(STARTUP_LOG) > os.path.getmtime(PLAYBACK_STATE):
            state = "playing"
    except OSError:
        pass
    return {"video": filename, "playing": bool(filename) and state != "stopped"}


def forget_video(filename):
    try:
        with open(LAST_PLAYED, encoding="ascii") as state:
            saved = state.read().strip()
        if saved == filename:
            os.unlink(LAST_PLAYED)
            save_playback_state("stopped")
    except OSError:
        pass


def control_response(ser, timeout=5, limit=65536, require_terminator=False):
    deadline = time.monotonic() + timeout
    last_data = None
    response = bytearray()
    while time.monotonic() < deadline:
        chunk = ser.read(max(1, min(4096, ser.in_waiting)))
        if chunk:
            if not response:
                chunk = chunk.lstrip(b"\0")
            if not chunk:
                continue
            response.extend(chunk)
            last_data = time.monotonic()
            if len(response) > limit:
                raise SystemExit("Controller response exceeded the safe limit")
            if b"\0" in response:
                return bytes(response).split(b"\0", 1)[0]
        elif response and not require_terminator and time.monotonic() - last_data >= 0.4:
            return bytes(response)
    raise SystemExit("Controller did not return a complete response")


def send_control(ser, packet, require_terminator=False):
    ser.reset_input_buffer()
    ser.write(packet)
    ser.flush()
    return control_response(ser, require_terminator=require_terminator)


def send_query(ser, packet, valid, require_terminator=False):
    response = b""
    for attempt in range(3):
        try:
            response = send_control(ser, packet, require_terminator=require_terminator)
        except SystemExit as exc:
            if str(exc) != "Controller did not return a complete response":
                raise
        if valid(response):
            return response
        if attempt < 2:
            time.sleep(0.15)
    raise SystemExit("The display did not answer. Check its USB connection and try Refresh again.")


def storage_values(ser):
    response = send_query(ser, simple_packet(0x64),
                          lambda data: len(data.split(b"-")) == 6 and
                          all(part.isdigit() for part in data.split(b"-")))
    try:
        values = [int(part) for part in response.decode("ascii").split("-")]
    except (ValueError, UnicodeDecodeError):
        raise SystemExit(f"Could not read storage values: {response[:120]!r}")
    if len(values) != 6 or any(value < 0 for value in values):
        raise SystemExit(f"Unexpected storage response: {response[:120]!r}")
    return dict(zip(
        ("internal_total_kib", "internal_used_kib", "internal_valid_kib",
         "card_total_kib", "card_used_kib", "card_valid_kib"), values
    ))


def listed_videos(ser):
    prefix = b"result:dir:file:"
    response = send_query(ser, command_packet(0x65, VIDEO_DIR),
                          lambda data: data.startswith(prefix), require_terminator=True)
    if not response.startswith(prefix):
        raise SystemExit(f"Could not list videos: {response[:120]!r}")
    try:
        names = response[len(prefix):].decode("ascii").split("/")
    except UnicodeDecodeError:
        raise SystemExit("Controller returned filenames that are not ASCII")
    return [name for name in names if name]


def selected_video_size(ser, path):
    for attempt in range(3):
        try:
            response = send_control(ser, command_packet(0x6e, path))
            if response.isdigit():
                return int(response)
            if response:
                raise SystemExit(f"Could not verify selected video: {response[:120]!r}")
        except SystemExit as exc:
            if str(exc) != "Controller did not return a complete response":
                raise
        if attempt < 2:
            time.sleep(0.15)
    raise SystemExit("The display did not answer the selected video's size check. Try Play Selected again.")


def stop_playback(ser):
    ser.reset_input_buffer()
    ser.write(simple_packet(0x79))
    ser.flush()
    time.sleep(0.075)
    ser.write(simple_packet(0x96))
    ser.flush()
    response = control_response(ser)
    if not response.startswith(b"media_stop"):
        raise SystemExit(f"Could not stop playback: {response[:120]!r}")
    save_playback_state("stopped")


def firmware_check(ser):
    hello = simple_packet(0x01)
    hello[10:12] = bytes.fromhex("c5 d3")
    try:
        return send_query(ser, hello, lambda response: response.startswith(b"chs_"))
    except SystemExit as exc:
        if str(exc).startswith("The display did not answer."):
            raise SystemExit("The display did not answer its firmware check. The command was not sent.")
        raise


def clear_screen():
    # CT13INCH accepts a 440 x 1920 BGRA bitmap. This path was tested live
    # with full_png_sucess and needReSend:0 replies on this display.
    if device_port(required=False) is None:
        raise SystemExit("G600 display not detected; screen was not cleared.")
    filename = last_played_video()
    if filename is None:
        raise SystemExit("Play a stored video before clearing, so it can be restored if needed.")
    width, height = 440, 1920
    payload_size = width * height * 4
    restore_path = video_path(filename)

    try:
        with serial.Serial(device_port(), 115200, timeout=1.5, write_timeout=15) as ser:
            firmware = firmware_check(ser)
            if not firmware.startswith(b"chs_113inch"):
                raise SystemExit("This display did not identify as an 11.3-inch G600; screen was not cleared.")
            size_response = send_control(ser, command_packet(0x6e, restore_path))
            if not size_response.isdigit() or int(size_response) < 8:
                raise SystemExit("The stored video for recovery is unavailable. Screen was not cleared.")
            stop_playback(ser)

            ser.write(b"\x2c" * 250)
            ser.flush()
            header = bytearray(250)
            header[:7] = b"\xc8\xef\x69\x00" + payload_size.to_bytes(3, "big")
            ser.write(header)
            ser.flush()

            pixels = b"\x00\x00\x00\xff" * (width * height)
            batch = bytearray()
            for offset in range(0, payload_size, 249):
                block = pixels[offset:offset + 249]
                batch.extend(block)
                batch.extend(bytes(250 - len(block)))
                if len(batch) >= 25000:
                    ser.write(batch)
                    ser.flush()
                    batch.clear()
            if batch:
                ser.write(batch)
                ser.flush()

            ser.reset_input_buffer()
            ser.write(simple_packet(0x86))
            ser.flush()
            response = ser.read(1024).rstrip(b"\0")
            if not response.startswith(b"full_png_sucess"):
                raise SystemExit(f"Screen did not confirm the black frame: {response[:80]!r}")

            ser.reset_input_buffer()
            ser.write(simple_packet(0xcf))
            ser.flush()
            response = ser.read(1024).rstrip(b"\0")
            if not response.startswith(b"needReSend:0"):
                raise SystemExit(f"Screen requested a retry or gave no status: {response[:80]!r}")
    except (Exception, SystemExit) as exc:
        if str(exc).startswith("This display did not identify as an 11.3-inch G600"):
            raise SystemExit(str(exc))
        try:
            restart_and_resume()
        except (Exception, SystemExit) as recovery_exc:
            raise SystemExit(f"Clear failed: {exc}. Recovery also failed: {recovery_exc}")
        raise SystemExit(f"Clear failed: {exc}. Previous video was restored.")
    print("Screen cleared to black; playback stopped. Select a video to play again.")


def restart_and_resume():
    filename = last_played_video()
    if filename is None:
        raise SystemExit("Choose and play a stored video before restarting the display.")
    path = video_path(filename)

    with serial.Serial(device_port(), 115200, timeout=0.2) as ser:
        firmware_check(ser)
        ser.reset_input_buffer()
        ser.write(simple_packet(0x84))
        ser.flush()

    disconnect_deadline = time.monotonic() + 8
    while device_port(required=False) is not None and time.monotonic() < disconnect_deadline:
        time.sleep(0.05)
    if device_port(required=False) is not None:
        raise SystemExit("Restart was sent, but the display did not disconnect.")

    reconnect_deadline = time.monotonic() + 35
    settled = False
    while time.monotonic() < reconnect_deadline:
        if device_port(required=False) is None:
            time.sleep(0.1)
            continue
        if not settled:
            time.sleep(5)
            settled = True
        try:
            with serial.Serial(device_port(), 115200, timeout=0.2) as ser:
                size_response = send_control(ser, command_packet(0x6e, path))
                if not size_response.isdigit() or int(size_response) < 8:
                    time.sleep(0.2)
                    continue
                stop_playback(ser)
                size_response = send_control(ser, command_packet(0x6e, path))
                if not size_response.isdigit() or int(size_response) < 8:
                    time.sleep(0.2)
                    continue
                response = send_control(ser, command_packet(0x78, path, flag=0))
                if not response.startswith(b"play_video_success"):
                    raise SystemExit(f"Display restarted, but could not resume {filename}: {response[:120]!r}")
                remember_video(filename)
                print(f"Display restarted; {filename} is playing")
                return
        except serial.SerialException:
            pass
        except SystemExit as exc:
            if (str(exc) != "Controller did not return a complete response"
                    and not str(exc).startswith("Could not stop playback:")):
                raise
        time.sleep(0.2)
    raise SystemExit("Display restarted, but did not reconnect in time to resume playback.")


def control(action, filename=None):
    if action == "brightness-current":
        print(brightness_level())
        return
    if action == "brightness-live":
        brightness_stream()
        return
    if action == "status":
        print(json.dumps(playback_status()))
        return
    if action == "resume":
        filename = last_played_video()
        if filename is None:
            raise SystemExit("No previous video to start. Use Play Selected first.")
        control("play", filename)
        return
    if action == "restart":
        restart_and_resume()
        return
    if action == "clear":
        clear_screen()
        return
    if action == "brightness":
        try:
            brightness = brightness_packet(int(filename))
        except (TypeError, ValueError):
            raise SystemExit("Brightness must be a number from 1 to 100")
    with serial.Serial(device_port(), 115200, timeout=0.2) as ser:
        if action == "brightness":
            firmware_check(ser)
            ser.write(brightness)
            ser.flush()
            remember_brightness(brightness[10])
            print(f"Brightness command sent: {brightness[10]}%")
        elif action == "storage":
            print(json.dumps(storage_values(ser)))
        elif action == "list":
            print(json.dumps(listed_videos(ser)))
        elif action == "play":
            path = video_path(filename)
            stored_size = selected_video_size(ser, path)
            if stored_size < 8:
                unit = "byte" if stored_size == 1 else "bytes"
                raise SystemExit(
                    f"{filename} is only {stored_size} {unit} on the display "
                    "and is not a playable MP4. Reupload a valid copy or delete this entry."
                )
            try:
                stop_playback(ser)
            except SystemExit as exc:
                if str(exc) == "Controller did not return a complete response":
                    raise SystemExit("The display did not confirm Stop. Try Play Selected again.")
                raise
            if selected_video_size(ser, path) <= 0:
                raise SystemExit("The selected video is no longer available on the display.")
            try:
                response = send_control(ser, command_packet(0x78, path, flag=0))
            except SystemExit as exc:
                if str(exc) == "Controller did not return a complete response":
                    raise SystemExit("The display did not confirm playback. Check the screen before trying Play Selected again.")
                raise
            if not response.startswith(b"play_video_success"):
                raise SystemExit(f"Could not play video: {response[:120]!r}")
            remember_video(filename)
            print("Playback started")
        elif action == "stop":
            stop_playback(ser)
            print("Playback stopped; the last frame may remain on screen")
        elif action == "delete":
            path = video_path(filename)
            firmware_check(ser)
            ser.reset_input_buffer()
            ser.write(command_packet(0x66, path))
            ser.flush()
            time.sleep(0.05)
            firmware_check(ser)
            if filename in listed_videos(ser):
                raise SystemExit("Delete was sent, but the video is still listed")
            forget_video(filename)
            print("Video deleted")

def upload(source, start_playback=True):
    if not os.path.isfile(source):
        raise SystemExit(f"File not found: {source}")

    data = open(source, "rb").read()
    size = len(data)

    filename = os.path.basename(source)
    destination = f"/mnt/UDISK/video/{filename}"

    framed = bytearray()
    for pos in range(0, size, 249):
        block = data[pos:pos+249]
        framed.extend(block)
        framed.extend(bytes(250-len(block)))

    print(f"File: {filename}")
    print(f"Size: {size} bytes")
    print("Uploading...")

    with serial.Serial(device_port(), 115200, timeout=10) as ser:
        ser.reset_input_buffer()

        ser.write(command_packet(0x6f, destination, size=size))
        ser.flush()

        response = read_response(ser)

        if not response.startswith(b"create_success"):
            raise SystemExit(f"Create failed: {response!r}")

        sent = 0

        while sent < len(framed):
            end = min(sent + 25000, len(framed))
            ser.write(framed[sent:end])
            ser.flush()
            sent = end

            percent = sent * 100 // len(framed)
            print(f"\rProgress: {percent}%", end="", flush=True)

        print()
        print("PROCESSING", flush=True)

        time.sleep(1)
        response = read_response(ser, 2048)

        if b"file_rev_done" not in response:
            raise SystemExit(f"Transfer did not finish correctly: {response!r}")

        # Verify stored file size
        ser.reset_input_buffer()
        ser.write(command_packet(0x6e, destination))
        ser.flush()

        response = read_response(ser)

        try:
            stored_size = int(response.split(b"\0")[0])
        except ValueError:
            raise SystemExit(f"Could not verify file: {response!r}")

        if stored_size != size:
            raise SystemExit(
                f"Verification failed: expected {size}, controller reports {stored_size}"
            )

        print("Verified.")

        if start_playback:
            # Start the uploaded video
            ser.reset_input_buffer()
            ser.write(command_packet(0x78, destination, flag=1))
            ser.flush()

            response = read_response(ser)

            if not response.startswith(b"play_video_success"):
                raise SystemExit(f"Play failed: {response!r}")
            remember_video(filename)

    print("Upload complete — video is playing." if start_playback else "Upload complete.")


def upload_only(source):
    filename = os.path.basename(source)
    video_path(filename)
    if not os.path.isfile(source):
        raise SystemExit(f"File not found: {source}")
    size = os.path.getsize(source)
    with serial.Serial(device_port(), 115200, timeout=0.2) as ser:
        if any(name.casefold() == filename.casefold() for name in listed_videos(ser)):
            raise SystemExit(
                f"{filename} is already stored on the display. "
                "Choose a different filename or delete the stored copy first."
            )
        available = storage_values(ser)["internal_valid_kib"] * 1024
        if size > available:
            raise SystemExit(
                f"Not enough display storage for {filename}. "
                f"Video size: {size / 1048576:.2f} MB; "
                f"display reports {available / 1048576:.2f} MB available. "
                "Delete other uploaded videos from Stored Videos to make room, "
                "or choose a smaller MP4."
            )
        stop_playback(ser)
    upload(source, start_playback=False)

def main():
    if len(sys.argv) == 2 and not sys.argv[1].startswith("--"):
        source = os.path.abspath(sys.argv[1])
        try:
            upload(source)
        except SystemExit as exc:
            if not str(exc).startswith("Play failed:"):
                raise
        time.sleep(3)
        control("play", os.path.basename(source))
    elif len(sys.argv) == 3 and sys.argv[1] == "--upload-only":
        upload_only(os.path.abspath(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] in {"--storage", "--list", "--stop", "--resume", "--status", "--restart", "--clear", "--brightness-current", "--brightness-live"}:
        control(sys.argv[1][2:])
    elif len(sys.argv) == 3 and sys.argv[1] in {"--play", "--delete", "--brightness"}:
        control(sys.argv[1][2:], sys.argv[2])
    else:
        raise SystemExit("Usage: shinysnake-upload VIDEO.mp4 | --upload-only VIDEO.mp4 | --storage | --list | --play NAME | --stop | --resume | --status | --delete NAME | --restart | --clear | --brightness 1-100 | --brightness-current | --brightness-live")


if __name__ == "__main__":
    main()
