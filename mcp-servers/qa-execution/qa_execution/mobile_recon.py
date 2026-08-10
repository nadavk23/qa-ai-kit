"""Runtime mobile recon helpers — the on-device half of Layer 2.

Structured first-pass audits that run against an *allocated* device session,
mirroring the web recon dimensions:

- Android accessibility  — from the uiautomator hierarchy (adb-native)
- Android performance     — cold start / memory / jank via `am` + `dumpsys`
- iOS accessibility       — from the XCUITest page source (Appium)

Deliberately shallow, same as web recon: enough signal to flag risk and decide
where a deeper pass is worth it. Each returns a formatted report string.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from qa_execution.android import AndroidDevice, _dump_ui_xml, _parse_bounds

_MIN_TOUCH_DP = 48  # Material / WCAG 2.5.5 target-size floor
_IMAGE_CLASSES = ("ImageView", "ImageButton")


# --------------------------------------------------------------------------- #
# Android accessibility
# --------------------------------------------------------------------------- #

def _android_density(device: AndroidDevice) -> int | None:
    try:
        proc = device.adb("shell", "wm", "density", timeout=5)
        m = re.search(r"(\d+)", proc.stdout)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def android_a11y_audit_sync(device: AndroidDevice, limit: int = 12) -> str:
    """First-pass structural accessibility scan of the current Android screen.

    Flags interactive elements with no accessible name, images with no
    content-desc, and touch targets below the 48dp floor. Does NOT cover color
    contrast, TalkBack focus order, or dynamic-type scaling — those need a
    manual TalkBack pass.
    """
    xml = _dump_ui_xml(device)
    root = ET.fromstring(xml)
    density = _android_density(device)  # px per 160dp; None if unavailable

    unlabeled_controls: list[str] = []
    undescribed_images: list[str] = []
    small_targets: list[str] = []
    interactive = 0

    for el in root.iter():
        a = el.attrib
        klass = a.get("class", "")
        short = klass.split(".")[-1] if klass else "View"
        text = a.get("text", "").strip()
        desc = a.get("content-desc", "").strip()
        clickable = a.get("clickable") == "true"
        rid = a.get("resource-id", "")
        tag = rid.split("/")[-1] if rid else short

        if clickable:
            interactive += 1
            if not text and not desc:
                unlabeled_controls.append(tag)
            # touch-target size (needs density to convert px→dp)
            if density:
                b = _parse_bounds(a.get("bounds", ""))
                if b:
                    w_dp = (b[2] - b[0]) * 160 / density
                    h_dp = (b[3] - b[1]) * 160 / density
                    if 0 < min(w_dp, h_dp) < _MIN_TOUCH_DP:
                        small_targets.append(f"{tag} ({w_dp:.0f}x{h_dp:.0f}dp)")

        if short in _IMAGE_CLASSES and not desc:
            undescribed_images.append(tag)

    def _dedup(xs: list[str]) -> list[str]:
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    unlabeled_controls = _dedup(unlabeled_controls)
    undescribed_images = _dedup(undescribed_images)
    small_targets = _dedup(small_targets)

    lines = [
        "=== ANDROID ACCESSIBILITY (first-pass, structural) ===",
        f"Scanned {interactive} clickable element(s)"
        + ("" if density else "  [density unknown — target-size checks skipped]"),
    ]
    fails = warns = 0
    if unlabeled_controls:
        fails += 1
        lines.append(
            f"  FAIL [control-name] {len(unlabeled_controls)} clickable element(s) "
            "with no text or content-desc (invisible to TalkBack):"
        )
        for t in unlabeled_controls[:limit]:
            lines.append(f"        {t}")
    if undescribed_images:
        fails += 1
        lines.append(
            f"  FAIL [image-desc] {len(undescribed_images)} ImageView/ImageButton "
            "with no content-desc:"
        )
        for t in undescribed_images[:limit]:
            lines.append(f"        {t}")
    if small_targets:
        warns += 1
        lines.append(
            f"  WARN [target-size] {len(small_targets)} touch target(s) below {_MIN_TOUCH_DP}dp:"
        )
        for t in small_targets[:limit]:
            lines.append(f"        {t}")
    if not (unlabeled_controls or undescribed_images or small_targets):
        lines.append("  No structural a11y issues in the checked rules on this screen.")

    lines.append(
        "\nScope note: one screen, structural only — no contrast, TalkBack focus "
        "order, or dynamic-type. Re-run on each key screen; go deeper with a "
        "manual TalkBack pass and Accessibility Scanner on the flagged screens."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Android performance (cold start / memory / jank)
# --------------------------------------------------------------------------- #

def _resolve_launch_component(device: AndroidDevice, package: str) -> str | None:
    try:
        proc = device.adb("shell", "cmd", "package", "resolve-activity", "--brief", package, timeout=10)
        for line in proc.stdout.splitlines():
            line = line.strip()
            if "/" in line and line.startswith(package):
                return line
    except Exception:
        pass
    return None


def android_perf_snapshot_sync(device: AndroidDevice, package: str = "") -> str:
    """First-pass Android performance: cold-start time, memory (PSS), and jank.

    Uses `am start -W` (startup), `dumpsys meminfo` (memory), and
    `dumpsys gfxinfo` (frame jank). Single sample on an emulator/device — not a
    controlled benchmark. Pass `package` explicitly, or the session's package
    is used.
    """
    pkg = package or device.package
    if not pkg:
        return (
            "FAIL: no package known for this session. Pass package=<app id>, or "
            "allocate the device with a package."
        )

    lines = [f"=== ANDROID PERFORMANCE (first-pass, single sample) — {pkg} ==="]

    # Cold start: force-stop then timed launch.
    component = _resolve_launch_component(device, pkg)
    if component:
        try:
            device.adb("shell", "am", "force-stop", pkg, timeout=10)
            proc = device.adb("shell", "am", "start", "-W", "-n", component, timeout=30)
            total = re.search(r"TotalTime:\s*(\d+)", proc.stdout)
            wait = re.search(r"WaitTime:\s*(\d+)", proc.stdout)
            if total:
                t = int(total.group(1))
                band = "GOOD" if t <= 1000 else "NEEDS-WORK" if t <= 2500 else "POOR"
                extra = f" (WaitTime {wait.group(1)}ms)" if wait else ""
                lines.append(f"  Cold start (TotalTime): {t} ms{extra}   [{band}]")
            else:
                lines.append("  Cold start: could not parse TotalTime from am start")
        except Exception as e:
            lines.append(f"  Cold start: measurement failed ({type(e).__name__}: {e})")
    else:
        lines.append("  Cold start: launchable component not resolved — skipped")

    # Memory: total PSS.
    try:
        proc = device.adb("shell", "dumpsys", "meminfo", pkg, timeout=20)
        m = re.search(r"TOTAL(?:\s+PSS)?:?\s+(\d+)", proc.stdout) or re.search(
            r"^\s*TOTAL\s+(\d+)", proc.stdout, re.MULTILINE
        )
        if m:
            pss_mb = int(m.group(1)) / 1024
            band = "GOOD" if pss_mb <= 150 else "NEEDS-WORK" if pss_mb <= 350 else "POOR"
            lines.append(f"  Memory (TOTAL PSS):     {pss_mb:.0f} MB   [{band}]")
        else:
            lines.append("  Memory: could not parse PSS (is the app running?)")
    except Exception as e:
        lines.append(f"  Memory: measurement failed ({type(e).__name__}: {e})")

    # Jank: gfxinfo frame stats.
    try:
        proc = device.adb("shell", "dumpsys", "gfxinfo", pkg, timeout=20)
        total_f = re.search(r"Total frames rendered:\s*(\d+)", proc.stdout)
        janky = re.search(r"Janky frames:\s*(\d+)\s*\(([\d.]+)%\)", proc.stdout)
        if total_f and janky:
            pct = float(janky.group(2))
            band = "GOOD" if pct <= 5 else "NEEDS-WORK" if pct <= 20 else "POOR"
            lines.append(
                f"  Jank: {janky.group(1)}/{total_f.group(1)} frames "
                f"janky ({pct:.1f}%)   [{band}]"
            )
        else:
            lines.append("  Jank: no gfxinfo frame stats yet — interact with the app, then re-run")
    except Exception as e:
        lines.append(f"  Jank: measurement failed ({type(e).__name__}: {e})")

    lines.append(
        "\nNote: single sample, unthrottled, emulator timings differ from real "
        "hardware. Go deeper with Android Studio Profiler, Macrobenchmark for "
        "startup, and Perfetto for jank on a physical device."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# iOS accessibility (from XCUITest page source)
# --------------------------------------------------------------------------- #

_IOS_INTERACTIVE = (
    "XCUIElementTypeButton",
    "XCUIElementTypeImage",
    "XCUIElementTypeCell",
    "XCUIElementTypeSwitch",
    "XCUIElementTypeLink",
    "XCUIElementTypeTextField",
    "XCUIElementTypeSecureTextField",
)


def ios_a11y_audit_sync(device, limit: int = 12) -> str:
    """First-pass structural accessibility scan of the current iOS screen.

    From the XCUITest hierarchy: interactive elements with no accessibility
    name/label/value, and elements explicitly marked accessible=false. Does NOT
    cover contrast, VoiceOver rotor order, or Dynamic Type — needs a manual
    VoiceOver pass.
    """
    source = device.driver.page_source
    try:
        root = ET.fromstring(source)
    except ET.ParseError as e:
        return f"FAIL: page_source parse failed ({e}); raw size {len(source)} bytes"

    nameless: list[str] = []
    not_accessible: list[str] = []
    interactive = 0

    for el in root.iter():
        etype = el.tag
        if etype not in _IOS_INTERACTIVE:
            continue
        a = el.attrib
        if a.get("visible") == "false":
            continue
        interactive += 1
        short = etype.replace("XCUIElementType", "")
        name = (a.get("name") or a.get("label") or a.get("value") or "").strip()
        if not name:
            nameless.append(short)
        elif a.get("accessible") == "false":
            not_accessible.append(f"{short}:{name[:24]}")

    lines = [
        "=== iOS ACCESSIBILITY (first-pass, structural) ===",
        f"Scanned {interactive} visible interactive element(s)",
    ]
    if nameless:
        lines.append(
            f"  FAIL [control-name] {len(nameless)} interactive element(s) with no "
            "accessibility name/label (invisible to VoiceOver):"
        )
        for t in nameless[:limit]:
            lines.append(f"        {t}")
    if not_accessible:
        lines.append(
            f"  WARN [not-accessible] {len(not_accessible)} named element(s) marked "
            "accessible=false:"
        )
        for t in not_accessible[:limit]:
            lines.append(f"        {t}")
    if not (nameless or not_accessible):
        lines.append("  No structural a11y issues in the checked rules on this screen.")

    lines.append(
        "\nScope note: one screen, structural only — no contrast, VoiceOver rotor "
        "order, or Dynamic Type. Go deeper with a manual VoiceOver pass and the "
        "Accessibility Inspector on the flagged screens."
    )
    return "\n".join(lines)
