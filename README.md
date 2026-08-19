# DisplayPort Fix on OS X Snow Leopard and Lion for ATI 5000 series GPUs

*Copyright © by Michael McSky 2026 - CC BY-NC-SA 4.0 License*

Issue:
OS X **Snow Leopard 10.6.8** has **no working DisplayPort output** with the native
ATI 5000 driver stack when using a **regular PC ATI 5000 series GPU**.
Lion **10.7.5** can initialize DisplayPort, but **fails** to reactivate it after
**hotplug and sleep/wake**.
The DP pixel clock remains off and the display **stays black**.
This patch was developed and tested on a Hackintosh using a PC version of an
ATI Radeon HD 5000 series GPU. No conclusions are made about the behavior
of genuine Macs using Apple/Mac Edition graphics cards.

**This fix:**
This patch **fixes these DisplayPort problems** specifically for
OS X **Snow Leopard 10.6.8** and OS X **Lion 10.7.5**.
Snow Leopard receives the tested Lion display core compatibility changes
together with the **0xff PPLL guard fix**.
Lion receives the 0xff PPLL guard fix required to **restore DisplayPort
after hotplug and sleep/wake**.

The behavior of genuine Macs with Apple/Mac Edition graphics cards was not
tested. It is possible that the patch could also help such systems, but this
has not been verified.

*One might ask why a patch is still being made for such old hardware and
operating systems. Many older macOS projects can only be opened and edited
correctly with the original software, plugins and system versions. Snow
Leopard and Lion work very well with Radeon HD 5000 series cards, which are
still easy and inexpensive to find on the used market. This makes it possible
to build a fast and practical Retro Mac or Hackintosh system with older
hardware. With this patch, such a Retro system can also use DisplayPort, making
old hardware much easier to use with modern monitors today.*

**This package builds, installs and restores the tested DisplayPort fixes for:**

- OS X Snow Leopard 10.6.8
- OS X Lion 10.7.5 / 11G63

**The patch is expected to be applicable to these PC versions of ATI Radeon HD
5000 series graphics cards:**

- ATI Radeon HD 5770 (OutOfTheBox)
- ATI Radeon HD 5870 (OutOfTheBox)
- ATI Radeon HD 5750
- ATI Radeon HD 5850
- ATI Radeon HD 5830
- ATI Radeon HD 5450

The target is always selected manually in `patchKext.py`. The patcher does not
auto-detect the operating system and never reads kexts directly from
`/System/Library/Extensions`. No Apple kexts are included in this package.

## 1. Prepare the original kexts

Place the original source kext bundle(s) in `YourKextSource/`.

For the Snow Leopard patch, use the complete OS X 10.7.2 GM2 / 11C74 bundles:

The sizes below are bundle payload sizes as calculated by the patcher
(regular-file bytes plus stored symbolic-link sizes).

- `ATISupport.kext` — 3527235 bytes
- `ATIFramebuffer.kext` — 301392 bytes
- `ATI5000Controller.kext` — 674665 bytes

For the Lion file-based patch, copy this bundle manually from a clean OS X Lion
10.7.5 / 11G63 `/System/Library/Extensions` directory:

- `ATI5000Controller.kext` — CFBundleVersion 7.3.2 — 697826 bytes

The patcher additionally verifies bundle identity, exact binary SHA-256 and the
expected patch pattern. A kext from the wrong target or build is rejected.

If you use the optional OpenCore method for Lion described in section 3.1, no
Lion source kext has to be placed in `YourKextSource/`; the fix can be applied
directly at boot with `Kernel -> Patch`.

## 2. Build the patch

Run:

    python patchKext.py

At the prompt enter `SL` or `Lion`. Input is case-insensitive. Enter `Q` to quit.
The target is deliberately selected by the user and is not inferred from the
currently running operating system.

To validate everything without creating `FinalPatchedKext/`:

    python patchKext.py --dry-run

A real build creates `FinalPatchedKext/` with the patched kext(s),
`PATCH-MANIFEST.txt`, `PATCH-REPORT.txt` and `SHA256SUMS.txt`.

For Lion, this build step is only required for the file-based installation
method. It can be skipped when using the optional OpenCore patch in section 3.1.

## 3. Install

Run on the target system:

    python installKextOnSystem.py

For a non-destructive validation first use:

    python installKextOnSystem.py --dry-run

The installer reads the explicit target from `PATCH-MANIFEST.txt`, then
independently verifies the expected kext set, bundle metadata, exact bundle payload sizes and golden
SHA-256 hashes. On the real target system it also checks the installed system
binary hashes before any replacement.

The following target-specific directory is the **planned backup location** next
to the installer:

- Snow Leopard: `SystemKextBackupBeforeInstall-SL/`
- Lion: `SystemKextBackupBeforeInstall-Lion/`

The directory is created only during a **real installation on the matching
target system**, after the patched output and current system state have been
verified and the user has confirmed the installation. `patchKext.py`, dry-run
mode and an installation that aborts before the backup stage do **not** create a
backup directory.

