# Release candidate status

The tested build is `dist/G600-Display-for-Linux-rc1-x86_64.tar.gz`. Its
companion `.sha256` file verifies the download. This archive is prepared for
review and has not been published.

## Completed

- G600 USB upload, listing, playback, storage, deletion, restart, clear, and
  brightness were tested on the user's SteamOS PC.
- GUI startup and MP4 preview decoding passed in Ubuntu 24.04, Fedora 44, and
  CachyOS container userspaces. The official Bazzite 44 image also decoded
  the MP4 and created the GUI window through the host display socket.
- The Fedora minimal-container font failure was fixed with bundled DejaVu
  fonts and a fallback Fontconfig file.
- The extracted archive's 41 file checksums pass. The executable's bundled
  FFmpeg decodes a preview frame. Third-party notices and FFmpeg source are
  included.
- The project owner approved use of the selected logo on 2026-09-17.
- The project owner chose the MIT license for original app code on 2026-09-17.

## Still to decide or validate

- Community testers on real Ubuntu, Fedora, Bazzite, and CachyOS desktops
  should confirm native file picker behavior and USB serial permissions.
  Container tests share the SteamOS host desktop and USB environment.
- The archive distributes the compiled app and corresponding FFmpeg source.
  The GitHub repository will contain the MIT-licensed application source.
