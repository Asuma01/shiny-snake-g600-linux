# Contributing and reporting problems

The current target is the Shiny Snake G600 11.3-inch USB case display on
modern x86-64 Linux desktops. The app intentionally uploads MP4 files only.

For a useful bug report, include:

- Linux distribution and version, desktop environment, and whether the app was
  downloaded or built from source.
- The action you tried, what appeared on the case screen, and the exact error
  shown by the app.
- Whether **Refresh from Display** detects the device and lists stored videos.
- Whether the standalone executable passes `--self-check` with a local MP4.

Attach a screenshot if it helps. Remove personal filenames and unrelated USB
traffic from any logs before posting them publicly. Please do not upload an
entire USB capture when a short excerpt showing the relevant command and
response will answer the question.

Build instructions are in [BUILDING.md](BUILDING.md). Protocol changes should
be tied to a capture or a repeatable device test, especially for commands that
write to or delete display storage.