Before the first active system kext is changed, the installer copies and
verifies the complete current target kext set into that directory. The backup
normally contains `BACKUP-MANIFEST.txt`, which records the exact bundle version,
bundle payload size and SHA-256 of every backed-up system kext. If the manifest is later
deleted, restore mode can still independently identify a complete built-in
trusted backup state as described below.

After a successful installation, keep an external copy of the complete backup
directory. Do not rely on the working copy next to the installer as the only
copy of the original system kexts.

Before privileged system changes, the installer validates administrator access
with `/usr/bin/sudo -v`. Failed authentication aborts before `/System/Library/Extensions`
is modified.

The new kexts are then staged and revalidated for bundle identity, version,
exact bundle payload size and binary SHA-256 before installation. The same checks are
repeated after activation. The installer does not perform an automatic rollback.
The verified target-specific backup remains the explicit recovery path through
`python installKextOnSystem.py --restore`.

The installer then touches `/System/Library/Extensions`, runs
`kextcache -system-prelinked-kernel` and `kextcache -system-caches`, and checks
both command exit codes. It does not parse normal informational output from
`kextcache`. Afterward it verifies that a non-empty target `kernelcache*` file
exists and is at least as new as `/System/Library/Extensions`. On Snow Leopard
it also verifies that a non-empty `Extensions.mkext` exists, but does **not** use
its modification time as a hard-failure condition.

Nothing inside `/System/Library/Extensions` is changed after the final cache
rebuild. If a real replacement or cache command fails after system modification
has started, the installer stops and reports that the system may already have
been modified. Repair the caches or use the verified backup before rebooting.

Both supported installation targets require an **x86_64 kernel**. The PPLL
guard rewrite described below modifies only the x86_64 controller slice;
an i386 kernel is therefore intentionally rejected by the installer.

The Lion installation is intentionally limited to OS X Lion 10.7.5 / 11G63.
It replaces only `ATI5000Controller.kext`. The optional OpenCore method below
applies the same controller fix at boot without replacing the on-disk kext.

The Snow Leopard installation replaces the tested three-kext patch set. A known
earlier Snow Leopard hybrid state is recognized and only the controller is
updated when appropriate.

### 3.1 Optional Lion OpenCore patch (no `/S/L/E` replacement)

For OS X Lion 10.7.5 / 11G63, installing the patched
`ATI5000Controller.kext` into `/System/Library/Extensions` is optional. Lion
needs only the 23-byte PPLL guard rewrite, so OpenCore can apply the same binary
replacement at boot through `Kernel -> Patch`. The original Apple kext can stay
unchanged on disk.

This OpenCore method is intended only for the Lion target. Snow Leopard still
needs the complete tested three-kext Lion display-core backport and therefore
uses the file-based patcher/installer described above.

Before switching to the OpenCore method, restore the original Apple Lion
10.7.5 / 11G63 `ATI5000Controller.kext` and rebuild the system kext caches. Do
not use the file-patched controller and the OpenCore patch at the same time.

Add the following dictionary to the `Kernel -> Patch` array in OpenCore's
`config.plist`:

```xml
<dict>
    <key>Arch</key>
    <string>x86_64</string>
    <key>Base</key>
    <string></string>
    <key>Comment</key>
    <string>ATI5000Controller DP PPLL 0xff fix - Lion 10.7.5</string>
    <key>Count</key>
    <integer>1</integer>
    <key>Enabled</key>
    <true/>
    <key>Find</key>
    <data>QYD+Ag+HiwAAAEGI90mJ/EEPtvdMiec=</data>
    <key>Identifier</key>
    <string>com.apple.kext.ATI5000Controller</string>
    <key>Limit</key>
    <integer>0</integer>
    <key>Mask</key>
    <data></data>
    <key>MaxKernel</key>
    <string>11.99.99</string>
    <key>MinKernel</key>
    <string>11.0.0</string>
    <key>Replace</key>
    <data>RIjw/sA8Aw+HiAAAAEGJ90mJ/JCQkJA=</data>
    <key>ReplaceMask</key>
    <data></data>
    <key>Skip</key>
    <integer>0</integer>
</dict>
```

The same entry in an OpenCore editor such as OCAT uses these values:

```text
Arch:        x86_64
Base:        <empty>
Comment:     ATI5000Controller DP PPLL 0xff fix - Lion 10.7.5
Count:       1
Enabled:     True
Identifier:  com.apple.kext.ATI5000Controller
Find:        4180FE020F878B0000004188F74989FC410FB6F74C89E7
Mask:        <empty>
MaxKernel:   11.99.99
MinKernel:   11.0.0
Replace:     4488F0FEC03C030F87880000004189F74989FC90909090
ReplaceMask: <empty>
Limit:       0
Skip:        0
```

The `Find` and `Replace` data are exactly the same tested 23-byte sequence
documented below. The entry is restricted to `x86_64`, targeted at
`com.apple.kext.ATI5000Controller` and limited to Darwin 11.x. The project is
still tested specifically on OS X Lion 10.7.5 / 11G63.

