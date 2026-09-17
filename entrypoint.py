#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile


def self_check():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg = os.path.join(app_dir, "ffmpeg")
    logo = os.path.join(app_dir, "assets", "g600-display-linux-final.png")
    spinner = os.path.join(app_dir, "assets", "spinner", "frame-00.png")
    font_config = os.path.join(app_dir, "assets", "fonts", "fonts.conf")
    regular_font = os.path.join(app_dir, "assets", "fonts", "DejaVuSans.ttf")
    bold_font = os.path.join(app_dir, "assets", "fonts", "DejaVuSans-Bold.ttf")
    for filename in (ffmpeg, logo, spinner, font_config, regular_font, bold_font):
        if not os.path.isfile(filename):
            raise SystemExit(f"Bundled file is missing: {filename}")
    subprocess.run([ffmpeg, "-version"], stdout=subprocess.DEVNULL, check=True, timeout=10)
    decoded = False
    if len(sys.argv) > 2:
        with tempfile.TemporaryDirectory() as directory:
            image = os.path.join(directory, "preview.png")
            subprocess.run(
                [ffmpeg, "-nostdin", "-threads", "1", "-y", "-loglevel", "error",
                 "-i", sys.argv[2], "-frames:v", "1", "-vf", "scale=118:280", image],
                check=True, timeout=20,
            )
            with open(image, "rb") as preview:
                decoded = preview.read(8) == b"\x89PNG\r\n\x1a\n"
            if not decoded:
                raise SystemExit("Bundled FFmpeg did not create a PNG preview")
    print(json.dumps({"bundle": "ok", "preview_decoded": decoded}))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--licenses":
        app_dir = os.path.dirname(os.path.abspath(__file__))
        notice_paths = (
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "third_party/FFmpeg-LICENSE.md",
            "third_party/FFmpeg-COPYING.LGPLv2.1",
            "third_party/dbus-next-LICENSE",
            "third_party/DejaVu-Fonts-LICENSE",
            "third_party/pyserial-LICENSE.txt",
            "third_party/CPython-copyright",
            "third_party/Tcl-copyright",
            "third_party/Tk-copyright",
            "third_party/PyInstaller-COPYING.txt",
        )
        shared_lib_notices = os.path.join(app_dir, "third_party", "ubuntu-shared-libs")
        notice_paths += tuple(
            f"third_party/ubuntu-shared-libs/{name}"
            for name in sorted(os.listdir(shared_lib_notices))
        )
        for relative_path in notice_paths:
            print(f"\n===== {relative_path} =====\n")
            with open(os.path.join(app_dir, relative_path), encoding="utf-8") as notice:
                print(notice.read())
    elif len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        self_check()
    elif len(sys.argv) > 1 and sys.argv[1] == "--controller":
        del sys.argv[1]
        import serial
        from controller import main as controller_main
        try:
            controller_main()
        except (serial.SerialException, PermissionError) as exc:
            raise SystemExit(
                f"Cannot access the G600 USB serial connection: {exc}. "
                "Check the USB connection and serial-port permission."
            ) from None
    else:
        # Minimal desktop images can omit the system fontconfig setup entirely.
        # Give Tk a bundled fallback without changing a configured desktop.
        if not os.environ.get("FONTCONFIG_FILE") and not os.path.isfile("/etc/fonts/fonts.conf"):
            app_dir = os.path.dirname(os.path.abspath(__file__))
            os.environ["FONTCONFIG_FILE"] = os.path.join(app_dir, "assets", "fonts", "fonts.conf")
        import gui  # noqa: F401 - importing starts the Tk application


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # `--licenses | head` can close stdout before all notices are printed.
        try:
            sys.stdout.close()
        except OSError:
            pass
        raise SystemExit(0) from None
