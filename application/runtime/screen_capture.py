from __future__ import annotations

import asyncio
import os
import secrets
import threading
import time
from typing import Any
import gi
import numpy as np
from PIL import Image

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType, MessageType

from application.state import ScreenRegion


# ============================================================
# GSTREAMER INITIALIZATION
# ============================================================

Gst.init(None)


# ============================================================
# XDG DESKTOP PORTAL CONSTANTS
# ============================================================

PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"

SCREENCAST_IFACE = "org.freedesktop.portal.ScreenCast"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"


# ============================================================
# STATIC INTROSPECTION XML
#
# Do not introspect the complete portal object with dbus-next.
# On the current Ubuntu/portal stack, another portal interface
# exposes "power-saver-enabled", which dbus-next can reject
# during introspection parsing.
#
# Only the interfaces required by SubVision are declared here.
# ============================================================

SCREENCAST_XML = """
<node>
  <interface name="org.freedesktop.portal.ScreenCast">

    <method name="CreateSession">
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="handle" type="o" direction="out"/>
    </method>

    <method name="SelectSources">
      <arg name="session_handle" type="o" direction="in"/>
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="handle" type="o" direction="out"/>
    </method>

    <method name="Start">
      <arg name="session_handle" type="o" direction="in"/>
      <arg name="parent_window" type="s" direction="in"/>
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="handle" type="o" direction="out"/>
    </method>

    <method name="OpenPipeWireRemote">
      <arg name="session_handle" type="o" direction="in"/>
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="fd" type="h" direction="out"/>
    </method>

  </interface>
</node>
"""


SESSION_XML = """
<node>
  <interface name="org.freedesktop.portal.Session">
    <method name="Close"/>
  </interface>
</node>
"""


# ============================================================
# ERRORS
# ============================================================

class ScreenCaptureError(RuntimeError):
    """Base error for the SubVision screen-capture service."""


class ScreenCapturePermissionError(ScreenCaptureError):
    """The user cancelled or denied the Portal screen-share request."""


class ScreenCaptureTimeoutError(ScreenCaptureError):
    """Portal startup or frame acquisition exceeded its timeout."""


# ============================================================
# PORTAL REQUEST TRACKER
#
# CreateSession / SelectSources / Start return a Request object
# path first. Their actual result arrives asynchronously through:
#
#     org.freedesktop.portal.Request.Response
# ============================================================

class _RequestTracker:
    def __init__(
        self,
        bus: MessageBus,
    ) -> None:
        self._responses: dict[
            str,
            tuple[
                int,
                dict[str, Any],
            ],
        ] = {}

        self._waiters: dict[
            str,
            asyncio.Future[
                tuple[
                    int,
                    dict[str, Any],
                ]
            ],
        ] = {}

        bus.add_message_handler(
            self._on_message
        )

    def _on_message(
        self,
        message,
    ) -> None:
        if (
            message.message_type
            != MessageType.SIGNAL
        ):
            return

        if (
            message.interface
            != REQUEST_IFACE
        ):
            return

        if (
            message.member
            != "Response"
        ):
            return

        request_path = message.path
        response_code = message.body[0]
        results = message.body[1]

        waiter = self._waiters.pop(
            request_path,
            None,
        )

        if waiter is not None:
            if not waiter.done():
                waiter.set_result(
                    (
                        response_code,
                        results,
                    )
                )

            return

        # The signal may arrive before wait() is registered.
        self._responses[
            request_path
        ] = (
            response_code,
            results,
        )

    async def wait(
        self,
        request_path: str,
    ) -> tuple[
        int,
        dict[str, Any],
    ]:
        cached = self._responses.pop(
            request_path,
            None,
        )

        if cached is not None:
            return cached

        loop = asyncio.get_running_loop()

        future: asyncio.Future[
            tuple[
                int,
                dict[str, Any],
            ]
        ] = loop.create_future()

        self._waiters[
            request_path
        ] = future

        return await future


# ============================================================
# HELPERS
# ============================================================

def _value_of(
    value: Any,
) -> Any:
    if isinstance(
        value,
        Variant,
    ):
        return value.value

    return value


def _make_token(
    prefix: str,
) -> str:
    return (
        prefix
        + secrets.token_hex(8)
    )


