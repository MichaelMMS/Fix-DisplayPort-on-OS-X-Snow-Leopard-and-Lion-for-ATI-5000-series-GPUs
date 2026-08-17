# -*- coding: utf-8 -*-

"""Internal shared helpers for the HD5000 DisplayPort tools.

This module is not intended to be executed directly.  It contains UI, file,
plist, hashing and bundle-validation helpers shared by patchKext.py and
installKextOnSystem.py.

Compatible with Python 2.6 and later 2.x releases, and with modern Python 3.
"""

from __future__ import print_function

import hashlib
import os
import re
import stat
import sys

# noinspection SpellCheckingInspection
try:
    import plistlib
except ImportError:
    # noinspection SpellCheckingInspection
    plistlib = None

try:
    from xml.parsers.expat import ExpatError
except ImportError:
    ExpatError = ValueError


ASCII_LOGO = r"""Michael Mc.              @@@@@@@
                      @@@@@@:
                   @@@@@@
                 @@@@@@
               @@@@@@
              @@@@@
            @@@@@{
           @@@@@
           @@@@@
          @@@@@@                   ?@@@#
           @@@@@@                @@@@@
           M@@@@@@@            @@@@&
             @@@@@@@@@@@     @@@@@
                 |@@@@@@@@@ @@@@   @@@
                      @@@@@@@@%@@@@@@@      @@@@@@
                      @@@@@@@@@@:@@@@@  @@@@@@@@@
                    8@@@@@@0     @@@@@@@@@ :@@@@x
                  @@@@@@@@                @@@@@
               @@@@@@ @@@                @@@@@
           @@@@@@@                     @@@@@
     @@@@@@@@@                       @@@@@
   @@@@@@                         @@@@@'
                              @@@@@@     presents:"""

ARROW = "➔"
OK = "✓"
FAIL = "✗"
DOT = "•"


class Colors(object):
    """Mutable ANSI color palette shared by both command-line tools."""

    def __init__(self, enabled=False):
        self.enabled = False
        self.default = ""
        self.red = ""
        self.green = ""
        self.yellow = ""
        self.light_yellow = ""
        self.light_red = ""
        self.blue = ""
        self.magenta = ""
        self.light_magenta = ""
        self.cyan = ""
        self.dark_blue = ""
        self.gray = ""
        self.set_enabled(enabled)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.default = "\033[0m" if self.enabled else ""
        self.red = "\033[31m" if self.enabled else ""
        self.green = "\033[32m" if self.enabled else ""
        self.yellow = "\033[33m" if self.enabled else ""
        self.light_yellow = "\033[93m" if self.enabled else ""
        # Use only classic ANSI attributes here. Older Apple Terminal versions can
        # interpret the 256-color sequence ESC[38;5;208m as attribute 5 (blink).
        self.light_red = "\033[1;31m" if self.enabled else ""
        self.blue = "\033[34m" if self.enabled else ""
        self.magenta = "\033[35m" if self.enabled else ""
        self.light_magenta = "\033[95m" if self.enabled else ""
        self.cyan = "\033[36m" if self.enabled else ""
        self.dark_blue = "\033[1;34m" if self.enabled else ""
        self.gray = "\033[37m" if self.enabled else ""


COLORS = Colors(False)
_ERROR_TYPE = RuntimeError


def set_error_type(error_type):
    global _ERROR_TYPE
    _ERROR_TYPE = error_type


def _error_class(error_type):
    return error_type if error_type is not None else _ERROR_TYPE


def terminal_supports_color(no_color):
    if no_color:
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, IOError, OSError):
        return False


def set_color_enabled(enabled):
    COLORS.set_enabled(enabled)


def line(text=""):
    print(text)


def status(text, color=None, indent=1, symbol=ARROW):
    if color is None:
        color = COLORS.default
    prefix = "  " * indent + symbol + " "
    print(prefix + color + text + COLORS.default)


def detail(label, value, indent=2, color=None):
    if color is None:
        color = COLORS.default
    if label:
        label = label[:1].upper() + label[1:]
    prefix = "  " * indent + DOT + " "
    print(prefix + color + label + COLORS.default + ": " + value)


def section(title):
    line()
    if title:
        title = title[:1].upper() + title[1:]
    if not title.endswith("…"):
        title += "…"
    print(COLORS.dark_blue + title + COLORS.default)


def ensure_period(text):
    if text.endswith("."):
        return text
    return text + "."