With this method the Apple kext in `/System/Library/Extensions` remains
original. The DisplayPort fix can be disabled simply by disabling this
OpenCore patch entry.

## 4. Technical background and patch internals

This section documents the reason for the patch and the binary changes in
engineering detail. The conclusions below come from repeated tests on a
Hackintosh with a PC version of an ATI Radeon HD 5870, comparisons between
the Snow Leopard, Lion and Mountain Lion ATI stacks, IORegistry captures and
a small read-only diagnostic utility written in C and compiled specifically for the
investigation. Genuine Macs and Apple/Mac Edition graphics cards were not part
of the test platform.

### 4.1 Observed failure modes

The three operating-system generations behave differently:

**Native Snow Leopard 10.6.8**

The native 10.6.8 ATI 5000 stack does not bring up DisplayPort correctly on the
tested regular PC Radeon HD 5870. DVI can work while the DisplayPort display
stays black. This is the first problem addressed by the Snow Leopard hybrid
stack.

**Snow Leopard with the first Lion 10.7.2 display-core backport (v1)**

The v1 combination uses the complete Lion 10.7.2 GM2 / 11C74 display core
needed by the HD 5870 on Snow Leopard. With that combination DisplayPort can
initialize correctly, full hardware acceleration is available, cold and
warm boot work, and DVI/HDMI remain usable. The working DP state was also
reproduced without WhateverGreen, which helped separate the controller problem
from WEG-specific injection or connector handling.

However, getting DP working initially did not solve every display transition.
A direct DP unplug/replug could succeed, but transition sequences such as
DP -> DVI -> DP and especially sleep -> wake could leave the DP display black.
The machine itself stayed alive and could still be inspected through Screen
Sharing. This was an important distinction: the remaining problem was not a
complete GPU hang and not simply missing EDID detection.

The failing state showed that the display path could be detected and logically
reconfigured while the DisplayPort pixel-clock path was not brought back to
its active value. In the failing v1 wake state `Current V.Clk0` remained at
`0 kHz`.

**Lion 10.7.5 / 11G63**

Lion already contains the display-core changes needed to initialize DP, so it
does not need the Snow Leopard compatibility backport. It still contains the
same old PPLL-ID guard in `ATI5000Controller`, however. The tested result is the
same class of reactivation failure: the monitor can work initially and then
stay black after a DP transition or sleep/wake because the DP pixel clock is
not programmed again.

**Mountain Lion 10.8.5**

Mountain Lion became the reference implementation because the same HD 5870 and
DisplayPort monitor work correctly there, including sleep/wake. Tests also
showed that this successful wake behavior was not dependent on the custom
AGPMInjector-HD5870 kext. Comparing the Mountain Lion controller path against
Lion exposed a small but critical change in the PPLL guard logic.

### 4.2 How the clock problem was isolated

IORegistry data alone was useful for connector topology, but it did not expose
enough of the internal ATI controller state to explain why an apparently valid
DP connection could remain black. For that reason a small read-only diagnostic
utility was written in C and compiled for OS X during the investigation.

The tool is read-only. It uses the ATI user client and selector 7
(`updateDeviceProperties` -> `ATIController::getPropertiesForUserClient`) to
retrieve the driver's `ATY,DeviceConfig` state. Among other fields it records:

- connector online state and current/supported connection type
- UNIPHY selection
- transmitter number and transmitter link
- DIG number
- HPD number
- CRTC index
- PLL index
- EDID / connection state
- dynamic, static and normal PLL assigner data
- `PLL for Display Port` and `PLL for Display Port PPLL`
- assigned PLL and CRTC masks
- `ConnectionsOnTransmitter` ownership bitmaps
- interrupt dictionaries on Mountain Lion

A useful comparison sequence was not just "DP works" versus "DP is black".
Several transition states were captured separately: DP from cold boot, DP
unplugged, direct DP replug, DVI active, DVI unplugged and DP after DVI. That
made it possible to separate physical connector/HPD state from logical
CRTC/DIG/PLL ownership.

On Mountain Lion, the logical framebuffer can move between the physical DP and
DVI connectors while the physical HPD and transmitter information remains
separate. Most importantly for the final patch, working DP uses PLL index
`255` (`0xff`) as a special DisplayPort clock-selection value.

The decisive clock result was:

- failing v1 wake: `Current V.Clk0 = 0 kHz`
- successful final v3 wake: `Current V.Clk0 = 270000 kHz`
- successful Mountain Lion wake: the same active DP clock state, with DP PLL
  index `255 / 0xff`

This changed the investigation from "which connector callback is missing?" to
"why is the requested DP clock programming discarded?".

### 4.3 Root cause in `hwProgramPpllUsingBios()`

The relevant clock-programming path is:

