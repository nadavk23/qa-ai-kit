"""Mobile testing via Appium — iOS Simulator support.

Wraps Appium-Python-Client behind async-friendly helpers. Multiple devices can
be allocated concurrently; each is identified by an opaque token returned from
`DeviceRegistry.allocate_ios` and passed back on every subsequent call.

Assumes an Appium server is running externally (default http://127.0.0.1:4723).
Override with the QA_APPIUM_URL environment variable.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import time
import xml.etree.ElementTree as ET
from typing import Any

from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait


DEFAULT_APPIUM_URL = "http://127.0.0.1:4723"

_IOS_STRATEGIES: dict[str, str] = {
    "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
    "predicate": AppiumBy.IOS_PREDICATE,
    "xpath": AppiumBy.XPATH,
    "class_chain": AppiumBy.IOS_CLASS_CHAIN,
}


def ios_by(strategy: str) -> str:
    """Translate a friendly strategy name into an AppiumBy constant."""
    if strategy not in _IOS_STRATEGIES:
        raise ValueError(
            f"Unknown iOS locator strategy {strategy!r}. "
            f"Expected one of: {sorted(_IOS_STRATEGIES)}"
        )
    return _IOS_STRATEGIES[strategy]


class MobileDevice:
    def __init__(
        self,
        driver: webdriver.Remote,
        platform: str,
        device_name: str,
        version: str | None,
        app: str | None,
        bundle_id: str | None,
    ) -> None:
        self.driver = driver
        self.platform = platform
        self.device_name = device_name
        self.version = version
        self.app = app
        self.bundle_id = bundle_id


class DeviceRegistry:
    """Token-keyed registry of allocated mobile devices. One instance per server.

    Holds both iOS sessions (MobileDevice — Appium-backed) and Android sessions
    (AndroidDevice from qa_execution.android — adb-backed). Tools dispatch on
    `device.platform`. The Android module is imported lazily so iOS-only users
    don't need the Android SDK present.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._devices: dict[str, Any] = {}  # MobileDevice | AndroidDevice

    async def allocate_ios(
        self,
        version: str | None,
        device_name: str | None,
        app: str | None,
        bundle_id: str | None,
        server_url: str | None = None,
    ) -> tuple[str, MobileDevice]:
        if not app and not bundle_id:
            raise ValueError(
                "Provide either `app` (path to .app/.ipa) or `bundle_id` "
                "(of an app already installed on the simulator)."
            )
        if app and bundle_id:
            raise ValueError("Provide `app` OR `bundle_id`, not both.")

        opts = XCUITestOptions()
        opts.device_name = device_name or "iPhone 15"
        if version:
            opts.platform_version = version
        if app:
            opts.app = app
        if bundle_id:
            opts.bundle_id = bundle_id

        url = server_url or os.environ.get("QA_APPIUM_URL", DEFAULT_APPIUM_URL)
        driver = await asyncio.to_thread(webdriver.Remote, url, options=opts)

        device = MobileDevice(
            driver=driver,
            platform="ios",
            device_name=opts.device_name,
            version=version,
            app=app,
            bundle_id=bundle_id,
        )
        token = secrets.token_hex(8)
        async with self._lock:
            self._devices[token] = device
        return token, device

    async def allocate_android(
        self,
        emulator_name: str | None,
        app: str | None,
        package: str | None,
    ) -> tuple[str, Any]:
        from qa_execution.android import AndroidAllocator  # lazy import

        token, device = await AndroidAllocator.allocate(emulator_name, app, package)
        async with self._lock:
            self._devices[token] = device
        return token, device

    async def release(self, token: str) -> bool:
        async with self._lock:
            device = self._devices.pop(token, None)
        if device is None:
            return False
        platform = getattr(device, "platform", None)
        if platform == "ios":
            try:
                await asyncio.to_thread(device.driver.quit)
            except WebDriverException:
                pass
        elif platform == "android":
            # If we started the emulator, leave it running — releasing the token
            # only relinquishes our handle to it. User can kill the emulator via
            # the AVD manager or `adb emu kill` when they're done.
            pass
        return True

    def get(self, token: str) -> Any:
        device = self._devices.get(token)
        if device is None:
            raise KeyError(
                f"Unknown device token {token!r}. "
                f"Call device_allocate first, or device_list to see active tokens."
            )
        return device

    def list(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for tk, d in self._devices.items():
            platform = getattr(d, "platform", "unknown")
            if platform == "ios":
                out.append(
                    {
                        "token": tk,
                        "platform": "ios",
                        "device_name": d.device_name,
                        "version": d.version,
                        "app": d.app,
                        "bundle_id": d.bundle_id,
                    }
                )
            elif platform == "android":
                out.append(
                    {
                        "token": tk,
                        "platform": "android",
                        "device_id": d.device_id,
                        "package": d.package,
                    }
                )
            else:
                out.append({"token": tk, "platform": platform})
        return out


# ---------- sync iOS action helpers (run via asyncio.to_thread) ----------

def _wait_for(device: MobileDevice, strategy: str, value: str, timeout_ms: int):
    by = ios_by(strategy)
    return WebDriverWait(device.driver, max(timeout_ms / 1000, 0.1)).until(
        lambda d: d.find_element(by, value)
    )


def ios_tap_sync(device: MobileDevice, strategy: str, value: str, timeout_ms: int) -> str:
    el = _wait_for(device, strategy, value, timeout_ms)
    el.click()
    return f"tapped {strategy}={value!r}"


def ios_type_sync(
    device: MobileDevice, strategy: str, value: str, text: str, clear: bool, timeout_ms: int
) -> str:
    el = _wait_for(device, strategy, value, timeout_ms)
    if clear:
        el.clear()
    el.send_keys(text)
    return f"typed into {strategy}={value!r}"


def ios_assert_element_sync(
    device: MobileDevice, strategy: str, value: str, present: bool, timeout_ms: int
) -> tuple[bool, str]:
    by = ios_by(strategy)
    found = False
    try:
        WebDriverWait(device.driver, max(timeout_ms / 1000, 0.1)).until(
            lambda d: d.find_element(by, value)
        )
        found = True
    except TimeoutException:
        found = False
    except WebDriverException as e:
        return False, f"driver error: {type(e).__name__}: {e}"
    if found == present:
        desc = "present" if present else "absent"
        return True, f"element {strategy}={value!r} is {desc}"
    actual = "present" if found else "absent"
    expected = "present" if present else "absent"
    return False, (
        f"expected element {strategy}={value!r} to be {expected}, was {actual}"
    )


def _element_text(el) -> str:
    """Best-effort text extraction from an iOS element."""
    for attr in ("value", "label", "name"):
        try:
            v = el.get_attribute(attr)
        except WebDriverException:
            v = None
        if v:
            return v
    return ""


def ios_assert_text_sync(
    device: MobileDevice,
    text: str,
    strategy: str | None,
    value: str | None,
    timeout_ms: int,
) -> tuple[bool, str]:
    end = time.monotonic() + max(timeout_ms / 1000, 0.0)
    last_err = ""
    while True:
        try:
            if strategy and value:
                el = device.driver.find_element(ios_by(strategy), value)
                if text in _element_text(el):
                    return True, f"text {text!r} found in {strategy}={value!r}"
            else:
                source = device.driver.page_source
                if text in source:
                    return True, f"text {text!r} found on screen"
        except NoSuchElementException as e:
            last_err = f"{type(e).__name__}: element {strategy}={value!r} not yet present"
        except WebDriverException as e:
            return False, f"driver error: {type(e).__name__}: {e}"
        if time.monotonic() >= end:
            break
        time.sleep(0.2)
    detail = f" ({last_err})" if last_err else ""
    return False, f"text {text!r} not found within {timeout_ms}ms{detail}"


def ios_inspect_sync(device: MobileDevice, limit: int) -> str:
    source = device.driver.page_source
    try:
        root = ET.fromstring(source)
    except ET.ParseError as e:
        return f"inspect: page_source parse failed ({e}); raw size {len(source)} bytes"

    elements: list[dict[str, str]] = []
    for el in root.iter():
        attrs = el.attrib
        name = attrs.get("name", "")
        label = attrs.get("label", "")
        value = attrs.get("value", "")
        if not (name or label or value):
            continue
        elements.append(
            {
                "type": el.tag.replace("XCUIElementType", ""),
                "name": name,
                "label": label,
                "value": value,
                "enabled": attrs.get("enabled", ""),
                "visible": attrs.get("visible", ""),
            }
        )
        if len(elements) >= limit:
            break

    lines = [f"Elements ({len(elements)}):"]
    for i, el in enumerate(elements):
        parts = [f"[{i}] {el['type']}"]
        if el["name"]:
            parts.append(f"name={el['name']!r}")
        if el["label"] and el["label"] != el["name"]:
            parts.append(f"label={el['label']!r}")
        if el["value"]:
            parts.append(f"value={el['value']!r}")
        if el["enabled"] == "false":
            parts.append("(disabled)")
        if el["visible"] == "false":
            parts.append("(hidden)")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)


