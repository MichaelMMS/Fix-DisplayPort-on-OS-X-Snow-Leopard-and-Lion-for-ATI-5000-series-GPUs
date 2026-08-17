#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Build the tested ATI HD 5000 DisplayPort patch for Snow Leopard or Lion.

Designed for Python 2.6 and later 2.x releases. The code also stays usable on
modern Python 3 so the patch logic can be validated on another Mac if needed.

The patcher never reads from or writes to /System/Library/Extensions. The user
manually places the required original kext bundle(s) in YourKextSource/ and
explicitly selects either the Snow Leopard or Lion target.
"""

from __future__ import print_function

import os
import shutil
import sys
import tempfile

# The mixed-case internal module name is retained intentionally.
# noinspection PyPep8Naming
from _baselib import _baseRuntimeData as config
from _baselib._functions import (
    COLORS, FAIL, OK, detail, error_status,
    exit_status, line, parse_args, print_basic_help, print_program_header, read_binary,
    read_console_line, read_plist, script_directory as resolve_script_directory,
    section, set_color_enabled, set_error_type, sha256_data, sha256_file, status,
    terminal_supports_color, validate_kext_bundle_core, validate_regular_file,
    write_ascii, write_binary, write_utf8,
)


PROGRAM_NAME = "ATI HD 5000 Snow Leopard and Lion DisplayPort patcher"
PROGRAM_VERSION = config.PACKAGE_VERSION
TITLE = "| DisplayPort fix for OS X Snow Leopard 10.6.8 and OS X Lion 10.7.5 |"


class PatcherError(Exception):
    pass


class BundleSizeError(PatcherError):
    pass


set_error_type(PatcherError)


def prompt_target():
    while True:
        prompt = (
            COLORS.default + "Please input target, " +
            COLORS.light_magenta + "SL" + COLORS.default + " or " +
            COLORS.light_magenta + "Lion" + COLORS.default +
            ", or Q to quit: "
        )
        try:
            answer = read_console_line(prompt)
        except EOFError:
            return None
        answer = answer.strip()
        if answer.lower() == "q":
            return None
        target = config.get_target(answer)
        if target is not None:
            return target


def pacifist_size_hint(indent=3):
    prefix = "  " * indent
    print(prefix + COLORS.light_red +
          "If you've extracted the kexts from the installer DMG using Pacifist," +
          COLORS.default)
    print(prefix + COLORS.light_red +
          "make sure to extract the one with the correct file size." +
          COLORS.default)
    print(prefix + COLORS.light_red +
          "The installer DMG contains several kexts with the same name but different file sizes." +
          COLORS.default)


def print_logo_and_select_target(script_dir, dry_run):
    print_program_header(TITLE, config.COPYRIGHT_LINE)
    line("Issue:")
    line("OS X Snow Leopard 10.6.8 has no working DisplayPort output with the native")
    line("ATI 5000 driver stack when using a regular PC ATI 5000 series GPU.")
    line("Lion 10.7.5 can initialize DisplayPort, but fails to reactivate it after")
    line("hotplug and sleep/wake.")
    line("The DP pixel clock remains off and the display stays black.")
    line("This patch was developed and tested on a Hackintosh using a PC version of an")
    line("ATI Radeon HD 5000 series GPU. No conclusions are made about the behavior")
    line("of genuine Macs using Apple/Mac Edition graphics cards.")
    line()
    line("This fix:")
    line("This patch fixes these DisplayPort problems specifically for")
    line("OS X Snow Leopard 10.6.8 and OS X Lion 10.7.5.")
    line("Snow Leopard receives the tested Lion display core compatibility changes")
    line("together with the 0xff PPLL guard fix.")
    line("Lion receives the 0xff PPLL guard fix required to restore DisplayPort")
    line("after hotplug and sleep/wake.")
    line()
    line("Requirements:")
    line("  - Python 2.6 or newer")
    line("  - target system running an x86_64 kernel")
    line("  - original source kext bundle(s) placed manually in %s/" % config.SOURCE_DIR_NAME)
    line()
    line("Required Snow Leopard source kexts "
         "(Only needed if you want to create Snow Leopard patch!):")
    for spec in config.SNOW_LEOPARD.kexts:
        line("  - %s from OS X 10.7.2 GM2 11C74" % spec.bundle)
    line()
    line("Required Lion source kext:")
    line("  - ATI5000Controller.kext from OS X Lion 10.7.5 / 11G63")
    line("    Copy it manually from /System/Library/Extensions")
    line()

    target = prompt_target()
    if target is None:
        return None

    line()
    detail("Selected target", target.display_name, indent=1, color=COLORS.green)
    detail("Expected source", target.source_build, indent=1)
    detail("Source", os.path.join(script_dir, config.SOURCE_DIR_NAME), indent=1)
    detail("Output", os.path.join(script_dir, config.OUTPUT_DIR_NAME), indent=1)
    detail("Mode", "dry-run" if dry_run else "build", indent=1,
           color=COLORS.yellow if dry_run else COLORS.green)
    line()
    line("The source kexts are validated by target, version, identifier, bundle size,")
    line("binary SHA-256 and patch pattern before any output is created.")
    line("This program does not install or modify anything in %s." % config.SYSTEM_EXTENSIONS_DIR)
    line("The original source kexts remain untouched.")
    return target


def find_offsets(data, pattern):
    offsets = []
    start = 0
    while True:
        offset = data.find(pattern, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + 1
    return offsets


def format_offsets(offsets):
    if not offsets:
        return "none"
    return ", ".join(["0x%x" % offset for offset in offsets])


def known_other_target(binary_hash, bundle_name, selected_target):
    for target in config.TARGETS:
        if target.key == selected_target.key:
            continue
        spec = config.find_kext_spec(target, bundle_name)
        if spec is None:
            continue
        if binary_hash in (spec.source_hash, spec.final_hash):
            return target
    return None


def validate_bundle(source_dir, spec, target):
    bundle_path = os.path.join(source_dir, spec.bundle)
    if not os.path.exists(bundle_path):
        raise PatcherError("missing source kext: %s" % bundle_path)
    if os.path.islink(bundle_path):
        raise PatcherError("source kext must not be a symbolic link: %s" % bundle_path)
    if not os.path.isdir(bundle_path):
        raise PatcherError("source kext is not a directory: %s" % bundle_path)

    preliminary_info = os.path.join(bundle_path, "Contents", "Info.plist")
    preliminary_binary = os.path.join(bundle_path, "Contents", "MacOS", spec.executable)
    validate_regular_file(preliminary_info, "Info.plist")
    validate_regular_file(preliminary_binary, "kext binary")
    info = read_plist(preliminary_info)
    preliminary_hash = sha256_file(preliminary_binary)

    if preliminary_hash != spec.source_hash:
        other_target = known_other_target(preliminary_hash, spec.bundle, target)
        if other_target is not None:
            raise PatcherError(
                "%s matches the tested source for the %s patch, but %s was selected\n"
                "    source build: %s\n"
                "    found version: %s\n"
                "    selected target: %s" %
                (spec.bundle, other_target.display_name, target.display_name,
                 other_target.source_build, info.get("CFBundleVersion"), target.key)
            )

    info_path, binary_path, bundle_version, bundle_size = validate_kext_bundle_core(
        bundle_path, spec, target.expected_bundle_version,
        "bundle size does not match the tested %s source" % target.source_build,
        BundleSizeError,
    )

    data = read_binary(binary_path)
    source_hash = sha256_data(data)
    if source_hash != spec.source_hash:
        raise PatcherError(
            "%s binary hash does not match the tested %s source\n"
            "    found:    %s\n"
            "    expected: %s" %
            (spec.bundle, target.source_build, source_hash, spec.source_hash)
        )

    return {
        "bundle_path": bundle_path,
        "info_path": info_path,
        "binary_path": binary_path,
        "version": bundle_version,
        "bundle_size": bundle_size,
        "source_hash": source_hash,
        "source_data": data,
    }


def patch_atisupport(data, spec):
    old_offsets = find_offsets(data, config.ATISUPPORT_OLD)
    expected = list(spec.patch_offsets)
    if old_offsets != expected:
        raise PatcherError(
            "ATISupport patch pattern mismatch: found at %s, expected %s" %
            (format_offsets(old_offsets), format_offsets(expected))
        )
    if len(config.ATISUPPORT_OLD) != len(config.ATISUPPORT_NEW):
        raise PatcherError("internal ATISupport patch length mismatch")

    patched = data.replace(config.ATISUPPORT_OLD, config.ATISUPPORT_NEW)
    if find_offsets(patched, config.ATISUPPORT_OLD):
        raise PatcherError("ATISupport old symbol remains after patch")
    if find_offsets(patched, config.ATISUPPORT_NEW) != expected:
        raise PatcherError("ATISupport new symbol verification failed")
    if len(patched) != len(data):
        raise PatcherError("ATISupport binary size changed unexpectedly")
    return patched, old_offsets


def patch_controller(data, spec):
    old_offsets = find_offsets(data, config.CONTROLLER_OLD)
    expected = list(spec.patch_offsets)
    if old_offsets != expected:
        raise PatcherError(
            "ATI5000Controller patch pattern mismatch: found at %s, expected %s" %
            (format_offsets(old_offsets), format_offsets(expected))
        )
    if len(config.CONTROLLER_OLD) != len(config.CONTROLLER_NEW):
        raise PatcherError("internal ATI5000Controller patch length mismatch")

    patched = data.replace(config.CONTROLLER_OLD, config.CONTROLLER_NEW)
    if find_offsets(patched, config.CONTROLLER_OLD):
        raise PatcherError("ATI5000Controller old code remains after patch")
    if find_offsets(patched, config.CONTROLLER_NEW) != expected:
        raise PatcherError("ATI5000Controller new code verification failed")
    if len(patched) != len(data):
        raise PatcherError("ATI5000Controller binary size changed unexpectedly")
    return patched, old_offsets


def build_specs(target):
    patchers = {
        "atisupport": patch_atisupport,
        "controller": patch_controller,
    }
    return [(spec, patchers.get(spec.patch_kind)) for spec in target.kexts]


def validate_and_prepare(source_dir, specs, target):
    prepared = []
    section("source check")
    for spec, patcher in specs:
        line()
        status(spec.bundle, COLORS.cyan)
        result = validate_bundle(source_dir, spec, target)
        detail("version", result["version"])
        detail("identifier", spec.bundle_id)
        detail("bundle size", "%s bytes" % result["bundle_size"])
        detail("source SHA-256", result["source_hash"])
        status("Source binary matches the tested %s build." % target.source_build,
               COLORS.green, indent=2, symbol=OK)

        if patcher is None:
            patched_data = result["source_data"]
            patch_offsets = []
            status("No binary patch required.", COLORS.default, indent=2)
        else:
            patched_data, patch_offsets = patcher(result["source_data"], spec)
            detail("patch", spec.patch_name, indent=2, color=COLORS.magenta)
            detail("offset", format_offsets(patch_offsets), indent=2)
            status("Patch pattern verified.", COLORS.green, indent=2, symbol=OK)

        final_hash = sha256_data(patched_data)
        if final_hash != spec.final_hash:
            raise PatcherError(
                "%s final hash mismatch\n"
                "    found:    %s\n"
                "    expected: %s" % (spec.bundle, final_hash, spec.final_hash)
            )

        detail("final SHA-256", final_hash)
        status("Final binary matches the tested golden build.", COLORS.green,
               indent=2, symbol=OK)
        result["patched_data"] = patched_data
        result["final_hash"] = final_hash
        result["patch_offsets"] = patch_offsets
        prepared.append((spec, result))
    return prepared


def ensure_destination_is_safe(output_dir):
    if os.path.lexists(output_dir):
        raise PatcherError(
            "There is already an output directory %s\n"
            "Please remove or move it and run the patcher again." % output_dir
        )
    parent = os.path.dirname(output_dir)
    if not os.path.isdir(parent):
        raise PatcherError("output parent directory does not exist: %s" % parent)
    if not os.access(parent, os.W_OK):
        raise PatcherError("output parent directory is not writable: %s" % parent)


def copy_bundle(source_bundle, target_bundle):
    try:
        shutil.copytree(source_bundle, target_bundle, symlinks=True)
    except (IOError, OSError, shutil.Error) as exc:
        raise PatcherError("cannot copy %s: %s" % (source_bundle, exc))


def create_manifest(target, prepared):
    kext_names = ",".join([spec.bundle for spec, _result in prepared])
    lines = [
        "HD5000 DisplayPort patch manifest",
        "Manifest-Version: 1",
        "Target: %s" % target.key,
        "Target-OS: %s" % target.display_name,
        "Target-OS-Version: %s" % target.target_os_version,
        "Target-Build: %s" % (target.target_build if target.target_build else "not-fixed"),
        "Source-Build: %s" % target.source_build,
        "Bundle-Version: %s" % target.expected_bundle_version,
        "Patcher-Version: %s" % PROGRAM_VERSION,
        "Kext-Count: %s" % len(prepared),
        "Kexts: %s" % kext_names,
        "",
    ]
    return "\n".join(lines)


def create_report(target, prepared):
    lines = [
        "ATI HD 5000 DisplayPort patch report",
        "",
        "Patcher version: %s" % PROGRAM_VERSION,
        "Target: %s" % target.display_name,
        "Target build: %s" % (target.target_build if target.target_build else "not fixed"),
        "Source build: %s" % target.source_build,
        "",
    ]
    for spec, result in prepared:
        lines.append(spec.bundle)
        lines.append("  Version: %s" % result["version"])
        lines.append("  Source path: %s" % result["bundle_path"])
        lines.append("  Bundle size: %s bytes" % result["bundle_size"])
        lines.append("  Source SHA-256: %s" % result["source_hash"])
        lines.append("  Action: %s" % spec.patch_name)
        if result["patch_offsets"]:
            lines.append("  Patch offset: %s" % format_offsets(result["patch_offsets"]))
        lines.append("  Final SHA-256: %s" % result["final_hash"])
        lines.append("")
    lines.append("All final binary hashes match the tested golden builds.")
    lines.append("")
    return "\n".join(lines)


def create_sums(prepared):
    lines = []
    for spec, result in prepared:
        rel = "%s/Contents/MacOS/%s" % (spec.bundle, spec.executable)
        lines.append("%s  %s" % (result["final_hash"], rel))
    lines.append("")
    return "\n".join(lines)


def write_output(output_dir, prepared, target):
    parent = os.path.dirname(output_dir)
    temp_output = None
    try:
        temp_output = tempfile.mkdtemp(prefix=".hd5000-final-", dir=parent)
        for spec, result in prepared:
            target_bundle = os.path.join(temp_output, spec.bundle)
            copy_bundle(result["bundle_path"], target_bundle)
            target_binary = os.path.join(target_bundle, "Contents", "MacOS", spec.executable)
            validate_regular_file(target_binary, "copied kext binary")
            write_binary(target_binary, result["patched_data"])

            _info_path, verified_binary, _version, _bundle_size = validate_kext_bundle_core(
                target_bundle, spec, target.expected_bundle_version,
                "output bundle size changed while creating the validated patch",
                PatcherError,
            )
            installed_hash = sha256_file(verified_binary)
            if installed_hash != result["final_hash"]:
                raise PatcherError(
                    "%s verification after write failed\n"
                    "    found:    %s\n"
                    "    expected: %s" %
                    (spec.bundle, installed_hash, result["final_hash"])
                )

        write_ascii(os.path.join(temp_output, config.MANIFEST_NAME),
                    create_manifest(target, prepared))
        write_utf8(os.path.join(temp_output, config.REPORT_NAME),
                   create_report(target, prepared))
        write_ascii(os.path.join(temp_output, config.SUMS_NAME), create_sums(prepared))

        if os.path.lexists(output_dir):
            raise PatcherError("output appeared while patching: %s" % output_dir)
        try:
            os.rename(temp_output, output_dir)
        except OSError as exc:
            raise PatcherError("cannot finalize output directory: %s" % exc)
        temp_output = None
    finally:
        if temp_output is not None and os.path.exists(temp_output):
            try:
                shutil.rmtree(temp_output)
            except (IOError, OSError, shutil.Error):
                pass


def show_write_plan(output_dir, prepared, target, dry_run):
    section("output")
    detail("Target", target.display_name, indent=1)
    if dry_run:
        status("Dry-run active, nothing will be written.", COLORS.yellow)
        for spec, _result in prepared:
            status("Would create %s." % spec.bundle, COLORS.default, indent=2)
            if spec.patch_kind is not None:
                detail("Would patch", spec.patch_name, indent=3, color=COLORS.magenta)
            else:
                detail("Would copy", "byte-identical tested source bundle", indent=3)
        status("Would create %s." % config.MANIFEST_NAME, COLORS.default, indent=2)
        status("Would create %s." % config.REPORT_NAME, COLORS.default, indent=2)
        status("Would create %s." % config.SUMS_NAME, COLORS.default, indent=2)
        detail("target", output_dir, indent=2)
    else:
        status("Creating validated output.", COLORS.cyan)


# noinspection DuplicatedCode
def main(argv):
    set_color_enabled(terminal_supports_color("--no-color" in argv[1:]))
    try:
        dry_run, no_color, show_help, show_version = parse_args(argv)
    except PatcherError as exc:
        line()
        error_status(exc)
        line(COLORS.default + "  Try --help." + COLORS.default)
        exit_status()
        line()
        return 2

    set_color_enabled(terminal_supports_color(no_color))
    if show_help:
        print_basic_help(
            os.path.basename(argv[0]),
            "validate and simulate the selected patch without writing %s/" %
            config.OUTPUT_DIR_NAME,
            "show patcher version",
        )
        return 0
    if show_version:
        line("%s %s" % (PROGRAM_NAME, PROGRAM_VERSION))
        return 0

    target = None
    try:
        script_dir = resolve_script_directory(__file__)
        source_dir = os.path.join(script_dir, config.SOURCE_DIR_NAME)
        output_dir = os.path.join(script_dir, config.OUTPUT_DIR_NAME)

        target = print_logo_and_select_target(script_dir, dry_run)
        if target is None:
            line()
            status("Quit by user.", COLORS.yellow, indent=1)
            exit_status()
            line()
            return 0

        if sys.version_info < (2, 6):
            raise PatcherError("Python 2.6 or newer is required")
        if not os.path.exists(source_dir):
            raise PatcherError("source directory is missing: %s" % source_dir)
        if os.path.islink(source_dir):
            raise PatcherError("source directory must not be a symbolic link: %s" % source_dir)
        if not os.path.isdir(source_dir):
            raise PatcherError("source path is not a directory: %s" % source_dir)

        ensure_destination_is_safe(output_dir)
        specs = build_specs(target)
        prepared = validate_and_prepare(source_dir, specs, target)
        show_write_plan(output_dir, prepared, target, dry_run)

        if not dry_run:
            write_output(output_dir, prepared, target)
            status("Output created and verified.", COLORS.green, indent=1, symbol=OK)
            detail("path", output_dir, indent=2)

        section("done")
        if dry_run:
            status("All checks passed, source files were not modified.", COLORS.green,
                   indent=1, symbol=OK)
            status("Dry-run finished, no output files were created.", COLORS.yellow)
        else:
            status("All patches match the tested golden binaries.", COLORS.green,
                   indent=1, symbol=OK)
            status("No system kexts were installed or modified.", COLORS.cyan)
            line()
            line("All kexts have been patched successfully.")
            print(COLORS.default + "Now you can run: " +
                  COLORS.light_magenta + "python %s" % config.INSTALLER_SCRIPT_NAME +
                  COLORS.default)
            line()
            line("A real install on the matching target creates a verified backup next to")
            line("this package before the first system kext is changed.")
            line("Keep an external copy of that backup and read %s for restore details." %
                 config.README_NAME)
            line()
            line("All done, goodbye.")
        line()
        return 0

    except PatcherError as exc:
        error_status(exc, indent=2)
        if isinstance(exc, BundleSizeError) and target is not None and target.key == "SL":
            pacifist_size_hint(indent=3)
        status("No system kexts were modified.", COLORS.yellow, indent=2)
        exit_status(indent=3)
        line()
        return 1
    except KeyboardInterrupt:
        status("Interrupted by user.", COLORS.yellow, indent=2, symbol=FAIL)
        status("No system kexts were modified.", COLORS.yellow, indent=2)
        exit_status(indent=3)
        line()
        return 130
    # Last-resort safety net for unexpected patcher failures.
    # noinspection PyBroadException
    except Exception as exc:
        error_status(exc, unexpected=True, indent=2)
        status("No system kexts were modified.", COLORS.yellow, indent=2)
        exit_status(indent=3)
        line()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
