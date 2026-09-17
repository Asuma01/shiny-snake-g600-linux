# Third-party components

This release candidate bundles CPython 3.10, Tcl/Tk 8.6, pyserial 3.5,
dbus-next 0.2.3, DejaVu Sans fonts, and FFmpeg 9.0.1. PyInstaller is used to
create the bundle. Exact license and copyright texts from the build inputs are
in `third_party/` and are printed by the executable's `--licenses` command.
Project references:

- [CPython license](https://docs.python.org/3.10/license.html)
- [Tcl/Tk license](https://www.tcl.tk/software/tcltk/license.html)
- [pyserial license](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt)
- [dbus-next license](https://github.com/altdesktop/python-dbus-next/blob/master/LICENSE)
- [PyInstaller license](https://pyinstaller.org/en/stable/license.html)
- [FFmpeg licensing](https://ffmpeg.org/legal.html)
- [DejaVu fonts license](https://dejavu-fonts.github.io/License.html)

## FFmpeg

The included FFmpeg executable is built from the official 9.0.1 source
archive with `--disable-gpl --disable-nonfree --disable-autodetect`, without
`--enable-version3` or external codec libraries. `ffmpeg -L` identifies its
license as LGPL 2.1 or later. The full build options are in `Dockerfile`.
The corresponding unmodified source archive is distributed as
`dist/ffmpeg-9.0.1.tar.xz` (SHA-256:
`cf38e0e28c7e5605942c4a77755349b0145804a397af37eb1fb4c77cb237f635`).
It is also available from [FFmpeg's release archive](https://ffmpeg.org/releases/ffmpeg-9.0.1.tar.xz).
The build verifies the release's GPG signature against the FFmpeg release key.
FFmpeg's source license overview and LGPL text are in `third_party/` and
included in the executable's `--licenses` output.

The bundled `dbus-next` license text is also in `third_party/` and in
`--licenses` output.

The bundled DejaVu Sans regular and bold fonts provide a fallback when a
desktop has no Fontconfig installation. Their license is in `third_party/`
and in `--licenses` output.

The CPython, Tcl, Tk, PyInstaller, and pyserial notices are also in
`third_party/` and in `--licenses` output. The CPython, Tcl, and Tk copyright
files were copied from the Ubuntu 22.04 build image; the pyserial notice is
from upstream tag v3.5.

The executable also embeds shared libraries from the Ubuntu 22.04 build image
for X11, fonts, compression, cryptography, and other runtime functions. Their
package copyright files are in `third_party/ubuntu-shared-libs/` and in
`--licenses` output.

FFmpeg's license file requests credit to the Independent JPEG Group when
distributing executables. The original FFmpeg source was used without edits
to its JPEG routines.

## Artwork

The project owner approved use of the selected logo on 2026-09-17. The logo
contains a Tux illustration based on user-supplied raster artwork.
The original Tux was created by Larry Ewing using The GIMP; credit Larry
Ewing and The GIMP. The exact provenance and reuse terms of the supplied
derivative raster has not been independently verified. The snake artwork
resembles the manufacturer's mark, and no manufacturer permission is recorded.
See the [original Tux attribution record](https://commons.wikimedia.org/wiki/File:Tux.png).

This notice records the current bundle; it is not a completed publication
review of all packaged components and artwork.
