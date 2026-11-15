# Toolchain forensics scripts (archived)

These are the helper scripts from the 1080 toolchain-forensics runs. They are written up in
docs/TOOLING_DECOMP.md under "Toolchain forensics" I–VII and in the related IDO_CODEGEN kits.
Examples are the IDO 4.1 `accom` / `ccom` wrappers, the MIPSpro 7.2 `edgcpfe` front-end wrappers,
the EFS / idb extractors and the as1 survey drivers.

They used to live in `tools/forensics/scripts/`, next to about 3 GB of downloaded SGI toolchain
images (`tools/forensics/dl_*`, `x_*`, untracked). Those downloads were deleted when the project
was wrapped up (2026-11-15). Many scripts still contain hard-coded paths into
`tools/forensics/...`. To run them again:

1. Download the images again into `tools/forensics/`. The URLs and sha256s are listed in
   docs/TOOLING_DECOMP.md.
2. Copy these scripts back to `tools/forensics/scripts/`.

The only toolchain the 1080 build actually needs from this work is MIPSpro 7.2.1. That one is
fetched by the 1080 repo's own `tools/fetch-mipspro721.sh`, not from here.