def _red_text_with_default_kexts(text):
    parts = re.split(r"(\S+\.kext)", text)
    output = COLORS.red
    for part in parts:
        if not part:
            continue
        if part.endswith(".kext"):
            output += COLORS.default + part + COLORS.red
        else:
            output += part
    return output + COLORS.default


def _print_red_error_with_default_kexts(prefix, text):
    print(prefix + _red_text_with_default_kexts(text))


def error_status(message, unexpected=False, indent=1):
    """Print error prose in red while keeping paths and kext names default."""
    lines = str(message).splitlines() or [""]
    label = "Unexpected error: " if unexpected else "Error: "
    prefix = "  " * indent + FAIL + " "
    continuation_prefix = " " * len(prefix)

    first = lines[0]
    path_at = first.find("/")
    if path_at >= 0:
        red_part = label + first[:path_at]
        path_part = first[path_at:]
        output = prefix + _red_text_with_default_kexts(red_part)
        output += path_part + COLORS.default
        print(output)
    else:
        _print_red_error_with_default_kexts(prefix, ensure_period(label + first))

    for extra in lines[1:]:
        text = extra.strip()
        if text.startswith("Please "):
            print(continuation_prefix + COLORS.red + ensure_period(text) + COLORS.default)
        else:
            print(continuation_prefix + COLORS.default + ensure_period(text) + COLORS.default)


def exit_status(indent=2):
    status("I will exit.", COLORS.red, indent=indent, symbol=FAIL)


def print_logo():
    logo_lines = ASCII_LOGO.splitlines()
    for index, logo_line in enumerate(logo_lines):
        if index == 0 and logo_line.startswith("Michael Mc."):
            name = "Michael Mc."
            rest = logo_line[len(name):]
            print(COLORS.default + name + COLORS.cyan + rest + COLORS.default)
        elif index == len(logo_lines) - 1 and logo_line.endswith("presents:"):
            marker = "presents:"
            rest = logo_line[:-len(marker)]
            print(COLORS.cyan + rest + COLORS.default + marker + COLORS.default)
        else:
            print(COLORS.cyan + logo_line + COLORS.default)


def print_program_header(title, copyright_line):
    """Print the common logo, title and copyright header."""
    line()
    print_logo()
    line()
    print(COLORS.light_yellow + title + COLORS.default)
    line()
    print(COLORS.gray + copyright_line + COLORS.default)
    line()
    line()


def read_console_line(prompt_text):
    """Read one terminal line without raw_input/input version branching."""
    sys.stdout.write(prompt_text)
    sys.stdout.flush()
    answer = sys.stdin.readline()
    if answer == "":
        raise EOFError()
    return answer.rstrip("\r\n")


def prompt_enter_or_quit(prompt_text):
    while True:
        try:
            answer = read_console_line(prompt_text)
        except EOFError:
            return False

        answer = answer.strip()
        if answer == "":
            return True
        if answer.lower() == "q":
            return False
        line("Please press Enter to continue or Q to quit.")


def parse_args(argv, error_type=None):
    dry_run = False
    no_color = False
    show_help = False
    show_version = False

    for arg in argv[1:]:
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--no-color":
            no_color = True
        elif arg in ("-h", "--help"):
            show_help = True
        elif arg == "--version":
            show_version = True
        else:
            raise _error_class(error_type)("unknown option: %s" % arg)

    return dry_run, no_color, show_help, show_version


def print_basic_help(program, dry_run_text, version_text):
    line("Usage: %s [options]" % program)
    line()
    line("Options:")
    line("  --dry-run    %s" % dry_run_text)
    line("  --no-color   disable ANSI colors")
    line("  --version    %s" % version_text)
    line("  -h, --help   show this help")


def validate_kext_identity(bundle_path, spec, expected_version, error_type=None):
    """Validate common Info.plist identity fields and return core paths/version."""
    error_class = _error_class(error_type)
    info_path = os.path.join(bundle_path, "Contents", "Info.plist")
    binary_path = os.path.join(bundle_path, "Contents", "MacOS", spec.executable)

    validate_regular_file(info_path, "Info.plist", error_class)
    validate_regular_file(binary_path, "kext binary", error_class)

    info = read_plist(info_path, error_class)
    bundle_id = info.get("CFBundleIdentifier")
    bundle_version = info.get("CFBundleVersion")
    executable = info.get("CFBundleExecutable")

    if bundle_id != spec.bundle_id:
        raise error_class("%s has unexpected CFBundleIdentifier: %s" %
                          (spec.bundle, bundle_id))
    if bundle_version != expected_version:
        raise error_class("%s has unsupported CFBundleVersion: %s, expected %s" %
                          (spec.bundle, bundle_version, expected_version))
    if executable != spec.executable:
        raise error_class("%s has unexpected CFBundleExecutable: %s" %
                          (spec.bundle, executable))

    return info_path, binary_path, bundle_version


