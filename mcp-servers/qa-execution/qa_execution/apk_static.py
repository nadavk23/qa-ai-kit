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


def _xmltree(aapt_path: str, apk_path: str) -> str:
    """Dump the (binary) AndroidManifest.xml as a text tree.

    aapt and aapt2 take different argument shapes for this command, so branch on
    which binary we resolved.
    """
    name = Path(aapt_path).name
    if "aapt2" in name:
        cmd = [aapt_path, "dump", "xmltree", "--file", "AndroidManifest.xml", apk_path]
    else:
        cmd = [aapt_path, "dump", "xmltree", apk_path, "AndroidManifest.xml"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(
            f"'{name} dump xmltree' failed: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


_COMPONENT_ELEMENTS = ("activity", "activity-alias", "service", "receiver", "provider")


def _attr_bool(line: str) -> bool | None:
    """Interpret an aapt xmltree boolean attribute line. 0xffffffff=true, 0x0=false."""
    if "0xffffffff" in line:
        return True
    if re.search(r"=\(type 0x12\)0x0\b", line):
        return False
    return None


def _attr_str(line: str) -> str | None:
    """Extract a string attribute value from an aapt xmltree line."""
    raw = re.search(r'\(Raw:\s*"([^"]*)"', line)
    if raw:
        return raw.group(1)
    m = re.search(r'="([^"]*)"', line)
    return m.group(1) if m else None


def _parse_manifest_security(tree: str) -> dict:
    """Parse `aapt dump xmltree AndroidManifest.xml` for security-relevant facts.

    Indentation encodes nesting. We track application-level flags and each
    exported/permission state per component (activity/service/receiver/provider).
    """
    app: dict[str, bool | None] = {
        "debuggable": None,
        "allowBackup": None,
        "usesCleartextTraffic": None,
        "networkSecurityConfig": False,
    }
    components: list[dict] = []
    cur: dict | None = None
    cur_indent = -1
    in_application = False

    for line in tree.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if stripped.startswith("E: "):
            element = stripped[3:].split(" ", 1)[0]
            # A new element at or above the current component's depth closes it.
            if cur is not None and indent <= cur_indent:
                cur = None
            if element == "application":
                in_application = True
            elif element in _COMPONENT_ELEMENTS:
                cur = {
                    "type": element,
                    "name": None,
                    "exported": None,
                    "permission": False,
                    "intent_filter": False,
                }
                cur_indent = indent
                components.append(cur)
            elif element == "intent-filter" and cur is not None:
                cur["intent_filter"] = True
            continue

        if stripped.startswith("A: "):
            if cur is not None and indent > cur_indent:
                # attribute of the current component
                if ":name(" in stripped and cur["name"] is None:
                    cur["name"] = _attr_str(stripped)
                elif ":exported(" in stripped:
                    cur["exported"] = _attr_bool(stripped)
                elif ":permission(" in stripped:
                    cur["permission"] = True
            elif in_application and cur is None:
                # application-level attribute
                if ":debuggable(" in stripped:
                    app["debuggable"] = _attr_bool(stripped)
                elif ":allowBackup(" in stripped:
                    app["allowBackup"] = _attr_bool(stripped)
                elif ":usesCleartextTraffic(" in stripped:
                    app["usesCleartextTraffic"] = _attr_bool(stripped)
                elif ":networkSecurityConfig(" in stripped:
                    app["networkSecurityConfig"] = True
            continue

    return {"app": app, "components": components}


def _is_exported(comp: dict) -> bool:
    """A component is externally reachable if exported=true, or (exported unset
    and it declares an intent-filter — the legacy implicit-export rule)."""
    if comp["exported"] is True:
        return True
    if comp["exported"] is None and comp["intent_filter"]:
        return True
    return False


def apk_security_sync(apk_path: str) -> str:
    """Deeper static security pass over an APK's manifest (v0.6).

    Complements apk_inspect (badging) by parsing AndroidManifest.xml for the
    facts badging can't show: per-component exported flags and permission
    protection, allowBackup, cleartext traffic, and network-security-config.
    Still static and first-pass — no dataflow, no native-lib or dependency
    analysis; for that, reach for MobSF / apkanalyzer.
    """
    apk = Path(apk_path).expanduser()
    if not apk.is_file():
        return f"FAIL: APK not found: {apk_path}"
    if apk.suffix.lower() != ".apk":
        return f"FAIL: not an .apk file: {apk_path}"
    try:
        aapt_path = find_aapt()
        tree = _xmltree(aapt_path, str(apk))
    except FileNotFoundError as e:
        return f"FAIL: {e}"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"

    parsed = _parse_manifest_security(tree)
    app = parsed["app"]
    comps = parsed["components"]

    lines = [
        f"########## DEEP APK SECURITY: {apk.name} ##########",
        "(aapt xmltree — static manifest analysis, app not run)\n",
        "=== APPLICATION FLAGS ===",
    ]
    if app["debuggable"] is True:
        lines.append("  FAIL [debuggable] android:debuggable=true — must be false in release")
    else:
        lines.append("  PASS [debuggable] Not debuggable")
    # allowBackup defaults to true when unset (< API 31 semantics worth flagging).
    if app["allowBackup"] is True or app["allowBackup"] is None:
        state = "true" if app["allowBackup"] else "unset (defaults true on older platforms)"
        lines.append(
            f"  WARN [allowBackup] android:allowBackup={state} — app data can be "
            "extracted via adb backup; set false unless intentional"
        )
    else:
        lines.append("  PASS [allowBackup] Backups disabled")
    if app["usesCleartextTraffic"] is True:
        lines.append("  FAIL [cleartext] android:usesCleartextTraffic=true — allows plaintext HTTP")
    elif app["networkSecurityConfig"]:
        lines.append("  PASS [network] networkSecurityConfig present — review it for cleartext exemptions")
    else:
        lines.append("  PASS [cleartext] Cleartext not explicitly enabled")

    # Exported components without permission protection.
    exposed = [
        c for c in comps if _is_exported(c) and not c["permission"]
    ]
    lines.append(f"\n=== COMPONENTS ({len(comps)} total; {len(exposed)} exported & unprotected) ===")
    if exposed:
        for c in exposed:
            reason = "exported=true" if c["exported"] is True else "implicit (intent-filter, no exported)"
            sev = "FAIL" if c["type"] == "provider" else "WARN"
            lines.append(
                f"  {sev} [{c['type']}] {c['name'] or '(unnamed)'} — reachable by other apps "
                f"({reason}), no android:permission guard"
            )
        lines.append(
            "        → confirm each is meant to be public; add android:permission "
            "or set exported=false otherwise. Exported providers are highest-risk."
        )
    else:
        lines.append("  PASS — no exported components lack permission protection")

    lines.append(
        "\n=== GO DEEPER ===\n"
        "  Static manifest only — no dataflow, secrets, native libs, or dependency "
        "CVEs. For those: MobSF, apkanalyzer, or a dedicated mobile pentest.\n"
        "########## END DEEP APK SECURITY ##########"
    )
    return "\n".join(lines)


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
