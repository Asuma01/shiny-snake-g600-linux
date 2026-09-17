# G600 Display for Linux — release candidate

## Download the app

**[Download G600 Display for Linux RC1 (x86-64)](https://github.com/Asuma01/shiny-snake-g600-linux/releases/download/v0.1.0-rc1/G600-Display-for-Linux-rc1-x86_64.tar.gz)**

This is one download containing the standalone app and its required notices.
Extract it, then open `G600-Display-for-Linux` to run the app. It does not need
installation, Python, FFmpeg, or additional codecs. See the
[RC1 release page](https://github.com/Asuma01/shiny-snake-g600-linux/releases/tag/v0.1.0-rc1)
for the checksum and release notes.

An unofficial controller for the Shiny Snake G600 11.3-inch USB case display.
It uploads MP4 videos, lists the display's stored videos, controls playback,
shows storage usage, sets brightness, clears the screen, and restarts the
display. Preview frames are saved on the computer, not on the display.

This standalone build is for modern AMD and Intel x86-64 PCs running a
glibc-based Linux desktop. It includes its own Python runtime, serial library,
fallback fonts, and MP4 preview decoder. It does not need a separate Python,
FFmpeg, kdialog, font package, or codec installation. A graphical desktop and
USB serial support are still required.
It was built on Ubuntu 22.04. GUI startup was checked on one SteamOS PC and
in Ubuntu 24.04, Fedora 44, and CachyOS containers. In the official Bazzite
44 image, bundled MP4 decoding passed and the GUI created its expected window
using this PC's desktop display socket. These container checks do not verify
each distribution's native desktop integration or USB permissions. USB control
on other Linux systems still needs community testing.

## Start the app

Extract the release archive. Open `G600-Display-for-Linux` in
your file manager. If your file manager asks whether to run the file, choose
**Run**. If it will not launch, open a terminal in the extracted folder and run:

```sh
chmod +x G600-Display-for-Linux
./G600-Display-for-Linux
```

The app finds the G600 by its USB serial identity (`0525:a4a7`). Use **Refresh
from Display** to load the saved video list and storage values. Uploading an
MP4 adds it to the list; select it and click **Play Selected** to start it.

If the screen
is connected but the app reports a permission error, the local system needs
access to that USB serial device. `70-g600-display.rules` is an optional rule
for distributions using udev and `uaccess`; installing a device rule is a
system administration step and is not required on systems that already grant
access. Other session managers may use a serial-device group instead.

For a bundle check with an MP4 sample:

```sh
./G600-Display-for-Linux --self-check sample.mp4
```

This is a release candidate for testing. The archive includes third-party
notices and the source archive for the bundled FFmpeg executable; keep them
with the program when sharing it. It supports
the G600 11.3-inch controller family confirmed by our captures. Other display
sizes and unrelated USB screens are outside the current scope. The display
does not expose a verified video download command, so this app cannot export
stored MP4 files back to the computer.

## Build from source

The application source, build recipe, and bundled artwork are in this
repository. [BUILDING.md](BUILDING.md) explains how to build the standalone
executable and package a release candidate. Build tools are needed only by
developers; testers can use the release archive above.

The original application code is released under the [MIT license](LICENSE).
The logo, fonts, FFmpeg, and other bundled components retain separate terms;
see [license scope](LICENSE_SCOPE.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).

This is an independent, unofficial project. USB commands were checked against
captures from the official Windows application on one G600. The
[InfoPanel G600 protocol work](https://github.com/habibrehmansg/infopanel/pull/94)
was also used as a research cross-check. It does not replace the captured
behavior of this specific device.