```text
ATI5000Controller::hwProgramPixelClock()
        -> ATI5000Controller::hwProgramPpllUsingBios()
        -> AtomBiosProxy::setPixelClock()
        -> AtiAtomBiosPllDce40::setPixelClock()
        -> ATOM SetPixelClock
        -> PPLL0 / V.Clk0
```

The C fragments in this section are **semantic pseudocode reconstructed from
binary disassembly**. They are not claimed to be Apple's original source code.

The newer PLL assigner used by Lion represents the DisplayPort states with two
special values:

```text
DP ON:   PLL ID = 0xff, External Clock ID = 0xff
DP OFF:  PLL ID = 0xfe
```

Lion 10.7.2 and Lion 10.7.5 still have the older input guard in
`hwProgramPpllUsingBios()`:

```c
if (pllId > 2)
    return;
```

That accepts only `0`, `1` and `2`. It rejects both `0xfe` and `0xff`, including
`0xff`, which is exactly the value used when DisplayPort must be enabled again.
The function returns before the lower ATOM BIOS pixel-clock programming path is
reached.

The historical comparison with Snow Leopard explains how this regression could
have happened. Snow Leopard also has a `pllId <= 2` style guard, but at that
stage its caller still supplies an ordinary PPLL ID `0`, `1` or `2`. After the
guard, Snow Leopard checks the active connector and can replace the PLL ID in
`ActiveConnectorInfo` with `0xff` for DisplayPort before calling the lower
`setPixelClock()` path. Simplified:

```c
/* Snow Leopard behavior, reconstructed semantically */
if (pllId > 2)
    return;

if (connectionIsDisplayPort && capabilityAllowsIt)
    activeInfo.pllId = 0xff;
else
    activeInfo.pllId = pllId;

setPixelClock(...);
```

Lion moved the DisplayPort PLL assignment earlier. The caller now arrives at
`hwProgramPpllUsingBios()` with `pllId == 0xff`, but the old Snow-Leopard-style
guard remained in place:

```text
Snow Leopard
normal ID 0/1/2 -> old guard accepts -> DP detected later -> ID becomes 0xff
-> ATOM SetPixelClock

Lion
DP assigned 0xff earlier -> old guard sees 0xff -> return -> no SetPixelClock
```

The lower Lion code can already handle `0xff`. In the tested 10.7.2 stack,
`AtiAtomBiosPllDce40::setPixelClock()` maps PLL ID `1` to BIOS selector 1, ID `2`
to selector 2, and other values such as `0xff` to selector 0 before invoking the
ATOM `SetPixelClock` command. The hardware-support path therefore exists; the
controller guard prevents it from being reached.

This also explains the otherwise confusing transition tests. A direct DP
unplug/replug can work even with the old guard. When Lion turns off a DP path
whose old PLL ID is greater than 1 and the target clock is zero, the caller can
change `0xff` to `0xfe`. The old guard rejects `0xfe`, so PPLL0 is not actually
reprogrammed to zero and `V.Clk0` can remain at `270000 kHz`. A direct DP replug
then appears successful because the clock never went away.

DVI -> DP and sleep -> wake are different. DVI uses a normal PLL ID, so its
shutdown path can genuinely bring PPLL0 / `V.Clk0` down to zero. Sleep also
leaves the tested DP clock at zero. The following DP re-enable request uses
`0xff`; Lion rejects it at the old guard, `ATOM SetPixelClock` is never called,
`V.Clk0` remains `0 kHz`, and the monitor stays black.

Mountain Lion 10.8.5 changes exactly this decision:

```c
if ((uint8_t)(pllId + 1) > 3)
    return;
```

The 8-bit arithmetic is important. Incrementing `0xff` wraps to `0x00`, so the
special DP-on value is accepted while `0xfe` is still rejected:

| `pllId` | 8-bit `pllId + 1` | Result |
|---|---:|---|
| `0x00` | `0x01` | allowed |
| `0x01` | `0x02` | allowed |
| `0x02` | `0x03` | allowed |
| `0x03..0xfe` | `0x04..0xff` | return |
| `0xff` | `0x00` | allowed |

The patch backports that **specific Mountain Lion guard behavior**. It does not
remove the bounds check, force a PLL permanently on or accept arbitrary IDs.
Normal PPLL IDs remain unchanged, `0xfe` remains rejected, and `0xff` is allowed
to reach the existing Lion ATOM BIOS code.

### 4.4 Exact x86_64 guard rewrite and assembly explanation

The patch is defined by an exact 23-byte replacement. The assembly shown below
is the disassembly of those bytes and of the surrounding tested binaries; it is
not a guessed line-for-line reconstruction from C.

The 10.7.2 / 11C74 x86_64 function starts at virtual address `0x15d36`. Just
before the patch window, Lion copies the second unsigned-byte argument from
`DL` into `R14B`; this is the PLL ID used by the guard:

```asm
15d45  movq   %rcx, %rbx        ; save ClockParams& from RCX in RBX
15d48  movb   %dl, %r14b        ; copy incoming PLL ID from DL into R14B
```

The original 23-byte window is:

```text
41 80 FE 02 0F 87 8B 00 00 00 41 88 F7 49 89 FC 41 0F B6 F7 4C 89 E7
```

Decoded in the original Lion binary:

```asm
15d4b  cmpb   $0x02, %r14b      ; unsigned compare: PLL ID versus 2
15d4f  ja     0x15de0           ; if PLL ID > 2, jump to function return
15d55  movb   %sil, %r15b       ; save low byte of first byte argument in R15B
15d58  movq   %rdi, %r12        ; save the C++ this pointer from RDI in R12
15d5b  movzbl %r15b, %esi       ; zero-extend saved byte back into ESI
15d5f  movq   %r12, %rdi        ; restore this pointer to RDI before next call
```

The first two instructions are the actual bug. In C-like semantics they are:

```c
if (pllId > 2)
    return;
```

Mountain Lion 10.8.5 does **not** use the same register allocation as Lion, so
its machine code must not be copied blindly. Its corresponding function saves
the PLL ID in `BL` and contains this sequence:

```asm
14d46  movl   %edx, %ebx        ; save PLL ID argument in EBX / BL
14d48  movl   %esi, %r15d       ; save first byte argument in R15D
14d4b  movq   %rdi, %r12        ; save this pointer in R12
14d4e  movb   %bl, %al          ; copy PLL ID into temporary 8-bit AL
14d50  incb   %al               ; add 1 as an 8-bit value; 0xff wraps to 0x00
14d52  cmpb   $0x03, %al        ; unsigned compare the wrapped value with 3
14d54  ja     0x14ddf           ; return only when wrapped value is above 3
```

The patch therefore ports the **semantics** of the Mountain Lion guard into the
Lion register layout. In Lion the live PLL ID is already in `R14B`, not `BL`.
The patched 23 bytes are:

```text
44 88 F0 FE C0 3C 03 0F 87 88 00 00 00 41 89 F7 49 89 FC 90 90 90 90
```

Disassembled in the patched 10.7.2 controller:

```asm
15d4b  movb   %r14b, %al        ; copy Lion's saved PLL ID into temporary AL
15d4e  incb   %al               ; increment only 8 bits: 0xff becomes 0x00
15d50  cmpb   $0x03, %al        ; compare wrapped temporary value with 3
15d52  ja     0x15de0           ; IDs 0x03..0xfe return; 0/1/2/0xff continue
15d58  movl   %esi, %r15d       ; save the already prepared first argument
15d5b  movq   %rdi, %r12        ; save the unchanged this pointer in R12
15d5e  nop                       ; intentional padding, performs no operation
15d5f  nop                       ; intentional padding, performs no operation
15d60  nop                       ; intentional padding, performs no operation
15d61  nop                       ; intentional padding, performs no operation
```

#### Why the patch contains four `NOP` instructions

The patch must stay inside the exact original 23-byte region. Moving the code
that follows `0x15d61` would change branch/call targets and would turn a small,
verifiable binary patch into a much more invasive relocation problem. No code
cave is needed or used.

The original guard consumes 10 bytes:

```text
cmpb (4 bytes) + ja near (6 bytes) = 10 bytes
```

The new Mountain-Lion-style guard consumes 13 bytes:

```text
movb (3) + incb (2) + cmpb (2) + ja near (6) = 13 bytes
```

So the new guard needs three additional bytes. Space is recovered from the
register-setup instructions immediately after the old guard. The original
setup takes 13 bytes:

```asm
movb   %sil, %r15b       ; 3 bytes
movq   %rdi, %r12        ; 3 bytes
movzbl %r15b, %esi       ; 4 bytes
movq   %r12, %rdi        ; 3 bytes
```

The original setup keeps the first unsigned-byte argument in `R15B` for later
use, zero-extends that byte into `ESI` for the following
`getActiveConnectorForEh(unsigned char)` call, and saves the C++ `this` pointer
in `R12`.

In the tested Lion instruction stream, the replacement can preserve the same
low argument byte and the same `this` pointer more compactly:

```asm
movl   %esi, %r15d       ; 3 bytes: save ESI; its low byte becomes R15B
movq   %rdi, %r12        ; 3 bytes: save the unchanged this pointer
```

The patch itself never changes `ESI` or `RDI`. The following function receives
an `unsigned char`, so the low byte `SIL` is the relevant argument value, while
`R15B` still contains that same byte for the later connector-info write.
`RDI` likewise remains the live `this` pointer while `R12` keeps the saved copy
needed later in the function. The immediate restore instructions from the
original sequence are therefore unnecessary in this tested path.

The compact setup saves seven bytes; the larger guard uses three of those
bytes, leaving **four bytes** in the fixed patch window. Those four bytes are
deliberately filled with `NOP` (`0x90`).

A `NOP` means "no operation": the CPU advances to the next instruction without
changing registers, flags or memory. Using four explicit one-byte NOPs is safer
than leaving stale bytes from the removed Lion instructions. It guarantees that
no fragment of the old instruction sequence can accidentally execute and keeps
the first untouched instruction exactly at `0x15d62`.