def ios_screenshot_sync(device: MobileDevice, path: str) -> str:
    device.driver.save_screenshot(path)
    return path


def ios_wait_sync(
    device: MobileDevice, strategy: str | None, value: str | None, timeout_ms: int
) -> tuple[bool, str]:
    if not strategy or not value:
        time.sleep(max(timeout_ms / 1000, 0.0))
        return True, f"slept {timeout_ms}ms"
    try:
        _wait_for(device, strategy, value, timeout_ms)
        return True, f"element {strategy}={value!r} appeared"
    except TimeoutException:
        return False, f"element {strategy}={value!r} did not appear in {timeout_ms}ms"


def ios_scroll_sync(device: MobileDevice, direction: str) -> str:
    direction = direction.lower()
    if direction not in {"up", "down", "left", "right"}:
        raise ValueError(
            f"direction must be one of up/down/left/right, got {direction!r}"
        )
    device.driver.execute_script("mobile: swipe", {"direction": direction})
    return f"scrolled {direction}"


def ios_logs_sync(
    device: MobileDevice, log_type: str, limit: int
) -> str:
    """Read recent iOS device logs via Appium's driver.get_log().

    log_type: typically "syslog" (device console) or "crashlog". The exact set
              depends on the Appium driver — common values: syslog, crashlog,
              performance, server, safariConsole.
    limit:    return up to this many of the most recent entries (tail).
    """
    try:
        available = device.driver.get_log_types()
    except Exception as e:
        return f"FAIL: driver.get_log_types unavailable ({type(e).__name__}: {e})"
    if log_type not in available:
        return (
            f"FAIL: log type {log_type!r} not exposed by this driver. "
            f"Available: {available}"
        )
    try:
        entries = device.driver.get_log(log_type)
    except Exception as e:
        return f"FAIL: driver.get_log({log_type!r}) failed: {type(e).__name__}: {e}"
    if not entries:
        return f"(no {log_type} entries)"
    lines: list[str] = []
    for entry in entries[-limit:]:
        ts = entry.get("timestamp", "")
        lvl = entry.get("level", "")
        msg = entry.get("message", "")
        lines.append(f"{ts} [{lvl}] {msg}".rstrip())
    return "\n".join(lines)
