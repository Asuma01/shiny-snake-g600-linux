#!/usr/bin/python3

import os
import re
import subprocess
import threading
import queue
import json
import time
import hashlib
import math
import sys
import shutil
import tkinter as tk
from tkinter import filedialog, ttk
from controller import device_port

APP_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADER = ([sys.executable, "--controller"] if getattr(sys, "frozen", False)
            else [sys.executable, os.path.join(APP_DIR, "entrypoint.py"), "--controller"])
FFMPEG = os.environ.get("G600_FFMPEG") or (
    os.path.join(APP_DIR, "ffmpeg")
    if os.path.isfile(os.path.join(APP_DIR, "ffmpeg"))
    else "/usr/bin/ffmpeg"
)

events = queue.Queue()
root = tk.Tk()
selected_path = tk.StringVar()
selected = tk.StringVar(value="No video selected")
preview_image = None
preview_mode = "none"
preview_request_id = 0
playback_video = None
playback_running = False
brightness_window = None
brightness_updates = None


def set_busy(busy):
    state = "disabled" if busy else "normal"
    for button in (choose_button, upload_button, refresh_button, play_button,
                   stop_button, delete_button, restart_button, brightness_button,
                   clear_button):
        button.config(state=state)
    if not busy and playback_video is None:
        stop_button.config(state="disabled")


def backend_call(*args):
    result = subprocess.run(
        [*UPLOADER, *args], capture_output=True, text=True,
        timeout=70 if args and args[0] in {"--restart", "--clear"} else 40
    )
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr).strip() or "Controller command failed")
    return result.stdout.strip()


def sync_playback_state():
    global playback_video, playback_running
    state = json.loads(backend_call("--status"))
    playback_video = state["video"]
    playback_running = state["playing"]
    stop_button.config(
        text="Stop" if playback_running else "Start",
        state="normal" if playback_video else "disabled"
    )


def device_worker(action, filename=None):
    try:
        if action in {"refresh", "delete"}:
            if action == "delete":
                backend_call("--delete", filename)
                try:
                    os.unlink(thumbnail_file(filename, "uploaded"))
                except OSError:
                    pass
            storage = json.loads(backend_call("--storage"))
            videos = json.loads(backend_call("--list"))
            events.put(("device_data", (storage, videos, action)))
        elif action in {"play", "stop", "resume", "restart", "clear"}:
            arguments = (f"--{action}", str(filename)) if filename is not None else (f"--{action}",)
            result = backend_call(*arguments)
            events.put(("control_success", result))
    except Exception as exc:
        events.put(("control_error", (action, str(exc))))


def selected_video():
    selected_items = video_list.curselection()
    if not selected_items:
        themed_dialog("No Video Selected", "Select a stored video first.", kind="warning")
        return None
    return video_list.get(selected_items[0])


