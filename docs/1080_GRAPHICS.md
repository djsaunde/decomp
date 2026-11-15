# 1080: graphics pipeline (libgdl GfxLib), for a port author

> agent-b run 476, 2026-11-15, 1080 branch agent-b (f00df5e00 [rename, 52 gfx_], 9a27aa26d [headers],
> 54299fbde [DLMark / Window conversions], f15861371 [rename, 1]). Code: game_libs
> `src/game_libs/game_libs_post0b.c` 0x41F90-0x5A9D0 plus NCC donors `game_libs_ncc_*.cpp`.
> Headers: `include/gdl/{dlctx,rcp,window,polyshape,material,light,sprite,node}.h`.
> Addresses are game_libs segment offsets (`nm build/tenshoe.elf` value). Related: docs/1080_ENGINE_CORE.md
> (map of the whole engine core), docs/1080_SYSTEM_LAYER.md (heap, files, hostio).

## Index
- [1. Frame flow](#1-frame-flow)
- [2. The GfxLib global](#2-the-gfxlib-global)
- [3. Display-list building](#3-display-list-building)
- [4. Windows, viewports, matrices](#4-windows-viewports-matrices)
- [5. Microcode](#5-microcode)
- [6. Materials and textures](#6-materials-and-textures)
- [7. Shapes](#7-shapes)
- [8. Lights, fog, hilites](#8-lights-fog-hilites)
- [9. What a port must replace](#9-what-a-port-must-replace)
- [10. Open items](#10-open-items)

## 1. Frame flow

```
app_run (0x34EB4)          timing labels "gfx.Start" / "app.Update" / "app.Display" / "gfx.End"
  gfx_start (0x44DE4)      reset the per-frame DLContexts ("Start", "Anm", "MHupd" timers)
  App_Update (0x41D40)     Node tree update (Node vtable slot 3)
  App_Display (0x41EDC)    Node tree display (slot 2): every ScreenWindow ->
      ScreenWindow_display (0x4C5E4)
          gfx +0x254 = this (the "current window" every emitter writes to)
          perspNorm = gfx_calcPerspNorm(near, far)        -> gfx +0x208
          gfx_dlMarkBegin(&mark15C, dl) ... clear (gfx_clearScreen or a zero quad) ...
          G_DL -> startDL[fbIndex]->frameStart, Vp + G_MOVEMEM (viewport), FogParms_emit
          Window_display (0x4EB54)
              gfx_beginView: gfx_updateLights, gfx_resetModelView, matrix mode = modelview
              gfx_matrixModeProjection; Window_setupView (proj = perspective/ortho); gfx_loadMatrix
              gfx_matrixModeModelView; then the child nodes' display()
                  MNode/QNode/SNode_display: gfx_loadMatrix / gfx_multMatrix / gfx_loadIdentity
                  PolyShape_display / Sprite_display / MorphPoly_display: append Gfx
          gfx_dlMarkEnd; gfx_addWindow (0x48354, "too many windows")
  gfx_end (0x44EDC)        "MorphUpd", "ADrawUpd", "Swap", "DoneSwap", "1GFrame" timers
      gfx_submitFrame (0x4CDB0) -> gfx_queueGfxTask (0x4CEFC)
          gfx_endDL; marked span = gfx_dlMarkStart .. + gfx_dlMarkLength;
          RcpMgr_initTask (F3DEX ucode) + RcpMgr_queueTask
      gfx_swapBuffer (0x46B64): osViSwapBuffer + gfx_waitRetrace
RcpMgr thread: RcpMgr_service (0x4D688) receives retrace / RSP / RDP / audio messages,
  RcpMgr_startTask (0x4DA40) -> osSpTaskLoad / osSpTaskStartGo; gfx tasks can be yielded
  for audio tasks ("SndRSP", gl_osSpTaskYielded, "gfx-resume").
```

GfxLib_init (0x445AC) at boot: two size pairs (320, 240) (gfx_setSizePairA/B), "MainStatic" heap,
the main ScreenWindow (gfx +0x240), "MainStaticDL" (gfx +0x214, the static list materials and the
font are compiled into), "OneFrame" DLs (+0x280 / +0x284), the RcpMgr (+0x218), the message queue.
GfxLib_reset (0x44918) clears the per-frame state, resets FogParms, waits for the RCP to go idle.
gfx_setVideoMode (0x44B78) picks the VI mode ("video mode not supported").

## 2. The GfxLib global

One data object in the bootup.uso data section, reached as `&D_00000000 + K` (a USO base
placeholder; do not retype it as a struct in matched code, see READABILITY_PLAN section 9 rule 4e).
Known fields:

| off | meaning | evidence |
|---|---|---|
| 0x60 | projection matrix (f32[4][4]) | gfx_matrixModeProjection points +0xE0 here |
| 0xA0 | modelview matrix | gfx_matrixModeModelView, gfx_resetModelView |
| 0xE0 | current matrix pointer | gfx_loadMatrix / multMatrix / loadIdentity |
| 0x18C | light list head (Link {obj, next}) | gfx_updateLights, gfx_setLightDirs, gfx_selectLights |
| 0x1C4 | flags (bit 1 cleared by gfx_beginView; bit 2 = clear with a zero quad) | ScreenWindow_display |
| 0x1F4 | matrix mode (1 projection, 0 modelview) | gfx_matrixMode* |
| 0x1F8 | 3-4 signed bytes (float * 127) | 0x47AB4 / 0x47AD8, role open |
| 0x204 | frame-buffer index (0 / 1) | ScreenWindow_display, gfx_clearFbRect |
| 0x208 | perspNorm (u16) | gfx_calcPerspNorm -> gfx_emitPerspNorm |
| 0x214 | MainStaticDL (DLContext *) | gfx_callStaticDL, MorphPoly_init |
| 0x218 | RcpMgr * | GfxLib_hostioParms, GfxLib_reset busy-wait |
| 0x240 | main ScreenWindow * | GfxLib_init, gfx_drawFbChar / gfx_drawFbSplash / gfx_clearFbRect |
| 0x254 | current ScreenWindow * (emitters write to ->dl at +0x158) | ScreenWindow_display, gfx_emitRenderState, FogParms_emit |
| 0x28C | word set by 0x46788 (GfxLib_reset, TextWin_draw) | role open |
| 0x2AC | 51 words zeroed by GfxLib_reset | |

## 3. Display-list building

`DLContext` (dlctx.h, 0x7C) = six growable buffers {base, count, max, cur}: Gfx (8 bytes), Vtx (0x10),
Light (0x48), Mtx (0x40), Vp (0x10), Hilite. Every emitter appends with
`n = ctx->gfx.cur->count++; Gfx *g = ctx->gfx.cur->base + n*8; g->w0 = ...; g->w1 = ...;`.
gfx_newDLContext (0x56580) / gfx_resetDLContext / gfx_endDL (G_RDPPIPESYNC + G_ENDDL, then the
overflow report) / gfx_printDLUsage. `DLMark` (window.h) records a [start, end) Gfx span of a context
(gfx_dlMarkBegin / End / Length / Start); the frame task is the span between the two marks.

Emitters (0x56580-0x5A2C4): gfx_emitRenderMode / CombineMode / Combine1 / Combine2 / GeometryMode /
CycleType / Fog, gfx_setColorImage / setDepthImage, gfx_loadTexture, gfx_initRDPState (other modes, combiner,
blend / prim colour, depth image, G_MOVEWORD setup), gfx_clearScreen (fill-mode rect over colour and Z),
gfx_emitPerspNorm (G_MOVEWORD G_MW_PERSPNORM), gfx_endDLFullSync (G_RDPFULLSYNC + end),
gfx_callStaticDL (G_DL into MainStaticDL), gfx_emitStateAndPrimColour (state + G_SETPRIMCOLOR
from an RGBA5551 short), gfx_emitRenderState (the 4 state emitters, each skipped when its
field is 0), gfx_setPrimColour / setEnvColour / setBlendColour, gfx_fillRect (RDP rect, or the CPU
path gfx_clearFbRect). "DDM" hooks (gfx_addDdm / callDdm / getDdm, GDL_MAX_DDM) are per-frame
callbacks that append their own state (gfx_initDdm sets their default render state).

The GBI is **F3DEX 1.x** (opcodes seen in the emitters: 0x01 G_MTX, 0x04 G_VTX with
(n << 10 | n*16 - 1), 0xB5 G_LINE3D, 0xB6/0xB7 G_CLEAR/SETGEOMETRYMODE, 0xB9/0xBA
G_SETOTHERMODE_L/H, 0xBB G_TEXTURE, 0xBC G_MOVEWORD (PERSPNORM 0x0E, FOG 0x08, segments / clip),
0xC0 G_NOOP, 0x06 G_DL, 0xE7 G_RDPPIPESYNC, 0xE9 G_RDPFULLSYNC, 0xF8 SETFOGCOLOR, 0xF9 SETBLENDCOLOR,
0xFA SETPRIMCOLOR, 0xFC SETCOMBINE, 0xB8 G_ENDDL). A port that interprets the lists should take Fast3D/F3DEX1
semantics (e.g. the gbi.h with F3DEX_GBI, not F3DEX_GBI_2).

CPU frame-buffer drawing exists for debug output: gfx_drawText (0x46050) -> gfx_drawFbChar (8x8 font,
320-wide RGBA5551), gfx_drawFbSplash (128x128 image centred), dbg_screenOverlay_00042938.

## 4. Windows, viewports, matrices

`Window` (window.h, 0x144) / `ScreenWindow` (0x1CC). Window: projection at +0x30, camera (MCamera)
at +0x70, flags +0x78, projType +0x7C (1 = perspective from the camera fov, else ortho of the
frame-buffer size), near/far/aspect +0xAC-0xB4, frame-buffer width/height +0xB8/+0xBC, viewport
vpW/vpH/vpX/vpY +0xC8-0xD4, Z buffer +0xF0, colour buffers +0xF4/+0xF8 (RGBA5551, one allocation
+0xFC). ScreenWindow: fbIndex +0x144, fbOwner +0x148, per-buffer "startdraw" / "bg" / "setupDyn"
DLContexts, current dl +0x158, two DLMarks +0x15C/+0x168.

The viewport becomes a `Vp` with vscale = (vpW*2, vpH*2, 0x1FF), vtrans = (vpX*4 + vpW*2, ..., 0x1FF)
(RSP quarter-pixel units). The software matrix stack is OpenGL-like: gfx_matrixModeProjection /
gfx_matrixModeModelView select +0x60 / +0xA0, gfx_loadMatrix copies in, gfx_multMatrix
premultiplies (cur = a * cur), gfx_loadIdentity. Matrices are float 4x4 (math_* in 0x5BBEC-0x5FD20);
they are converted to the RSP fixed-point Mtx (guMtxF2L style) when a node emits G_MTX into the
DLContext Mtx buffer. A port can keep the float matrices and skip the conversion.

## 5. Microcode

RcpTask (rcp.h) setters, from the ucode_data blocks in bootup .data:

| setter | ucode | used |
|---|---|---|
| RcpTask_setUcodeF3DEX (0x4D254) | F3DEX 1.23 (gfx) | yes, RcpMgr_initTask: the main 3D task |
| RcpTask_setUcodeF3DLP_Rej (0x4D2D0) | F3DLP.Rej (low precision, clip-reject) | yes, RcpMgr_initTask alternative |
| RcpTask_setUcodeF3DLX_Rej (0x4D304) | F3DLX.Rej | not called |
| RcpTask_setUcodeF3DEX_NoN (0x4D338) | F3DEX.NoN (no near clip) | not called |
| RcpTask_setUcodeSgi20H* (0x4D16C / 88 / 1C0 / 1F4) | SGI "RSP SW Version: 2.0H" Fast3D-family (fifo / dram output variants) | not called |
| RcpTask_noUcode_fastQ / _NoC | unsupported (sys_fatal "fastQ" / "NoC") | |

Task: type 1 (M_GFXTASK), rspboot from cart 0xB0000B70, ucode size 0x1000, data 0x800, yield buffer
0xC00. The audio task goes through the same RcpMgr (docs/1080_AUDIO.md). For a port: the only
display-list semantics that matter are F3DEX 1.23 (F3DLP.Rej uses the same command set with
lower-precision clipping).

## 6. Materials and textures

`BaseMat` (material.h, 0x60; vptr at +0x5C) / `Mat` (0x90). Texture fields: texels +0x1C, width/height
+0x20/+0x22 (s16), format +0x24 (0x110 for a frame-buffer texture; 0x508 / 0x608 carry a 0x200-byte
TLUT), texFlags +0x28 (0x10 = texels points to an image record), geomFlags +0x38 (bit 20 texgen,
bit 24 texgen linear). Material state is compiled once into MainStaticDL; drawing a material is a
G_DL (gfx_callStaticDL) into that span. BaseMat_vslot4 (0x437C0) rebuilds a material list (lights via
gfx_setLightDirs); gfx_setupMatTextures (0x45E20) sets texgen + G_TEXTURE scale and calls
gfx_loadTexture (0x578B4, 0x25CC bytes: tile/LOAD_BLOCK/TLUT per format, "bad texfmt num %d",
"unkown tile") per texture; gfx_flushTexture writes texels and TLUT back from the CPU cache;
gfx_assertTexAligned ("Texture not aligned"). GDL_MC material commands: gfx_decodeMatCmd (0x51694+),
Mat_fromFrameBuffer (render-to-texture from a ScreenWindow), Mat_clone.

## 7. Shapes

- `BasePolyShape` (polyshape.h, 0xB0): s16 vertex rows (+0x60), PolyTri {flags, v[3]} (+0x68), face /
  vertex normals, RGB888 palette, remap table; built from a GDL shape command stream
  (BasePolyShape_parse / parseCmd / parseMats, 0x4F9E4-0x54144); ZoneShape.
- `PolyShape` (0xC0): PolyShape_init (0x493AC) compiles the geometry once into MainStaticDL
  ("genpoly": G_VTX batches and triangles, built through PolyShape_addFace, "face overflow");
  PolyShape_display (0x48AEC) then only emits G_MTX (0x01020040, modelview load), the material
  state / G_SETPRIMCOLOR and G_DL (0x06) into the static span. Line shapes use gfx_vtxBatchBegin /
  gfx_findVtx / gfx_findFaceVtxs (dedupe vertices within a batch) and gfx_emitLineBatch
  (G_VTX + G_LINE3D with width); gfx_makeVtx builds a Vtx (ob, tc, colour/normal, alpha).
  PolyShape_shade (0x49DBC) computes vertex colours or packed normals (gfx_floatToS8x3)
  ("No PNorms for flat shading").
- `MorphPoly` (0xDC): per-frame vertex rewrite (MorphPoly_setVerts, MorphPoly_applyUpdateList over the
  -1 terminated update list, MorphPoly_update / updateColours, "Morphpoly: nothing to update");
  SkinMgr (skin.cpp, 0x68C14+) drives it.
- `Sprite` (sprite.h, 0xD8): textured 2D quads; its "SS StartDL" sets 1-cycle, render mode, texture
  filter and G_TEXTURE once ("SS EndDL", "sprblock").
- Shadow (Shadow_ctor 0x4B0A8): projected blob.

## 8. Lights, fog, hilites

`BaseLight` (light.h, 0x138) on the gfx light list; `LightTarget` (0x16C, "lighttarget") selects the
lights whose mask matches (gfx_selectLights: direction = light pos - target, normalised). Per frame:
gfx_updateLights (cache positions, dirty flag), gfx_transformLightDirs (into eye space),
gfx_setLightDirs (Lights block: dir bytes = dir * 120 at +0x10 + 16*i after the 8-byte ambient).
gfx_makeLookAt fills a LookAt (two Light_t, guLookAtReflect layout) for reflection mapping;
gfx_calcHilite computes hilite texture coordinates (guLookAtHilite form, 32x32 hilite).
FogParms (0x18: colour f32[4], min, max; "FogParms" / "Min" / "Max"): FogParms_set / setDefault
(white, 996..1000) / lerp / emit (gfx_emitFog: G_SETFOGCOLOR + G_MW_FOG).

## 9. What a port must replace

1. **RCP execution**: RcpMgr / RcpTask, osSpTaskLoad/StartGo, the yield logic. Replace with an
   F3DEX 1.x display-list interpreter (or hook the emitters directly and skip the GBI).
2. **VI / frame buffers**: gfx_setVideoMode, osViSwapBuffer, gfx_waitRetrace, the RGBA5551 colour and
   Z buffers ScreenWindow_allocBuffers carves out of the heap. CPU drawing into the frame buffer
   (gfx_drawText / drawFbChar / drawFbSplash / clearFbRect, Mat_fromFrameBuffer render-to-texture)
   needs a readable/writable colour buffer in the port.
3. **Fixed-point conversions**: Mtx (guMtxF2L), Vp quarter-pixel units, perspNorm (G_MW_PERSPNORM,
   ignore on a float pipeline), s8 normals (gfx_floatToS8x3), Light_t dir bytes.
4. **Texture formats**: gfx_loadTexture's format table (format codes such as 0x110, 0x508 / 0x608
   with a TLUT; the full code -> G_IM_FMT/SIZ table is not decoded yet) and TMEM tiling; texgen (G_TEXTURE_GEN) environment mapping and hilites.
5. **Cache / physical addresses**: osVirtualToPhysical in every G_DL / G_VTX word (gl_func_0006C384),
   osWritebackDCache (gfx_flushTexture). Both become no-ops.
6. Keep: the DLContext / Node / Window structure, the matrix stack, materials, shapes and lights are
   plain C/C++ data and logic.

## 10. Open items

- Roles still open (kept as `gfx_func_` / factual names): 0x43D2C (copies +0x64), 0x453A8 (two libm calls
  on floats, results unused), 0x46788 (gfx +0x28C), 0x46B44 (gfx_vcall thunk), 0x47AB4 / 0x47AD8
  (gfx +0x1F8 bytes), 0x47F68 (gfx +0x188 / +0x1E0 mode), 0x4E138 ((gfx +0x14 & 3) == 0);
  gfx_setSizePairA/B (which of the two 320x240 pairs is screen vs frame buffer); the five
  gfx_emptyStub_ (likely vtable slots).
- Not converted to the new structs yet: ScreenWindow_display (NCC donor with its own local struct),
  Window_setupView, ScreenWindow_allocBuffers, LightTarget_ctor, BaseLight_ctor, BaseMat_init,
  MorphPoly_init, Sprite_ctor (has its own Obj620 view). Window/ScreenWindow fields between 0x100 and
  0x144 and 0x174-0x1C0 are mostly unnamed.
- A typed model of the GfxLib global (section 2) for documentation; matched code must keep the
  `D_00000000 + K` form.