def _region_coordinates(
    region: ScreenRegion,
) -> tuple[
    int,
    int,
    int,
    int,
]:
    """
    Read ScreenRegion without coupling the capture layer to
    one concrete ScreenRegion implementation detail.
    """

    coordinates = getattr(
        region,
        "coordinates",
        None,
    )

    if coordinates is not None:
        if callable(coordinates):
            coordinates = coordinates()

        x1, y1, x2, y2 = coordinates

    else:
        x1 = getattr(
            region,
            "x1",
        )

        y1 = getattr(
            region,
            "y1",
        )

        x2 = getattr(
            region,
            "x2",
        )

        y2 = getattr(
            region,
            "y2",
        )

    return (
        int(x1),
        int(y1),
        int(x2),
        int(y2),
    )


# ============================================================
# SCREEN CAPTURE ADAPTER
# ============================================================

class ScreenCaptureAdapter:
    """
    Persistent Wayland screen-capture service.

    Backend:
        XDG Desktop Portal
        -> ScreenCast session
        -> PipeWire remote
        -> GStreamer pipewiresrc
        -> BGR numpy frame

    Public lifecycle:

        capture_adapter.start()

        image = capture_adapter.capture(
            selected_region
        )

        capture_adapter.close()

    Important behavior:

    1. start() is NON-BLOCKING.
       It starts Portal setup on a dedicated thread so the Qt
       GUI does not have to block while GNOME displays the
       "Share Screen" permission dialog.

    2. The Portal + PipeWire session remains alive between
       capture() calls.

       Manual mode:
           Start -> Share once -> R -> R -> R ...

       Auto mode:
           Start -> Share once -> capture every timer cycle.

    3. capture() waits for a NEW PipeWire frame after the call
       begins. This is intentional. The runtime hides SubVision
       before calling capture(), so waiting for a fresh frame
       avoids returning an old frame that still contains the
       SubVision overlay.

    4. Region coordinates are logical Qt/Portal coordinates.
       QScreen.devicePixelRatio() is deliberately NOT used.

       Effective capture scale is derived from:

           PipeWire frame size / Portal logical monitor size

       Example from the current machine:

           Portal:    1536 x 864
           PipeWire:  1920 x 1080
           scale:     1.25 x 1.25
    """

    def __init__(
        self,
        *,
        startup_timeout_seconds: float = 120.0,
        frame_timeout_seconds: float = 5.0,
    ) -> None:
        if startup_timeout_seconds <= 0:
            raise ValueError(
                "startup_timeout_seconds "
                "must be > 0."
            )

        if frame_timeout_seconds <= 0:
            raise ValueError(
                "frame_timeout_seconds "
                "must be > 0."
            )

        self.startup_timeout_seconds = (
            float(
                startup_timeout_seconds
            )
        )

        self.frame_timeout_seconds = (
            float(
                frame_timeout_seconds
            )
        )

        # ----------------------------------------------------
        # Service lifecycle
        # ----------------------------------------------------

        self._lifecycle_lock = (
            threading.RLock()
        )

        self._thread: (
            threading.Thread
            | None
        ) = None

        self._loop: (
            asyncio.AbstractEventLoop
            | None
        ) = None

        self._ready_event = (
            threading.Event()
        )

        self._closing = False

        self._startup_error: (
            BaseException
            | None
        ) = None

        # ----------------------------------------------------
        # Portal / PipeWire state
        #
        # These are owned by the capture-service thread.
        # ----------------------------------------------------

        self._bus: (
            MessageBus
            | None
        ) = None

        self._session_handle: (
            str
            | None
        ) = None

        self._pipewire_fd: (
            int
            | None
        ) = None

        self._pipewire_node_id: (
            int
            | None
        ) = None

        self._portal_position: (
            tuple[int, int]
            | None
        ) = None

        self._portal_size: (
            tuple[int, int]
            | None
        ) = None

        # ----------------------------------------------------
        # GStreamer state
        # ----------------------------------------------------

        self._pipeline = None
        self._appsink = None

        # ----------------------------------------------------
        # Latest-frame state
        #
        # appsink's callback executes on GStreamer's streaming
        # thread. capture() may execute on a QRunnable worker.
        # A Condition protects both the frame and sequence.
        # ----------------------------------------------------

        self._frame_condition = (
            threading.Condition()
        )

        self._latest_frame: (
            np.ndarray
            | None
        ) = None

        self._frame_sequence = 0

        self._stream_error: (
            BaseException
            | None
        ) = None

    # ========================================================
    # PUBLIC: START
    # ========================================================

    def start(
        self,
    ) -> None:
        """
        Start Portal/PipeWire setup in the background.

        This method returns immediately.

        GNOME's screen-share dialog will appear asynchronously.
        capture() waits for setup to finish when necessary.
        """

        with self._lifecycle_lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return

            self._reset_for_start()

            self._thread = (
                threading.Thread(
                    target=(
                        self._service_thread_main
                    ),
                    name=(
                        "SubVision-WaylandCapture"
                    ),
                    daemon=True,
                )
            )

            self._thread.start()

    # ========================================================
    # PUBLIC: WAIT UNTIL PORTAL IS READY
    # ========================================================

    def wait_until_ready(
        self,
        timeout: float | None = None,
    ) -> None:
        """
        Wait until Portal + PipeWire + GStreamer are initialized.

        Raises:
            ScreenCapturePermissionError
            ScreenCaptureTimeoutError
            ScreenCaptureError
        """

        if timeout is None:
            timeout = (
                self.startup_timeout_seconds
            )

        # Preserve compatibility if a caller invokes capture()
        # before explicitly starting the service.
        with self._lifecycle_lock:
            thread_alive = (
                self._thread is not None
                and self._thread.is_alive()
            )

        if not thread_alive:
            self.start()

        completed = (
            self._ready_event.wait(
                timeout
            )
        )

        if not completed:
            raise ScreenCaptureTimeoutError(
                "Timed out while waiting for "
                "Wayland ScreenCast permission."
            )

        startup_error = (
            self._startup_error
        )

        if startup_error is not None:
            if isinstance(
                startup_error,
                ScreenCaptureError,
            ):
                raise startup_error

            raise ScreenCaptureError(
                "Could not initialize the "
                "Wayland screen-capture service."
            ) from startup_error

        if (
            self._pipeline is None
            or self._pipewire_fd is None
            or self._portal_size is None
        ):
            raise ScreenCaptureError(
                "Wayland capture setup finished "
                "without a valid PipeWire stream."
            )

    # ========================================================
    # PUBLIC: CAPTURE REGION
    # ========================================================

    def capture(
        self,
        region: ScreenRegion,
    ) -> np.ndarray:
        """
        Return a fresh BGR uint8 ndarray for `region`.

        `region` is expected to use global logical coordinates
        from Qt / AppState.

        The returned image is local to the selected region:

            shape = (crop_height, crop_width, 3)
            dtype = uint8
            color = BGR
        """

        self.wait_until_ready()

        full_frame = (
            self._get_latest_frame(
                timeout=(
                    self.frame_timeout_seconds
                )
            )
        )

        cropped = (
            self._crop_logical_region(
                frame=full_frame,
                region=region,
            )
        )

        if cropped.size == 0:
            raise ScreenCaptureError(
                "Captured region is empty."
            )

        if (
            cropped.ndim != 3
            or cropped.shape[2] != 3
        ):
            raise ScreenCaptureError(
                "Captured image is not "
                "a 3-channel BGR image."
            )

        if (
            cropped.shape[0] < 1
            or cropped.shape[1] < 1
        ):
            raise ScreenCaptureError(
                "Captured region has "
                "invalid dimensions."
            )

        if cropped.dtype != np.uint8:
            cropped = cropped.astype(
                np.uint8,
                copy=False,
            )

        return np.ascontiguousarray(
            cropped
        )

    # ========================================================
    # PUBLIC: CLOSE
    # ========================================================

    def close(
        self,
    ) -> None:
        """
        Stop GStreamer and close:

            PipeWire FD
            Portal ScreenCast session
            D-Bus connection

        Safe to call more than once.
        """

        with self._lifecycle_lock:
            self._closing = True

            loop = self._loop
            thread = self._thread

        if (
            loop is not None
            and loop.is_running()
        ):
            try:
                future = (
                    asyncio.run_coroutine_threadsafe(
                        self._async_cleanup(),
                        loop,
                    )
                )

                future.result(
                    timeout=10.0
                )

            except Exception:
                # Cleanup is repeated in the service thread's
                # finally block, so do not make application Stop
                # fail solely because this synchronous wait did.
                pass

            try:
                loop.call_soon_threadsafe(
                    loop.stop
                )

            except RuntimeError:
                pass

        if (
            thread is not None
            and thread.is_alive()
            and thread
            is not threading.current_thread()
        ):
            thread.join(
                timeout=10.0
            )

        with self._lifecycle_lock:
            self._thread = None
            self._loop = None

        with self._frame_condition:
            self._latest_frame = None
            self._frame_sequence = 0
            self._stream_error = None

    # ========================================================
    # PUBLIC: STATUS
    # ========================================================

    @property
    def is_ready(
        self,
    ) -> bool:
        return (
            self._ready_event.is_set()
            and self._startup_error is None
            and self._pipeline is not None
        )

    @property
    def portal_position(
        self,
    ) -> tuple[
        int,
        int,
    ] | None:
        return self._portal_position

    @property
    def portal_size(
        self,
    ) -> tuple[
        int,
        int,
    ] | None:
        return self._portal_size

    @property
    def pipewire_node_id(
        self,
    ) -> int | None:
        return self._pipewire_node_id

    # ========================================================
    # SERVICE THREAD
    # ========================================================

    def _service_thread_main(
        self,
    ) -> None:
        loop = asyncio.new_event_loop()

        asyncio.set_event_loop(
            loop
        )

        with self._lifecycle_lock:
            self._loop = loop

        try:
            loop.run_until_complete(
                self._async_open()
            )

            self._ready_event.set()

            if not self._closing:
                loop.run_forever()

        except BaseException as exc:
            if (
                not self._closing
                or self._startup_error is None
            ):
                self._startup_error = exc

            self._ready_event.set()

            with self._frame_condition:
                self._stream_error = exc

                self._frame_condition.notify_all()

        finally:
            try:
                loop.run_until_complete(
                    self._async_cleanup()
                )

            except Exception:
                pass

            try:
                loop.close()

            except Exception:
                pass

            self._ready_event.set()

    # ========================================================
    # ASYNC: OPEN PORTAL SESSION
    # ========================================================

    async def _async_open(
        self,
    ) -> None:
        # ----------------------------------------------------
        # 1. Connect to user session D-Bus.
        #
        # Unix-FD negotiation is mandatory because
        # OpenPipeWireRemote returns D-Bus type "h".
        # ----------------------------------------------------

        self._bus = await MessageBus(
            bus_type=BusType.SESSION,
            negotiate_unix_fd=True,
        ).connect()

        tracker = _RequestTracker(
            self._bus
        )

        # ----------------------------------------------------
        # 2. Create ScreenCast interface proxy.
        # ----------------------------------------------------

        portal_object = (
            self._bus.get_proxy_object(
                PORTAL_BUS,
                PORTAL_PATH,
                SCREENCAST_XML,
            )
        )

        screencast = (
            portal_object.get_interface(
                SCREENCAST_IFACE
            )
        )

        # ----------------------------------------------------
        # 3. Create session.
        # ----------------------------------------------------

        create_request = (
            await screencast.call_create_session(
                {
                    "handle_token": Variant(
                        "s",
                        _make_token(
                            "subvision_create_"
                        ),
                    ),
                    "session_handle_token": Variant(
                        "s",
                        _make_token(
                            "subvision_session_"
                        ),
                    ),
                }
            )
        )

        response, results = (
            await tracker.wait(
                create_request
            )
        )

        if response == 1:
            raise ScreenCapturePermissionError(
                "ScreenCast session creation "
                "was cancelled."
            )

        if response != 0:
            raise ScreenCaptureError(
                "CreateSession failed. "
                f"response={response}"
            )

        self._session_handle = (
            _value_of(
                results[
                    "session_handle"
                ]
            )
        )

        # ----------------------------------------------------
        # 4. Request one monitor.
        #
        # types=1:
        #     MONITOR
        #
        # multiple=False:
        #     one monitor only
        #
        # cursor_mode=1:
        #     cursor hidden from captured video
        # ----------------------------------------------------

        select_request = (
            await screencast.call_select_sources(
                self._session_handle,
                {
                    "handle_token": Variant(
                        "s",
                        _make_token(
                            "subvision_select_"
                        ),
                    ),
                    "types": Variant(
                        "u",
                        1,
                    ),
                    "multiple": Variant(
                        "b",
                        False,
                    ),
                    "cursor_mode": Variant(
                        "u",
                        1,
                    ),
                },
            )
        )

        response, _ = (
            await tracker.wait(
                select_request
            )
        )

        if response == 1:
            raise ScreenCapturePermissionError(
                "Monitor selection "
                "was cancelled."
            )

        if response != 0:
            raise ScreenCaptureError(
                "SelectSources failed. "
                f"response={response}"
            )

        # ----------------------------------------------------
        # 5. Start session.
        #
        # GNOME displays its native "Share Screen" dialog here.
        # ----------------------------------------------------

        start_request = (
            await screencast.call_start(
                self._session_handle,
                "",
                {
                    "handle_token": Variant(
                        "s",
                        _make_token(
                            "subvision_start_"
                        ),
                    ),
                },
            )
        )

        response, results = (
            await tracker.wait(
                start_request
            )
        )

        if response == 1:
            raise ScreenCapturePermissionError(
                "User cancelled "
                "screen sharing."
            )

        if response != 0:
            raise ScreenCaptureError(
                "ScreenCast Start failed. "
                f"response={response}"
            )

        # ----------------------------------------------------
        # 6. Read stream metadata.
        # ----------------------------------------------------

        streams_variant = results.get(
            "streams"
        )

        if streams_variant is None:
            raise ScreenCaptureError(
                "Portal started successfully "
                "but returned no streams."
            )

        streams = _value_of(
            streams_variant
        )

        if not streams:
            raise ScreenCaptureError(
                "Portal returned an "
                "empty stream list."
            )

        first_stream = streams[0]

        self._pipewire_node_id = int(
            first_stream[0]
        )

        properties = first_stream[1]

        position_raw = _value_of(
            properties.get(
                "position"
            )
        )

        size_raw = _value_of(
            properties.get(
                "size"
            )
        )

        if position_raw is None:
            self._portal_position = (
                0,
                0,
            )

        else:
            self._portal_position = (
                int(
                    position_raw[0]
                ),
                int(
                    position_raw[1]
                ),
            )

        if size_raw is None:
            raise ScreenCaptureError(
                "Portal stream did not "
                "return logical monitor size."
            )

        self._portal_size = (
            int(
                size_raw[0]
            ),
            int(
                size_raw[1]
            ),
        )

        if (
            self._portal_size[0] <= 0
            or self._portal_size[1] <= 0
        ):
            raise ScreenCaptureError(
                "Portal returned invalid "
                "logical monitor dimensions."
            )

        # ----------------------------------------------------
        # 7. Open restricted PipeWire remote.
        # ----------------------------------------------------

        self._pipewire_fd = (
            await screencast
            .call_open_pipe_wire_remote(
                self._session_handle,
                {},
            )
        )

        # Verify descriptor immediately.
        os.fstat(
            self._pipewire_fd
        )

        # ----------------------------------------------------
        # 8. Start persistent GStreamer stream.
        # ----------------------------------------------------

        self._start_gstreamer_pipeline()

    # ========================================================
    # GSTREAMER: START PERSISTENT PIPELINE
    # ========================================================

    def _start_gstreamer_pipeline(
        self,
    ) -> None:
        if self._pipewire_fd is None:
            raise ScreenCaptureError(
                "Cannot start GStreamer: "
                "PipeWire FD is missing."
            )

        if self._pipewire_node_id is None:
            raise ScreenCaptureError(
                "Cannot start GStreamer: "
                "PipeWire node ID is missing."
            )

        pipeline_description = (
            f"pipewiresrc "
            f"fd={self._pipewire_fd} "
            f"path={self._pipewire_node_id} "
            f"do-timestamp=true "
            f"! videoconvert "
            f"! video/x-raw,format=BGR "
            f"! appsink "
            f"name=subvision_framesink "
            f"emit-signals=true "
            f"sync=false "
            f"max-buffers=1 "
            f"drop=true"
        )

        try:
            pipeline = Gst.parse_launch(
                pipeline_description
            )

        except Exception as exc:
            raise ScreenCaptureError(
                "Could not build the "
                "GStreamer PipeWire pipeline."
            ) from exc

        appsink = pipeline.get_by_name(
            "subvision_framesink"
        )

        if appsink is None:
            pipeline.set_state(
                Gst.State.NULL
            )

            raise ScreenCaptureError(
                "GStreamer appsink "
                "was not created."
            )

        appsink.connect(
            "new-sample",
            self._on_new_sample,
        )

        state_result = pipeline.set_state(
            Gst.State.PLAYING
        )

        if (
            state_result
            == Gst.StateChangeReturn.FAILURE
        ):
            pipeline.set_state(
                Gst.State.NULL
            )

            raise ScreenCaptureError(
                "GStreamer pipeline failed "
                "to enter PLAYING state."
            )

        self._pipeline = pipeline
        self._appsink = appsink

    # ========================================================
    # GSTREAMER: NEW FRAME CALLBACK
    # ========================================================

    def _on_new_sample(
        self,
        appsink,
    ):
        try:
            sample = appsink.emit(
                "pull-sample"
            )

            if sample is None:
                return Gst.FlowReturn.EOS

            frame = (
                self._sample_to_bgr(
                    sample
                )
            )

            with self._frame_condition:
                self._latest_frame = frame
                self._frame_sequence += 1
                self._stream_error = None

                self._frame_condition.notify_all()

            return Gst.FlowReturn.OK

        except BaseException as exc:
            with self._frame_condition:
                self._stream_error = exc

                self._frame_condition.notify_all()

            return Gst.FlowReturn.ERROR

    # ========================================================
    # GSTREAMER SAMPLE -> BGR NUMPY
    # ========================================================

    @staticmethod
    def _sample_to_bgr(
        sample,
    ) -> np.ndarray:
        caps = sample.get_caps()

        if caps is None:
            raise ScreenCaptureError(
                "PipeWire sample has "
                "no video caps."
            )

        structure = caps.get_structure(
            0
        )

        width = int(
            structure.get_value(
                "width"
            )
        )

        height = int(
            structure.get_value(
                "height"
            )
        )

        pixel_format = (
            structure.get_value(
                "format"
            )
        )

        if (
            width <= 0
            or height <= 0
        ):
            raise ScreenCaptureError(
                "PipeWire returned invalid "
                "frame dimensions."
            )

        if pixel_format != "BGR":
            raise ScreenCaptureError(
                "Unexpected GStreamer format: "
                f"{pixel_format!r}. "
                "Expected 'BGR'."
            )

        buffer = sample.get_buffer()

        if buffer is None:
            raise ScreenCaptureError(
                "PipeWire sample contains "
                "no Gst.Buffer."
            )

        success, map_info = buffer.map(
            Gst.MapFlags.READ
        )

        if not success:
            raise ScreenCaptureError(
                "Could not map "
                "GStreamer frame buffer."
            )

        try:
            raw = np.frombuffer(
                map_info.data,
                dtype=np.uint8,
            )

            row_bytes = (
                width
                * 3
            )

            expected_size = (
                row_bytes
                * height
            )

            # Fast path: no row padding.
            if raw.size == expected_size:
                frame = (
                    raw.reshape(
                        (
                            height,
                            width,
                            3,
                        )
                    )
                    .copy()
                )

                return np.ascontiguousarray(
                    frame
                )

            # Robust path: packed BGR with row-stride padding.
            if (
                raw.size % height
                != 0
            ):
                raise ScreenCaptureError(
                    "Unexpected GStreamer "
                    "buffer size. "
                    f"got={raw.size}, "
                    f"minimum_expected="
                    f"{expected_size}"
                )

            stride = (
                raw.size
                // height
            )

            if stride < row_bytes:
                raise ScreenCaptureError(
                    "GStreamer row stride "
                    "is smaller than the "
                    "BGR pixel row."
                )

            rows = raw.reshape(
                (
                    height,
                    stride,
                )
            )

            pixel_bytes = (
                rows[
                    :,
                    :row_bytes,
                ]
                .copy()
            )

            frame = (
                pixel_bytes.reshape(
                    (
                        height,
                        width,
                        3,
                    )
                )
            )

            return np.ascontiguousarray(
                frame
            )

        finally:
            buffer.unmap(
                map_info
            )

    # ========================================================
    # CAPTURE: WAIT FOR A FRAME NEWER THAN THIS CALL
    # ========================================================

    def _get_latest_frame(
        self,
        *,
        timeout: float,
    ) -> np.ndarray:
        """
        Return the latest available PipeWire frame.

        SessionRunner đã:
            1. ẩn SubVision output;
            2. chờ capture_settle_ms;

        trước khi gọi capture().

        Vì vậy frame mới nhất tại thời điểm này đã là candidate
        phù hợp để capture.

        Không yêu cầu phải xuất hiện thêm một frame sau thời điểm
        capture() bắt đầu, vì Wayland/PipeWire có thể không phát
        frame mới khi nội dung màn hình đang đứng yên.
        """

        deadline = (
            time.monotonic()
            + timeout
        )

        with self._frame_condition:
            while self._latest_frame is None:
                if self._stream_error is not None:
                    raise ScreenCaptureError(
                        "Wayland/PipeWire stream failed."
                    ) from self._stream_error

                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    gst_error = (
                        self._read_gstreamer_error()
                    )

                    if gst_error is not None:
                        raise ScreenCaptureError(
                            "GStreamer/PipeWire "
                            f"stream error: {gst_error}"
                        )

                    raise ScreenCaptureTimeoutError(
                        "Timed out while waiting "
                        "for the first Wayland frame."
                    )

                self._frame_condition.wait(
                    remaining
                )

            return self._latest_frame.copy()

    def _wait_for_fresh_frame(
        self,
        *,
        timeout: float,
    ) -> np.ndarray:
        deadline = (
            time.monotonic()
            + timeout
        )

        with self._frame_condition:
            baseline_sequence = (
                self._frame_sequence
            )

            while (
                self._frame_sequence
                <= baseline_sequence
            ):
                if (
                    self._stream_error
                    is not None
                ):
                    raise ScreenCaptureError(
                        "Wayland/PipeWire "
                        "stream failed."
                    ) from self._stream_error

                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    gst_error = (
                        self._read_gstreamer_error()
                    )

                    if gst_error is not None:
                        raise ScreenCaptureError(
                            "GStreamer/PipeWire "
                            f"stream error: {gst_error}"
                        )

                    raise ScreenCaptureTimeoutError(
                        "Timed out while waiting "
                        "for a fresh Wayland frame."
                    )

                self._frame_condition.wait(
                    remaining
                )

            frame = self._latest_frame

            if frame is None:
                raise ScreenCaptureError(
                    "Frame sequence advanced "
                    "without a valid image."
                )

            return frame.copy()

    # ========================================================
    # COORDINATE MAPPING + CROP
    # ========================================================

    def _crop_logical_region(
        self,
        *,
        frame: np.ndarray,
        region: ScreenRegion,
    ) -> np.ndarray:
        portal_position = (
            self._portal_position
        )

        portal_size = (
            self._portal_size
        )

        if portal_position is None:
            raise ScreenCaptureError(
                "Portal monitor position "
                "is unavailable."
            )

        if portal_size is None:
            raise ScreenCaptureError(
                "Portal monitor size "
                "is unavailable."
            )

        x1, y1, x2, y2 = (
            _region_coordinates(
                region
            )
        )

        if x2 <= x1:
            raise ScreenCaptureError(
                "Invalid region: "
                "x2 must be greater than x1."
            )

        if y2 <= y1:
            raise ScreenCaptureError(
                "Invalid region: "
                "y2 must be greater than y1."
            )

        portal_x, portal_y = (
            portal_position
        )

        portal_width, portal_height = (
            portal_size
        )

        monitor_x2 = (
            portal_x
            + portal_width
        )

        monitor_y2 = (
            portal_y
            + portal_height
        )

        # Strict validation is safer than silently clipping a
        # region that belongs to another monitor.
        if (
            x1 < portal_x
            or y1 < portal_y
            or x2 > monitor_x2
            or y2 > monitor_y2
        ):
            raise ScreenCaptureError(
                "Selected region is outside "
                "the monitor shared through "
                "the Wayland ScreenCast Portal. "
                f"region={(x1, y1, x2, y2)}, "
                f"shared_monitor="
                f"{(portal_x, portal_y, monitor_x2, monitor_y2)}"
            )

        frame_height, frame_width = (
            frame.shape[:2]
        )

        # IMPORTANT:
        # Do not use QScreen.devicePixelRatio().
        #
        # Fractional Wayland scaling is inferred from the
        # actual stream dimensions observed at runtime.
        scale_x = (
            frame_width
            / portal_width
        )

        scale_y = (
            frame_height
            / portal_height
        )

        # Global logical -> monitor-local logical.
        local_x1 = (
            x1
            - portal_x
        )

        local_y1 = (
            y1
            - portal_y
        )

        local_x2 = (
            x2
            - portal_x
        )

        local_y2 = (
            y2
            - portal_y
        )

        # Monitor-local logical -> PipeWire frame pixels.
        #
        # round() intentionally matches the mapping verified
        # by the standalone Wayland prototype.
        physical_x1 = round(
            local_x1
            * scale_x
        )

        physical_y1 = round(
            local_y1
            * scale_y
        )

        physical_x2 = round(
            local_x2
            * scale_x
        )

        physical_y2 = round(
            local_y2
            * scale_y
        )

        # Numerical safety only. A region outside the shared
        # monitor has already been rejected above.
        physical_x1 = max(
            0,
            min(
                frame_width,
                physical_x1,
            ),
        )

        physical_y1 = max(
            0,
            min(
                frame_height,
                physical_y1,
            ),
        )

        physical_x2 = max(
            0,
            min(
                frame_width,
                physical_x2,
            ),
        )

        physical_y2 = max(
            0,
            min(
                frame_height,
                physical_y2,
            ),
        )

        if (
            physical_x2
            <= physical_x1
            or physical_y2
            <= physical_y1
        ):
            raise ScreenCaptureError(
                "Logical region mapped to "
                "an empty PipeWire crop."
            )

        cropped = frame[
            physical_y1:physical_y2,
            physical_x1:physical_x2,
        ]

        if cropped.size == 0:
            raise ScreenCaptureError(
                "Captured region is empty."
            )

        # ========================================================
        # NORMALIZE BACK TO LOGICAL COORDINATE SPACE
        #
        # PipeWire may expose the monitor at physical resolution
        # while Qt/AppState use logical coordinates. OCR must see
        # an image whose size matches ScreenRegion exactly; then its
        # bboxes can be mapped back to the screen with a simple
        # region-origin offset.
        # ========================================================

        logical_width = x2 - x1
        logical_height = y2 - y1

        if (
            cropped.shape[1] != logical_width
            or cropped.shape[0] != logical_height
        ):
            # Pillow is deliberately used here instead of OpenCV.
            # The GUI-enabled opencv-python package mutates Qt's
            # platform-plugin environment on Linux, which can make
            # PyQt6 load cv2/qt/plugins instead of its own xcb plugin.
            rgb = np.ascontiguousarray(
                cropped[:, :, ::-1]
            )

            resized_rgb = np.asarray(
                Image.fromarray(rgb).resize(
                    (
                        logical_width,
                        logical_height,
                    ),
                    Image.Resampling.LANCZOS,
                ),
                dtype=np.uint8,
            )

            cropped = np.ascontiguousarray(
                resized_rgb[:, :, ::-1]
            )

        return np.ascontiguousarray(cropped)

    # ========================================================
    # GSTREAMER ERROR INSPECTION
    # ========================================================

    def _read_gstreamer_error(
        self,
    ) -> str | None:
        pipeline = self._pipeline

        if pipeline is None:
            return None

        bus = pipeline.get_bus()

        if bus is None:
            return None

        message = bus.pop_filtered(
            Gst.MessageType.ERROR
        )

        if message is None:
            return None

        error, debug = (
            message.parse_error()
        )

        if debug:
            return (
                f"{error.message}; "
                f"debug={debug}"
            )

        return error.message

    # ========================================================
    # CLEANUP
    # ========================================================

    async def _async_cleanup(
        self,
    ) -> None:
        # ----------------------------------------------------
        # Stop GStreamer before closing its PipeWire FD.
        # ----------------------------------------------------

        pipeline = self._pipeline

        self._pipeline = None
        self._appsink = None

        if pipeline is not None:
            try:
                pipeline.set_state(
                    Gst.State.NULL
                )

            except Exception:
                pass

        # Wake capture() if it is waiting for another frame.
        with self._frame_condition:
            if self._closing:
                self._stream_error = (
                    ScreenCaptureError(
                        "Screen capture service "
                        "is closing."
                    )
                )

            self._frame_condition.notify_all()

        # ----------------------------------------------------
        # Close PipeWire FD.
        # ----------------------------------------------------

        pipewire_fd = (
            self._pipewire_fd
        )

        self._pipewire_fd = None

        if pipewire_fd is not None:
            try:
                os.close(
                    pipewire_fd
                )

            except OSError:
                pass

        # ----------------------------------------------------
        # Close Portal session.
        # ----------------------------------------------------

        bus = self._bus
        session_handle = (
            self._session_handle
        )

        self._session_handle = None

        if (
            bus is not None
            and session_handle is not None
        ):
            try:
                session_object = (
                    bus.get_proxy_object(
                        PORTAL_BUS,
                        session_handle,
                        SESSION_XML,
                    )
                )

                session = (
                    session_object
                    .get_interface(
                        SESSION_IFACE
                    )
                )

                await session.call_close()

            except Exception:
                pass

        # ----------------------------------------------------
        # Disconnect D-Bus.
        # ----------------------------------------------------

        self._bus = None

        if bus is not None:
            try:
                bus.disconnect()

            except Exception:
                pass

    # ========================================================
    # RESET FOR RESTART
    # ========================================================

    def _reset_for_start(
        self,
    ) -> None:
        self._closing = False

        self._startup_error = None

        self._ready_event.clear()

        self._bus = None
        self._session_handle = None

        self._pipewire_fd = None
        self._pipewire_node_id = None

        self._portal_position = None
        self._portal_size = None

        self._pipeline = None
        self._appsink = None

        with self._frame_condition:
            self._latest_frame = None
            self._frame_sequence = 0
            self._stream_error = None