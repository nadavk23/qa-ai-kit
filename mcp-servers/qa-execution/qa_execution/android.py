"""Android testing via direct adb — no Appium dependency.

Drives an Android emulator (or attached device) through the standard `adb`
binary that ships with the Android SDK platform-tools. UI interactions are
implemented via `uiautomator dump` (for inspection) + `adb shell input`
(for tap/type/keys). Logcat tailing is exposed for real-time debug.

Designed to work on networks where the npm public registry is blocked —
nothing here pulls anything from npm or runs an Appium server. The Android
SDK is the only prerequisite.

A single `AndroidDevice` represents one allocated emulator/device session;
it is tracked by token in the shared DeviceRegistry alongside iOS sessions.
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


_BOUNDS_RE = re.compile(r"\[(\-?\d+),(\-?\d+)\]\[(\-?\d+),(\-?\d+)\]")

_ANDROID_STRATEGIES = ("text", "accessibility_id", "resource_id", "xpath")

_KEYCODES = {
    "back": "KEYCODE_BACK",
    "home": "KEYCODE_HOME",
    "menu": "KEYCODE_MENU",
    "enter": "KEYCODE_ENTER",
    "tab": "KEYCODE_TAB",
}


# ---------- tool discovery ----------

def find_adb() -> str:
    """Locate the adb binary. Raises FileNotFoundError if unavailable."""
    candidate = shutil.which("adb")
    if candidate:
        return candidate
    paths_to_try: list[Path] = []
    if "ANDROID_HOME" in os.environ:
        paths_to_try.append(Path(os.environ["ANDROID_HOME"]) / "platform-tools/adb")
    if "ANDROID_SDK_ROOT" in os.environ:
        paths_to_try.append(Path(os.environ["ANDROID_SDK_ROOT"]) / "platform-tools/adb")
    paths_to_try.extend(
        [
            Path.home() / "Library/Android/sdk/platform-tools/adb",
            Path("/usr/local/share/android-sdk/platform-tools/adb"),
            Path("/opt/homebrew/share/android-sdk/platform-tools/adb"),
        ]
    )
    for p in paths_to_try:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    raise FileNotFoundError(
        "adb not found. Install Android SDK platform-tools, or set ANDROID_HOME."
    )


def find_emulator() -> str:
    """Locate the emulator binary. Raises FileNotFoundError if unavailable."""
    candidate = shutil.which("emulator")
    if candidate:
        return candidate
    paths_to_try: list[Path] = []
    if "ANDROID_HOME" in os.environ:
        paths_to_try.append(Path(os.environ["ANDROID_HOME"]) / "emulator/emulator")
    paths_to_try.extend(
        [
            Path.home() / "Library/Android/sdk/emulator/emulator",
            Path("/usr/local/share/android-sdk/emulator/emulator"),
        ]
    )
    for p in paths_to_try:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    raise FileNotFoundError(
        "emulator not found. Install Android SDK emulator, or set ANDROID_HOME."
    )


# ---------- AndroidDevice ----------

class AndroidDevice:
    def __init__(self, device_id: str, adb_path: str, package: str | None) -> None:
        self.platform = "android"
        self.device_id = device_id
        self.adb_path = adb_path
        self.package = package
        self.emulator_proc: subprocess.Popen | None = None  # set if we started the AVD

    def adb(self, *args: str, timeout: float = 30.0, check: bool = False) -> subprocess.CompletedProcess:
        """Run `adb -s <device_id> <args>` and return the CompletedProcess.

        Stdout/stderr captured as text. Does not raise on non-zero exit unless
        check=True. Use the returncode and stderr to decide.
        """
        cmd = [self.adb_path, "-s", self.device_id, *args]
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=check
        )

    def adb_exec_out(self, *args: str, timeout: float = 30.0) -> bytes:
        """Run `adb -s <id> exec-out <args>` for binary stdout (screenshots, etc.)."""
        cmd = [self.adb_path, "-s", self.device_id, "exec-out", *args]
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(
                f"adb exec-out failed (exit {proc.returncode}): {proc.stderr.decode(errors='replace')}"
            )
        return proc.stdout


# ---------- emulator lifecycle ----------

def list_running_devices(adb_path: str) -> list[str]:
    """Return adb device serials currently listed as `device` (not offline/unauthorized)."""
    proc = subprocess.run(
        [adb_path, "devices"], capture_output=True, text=True, timeout=10
    )
    serials = []
    for line in proc.stdout.splitlines()[1:]:  # skip "List of devices attached" header
        line = line.strip()
        if not line or "\t" not in line:
            continue
        serial, state = line.split("\t", 1)
        if state.strip() == "device":
            serials.append(serial)
    return serials


def list_avds(emulator_path: str) -> list[str]:
    proc = subprocess.run(
        [emulator_path, "-list-avds"], capture_output=True, text=True, timeout=10
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def start_emulator(emulator_path: str, avd_name: str) -> subprocess.Popen:
    """Spawn the emulator detached. Returns the Popen handle (don't wait on it)."""
    # -no-snapshot-save: don't overwrite the AVD snapshot on quit (safer for tests)
    # -no-boot-anim: faster boot
    cmd = [emulator_path, "-avd", avd_name, "-no-snapshot-save", "-no-boot-anim"]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_emulator(adb_path: str, existing_serials: set[str], boot_timeout: float = 120.0) -> str:
    """Wait for a new emulator serial to appear and finish booting. Returns serial."""
    end = time.monotonic() + boot_timeout
    new_serial: str | None = None
    while time.monotonic() < end:
        serials = set(list_running_devices(adb_path))
        new = serials - existing_serials
        new = {s for s in new if s.startswith("emulator-")}
        if new:
            new_serial = next(iter(new))
            break
        time.sleep(1.0)
    if not new_serial:
        raise TimeoutError("Emulator did not appear in adb devices within timeout.")
    # Wait for boot_completed
    while time.monotonic() < end:
        proc = subprocess.run(
            [adb_path, "-s", new_serial, "shell", "getprop", "sys.boot_completed"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.stdout.strip() == "1":
            return new_serial
        time.sleep(1.0)
    raise TimeoutError(f"Emulator {new_serial} did not finish booting within timeout.")


# ---------- UI inspection ----------

def _dump_ui_xml(device: AndroidDevice) -> str:
    """Capture the current UI hierarchy as XML. Returns the XML string.

    Uses `uiautomator dump` to write /sdcard/window_dump.xml, then cats it back.
    Two-step because `dump /dev/tty` is unreliable across Android versions.
    """
    dump = device.adb(
        "shell", "uiautomator", "dump", "/sdcard/window_dump.xml", timeout=15
    )
    if dump.returncode != 0:
        raise RuntimeError(f"uiautomator dump failed: {dump.stderr.strip()}")
    cat = device.adb("shell", "cat", "/sdcard/window_dump.xml", timeout=10)
    if cat.returncode != 0 or not cat.stdout.strip():
        raise RuntimeError(f"failed to read UI dump: {cat.stderr.strip()}")
    return cat.stdout


def _parse_bounds(bounds: str) -> tuple[int, int, int, int] | None:
    m = _BOUNDS_RE.match(bounds.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def _matches(el: ET.Element, strategy: str, value: str) -> bool:
    if strategy == "text":
        return el.attrib.get("text", "") == value
    if strategy == "accessibility_id":
        return el.attrib.get("content-desc", "") == value
    if strategy == "resource_id":
        return el.attrib.get("resource-id", "") == value
    # xpath handled separately by caller
    return False


def _find_element(device: AndroidDevice, strategy: str, value: str) -> ET.Element | None:
    if strategy not in _ANDROID_STRATEGIES:
        raise ValueError(
            f"Unknown Android locator strategy {strategy!r}. "
            f"Expected one of: {_ANDROID_STRATEGIES}"
        )
    xml = _dump_ui_xml(device)
    root = ET.fromstring(xml)
    if strategy == "xpath":
        # ElementTree's XPath is limited; supports basic predicates
        matches = root.findall(value)
        return matches[0] if matches else None
    for el in root.iter():
        if _matches(el, strategy, value):
            return el
    return None


def _wait_for_element(
    device: AndroidDevice, strategy: str, value: str, timeout_ms: int
) -> ET.Element:
    end = time.monotonic() + max(timeout_ms / 1000, 0.0)
    last_err: Exception | None = None
    while True:
        try:
            el = _find_element(device, strategy, value)
            if el is not None:
                return el
        except Exception as e:
            last_err = e
        if time.monotonic() >= end:
            break
        time.sleep(0.3)
    detail = f" ({type(last_err).__name__}: {last_err})" if last_err else ""
    raise TimeoutError(
        f"Element {strategy}={value!r} not found within {timeout_ms}ms{detail}"
    )


# ---------- sync action helpers (run via asyncio.to_thread) ----------

def android_screenshot_sync(device: AndroidDevice, path: str) -> str:
    png = device.adb_exec_out("screencap", "-p", timeout=15)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(png)
    return path


def android_inspect_sync(device: AndroidDevice, limit: int) -> str:
    xml = _dump_ui_xml(device)
    root = ET.fromstring(xml)
    elements: list[dict[str, str]] = []
    for el in root.iter():
        attrs = el.attrib
        text = attrs.get("text", "")
        desc = attrs.get("content-desc", "")
        rid = attrs.get("resource-id", "")
        klass = attrs.get("class", "")
        clickable = attrs.get("clickable", "")
        if not (text or desc or rid):
            continue
        elements.append(
            {
                "class": klass.split(".")[-1] if klass else "",
                "text": text,
                "desc": desc,
                "resource_id": rid,
                "clickable": clickable,
                "bounds": attrs.get("bounds", ""),
            }
        )
        if len(elements) >= limit:
            break

    lines = [f"Elements ({len(elements)}):"]
    for i, el in enumerate(elements):
        parts = [f"[{i}] {el['class']}"]
        if el["text"]:
            parts.append(f"text={el['text']!r}")
        if el["desc"] and el["desc"] != el["text"]:
            parts.append(f"desc={el['desc']!r}")
        if el["resource_id"]:
            parts.append(f"id={el['resource_id']}")
        if el["clickable"] == "true":
            parts.append("(clickable)")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


def android_tap_sync(
    device: AndroidDevice, strategy: str, value: str, timeout_ms: int
) -> str:
    el = _wait_for_element(device, strategy, value, timeout_ms)
    bounds = _parse_bounds(el.attrib.get("bounds", ""))
    if not bounds:
        raise RuntimeError(f"Element found but has no bounds attribute: {el.attrib}")
    x1, y1, x2, y2 = bounds
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    proc = device.adb("shell", "input", "tap", str(cx), str(cy), timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(f"adb input tap failed: {proc.stderr.strip()}")
    return f"tapped {strategy}={value!r} at ({cx},{cy})"


def _escape_text_for_input(text: str) -> str:
    """Escape a string for `adb shell input text`. Spaces become %s; quotes escaped."""
    # adb shell input text doesn't handle spaces directly; %s is the documented escape
    return text.replace(" ", "%s").replace("'", r"\'").replace('"', r'\"')


def android_type_sync(
    device: AndroidDevice,
    strategy: str,
    value: str,
    text: str,
    clear: bool,
    timeout_ms: int,
) -> str:
    # Focus the field first by tapping it
    android_tap_sync(device, strategy, value, timeout_ms)
    if clear:
        # Select-all + delete: KEYCODE_MOVE_END then long-press select... simpler:
        # send a bunch of backspaces. Not ideal but reliable across versions.
        for _ in range(100):
            device.adb("shell", "input", "keyevent", "KEYCODE_DEL", timeout=5)
    escaped = _escape_text_for_input(text)
    proc = device.adb("shell", "input", "text", escaped, timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(f"adb input text failed: {proc.stderr.strip()}")
    return f"typed into {strategy}={value!r}"


def android_assert_element_sync(
    device: AndroidDevice, strategy: str, value: str, present: bool, timeout_ms: int
) -> tuple[bool, str]:
    try:
        _wait_for_element(device, strategy, value, timeout_ms)
        found = True
    except TimeoutError:
        found = False
    except Exception as e:
        return False, f"driver error: {type(e).__name__}: {e}"
    if found == present:
        desc = "present" if present else "absent"
        return True, f"element {strategy}={value!r} is {desc}"
    expected = "present" if present else "absent"
    actual = "present" if found else "absent"
    return False, f"expected element {strategy}={value!r} to be {expected}, was {actual}"


def android_assert_text_sync(
    device: AndroidDevice,
    text: str,
    strategy: str | None,
    value: str | None,
    timeout_ms: int,
) -> tuple[bool, str]:
    end = time.monotonic() + max(timeout_ms / 1000, 0.0)
    last_err: Exception | None = None
    while True:
        try:
            if strategy and value:
                el = _find_element(device, strategy, value)
                if el is not None:
                    el_text = (el.attrib.get("text", "") + " " + el.attrib.get("content-desc", "")).strip()
                    if text in el_text:
                        return True, f"text {text!r} found in {strategy}={value!r}"
            else:
                xml = _dump_ui_xml(device)
                if text in xml:
                    return True, f"text {text!r} found on screen"
        except Exception as e:
            last_err = e
        if time.monotonic() >= end:
            break
        time.sleep(0.3)
    detail = f" ({type(last_err).__name__}: {last_err})" if last_err else ""
    return False, f"text {text!r} not found within {timeout_ms}ms{detail}"


def android_wait_sync(
    device: AndroidDevice, strategy: str | None, value: str | None, timeout_ms: int
) -> tuple[bool, str]:
    if not strategy or not value:
        time.sleep(max(timeout_ms / 1000, 0.0))
        return True, f"slept {timeout_ms}ms"
    try:
        _wait_for_element(device, strategy, value, timeout_ms)
        return True, f"element {strategy}={value!r} appeared"
    except TimeoutError as e:
        return False, str(e)


def android_scroll_sync(device: AndroidDevice, direction: str) -> str:
    """Swipe-scroll based on screen size queried via `wm size`."""
    direction = direction.lower()
    if direction not in {"up", "down", "left", "right"}:
        raise ValueError(
            f"direction must be one of up/down/left/right, got {direction!r}"
        )
    proc = device.adb("shell", "wm", "size", timeout=5)
    m = re.search(r"(\d+)x(\d+)", proc.stdout)
    if not m:
        # fallback to a generic 1080x1920 swipe
        w, h = 1080, 1920
    else:
        w, h = int(m.group(1)), int(m.group(2))
    cx, cy = w // 2, h // 2
    # 40% of screen swipe
    dx, dy = int(w * 0.4), int(h * 0.4)
    if direction == "down":
        x1, y1, x2, y2 = cx, cy + dy // 2, cx, cy - dy // 2
    elif direction == "up":
        x1, y1, x2, y2 = cx, cy - dy // 2, cx, cy + dy // 2
    elif direction == "right":
        x1, y1, x2, y2 = cx + dx // 2, cy, cx - dx // 2, cy
    else:  # left
        x1, y1, x2, y2 = cx - dx // 2, cy, cx + dx // 2, cy
    proc = device.adb(
        "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "250", timeout=10
    )
    if proc.returncode != 0:
        raise RuntimeError(f"adb input swipe failed: {proc.stderr.strip()}")
    return f"scrolled {direction}"


def android_keyevent_sync(device: AndroidDevice, key: str) -> str:
    key_lc = key.lower()
    keycode = _KEYCODES.get(key_lc, key.upper() if key.upper().startswith("KEYCODE_") else None)
    if not keycode:
        raise ValueError(
            f"Unknown key {key!r}. Use one of {sorted(_KEYCODES)} "
            f"or a literal KEYCODE_* name."
        )
    proc = device.adb("shell", "input", "keyevent", keycode, timeout=5)
    if proc.returncode != 0:
        raise RuntimeError(f"adb keyevent failed: {proc.stderr.strip()}")
    return f"sent key {keycode}"


def android_logcat_sync(
    device: AndroidDevice, filter_expr: str | None, lines: int, clear: bool
) -> str:
    """Tail recent logcat output. `filter_expr` follows logcat tag:level syntax
    (e.g. 'MyApp:V *:S' for verbose-from-MyApp, silence-everything-else)."""
    if clear:
        device.adb("logcat", "-c", timeout=10)
        return "(logcat buffer cleared)"
    args = ["logcat", "-d", "-t", str(max(lines, 1))]
    if filter_expr:
        args.extend(filter_expr.split())
    proc = device.adb(*args, timeout=20)
    if proc.returncode != 0:
        return f"logcat failed: {proc.stderr.strip()}"
    return proc.stdout or "(no log lines)"


def android_launch_app_sync(device: AndroidDevice, package: str) -> str:
    """Launch an app by package name via monkey (works for any package with a launcher)."""
    proc = device.adb(
        "shell", "monkey", "-p", package, "-c",
        "android.intent.category.LAUNCHER", "1",
        timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"app launch failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return f"launched {package}"


def android_install_apk_sync(device: AndroidDevice, apk_path: str) -> str:
    proc = device.adb("install", "-r", apk_path, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"install failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return f"installed {apk_path}"


# ---------- DeviceRegistry extension ----------

class AndroidAllocator:
    """Helper for DeviceRegistry to allocate an Android session.

    Kept as a free-function-like class so DeviceRegistry (in mobile.py) doesn't
    have to import this module unconditionally — and so iOS code paths don't
    require the Android SDK to be present.
    """

    @staticmethod
    async def allocate(
        emulator_name: str | None,
        app: str | None,
        package: str | None,
    ) -> tuple[str, AndroidDevice]:
        adb_path = await asyncio.to_thread(find_adb)
        existing = set(await asyncio.to_thread(list_running_devices, adb_path))

        emulator_proc: subprocess.Popen | None = None
        serial: str

        if not existing:
            # Need to start an emulator. Require emulator_name.
            if not emulator_name:
                avds = await asyncio.to_thread(find_emulator)
                avd_list = await asyncio.to_thread(list_avds, avds)
                raise ValueError(
                    "No emulator is currently running and no emulator_name was given. "
                    f"Available AVDs: {avd_list}. Pass emulator_name=<one of those>."
                )
            emulator_path = await asyncio.to_thread(find_emulator)
            avds_available = await asyncio.to_thread(list_avds, emulator_path)
            if emulator_name not in avds_available:
                raise ValueError(
                    f"AVD {emulator_name!r} not found. Available: {avds_available}"
                )
            emulator_proc = await asyncio.to_thread(
                start_emulator, emulator_path, emulator_name
            )
            serial = await asyncio.to_thread(wait_for_emulator, adb_path, existing)
        else:
            # Use the first running device. If user asked for a specific emulator
            # name and one matches, we use it; otherwise we just use whatever's up.
            serial = sorted(existing)[0]

        device = AndroidDevice(device_id=serial, adb_path=adb_path, package=package)
        device.emulator_proc = emulator_proc

        # Install + launch the app if requested
        if app:
            await asyncio.to_thread(android_install_apk_sync, device, app)
        if package:
            await asyncio.to_thread(android_launch_app_sync, device, package)

        token = secrets.token_hex(8)
        return token, device
