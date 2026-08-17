# -*- coding: utf-8 -*-

"""Internal runtime data for the ATI HD 5000 DisplayPort tools.

This module contains only static metadata shared by patchKext.py and
installKextOnSystem.py. It is not intended to be executed directly.

Compatible with Python 2.6 and later 2.x releases, and with modern Python 3.
"""

import binascii


PACKAGE_VERSION = "1.0.0"
COPYRIGHT_LINE = "Copyright © by Michael McSky 2026 - CC BY-NC-SA 4.0 License"

SOURCE_DIR_NAME = "YourKextSource"
OUTPUT_DIR_NAME = "FinalPatchedKext"
REPORT_NAME = "PATCH-REPORT.txt"
SUMS_NAME = "SHA256SUMS.txt"
MANIFEST_NAME = "PATCH-MANIFEST.txt"
BACKUP_MANIFEST_NAME = "BACKUP-MANIFEST.txt"
SYSTEM_EXTENSIONS_DIR = "/System/Library/Extensions"
KEXT_CACHE_STARTUP_DIR = "/System/Library/Caches/com.apple.kext.caches/Startup"
LION_KERNEL_CACHE_NAME = "kernelcache"
SNOW_LEOPARD_KERNEL_CACHE_PREFIX = "kernelcache_x86_64."
SNOW_LEOPARD_MKEXT_NAME = "Extensions.mkext"
PATCHER_SCRIPT_NAME = "patchKext.py"
INSTALLER_SCRIPT_NAME = "installKextOnSystem.py"
README_NAME = "README.md"


class KextSpec(object):
    """Typed-at-runtime metadata record for one ATI kext bundle."""

    def __init__(self, bundle, executable, bundle_id, bundle_size,
                 system_original_bundle_size, system_original_version,
                 system_original_hash, source_hash, final_hash,
                 patch_kind, patch_name, patch_offsets):
        self.bundle = str(bundle)
        self.executable = str(executable)
        self.bundle_id = str(bundle_id)
        self.bundle_size = int(bundle_size)
        self.system_original_bundle_size = int(system_original_bundle_size)
        self.system_original_version = str(system_original_version)
        self.system_original_hash = str(system_original_hash)
        self.source_hash = str(source_hash)
        self.final_hash = str(final_hash)
        self.patch_kind = patch_kind
        self.patch_name = str(patch_name)
        self.patch_offsets = tuple([int(value) for value in patch_offsets])


class TargetSpec(object):
    """Runtime metadata record for one explicitly selected patch target."""

    def __init__(self, key, display_name, target_os_version, target_build,
                 source_build, expected_bundle_version, backup_dir_name, kexts):
        self.key = str(key)
        self.display_name = str(display_name)
        self.target_os_version = str(target_os_version)
        self.target_build = str(target_build) if target_build else ""
        self.source_build = str(source_build)
        self.expected_bundle_version = str(expected_bundle_version)
        self.backup_dir_name = str(backup_dir_name)
        self.kexts = tuple(kexts)


# Shared 23-byte ML-style PPLL guard rewrite. The byte pattern is the same in
# the tested 11C74 and 11G63 controller binaries; only the file offset differs.
CONTROLLER_OLD = binascii.unhexlify(
    "4180fe020f878b0000004188f74989fc410fb6f74c89e7"
)
CONTROLLER_NEW = binascii.unhexlify(
    "4488f0fec03c030f87880000004189f74989fc90909090"
)

# Snow Leopard-only ATISupport compatibility patch.
ATISUPPORT_OLD = b"__ZN13IOEventSource12checkForWorkEv"
ATISUPPORT_NEW = b"__ZN13IOCommandGate12checkForWorkEv"


SNOW_LEOPARD_KEXTS = (
    KextSpec(
        "ATISupport.kext",
        "ATISupport",
        "com.apple.kext.ATISupport",
        3527235,
        3399537,
        "6.3.6",
        "85baff9ed464cf2c5ea5e8bf642aec8c9908a70f6673beae58bcccfd97345034",
        "0f7abb8b45897ae59bb0a06921c618d674459783c6389e3fc03db3936e091f49",
        "9de7242b5eacc9f1def8492b5334841d18add5c592c11479265f4dfaa7f296a2",
        "atisupport",
        "Snow Leopard checkForWork compatibility",
        (0x194480, 0x34BE11),
    ),
    KextSpec(
        "ATIFramebuffer.kext",
        "ATIFramebuffer",
        "com.apple.kext.ATIFramebuffer",
        301392,
        310362,
        "6.3.6",
        "e26c7cd79b117f93a338c6c6e1673c542e0483c0ac34f33e9c956d4a08c0c8ae",
        "8189d23b691e8dc8c55883a3435e372ca54291a638f9a912fb1a9985aa597c5e",
        "8189d23b691e8dc8c55883a3435e372ca54291a638f9a912fb1a9985aa597c5e",
        None,
        "copied unchanged",
        (),
    ),
    KextSpec(
        "ATI5000Controller.kext",
        "ATI5000Controller",
        "com.apple.kext.ATI5000Controller",
        674665,
        701991,
        "6.3.6",
        "5139acf5b60bc1088ef7a3cef5765ecfd29cb19eac04617001b4736b4767a0c0",
        "89d9de079da9260d2480aba68e7aba15f6fdcf4f474f21493cc78e1854a1b780",
        "8e14084aac4156095f966957a9473496943db084a6fc230d6f08711adbea2fb1",
        "controller",
        "DisplayPort VCLK 0xff PPLL guard",
        (0x16D4B,),
    ),
)


LION_KEXTS = (
    KextSpec(
        "ATI5000Controller.kext",
        "ATI5000Controller",
        "com.apple.kext.ATI5000Controller",
        697826,
        697826,
        "7.3.2",
        "b9a6866844953c593a0bd479f47fdf3e8f9435cb9fb9c1e0bc3dee94cd68dd4d",
        "b9a6866844953c593a0bd479f47fdf3e8f9435cb9fb9c1e0bc3dee94cd68dd4d",
        "07b59562d17eb647384e7898505b6abf340d286dc8168859c91d8d6095d363ac",
        "controller",
        "DisplayPort VCLK 0xff PPLL guard",
        (0x17739,),
    ),
)


SNOW_LEOPARD = TargetSpec(
    "SL",
    "OS X Snow Leopard 10.6.8",
    "10.6.8",
    "",
    "OS X 10.7.2 GM2 11C74",
    "7.1.2",
    "SystemKextBackupBeforeInstall-SL",
    SNOW_LEOPARD_KEXTS,
)

LION = TargetSpec(
    "LION",
    "OS X Lion 10.7.5",
    "10.7.5",
    "11G63",
    "OS X Lion 10.7.5 / 11G63",
    "7.3.2",
    "SystemKextBackupBeforeInstall-Lion",
    LION_KEXTS,
)

TARGETS = (SNOW_LEOPARD, LION)


def get_target(key):
    normalized = str(key).strip().upper()
    for target in TARGETS:
        if target.key == normalized:
            return target
    return None


def find_kext_spec(target, bundle_name):
    for spec in target.kexts:
        if spec.bundle == bundle_name:
            return spec
    return None
