# 1080: snoweffects.uso (snow particles, board / hand trails, map lights)

> Readability pass, agent-c run 798 (branch agent-c: 6e50d3958 pure rename, a99c7d6e6 / 5975c3dd3
> call naming, b2193673a fields + tags). Matching history: docs/1080_NEW_MODULES.md (snoweffects sections).

## Index
- [1. Layout: four TUs](#1-layout-four-tus)
- [2. Classes (from the module's vtables and name strings)](#2-classes-from-the-modules-vtables-and-name-strings)
- [3. Trail virtual slots](#3-trail-virtual-slots)
- [4. Readability state and rules](#4-readability-state-and-rules)

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
| BoardTrail (donor class `SnowEffect`) | Data+0x458 | "board trail" | children: NormalParticles (+0x9C), Powder (+0x98, createPowder), Spec (+0xA0, createSpec); spawn effects A/B/C by flag bits |
| HandTrail | Data+0x59C | "hand trail" | stride 2; placeEnds 0x7960 |
| BoardSpray | Data+0x778 | "board spray" | stride 4; draw / emit / placeEnds / setDefaults overrides |
| SnowColourItemType | Data+0x3C8 / 0x6E8 | | ColourItemType create (0x7D8C; 0x91BC unreferenced twin) |
| LocalLight (SNode) | Data+0x964 | "Local Light", "DynLight::Parms" | ctor 0x9328, Parms at +0x240; lit-vertex list, flicker (Data+0x958 sequences) |
| LocalLightType | Data+0x880 | | SNodeItemType create 0x9E10 |
| MapLighter (was SnowLink) | Data+0x9C4 | "MapLighter" | display = cullLights (cam_isSphereInView over the "lig" items), update 0xA10C, syncLight 0x9F44 |

## 3. Trail virtual slots

| slot | SnowRing | BoardTrail | HandTrail | BoardSpray |
|---|---|---|---|---|
| 10 init | pure | init 0x5FD4 | init 0x78E8 | init 0x7F60 |
| 11 draw (DL) | SnowRing_draw 0x40B4 (setupDL 0x4188) | = | = | draw 0x8C60 |
| 12 emit (from SnowRing_update) | emit 0x47D4 | = | = | emit 0x7FE0 |
| 13 calcWidth (+0x50) | 1.0 (0x4E4C) | lean fade 0x63B4 | base | base |
| 14 placeEnds (probe 0x52D4) | 0x4E5C | = | 0x7960 | 0x8D70 |
| 15 spawn | empty 0x52CC | dispatch 0x634C (A/B/C) | base | base |
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
- The spawnA/B/C and SnowFall_fill donors are spliced (plan cannot prove them): their calls were
  named by hand from the ROM jal relocs and pinned by `name-placeholder-calls.py check`.
- Next: struct names for the donor-only offsets (SnowEffect +0x174..+0x230 effect parameters),
  SnowParticle unk fields from the donor names (gravity, life, decay, size, alpha ...), and the
  SnowColourItemType's actual item kind.
