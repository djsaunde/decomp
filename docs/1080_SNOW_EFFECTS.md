# 1080: snoweffects.uso (snow particles, board / hand trails, map lights)

> Readability pass, agent-c run 798 (branch agent-c: 6e50d3958 pure rename, a99c7d6e6 / 5975c3dd3
> call naming, b2193673a fields + tags); run 803 (fields: 05b0ad25e, 2aedb0c92, 9c58b352d, 7a03c9316,
> 568bd65aa, d056f299f; pure rename ce091eacf). Matching history: docs/1080_NEW_MODULES.md (snoweffects sections).

## Index
- [1. Layout: four TUs](#1-layout-four-tus)
- [2. Classes (from the module's vtables and name strings)](#2-classes-from-the-modules-vtables-and-name-strings)
- [3. Trail virtual slots](#3-trail-virtual-slots)
- [4. Readability state and rules](#4-readability-state-and-rules)
- [5. Struct fields (run 803)](#5-struct-fields-run-803)

## 1. Layout: four TUs

Text 0xA900, four C++ TUs (each repeats the static fs_gdlRead*_snow readers and its Parm*_read_snow
methods): 0x0-0x3D64 particles + snowfall, 0x3D70-0x7E1C trail base + board / hand trail,
0x7E20-0x924C board spray, 0x9250-0xA900 lights.

## 2. Classes (from the module's vtables and name strings)

Evidence: `scripts/uso-imports.py sites snoweffects --section data` (vtable words) plus the Data
strings each function stores. Vtable pointer = hostioParms word - 0xC; slot N at vptr + 0xC + 8N
(slot 2 display, 3 update, 8 loadData, 10+ class-specific).

| class (functions) | vtable | name string | notes |
|---|---|---|---|
| SnowPool (`Particle handler`) | Data+0x60 | "snow puffs" | Node pool of 0x58-byte SnowParticle; init slot 10, buildTexDL slot 11, display 0xC90 |
| PowderParticles / NormalParticles / SpecParticles | Data+0x158 / 0x1C8 / 0x238 | "snow specs" / "norm specs" / "norm specs" | SnowPool subclasses: only buildTexDL differs (0x15D0 / 0x1A18 / 0x1E60) |
| SnowFall (`Snow Flakes`) | Data+0xD0 | "snow flakes" | display 0x28E0, update moveFlakes, fill 0x39C4, frustum planes |
| SnowRing (trail base, abstract) | Data+0x4F0 | "trail" (DL context) | ring of slots x stride points, Vtx, slot 10 pure |
| BoardTrail (C struct BoardTrail; ncc_b donor class `SnowEffect`) | Data+0x458 | "board trail" | children: NormalParticles (+0x9C), Powder (+0x98, createPowder), Spec (+0xA0, createSpec); spawn effects by flag bits: 1 spawnPowder, 2 spawnNormal, 4 spawnSpec |
| HandTrail | Data+0x59C | "hand trail" | stride 2; placeEnds 0x7960 |
| BoardSpray | Data+0x778 | "board spray" | stride 4; draw / emit / placeEnds / setDefaults overrides |
| SnowColourItemType | Data+0x3C8 / 0x6E8 | | ColourItemType with slot 10 = create 0x7D8C (0x91BC unreferenced twin): a plain 0x40-byte libgdl colour item, vptr bootup ColourItem_vtbl_75A0 (game.uso ColourSubItem, game_libs ColourItem_create_0000C5B0). No in-module vptr store: per-TU template copies |
| LocalLight (SNode) | Data+0x964 | "Local Light", "DynLight::Parms" | ctor 0x9328, Parms at +0x240; lit-vertex list, flicker (Data+0x958 sequences) |
| LocalLightType | Data+0x880 | | SNodeItemType create 0x9E10 |
| MapLighter (C struct, was SnowLink) | Data+0x9C4 | "MapLighter" | display = cullLights (cam_isSphereInView over the "lig" items), update 0xA10C, syncLight 0x9F44. bootup game_createMap: ctor(0, map MorphPoly, reg->light0, reg->light1) then syncLight |

## 3. Trail virtual slots

| slot | SnowRing | BoardTrail | HandTrail | BoardSpray |
|---|---|---|---|---|
| 10 init | pure | init 0x5FD4 | init 0x78E8 | init 0x7F60 |
| 11 draw (DL) | SnowRing_draw 0x40B4 (setupDL 0x4188) | = | = | draw 0x8C60 |
| 12 emit (from SnowRing_update) | emit 0x47D4 | = | = | emit 0x7FE0 |
| 13 calcWidth (+0x50) | 1.0 (0x4E4C) | lean fade 0x63B4 | base | base |
| 14 placeEnds (probe 0x52D4) | 0x4E5C | = | 0x7960 | 0x8D70 |
| 15 spawn | empty 0x52CC | dispatch 0x634C (Powder / Normal / Spec) | base | base |
| 16 (2 args) | empty 0x5440 | = | = | empty 0x90F0 |

`hits` (+0x144) counts end points the probe pushed back; SnowRing_emitTick advances the ring only
when hits >= 2. +0x2C is the trailed object (`cam` in the donors: lean +0x970, state +0x9A2).

## 4. Readability state and rules

- Census after run 798: 106 fns, 1 placeholder (`snoweffects_uso_func_00000000`, the Text+0 Vec3 dot:
  `*_00000000` names are never renamed, tagged UNNAMED sentinel), 3 weak (empty vslots, UNNAMED
  unknown-role), 102 real; calls 170 named / 4 left (the Vec3 dot, tagged); raw casts 0; 50 accessor
  uses = the SNOW_PH / SNOW_W phantom words in the NCC donors (RAW byte-lock).
- Donors: renames and comments only. Tags in donors go as trailing comments on the existing line so
  no line is added or moved (as1 line ties, uopt cut positions). Verify every snoweffects .o .text
  before / after (objdump -d, names stripped), then the gate.
- The spawnPowder / Normal / Spec and SnowFall_fill donors are spliced (plan cannot prove them): their calls
  were named by hand from the ROM jal relocs and pinned by `name-placeholder-calls.py check`.
- Struct (typedef) names are not linker symbols: rename them by hand, never through rename-symbol.py. The
  ncc_b donor keeps class `SnowEffect`: the Makefile maps its mangled method names
  (`init__10SnowEffect...`) with --redefine-sym.
- snoweffects_uso.c (plain C) now includes gdl/gl_data.h, for the ColourItem_vtbl_75A0 token (= D_00000000).
  Adding that line, and comment lines between functions, left the .o byte-identical. Donors still never gain lines.
- Next: see the end of section 5.

## 5. Struct fields (run 803)

`unkNN` struct fields over src/snoweffects_uso (C + donors): 124 -> 42 (typed 101 -> 23, char pads 23 -> 19).
Field renames only touch declarations and `->` uses, so line counts stay the same in every donor. Each named
field has its evidence in a trailing comment.

- **SnowParticle** (0x58): pos, vel, accel (snowfall sway), gravity, minVelY, angle (randf * 360 at snowfall
  spawn, no reader), life (<= 0 kills; oldest = least life), decay, size, aspect (sprite height / width,
  SnowPool_display), sizeVel, fadeAt, col, unk4C (only copied), alpha, alphaVel.
- **SnowRing** (base of every trail): mtx (+0x30, world matrix), endXInit / endZInit -> endX / endZ (end
  points at (+-endX cos a, 0, +-endZ * width * sin a)), drag / pointGravity (SnowRing_update), lean (+0x4C =
  +-owner +0x970), flags (+0x54, BoardTrail's effect bits), on / prevOn / prevState / noGround (+0x74..+0x80),
  texW / texH (+0xA8), endA / endB / across / velDir / perp / endP / endQ / origin (+0xE4..+0x138), hits,
  cosA (+0x148 = -(perp . velDir), placeEnds' angle), hitDistP / Q, then the emit parameters velOfs, dropY,
  maxDist, alphaSpeed, alpha, alphaLean, alphaDecay (+0x154..+0x16C). SnowSlot +0x04 = tex (ring texture).
  Owner (SnowOwner / donor `cam`) offsets used: +0x318 vel, +0x348 speed, +0x3B0 up axis, +0x970 lean,
  +0x9A2 state (97 / 98 / 99), +0xA30 colour, +0xA58 flags (0x80 mirrors).
- **BoardSpray** (+0x178..+0x1EC; its C init / setDefaults take a SnowRing *, so the fields sit in the C
  SnowRing with a `spray` prefix): sprayFade, sprayLiftY, sprayUpScale, sprayPerpScale, sprayVelScale,
  sprayOuterLift, sprayStrength (lean strength -1..1), sprayMinLean / MaxLean / RampBase, sprayTex.
- **BoardTrail** (+0x174..+0x230): one parameter block per effect, prefixed by the pool it fills
  (powder* +0x174..+0x1AC, norm* +0x1B0..+0x1D0 incl. normAirFrames / normBurst / normLastState, spec*
  +0x1DC..+0x224 incl. specTint, the r g b the colour lerps to by specTintMix). The same names are in the
  MIPSpro donor structs SnowEm / SnowEmB / SnowEmC.
- **SnowPool / SnowFall**: tex (+0x2C, holder of the texture DL at +0x60), texW / texH, fillCount, drawn,
  fadeIn / fadeChance, lastCam, follow, filled, visible, rgba (from the ncc_nm_h / ncc_c donor structs).
- **MapLighter**: shape (+0x2C), light0 (+0x30, was src), light1 (+0x34), tgt (the LocalLight), pos (+0x40).

Left as unkNN: fields with no reader in the module (SnowParticle +0x4C, SnowPoint +0x28, SnowSlot +0x08,
SnowRing +0x170 / +0x174 / +0x18C / +0x190 / +0x194 / +0x198 / +0x1F0, BoardTrail +0x1E4 / +0x1F0 / +0x1F4 /
+0x200 / +0x230), BoardTrail +0x1A4 (set to 5 on owner state 98, >= 5 re-arms the powder burst) and +0x1D8
(owner +0xA20 last frame), SnowHit +0x10, SnowColourItem +0x3C (game.uso ColourSubItem's unk3C has no
reader either), LocalLight pads.

**Next:** the owner class at SnowRing +0x2C (the rider: +0x9A0 groundSurface, +0x9A2 state, +0xA20,
+0xA30 colour; GAME_CLASSES has the DNode layout) so SnowOwner can use the real struct; SnowPoint w[4]
(w[0] the vertical velocity term, w[1] alpha, w[2] alpha decay); the LocalLight pads (+0x240 Parms).
For the bootup owner: bootup_uso_o2_6808.c's two UNNAMED comments at T+0x6E74 / T+0x6EA8 say module 60's
exporter is unknown, but `uso-imports.py callers` resolves both: MapLighter_ctor_00009E88 and
MapLighter_syncLight_00009F44.
