#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Install a validated ATI HD 5000 DisplayPort patch on Snow Leopard or Lion.

Designed for Python 2.6 and later 2.x releases. The code also stays usable on
modern Python 3 for dry-run/UI validation.

The installer reads the target selected earlier by patchKext.py from the
validated patch manifest. It can also restore a previously verified pre-install
backup with --restore. Both operations validate the target, bundle metadata,
SHA-256 hashes and system state before replacement and cache rebuild.
"""

from __future__ import print_function

import os
import shutil
import subprocess
import sys

# The internal support modules intentionally use leading underscores.
# noinspection PyPep8Naming,PyProtectedMember
from _baselib import _baseRuntimeData as config
# noinspection PyProtectedMember
from _baselib._functions import (
    COLORS, FAIL, OK, bundle_payload_size, detail, error_status,
    exit_status, finder_size_text, join_path, line, parse_args, print_program_header,
    prompt_enter_or_quit, read_console_line, read_plist,
    script_directory as resolve_script_directory, section, set_color_enabled,
    set_error_type, sha256_file, status, terminal_supports_color,
    validate_kext_bundle_core, validate_kext_identity, validate_regular_file, write_ascii,
)


PROGRAM_NAME = "ATI HD 5000 Snow Leopard and Lion DisplayPort kext installer"
PROGRAM_VERSION = config.PACKAGE_VERSION


class InstallerError(Exception):
    pass


class MissingPatchedOutputError(InstallerError):
    pass


class ManifestError(InstallerError):
    pass


class UnknownSystemKextError(InstallerError):
    pass


class MixedSystemStateError(InstallerError):
    pass


class CommandError(InstallerError):
    pass


set_error_type(InstallerError)


def target_title(target=None, restore=False):
    if target is None:
        if restore:
            return ("| Restore ATI 5000 DisplayPort backup on OS X Snow Leopard "
                    "10.6.8 or OS X Lion 10.7.5 |")
        return ("| Install ATI 5000 DisplayPort patch on OS X Snow Leopard "
                "10.6.8 or OS X Lion 10.7.5 |")
    if restore:
        return "| Restore ATI 5000 DisplayPort backup on %s |" % target.display_name
    return "| Install ATI 5000 DisplayPort patch on %s |" % target.display_name


def print_installer_header(target=None, restore=False):
    print_program_header(target_title(target, restore), config.COPYRIGHT_LINE)


def print_intro(script_dir, target, dry_run, restore=False):
    line("Purpose:")
    if restore:
        line("This mode validates and restores the pre-install ATI system kext backup")
        line("for %s." % target.display_name)
    elif target.key == "SL":
        line("This installer validates and installs the tested three-kext DisplayPort")
        line("patch set for OS X Snow Leopard 10.6.8.")
    else:
        line("This installer validates and installs the tested ATI5000Controller")
        line("DisplayPort PPLL guard patch for OS X Lion 10.7.5 / 11G63.")
    line()
    line("Safety:")
    if restore:
        line("  - validates every backed-up kext and its known trusted state")
        line("  - validates BACKUP-MANIFEST.txt when present")
        line("  - can recover safely without the manifest when all built-in checks match")
        line("  - verifies the current system state before replacement")
        line("  - detects if the backup has already been restored")
        line("  - stages and verifies every backup bundle before activation")
        line("  - keeps the verified backup available for explicit --restore recovery")
    else:
        line("  - reads the selected target from the patch manifest")
        line("  - independently validates every patched kext and golden SHA-256")
        line("  - verifies the current system binary hashes before replacement")
        line("  - a real matching-target install creates a verified backup manifest")
        line("  - stages and verifies every replacement before activation")
        line("  - keeps the verified backup available for explicit --restore recovery")
        line()
        line("Restore:")
        line("  - restore the verified pre-install backup later with:")
        print("    " + COLORS.light_magenta +
              "python %s --restore" % config.INSTALLER_SCRIPT_NAME + COLORS.default)
        line("  - please read %s before using restore" % config.README_NAME)
    line()
    backup_dir = join_path(script_dir, target.backup_dir_name)
    line("Backup location:")
    detail("Path", backup_dir, indent=1)
    if restore:
        line("  - this directory must already contain a verified backup")
        line("  - keep an external copy of this backup directory")
    else:
        line("  - created only during a real install on the matching target system")
        line("  - patcher, dry-run and pre-backup aborts do not create this directory")
        line("  - keep an external copy of this backup directory after installation")
    line("  - %s contains full backup and manual recovery instructions" %
         config.README_NAME)
    line()
    if restore:
        line("Required verified backup kext%s:" %
             ("" if len(target.kexts) == 1 else "s"))
    else:
        line("Required patched kext%s, created by %s:" %
             ("" if len(target.kexts) == 1 else "s", config.PATCHER_SCRIPT_NAME))
    for spec in target.kexts:
        line("  - %s" % spec.bundle)
    line()
    if not prompt_enter_or_quit("Press Enter to continue or Q to quit… "):
        return False
    line()
    detail("Patch target", target.display_name, indent=1, color=COLORS.green)
    detail("Source", backup_dir if restore else
           join_path(script_dir, config.OUTPUT_DIR_NAME), indent=1)
    detail("Target", config.SYSTEM_EXTENSIONS_DIR, indent=1)
    if restore:
        mode = "restore dry-run" if dry_run else "restore"
    else:
        mode = "dry-run" if dry_run else "install"
    detail("Mode", mode, indent=1,
           color=COLORS.yellow if dry_run else COLORS.green)
    return True


def patched_output_hint(indent=3):
    prefix = "  " * indent
    print(prefix + COLORS.light_red +
          "The patched kexts have not been created yet." + COLORS.default)
    print(prefix + COLORS.light_red + "Run: " + COLORS.light_magenta +
          "python %s" % config.PATCHER_SCRIPT_NAME + COLORS.default)
    print(prefix + COLORS.light_red + "Please read %s before continuing." % config.README_NAME +
          COLORS.default)


def ensure_patched_output_dir(output_dir):
    if not os.path.exists(output_dir):
        raise MissingPatchedOutputError("patched kext directory is missing: %s" % output_dir)
    if os.path.islink(output_dir):
        raise InstallerError("patched kext directory must not be a symbolic link: %s" % output_dir)
    if not os.path.isdir(output_dir):
        raise MissingPatchedOutputError("patched kext path is not a directory: %s" % output_dir)


def read_manifest_file(path, label):
    try:
        handle = open(path, "rb")
        try:
            data = handle.read()
        finally:
            handle.close()
    except (IOError, OSError) as exc:
        raise ManifestError("cannot read %s manifest: %s" % (label, exc))

    if not isinstance(data, str):
        try:
            data = data.decode("ascii")
        except (AttributeError, UnicodeError):
            raise ManifestError("%s manifest must contain ASCII text only" % label)
    return str(data)


def parse_key_value_manifest(path, expected_header, label):
    validate_regular_file(path, "%s manifest" % label, ManifestError)
    text = read_manifest_file(path, label)
    lines = text.splitlines()
    if not lines or lines[0].strip() != expected_header:
        raise ManifestError("%s manifest header is invalid" % label)

    values = {}
    for raw_line in lines[1:]:
        line_text = raw_line.strip()
        if not line_text:
            continue
        if ":" not in line_text:
            raise ManifestError("invalid %s manifest line: %s" % (label, line_text))
        key, value = line_text.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in values:
            raise ManifestError("duplicate or empty %s manifest key: %s" % (label, key))
        values[key] = value
    return values


def parse_manifest(output_dir):
    manifest_path = join_path(output_dir, config.MANIFEST_NAME)
    values = parse_key_value_manifest(
        manifest_path, "HD5000 DisplayPort patch manifest", "patch"
    )

    required_keys = (
        "Manifest-Version", "Target", "Target-OS", "Target-OS-Version",
        "Target-Build", "Source-Build", "Bundle-Version", "Patcher-Version",
        "Kext-Count", "Kexts",
    )
    for key in required_keys:
        if key not in values:
            raise ManifestError("patch manifest is missing required key: %s" % key)

    if values["Manifest-Version"] != "1":
        raise ManifestError("unsupported patch manifest version: %s" %
                            values["Manifest-Version"])

    target = config.get_target(values["Target"])
    if target is None:
        raise ManifestError("patch manifest contains an unknown target: %s" %
                            values["Target"])

    expected = {
        "Target": target.key,
        "Target-OS": target.display_name,
        "Target-OS-Version": target.target_os_version,
        "Target-Build": target.target_build if target.target_build else "not-fixed",
        "Source-Build": target.source_build,
        "Bundle-Version": target.expected_bundle_version,
        "Patcher-Version": PROGRAM_VERSION,
        "Kext-Count": str(len(target.kexts)),
        "Kexts": ",".join([spec.bundle for spec in target.kexts]),
    }
    for key, expected_value in expected.items():
        if values.get(key) != expected_value:
            raise ManifestError(
                "patch manifest %s mismatch\n"
                "    found:    %s\n"
                "    expected: %s" % (key, values.get(key), expected_value)
            )

    return target, manifest_path


def list_kext_bundle_names(directory, list_error_text):
    """Return sorted .kext directory/link names from one validated container."""
    try:
        entries = os.listdir(directory)
    except (IOError, OSError) as exc:
        raise InstallerError("%s: %s" % (list_error_text, exc))

    found = []
    for entry in entries:
        if not entry.endswith(".kext"):
            continue
        path = join_path(directory, entry)
        if os.path.isdir(path) or os.path.islink(path):
            found.append(entry)
    found.sort()
    return found


def validate_exact_output_kext_set(output_dir, target):
    found = list_kext_bundle_names(output_dir, "cannot list patched output directory")
    expected = sorted([spec.bundle for spec in target.kexts])
    if found != expected:
        raise InstallerError(
            "patched output kext set does not match manifest target %s\n"
            "    found:    %s\n"
            "    expected: %s" %
            (target.key, ", ".join(found) if found else "none",
             ", ".join(expected))
        )


def validate_patched_bundle(output_dir, spec, target):
    bundle_path = join_path(output_dir, spec.bundle)
    if not os.path.exists(bundle_path):
        raise MissingPatchedOutputError("missing patched kext: %s" % bundle_path)
    if os.path.islink(bundle_path):
        raise InstallerError("patched kext must not be a symbolic link: %s" % bundle_path)
    if not os.path.isdir(bundle_path):
        raise InstallerError("patched kext is not a directory: %s" % bundle_path)

    info_path, binary_path, bundle_version, bundle_size = validate_kext_bundle_core(
        bundle_path, spec, target.expected_bundle_version,
        "patched bundle size does not match the tested %s build" % target.source_build,
    )

    binary_hash = sha256_file(binary_path)
    if binary_hash != spec.final_hash:
        raise InstallerError(
            "%s patched binary hash does not match the tested golden build\n"
            "    found:    %s\n"
            "    expected: %s" %
            (spec.bundle, binary_hash, spec.final_hash)
        )

    return {
        "bundle_path": bundle_path,
        "info_path": info_path,
        "binary_path": binary_path,
        "bundle_size": bundle_size,
        "version": bundle_version,
        "hash": binary_hash,
    }


def validate_all_patched(output_dir, target):
    validate_exact_output_kext_set(output_dir, target)
    section("patched kext check")
    prepared = []
    for spec in target.kexts:
        line()
        status(spec.bundle, COLORS.default, indent=1)
        result = validate_patched_bundle(output_dir, spec, target)
        detail("Version", result["version"], indent=2)
        detail("Bundle size", "%s bytes (%s)" %
               (result["bundle_size"], finder_size_text(result["bundle_size"])), indent=2)
        detail("SHA-256", result["hash"], indent=2)
        status("Patched kext matches the tested golden build.", COLORS.green,
               indent=2, symbol=OK)
        prepared.append((spec, result))
    return prepared


def command_exists(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def command_text(args):
    return " ".join(args)


def run_command(args, use_sudo=False, capture=True, allow_failure=False):
    cmd = list(args)
    if use_sudo and os.geteuid() != 0:
        cmd = ["/usr/bin/sudo"] + cmd

    try:
        if capture:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
        else:
            process = subprocess.Popen(cmd)
            process.wait()
            stdout, stderr = b"", b""
    except (IOError, OSError) as exc:
        raise CommandError("cannot execute command: %s\n    reason: %s" %
                           (command_text(cmd), exc))

    if process.returncode != 0 and not allow_failure:
        def decode(value):
            if not value:
                return ""
            if not isinstance(value, str):
                try:
                    value = value.decode("utf-8", "replace")
                except (AttributeError, UnicodeError):
                    value = str(value)
            return value.strip()

        out_text = decode(stdout)
        err_text = decode(stderr)
        message = ("command failed: %s\n    exit code: %s" %
                   (command_text(cmd), process.returncode))
        if err_text:
            message += "\n    stderr: %s" % err_text
        elif out_text:
            message += "\n    output: %s" % out_text
        raise CommandError(message)

    return process.returncode, stdout, stderr


def system_command_value(args):
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, _stderr = process.communicate()
        if process.returncode != 0:
            return None
        if not isinstance(stdout, str):
            stdout = stdout.decode("utf-8", "replace")
        return str(stdout.strip())
    except (IOError, OSError, UnicodeError):
        return None


def get_os_version():
    if not command_exists("/usr/bin/sw_vers"):
        return None
    return system_command_value(["/usr/bin/sw_vers", "-productVersion"])


def get_os_build():
    if not command_exists("/usr/bin/sw_vers"):
        return None
    return system_command_value(["/usr/bin/sw_vers", "-buildVersion"])


def get_machine_architecture():
    if not command_exists("/usr/bin/uname"):
        return None
    return system_command_value(["/usr/bin/uname", "-m"])


def validate_system_environment(target, dry_run):
    section("system check")
    os_version = get_os_version()
    os_build = get_os_build()
    version_matches = os_version == target.target_os_version
    build_matches = not target.target_build or os_build == target.target_build

    if version_matches and build_matches:
        display = target.display_name
        if target.target_build:
            display += " (%s)" % target.target_build
        detail("OS", display, indent=1)
        architecture = get_machine_architecture()
        detail("Kernel architecture", architecture if architecture else "unknown", indent=1)
        if architecture != "x86_64":
            raise InstallerError(
                "%s patch requires the x86_64 kernel, found %s" %
                (target.display_name, architecture if architecture else "unknown")
            )
        status("Target operating system verified.", COLORS.green, indent=1, symbol=OK)
        return True

    if dry_run:
        found_version = os_version if os_version else "unknown/non-macOS host"
        detail("Host OS", found_version, indent=1)
        if os_build:
            detail("Host build", os_build, indent=1)
        status("Non-target host detected; system kext hash verification will be "
               "skipped in this dry-run.", COLORS.light_red, indent=1)
        status("On %s, the dry-run performs the full system hash check." % target.display_name,
               COLORS.light_red, indent=1)
        return False

    found = os_version if os_version else "unknown"
    if target.target_build:
        found += " / %s" % (os_build if os_build else "unknown build")
    raise InstallerError("this patch targets %s, found %s" % (target.display_name, found))


def system_bundle_info(spec, target):
    bundle_path = join_path(config.SYSTEM_EXTENSIONS_DIR, spec.bundle)
    info_path = join_path(bundle_path, "Contents", "Info.plist")
    binary_path = join_path(bundle_path, "Contents", "MacOS", spec.executable)

    if not os.path.exists(bundle_path):
        raise InstallerError("installed system kext is missing: %s" % bundle_path)
    if os.path.islink(bundle_path):
        raise InstallerError("installed system kext must not be a symbolic link: %s" % bundle_path)
    if not os.path.isdir(bundle_path):
        raise InstallerError("installed system kext is not a directory: %s" % bundle_path)

    validate_regular_file(info_path, "system Info.plist")
    validate_regular_file(binary_path, "system kext binary")
    info = read_plist(info_path)
    if info.get("CFBundleIdentifier") != spec.bundle_id:
        raise InstallerError("%s installed system CFBundleIdentifier is unexpected: %s" %
                             (spec.bundle, info.get("CFBundleIdentifier")))
    if info.get("CFBundleExecutable") != spec.executable:
        raise InstallerError("%s installed system CFBundleExecutable is unexpected: %s" %
                             (spec.bundle, info.get("CFBundleExecutable")))

    version = str(info.get("CFBundleVersion"))
    binary_hash = sha256_file(binary_path)
    if binary_hash == spec.system_original_hash:
        state = "original"
        expected_size = spec.system_original_bundle_size
        expected_version = spec.system_original_version
    elif binary_hash == spec.final_hash:
        state = "patched"
        expected_size = spec.bundle_size
        expected_version = target.expected_bundle_version
    elif (target.key == "SL" and binary_hash == spec.source_hash and
          spec.source_hash != spec.final_hash):
        state = "lion_source"
        expected_size = spec.bundle_size
        expected_version = target.expected_bundle_version
    else:
        raise UnknownSystemKextError(
            "%s installed system binary does not match a known safe %s state\n"
            "    found:             %s\n"
            "    original expected: %s\n"
            "    patched expected:  %s" %
            (spec.bundle, target.key, binary_hash,
             spec.system_original_hash, spec.final_hash)
        )

    bundle_size = bundle_payload_size(bundle_path)
    if bundle_size != expected_size:
        raise InstallerError(
            "%s installed %s bundle has an unexpected size\n"
            "    found:    %s bytes\n"
            "    expected: %s bytes (%s)" %
            (spec.bundle, state, bundle_size, expected_size,
             finder_size_text(expected_size))
        )
    if version != expected_version:
        raise InstallerError(
            "%s installed %s CFBundleVersion is unexpected\n"
            "    found:    %s\n"
            "    expected: %s" %
            (spec.bundle, state, version, expected_version)
        )

    return {
        "bundle_path": bundle_path,
        "binary_path": binary_path,
        "version": version,
        "bundle_size": bundle_size,
        "hash": binary_hash,
        "state": state,
    }


def validate_installed_system_kexts(target):
    states = []
    results = []
    for spec in target.kexts:
        line()
        status(spec.bundle, COLORS.default, indent=1)
        result = system_bundle_info(spec, target)
        detail("Version", str(result["version"]), indent=2)
        detail("Current SHA-256", result["hash"], indent=2)
        if result["state"] == "original":
            status("Original %s binary verified." % target.display_name, COLORS.green,
                   indent=2, symbol=OK)
        elif result["state"] == "patched":
            status("Tested patched binary is already installed.", COLORS.yellow,
                   indent=2, symbol=OK)
        else:
            status("Known earlier Snow Leopard hybrid binary detected.", COLORS.light_red,
                   indent=2, symbol=OK)
        states.append(result["state"])
        results.append((spec, result))

    if all(state == "patched" for state in states):
        return "already_patched", results
    if all(state == "original" for state in states):
        return "original", results

    if target.key == "SL":
        state_by_bundle = {}
        for spec, result in results:
            state_by_bundle[spec.bundle] = result["state"]
        if (state_by_bundle.get("ATISupport.kext") == "patched" and
                state_by_bundle.get("ATIFramebuffer.kext") == "patched" and
                state_by_bundle.get("ATI5000Controller.kext") == "lion_source"):
            status("Known earlier Snow Leopard hybrid stack verified; "
                   "only the controller needs updating.",
                   COLORS.green, indent=1, symbol=OK)
            return "test3a2", results

    state_lines = []
    for spec, result in results:
        state_lines.append("    %s: %s" % (spec.bundle, result["state"]))
    raise MixedSystemStateError(
        "mixed original/patched ATI system stack detected\n" + "\n".join(state_lines)
    )


def expected_current_hashes(system_results):
    expected = {}
    if system_results:
        for spec, result in system_results:
            expected[spec.bundle] = result["hash"]
    return expected


def backup_manifest_key(spec, field_name):
    return "Kext-%s-%s" % (spec.bundle, field_name)


def create_backup_manifest(target, records):
    lines = [
        "HD5000 system kext backup manifest",
        "Manifest-Version: 1",
        "Target: %s" % target.key,
        "Target-OS: %s" % target.display_name,
        "Target-OS-Version: %s" % target.target_os_version,
        "Target-Build: %s" % (target.target_build if target.target_build else "not-fixed"),
        "Installer-Version: %s" % PROGRAM_VERSION,
        "Kext-Count: %s" % len(target.kexts),
        "Kexts: %s" % ",".join([spec.bundle for spec in target.kexts]),
    ]
    for spec in target.kexts:
        record = records[spec.bundle]
        lines.append("%s: %s" %
                     (backup_manifest_key(spec, "Bundle-Version"), record["version"]))
        lines.append("%s: %s" %
                     (backup_manifest_key(spec, "Bundle-Size"), record["bundle_size"]))
        lines.append("%s: %s" %
                     (backup_manifest_key(spec, "SHA-256"), record["hash"]))
    lines.append("")
    return "\n".join(lines)


def parse_backup_manifest(backup_dir, target):
    manifest_path = join_path(backup_dir, config.BACKUP_MANIFEST_NAME)
    values = parse_key_value_manifest(
        manifest_path, "HD5000 system kext backup manifest", "backup"
    )
    required = (
        "Manifest-Version", "Target", "Target-OS", "Target-OS-Version",
        "Target-Build", "Installer-Version", "Kext-Count", "Kexts",
    )
    for key in required:
        if key not in values:
            raise ManifestError("backup manifest is missing required key: %s" % key)
    if values["Manifest-Version"] != "1":
        raise ManifestError("unsupported backup manifest version: %s" %
                            values["Manifest-Version"])

    expected = {
        "Target": target.key,
        "Target-OS": target.display_name,
        "Target-OS-Version": target.target_os_version,
        "Target-Build": target.target_build if target.target_build else "not-fixed",
        "Installer-Version": PROGRAM_VERSION,
        "Kext-Count": str(len(target.kexts)),
        "Kexts": ",".join([spec.bundle for spec in target.kexts]),
    }
    for key, expected_value in expected.items():
        if values.get(key) != expected_value:
            raise ManifestError(
                "backup manifest %s mismatch\n"
                "    found:    %s\n"
                "    expected: %s" % (key, values.get(key), expected_value)
            )

    for spec in target.kexts:
        for field_name in ("Bundle-Version", "Bundle-Size", "SHA-256"):
            key = backup_manifest_key(spec, field_name)
            if key not in values:
                raise ManifestError("backup manifest is missing required key: %s" % key)
    return values, manifest_path


def validate_exact_backup_kext_set(backup_dir, target):
    found = list_kext_bundle_names(backup_dir, "cannot list backup directory")
    expected = sorted([spec.bundle for spec in target.kexts])
    if found != expected:
        raise InstallerError(
            "backup kext set does not match target %s\n"
            "    found:    %s\n"
            "    expected: %s" %
            (target.key, ", ".join(found) if found else "none", ", ".join(expected))
        )


def backup_bundle_metadata(bundle_path, spec):
    info_path = join_path(bundle_path, "Contents", "Info.plist")
    binary_path = join_path(bundle_path, "Contents", "MacOS", spec.executable)
    validate_regular_file(info_path, "backup Info.plist")
    validate_regular_file(binary_path, "backup kext binary")
    info = read_plist(info_path)
    if info.get("CFBundleIdentifier") != spec.bundle_id:
        raise InstallerError("%s backup CFBundleIdentifier is unexpected: %s" %
                             (spec.bundle, info.get("CFBundleIdentifier")))
    if info.get("CFBundleExecutable") != spec.executable:
        raise InstallerError("%s backup CFBundleExecutable is unexpected: %s" %
                             (spec.bundle, info.get("CFBundleExecutable")))
    return {
        "info_path": info_path,
        "binary_path": binary_path,
        "version": str(info.get("CFBundleVersion")),
        "bundle_size": bundle_payload_size(bundle_path),
        "hash": sha256_file(binary_path),
    }


def validate_backup_bundle(backup_dir, spec, manifest_values=None):
    bundle_path = join_path(backup_dir, spec.bundle)
    if not os.path.exists(bundle_path):
        raise InstallerError("missing backup kext: %s" % bundle_path)
    if os.path.islink(bundle_path):
        raise InstallerError("backup kext must not be a symbolic link: %s" % bundle_path)
    if not os.path.isdir(bundle_path):
        raise InstallerError("backup kext is not a directory: %s" % bundle_path)

    metadata = backup_bundle_metadata(bundle_path, spec)
    if manifest_values is not None:
        version_key = backup_manifest_key(spec, "Bundle-Version")
        size_key = backup_manifest_key(spec, "Bundle-Size")
        hash_key = backup_manifest_key(spec, "SHA-256")
        if manifest_values.get(version_key) != metadata["version"]:
            raise InstallerError(
                "%s backup version does not match its manifest\n"
                "    found:    %s\n"
                "    expected: %s" %
                (spec.bundle, metadata["version"], manifest_values.get(version_key))
            )
        try:
            manifest_size = int(manifest_values.get(size_key, ""))
        except (TypeError, ValueError):
            raise ManifestError(
                "backup manifest contains an invalid bundle size for %s" % spec.bundle
            )
        if metadata["bundle_size"] != manifest_size:
            raise InstallerError(
                "%s backup bundle size does not match its manifest\n"
                "    found:    %s bytes\n"
                "    expected: %s bytes" %
                (spec.bundle, metadata["bundle_size"], manifest_size)
            )
        if manifest_values.get(hash_key) != metadata["hash"]:
            raise InstallerError(
                "%s backup binary hash does not match its manifest\n"
                "    found:    %s\n"
                "    expected: %s" %
                (spec.bundle, metadata["hash"], manifest_values.get(hash_key))
            )

    metadata["bundle_path"] = bundle_path
    return metadata


def backup_state_label(state_name):
    if state_name == "original":
        return "original Apple system kext state"
    if state_name == "test3a2":
        return "known earlier Snow Leopard hybrid state"
    return "unknown state"


def identify_known_backup_state(prepared, target):
    by_bundle = {}
    for spec, result in prepared:
        by_bundle[spec.bundle] = result

    original_matches = True
    for spec in target.kexts:
        result = by_bundle.get(spec.bundle)
        if result is None:
            original_matches = False
            break
        if (result["hash"] != spec.system_original_hash or
                result["bundle_size"] != spec.system_original_bundle_size or
                result["version"] != spec.system_original_version):
            original_matches = False
            break
    if original_matches:
        return "original"

    if target.key == "SL":
        expected_hashes = {
            "ATISupport.kext": config.SNOW_LEOPARD_KEXTS[0].final_hash,
            "ATIFramebuffer.kext": config.SNOW_LEOPARD_KEXTS[1].final_hash,
            "ATI5000Controller.kext": config.SNOW_LEOPARD_KEXTS[2].source_hash,
        }
        test3a2_matches = True
        for spec in target.kexts:
            result = by_bundle.get(spec.bundle)
            if result is None:
                test3a2_matches = False
                break
            if (result["hash"] != expected_hashes.get(spec.bundle) or
                    result["bundle_size"] != spec.bundle_size or
                    result["version"] != target.expected_bundle_version):
                test3a2_matches = False
                break
        if test3a2_matches:
            return "test3a2"

    return None


def validate_backup_contents(backup_dir, target, show_output=False):
    if not os.path.exists(backup_dir):
        raise InstallerError("backup directory is missing: %s" % backup_dir)
    if os.path.islink(backup_dir):
        raise InstallerError("backup directory must not be a symbolic link: %s" % backup_dir)
    if not os.path.isdir(backup_dir):
        raise InstallerError("backup path is not a directory: %s" % backup_dir)

    manifest_path = join_path(backup_dir, config.BACKUP_MANIFEST_NAME)
    manifest_values = None
    if os.path.exists(manifest_path):
        manifest_values, manifest_path = parse_backup_manifest(backup_dir, target)
    else:
        manifest_path = None

    validate_exact_backup_kext_set(backup_dir, target)
    prepared = []
    if show_output:
        section("backup check")
        if manifest_path is not None:
            detail("Manifest", manifest_path, indent=1)
        else:
            status("BACKUP-MANIFEST.txt is missing.", COLORS.light_red,
                   indent=1, symbol=FAIL)
            status("Using independent recovery verification against known trusted states.",
                   COLORS.light_red, indent=1)

    for spec in target.kexts:
        result = validate_backup_bundle(backup_dir, spec, manifest_values)
        prepared.append((spec, result))
        if show_output:
            line()
            status(spec.bundle, COLORS.default, indent=1)
            detail("Version", result["version"], indent=2)
            detail("Bundle size", "%s bytes (%s)" %
                   (result["bundle_size"], finder_size_text(result["bundle_size"])),
                   indent=2)
            detail("SHA-256", result["hash"], indent=2)
            if manifest_path is not None:
                status("Backup kext and manifest verified.", COLORS.green,
                       indent=2, symbol=OK)
            else:
                status("Backup kext checked without a manifest.", COLORS.green,
                       indent=2, symbol=OK)

    backup_state = identify_known_backup_state(prepared, target)
    if backup_state is None:
        raise InstallerError(
            "backup cannot be matched to a complete known safe %s pre-install state" %
            target.key
        )

    if show_output:
        status("Backup matches the %s." % backup_state_label(backup_state),
               COLORS.green, indent=1, symbol=OK)
        if manifest_path is None:
            status("Manifest-less recovery is safe because all kext metadata, sizes and "
                   "SHA-256 hashes match a built-in trusted state.",
                   COLORS.green, indent=1, symbol=OK)
    return prepared, manifest_path, backup_state


def validate_backup_dir(backup_dir, system_results, target):
    expected = expected_current_hashes(system_results)
    if not expected:
        return False
    try:
        prepared, _manifest_path, _backup_state = validate_backup_contents(
            backup_dir, target, False
        )
    except InstallerError:
        return False
    for spec, result in prepared:
        if result["hash"] != expected.get(spec.bundle):
            return False
    return True


def collect_backup_record(bundle_path, spec, expected_hash):
    metadata = backup_bundle_metadata(bundle_path, spec)
    if metadata["hash"] != expected_hash:
        raise InstallerError(
            "backup verification failed for %s\n"
            "    found:    %s\n"
            "    expected: %s" % (spec.bundle, metadata["hash"], expected_hash)
        )
    return {
        "version": metadata["version"],
        "bundle_size": metadata["bundle_size"],
        "hash": metadata["hash"],
    }


def create_verified_backup(backup_dir, target, dry_run, system_results=None):
    section("backup")
    if os.path.lexists(backup_dir):
        if system_results:
            if validate_backup_dir(backup_dir, system_results, target):
                status("Existing pre-install system backup is complete and verified.",
                       COLORS.green, indent=1, symbol=OK)
                detail("Path", backup_dir, indent=2)
                return
            raise InstallerError(
                "existing backup directory is incomplete, invalid or from a different "
                "system state: %s" % backup_dir
            )
        if dry_run:
            try:
                _prepared, _manifest_path, backup_state = validate_backup_contents(
                    backup_dir, target, False
                )
            except InstallerError as exc:
                raise InstallerError(
                    "existing backup directory cannot be independently verified on this "
                    "non-target dry-run host: %s\n    reason: %s" %
                    (backup_dir, str(exc).splitlines()[0])
                )
            status("Existing target backup is complete and independently verified.",
                   COLORS.green, indent=1, symbol=OK)
            detail("Path", backup_dir, indent=2)
            detail("Backup state", backup_state_label(backup_state), indent=2)
            status("Current-system comparison is skipped on this non-target dry-run host.",
                   COLORS.light_red, indent=1)
            return
        raise InstallerError(
            "internal error: current system state is unavailable while validating "
            "an existing backup"
        )

    if dry_run:
        count = len(target.kexts)
        status("Would create a verified backup of the current %s ATI system kext%s." %
               (count, "" if count == 1 else "s"), COLORS.yellow, indent=1)
        status("Would write %s with exact backup hashes and bundle metadata." %
               config.BACKUP_MANIFEST_NAME, COLORS.yellow, indent=1)
        detail("Path", backup_dir, indent=2)
        return

    expected = expected_current_hashes(system_results)
    if len(expected) != len(target.kexts):
        raise InstallerError(
            "internal error: current system hashes are unavailable for backup verification"
        )

    parent = os.path.dirname(backup_dir)
    if not os.path.isdir(parent):
        raise InstallerError("backup parent directory does not exist: %s" % parent)
    if not os.access(parent, os.W_OK):
        raise InstallerError("backup parent directory is not writable: %s" % parent)

    temp_backup = backup_dir + ".tmp-%s" % os.getpid()
    if os.path.lexists(temp_backup):
        raise InstallerError("temporary backup path already exists: %s" % temp_backup)

    try:
        os.mkdir(temp_backup)
        records = {}
        for spec in target.kexts:
            source = join_path(config.SYSTEM_EXTENSIONS_DIR, spec.bundle)
            target_path = join_path(temp_backup, spec.bundle)
            status("Backing up %s." % spec.bundle, COLORS.default, indent=2)
            if command_exists("/usr/bin/ditto"):
                run_command(["/usr/bin/ditto", source, target_path], capture=True)
            else:
                # noinspection PyTypeChecker
                shutil.copytree(source, target_path, symlinks=True)
            records[spec.bundle] = collect_backup_record(
                target_path, spec, expected[spec.bundle]
            )

        manifest_path = join_path(temp_backup, config.BACKUP_MANIFEST_NAME)
        write_ascii(manifest_path, create_backup_manifest(target, records))
        validate_backup_contents(temp_backup, target, False)
        os.rename(temp_backup, backup_dir)
        status("Pre-install system backup created and verified.", COLORS.green,
               indent=1, symbol=OK)
        detail("Path", backup_dir, indent=2)
        detail("Manifest", join_path(backup_dir, config.BACKUP_MANIFEST_NAME), indent=2)
    # noinspection PyBroadException
    except (Exception, KeyboardInterrupt):
        if os.path.exists(temp_backup):
            try:
                shutil.rmtree(temp_backup)
            except (IOError, OSError, shutil.Error):
                pass
        raise


def ensure_required_commands():
    commands = [
        "/usr/bin/sudo",
        "/usr/bin/ditto",
        "/usr/sbin/chown",
        "/bin/chmod",
        "/bin/mv",
        "/bin/rm",
        "/usr/bin/touch",
        "/usr/sbin/kextcache",
    ]
    missing = [path for path in commands if not command_exists(path)]
    if missing:
        raise InstallerError("required system command is missing: %s" % missing[0])


def obtain_admin_privileges(dry_run):
    if dry_run or os.geteuid() == 0:
        return
    section("administrator access")
    status("Administrator privileges are required to replace system kexts.", COLORS.light_red)
    status("OS X may ask for your administrator password.", COLORS.light_red)
    rc, _out, _err = run_command(["/usr/bin/sudo", "-v"], capture=False, allow_failure=True)
    if rc != 0:
        raise InstallerError("administrator authentication failed")
    status("Administrator access validated.", COLORS.green, indent=1, symbol=OK)


def temp_paths(spec):
    target_path = join_path(config.SYSTEM_EXTENSIONS_DIR, spec.bundle)
    stage = join_path(config.SYSTEM_EXTENSIONS_DIR,
                         ".%s.hd5000-stage" % spec.bundle)
    original = join_path(config.SYSTEM_EXTENSIONS_DIR,
                            ".%s.hd5000-original" % spec.bundle)
    return target_path, stage, original


def ensure_no_leftovers(target):
    for spec in target.kexts:
        _target_path, stage, original = temp_paths(spec)
        if os.path.lexists(stage):
            raise InstallerError("leftover staging path exists from an earlier run: %s" % stage)
        if os.path.lexists(original):
            raise InstallerError("leftover original path exists from an earlier run: %s" % original)


def cleanup_stage_paths(target, allow_failure=True):
    for spec in target.kexts:
        _target_path, stage, _original = temp_paths(spec)
        if os.path.lexists(stage):
            run_command(["/bin/rm", "-rf", stage], use_sudo=True,
                        capture=True, allow_failure=allow_failure)


def verify_staged_bundle(stage_path, spec, expected_hash, expected_size, expected_version):
    _info_path, binary, _version = validate_kext_identity(
        stage_path, spec, expected_version, InstallerError
    )
    binary_hash = sha256_file(binary)
    if binary_hash != expected_hash:
        raise InstallerError(
            "%s staged binary verification failed\n"
            "    found:    %s\n"
            "    expected: %s" % (spec.bundle, binary_hash, expected_hash)
        )
    bundle_size = bundle_payload_size(stage_path)
    if bundle_size != expected_size:
        raise InstallerError(
            "%s staged bundle size verification failed\n"
            "    found:    %s bytes\n"
            "    expected: %s bytes" % (spec.bundle, bundle_size, expected_size)
        )


def stage_bundles(prepared, target, dry_run, restore=False):
    section("staging")
    source_label = "backup" if restore else "patched"
    if dry_run:
        for spec, result in prepared:
            _target_path, stage, _original = temp_paths(spec)
            line()
            status(spec.bundle, COLORS.default, indent=1)
            detail("Would stage", stage, indent=2)
            detail("Source", result["bundle_path"], indent=2)
            status("Would set root:wheel ownership and safe permissions.", COLORS.yellow,
                   indent=2)
            status("Would revalidate %s bundle metadata, SHA-256 and size." % source_label,
                   COLORS.yellow, indent=2)
        return

    ensure_no_leftovers(target)
    try:
        for spec, result in prepared:
            _target_path, stage, _original = temp_paths(spec)
            line()
            status(spec.bundle, COLORS.default, indent=1)
            run_command(["/usr/bin/ditto", result["bundle_path"], stage],
                        use_sudo=True, capture=True)
            run_command(["/usr/sbin/chown", "-R", "root:wheel", stage],
                        use_sudo=True, capture=True)
            run_command(["/bin/chmod", "-R", "go-w", stage],
                        use_sudo=True, capture=True)
            if command_exists("/usr/bin/xattr"):
                run_command(["/usr/bin/xattr", "-dr", "com.apple.quarantine", stage],
                            use_sudo=True, capture=True, allow_failure=True)
            verify_staged_bundle(
                stage, spec, result["hash"], result["bundle_size"], result["version"]
            )
            status("Staged %s bundle verified." % source_label,
                   COLORS.green, indent=2, symbol=OK)
    # noinspection PyBroadException
    except (Exception, KeyboardInterrupt):
        cleanup_stage_paths(target, allow_failure=True)
        raise


def newest_kernel_cache(target):
    startup_dir = config.KEXT_CACHE_STARTUP_DIR
    if not os.path.isdir(startup_dir):
        raise InstallerError("kernel cache directory is missing: %s" % startup_dir)

    candidates = []
    try:
        names = os.listdir(startup_dir)
    except OSError as exc:
        raise InstallerError("cannot read kernel cache directory: %s" % exc)

    for name in names:
        if target.key == "LION":
            accepted = name == config.LION_KERNEL_CACHE_NAME
        else:
            accepted = name.startswith(config.SNOW_LEOPARD_KERNEL_CACHE_PREFIX)
            if accepted:
                suffix = name[len(config.SNOW_LEOPARD_KERNEL_CACHE_PREFIX):]
                accepted = bool(suffix) and "." not in suffix
        if not accepted:
            continue
        path = join_path(startup_dir, name)
        if os.path.isfile(path) and not os.path.islink(path) and os.path.getsize(path) > 0:
            candidates.append(path)

    if not candidates:
        raise InstallerError("no target kernelcache file was created in %s" % startup_dir)
    return max(candidates, key=lambda item: os.stat(item).st_mtime)


def verify_cache_results(target):
    try:
        extensions_mtime = os.stat(config.SYSTEM_EXTENSIONS_DIR).st_mtime
    except OSError as exc:
        raise InstallerError("cannot read system extensions timestamp: %s" % exc)

    kernel_cache = newest_kernel_cache(target)
    try:
        kernel_mtime = os.stat(kernel_cache).st_mtime
    except OSError as exc:
        raise InstallerError("cannot read kernel cache timestamp: %s" % exc)
    if kernel_mtime < extensions_mtime:
        raise InstallerError(
            "kernel cache is older than /System/Library/Extensions after rebuild\n"
            "    kernel cache: %s" % kernel_cache
        )

    verified = [("Kernel cache", kernel_cache)]
    if target.key == "SL":
        mkext_path = join_path(config.KEXT_CACHE_STARTUP_DIR,
                                  config.SNOW_LEOPARD_MKEXT_NAME)
        if not os.path.isfile(mkext_path) or os.path.islink(mkext_path):
            raise InstallerError("Snow Leopard mkext cache is missing: %s" % mkext_path)
        if os.path.getsize(mkext_path) <= 0:
            raise InstallerError("Snow Leopard mkext cache is empty: %s" % mkext_path)
        verified.append(("Extensions.mkext", mkext_path))
    return verified


def rebuild_caches(target):
    run_command(["/usr/bin/touch", config.SYSTEM_EXTENSIONS_DIR],
                use_sudo=True, capture=True)
    run_command(["/usr/sbin/kextcache", "-system-prelinked-kernel"],
                use_sudo=True, capture=True)
    run_command(["/usr/sbin/kextcache", "-system-caches"],
                use_sudo=True, capture=True)
    if command_exists("/bin/sync"):
        run_command(["/bin/sync"], use_sudo=True, capture=True)
    return verify_cache_results(target)


def perform_operation(prepared, target, dry_run, restore=False):
    section("restore" if restore else "installation")
    if dry_run:
        for spec, _result in prepared:
            target_path, stage, _original = temp_paths(spec)
            line()
            status(spec.bundle, COLORS.default, indent=1)
            detail("Would restore" if restore else "Would replace", target_path, indent=2)
            detail("Verified staged bundle", stage, indent=2)
        line()
        status("Would rebuild the prelinked kernel and system kext caches.",
               COLORS.yellow, indent=1)
        status("Would verify the kernel cache and required cache files.",
               COLORS.yellow, indent=1)
        return

    for spec, result in prepared:
        target_path, stage, _original = temp_paths(spec)
        line()
        status(spec.bundle, COLORS.default, indent=1)
        run_command(["/bin/rm", "-rf", target_path], use_sudo=True, capture=True)
        run_command(["/bin/mv", stage, target_path], use_sudo=True, capture=True)
        verify_staged_bundle(
            target_path, spec, result["hash"], result["bundle_size"],
            result["version"]
        )
        status("Restored bundle verified." if restore else "Installed bundle verified.",
               COLORS.green, indent=2, symbol=OK)

    section("cache rebuild")
    status("Rebuilding kernel extension caches.", COLORS.cyan, indent=1)
    verified_caches = rebuild_caches(target)
    status("Kext caches rebuilt and verified.", COLORS.green,
           indent=1, symbol=OK)
    for label, path in verified_caches:
        detail(label, path, indent=2)


def print_install_plan(backup_dir, target, dry_run, install_prepared):
    section("install plan")
    detail("Patch target", target.display_name, indent=1)
    detail("System extensions", config.SYSTEM_EXTENSIONS_DIR, indent=1)
    detail("Backup location", backup_dir, indent=1)
    if dry_run:
        status("Dry-run active, no files will be written or moved.", COLORS.yellow,
               indent=1)
    else:
        count = len(install_prepared)
        status("%s ATI kext%s will be replaced after backup and staging verification." %
               (count, "" if count == 1 else "s"), COLORS.light_red, indent=1)


def print_restore_plan(backup_dir, target, dry_run, restore_prepared):
    section("restore plan")
    detail("Patch target", target.display_name, indent=1)
    detail("System extensions", config.SYSTEM_EXTENSIONS_DIR, indent=1)
    detail("Backup", backup_dir, indent=1)
    if dry_run:
        status("Restore dry-run active, no files will be written or moved.",
               COLORS.yellow, indent=1)
    else:
        count = len(restore_prepared)
        status("%s ATI kext%s will be restored after staging verification." %
               (count, "" if count == 1 else "s"), COLORS.light_red, indent=1)


def confirm_real_restore(restore_prepared, target):
    section("restore confirmation")
    count = len(restore_prepared)
    line("  Target: %s" % target.display_name)
    line("  %s verified backup kext%s will now be restored." %
         (count, "" if count == 1 else "s"))
    line("  The verified backup remains available for explicit recovery with --restore.")
    line()
    return prompt_enter_or_quit("Press Enter to restore or Q to quit… ")


def target_hint_from_output(output_dir):
    """Read only a non-authoritative target hint for the early UI header."""
    manifest_path = join_path(output_dir, config.MANIFEST_NAME)
    try:
        handle = open(manifest_path, "rb")
        try:
            data = handle.read()
        finally:
            handle.close()
    except (IOError, OSError):
        return None

    if not isinstance(data, str):
        try:
            data = data.decode("ascii")
        except (AttributeError, UnicodeDecodeError):
            return None

    for manifest_line in data.splitlines():
        if not manifest_line.startswith("Target:"):
            continue
        value = manifest_line.split(":", 1)[1].strip()
        return config.get_target(value)
    return None


def restore_target_hint(script_dir):
    """Return a target hint only when exactly one backup directory exists."""
    found = []
    for target in config.TARGETS:
        path = join_path(script_dir, target.backup_dir_name)
        if os.path.lexists(path):
            found.append(target)
    if len(found) == 1:
        return found[0]
    return None


def select_restore_target(script_dir):
    available = []
    for target in config.TARGETS:
        path = join_path(script_dir, target.backup_dir_name)
        if os.path.lexists(path):
            available.append((target, path))

    if not available:
        raise InstallerError(
            "no pre-install backup directory was found next to the installer"
        )
    if len(available) == 1:
        return available[0]

    line()
    status("Both Snow Leopard and Lion backup directories are present.",
           COLORS.light_red, indent=1)
    while True:
        prompt = (
            COLORS.default + "Please input backup target, " +
            COLORS.light_magenta + "SL" + COLORS.default + " or " +
            COLORS.light_magenta + "Lion" + COLORS.default +
            ", or Q to quit: "
        )
        try:
            answer = read_console_line(prompt)
        except EOFError:
            return None, None
        if answer.strip().lower() == "q":
            return None, None
        selected = config.get_target(answer)
        if selected is not None:
            for target, path in available:
                if target.key == selected.key:
                    return target, path


def parse_installer_args(argv):
    restore_count = argv[1:].count("--restore")
    if restore_count > 1:
        raise InstallerError("option specified more than once: --restore")
    restore = restore_count == 1
    filtered = [argv[0]]
    for arg in argv[1:]:
        if arg != "--restore":
            filtered.append(arg)
    dry_run, no_color, show_help, show_version = parse_args(filtered)
    return dry_run, no_color, show_help, show_version, restore


def restore_completion_text():
    line()
    line("Restore completed successfully.")
    line("Please restart the system now.")
    line()
    line("For details about backup and restore behavior, please read %s." %
         config.README_NAME)
    line()
    line("All done, goodbye.")
    line()


def show_existing_backup_status(backup_dir, target):
    line()
    if not os.path.lexists(backup_dir):
        status("No verified pre-install backup was found next to the installer.",
               COLORS.light_red, indent=1, symbol=FAIL)
        detail("Expected backup", backup_dir, indent=2)
        status("Restore is not available from this package directory.",
               COLORS.light_red, indent=1)
        line()
        line("If you saved the original kexts elsewhere, keep them on external storage.")
        line("See %s for manual recovery instructions." % config.README_NAME)
        return False

    try:
        _prepared, manifest_path, backup_state = validate_backup_contents(
            backup_dir, target, False
        )
    except InstallerError as exc:
        status("A backup directory exists, but it could not be verified.",
               COLORS.red, indent=1, symbol=FAIL)
        detail("Backup", backup_dir, indent=2)
        detail("Reason", str(exc).splitlines()[0], indent=2, color=COLORS.red)
        status("Restore is not available until the backup is repaired or replaced.",
               COLORS.light_red, indent=1)
        line()
        line("See %s for backup and manual recovery instructions." % config.README_NAME)
        return False

    status("Verified pre-install backup is available for restore.",
           COLORS.green, indent=1, symbol=OK)
    detail("Backup state", backup_state_label(backup_state), indent=2)
    if manifest_path is None:
        status("BACKUP-MANIFEST.txt is missing; trusted-state verification succeeded.",
               COLORS.light_red, indent=2)
    install_restore_hint(backup_dir)
    return True


def install_restore_hint(backup_dir):
    line()
    line("To restore this verified pre-install backup later, run:")
    print("  " + COLORS.light_magenta +
          "python %s --restore" % config.INSTALLER_SCRIPT_NAME + COLORS.default)
    detail("Backup", backup_dir, indent=1)
    line()
    line("Keep an external copy of this backup directory.")
    line("Please read %s before using restore." % config.README_NAME)


def print_manual_recovery_help(target):
    section("manual recovery")
    status("Restore was stopped before system changes because the backup or current "
           "system could not be accepted as a complete known safe state.",
           COLORS.light_red, indent=1, symbol=FAIL)
    line()
    line("If you still have known original kexts saved elsewhere, you can recover")
    line("manually. First preserve the currently installed ATI kexts:")
    print('  /bin/mkdir -p "$HOME/Desktop/ATI-Kext-Manual-Backup"')
    for spec in target.kexts:
        source = "%s/%s" % (config.SYSTEM_EXTENSIONS_DIR, spec.bundle)
        destination = "$HOME/Desktop/ATI-Kext-Manual-Backup/%s" % spec.bundle
        print('  /usr/bin/ditto "%s" "%s"' % (source, destination))
    line()
    line("Then, only if your saved kexts are known originals for this target,")
    line("replace /path/to/original below with the directory that contains them:")
    for spec in target.kexts:
        target_path = "%s/%s" % (config.SYSTEM_EXTENSIONS_DIR, spec.bundle)
        source_path = "/path/to/original/%s" % spec.bundle
        print('  sudo /bin/rm -rf "%s"' % target_path)
        print('  sudo /usr/bin/ditto "%s" "%s"' % (source_path, target_path))
        print('  sudo /usr/sbin/chown -R root:wheel "%s"' % target_path)
        print('  sudo /bin/chmod -R go-w "%s"' % target_path)
    print('  sudo /usr/bin/touch "%s"' % config.SYSTEM_EXTENSIONS_DIR)
    print("  sudo /usr/sbin/kextcache -system-prelinked-kernel")
    print("  sudo /usr/sbin/kextcache -system-caches")
    line()
    line("Do not mix Snow Leopard and Lion kexts. Keep the manual backup and any")
    line("verified installer backup on external storage before further changes.")
    line("See the Manual recovery section in %s for details." % config.README_NAME)


def quit_before_system_changes():
    line()
    status("Quit by user.", COLORS.yellow, indent=1)
    status("No system kexts were modified.", COLORS.yellow, indent=1)
    exit_status(indent=2)
    line()
    return 0


def confirm_real_install(install_prepared, target):
    section("installation confirmation")
    count = len(install_prepared)
    line("  Target: %s" % target.display_name)
    line("  %s verified ATI kext%s will now be installed." %
         (count, "" if count == 1 else "s"))
    line("  A verified backup is created before the first system kext is changed.")
    line()
    return prompt_enter_or_quit("Press Enter to install or Q to quit… ")


def print_installer_help(program):
    line("Usage: %s [options]" % program)
    line()
    line("Options:")
    line("  --dry-run    validate and simulate without changing the system")
    line("  --restore    restore the verified pre-install system kext backup")
    line("  --no-color   disable ANSI colors")
    line("  --version    show installer version")
    line("  -h, --help   show this help")


def validate_restore_system_state(system_state, system_results, backup_prepared):
    changed = select_changed_bundles(backup_prepared, system_results)
    if not changed:
        return "already_restored", changed
    if system_state != "already_patched":
        raise MixedSystemStateError(
            "current ATI system state is known, but it does not match this backup and "
            "is not the tested patched state expected before restore"
        )
    return "restore_allowed", changed


def select_changed_bundles(prepared, system_results):
    if not system_results:
        return list(prepared)
    current_by_bundle = {}
    for spec, result in system_results:
        current_by_bundle[spec.bundle] = result["hash"]
    changed = []
    for spec, result in prepared:
        if current_by_bundle.get(spec.bundle) != result["hash"]:
            changed.append((spec, result))
    return changed


# noinspection DuplicatedCode
def main(argv):
    set_color_enabled(terminal_supports_color("--no-color" in argv[1:]))

    try:
        dry_run, no_color, show_help, show_version, restore = parse_installer_args(argv)
    except InstallerError as exc:
        print_installer_header(None, restore="--restore" in argv[1:])
        error_status(exc, indent=1)
        line(COLORS.default + "  Try --help." + COLORS.default)
        exit_status(indent=2)
        line()
        return 2

    set_color_enabled(terminal_supports_color(no_color))

    if show_help:
        print_installer_help(os.path.basename(argv[0]))
        return 0

    if show_version:
        line("%s %s" % (PROGRAM_NAME, PROGRAM_VERSION))
        return 0

    system_modified = False
    staged_paths_owned = False
    target = None

    try:
        if sys.version_info < (2, 6):
            raise InstallerError("Python 2.6 or newer is required")

        script_dir = resolve_script_directory(__file__)

        if restore:
            print_installer_header(restore_target_hint(script_dir), restore=True)
            target, backup_dir = select_restore_target(script_dir)
            if target is None:
                line()
                status("Quit by user.", COLORS.yellow, indent=1)
                exit_status(indent=2)
                line()
                return 0

            if not print_intro(script_dir, target, dry_run, restore=True):
                line()
                status("Quit by user.", COLORS.yellow, indent=1)
                exit_status(indent=2)
                line()
                return 0

            backup_prepared, backup_manifest_path, backup_state = validate_backup_contents(
                backup_dir, target, True
            )
            status("Verified backup is eligible for restore.", COLORS.green,
                   indent=1, symbol=OK)
            detail("Backup state", backup_state_label(backup_state), indent=2)
            if backup_manifest_path is not None:
                detail("Backup manifest", backup_manifest_path, indent=2)
            else:
                status("Restore will continue without BACKUP-MANIFEST.txt.",
                       COLORS.light_red, indent=2)

            target_host = validate_system_environment(target, dry_run)
            if target_host:
                system_state, system_results = validate_installed_system_kexts(target)
                restore_state, restore_prepared = validate_restore_system_state(
                    system_state, system_results, backup_prepared
                )
                if restore_state == "already_restored":
                    section("done")
                    status("The current system already matches the verified backup.",
                           COLORS.green, indent=1, symbol=OK)
                    status("The backup may already have been restored manually.",
                           COLORS.cyan, indent=1)
                    status("No system changes are required.", COLORS.cyan, indent=1)
                    line()
                    line("For details about backup and restore behavior, please read %s." %
                         config.README_NAME)
                    line()
                    line("All done, goodbye.")
                    line()
                    return 0
            else:
                section("system kext hashes")
                status("System hash check skipped on this non-target restore dry-run host.",
                       COLORS.light_red, indent=1)
                status("On %s, restore dry-run verifies the current system hashes too." %
                       target.display_name, COLORS.light_red, indent=1)
                restore_prepared = list(backup_prepared)

            print_restore_plan(backup_dir, target, dry_run, restore_prepared)

            if dry_run:
                stage_bundles(restore_prepared, target, True, restore=True)
                perform_operation(restore_prepared, target, True, restore=True)
                section("done")
                status("All available restore checks passed.", COLORS.green,
                       indent=1, symbol=OK)
                status("Restore dry-run finished, no system kexts were modified.",
                       COLORS.yellow, indent=1)
                line()
                line("For restore instructions, please read %s." % config.README_NAME)
                line()
                line("All done, goodbye.")
                line()
                return 0

            ensure_required_commands()
            ensure_no_leftovers(target)
            if not confirm_real_restore(restore_prepared, target):
                return quit_before_system_changes()

            obtain_admin_privileges(False)
            stage_bundles(restore_prepared, target, False, restore=True)
            staged_paths_owned = True
            system_modified = True
            perform_operation(restore_prepared, target, False, restore=True)
            staged_paths_owned = False
            system_modified = False

            section("done")
            status("Verified pre-install backup restored successfully.", COLORS.green,
                   indent=1, symbol=OK)
            status("Kernel extension caches have been rebuilt successfully.", COLORS.green,
                   indent=1, symbol=OK)
            detail("Restored from", backup_dir, indent=2)
            restore_completion_text()
            return 0

        output_dir = join_path(script_dir, config.OUTPUT_DIR_NAME)
        print_installer_header(target_hint_from_output(output_dir), restore=False)
        ensure_patched_output_dir(output_dir)
        target, manifest_path = parse_manifest(output_dir)

        if not print_intro(script_dir, target, dry_run, restore=False):
            line()
            status("Quit by user.", COLORS.yellow, indent=1)
            exit_status(indent=2)
            line()
            return 0

        section("patch manifest")
        detail("Path", manifest_path, indent=1)
        detail("Target", target.key, indent=1)
        status("Patch manifest matches this installer and target profile.",
               COLORS.green, indent=1, symbol=OK)

        prepared = validate_all_patched(output_dir, target)
        backup_dir = join_path(script_dir, target.backup_dir_name)

        target_host = validate_system_environment(target, dry_run)
        if target_host:
            system_state, system_results = validate_installed_system_kexts(target)
            if system_state == "already_patched":
                section("done")
                count = len(target.kexts)
                if count == 1:
                    already_text = "The tested patched kext is already installed."
                else:
                    already_text = "All %s tested patched kexts are already installed." % count
                status(already_text, COLORS.green, indent=1, symbol=OK)
                status("No system changes are required.", COLORS.cyan, indent=1)
                show_existing_backup_status(backup_dir, target)
                line()
                line("All done, goodbye.")
                line()
                return 0
        else:
            system_results = None
            section("system kext hashes")
            status("System hash check skipped on this non-target dry-run host.",
                   COLORS.light_red, indent=1)
            for spec in target.kexts:
                line()
                status(spec.bundle, COLORS.default, indent=1)
                detail("Expected original SHA-256", spec.system_original_hash, indent=2)

        install_prepared = select_changed_bundles(prepared, system_results)
        print_install_plan(backup_dir, target, dry_run, install_prepared)

        if dry_run:
            create_verified_backup(backup_dir, target, True, system_results)
            stage_bundles(install_prepared, target, True, restore=False)
            perform_operation(install_prepared, target, True, restore=False)
            section("done")
            status("All available checks passed.", COLORS.green, indent=1, symbol=OK)
            status("Dry-run finished, no system kexts were modified.", COLORS.yellow,
                   indent=1)
            line()
            line("A real install creates the backup used by --restore.")
            line("Please read %s for backup and restore instructions." % config.README_NAME)
            line()
            line("All done, goodbye.")
            line()
            return 0

        ensure_required_commands()
        ensure_no_leftovers(target)
        if not confirm_real_install(install_prepared, target):
            return quit_before_system_changes()

        obtain_admin_privileges(False)
        create_verified_backup(backup_dir, target, False, system_results)
        stage_bundles(install_prepared, target, False, restore=False)
        staged_paths_owned = True
        system_modified = True
        perform_operation(install_prepared, target, False, restore=False)
        staged_paths_owned = False
        system_modified = False

        section("done")
        status("All patched kexts have been installed and verified.", COLORS.green,
               indent=1, symbol=OK)
        status("Kernel extension caches have been rebuilt successfully.", COLORS.green,
               indent=1, symbol=OK)
        detail("System backup", backup_dir, indent=2)
        install_restore_hint(backup_dir)
        line()
        line("Please restart the system now.")
        line()
        line("All done, goodbye.")
        line()
        return 0

    except MissingPatchedOutputError as exc:
        error_status(exc, indent=2)
        patched_output_hint(indent=3)
        status("No system kexts were modified.", COLORS.yellow, indent=2)
        exit_status(indent=3)
        line()
        return 1
    except KeyboardInterrupt:
        line()
        status("Interrupted by user.", COLORS.yellow, indent=2, symbol=FAIL)
        if staged_paths_owned and target is not None:
            cleanup_stage_paths(target, allow_failure=True)
        if not system_modified:
            status("No system kexts were modified.", COLORS.yellow, indent=2)
        else:
            status("The installer was interrupted during a system operation.", COLORS.red,
                   indent=2, symbol=FAIL)
            status("System kexts may already have been modified.",
                   COLORS.light_red, indent=2)
            status("Repair caches or restore the verified backup before rebooting.",
                   COLORS.light_red, indent=2)
        exit_status(indent=3)
        line()
        return 130
    except InstallerError as exc:
        if staged_paths_owned and target is not None:
            cleanup_stage_paths(target, allow_failure=True)
        error_status(exc, indent=2)
        if not system_modified:
            status("No system kexts were modified.", COLORS.yellow, indent=2)
            if target is not None and (restore or isinstance(
                    exc, (UnknownSystemKextError, MixedSystemStateError))):
                print_manual_recovery_help(target)
        else:
            status("System kexts may already have been modified.",
                   COLORS.light_red, indent=2)
            status("Repair caches or restore the verified backup before rebooting.",
                   COLORS.light_red, indent=2)
        exit_status(indent=3)
        line()
        return 1
    # Last-resort safety net for unexpected installer failures.
    # noinspection PyBroadException
    except Exception as exc:
        if staged_paths_owned and target is not None:
            cleanup_stage_paths(target, allow_failure=True)
        error_status(exc, unexpected=True, indent=2)
        if not system_modified:
            status("No system kexts were modified.", COLORS.yellow, indent=2)
        else:
            status("An unexpected error occurred during a system operation.", COLORS.red,
                   indent=2, symbol=FAIL)
        exit_status(indent=3)
        line()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
