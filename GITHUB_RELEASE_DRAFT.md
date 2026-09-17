# G600 Display for Linux — RC1

**[Download the app bundle (one x86-64 file)](https://github.com/Asuma01/shiny-snake-g600-linux/releases/download/v0.1.0-rc1/G600-Display-for-Linux-rc1-x86_64.tar.gz)**

Extract the download and run `G600-Display-for-Linux`. This is a portable app,
so there is no separate installer.

This is the first public test candidate for the Shiny Snake G600 11.3-inch USB
case display on modern AMD and Intel x86-64 Linux desktops. It is an
independent, unofficial project. The original app code is available in this
repository under MIT; artwork and bundled components retain separate terms
described in `LICENSE_SCOPE.md`.

## What it does

- Uploads MP4 videos and lists videos already stored on the display.
- Plays a selected video, stops and restarts playback, deletes stored videos,
  and shows onboard storage values.
- Sets brightness, clears the screen, and restarts the controller.
- Saves video preview frames on the computer for videos uploaded through this
  app.

## Download and run

Download `G600-Display-for-Linux-rc1-x86_64.tar.gz` and its matching `.sha256`
file from this release. Extract the archive and run `G600-Display-for-Linux`.
The archive contains full instructions, third-party notices, and the source
archive for the bundled FFmpeg executable. No separate Python, FFmpeg, or
video codec installation is needed. A graphical Linux desktop and USB serial
access are required.

## Testing so far

The main controls were tested with one G600 on SteamOS. GUI startup and MP4
preview decoding passed in Ubuntu 24.04, Fedora 44, and CachyOS container
userspaces. The official Bazzite 44 image also passed preview decoding and
created the GUI window using the host desktop socket. Container checks do not
verify each distribution's own desktop integration or USB permissions.

## Limits and feedback

- MP4 upload only. JPG, PNG, and GIF conversion is not included.
- The app cannot download a video back from the display; no verified export
  command is available.
- Only the G600 11.3-inch controller family is supported. Other display sizes
  and unrelated USB screens are untested.

Please report problems using the details requested in `CONTRIBUTING.md`.
Include the Linux distribution, desktop, action, exact error message, and what
the case screen showed.