def brightness_worker(updates):
    process = None
    last_level = None
    try:
        process = subprocess.Popen(
            [*UPLOADER, "--brightness-live"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        ready = process.stdout.readline().strip()
        if ready != "READY":
            raise RuntimeError(ready or "The display did not respond to the brightness control.")
        events.put(("brightness_ready", None))
        while True:
            level = updates.get()
            if level is None:
                break
            closing = False
            while True:
                try:
                    next_level = updates.get_nowait()
                except queue.Empty:
                    break
                if next_level is None:
                    closing = True
                    break
                level = next_level
            if level != last_level:
                process.stdin.write(f"{level}\n")
                process.stdin.flush()
                answer = process.stdout.readline().strip()
                if answer != f"SET {level}":
                    raise RuntimeError(answer or "The display did not accept the brightness change.")
                last_level = level
                events.put(("brightness_set", level))
            if closing:
                break
            time.sleep(0.08)
    except Exception as exc:
        events.put(("brightness_error", str(exc)))
    finally:
        if process is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=3)
        events.put(("brightness_done", last_level))


def open_brightness_slider():
    global brightness_window, brightness_updates
    if brightness_window is not None:
        brightness_window.lift()
        return
    try:
        initial_level = int(backend_call("--brightness-current"))
    except Exception as exc:
        themed_dialog("Controller Error", str(exc), kind="error")
        return

    set_busy(True)
    brightness_updates = queue.Queue()
    brightness_window = tk.Toplevel(root)
    brightness_window.title("Display Brightness")
    brightness_window.resizable(False, False)
    brightness_window.transient(root)
    brightness_window.configure(bg=APP_BG)
    if app_logo is not None:
        brightness_window.iconphoto(True, app_logo)
    panel = tk.Frame(brightness_window, bg=CARD, highlightbackground=LINE,
                     highlightthickness=1, padx=22, pady=20)
    panel.pack(fill="both", expand=True, padx=12, pady=12)
    label(panel, "Display Brightness", font=("DejaVu Sans", 13, "bold")).pack(anchor="w")
    label(panel, "Move the slider to change display brightness.",
          font=("DejaVu Sans", 10), fg=MUTED).pack(anchor="w", pady=(8, 12))
    value_label = label(panel, f"{initial_level}%", font=("DejaVu Sans", 16, "bold"))
    value_label.pack()
    initializing = True

    def changed(value):
        if initializing:
            return
        level = int(float(value))
        value_label.config(text=f"{level}%")
        brightness_updates.put(level)

    scale = tk.Scale(
        panel, from_=1, to=100, orient="horizontal", length=350,
        showvalue=False, command=changed, bg=CARD, fg=INK,
        troughcolor="#d8e5f5", activebackground=BLUE,
        highlightthickness=0, bd=0
    )
    scale.pack(pady=(3, 12))
    scale.set(initial_level)
    initializing = False

    def close():
        global brightness_window
        brightness_window.destroy()
        brightness_window = None
        brightness_updates.put(None)
        device_status.config(text="Finishing brightness adjustment...")

    button(panel, "Close", close, primary=True).pack(anchor="e")
    brightness_window.protocol("WM_DELETE_WINDOW", close)
    brightness_window.update_idletasks()
    width = max(450, brightness_window.winfo_reqwidth())
    height = brightness_window.winfo_reqheight()
    x = root.winfo_rootx() + (root.winfo_width() - width) // 2
    y = root.winfo_rooty() + (root.winfo_height() - height) // 2
    brightness_window.geometry(f"{width}x{height}+{x}+{y}")
    threading.Thread(target=brightness_worker, args=(brightness_updates,), daemon=True).start()


def device_action(action):
    if action == "toggle":
        if playback_video is None:
            return
        action = "stop" if playback_running else "resume"
    filename = selected_video() if action in {"play", "delete"} else None
    if action in {"play", "delete"} and filename is None:
        return
    if action == "delete" and not themed_dialog(
        "Delete Video", f"Permanently delete {filename} from the display?",
        kind="warning", confirm_label="Delete Video", danger=True
    ):
        return
    if action == "restart" and not themed_dialog(
        "Restart Display", "Restart the display and resume the last played video?",
        kind="question", confirm_label="Restart Display"
    ):
        return
    if action == "brightness":
        open_brightness_slider()
        return
    set_busy(True)
    device_status.config(text="Working with the display...")
    threading.Thread(target=device_worker, args=(action, filename), daemon=True).start()


PREVIEW_CACHE = os.path.expanduser("~/.cache/g600-display-linux/previews")
LOCAL_VIDEO_DIRS = ("~/Videos", "~/Downloads", "~/Desktop", "~/Pictures")


def thumbnail_file(name, prefix):
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return os.path.join(PREVIEW_CACHE, f"{prefix}-{digest}.png")


def extract_thumbnail(filename, destination):
    try:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        result = subprocess.run(
            [FFMPEG, "-nostdin", "-threads", "1", "-y",
             "-loglevel", "error", "-i", filename, "-frames:v", "1",
             "-vf", "scale=118:280", destination],
            capture_output=True, timeout=20
        )
        return result.returncode == 0 and os.path.isfile(destination)
    except (OSError, subprocess.TimeoutExpired):
        return False


def show_preview_message(message):
    global preview_image
    preview_image = None
    preview_canvas.delete("all")
    preview_canvas.create_text(59, 140, text=message, fill="#a9c9ee",
                               font=("DejaVu Sans", 9), justify="center",
                               width=108)


def show_preview_file(filename, source=None):
    global preview_image
    try:
        preview_image = tk.PhotoImage(file=filename)
        preview_canvas.delete("all")
        preview_canvas.create_image(59, 140, image=preview_image, anchor="center")
        if source:
            preview_canvas.create_rectangle(0, 258, 118, 280,
                                            fill=SIDEBAR_DARK, outline="")
            preview_canvas.create_text(59, 269, text=source, fill="#ffffff",
                                       font=("DejaVu Sans", 8, "bold"))
        return True
    except (OSError, tk.TclError):
        show_preview_message("Preview unavailable")
        return False


def make_preview(filename):
    global preview_mode, preview_request_id
    preview_mode = "chosen"
    preview_request_id += 1
    preview_file = thumbnail_file(filename, "chosen")
    if extract_thumbnail(filename, preview_file):
        show_preview_file(preview_file, "LOCAL FILE")
    else:
        show_preview_message("Preview unavailable\nfor this MP4")


def find_matching_local_video(name, selected_file):
    matches = []
    if selected_file and os.path.basename(selected_file) == name and os.path.isfile(selected_file):
        return selected_file
    for directory in LOCAL_VIDEO_DIRS:
        directory = os.path.expanduser(directory)
        if not os.path.isdir(directory):
            continue
        for current, folders, files in os.walk(directory):
            folders[:] = [folder for folder in folders if not folder.startswith(".")]
            if name in files:
                matches.append(os.path.join(current, name))
                if len(matches) > 1:
                    return None
    return matches[0] if matches else None


def stored_preview_worker(name, request_id, selected_file):
    source = find_matching_local_video(name, selected_file)
    if source:
        destination = thumbnail_file(name, "local")
        if extract_thumbnail(source, destination):
            events.put(("stored_preview", (name, request_id, destination, "LOCAL COPY")))
            return
    events.put(("stored_preview", (name, request_id, None, None)))


def on_stored_selection(_event=None):
    global preview_mode, preview_request_id
    selected_items = video_list.curselection()
    if not selected_items:
        return
    name = video_list.get(selected_items[0])
    preview_mode = "stored"
    preview_request_id += 1
    request_id = preview_request_id
    uploaded_thumbnail = thumbnail_file(name, "uploaded")
    if os.path.isfile(uploaded_thumbnail):
        show_preview_file(uploaded_thumbnail, "UPLOADED HERE")
        return
    show_preview_message("Loading preview...")
    threading.Thread(target=stored_preview_worker,
                     args=(name, request_id, selected_path.get()), daemon=True).start()


def choose_video():
    directories = (
        os.path.dirname(selected_path.get()),
        os.environ.get("G600_VIDEO_DIR"),
        os.path.expanduser("~/Videos"),
        os.path.expanduser("~/Pictures"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~"),
    )
    initialdir = next(path for path in directories if path and os.path.isdir(path))
    filename = None
    root.lift()
    root.update_idletasks()
    try:
        from file_picker import choose_mp4
        parent_window = f"x11:{root.winfo_id():x}" if os.environ.get("DISPLAY") else ""
        filename = choose_mp4(initialdir, parent_window)
    except Exception:
        pass  # The desktop may not offer a file portal; use another picker below.
    else:
        if filename is None:
            return
    if filename is None and shutil.which("kdialog"):
        result = subprocess.run(
            ["kdialog", "--getopenfilename", initialdir + "/", "*.mp4 *.MP4|MP4 Videos"],
            text=True, capture_output=True,
        )
        if result.returncode == 0:
            filename = result.stdout.strip()
        elif result.returncode == 1:
            return
    elif filename is None and shutil.which("zenity"):
        result = subprocess.run(
            ["zenity", "--file-selection", "--title=Choose MP4 Video",
             "--filename=" + initialdir + "/",
             "--file-filter=MP4 videos | *.mp4 *.MP4"],
            text=True, capture_output=True,
        )
        if result.returncode == 0:
            filename = result.stdout.strip()
        elif result.returncode == 1:
            return
    if filename is None:
        filename = filedialog.askopenfilename(
            parent=root,
            title="Choose MP4 Video",
            initialdir=initialdir,
            filetypes=[("MP4 videos", "*.mp4 *.MP4"), ("All files", "*")],
        )

    if filename:
        selected_path.set(filename)
        selected.set(os.path.basename(filename))
        make_preview(filename)


def upload_worker(filename):
    try:
        process = subprocess.Popen(
            [*UPLOADER, "--upload-only", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        output = ""
        last_progress = -1
        processing_sent = False

        while True:
            char = process.stdout.read(1)

            if char == "" and process.poll() is not None:
                break

            if not char:
                continue

            output += char

            match = re.search(
                r"Progress:\s*(\d+)%",
                output[-120:]
            )

            if match:
                value = int(match.group(1))
                if value != last_progress:
                    last_progress = value
                    events.put(("progress", value))

            if (
                not processing_sent
                and "PROCESSING" in output[-50:]
            ):
                processing_sent = True
                events.put(("processing", None))

        returncode = process.wait()

        if returncode == 0:
            extract_thumbnail(filename, thumbnail_file(os.path.basename(filename), "uploaded"))
            try:
                storage = json.loads(backend_call("--storage"))
                videos = json.loads(backend_call("--list"))
                events.put(("device_data", (storage, videos, "upload")))
                events.put(("success", "Video uploaded. The Stored videos list has been refreshed. Select a video and click Play Selected to start playback."))
            except Exception:
                events.put(("success", "Video uploaded. Click Refresh to update Stored videos, then select a video and click Play Selected."))
        else:
            events.put(("error", output))

    except Exception as exc:
        events.put(("error", str(exc)))


def upload_video():
    filename = selected_path.get()

    if not filename:
        themed_dialog("No Video Selected", "Choose an MP4 video first.", kind="warning")
        return

    set_busy(True)

    start_spinner()
    status.config(text="Uploading...")

    threading.Thread(
        target=upload_worker,
        args=(filename,),
        daemon=True
    ).start()


def check_events():
    global brightness_window, connection_response_failed
    try:
        while True:
            event, data = events.get_nowait()

            if event == "progress":
                status.config(text=f"Uploading... {data}%")

            elif event == "processing":
                status.config(
                    text="Processing. Please wait."
                )

            elif event == "success":
                stop_spinner()

                set_busy(False)

                themed_dialog("Upload Complete", data)

                status.config(text="Upload complete.")
                sync_playback_state()

            elif event == "error":
                stop_spinner()

                set_busy(False)

                status.config(text="Upload failed.")
                sync_playback_state()

                title = ("Not Enough Display Storage"
                         if "Not enough display storage" in data else "Upload Failed")
                themed_dialog(title, data.strip() or "Unknown error", kind="error")

            elif event == "device_data":
                connection_response_failed = False
                render_connection()
                storage, videos, action = data
                refresh_button.config(text="Refresh from Display")
                storage_hint.set("Click Refresh from Display to update storage and saved videos.")
                internal = (storage["internal_total_kib"], storage["internal_used_kib"], storage["internal_valid_kib"])
                storage_text.set(
                    "Total: %.2f MB  ·  Used: %.2f MB  ·  Free: %.2f MB" %
                    tuple(value / 1024 for value in internal)
                )
                storage_total.set(f"{internal[0] / 1024:.2f} MB")
                storage_used.set(f"{internal[1] / 1024:.2f} MB")
                storage_free.set(f"{internal[2] / 1024:.2f} MB")
                previous_selection = video_list.curselection()
                previous_name = video_list.get(previous_selection[0]) if previous_selection else None
                video_list.delete(0, tk.END)
                for name in videos:
                    video_list.insert(tk.END, name)
                if previous_name in videos:
                    video_list.selection_set(videos.index(previous_name))
                    on_stored_selection()
                elif preview_mode == "stored":
                    show_preview_message("Choose a stored\nvideo to preview")
                device_status.config(text=("Video deleted. " if action == "delete" else "") + f"{len(videos)} stored videos")
                set_busy(False)
                sync_playback_state()

            elif event == "stored_preview":
                name, request_id, thumbnail, source = data
                selected_items = video_list.curselection()
                if (request_id == preview_request_id and selected_items
                        and video_list.get(selected_items[0]) == name):
                    if thumbnail:
                        show_preview_file(thumbnail, source)
                    else:
                        show_preview_message("Preview unavailable\nOriginal video not\non this computer")

            elif event == "control_success":
                connection_response_failed = False
                render_connection()
                device_status.config(text=data)
                set_busy(False)
                sync_playback_state()

            elif event == "control_error":
                action, error = data
                if action == "refresh":
                    connection_response_failed = True
                    render_connection()
                device_status.config(text="Controller action failed.")
                set_busy(False)
                sync_playback_state()
                themed_dialog("Controller Error", error, kind="error")

            elif event == "brightness_ready":
                device_status.config(text="Move the slider to adjust brightness.")

            elif event == "brightness_set":
                device_status.config(text=f"Brightness set to {data}%")

            elif event == "brightness_error":
                if brightness_window is not None:
                    brightness_window.destroy()
                    brightness_window = None
                themed_dialog("Controller Error", data, kind="error")

            elif event == "brightness_done":
                set_busy(False)
                sync_playback_state()

    except queue.Empty:
        pass

    root.after(100, check_events)


APP_BG = "#eef4fc"
CARD = "#ffffff"
SIDEBAR = "#103b74"
SIDEBAR_DARK = "#092b56"
INK = "#142c50"
MUTED = "#667f9f"
BLUE = "#145fbd"
BLUE_HOVER = "#0c4e9f"
LINE = "#d8e5f5"


def label(parent, text="", *, font=("DejaVu Sans", 10), fg=INK, bg=CARD, **kwargs):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, **kwargs)


def button(parent, text, command, *, primary=False, danger=False):
    color = BLUE if primary else ("#fff1f1" if danger else "#eaf2fc")
    foreground = "#ffffff" if primary else ("#a23838" if danger else INK)
    return tk.Button(
        parent, text=text, command=command, font=("DejaVu Sans", 10, "bold"),
        bg=color, fg=foreground,
        activebackground=BLUE_HOVER if primary else "#dceafb",
        activeforeground="#ffffff" if primary else foreground,
        disabledforeground="#90a3bb", borderwidth=0, relief="flat",
        padx=16, pady=11, cursor="hand2", highlightthickness=0
    )


def themed_dialog(title, message, *, kind="info", confirm_label=None, danger=False):
    result = {"confirmed": False}
    dialog = tk.Toplevel(root)
    dialog.withdraw()
    dialog.title(title)
    dialog.configure(bg=APP_BG)
    dialog.resizable(False, False)
    dialog.transient(root)
    if app_logo is not None:
        dialog.iconphoto(True, app_logo)

    panel = tk.Frame(dialog, bg=CARD, highlightbackground=LINE, highlightthickness=1,
                     padx=22, pady=20)
    panel.pack(fill="both", expand=True, padx=12, pady=12)
    heading = tk.Frame(panel, bg=CARD)
    heading.pack(fill="x")
    accent = {"info": "#1aa568", "warning": "#d9891b", "error": "#d93030",
              "question": BLUE}[kind]
    symbol = {"info": "✓", "warning": "!", "error": "!", "question": "?"}[kind]
    icon = tk.Canvas(heading, width=38, height=38, bg=CARD, highlightthickness=0)
    icon.pack(side="left", padx=(0, 12))
    icon.create_oval(2, 2, 36, 36, fill=accent, outline=accent)
    icon.create_text(19, 19, text=symbol, fill="#ffffff",
                     font=("DejaVu Sans", 17, "bold"))
    label(heading, title, font=("DejaVu Sans", 13, "bold")).pack(side="left")

    if len(message) > 350:
        details = tk.Frame(panel, bg=CARD)
        details.pack(fill="both", expand=True, pady=(16, 0))
        body = tk.Text(details, width=52, height=8, wrap="word", font=("DejaVu Sans", 10),
                       bg="#f3f8fe", fg=INK, relief="flat", padx=10, pady=10,
                       highlightthickness=1, highlightbackground=LINE)
        body.insert("1.0", message)
        body.config(state="disabled")
        body.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(details, orient="vertical", command=body.yview)
        scroll.pack(side="right", fill="y")
        body.config(yscrollcommand=scroll.set)
    else:
        label(panel, message, font=("DejaVu Sans", 10), fg=INK,
              justify="left", anchor="w", wraplength=420).pack(
                  fill="x", pady=(16, 0))

    actions = tk.Frame(panel, bg=CARD)
    actions.pack(fill="x", pady=(22, 0))

    def close(confirmed):
        result["confirmed"] = confirmed
        dialog.destroy()

    if confirm_label is not None:
        confirm = button(actions, confirm_label, lambda: close(True),
                         primary=not danger, danger=danger)
        confirm.pack(side="right", padx=(8, 0))
        cancel = button(actions, "Cancel", lambda: close(False))
        cancel.pack(side="right")
        cancel.focus_set()
    else:
        confirm = button(actions, "OK", lambda: close(True), primary=True)
        confirm.pack(side="right")
        confirm.focus_set()
        dialog.bind("<Return>", lambda _event: close(True))

    dialog.bind("<Escape>", lambda _event: close(False))
    dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
    dialog.update_idletasks()
    width = max(480, dialog.winfo_reqwidth())
    height = dialog.winfo_reqheight()
    x = root.winfo_rootx() + (root.winfo_width() - width) // 2
    y = root.winfo_rooty() + (root.winfo_height() - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.deiconify()
    dialog.grab_set()
    root.wait_window(dialog)
    return result["confirmed"]


def card(parent, *, padx=18, pady=16):
    outer = tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1)
    inner = tk.Frame(outer, bg=CARD, padx=padx, pady=pady)
    inner.pack(fill="both", expand=True)
    return outer, inner


root.withdraw()
root.title("G600 Display for Linux — Release Candidate")
root.geometry("1180x770")
root.minsize(1040, 690)
root.configure(bg=APP_BG)


def place_on_primary_monitor():
    """Center the window on the desktop's primary XRandR monitor if known."""
    if not shutil.which("xrandr"):
        return
    try:
        output = subprocess.run(["xrandr", "--listmonitors"],
                                capture_output=True, text=True, timeout=3, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return
    monitors = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        match = re.search(r"(\d+)/\d+x(\d+)/\d+([+-]\d+)([+-]\d+)", line)
        if match:
            width, height, left, top = map(int, match.groups())
            monitors.append(("*" in parts[1], width, height, left, top))
    if not monitors:
        return
    _, width, height, left, top = next((monitor for monitor in monitors if monitor[0]), monitors[0])
    x = left + max(0, (width - 1180) // 2)
    y = top + max(0, (height - 770) // 2)
    if x >= 0 and y >= 0:
        root.geometry(f"1180x770+{x}+{y}")

logo_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "g600-display-linux-final.png"
)
if not os.path.isfile(logo_file):
    logo_file = os.path.expanduser("~/.local/share/icons/g600-display-linux.png")
try:
    app_logo = tk.PhotoImage(file=logo_file)
    root.iconphoto(True, app_logo)
    sidebar_logo = app_logo.subsample(8)
except tk.TclError:
    app_logo = None
    sidebar_logo = None

shell = tk.Frame(root, bg=APP_BG)
shell.pack(fill="both", expand=True)

sidebar = tk.Frame(shell, bg=SIDEBAR, width=232)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

if sidebar_logo is not None:
    tk.Label(sidebar, image=sidebar_logo, bg=SIDEBAR).pack(pady=(26, 10))
label(sidebar, "G600 DISPLAY", font=("DejaVu Sans", 14, "bold"),
      fg="#ffffff", bg=SIDEBAR).pack()
label(sidebar, "FOR LINUX", font=("DejaVu Sans", 9, "bold"),
      fg="#a9c9ee", bg=SIDEBAR).pack(pady=(1, 9))
label(sidebar, "RELEASE CANDIDATE", font=("DejaVu Sans", 8, "bold"),
      fg="#ffffff", bg="#286db4", padx=12, pady=5).pack(pady=(0, 18))

tk.Frame(sidebar, bg="#386396", height=1).pack(fill="x", padx=22)
label(sidebar, "VIDEO PREVIEW", font=("DejaVu Sans", 9, "bold"),
      fg="#bcd6f4", bg=SIDEBAR).pack(anchor="w", padx=23, pady=(20, 10))

preview_border = tk.Frame(sidebar, bg="#5ca7e9", padx=2, pady=2)
preview_border.pack(padx=37)
preview_canvas = tk.Canvas(
    preview_border, width=118, height=280, bg=SIDEBAR_DARK,
    highlightthickness=0, bd=0
)
preview_canvas.pack()
preview_canvas.create_text(59, 140, text="Choose an\nMP4 to preview",
                           fill="#9fbddd", font=("DejaVu Sans", 10),
                           justify="center")
label(sidebar, "Unofficial Shiny Snake G600 display controller for Linux.",
      font=("DejaVu Sans", 9), fg="#bcd6f4", bg=SIDEBAR,
      wraplength=192, justify="center").pack(padx=18, pady=(14, 0))

content = tk.Frame(shell, bg=APP_BG, padx=22, pady=18)
content.pack(side="left", fill="both", expand=True)

# Header, including a simple connection indicator that does not send USB commands.
header, header_inner = card(content, padx=22, pady=15)
header.pack(fill="x")
header_left = tk.Frame(header_inner, bg=CARD)
header_left.pack(side="left", fill="x", expand=True)
label(header_left, "G600 Display for Linux", font=("DejaVu Sans", 18, "bold")).pack(anchor="w")
label(header_left, "Choose, upload and manage videos on your case display.",
      font=("DejaVu Sans", 10), fg=MUTED).pack(anchor="w", pady=(4, 0))
connection_panel = tk.Frame(header_inner, bg="#eff6fd", padx=12, pady=9)
connection_panel.pack(side="right")
connection_dot = label(connection_panel, "●", font=("DejaVu Sans", 15),
                       fg="#1fb765", bg="#eff6fd")
connection_dot.pack(side="left")
connection_text = label(connection_panel, "Checking display...", font=("DejaVu Sans", 9, "bold"),
                        bg="#eff6fd")
connection_text.pack(side="left", padx=(7, 0))


connection_response_failed = False


def render_connection():
    try:
        connected = device_port(required=False) is not None
    except SystemExit:
        connected = False
    if not connected:
        connection_dot.config(fg="#d93030")
        connection_text.config(text="Display NOT detected")
    elif connection_response_failed:
        connection_dot.config(fg="#d93030")
        connection_text.config(text="Display not responding")
    else:
        connection_dot.config(fg="#1fb765")
        connection_text.config(text="Display detected")


def update_connection():
    render_connection()
    root.after(3000, update_connection)


top_row = tk.Frame(content, bg=APP_BG)
top_row.pack(fill="x", pady=(14, 0))

upload_card, upload_inner = card(top_row)
upload_card.pack(side="left", fill="both", expand=True, padx=(0, 7))
label(upload_inner, "UPLOAD VIDEO", font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
label(upload_inner, "Choose an MP4, then upload it to the display.",
      fg=MUTED, font=("DejaVu Sans", 9)).pack(anchor="w", pady=(4, 12))
label(upload_inner, "SELECTED FILE", font=("DejaVu Sans", 8, "bold"), fg=MUTED).pack(anchor="w")
label(upload_inner, textvariable=selected, font=("DejaVu Sans", 10, "bold"),
      anchor="w", wraplength=480).pack(anchor="w", fill="x", pady=(3, 12))
upload_actions = tk.Frame(upload_inner, bg=CARD)
upload_actions.pack(fill="x")
choose_button = button(upload_actions, "Choose Video", choose_video)
choose_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
upload_button = button(upload_actions, "Upload Video", upload_video, primary=True)
upload_button.pack(side="left", fill="x", expand=True, padx=(6, 0))
status_row = tk.Frame(upload_inner, bg=CARD, height=40)
status_row.pack(fill="x", pady=(8, 0))
status_row.pack_propagate(False)
status = label(status_row, "Upload only; select a stored video to play it.",
               font=("DejaVu Sans", 9), fg=MUTED, anchor="w")
status.pack(side="left", fill="x", expand=True)
spinner_frame = tk.Frame(status_row, bg=CARD, width=40, height=40)
spinner_frame.pack(side="right")
spinner_canvas = tk.Canvas(spinner_frame, width=40, height=40,
                           bg=CARD, highlightthickness=0)
spinner_canvas.pack()

storage_card, storage_inner = card(top_row)
storage_card.pack(side="left", fill="both", expand=True, padx=(7, 0))
label(storage_inner, "DISPLAY STORAGE", font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
label(storage_inner, "Controller-reported onboard capacity", fg=MUTED,
      font=("DejaVu Sans", 9)).pack(anchor="w", pady=(4, 16))
storage_total = tk.StringVar(value="—")
storage_used = tk.StringVar(value="—")
storage_free = tk.StringVar(value="—")
storage_text = tk.StringVar(value="")
metrics = tk.Frame(storage_inner, bg=CARD)
metrics.pack(fill="x")
for column, (caption, value) in enumerate((
    ("TOTAL", storage_total), ("USED", storage_used), ("FREE", storage_free)
)):
    metric = tk.Frame(metrics, bg="#f3f8fe", padx=12, pady=10)
    metric.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 4, 0))
    label(metric, caption, font=("DejaVu Sans", 8, "bold"),
          fg=MUTED, bg="#f3f8fe").pack(anchor="w")
    label(metric, textvariable=value, font=("DejaVu Sans", 12, "bold"),
          bg="#f3f8fe").pack(anchor="w", pady=(4, 0))
    metrics.grid_columnconfigure(column, weight=1)
storage_hint = tk.StringVar(value="Click Load from Display to see storage and saved videos.")
label(storage_inner, textvariable=storage_hint,
      font=("DejaVu Sans", 9), fg=MUTED).pack(anchor="w", pady=(15, 0))

# Stored videos remain a real listbox with both scrollbars and the same actions.
library_card, library_inner = card(content)
library_card.pack(fill="both", expand=True, pady=(14, 0))
library_head = tk.Frame(library_inner, bg=CARD)
library_head.pack(fill="x", pady=(0, 12))
label(library_head, "STORED VIDEOS", font=("DejaVu Sans", 11, "bold")).pack(side="left")
refresh_button = button(library_head, "Load from Display", lambda: device_action("refresh"))
refresh_button.pack(side="right")

library_body = tk.Frame(library_inner, bg=CARD)
library_body.pack(fill="both", expand=True)
list_frame = tk.Frame(library_body, bg="#f5f9ff", highlightbackground=LINE,
                      highlightthickness=1)
list_frame.pack(side="left", fill="both", expand=True, padx=(0, 14))
list_area = tk.Frame(list_frame, bg="#f5f9ff")
list_area.pack(fill="both", expand=True)
video_list = tk.Listbox(
    list_area, width=45, height=6, exportselection=False,
    bg="#f5f9ff", fg=INK, selectbackground="#c6defb",
    selectforeground=INK, activestyle="none", bd=0,
    relief="flat", highlightthickness=0, font=("DejaVu Sans", 10)
)
video_list.pack(side="left", fill="both", expand=True, padx=(9, 0), pady=8)
video_list.bind("<<ListboxSelect>>", on_stored_selection)
scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=video_list.yview)
scrollbar.pack(side="right", fill="y")
horizontal_scrollbar = ttk.Scrollbar(list_frame, orient="horizontal", command=video_list.xview)
horizontal_scrollbar.pack(side="bottom", fill="x")
video_list.config(yscrollcommand=scrollbar.set, xscrollcommand=horizontal_scrollbar.set)

library_actions = tk.Frame(library_body, bg=CARD, width=202)
library_actions.pack(side="right", fill="y")
library_actions.pack_propagate(False)
play_button = button(library_actions, "Play Selected", lambda: device_action("play"), primary=True)
play_button.pack(fill="x", pady=(0, 8))
stop_button = button(library_actions, "Stop", lambda: device_action("toggle"))
stop_button.pack(fill="x", pady=(0, 8))
delete_button = button(library_actions, "Delete Selected", lambda: device_action("delete"), danger=True)
delete_button.pack(fill="x")
device_status = label(library_inner, "Click Load from Display to see saved videos and storage.",
                      font=("DejaVu Sans", 9), fg=MUTED, anchor="w")
device_status.pack(fill="x", pady=(10, 0))

controls_card, controls_inner = card(content, padx=18, pady=12)
controls_card.pack(fill="x", pady=(14, 0))
label(controls_inner, "DISPLAY CONTROLS", font=("DejaVu Sans", 10, "bold")).pack(
    anchor="w", pady=(0, 10)
)
control_buttons = tk.Frame(controls_inner, bg=CARD)
control_buttons.pack(fill="x")
restart_button = button(control_buttons, "Restart Display", lambda: device_action("restart"))
restart_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
clear_button = button(control_buttons, "Clear Screen", lambda: device_action("clear"))
clear_button.pack(side="left", fill="x", expand=True, padx=6)
brightness_button = button(control_buttons, "Set Brightness", lambda: device_action("brightness"))
brightness_button.pack(side="left", fill="x", expand=True, padx=(6, 0))

# Keep the existing upload animation and worker contracts intact.
spinner_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "assets", "spinner")
if not os.path.isdir(spinner_assets):
    spinner_assets = os.path.expanduser("~/.local/share/shinysnake-gui/spinner")
try:
    spinner_frames = [tk.PhotoImage(file=os.path.join(spinner_assets, f"frame-{index:02d}.png"))
                      for index in range(10)]
except tk.TclError:
    spinner_frames = []
spinner_angle = 0
spinner_running = False


def animate_spinner():
    global spinner_angle
    if not spinner_running:
        return
    spinner_canvas.delete("spinner")
    if spinner_frames:
        spinner_canvas.create_image(20, 20, image=spinner_frames[spinner_angle],
                                    tags="spinner")
        spinner_angle = (spinner_angle + 1) % len(spinner_frames)
    else:
        shades = ("#145fbd", "#317bd0", "#5394db", "#7aafe7", "#a4c8ef",
                  "#c9def7", "#d9e8fa", "#d9e8fa", "#c9def7", "#a4c8ef")
        for index, color in enumerate(shades):
            angle = 2 * math.pi * (index + spinner_angle) / len(shades)
            x = 20 + 13 * math.sin(angle)
            y = 20 - 13 * math.cos(angle)
            radius = 2.8 if index == 0 else 2.4
            spinner_canvas.create_oval(x - radius, y - radius,
                                       x + radius, y + radius,
                                       fill=color, outline="", tags="spinner")
        spinner_angle = (spinner_angle + 1) % len(shades)
    root.after(75, animate_spinner)


def start_spinner():
    global spinner_running, spinner_angle
    if spinner_running:
        return
    spinner_running = True
    spinner_angle = 0
    animate_spinner()


def stop_spinner():
    global spinner_running
    spinner_running = False
    spinner_canvas.delete("spinner")


update_connection()
sync_playback_state()
root.after(100, check_events)
place_on_primary_monitor()
root.deiconify()
root.mainloop()
