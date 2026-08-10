"""Static APK inspection — the 'point recon at an APK' entry point.

Runs `aapt`/`aapt2 dump badging` (ships with the Android SDK build-tools) to
read an APK *without installing or running it*. First-pass only: package
identity, SDK levels, launchable entry, permissions, and a few high-signal
security flags (debuggable, dangerous-permission surface).

Same philosophy as the rest of the Android path — the Android SDK is the only
prerequisite, nothing from npm. Deeper static analysis (per-component exported
flags, network-security-config, native libs) needs binary-manifest parsing and
is a roadmap item; this stays a fast first read.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

# Runtime permissions worth surfacing in a first-pass — the ones that map to a
# privacy/consent risk QA should confirm is handled (rationale, denial path).
_DANGEROUS_PERMISSIONS = {
    "android.permission.ACCESS_FINE_LOCATION": "precise location",
    "android.permission.ACCESS_COARSE_LOCATION": "approximate location",
    "android.permission.ACCESS_BACKGROUND_LOCATION": "background location",
    "android.permission.CAMERA": "camera",
    "android.permission.RECORD_AUDIO": "microphone",
    "android.permission.READ_CONTACTS": "contacts (read)",
    "android.permission.WRITE_CONTACTS": "contacts (write)",
    "android.permission.READ_SMS": "SMS (read)",
    "android.permission.SEND_SMS": "SMS (send)",
    "android.permission.RECEIVE_SMS": "SMS (receive)",
    "android.permission.READ_CALL_LOG": "call log",
    "android.permission.READ_PHONE_STATE": "phone state",
    "android.permission.READ_EXTERNAL_STORAGE": "external storage (read)",
    "android.permission.WRITE_EXTERNAL_STORAGE": "external storage (write)",
    "android.permission.READ_CALENDAR": "calendar (read)",
    "android.permission.BODY_SENSORS": "body sensors",
    "android.permission.ACTIVITY_RECOGNITION": "physical activity",
    "android.permission.POST_NOTIFICATIONS": "notifications",
}


def find_aapt() -> str:
    """Locate aapt2 (preferred) or aapt from the Android SDK build-tools.

    Search order mirrors find_adb: PATH first, then the SDK build-tools under
    $ANDROID_HOME / $ANDROID_SDK_ROOT / the macOS default, newest version first.
    Raises FileNotFoundError with actionable guidance if none is found.
    """
    for name in ("aapt2", "aapt"):
        found = shutil.which(name)
        if found:
            return found

    sdk_roots: list[Path] = []
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if env in os.environ:
            sdk_roots.append(Path(os.environ[env]))
    sdk_roots.append(Path.home() / "Library/Android/sdk")
    sdk_roots.append(Path("/usr/local/share/android-sdk"))
    sdk_roots.append(Path("/opt/homebrew/share/android-sdk"))

    for root in sdk_roots:
        build_tools = root / "build-tools"
        if not build_tools.is_dir():
            continue
        # Newest build-tools version wins (dir names sort well enough).
        for version_dir in sorted(build_tools.iterdir(), reverse=True):
            for name in ("aapt2", "aapt"):
                candidate = version_dir / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)

    raise FileNotFoundError(
        "aapt/aapt2 not found. Install Android SDK build-tools (Android Studio "
        "→ SDK Manager → SDK Tools → Android SDK Build-Tools), or set ANDROID_HOME."
    )


def _badging(aapt_path: str, apk_path: str) -> str:
    proc = subprocess.run(
        [aapt_path, "dump", "badging", apk_path],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"'{Path(aapt_path).name} dump badging' failed: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def apk_inspect_sync(apk_path: str) -> str:
    """Static first-pass recon of an APK file. Returns a formatted report."""
    apk = Path(apk_path).expanduser()
    if not apk.is_file():
        return f"FAIL: APK not found: {apk_path}"
    if apk.suffix.lower() != ".apk":
        return f"FAIL: not an .apk file: {apk_path}"

    try:
        aapt_path = find_aapt()
    except FileNotFoundError as e:
        return f"FAIL: {e}"
    try:
        out = _badging(aapt_path, str(apk))
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"

    # --- parse ---
    pkg = re.search(
        r"package: name='([^']*)'(?:\s+versionCode='([^']*)')?(?:\s+versionName='([^']*)')?",
        out,
    )
    name = pkg.group(1) if pkg else "(unknown)"
    version_code = pkg.group(2) if pkg and pkg.group(2) else "?"
    version_name = pkg.group(3) if pkg and pkg.group(3) else "?"

    sdk_min = re.search(r"sdkVersion:'(\d+)'", out)
    sdk_target = re.search(r"targetSdkVersion:'(\d+)'", out)
    label = re.search(r"application-label:'([^']*)'", out)
    launch = re.search(r"launchable-activity: name='([^']*)'", out)
    debuggable = "application-debuggable" in out

    perms = re.findall(r"uses-permission: name='([^']*)'", out)
    perms += re.findall(r"uses-permission-sdk-23: name='([^']*)'", out)
    perms = sorted(set(perms))
    dangerous = [(p, _DANGEROUS_PERMISSIONS[p]) for p in perms if p in _DANGEROUS_PERMISSIONS]

    size_mb = apk.stat().st_size / 1024 / 1024

    # --- report ---
    lines = [
        f"########## STATIC APK RECON: {apk.name} ##########",
        "(aapt badging — read-only, app not installed or run)\n",
        "=== IDENTITY ===",
        f"Package:      {name}",
        f"Label:        {label.group(1) if label else '(none)'}",
        f"Version:      {version_name} (code {version_code})",
        f"Min SDK:      {sdk_min.group(1) if sdk_min else '?'}"
        f"   Target SDK: {sdk_target.group(1) if sdk_target else '?'}",
        f"APK size:     {size_mb:.1f} MB",
        f"Launch entry: {launch.group(1) if launch else '(no launchable activity found)'}",
    ]

    lines.append("\n=== SECURITY (first-pass — static flags only) ===")
    if debuggable:
        lines.append("  FAIL [debuggable] android:debuggable=true — must be false in a release build")
    else:
        lines.append("  PASS [debuggable] Not marked debuggable")
    if sdk_target and int(sdk_target.group(1)) < 30:
        lines.append(
            f"  WARN [target-sdk] targetSdkVersion {sdk_target.group(1)} is old — "
            "misses recent platform security/privacy defaults"
        )
    if dangerous:
        lines.append(f"  WARN [permissions] {len(dangerous)} runtime (dangerous) permission(s) requested:")
        for p, human in dangerous:
            lines.append(f"        {human}  ({p})")
        lines.append(
            "        → confirm each has a runtime request, a rationale, and a graceful denial path."
        )
    else:
        lines.append("  PASS [permissions] No high-risk runtime permissions requested")

    lines.append(f"\n=== ALL PERMISSIONS ({len(perms)}) ===")
    if perms:
        for p in perms:
            lines.append(f"  {p}")
    else:
        lines.append("  (none declared)")

    lines.append(
        "\n=== GO DEEPER ===\n"
        "  - Install + run it for functionality/UI/a11y/perf recon: device_allocate "
        "then the android_* recon tools.\n"
        "  - Per-component exported flags, network-security-config, and native libs "
        "need binary-manifest analysis (roadmap) or a tool like apkanalyzer / MobSF.\n"
        "########## END STATIC APK RECON — first-pass only ##########"
    )
    return "\n".join(lines)