The conditional branch also changes from displacement `0x8b` to `0x88`. This is
not a different return target. The `ja` instruction itself moved forward by
three bytes because of the longer guard, so its relative displacement must be
three bytes smaller to land on the same existing `0x15de0` return path.

For Lion 10.7.5 / 11G63 the same original 23-byte pattern and the same patched
23-byte pattern are used, but at the later function location:

```text
function virtual start:      0x16724
patch virtual range:         0x16739..0x1674f
x86_64 FAT slice offset:     0x1000
universal file patch offset: 0x17739
```

This is why the patcher validates both the complete source SHA-256 and the exact
23-byte pattern at the expected target-specific offset before writing anything.

### 4.5 Snow Leopard patch composition

The final Snow Leopard patch is deliberately more than a PPLL byte patch.
Native Snow Leopard first needs the tested Lion 10.7.2 GM2 / 11C74 display core
to obtain functional DisplayPort. The 0xff guard fix is then applied on top of
that controller so the resulting stack can also re-enable the DP clock after a
transition.

The three source bundles are expected to report CFBundleVersion `7.1.2`.

**ATISupport.kext**

The Lion binary needs the tested Snow Leopard compatibility import rewrite. Two
occurrences are replaced:

```text
old: __ZN13IOEventSource12checkForWorkEv
new: __ZN13IOCommandGate12checkForWorkEv
```

Universal-file offsets:

```text
0x194480
0x34BE11
```

The patcher requires exactly two matches. This is not a wildcard symbol search;
a different binary is rejected.

**ATIFramebuffer.kext**

The tested complete 11C74 bundle is copied unchanged. Its source and final
binary SHA-256 are therefore identical.

**ATI5000Controller.kext**

The same 23-byte Mountain-Lion-style PPLL guard rewrite described above is
applied to the 11C74 controller. Only its x86_64 slice is modified; the i386
slice remains byte-identical and is not a supported runtime target.

```text
function virtual start:      0x15D36
patch virtual range:         0x15D4B..0x15D61
x86_64 FAT slice offset:     0x1000
universal file patch offset: 0x16D4B
```

The important development distinction is:

```text
native Snow Leopard
    -> no usable DisplayPort with the tested PC HD 5870

11C74 hybrid / v1
    -> DisplayPort initializes and acceleration works
    -> direct replug can work
    -> DP -> DVI -> DP and sleep/wake can still leave DP black
    -> failing wake can leave Current V.Clk0 at 0 kHz

11C74 hybrid + 0xff guard / final v3
    -> retains the working Lion display-core compatibility
    -> DP PPLL programming accepts the special 0xff ID
    -> successful wake restores Current V.Clk0 to 270000 kHz
```

### 4.6 Lion 10.7.5 / 11G63 patch

Lion already has working initial DP support, so only
`ATI5000Controller.kext` is modified. The tested bundle is CFBundleVersion
`7.3.2` and has a bundle payload size of `697826` bytes.

The 23-byte pattern occurs exactly once in the original 11G63 universal
binary:

```text
x86_64 function virtual start: 0x16724
patch virtual range:           0x16739..0x1674f
x86_64 FAT slice offset:       0x1000
universal file patch offset:   0x17739
i386 slice start:              0x54000
```

Only the x86_64 slice is modified. The i386 slice remains byte-identical.
The same tested 23-byte replacement can alternatively be applied at boot with
OpenCore `Kernel -> Patch` as described in section 3.1, leaving the original
Lion controller bundle unchanged in `/System/Library/Extensions`.

### 4.7 Binary identities used by the patcher

The patcher validates both structure and binary identity before writing output.
These are the principal tested binary SHA-256 values:

| Target | Binary | Source SHA-256 | Final SHA-256 |
|---|---|---|---|
| SL | `ATISupport` | `0f7abb8b45897ae59bb0a06921c618d674459783c6389e3fc03db3936e091f49` | `9de7242b5eacc9f1def8492b5334841d18add5c592c11479265f4dfaa7f296a2` |
| SL | `ATIFramebuffer` | `8189d23b691e8dc8c55883a3435e372ca54291a638f9a912fb1a9985aa597c5e` | `8189d23b691e8dc8c55883a3435e372ca54291a638f9a912fb1a9985aa597c5e` |
| SL | `ATI5000Controller` | `89d9de079da9260d2480aba68e7aba15f6fdcf4f474f21493cc78e1854a1b780` | `8e14084aac4156095f966957a9473496943db084a6fc230d6f08711adbea2fb1` |
| Lion | `ATI5000Controller` | `b9a6866844953c593a0bd479f47fdf3e8f9435cb9fb9c1e0bc3dee94cd68dd4d` | `07b59562d17eb647384e7898505b6abf340d286dc8168859c91d8d6095d363ac` |

For the Snow Leopard target, the patcher also validates the exact bundle payload
sizes of the selected 11C74 source bundles:

