"""Static IPA inspection — the iOS analog of apk_inspect (v0.6).

Reads an `.ipa` (a zip) WITHOUT installing or running it: unpacks the app
bundle's Info.plist and reports identity, minimum OS, the privacy-usage strings
(which sensitive resources the app asks for), App Transport Security posture,
custom URL schemes, and background modes.

Pure Python — `zipfile` + `plistlib` handle both binary and XML plists, so this
needs no Xcode, no external tools, and works anywhere the server runs. First-
pass only: no entitlements/provisioning-profile or binary analysis (that needs
codesign / a mobile pentest toolchain).
"""

from __future__ import annotations

import plistlib
import zipfile
from pathlib import Path

# Info.plist privacy keys → human labels. Presence means the app declares intent
# to use that resource; absence of a required one causes an App Store rejection.
_USAGE_KEYS = {
    "NSCameraUsageDescription": "camera",
    "NSMicrophoneUsageDescription": "microphone",
    "NSPhotoLibraryUsageDescription": "photo library (read)",
    "NSPhotoLibraryAddUsageDescription": "photo library (add)",
    "NSLocationWhenInUseUsageDescription": "location (in use)",
    "NSLocationAlwaysAndWhenInUseUsageDescription": "location (always)",
    "NSContactsUsageDescription": "contacts",
    "NSCalendarsUsageDescription": "calendars",
    "NSRemindersUsageDescription": "reminders",
    "NSMotionUsageDescription": "motion & fitness",
    "NSHealthShareUsageDescription": "health (read)",
    "NSHealthUpdateUsageDescription": "health (write)",
    "NSBluetoothAlwaysUsageDescription": "bluetooth",
    "NSFaceIDUsageDescription": "Face ID",
    "NSUserTrackingUsageDescription": "app tracking (IDFA)",
    "NSLocalNetworkUsageDescription": "local network",
    "NSSpeechRecognitionUsageDescription": "speech recognition",
}


def _find_info_plist(ipa: zipfile.ZipFile) -> str | None:
    """Return the zip path of Payload/<App>.app/Info.plist (top-level bundle only)."""
    candidates = []
    for name in ipa.namelist():
        parts = name.split("/")
        # Payload/Foo.app/Info.plist — exactly 3 segments, app bundle at index 1.
        if (
            len(parts) == 3
            and parts[0] == "Payload"
            and parts[1].endswith(".app")
            and parts[2] == "Info.plist"
        ):
            candidates.append(name)
    if not candidates:
        return None
    # Shortest path = the main app bundle (avoids plug-in/watch app plists).
    return min(candidates, key=len)


def ipa_inspect_sync(ipa_path: str) -> str:
    """Static first-pass recon of an IPA file. Returns a formatted report."""
    ipa_p = Path(ipa_path).expanduser()
    if not ipa_p.is_file():
        return f"FAIL: IPA not found: {ipa_path}"
    if ipa_p.suffix.lower() != ".ipa":
        return f"FAIL: not an .ipa file: {ipa_path}"

    try:
        with zipfile.ZipFile(ipa_p) as ipa:
            plist_name = _find_info_plist(ipa)
            if not plist_name:
                return "FAIL: no Payload/*.app/Info.plist found — is this a valid IPA?"
            info = plistlib.loads(ipa.read(plist_name))
    except zipfile.BadZipFile:
        return f"FAIL: not a readable zip/IPA: {ipa_path}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"

    bundle_id = info.get("CFBundleIdentifier", "(unknown)")
    name = info.get("CFBundleDisplayName") or info.get("CFBundleName", "(unknown)")
    short_ver = info.get("CFBundleShortVersionString", "?")
    build = info.get("CFBundleVersion", "?")
    min_os = info.get("MinimumOSVersion", "?")
    size_mb = ipa_p.stat().st_size / 1024 / 1024

    usage = [(human) for key, human in _USAGE_KEYS.items() if key in info]

    lines = [
        f"########## STATIC IPA RECON: {ipa_p.name} ##########",
        "(Info.plist — read-only, app not installed or run)\n",
        "=== IDENTITY ===",
        f"Bundle ID:    {bundle_id}",
        f"Name:         {name}",
        f"Version:      {short_ver} (build {build})",
        f"Minimum iOS:  {min_os}",
        f"IPA size:     {size_mb:.1f} MB",
    ]

    lines.append("\n=== SECURITY / PRIVACY (first-pass — Info.plist only) ===")
    # App Transport Security
    ats = info.get("NSAppTransportSecurity", {})
    if isinstance(ats, dict) and ats.get("NSAllowsArbitraryLoads") is True:
        lines.append(
            "  FAIL [ats] NSAllowsArbitraryLoads=true — App Transport Security "
            "disabled globally, plaintext HTTP allowed"
        )
    elif ats:
        lines.append("  WARN [ats] Custom App Transport Security config — review exception domains")
    else:
        lines.append("  PASS [ats] Default App Transport Security (HTTPS enforced)")

    # Tracking / IDFA
    if "NSUserTrackingUsageDescription" in info:
        lines.append("  WARN [tracking] Requests App Tracking Transparency (IDFA) — confirm consent flow")

    # URL schemes (deep-link / hijack surface)
    schemes = []
    for entry in info.get("CFBundleURLTypes", []) or []:
        schemes.extend(entry.get("CFBundleURLSchemes", []) or [])
    if schemes:
        lines.append(f"  WARN [url-schemes] Registers custom URL scheme(s): {', '.join(schemes)} "
                     "— validate inputs; prefer Universal Links")

    # Background modes
    bg = info.get("UIBackgroundModes", []) or []
    if bg:
        lines.append(f"  INFO [background] Background modes: {', '.join(bg)} — check battery/data impact")

    lines.append(f"\n=== PRIVACY USAGE STRINGS ({len(usage)}) ===")
    if usage:
        for human in usage:
            lines.append(f"  {human}")
        lines.append(
            "        → each declares access to sensitive data; confirm the runtime "
            "prompt, rationale, and graceful denial path."
        )
    else:
        lines.append("  (none declared)")

    lines.append(
        "\n=== GO DEEPER ===\n"
        "  - Install + run it for functionality/UI/a11y/perf recon: device_allocate "
        "then ios_inspect / ios_a11y_audit / ios_perf_snapshot.\n"
        "  - Entitlements, provisioning profile, and binary analysis need codesign "
        "/ a mobile pentest toolchain — out of scope for this static pass.\n"
        "########## END STATIC IPA RECON — first-pass only ##########"
    )
    return "\n".join(lines)
