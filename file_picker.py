"""Open the desktop's preferred file chooser through XDG Desktop Portal."""

import asyncio
import os
import secrets
from urllib.parse import urlsplit, unquote_to_bytes

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType


PORTAL = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"


async def _call(bus, message):
    reply = await bus.call(message)
    if reply.message_type != MessageType.METHOD_RETURN:
        raise RuntimeError(reply.body[0] if reply.body else "Desktop portal call failed")
    return reply


async def _open_mp4(initialdir, parent_window):
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        token = "g600_" + secrets.token_hex(12)
        sender = bus.unique_name[1:].replace(".", "_")
        expected_handle = f"{PORTAL_PATH}/request/{sender}/{token}"
        handles = {expected_handle}
        response = asyncio.get_running_loop().create_future()

        def on_message(message):
            if (message.message_type == MessageType.SIGNAL
                    and message.interface == REQUEST_INTERFACE
                    and message.member == "Response"
                    and message.path in handles
                    and not response.done()):
                response.set_result(message.body)

        bus.add_message_handler(on_message)

        async def watch(handle):
            rule = ("type='signal',interface='org.freedesktop.portal.Request',"
                    f"member='Response',path='{handle}'")
            await _call(bus, Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="AddMatch", signature="s", body=[rule],
            ))

        await watch(expected_handle)
        options = {
            "handle_token": Variant("s", token),
            "filters": Variant("a(sa(us))", [
                ["MP4 videos", [[0, "*.mp4"], [0, "*.MP4"]]],
            ]),
            "current_folder": Variant("ay", os.fsencode(initialdir) + b"\0"),
        }
        reply = await _call(bus, Message(
            destination=PORTAL,
            path=PORTAL_PATH,
            interface="org.freedesktop.portal.FileChooser",
            member="OpenFile", signature="ssa{sv}",
            body=[parent_window, "Choose MP4 Video", options],
        ))
        handle = reply.body[0]
        if handle != expected_handle:
            handles.add(handle)
            await watch(handle)

        code, results = await asyncio.wait_for(response, timeout=600)
        if code == 1:
            return None
        if code != 0:
            raise RuntimeError("Desktop file chooser did not return a file")
        uris = results["uris"].value
        if not uris:
            raise RuntimeError("Desktop file chooser returned no files")
        uri = urlsplit(uris[0])
        if uri.scheme != "file" or uri.netloc not in ("", "localhost"):
            raise RuntimeError("Desktop file chooser returned a nonlocal file")
        return os.fsdecode(unquote_to_bytes(uri.path))
    finally:
        bus.disconnect()


def choose_mp4(initialdir, parent_window=""):
    """Return an absolute file path, or None when the user cancels."""
    return asyncio.run(_open_mp4(initialdir, parent_window))
