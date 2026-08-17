Place the original source kext bundle(s) for the target you want to build in this directory.

Snow Leopard 10.6.8 patch:
  The following original OS X 10.7.2 GM2 / 11C74 kexts are required:

  ATISupport.kext
    expected bundle size: 3527235 bytes (3.53 MB)

  ATIFramebuffer.kext
    expected bundle size: 301392 bytes (301.39 kB)

  ATI5000Controller.kext
    expected bundle size: 674665 bytes (674.66 kB)

  If you use Pacifist to extract the kexts from the installer DMG, make sure
  you choose the complete bundle with the correct size. The installer DMG
  contains several items with the same kext name but different sizes.

Lion 10.7.5 patch:
  Only this original kext is required:

  ATI5000Controller.kext
    source: OS X Lion 10.7.5 / 11G63
    CFBundleVersion: 7.3.2
    expected bundle size: 697826 bytes (697.83 kB)

  Copy ATI5000Controller.kext manually from /System/Library/Extensions on the
  Lion 10.7.5 / 11G63 system and place it in this directory.

The patcher never reads kexts directly from /System/Library/Extensions.
It validates the selected target, bundle version, identifier, bundle size,
SHA-256 and patch pattern before creating FinalPatchedKext.

Bundle size means regular-file bytes plus the stored size of symbolic links.
This keeps size validation deterministic on legacy OS X filesystems and tools.

The final controller PPLL guard patch modifies only the x86_64 slice.
The target Snow Leopard or Lion system must therefore run an x86_64 kernel.
