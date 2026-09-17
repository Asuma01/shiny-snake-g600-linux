# Standalone Linux release draft

The release target is one x86-64 executable containing Python, Tk, pyserial, dbus-next,
artwork, fallback DejaVu fonts, and a static FFmpeg binary for MP4 previews. End users should not
need to install Python, kdialog, FFmpeg, or codecs. This directory is a
staging copy; the working SteamOS installation remains in `~/.local/bin`.

The build uses Ubuntu 22.04 as a compatibility baseline for modern
glibc-based desktop distributions. The first build stage compiles FFmpeg
9.0.1 from its signed official source archive with GPL and nonfree components
disabled. The second stage makes a PyInstaller one-file executable. Docker or
Podman and build packages are needed only on the build machine.

```sh
podman build --format docker -t g600-builder -f Dockerfile .
container_id=$(podman create g600-builder)
podman cp "$container_id:/src/dist/G600-Display-for-Linux" ./dist/
podman cp "$container_id:/src/dist/ffmpeg-9.0.1.tar.xz" ./dist/
podman rm "$container_id"
```

The app asks the desktop file portal to show its preferred file chooser. If a
portal is unavailable, it can use an already installed `kdialog` or `zenity`,
then Tk's built-in picker. None of those optional programs is required to run.
The bundle supplies fonts and a Fontconfig fallback for minimal installations.

`Dockerfile` is the reproducible build recipe. `build-onefile.sh` can also be
run directly on a compatible Linux build host with Python, Tk, PyInstaller,
pyserial, dbus-next, `readelf`, and a static FFmpeg binary supplied as `FFMPEG_BIN`.

The FFmpeg source archive SHA-256 is
`cf38e0e28c7e5605942c4a77755349b0145804a397af37eb1fb4c77cb237f635`.
The build verifies its GPG signature against fingerprint
`FCF986EA15E6E293A5644F10B4322F04D67658D8`. The compiled executable
reports LGPL 2.1 or later. Its exact configuration is in `Dockerfile`.
Distribute the corresponding FFmpeg source and the notices with any public
binary release. The built executable also prints these notices with
`--licenses`.

Run `G600-Display-for-Linux --self-check video.mp4` to verify bundled artwork
and MP4 preview decoding. `--controller --status` checks that the controller
entry point launches without a separate Python installation.

## Release gates

- Test the one-file GUI and USB operations on the G600: file selection,
  preview, detection, listing, upload, play, stop/start, delete, restart,
  clear, and brightness.
- GUI startup and MP4 preview decoding passed in Distrobox userspaces for
  Ubuntu 24.04, Fedora 44, and CachyOS (20260913), on a SteamOS/KDE host.
  These checks do not test each distribution's own desktop integration or USB
  permission policy. The official Bazzite 44.20260915.0 image passed MP4
  preview decoding and created a Tk window through the host's X11 display
  socket. Its own desktop session and USB permission policy remain untested.
- Confirm serial-port access as an ordinary user. Some systems require a USB
  permission rule or serial-device group membership; the optional
  `70-g600-display.rules` provides udev `uaccess` for suitable systems.
- Retain the artwork attribution and license scope notices with the release.

The one-file build does not use AppImage/FUSE. It still depends on a compatible
Linux kernel and glibc, a desktop display server, and USB serial support.
ARM, musl-based distributions, and legacy releases are outside the target.

## Package the release candidate

After building and extracting the executable into `dist/`, run
`./package-release.sh`. It creates a versioned archive and a matching SHA-256
file in `dist/`. The archive contains the executable, tester instructions,
the MIT license and its scope, third-party notices, the optional USB permission rule, and the unmodified
FFmpeg source archive.

Check the archive from an empty directory by extracting it, running
`sha256sum -c SHA256SUMS` inside the extracted folder, and using
`./G600-Display-for-Linux --self-check sample.mp4` with an MP4 file.