def script_directory(module_file, error_type=None):
    try:
        return os.path.dirname(os.path.abspath(module_file))
    except (AttributeError, IOError, OSError, TypeError) as exc:
        raise _error_class(error_type)("cannot determine script directory: %s" % exc)


def read_binary(path, error_type=None):
    try:
        handle = open(path, "rb")
        try:
            return handle.read()
        finally:
            handle.close()
    except (IOError, OSError) as exc:
        raise _error_class(error_type)("cannot read %s: %s" % (path, exc))


def write_binary(path, data, error_type=None):
    try:
        handle = open(path, "wb")
        try:
            handle.write(data)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except (IOError, OSError):
                pass
        finally:
            handle.close()
    except (IOError, OSError) as exc:
        raise _error_class(error_type)("cannot write %s: %s" % (path, exc))


def write_ascii(path, text, error_type=None):
    if not isinstance(text, bytes):
        text = text.encode("ascii")
    write_binary(path, text, error_type)


def write_utf8(path, text, error_type=None):
    if not isinstance(text, bytes):
        text = text.encode("utf-8")
    write_binary(path, text, error_type)


def sha256_data(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, error_type=None):
    return sha256_data(read_binary(path, error_type))


def finder_size_text(size_bytes):
    """Return a Finder-style decimal size using SI units (base 1000)."""
    if size_bytes >= 1000000:
        return "%.2f MB" % (float(size_bytes) / 1000000.0)
    if size_bytes >= 1000:
        return "%.2f kB" % (float(size_bytes) / 1000.0)
    return "%s bytes" % size_bytes


def bundle_payload_size(bundle_path, error_type=None):
    """Return regular-file bytes plus the stored size of symbolic links."""
    total = 0
    try:
        for root, dir_names, file_names in os.walk(bundle_path):
            for name in file_names:
                file_path = os.path.join(root, name)
                entry_stat = os.lstat(file_path)
                if stat.S_ISREG(entry_stat.st_mode) or stat.S_ISLNK(entry_stat.st_mode):
                    total += entry_stat.st_size
            for name in dir_names:
                dir_path = os.path.join(root, name)
                entry_stat = os.lstat(dir_path)
                if stat.S_ISLNK(entry_stat.st_mode):
                    total += entry_stat.st_size
    except (IOError, OSError) as exc:
        raise _error_class(error_type)("cannot calculate bundle size for %s: %s" %
                                       (bundle_path, exc))
    return total


def validate_bundle_size(bundle_path, bundle_name, expected_size, mismatch_text,
                         error_type=None):
    actual_size = bundle_payload_size(bundle_path, error_type)
    if actual_size != expected_size:
        raise _error_class(error_type)(
            "%s %s\n"
            "    found:    %s bytes\n"
            "    expected: %s bytes (%s)" %
            (bundle_name, mismatch_text, actual_size, expected_size,
             finder_size_text(expected_size))
        )
    return actual_size


def validate_kext_bundle_core(bundle_path, spec, expected_version,
                              size_mismatch_text, error_type=None):
    info_path, binary_path, bundle_version = validate_kext_identity(
        bundle_path, spec, expected_version, error_type
    )
    bundle_size = validate_bundle_size(
        bundle_path, spec.bundle, spec.bundle_size, size_mismatch_text, error_type
    )
    return info_path, binary_path, bundle_version, bundle_size


def read_plist(path, error_type=None):
    if plistlib is None:
        raise _error_class(error_type)("Python plistlib is unavailable")

    invalid_plist = getattr(plistlib, "InvalidFileException", ValueError)
    plist_errors = (IOError, OSError, ValueError, TypeError, AttributeError,
                    ExpatError, invalid_plist)
    try:
        if hasattr(plistlib, "readPlist"):
            return plistlib.readPlist(path)
        handle = open(path, "rb")
        try:
            return plistlib.load(handle)
        finally:
            handle.close()
    except plist_errors as exc:
        raise _error_class(error_type)("cannot read plist %s: %s" % (path, exc))


def validate_regular_file(path, label, error_type=None):
    if not os.path.exists(path):
        raise _error_class(error_type)("missing %s: %s" % (label, path))
    if os.path.islink(path):
        raise _error_class(error_type)("%s must not be a symbolic link: %s" % (label, path))
    if not os.path.isfile(path):
        raise _error_class(error_type)("%s is not a regular file: %s" % (label, path))