```text
ATISupport.kext          3527235 bytes
ATIFramebuffer.kext      301392 bytes
ATI5000Controller.kext   674665 bytes
```

For Lion 10.7.5 / 11G63:

```text
ATI5000Controller.kext   697826 bytes
```

For installer system-state verification, the untouched Snow Leopard 10.6.8 /
10K549 bundles have these tested bundle payload sizes:

```text
ATISupport.kext          3399537 bytes
ATIFramebuffer.kext       310362 bytes
ATI5000Controller.kext    701991 bytes
```

The bundle payload size is defined as the sum of regular-file bytes plus the
stored size of symbolic links. This is intentional: the untouched Snow Leopard
ATI bundles contain four legacy code-signature links whose stored payloads total
115 bytes per bundle. Counting those link payloads makes the check deterministic
when the same entries are preserved as symbolic links or materialized as small
regular files by older tools/filesystems.

Bundle payload size validation matters because the Lion installer media can contain
same-named extraction candidates that are not complete bundles. A matching
Mach-O binary hash alone is not enough to prove that the complete source kext
was selected.

### 4.8 Development path and why the final patch has two layers on SL

The final design came from narrowing the problem in stages rather than starting
with a guessed connector personality patch. Debugging was extensive and
required a large number of intermediate kext combinations and controller
builds. Each change had to be tested through cold/warm boot, direct DP replug,
DP/DVI transitions and sleep/wake while comparing driver state before and after
the transition.

For readability, the many internal test labels are not reproduced here. The key
milestones are simply called v1, v2 and v3 below; many additional intermediate
versions were created and tested between them. These labels describe debugging
milestones, not package release versions.

1. Native Snow Leopard established the first failure: no usable DP output.
2. The Lion 10.7.2 display-core backport established that newer ATI display
   components solve initial DP bring-up on Snow Leopard.
3. v1 proved that initial DP support and full acceleration are not the same
   problem as DP reactivation after a state transition.
4. Replug, DP/DVI transition and sleep/wake captures were compared rather than
   treating every black screen as the same failure.
5. Mountain Lion 10.8.5 was used as the known-good reference on the same GPU and
   monitor.
6. The compiled C diagnostic utility exposed the internal connector/PLL state
   and made the `Current V.Clk0 = 0 kHz` failure measurable.
7. v2 and several intermediate experiments did not change the wake result. That
   helped eliminate unrelated paths and showed that initial DP support alone was
   not sufficient.
8. Binary comparison of `hwProgramPpllUsingBios()` identified the changed
   Mountain Lion guard and the special `0xff` behavior.
9. Final v3 applied only that 23-byte guard rewrite on top of the known v1
   display-core base. Successful wake then restored the active DP clock state.
10. The same semantic fix was ported directly to the original Lion 10.7.5 /
    11G63 controller at its corresponding offset.

This explains why the two supported targets are intentionally different:

- Snow Leopard 10.6.8 needs **both** the tested Lion display-core compatibility
  layer and the `0xff` PPLL guard fix.
- Lion 10.7.5 already has the required display core and needs only the `0xff`
  PPLL guard fix in `ATI5000Controller`.

The package therefore validates exact known versions, bundle payload sizes, hashes and
patch patterns. It is not a generic "ATI 5000 binary patcher" for arbitrary OS
X releases or arbitrary controller binaries.

## 5. Restore the pre-install backup

To restore a verified backup created during a real installation before the
first system-kext replacement, run:

    python installKextOnSystem.py --restore

A restore can also be checked without modifying the system:

    python installKextOnSystem.py --restore --dry-run

On a non-target host, restore dry-run validates the backup independently against
the built-in trusted states but cannot compare it with that host's active
`/System/Library/Extensions`. On the actual target OS, dry-run performs the full
current-system comparison as well.

`--restore` does not use `FinalPatchedKext/`. It uses the target-specific backup
folder created next to the installer by a completed backup stage of a real
installation. The patcher and dry-run mode never create this folder.

`BACKUP-MANIFEST.txt` is the normal verification record, but it is not required
for recovery. If the manifest is missing, the installer independently checks all
backup kexts against the complete built-in trusted states. Restore continues only
when bundle identifiers, executables, versions, exact bundle payload sizes and SHA-256
hashes identify one complete known pre-install state.

The known restore states are:

- Snow Leopard: original OS X 10.6.8 ATI stack
- Snow Leopard: known earlier Snow Leopard hybrid stack
- Lion: original OS X Lion 10.7.5 / 11G63 `ATI5000Controller.kext`

Before restoring anything, the installer also validates the currently running
target OS and current system kext hashes. If the current system already matches
the backup, including after a restore performed manually, the installer reports
that the backup is already restored and exits without modifying files or
rebuilding caches.

If the current system does not already match the backup, a real restore proceeds
only from the tested **fully patched** state. A different known state that does
not match the selected backup is rejected instead of being silently converted
into another historical state. This prevents an unrelated or stale backup from
being applied merely because both sides happen to contain individually known
kext hashes.

The backup bundles are staged into temporary non-kext paths first and their
bundle identity, version, exact bundle payload size and binary SHA-256 are checked again. The
current target bundles are then replaced by the verified backup bundles.
Automatic rollback is intentionally not used. If the restore is interrupted or
a cache command fails after replacement has started, the installer reports that
the system may already have been modified; rerun restore or repair the caches
before rebooting.

After the restored bundles are verified, the installer touches
`/System/Library/Extensions`, runs both cache commands and performs the same
kernel-cache checks used by normal installation. On Snow Leopard,
`Extensions.mkext` must exist and be non-empty, but its modification time is not
used as a hard-abort criterion.

If both Snow Leopard and Lion backup directories are present next to the
installer, restore mode asks which backup target should be used. It does not
silently choose between them.

Keep an external copy of the complete target-specific backup directory. The
normal locations next to the installer are:

- Snow Leopard: `SystemKextBackupBeforeInstall-SL/`
- Lion: `SystemKextBackupBeforeInstall-Lion/`

## 6. Hard abort and manual recovery

A hard abort means that the installer could not prove that the backup and/or the
currently installed ATI kexts form a complete known safe state. This is
intentional: the installer will not overwrite system kexts when the state is
unknown, mixed, damaged or belongs to the wrong OS/build.

If you still have known original kexts stored elsewhere, first preserve the
currently installed ATI kexts before changing anything.

For Snow Leopard:

    /bin/mkdir -p "$HOME/Desktop/ATI-Kext-Manual-Backup"
    /usr/bin/ditto "/System/Library/Extensions/ATISupport.kext" "$HOME/Desktop/ATI-Kext-Manual-Backup/ATISupport.kext"
    /usr/bin/ditto "/System/Library/Extensions/ATIFramebuffer.kext" "$HOME/Desktop/ATI-Kext-Manual-Backup/ATIFramebuffer.kext"
    /usr/bin/ditto "/System/Library/Extensions/ATI5000Controller.kext" "$HOME/Desktop/ATI-Kext-Manual-Backup/ATI5000Controller.kext"

For Lion:

    /bin/mkdir -p "$HOME/Desktop/ATI-Kext-Manual-Backup"
    /usr/bin/ditto "/System/Library/Extensions/ATI5000Controller.kext" "$HOME/Desktop/ATI-Kext-Manual-Backup/ATI5000Controller.kext"

Then copy only known originals for the same target back to
`/System/Library/Extensions`. Replace `/path/to/original` below with the
directory that contains your independently saved original kexts.

For Snow Leopard:

    sudo /bin/rm -rf "/System/Library/Extensions/ATISupport.kext"
    sudo /usr/bin/ditto "/path/to/original/ATISupport.kext" "/System/Library/Extensions/ATISupport.kext"
    sudo /usr/sbin/chown -R root:wheel "/System/Library/Extensions/ATISupport.kext"
    sudo /bin/chmod -R go-w "/System/Library/Extensions/ATISupport.kext"
    sudo /bin/rm -rf "/System/Library/Extensions/ATIFramebuffer.kext"
    sudo /usr/bin/ditto "/path/to/original/ATIFramebuffer.kext" "/System/Library/Extensions/ATIFramebuffer.kext"
    sudo /usr/sbin/chown -R root:wheel "/System/Library/Extensions/ATIFramebuffer.kext"
    sudo /bin/chmod -R go-w "/System/Library/Extensions/ATIFramebuffer.kext"
    sudo /bin/rm -rf "/System/Library/Extensions/ATI5000Controller.kext"
    sudo /usr/bin/ditto "/path/to/original/ATI5000Controller.kext" "/System/Library/Extensions/ATI5000Controller.kext"
    sudo /usr/sbin/chown -R root:wheel "/System/Library/Extensions/ATI5000Controller.kext"
    sudo /bin/chmod -R go-w "/System/Library/Extensions/ATI5000Controller.kext"

For Lion:

    sudo /bin/rm -rf "/System/Library/Extensions/ATI5000Controller.kext"
    sudo /usr/bin/ditto "/path/to/original/ATI5000Controller.kext" "/System/Library/Extensions/ATI5000Controller.kext"
    sudo /usr/sbin/chown -R root:wheel "/System/Library/Extensions/ATI5000Controller.kext"
    sudo /bin/chmod -R go-w "/System/Library/Extensions/ATI5000Controller.kext"

After restoring the correct target kexts, rebuild both kext caches:

    sudo /usr/bin/touch "/System/Library/Extensions"
    sudo /usr/sbin/kextcache -system-prelinked-kernel
    sudo /usr/sbin/kextcache -system-caches

The installer prints the same target-specific example commands automatically
after a restore hard abort.

Do not mix Snow Leopard and Lion kexts. Preserve the manual backup, the verified
installer backup and any separately stored originals on external storage before
making further system changes.

After a successful install or restore, restart the system.

*Copyright © by Michael McSky 2026 - CC BY-NC-SA 4.0 License*