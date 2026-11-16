# 1080: graphics pipeline (libgdl GfxLib), for a port author

> agent-b run 476, 2026-11-15, 1080 branch agent-b (f00df5e00 [rename, 52 gfx_], 9a27aa26d [headers],
> 54299fbde [DLMark / Window conversions], f15861371 [rename, 1]). Run 481: 8b26df4ee [conversions,
> material.h MAT_FMT_*], ef315c9e8 [rename, 4]; sections 6.1 / 6.2 / 7.1 (texture formats, material
> and shape command streams) are new. Run 486: b55b99e94 [include/gdl/anim.h], 911bbf50e [rename, 18],
> e2fd6a234 [anim conversions], e5f211c67 [include/gdl/skin.h], 534001550 [gGfxLib, 43 sites];
> sections 11 / 12 (animation and skinning formats) are new. Code: game_libs
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
- [11. Skeletal animation (animate.cpp)](#11-skeletal-animation-animatecpp)
- [12. Skinning (skin.cpp)](#12-skinning-skincpp)
- [13. Run 500 (agent-b): structs for the post0b engine classes](#13-run-500-agent-b-structs-for-the-post0b-engine-classes)
- [14. Run 511 (agent-b): DNode, PhysQNode, Friction](#14-run-511-agent-b-dnode-physqnode-friction-includegdldnodeh)
- [15. Run 515 (agent-b): controllers, packed files, BallRotator](#15-run-515-agent-b-controllers-packed-files-ballrotator)

## 1. Frame flow
- [16. Run 521 (agent-b): pad renames, InputPad = PadCtl, CollShape, DL packets](#16-run-521-agent-b-pad-renames-inputpad--padctl-collshape-dl-packets)
- [17. Run 527 (agent-b): GfxLib struct, PolyShape_shade, texload, fault_printThread](#17-run-527-agent-b-gfxlib-struct-polyshape_shade-texload-fault_printthread)

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
placeholder; rule 4e keeps the symbol and K). Since run 527 the layout is the **GfxLib** struct in
include/gdl/gfxlib.h, reached as `gGfx->field` (= `((GfxLib *)&gGfxLib)->field`, the same K) or
`GFXLIB(&alias)->field` for the per-site aliases; see section 17.
Source spelling since run 486: `gGfxLib` (include/gdl/gl_data.h: Bss+0x3C168, Sym 154, 0x5D8 bytes), so
`(char *)&gGfxLib + 0x254`. 43 game_libs sites converted in run 486; run 489 added the 19 bootup_uso
sites (`convert`), Snower_display, MapProp_display and the gfx NCC donors whose base is CSE'd at K = 0
(Fader / ColourItem / PolyShape_shade / PolyShape_vslot12 / Sprite_display / RcpMgr_func_00043D38 /
light_setMirrorMatrix, the post0b GS4B / G240_4C300 macros). Per-site aliases (`gGfxLib_2c94_ctx`, ...)
keep their own symbols. Proof rule for a hand conversion: `sites FUNC` shows every D_00000000 LO16 at
that K naming Sym 154. Known fields:

| off | meaning | evidence |
|---|---|---|
| 0x0 | every-4th-frame flag: (gSysLib frame counter & 3) == 0 | gfx_setEvery4thFrameFlag (last call of gfx_end); PolyShape_display tests it |
| 0x130 | f32 scale (multiplies camera +0xA8 distances) | MapProp_display, Fog_display, Snower_display |
| 0x188 / 0x1E0 | view stage (0 projection, 1 modelview) / stage == 0 | gfx_setViewStage_00047F68, called twice by Window_display |
| 0x190 | the shadow light (MNode, position +0xA0) | gfx_setShadowLight / gfx_getShadowLight; "no shadowlight" |
| 0xE4 | extra model matrix pointer (shadow / mirror) | light_setShadowMatrix / light_setMirrorMatrix set it, PolyShape_display reads it |
| 0x20C | frame time (u32 prof_timerRead("OneFrame") at init; "WARNING: zero v frame time" below 10) | GfxLib_init, sys_timeInFrames |
| 0x60 | projection matrix (f32[4][4]) | gfx_matrixModeProjection points +0xE0 here |
| 0xA0 | modelview matrix | gfx_matrixModeModelView, gfx_resetModelView |
| 0xE0 | current matrix pointer | gfx_loadMatrix / multMatrix / loadIdentity |
| 0x18C | light list head (Link {obj, next}) | gfx_updateLights, gfx_setLightDirs, gfx_selectLights |
| 0x1C4 | flags (bit 1 cleared by gfx_beginView; bit 2 = clear with a zero quad) | ScreenWindow_display |
| 0x1F4 | matrix mode (1 projection, 0 modelview) | gfx_matrixMode* |
| 0x1F8 | s8 unit vector (float * 127) + pad | gfx_setDirBytes_00047AB4 / gfx_setDirFromVec_00047AD8; no reader in bootup.uso |
| 0x204 | frame-buffer index (0 / 1) | ScreenWindow_display, gfx_clearFbRect |
| 0x208 | perspNorm (u16) | gfx_calcPerspNorm -> gfx_emitPerspNorm |
| 0x214 | MainStaticDL (DLContext *) | gfx_callStaticDL, MorphPoly_init |
| 0x218 | RcpMgr * | GfxLib_hostioParms, GfxLib_reset busy-wait |
| 0x240 | main ScreenWindow * | GfxLib_init, gfx_drawFbChar / gfx_drawFbSplash / gfx_clearFbRect |
| 0x254 | current ScreenWindow * (emitters write to ->dl at +0x158) | ScreenWindow_display, gfx_emitRenderState, FogParms_emit |
| 0x28C | CPU-draw flag: gfx_drawText / gfx_fillRect draw into the frame buffer when set | gfx_setCpuDraw (0x46788): TextWin_draw and the debug sprintf set 1 then 0, GfxLib_reset 0 |
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

Run 489 (window.h): originX / originY +0xC0 / +0xC4 (Window_doCommand 110 sets them with vpX / vpY;
the clear rectangle's corner), clearColour f32[4] +0xDC (flag 0x4 = clear colour), clearFlags +0x104
(bit 2 with flag 0x2 = clear Z), displayMask +0x108 (Node_setDisplayMask in Window_display), two
4-entry hook lists: taskHooks +0x124 / nTaskHooks +0x11C (Window_addTaskHook; Window_runTaskHooks runs
them from RcpMgr_startTask on the task's window) and hooks +0x134 / nHooks +0x120
(Window_addHook_0004EDEC / Window_runHooks_0004ED0C); both counts are zeroed by Window_display.
ScreenWindow clearAlpha +0x1B0 = the RGBA5551 alpha bit of the clear fill. New windows copy their
defaults from gWindowDefaults (Bss Sym 324, 0x40 bytes) in Window_setDefaults. Window_projectPoint
maps a point through proj to frame-buffer pixels (0 when behind the eye). Window_display's order:
gfx_setViewStage(0), gfx_matrixModeProjection, Window_setupView, gfx_loadMatrix(proj),
gfx_setViewStage(1), gfx_matrixModeModelView, gfx_loadIdentity, gfx_emitProjection (guMtxF2L of the
projection into the DL, G_MTX projection load, three gfx_makeLookAt into gLookAt* objects).
gfx_setScreenSize (Data Syms 1853/1854, 320x240) is the size GfxLib_init gives the main ScreenWindow.

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
gfx_assertTexAligned ("Texture not aligned"). GDL_MC material commands: gfx_decodeMatCmd (0x51AD8),
Mat_fromFrameBuffer (render-to-texture from a ScreenWindow), Mat_clone.

More BaseMat fields (run 481, material.h): id +0x18 (-1; "MAT %d", "unknown mat(%d) size %d"),
shiftS / shiftT +0x2C / +0x2E, render tile +0x3C, next texture +0x40 (multi-texture chain), name
+0x44 ("<no name>"); geomFlags bit 22 = textured (Mat_print shows "Tex" vs "RGB").

### 6.1 Texture formats (gfx_loadTexture 0x578B4, NCC donor game_libs_ncc_578B4.cpp)

`format` = (component kind << 8) | bits per texel. hostio_sendImage computes the image size as
`(fmt & 0xFF) * w * h / 8` (+ 0x200 for 0x508); gfx_texelBytes (0x52144) returns 4 / 2 / 1 / 0.5
(else "unknown mat(%d) size %d"); gfx_texImageBytes = texelBytes * w * h, gfx_texRowBytes = texelBytes * w.
The G_SETTIMG / G_SETTILE words in each arm give the N64 format (macros `MAT_FMT_*` in material.h):

| code | N64 format | whole-texture load (no record) | image-record load (texFlags 0x10) |
|---|---|---|---|
| 0x120 | G_IM_FMT_RGBA, 32b | RGBA32 LoadBlock | RGBA32 LoadTile |
| 0x110 | G_IM_FMT_RGBA, 16b (also every frame-buffer texture) | RGBA16 LoadBlock | RGBA16 LoadTile |
| 0x408 | G_IM_FMT_IA, 8b | loaded as IA 16b (w*h/2 texels), render tile IA8 | IA8 LoadTile |
| 0x308 | G_IM_FMT_I, 8b | loaded as I 16b, render tile I8 | I8 LoadTile |
| 0x304 | G_IM_FMT_I, 4b | loaded as I 16b (w*h/4), render tile I4 | loaded as I8 at width/2 (LoadTextureTile_4b), render tile I4 |
| 0x508 | G_IM_FMT_CI, 8b + 256-entry RGBA16 TLUT | TLUT, then CI as 16b, render tile CI8 | TLUT, then CI8 LoadTile |
| 0x608 | 1 byte/texel + 0x200-byte TLUT (texelBytes, flush and size code accept it) | **rejected**: "bad texfmt num %d" | rejected: "unkown tile" |

Every load starts with G_SETOTHERMODE_H G_MDSFT_TEXTLUT = G_TT_NONE (0xBA000E02, 0), or G_TT_RGBA16
(0x8000) after a CI8 TLUT. The TLUT load is G_SETTIMG RGBA16 (the palette), G_RDPTILESYNC,
G_SETTILE tile 7 at TMEM 0x100 (64-bit words: the upper half), G_RDPLOADSYNC, G_LOADTLUT count 255
(0x073FC000), G_RDPPIPESYNC. CI textures go through a CI record: `*(texels)` -> {+0x8 pixels,
+0xC palette}.

- **Whole-texture path** (texFlags & 0x10 clear; the gbi gDPLoadMultiBlock form): pixels at
  `texels`, TMEM address = gfx_loadTexture's 3rd argument (& 0x1FF, 64-bit words), render tile =
  `tile` (& 7), shifts = shiftS / shiftT, LoadBlock with texels-1 clamped to 0x7FF and
  dxt = (0x7FF + w/8) / (w/8) (CALC_DXT). Port caveat: the shipped CI8 arm of this path reads the
  record pointer (and the LoadBlock width / height from it) from a stack slot that only the record
  path writes (0x59A04 `lw a2,476(sp)`), so CI8 is only well-defined with MAT_TEX_RECORD set.
- **Image-record path** (texFlags & 0x10; the gbi gDPLoadTextureTile form): `texels` points to a
  record {+0x0 image (or the CI record), +0x4 uls, +0x8 ult, +0xC image width, +0x10 image height};
  the texture is the (width x height) sub-rectangle at (uls, ult) of the wider image, loaded through
  tile 7 at TMEM 0 into render tile 0 (no shifts), SETTILESIZE from (0, 0).
- **Wrap / mask** (both paths): masks / maskt = 0x62F08(width) / (height) (log2); cms from texFlags
  0x100 (wrap, wins) / 0x200 (G_TX_CLAMP) / 0x400 (G_TX_MIRROR), cmt likewise from 0x1000 / 0x2000 /
  0x4000 (`MAT_TEX_*`).
- **gfx_setupMatTextures** (0x45E20): geomFlags bit 20 -> G_SETGEOMETRYMODE G_TEXTURE_GEN (+
  G_TEXTURE_GEN_LINEAR with bit 24), texFlags |= 0x1100 (wrap S and T), G_TEXTURE scale 1984 / 1984
  (3968 for S on a 64-wide texture); otherwise G_CLEARGEOMETRYMODE G_TEXTURE_GEN and scale 0xFFFF.
  The G_TEXTURE word is 0xBB040801 (tile 0, on). Then it walks the `next` chain, numbering `tile`
  0, 1, ..., calling gfx_loadTexture(ctx, mat, tmem) and advancing tmem by gfx_texImageBytes / 8;
  then G_RDPPIPESYNC.

### 6.2 Material commands (GDL_MC, gfx_decodeMatCmd 0x51AD8, donor game_libs_o2_51AD8.c)

A stream of s32 words `{op, args...}` decoded into a BaseMat; unknown ops print
"unknown GDL_MC cmd %d".

| op | args | effect |
|---|---|---|
| 200 | 1 | skipped |
| 201 | - | sub-parse (callee gets (stream, mat)) |
| 202 | index (+4 words) | copy the colour from table [index] (Data +0x160) if set, else sub-parse |
| 203 | format, texels, width, height, texFlags, shiftS, shiftT | the texture (section 6.1) |
| 204 | geomFlags | +0x34 = 0, geomFlags = arg |
| 205 / 206 | mask | geomFlags \|= mask / &= ~mask |
| 207 | word | +0x34 = word |
| 208 | name | look up a shared record: +0x48 = it, +0x34 / +0x38 = its words 1-2 |
| 209 | name | name (+0x44) |
| 210 | 4-char code | +0x58 = the 4 bytes, +0x32 = code[0], +0x30 = hex(code[1]) << 8 \| hex(code[2]) |
| 211 | index | copy the whole material from the global table [index] (Data +0x148); "No glbMat" if empty |

BasePolyShape_parseMats (0x51F5C, NCC donor game_libs_ncc_51F5C.cpp) is the token loop around it
("too many materials", "Too many objects for List", "no parent mat", "unknown MatCmd cmd %d").

## 7. Shapes

- `BasePolyShape` (polyshape.h, 0xB0): s16 vertex rows (+0x60), PolyTri {flags, v[3]} (+0x68), face /
  vertex normals, RGB888 palette, remap table; built from a GDL shape command stream
  (BasePolyShape_parse / parseCmd / parseMats, 0x4F9E4-0x54144; format in 7.1); ZoneShape.
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

### 7.1 Shape command stream (BasePolyShape_parse 0x52CD4, donor game_libs_o2_52CD4.c)

The on-cartridge shape is a stream of s32 words: `op = word & 0xFFFF`, then the op's arguments, until
op 2 (end). Pointers in the stream are already-relocated addresses of arrays in the same asset.
Field names refer to polyshape.h (BasePolyShape).

| op | args | effect |
|---|---|---|
| 0 | - | lit flag: normals are generated with lighting (passed to the normal generator) |
| 1 | - | no-op |
| 2 | - | end of stream |
| 4 | ptr | +0x64 |
| 6 | word | call (shape, word) |
| 7 | word | +0x78 |
| 8 | word | +0x7C, flags(+0x38) \|= 8 |
| 9 | word | +0x50 |
| 10, 19 | 1 | skipped |
| 11 / 21 | bool | flags(+0x38) bit 0x2000 / 0x4000 |
| 12 | word | +0x98 |
| 18 | int | +0x9C = int / 10000.0f (default 1.0) |
| 20 | bool | run a post-pass on the shape after parsing |
| 25 | ptr | palette (+0x5C, RGB888) |
| 26 | n, ptr | +0x44 (nTris) = n, +0x4C = ptr |
| 27 | n, ptr | nVerts (+0x40), verts (+0x60, s16 x/y/z rows) |
| 28 | n, ptr | nTris (+0x44), tris (+0x68, PolyTri {u16 flags, u16 v[3]}); enables the normal pass |
| 29 | n, ptr | materials: "Mats", +0x8C = n, +0x80 = ptr, +0x84 = alloc(n*4); BasePolyShape_parseMats on the GDL_MC stream (6.2) |
| 30 | ptr, ptr | +0x48, +0x6C |
| 31 | - | "parsed materials broken" (error) |
| 32 | ptr, ptr | +0x74, remap (+0x70, 3 u16 per vertex) |
| 34 | ptr, ptr | vtxNormals (+0x58), faceNormals (+0x54) (f32[3] each) |
| 35 | word | +0xA0 |
| 36 | 3 | "shape scale dont work mate" (unsupported) |
| other | | BasePolyShape_parseCmd (0x5231C): 3 = Node +0xC; 13 / 14 = node flags(+0x30) bit 2 / 1; 15 / 22 / 23 = flags(+0x38) bit 2 / 1 / 0x20000; 17 = +0x30 bit 4 then bit 2; 24 = flags(+0x38) \|= word; anything else "Invalid Shape cmd %d" |

After op 2: with tris present (op 28) and no palette (+0x5C) and no vertex normals, allocate
nVerts * 0xC vertex normals; without face normals allocate nTris * 0xC; then generate them
(palette shapes get the one-argument variant, others (shape, lit, 1)). Unless gfx flag 0x100 is set
the face-normal array is freed after use. A port can load these streams directly; every array is
big-endian (byte-swap s16 / u16 / f32 on a little-endian host).

## 8. Lights, fog, hilites

`BaseLight` (light.h, 0x138) on the gfx light list; `LightTarget` (0x16C, "lighttarget") selects the
lights whose mask matches (gfx_selectLights: direction = light pos - target, normalised). Per frame:
gfx_updateLights (cache positions, dirty flag), gfx_transformLightDirs (into eye space),
gfx_setLightDirs (Lights block: dir bytes = dir * 120 at +0x10 + 16*i after the 8-byte ambient).
gfx_makeLookAt fills a LookAt (two Light_t, guLookAtReflect layout) for reflection mapping;
gfx_calcHilite computes hilite texture coordinates (guLookAtHilite form, 32x32 hilite).
BaseLight HostIO parms (BaseLight_hostioParms): "Atten" +0xC8 (0..8000), "FallOff" +0xCC (0..1000),
"MaskID" +0xD0; the ctor sets dir = (0, 1, 0), intensity 1, mask 0xFFFF. Shadows and reflections:
SnowBoarder_display calls light_setMirrorMatrix_00054E78 (Householder reflection about a plane) and
light_setShadowMatrix_00054D04 (projection away from the shadow light, gfx_getShadowLight = GfxLib
+0x190); both build a matrix at their object's +0x12C and point GfxLib +0xE4 at it, which
PolyShape_display multiplies in. A port can do planar shadows / mirrors the same way.
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
4. **Texture formats**: the section 6.1 table (RGBA32 / RGBA16 / IA8 / I8 / I4 / CI8 with an RGBA16
   TLUT; convert to host formats at load time) and the TMEM layout (a multi-texture material packs
   its textures back to back from TMEM 0, render tiles 0..n); texgen (G_TEXTURE_GEN) environment
   mapping and hilites.
5. **Cache / physical addresses**: osVirtualToPhysical in every G_DL / G_VTX word (gl_func_0006C384),
   osWritebackDCache (gfx_flushTexture). Both become no-ops.
6. Keep: the DLContext / Node / Window structure, the matrix stack, materials, shapes and lights are
   plain C/C++ data and logic.

## 10. Open items

- Run 489 named the `gfx_func_` leftovers from their bodies and their TextReloc-resolved callers
  (R_MIPS_26 relocs name the callee Sym; new `scripts/uso-data-sites.py calls FUNC` / `calls --to FUNC`
  lists them, which resolves every `gl_func_00000000` placeholder call inside bootup.uso):
  gfx_setEvery4thFrameFlag, gfx_setViewStage_00047F68,
  gfx_setDirBytes / gfx_setDirFromVec, gfx_setScreenSize (+ gfx_setScreenSize2_00044CB0, no reader),
  kind-only gfx_copyField64_00043D2C / gfx_floatPairThunk_000453A8 / gfx_thunk_00046B44.
  The five gfx_emptyStub_ are exported but have no bootup.uso caller (kept).
- Profiler (compiled out; names from 20+ callers and their name strings): prof_timerStart /
  prof_timerStop ("MorphUpd", "ADrawUpd", "1GFrame", "OneFrame"), prof_beginSection / prof_endSection
  ("CPU", "Display()"), prof_timerRead_0004DD2C / _0004DD3C (return 1.0f), prof_timerReset_0004DD4C
  ("MHupd", "Anm"); gGfxPhase_* = Bss Sym 1850, the gfx_start / gfx_end phase label ("Start", "End",
  "Swap", "DoneSwap"). A port can drop all of it.
- Converted in run 481: Window_setupView, ScreenWindow_allocBuffers, LightTarget_ctor (now
  shape_cmdLightTarget, the GDL command that creates the node), BaseMat_init, MorphPoly_init, the
  Sprite_ctor cfe reference body. The ScreenWindow_display NCC donor keeps a local view (its member
  types carry the match) but its fields now use the window.h names. Run 489 converted BaseLight_ctor
  (light.h fields, the vptr stores; its stale 150-line decode comment replaced), the Sprite_ctor NCC
  donor (sprite.h member names, Sprite_vtbl, GBI comments), Window_setDefaults and Window_projectPoint.
- Row clipping (run 489): Window clipRowLo / clipRowHi (+0x10C / +0x110, set by MapProp_display,
  0..127) select which rows of a row-structured shape are drawn. PolyShape_clipToWindow_00049308 walks
  the shape's +0x84 elements whose row span (+0x50 / +0x54) overlaps, and PolyShape_clipRows_00043D38
  rewrites each element's row DL (rows outside become gDPNoOp, the head branches to the first kept
  row, the row after hi ends the list). RcpMgr_startTask runs it on RcpTask.clipShape (+0x70) with
  RcpTask.window (+0x74) as the current window. A port can cull rows on the CPU instead.
- Node_runCommands_00038C04 / Node_runCommandArgs_00038C70 (were ScreenWindow_func_*): the GDL
  command loop (vtable +0x38 doCommand per opcode until 0); ScreenWindow_ctor passes its varargs.
- Window / ScreenWindow: still unnamed Window +0x100, +0x114 / +0x118 (4-byte members the ctor zeroes), +0x80 / +0x84[5] / +0x98[5] (floats:
  defaults 50000 / {0, 2200, 3000, 19584, 12500}, scaled by 85 / fov into +0x98); ScreenWindow
  +0x174, +0x188, +0x1A0-0x1AC, +0x1B4 (PolyShape_stub_0004C20C writes it; probably a ScreenWindow
  method), +0x1B8, +0x1BC.
- Anim / skin: run 489 converted the frame-cache loops (SLOT_AT keeps the byte-offset address),
  allocSlot, the anim_blendPose donor (Animator / AnimPose views), SkinAnim_ctor, SkinMgr_reset, the
  SkinAnim_bind donor and the SkinAnim_bind / skinVerts / SkinMgr_update NM bodies. skin_cmdSkinMgr's
  NM body only got string annotations (its comments name its locals).
- Run 489 also named Window_projectPoint, BasePolyShape_getFaceNormal / sampleTri /
  getMatCodeChar / getMatCodeNum, MorphPoly_allocUpdateList / morphAll, PolyShape_buildStateDL,
  gfx_set/getShadowLight, light_setShadowMatrix / setMirrorMatrix (all evidence in renames.tsv).
- gfx_emitLights_000454C4 / gfx_emitOneLight_00045CB0 (were BaseMat_func_*): the Lights-record
  emitters BaseMat_vslot4 calls (section 8).
- Still unnamed in the area: BaseMat_func_00043BEC / 00051ED8,
  BasePolyShape_func_000510F0 (UV + subdivide) / 00052674 (static state reset, App_softReset) /
  00052BBC (extreme vertex of two triangles), PolyShape_func_00043584 (element reset; allocs the
  0x100-byte row table at +0x7C when gfx flags bit 8) / 000483BC, RcpMgr_func_0004DB38 (returns 1),
  DisplayMgr_func_0004DE80, the *_stub_ / *_vfn* leaves, gfx_emptyStub_ x5.
- The texture-format 0x608 (accepted by the size code, rejected by the loader) may be dead data.
- A typed model of the GfxLib global (section 2) for documentation; matched code must keep the
  `D_00000000 + K` form.

## 11. Skeletal animation (animate.cpp)

Header: `include/gdl/anim.h`. Code: game_libs 0x61E58-0x63704 (post0b + post1b; AnimData_load is the
IDO -O2 donor game_libs_o2_61F8C.c, anim_blendPose the NCC donor game_libs_ncc_62A2C.cpp).

**Objects.**
```
AnimDataMgr (0x48, "AnimDataMgr")  one per skeleton type: the anim file + a frame cache
  groups[numGroups]  AnimGroup (0xC)  {AnimData *anims; count; mgr}
    anims[count]     AnimData (0x20)  one anim: numNodes, numFrames, keys, frame data
  cache              AnimFrameCache {slots, count}: AnimFrameSlot (0x14) {pose, frame, anim, inUse, pending}
AnimPlayer (0xB0, "<Node>")         plays one anim on one skeleton (game.uso RiderAnim derives from it)
  animators          list of Animator (0x130, "anim"): one per animated node, nodeIndex +0x10C
```

**Anim ids.** `(group << 16) | index` (anim_formatId prints " %d:%d"). AnimDataMgr_lookup checks
group < numGroups ("Missing AnimGroup %d"), index < count ("Missing Anim %d:%d") and numFrames != 0
("Empty Anim %d:%d"). game.uso's RiderAnim keeps the group in `animSet` (0x10000 regular stance,
0x50000 switch stance) and ORs the anim number in; e.g. `startIfChanged(rider, 0x30001, 6, 6, 0x100, 20)`
plays group 3 anim 1, keys 6..6, blending in over 20 updates.

**File format** (AnimDataMgr_loadFile, the Node_Load path; ints read through the gSysLib stream):
```
int version; int numGroups;
per group:  int count;
  per anim: { int cmd; int val; } ... until cmd == 0
     1  keys:       val AnimKey {s32 frame; f32 rate} (8 bytes each)
     2  numNodes    (must equal AnimDataMgr.numNodes, "AMgr: bad num Nodes")
     3  frame data: val bytes = numFrames * numNodes * 14; loaded (mem_newAligned 8) or left in the
                    file with its offset recorded (fileOffset) for streaming
     4  skip val bytes
     5  numFrames
```
Big-endian like everything else; a port byte-swaps on load.

**Frames.** A frame is numNodes `AnimNodeKey` records, 14 bytes: `s16 trans[3]` (model units, unscaled),
`s16 quat[4]` (x y z w, times 1/32767: RoData 0x2094 = 0x38000100). anim_unpackKey turns one record
into an `AnimPose` {f32 trans[3]; f32 scale[3]; f32 quat[4]} (scale untouched; 1.0 from Animator_ctor).
Frame f starts at byte f * numNodes * 14.

**Frame cache.** AnimDataMgr_ctor(this, file, numNodes, numSlots) allocates numSlots poses of
numNodes * 14 bytes. AnimDataMgr_getSlot(cache, anim, frame) returns the slot already holding
(anim, frame) (AnimFrameCache_find) or claims a free one (allocSlot: first with inUse == 0) and fills it
with AnimData_readFrames: a memcpy from resident data (returns -1), or fs_setHandle + fs_gdlSeekFile
(fileOffset + frame * stride) + fs_gdlReadFileAsync (returns the read handle, kept in `pending`).
AnimFrameCache_getPose waits on a pending read (AnimData_waitFrames) and returns the pose. Every
AnimDataMgr update (and message 9) clears inUse on all slots, so slots live for one frame unless re-hit.
A port can load every frame at startup and drop the cache.

**AnimPlayer** (vtable Data 0x21F58: slot 3 update, 4 handleMsg, 10 onKey). API:
| call | does |
|---|---|
| start(p, anim, startKey, endKey, flags, blendFrames) | time = keys[startKey].frame; eventKey = blendEvent = -1000; blendCount = 0 |
| startIfChanged(same args) | start unless anim, startKey and endKey equal the current request |
| setBlend(p, animNeg, animPos, weight, flags, blendFrames) | weighted mode (flags \| 0x80) |
| setUpdateInterval(p, n) | fetch/apply poses every n updates |
| setKey(p, anim, key, frame, f) / getKeyFrame / getKeyTime | key table access ("BadKeyFrame" / "BadKeyTime") |

Update (slot 3) = AnimPlayer_advance then AnimPlayer_applyPose:
1. flags == 0 or anim == 0: nothing.
2. Weighted (0x80): anim = weight < 0 ? animNeg : animPos; time = frame(key 0) + |weight| *
   (frame(key 1) - frame(key 0)). Used for continuous poses (leaning, crouch amount).
3. Otherwise time += keys[endKey].rate (or -= when the end frame is below the start frame). When time
   crosses keys[eventKey].frame, onKey fires. At the end: time = end frame; with LOOP (2) either restart at
   the start key or, with PINGPONG (4), swap startKey / endKey.
4. frame0 = (int)time, frame1 = frame0 + 1 (clamped to numFrames - 1), frac = time - frame0.
5. Blend-in (0x100): blendCount++, blendWeight = blendCount / blendFrames, blendLeft = remaining; at the
   end the flag clears and, if blendEvent == -1, onKey fires.
6. Every updateInterval updates: slot0 / slot1 = getSlot(frame0 / frame1); applyPose fetches both poses
   and, per Animator, calls anim_blendPose(animator, pose0 + nodeIndex, pose1 + nodeIndex, frac,
   blendLeft, blendWeight).

anim_blendPose: x = lerp/slerp(frame0 record, frame1 record, frac) (math_quatSlerp for the rotation, linear
for the translation). blendLeft != 0: dst = cur blended toward x by blendWeight; else dst = x. Then
cur = dst only when blendLeft < 2, so during a blend-in `cur` stays frozen at the pose the blend started
from (a cross-fade from the old pose to the new anim). dst.scale.x = 1.0, and the target node is notified
through its vtable slot 9 (presumably to rebuild its matrix from dst). onKey (slot 10) is empty in the base; RiderAnim uses eventKey
(its `stateArg`) and blendEvent -1 to step its state machine.

## 12. Skinning (skin.cpp)

Header: `include/gdl/skin.h`. Code: game_libs 0x68C14-0x69C58 (post1b). Three shape-file node commands
build it (the ProcNodeList dispatcher, nodelist_*):
- **SkinMgr** (skin_cmdSkinMgr): args slot (< 4, "num < MAX_SKIN_MGRS"), bone table (0 = "Bad Skin
  Weights"); SkinMgr_ctor, registered in a 4-entry global table by slot.
- **SkinShape** (skin_cmdSkinShape): args slot, shape name; builds a "SkinShape" BasePolyShape and a
  MorphPoly over it under the current MNode, then SkinMgr_init(mgr, currentMNode, morphPoly) and
  MorphPoly_init. "no skinmgr" if the slot is empty.
- **SkinAnim** (skin_cmdSkinAnim): args slot, bone index; entry = mgr->boneTable[index] (8 bytes
  {s16 count; SkinWeight *weights}); SkinMgr_addAnim(mgr, SkinAnim_ctor(0, count, weights, currentMNode)).

SkinWeight = {s16 vert; s16 weight (percent)}. SkinMgr_init copies the shape's verts (s16[3], shape
+0x60, nVerts +0x40) to bindVerts, sets every main-bone weight to 100, inverts the main bone's matrix
(MNode +0x70) into invBone and gives the shape pointers to both (+0xA8 / +0xAC). SkinMgr_reset runs
SkinAnim_bind for every SkinAnim: subtract its weights from the main weights, and store each of its
vertices in its own bone's space (bind vert through the main bone matrix, then through the inverse
of the SkinAnim bone's matrix).

SkinMgr_update, once per frame (gSysLib +0x14 frame counter vs lastFrame):
```
for v: out[v] = weights[v] ? R(mainBone) * bindVerts[v] * weights[v] / 100 : 0
if jitter: out[v] += random in [-jitter/2, jitter/2) per axis; jitter = 0
for each SkinAnim a, i < a->count with w = a->weights[i].weight > 0:
    p = R(a->bone) * a->bindVerts[i] + (a->bone pos - mainBone pos)      (pos = MNode +0xA0)
    out[vert] = (w == 100) ? p : out[vert] + p * w / 100
MorphPoly_setVerts(shape, out)
```
R is the 3x3 part of the world matrix. A port can do the same on the CPU, or upload bind poses and bone
matrices and skin on the GPU (weights are per vertex per bone, at most the main bone plus the SkinAnims
that list the vertex).

## 13. Run 500 (agent-b): structs for the post0b engine classes

New headers (all in include/gdl, field names from the bodies, the exact NCC donors and HostIO parm tags):
- console.h: TextWin (0x58: rows / buf / maxCols / nRows / hScroll / visRows / top / cols / cur, cell size,
  origin, muted, ring next / prev, title, owner, colour) and ConsoleMgr (0x3C: curWin, winList, input,
  visibility = Node doFlags 0x4).
- mem.h: MemTracker (0x44 tree node: start / end marks, bytes, kb, heapId, sibling / children / parent /
  prevOpen, name[0x20]), MemTrackerPool, MemTrackerMgr (0x48: pool, open, root).
- mnode.h: MNode (0xB4: Flags, Mtx (local), CMtx (world), MtxMode), QNode (MNode + VQS / CVQS AnimPoses),
  SNode (0x88: Mtx object, pos, height, scale, rotX..Z, radius, next). Vtable slot 9 = setAnimPose (the
  Animator target call), MNode slot 10 = getCMtx.
- coll.h: CollObj (0x34: owner, next, kind, id, flags, hitMask, category, pos, vel, vptr at +0x30),
  CollCylinder, CollContact (0x40), CollObjMgr (statics / dynamics lists).
- item.h: ItemType (tag, next, typeId), ColourItemType (RGBA), ItemMgr (types).
- polyshape.h: PolyVert / PolyNormal, BasePolyShape mats / matCap / nMats (+0x84..+0x90).
- dlctx.h: DLCTX / DLBUF accessor macros (gfx_clearScreen's inline appends).
Converted bodies: Animator_ctor, the console, memtrack, MNode / SNode / QNode, CollObj, ItemType / ItemMgr,
CamFollow / FreeCam (on include/game/camera.h), gfx_clearScreen, BasePolyShape_genNormals / parse donor /
accessors, the Window_doCommand donor; ProcNodeList's state struct got the nodelist_dispatch field names.
Raw `*(T *)(p + K)` sites live in post0b: 1014 -> 705 (post1b unchanged at 240). Field conversions can
swap commutative operand order (IDO_CODEGEN.md#field-conversion-commutative-operand-swap).

Next: DNode (post1b, 0x3D4; DNode_init / resetXform / resetAccums are ~80 sites; its ctor parm tags name
the fields), BallRotator (cam_func_00036074 = BallRotator_reset), PolyShape_display, CollShape, the
HostIO objects, Window unk fields (+0x84 / +0x98 lanes, +0x100), ItemType +0x34..+0x40.

## 14. Run 511 (agent-b): DNode, PhysQNode, Friction (include/gdl/dnode.h)

New header include/gdl/dnode.h (game_libs post1b 0x63884-0x65E64):
- **DNode** (0x3D4): the QNode base flattened (mnode 0x00, vqs 0xB4 = position / scale / orientation quat,
  cvqs 0xDC = the vqs copy taken at the end of each integrate, which the run 470 names call lastPos /
  lastOrient), DNodeParms parms 0x108 (the 15 "DNode::Parms" tags imp spd spl spw gvt suc vsc usc tsc
  cog unc dsc csc rad cts with their ctor defaults), surfImp / surfSpd / surfVsc, the two DNodeAccum
  force accumulators impulseAcc 0x294 / moveAcc 0x2C8, angVel (quat), velDir, vel, worldCog, velDelta,
  lastVel, speed, friction 0x360, attached 0x39C (list DNode_updateAttached walks), axes 0x3B0 (3x3 rows
  from cvqs.quat, DNode_quatToMtx_00065B40; SnowBoarder calls them up / side / dir).
- **GdlParmV3** (0x20 Vec3 parm, type Data 0x221F0); float parms use GdlParmF from gdl/gadget.h.
- **PhysQNode** (0x124): owner DNode 0x108, body-space probeA / probeB. PhysQNode_pushProbes_00063964
  rotates them into world space and pushes the owner up by their depth below y = 0.
- **Friction** (0x170): coef ("Friction", 0..2) 0x150, limit ("Friction Limit", 0..10) 0x154,
  contactPoint 0x120, offsetLen 0x164, owner 0x16C. Friction_vfn11_00063F34 reflects +0x114 about the
  contact normal and pushes the owner by it scaled with clamp(((coef * owner->friction + k) * K)^2).
Call graph fixes from the bootup TextRelocs (scripts/uso-imports.py sites bootup): DNode_init calls
DNode_resetAccums_00065148 then DNode_quatToMtx_00065B40, and addImpulseAt / addMoveAt call
DNodeAccum_addForce_000641DC with the force passed through in $a2. Older comments named all of these
AnimPlayer_update; they are now XCALL-named. Renames: DNode_getSuc (was DNode_getF198_00065E3C),
PhysQNode_pushProbes_00063964.

Converted: every DNode_* body in post1b, DNodeAccum_addForce / apply (NM), PhysQNode_ctor, Friction_*.
Raw sites in post1b: 240 -> 113 (post0b 705, post1b2 8). Each step had an identical post1b .o
objdump -dr, and the gate passed.

**For agent-g:** include "gdl/dnode.h" in include/game/snowboarder.h and type SnowBoarder's first 0x3D4
bytes as `DNode dnode;` (or keep the SnowB* mirrors and add asserts against DNode offsets). The names
match run 470 except: lastPos / lastOrient are cvqs.trans / cvqs.quat; pos / orient are vqs.trans /
vqs.quat; up / side / dir are axes[0..2]; startPos 0x3A4 is unk3A4 in DNode. envobj.h ShpNode
(`char dnode[0xB4]`) can use it too.

Next: post1b pad_* (pad thread object, ~25 sites: pad_reset_000673FC, pad_startPlay_00067A10, pad_init /
initMotors / set*), ImageFile_init / BinFile_set / list_allocNode / DynArr, skin leftovers; then the run 500
list (BallRotator, PolyShape_display, CollShape, HostIO objects, Window +0x84 / +0x98 / +0x100,
ItemType +0x34..+0x40, PolyShape_func_00043584).

## 15. Run 515 (agent-b): controllers, packed files, BallRotator

New headers (all in include/gdl; evidence in each header comment):
- **pad.h**: the controller layer.
  - **PadDev** (0x13F8) is the Bss device block gSysDevBlock_3A4E8 (Sym 1505, whose 5112-byte span
    is exactly this size). Layout:
    - +0x0000 the 4 KB pad-thread stack;
    - +0x1000 OSThread;
    - +0x11B0 the message queue, with 4 slots at +0x11C8;
    - +0x1200 OSContPad[4] (osContGetReadData), +0x1218 OSContStatus[4] (osContInit);
    - +0x1228 OSPfs[4];
    - the per-port pakState / motorOn / hasMotor / motorValue;
    - readDone, the present bit pattern, motorRetry.

    The thread (pad_threadLoop_00066EEC donor) handles three messages: 5 is the SI event (pak
    probe), 1 starts a read (it pushes motorValue[] first), and 2 is read done.
  - **PadCtl** (0x80) is one controller, the object the bootup modes call InputPad
    (include/game/input.h, agent-h). Fields:
    - stick (raw / 80 with a 0.2 dead zone);
    - held / prevHeld / pressed / released;
    - doubleTap (the same press again within 10 frames), port (1-based);
    - injected input, replay, paused, recordMask, mirrorX;
    - the rumble pattern: a 0xFF-terminated byte string, rumblePrio, and dirIndex.

    pad_setIfNewer_00067A54 (start a rumble unless a higher-priority one is running),
    pad_set_00067A90, pad_clear_00067AA0 (clear the button words), pad_clearSlot (stop the motor)
    and pad_isSlotState2 (rumble pak present) are rename candidates. So is pad_testButton_00067550,
    which tests the port's bit in the present mask, i.e. "controller connected". The pad_update
    donor (game_libs_o2_675A4.c) still uses FW(); converting it is next.
- **binfile.h**: BinFileMgr (0x38: Node, fileHandle, groups, nGroups), BinFileGroup (0x10: files,
  nFiles, mgr), BinFile (0x20, Cfront vptr at +0x1C: flags bit 0 = no data, fileOffset, data, mgr,
  size), ImageFile (0x30: width / height / format / dataOffset / dataSize, from the tag stream that
  ImageFile_load reads).
- **mem.h** gained DynArr (0xC: items, count, capacity; 8-byte slots) and DynArrPool
  (list_allocNode_000665B4).
- **polyshape.h**: BasePolyShape +0xA8 / +0xAC are skinInvBone / skinBoneMtx (stored by SkinMgr_init).
- **ballrot.h**: BallRotator, the virtual trackball Node. It projects the cursor's current and
  previous screen points onto a sphere (centre, "Radius") and composes the drag rotation into its
  parent MNode's matrix. Its fields are named by role in BallRotator_reset / update / func_00036224.

Rename (pure, 36020705f): Friction_vfn11_00063F34 -> Friction_applyContact, plus its four
`kRo_Friction_applyContact_<K>` constants. The gl_data.h pool macro `kRo_Friction_vfn11_00063F34`
needed a one-token hand edit in the same commit: rename-symbol.py refuses a #define, and
`uso-data-sites.py check` keys every kRo_ pool on its function's name, so the gate fails unless the
pool macro and the function move together. **Any rename of a function that owns a kRo_ pool has this
problem** (a tool feature request for agent-a: let rename-symbol.py carry `kRo_<OLD>` along).

Raw sites: post1b 113 -> 58, post0b 705 -> 629. Every step had an identical objdump -dr for the
matching and NON_MATCHING .o, and the gate passed. Two conversions did not stay identical:
- pad_updateMotor_00067084: typed `dev->motorOn[a1]` keeps `this` live across the call (a spill),
  so the `v1 = a0 + a1` byte-row pointer stays, with a comment;
- the second nVerts loop of the SkinMgr_update NM body: BASEPOLY()->nVerts grew the NM .text by
  12 bytes of tail padding, so the raw form stays.

Next:
- convert the pad_update donor;
- CollShape (0x90: Node, the 12-byte AxisInfo tri planes at +0x2C, shape +0x84). Its bodies use the
  local views ObjB9 / ColB9 / TriB9 / ObjBE, which a coll.h CollShape should replace;
- PolyShape_display (29 sites, gctx = the GfxLib DL context);
- gfx_clearScreen (30), BasePolyShape_genNormals (24), math_mtxScaleRows (18);
- the HostIO objects, Window +0x84 / +0x98 / +0x100, ItemType +0x34..+0x40, PolyShape_func_00043584;
- the pad rename candidates above.

## 16. Run 521 (agent-b): pad renames, InputPad = PadCtl, CollShape, DL packets

Renames (pure, 6d1d0a47f; evidence in the commit message):
- pad_testButton_00067550 -> **pad_isConnected** (the port's bit in PadDev.present);
- pad_setIfNewer_00067A54 -> **pad_startRumble** (skipped when the same pattern is playing or
  rumblePrio is higher); pad_set_00067A90 -> **pad_setRumble**;
- pad_clear_00067AA0 -> **pad_clearButtons**; pad_clearSlot -> **pad_stopMotor**;
- pad_isSlotState2 / pad_isSlotState2Global -> **pad_hasRumblePak** / **pad_hasRumblePakGlobal**
  (pakState == 2).

Headers and bodies (hand edits; identical objdump -dr for every changed .o):
- **pad.h** is plain-C-typed (the NCC .cpp users of game/input.h have no s8 / u8 / f32), keeps its
  offset checks under `#ifndef __cplusplus`, and now owns InputFrame and PAD_REPLAY_*.
  game/input.h includes it and has `typedef PadCtl InputPad;`, with no duplicate defines.
- The **pad_update donor** (game_libs_o2_675A4.c) is fully field-typed. IDO lesson: a struct field
  read `p->f` is lowered in a different order from the `FW(p, off)` cast form inside a binary
  expression. The commutative pairs that read `X | FW(0x10)` had to be written `p->held | X`, and
  the doubleTap AND had to be `lastPressed & pressed`. The PLAY cursor that was scaled-index-first
  as ints is `&p->replayFrames[p->replayFrame]`. The rumble byte keeps a `char *` local read
  through a `u8 *` cast, because a `u8 *` local swaps the addu.
- **coll.h**:
  - CollShape (0x90): Node; tris; the token-stream fields 0x30 / 0x34 stream / 0x38 / box[6];
    unk54[3]; shape = BasePolyShape * at +0x84.
  - CollTri (12 bytes: axU / axV / axis / sign / tag / d).
  - CollGrid (the XZ cell grid at BasePolyShape +0xA0).
  - POLY_TRILIST / POLY_COLLGRID, for BasePolyShape unk4C / unkA0.

  CollShape_initTriPlane, the CollShape_raycast / query NM reference bodies, NullCollShape_ctor
  and the CollShape_ctor donor (game_libs_o2_3AC5C.c) use these types. The local views ObjB9 / TriB9
  / ColB9 / FaceB9 / ObjBE / TriBE / ColBE / FaceBE / GridBE and AxisInfo_3AA5C are gone.
- **dlctx.h** DLGfx {w0, w1} + DLPKT(): gfx_clearScreen has 0 raw sites (and takes f32 *colour).
- **polyshape.h** POLYTRI(): BasePolyShape_genNormals. Its three cross-product lines stay raw,
  because POLYVERT there reorders the lh loads (the same field-vs-cast effect).
- math_mtxScaleRows / math_mtxAddTranslation take f32 (*)[4].
- `uso-data-sites.py check --update-ratchet` dropped the 4 spelled post0b entries.

post0b cast sites (census, compiled code): 507.

Next:
- name BasePolyShape unk4C (s16 tri list, parse cmd 26) and unkA0 (CollGrid *, parse cmd 35) in
  polyshape.h, then drop POLY_TRILIST / POLY_COLLGRID;
- convert the CollShape_ctorPoly NM body;
- the HostIO objects, Window +0x84 / +0x98 / +0x100, ItemType +0x34..+0x40,
  PolyShape_func_00043584;
- PolyShape_display, whose matching code is the NCC donor game_libs_ncc_48AEC.cpp (the C body is
  NM reference only).

## 17. Run 527 (agent-b): GfxLib struct, PolyShape_shade, texload, fault_printThread

Hand edits only (no renames). Every changed .o had identical `objdump -d -r` in the matching
and NON_MATCHING builds; the gate passed before each commit.

- **include/gdl/gfxlib.h**: GfxLib (0x5D8), plain C types and `#ifndef __cplusplus` offset
  checks so the NCC donors can include it. Named: every4thFrame, proj / modelView / curMtx /
  extraMtx, worldScale[3] (+0x128: CollShape_query divides the probe point by it; [2] is the
  section 2 "+0x130 scale"), renderFlags (+0x13C), viewStage, lights, shadowLight, flags,
  mtxMode, dir, fbIndex, perspNorm, frameTime, staticDL, rcp, **textX / textY / charW / charH**
  (+0x21C..0x228, the gfx_drawText cursor and cell: dbg_screenOverlay sets 0x32,0x50 with 8x8
  cells then 0x78,0x78 with 16x16; sys_sprintf_00061B30 sets them for its CPU-drawn text),
  mainWindow, curWindow, cpuDraw, ddm[51]. Accessors: `gGfx` and `GFXLIB(p)`. post0b's 62
  sites use them (`gGfx->curWindow->dl` for the old `+0x254 ... +0x158` chains). The
  per-site zero-valued aliases keep their own symbols (`GFXLIB(&gGfxLib_44EDC_c)->rcp`).
  gGfxLib_3BE1C_128 is an alias pinned at +0x128 itself, so it stays a `f32[]`.
  agent-h converts game_libs.c.
- **polyshape.h**: BasePolyShape +0x30 unk30 (parseCmd 13 / 14 / 17 flag word), +0x38
  **shapeFlags** (parse cmd 8 sets 0x8 with the alpha table, cmd 11 0x2000, cmd 21 0x4000;
  0x8000 = normals through PolyShape_getNormal8), +0x4C **triList** (parse cmd 26), +0x50
  **vtxColours** (parse cmd 9, one RGBA word per vertex), +0x7C **alphas** (parse cmd 8),
  +0xA0 **collGrid** (parse cmd 35). POLY_TRILIST / POLY_COLLGRID (coll.h) are gone. The
  offsetof checks moved under `#ifndef __cplusplus`.
- **PolyShape_shade** (game_libs_ncc_49DBC.cpp): 47 raw sites to 0. Its parameters are
  `BasePolyShape *shape, ..., s32 tri, BaseMat *mat` (extern "C", so no mangling change).
  One edg lesson: `&shape->faceNormals[tri * 3]` renumbers the t registers against
  `(s32)shape->faceNormals + tri * 0xC`. The u32 `&vtxColours[v]` index form is fine.
- **texload.h**: gfx_flushTexture_00046C4C takes `BaseMat *` (TexImage width / height
  under MAT_TEX_RECORD, &TexCI.texels / &TexCI.tlut for CI8). The gfx_setupMatTextures NM
  reference body is on DLContext / BaseMat. The matching code is the agent-a port in
  src/match_imports/gfx_setupMatTextures_00045E20.c, which still uses its context types
  (GL470E4Object = DLContext, GLRenderNode = BaseMat).
- **fault_printThread**: on libultra OSThread / __OSThreadContext (include/libultra/os_thread.h,
  now included by post0b). The even FP slots that the matched code reads as 64-bit integers
  stay `*(long long *)&ctx->fpN`.
- CollShape_ctorPoly NM body: CollShape / BasePolyShape / PolyTri fields.

Census (compiled code, casts + accessor uses): post0b 738 -> 656, ncc_49DBC 47 -> 0, owner b
849 -> 767; whole ROM 5838 -> 5709.

Next:
- gfx_submitFrameTask_000469A8 (50), gfx_end (26), BasePolyShape_genNormals / genNormalsFast
  (24 each), FogParms_lerp (18), gfx_start / CamFollow_update / math_mtx4Adjugate (16);
- the gfx_* functions whose first parameter is the GfxLib (`a0[0x218 / 4]` in
  gfx_waitRetrace and others) can take `GfxLib *`;
- the run 521 leftovers that are still open: the HostIO objects, Window +0x84 / +0x98 / +0x100,
  ItemType +0x34..+0x40, PolyShape_func_00043584;
- the match_imports gfx_setupMatTextures port could include dlctx.h / material.h (agent-a).

## 18. Run 534 (agent-b): GfxLib-first gfx_* typed, frame submit / end / start on fields

Hand edits only (no renames). Every changed .o had identical `objdump -d -r` in the matching
and NON_MATCHING builds; the gate passed before each commit.

- **gfxlib.h** GfxLib, newly named: frameStartCbs[5] / nFrameStartCbs (+0x148 / +0x15C,
  gfx_start calls vtable +0x5C slot 0 of each), drawUpdates[10] / nDrawUpdates (+0x198 / +0x1C0,
  gfx_queuePush_0004E1BC overflows at 10; gfx_end calls slot 0 of each under "ADrawUpd"),
  colour[3] (+0x1FC u16, gfx_colorToRGB16_0004771C), morphs (+0x22C GfxMorphList: MorphPoly_display
  pushes itself, gfx_end runs its update under "MorphUpd", gfx_start empties it), nWindows /
  windows[8] (+0x258 / +0x25C, gfx_addWindow "too many windows"; gfx_end submits each),
  oneFrameDL[2] (+0x280, GfxLib_init "OneFrame"). New types GfxMorphList and **FogParms**
  (0x18: colour[4], min, max).
- **rcp.h** RcpMgr +0x24 **retraceCount** (RcpMgr_service `m24++` on each 'd' VI message;
  gfx_waitRetrace and the gfx_end "Swap" loop spin until it changes).
- **window.h**: WinClear (+0x100 / +0x104 are one 8-byte member object: Window_ctor builds it as
  a unit, Window_setDefaults copies it as a pair; WINCLEAR(p)). Window +0x80 **coneCos**, +0x84
  **drawDist[5]** (per-class draw distance at the reference 85-degree fov), +0x98
  **drawDistFov[5]** (drawDist * 85 / camera fov, Window_display). cam_isSphereInView culls a
  sphere of class i when drawDistFov[i] <= dist - radius or when dot(dir, view forward) <
  coneCos.
- **item.h** ItemType +0x34 **builtHead** (buildItems: first newItem(0) result, the rest chained
  through each item's next word), +0x38 **searchDown** (SNodeItemType_vslot15 direction). +0x40
  keeps unk40 (game_uso.c reads it): SNodeItemType_newItem attaches that Node under each new
  SNode item. +0x3C is still unknown (cleared with the item list).
- `GfxLib *` first parameter: gfx_waitRcpIdle, gfx_waitRetrace, gfx_setCpuDraw, gfx_swapBuffer,
  gfx_emitRenderState, gfx_emitFogRange, gfx_colorToRGB16, gfx_matrixModeProjection / ModelView,
  gfx_setDirBytes / FromVec, gfx_loadMatrix, gfx_loadIdentity, gfx_setViewStage,
  gfx_resetModelView, gfx_listAppend, gfx_set/getShadowLight, gfx_addWindow, gfx_queuePush,
  gfx_setEvery4thFrameFlag, gfx_callDdm, gfx_getDdm, gfx_start, gfx_end,
  gfx_submitFrameTask_000469A8. FogParms_lerp / hostioParms take `FogParms *`.
  BasePolyShape_genNormalsFast is on BasePolyShape fields.
- **IDO lesson (gfx_submitFrameTask)**: a load's type matters for CSE. The function reads
  arg0->mainWindow nine times; the matched code had them all as int loads (FW). Turning some into
  pointer-typed field loads stopped IDO from sharing them with the others and the frame grew from
  0x58 to 0xB0. All of them now go through `GFX_MAINWIN_I(g)` (`*(int *)&(g)->mainWindow`), and
  the ScreenWindow fields read through it (SCRWIN(temp_v1)->...) are fine, because the field
  loads were already single-typed.
- Tried and dropped: BasePolyShape_genNormals' three cross-product rows on POLYVERT fields. With
  the factors in source order the lh loads reorder (run 521); with both products' factors swapped
  every pair comes out reversed. The 24 raw `*(s16 *)(v + K)` reads stay.

Commits (agent-b, both hand edits, no renames): c57a84050 (gfxlib.h / rcp.h / WinClear and the
gfx_* bodies), fa5833113 (Window / ItemType fields, genNormalsFast).

Census (compiled code, casts + accessor uses): post0b 656 -> 512, post1b 103 (unchanged), owner b
767 -> 623; gfx_submitFrameTask 50 -> 1, gfx_end 26 -> 1, genNormalsFast 24 -> 0, FogParms_lerp
18 -> 0, gfx_start 16 -> 3 (the left sites are the unknown objects' vtables and gSysLib +0x1C).
Still in post0b's top: genNormals (24), Window_display (14), cam_isSphereInView (10, its camera
reads).

Next:
- genNormals cross products (try swapping only the second product, or a typed PolyVert local);
- the GfxLib-first functions that are still `char *` / NM bodies: gfx_beginView (NM),
  GfxLib_reset (NM), gfx_printWindowDLUsage (its a0 + 0x148 is not GfxLib: check the callers),
  gfx_vcall_0004E150 (+0x134), gfx_callStaticDL (gGfx->staticDL);
- PolyShape_func_00043584's object is PolyShape_init's clip-row Elem (ncc_493AC.cpp), not a
  BasePolyShape: give Elem a header first;
- post1b: boot_main_00066850's gSysApi table (a SysApi struct in gl_data.h needs the owner's OK),
  skin_cmdSkinShape's loader context.

## 19. Run 537 (agent-b): SysApi, NodeListState, libultra stand-ins, genNormals cross products

Hand edits only (no renames). Every changed .o had identical `objdump -d -r` in the matching
and NON_MATCHING builds; the gate passed before each commit.

- **include/gdl/sysapi.h** (new): SysApi, the table gSysApi (Bss+0x416A0, Sym 1558) points at.
  The table lives outside bootup.uso; the known slots: +0x0 / +0x4 memStart / memEnd
  (sys_setRegion; "Bootup Code size %dk" = (memStart + 0x80000000) >> 10), +0x8 / +0xC / +0x10 /
  +0x14 / +0x1C the USO error and warning words boot_main prints, +0x40 usoLoad, +0x44
  usoUnload, +0x48 fileInfo, +0x4C..+0x60 the kind-1 file services (fileOpen / fileRead /
  fileSeek / fileClose / fileError / fileRomAddr: fs_gdlOpenFile .. fs_gdlReadFileAsync),
  +0x70 symLookup(addr, &name, &offset) (the "(%s,0x%x)" in dbg_printThreads / dbg_faultThread),
  +0x74 usoPreLoad (app_loadUso). Installed by game_libs (TextReloc targets): boot_main sets
  +0x34 heapNew (mem_heapNewThunk), +0x80 dmaRead (dma_readChunked), +0x84 printfFn (dbg_printf),
  +0x94 timeInFrames, +0x98 / +0x9C tempAlloc / tempFree; app_initSystem sets +0x8C sprintfFn
  (sys_sprintf_00061B30) and +0x90 consoleSetOrigin (ConsoleDev_setOrigin). Accessors `SYSAPI`
  and `SYSAPI_AT(alias)` (the per-site zero aliases gSysApi_34458_obj / _34548_obj / _34A78_rec).
  game_libs_ncc_34A78.cpp (app_initSystem, not agent-b's) still spells +0x8C / +0x90 raw.
- **include/gdl/nodelist.h** (new): NodeListState (0x4C), the ProcNodeList interpreter state
  that was post0b's local Gl5591CArg (the edg donor's Strm). New names: +0x14 **animMgr**
  (ProcNodeList a2; anim_createAnimator "Null AnimatorMgr specified"), +0x28 **obj** (the
  object the last constructing command built), +0x2C **light** (light_addDefault), +0x38
  **linkNodes** (op 1016; the *_def commands append the new node to parent->node). On it:
  ProcNodeList, the four nodelist_check*, MNode_def, Node_def, light_addDefault_000513CC,
  anim_createAnimator, shape_cmdShape_00051520, shape_cmdLightTarget, skin_cmdSkinShape,
  skin_cmdSkinAnim. skin_cmdSkinMgr's NM body is still `int *self`.
- post1b donor stand-ins on libultra types: gl__VirtualToPhysicalTask (OSTask_t, the seven
  pointer fields osVirtualToPhysical converts), gl___osLeoResume (OSMesgQueue + a local
  __OSEventState, __osEventStateTab[OS_EVENT_PI]). The real code is the -O1 donors.
- **light.h**: BaseLight +0x10C is BaseLightParms (0x2C: GdlParms head "Parms", then one "col"
  colour parm in GdlParmRGBA layout) with **parms.col[4]** at +0x124 (for agent-a's
  gen_createLights port).
- **genNormals lesson**: the cross-product rows match on typed `PolyVert *` locals when only the
  SECOND product of each row has its factors swapped
  (`(b.y - a.y) * (c.z - b.z) - (b.z - a.z) * (c.y - b.y)`). Swapping both products, or neither,
  reorders the lh loads.
- Window_display takes `Window *`; it and cam_isSphereInView read the camera through MCamera
  (fov, mnode.world[3] = eye position, view[0..2][2] = the view forward column).

Commits (agent-b, all hand edits, no renames): 0c5f00bf4 (sysapi.h), 099cfd5d6 (nodelist.h +
libultra stand-ins), a27ba7aed (light.h BaseLightParms), 8cb7aaa4e (genNormals, Window_display,
cam_isSphereInView).

Census (compiled code, casts + accessor uses): post0b 512 -> 436, post1b 103 -> 42, owner b
623 -> 486; whole ROM casts 2957 -> 2858, accessor uses 935 -> 897.

Next:
- post0b's top: the `<block>` (18), CamFollow_update / math_mtx4Adjugate (16), gfx_findVtx (15),
  Mat_fromFrameBuffer / CollObjMgr_update (12), MorphPoly_updateColours / Window_setDefaults
  (10), BaseLight_ctor (8, now has BaseLightParms); DNode_updateAttached (16) in post1b;
  gl___osContGetInitData (8, post1b2) on os_cont.h;
- the fs_gdl* file object (kind +0x4, handle +0x20): a GdlFile struct in a header;
- the GfxLib* candidates not reached this run: gfx_beginView / GfxLib_reset NM bodies,
  gfx_callStaticDL, gfx_vcall_0004E150; the HostIO objects; PolyShape_func_00043584 after an
  Elem (clip-row) header;
- skin_cmdSkinMgr NM body onto NodeListState.

## 20. Run 542 (agent-b): NodeMsg, GdlInput, GdlFile, GdlVtx, the swapped controller helpers

Census (owner b raw struct-offset sites): 486 -> 366 (post0b 436 -> 337, post1b 42 -> 26,
post1b2 8 -> 3). All edits byte-identical in the matching and NON_MATCHING objects
(`~/.local/bin/mips-linux-gnu-objdump -d -r`, non-empty dumps), gate PASS for each commit.

- **NodeMsg** (include/gdl/node.h): `{tag, arg, reply}`, the handleMsg / doCommand argument.
  Node_handleMsg (0x38830) answers 0x2 (NODEMSG_SET_ACTIVE: DoDisplay | DoUpdate), 0xC (doFlags
  0x80 from payload +4), 0xD (find by name: reply = this when callback(name, *payload) == 0),
  0xE (find by serial). The census's `<block>` row was this K&R function.
- **GdlInput** (include/gdl/pad.h): the debug input object behind CamFollow.owner and
  BallRotator.input: PadCtl *pad +0xB4, prevPoint +0xBC, pan[3] +0xD4, curPoint +0xF8, enable
  +0x108, window +0x110. Its constructor/class is still unidentified (no caller of CamFollow_ctor).
- **GdlFile** (new include/gdl/gdlfile.h): kind +0x4 (GDLFILE_REMOTE 0 = HostIO, GDLFILE_LOCAL 1 =
  SYSAPI ROM files, read-only, GDLFILE_SRAM 2 = PI SRAM with the position word 0x3B8E8) and
  handle +0x20. All fs_gdl* methods, fs_func_0003593C and fs_set/getHandle take GdlFile *.
- **GdlVtx** (include/gdl/polyshape.h): libultra Vtx_t (ob / flag / tc / cn); gfx_findVtx_00048720
  compares ob, tc and (optionally) cn[0..2].
- Mat_fromFrameBuffer_0004F85C: spec is a Window (colorBuf[0], width, height), the texture is
  MAT_FMT_RGBA16. CollObjMgr_update / gfx_vcall_0004E150: vtable slot calls through VT_SLOT.
- math_mtx4Adjugate / Determinant: the 9-float helper is `DET3` = math_det3x3 (the old local `H`
  macro was counted as an accessor macro by the census).
- DNode.attached holds **Frictions**: DNode_updateAttached sets contactPoint = cvqs.trans + vel,
  contactDelta = contactPoint - prevContact (Friction +0x114 / +0x108, renamed from unk114 / unk108).
- **Controller helper names were pairwise swapped** (checked against libreultra): 0x6BC44 is
  __osContGetInitData (now gl___osContGetInitData_6BC44), 0x6BD14 is __osPackRequestData(cmd)
  (gl___osPackRequestData_6BD14), 0x6C11C is osContGetReadData (gl_osContGetReadData, called by
  the pad thread with &PadDev.conts), 0x6C1B8 is __osPackReadData (gl___osPackReadData). The first
  two keep an address suffix because their plain gl_ names are OLD names in renames.tsv (the chain
  folding in the gate and census keys renames by OLD, so a name can never be reused).
- gfxlib.h: GfxLib.fog (FogParms at 0x294), worldMtx at 0xE8, GFX_FLAG_MAPPARMS (flags 0x8, set by
  game_createMap for a COURSE_OP_MAP record; PolyShape_func_00043584 then allocates the 0x100-byte
  +0x7C buffer). GfxLib_reset's NM body is on fields.

Next: skin_cmdSkinMgr's NM body (its `self` is the skin command-parser context, not SkinMgr: find
the struct shared with skin_cmdSkinShape / skin_cmdSkinAnim); gfx_beginView, gfx_callStaticDL; the
HostIO objects; the clip-row element header with PolyShape_func_00043584 (+0x4C..+0x84);
MorphPoly_updateColours and Window_setDefaults (10 each), ScreenWindow_allocBuffers and
gfx_submitFrame_0004CDB0 (9), then BaseLight_ctor / LightTarget_display / coll_markZeroWeight (8).
BallRotator.input could become GdlInput * (ballrot.h would include pad.h).

## 21. Run 550 (agent-b): NodeListState.skinMgr, Mat clip rows, GfxLib views, GdlInput, FsStream

Census: all raw `*(T *)(p+K)` 1599 -> 1593 (match_imports 203 -> 197; owner b 366 -> 366: the
converted sites were NM / `a0[K/4]` index forms the census does not count). One hand-edit commit
(no renames); matching and NON_MATCHING objects byte-identical, gate PASS.

- **Spliced functions.** skin_cmdSkinMgr, gfx_beginView_00046BC4 and BallRotator_func_00036224
  are built in BOTH builds from their native ports in src/match_imports/ (REPLACE_FUNC_BODY);
  the `#ifdef NON_MATCHING` body in post0b / post1b is never linked. Convert the port (it is the
  real source); bind-native-relocations.py refuses the build ("native linked body changed") if the
  port's bytes move, which is a free byte check. A port can include gdl headers after its
  context_*.h (nodelist.h, gfxlib.h, window.h, pad.h: no typedef clashes); change the context's
  prototype to `struct X *`. In the NM reference body, name callees in comments only: the
  name-placeholder-calls check cannot prove CALL() names in a spliced function.
- **NodeListState +0x18 skinMgr**: the SkinMgr node command stores its SkinMgr in self and
  parent (ProcNodeList clears it). The Bss 0x41700 table (`gProcNodeList_41700`, gl_data.h) is the
  4-slot SkinMgr table (MAX_SKIN_MGRS) indexed by the slot argument; ProcNodeList clears its 4 words.
  The macro deserves a rename (gSkinMgrs_41700) and a corrected comment.
- **Mat = ncc_493AC.cpp's clip-row Elem.** PolyShape_init iterates the shape's mats (+0x84) and
  per material: lightDL 0x60 (PolyShape_allocLightDL, geomFlags 0x2000), triDL 0x6C
  (gGfx->staticDL; 0 if no triangle used it), triStart 0x8A, rowStart 0x80, rowGfx 0x7C (0x100
  bytes when GFX_FLAG_MAPPARMS: the triDL Gfx count at the end of each grid row), minCut / maxCut
  = the first / last row with triangles. PolyShape_func_00043584 is the Mat reset (unk84 = 1,
  unk4C = 1, minCut = -1, DLs cleared, rowGfx allocated). The edg Elem in ncc_493AC.cpp could
  now be spelled on these names (pool levers: check bytes).
- gfx_callStaticDL_00044540(int *start, DLContext *dl): G_DL into gGfx->staticDL at Gfx *start;
  `*(int *)&self->gfx.cur->base` is a byte lever (plain member swaps t6 / t8).
- gfx_beginView: `&s0->unk138` with `[1]` (renderFlags) must stay; `&s0->renderFlags` changes bytes.
- BallRotator.input is `struct GdlInput *`; in the port `*(int *)&((PadCtl *)ap)->held` is a byte
  lever (plain `->held` changes bytes).
- post1b fs_piXfer_00065EE4's records are FsStreams (gdl/dma.h): hdr, data, end, size, and the
  words read back from hdr / hdr + 4 land in wrPos / rdPos.

Next: rename gProcNodeList_41700 -> gSkinMgrs_41700 (and PolyShape_func_00043584 -> Mat_reset_00043584);
the HostIO objects; MorphPoly_updateColours and Window_setDefaults (10), ScreenWindow_allocBuffers
and gfx_submitFrame_0004CDB0 (9); then port-audit --owner b top: DNode_ctor (17), gfx_endDL (10),
BaseLight_hostioParms (9).

## 22. Run 553 (agent-b): gSkinMgrs, Mat_reset, MorphPoly.colours, WindowDefaults, ScreenWindow DLs, HostIO parms

Census (owner b raw struct-offset sites): 366 -> 327 (post0b 337 -> 298, post1b 26). port-audit
--owner b: 184 -> 155 (A 79 -> 71, B 27 -> 13, D 75 -> 68). Two rename commits (one tool, one
macro-only hand edit) and three hand-edit commits; every commit gated, all matching and
NON_MATCHING objects identical in section bytes, relocs and sizes (only .mdebug moves).

- **gSkinMgrs_41700** (was gProcNodeList_41700): Bss 0x41700 is SkinMgr *[MAX_SKIN_MGRS = 4]
  indexed by the skin slot (skin_cmdSkinMgr stores, skin_cmdSkinAnim / SkinShape read,
  ProcNodeList clears, SnowBoarder_ctor copies 0 / 2 / 1). The gl_data.h name is a `#define`, so
  rename-symbol.py refuses it ("not a symbol"): macro renames are hand edits and stay out of
  renames.tsv; the per-site linker aliases (`_5591C_z*`, `_90cc_fz`) do go through the tool.
- **Mat_reset_00043584** (was PolyShape_func_00043584). ncc_493AC.cpp's `Elem` is now `Mat` with
  material.h's member names (edg codegen unchanged by struct / member names).
- **MorphPoly.colours** (+0xC4, `u8 *`): RGBA per vertex; MorphPoly_updateColours copies RGB into
  cn[0..2] of the static DL's GdlVtx rows vtxStart + i, then clears it. Byte lever:
  `*(int *)&g->vtx.cur->base` (plain `->base` reorders an sll / lh).
- **WindowDefaults** (post0b, above App_main): gWindowDefaults' 0x40-byte layout (clear, width,
  height, originX/Y, near, far, flags, projType, clearColour). App_main and Window_setDefaults use
  it. Window_setDefaults' flags copy must stay a 1-word struct copy (Q1E760); a plain int copy
  reorders 13 insns. Its vcall is Window vtable slot 10 (VT_SLOT), as in ScreenWindow_allocBuffers.
  gl_data.h defines gWindowDefaults twice (lines 64 and 201, same expansion); one could go.
- ScreenWindow_allocBuffers: the 4-byte slot walk as SCRWIN(p)->startDL / setupDL / bgDL[0].
- gfx_submitFrame_0004CDB0(ScreenWindow *): oneFrameDL[fbIndex], marks, curBg->frameStart;
  packets via `*(char **)&DLCTX(o)->gfx.cur` / DLBUF.
- gfx_endDL: checks 2-6 through `DLBuf *b`; the second append's int carrier q must stay.
- BaseLight_hostioParms(BaseLight *): no int casts (pointer args to the K&R CALLs; the
  hostio_addFloat alias prototyped with pointer params, float min / max).
- dnode.h: DNodeParms.name `const char *`, GdlParmV3.type `void *`.
- gdl/backup.h and gdl/coll.h are C++-safe (offset asserts under `#ifndef __cplusplus`; coll.h
  includes "node.h" relatively).

Next: GdlParm / GdlParmF.type -> `void *` and GdlParms.name -> `const char *` in gadget.h. That
removes DNode_ctor's 13 remaining `(int)&` stores, but game_libs.c (29 sites) and
bootup_uso_90CC.c (43) store into them too (area h), so it needs either a coordinated change or
h's sign-off. Then BasePolyShape_avgTriColour (6), gfx_submitFrameTask_000469A8 /
gfx_newDLContext (5), coll_markZeroWeight_0003C7A4, ItemMgr_spawnItem; census b top: BaseLight_ctor,
LightTarget_display (8). The HostIO device object itself (gHostio, Bss 0x3C768, 8 bytes;
HostioDev_vtbl) is still untyped.

## 23. Run 560 (agent-b): port-audit top, BaseLight_ctor / LightTarget, HostioDev, gl_data.h dup

Census (owner b raw struct-offset sites): 327 -> 288 (post0b 298 -> 259, post1b 26). port-audit
owner b: 135 -> 109 (A 52 -> 44, B 12, C 3, D 68 -> 50; run 553's 155 had been lowered to 135 on
main before this run). Two hand-edit commits, no renames; both gated (ROM byte-identical,
3288/3288, 0 mismatches in all three source checks); every post0b change left the matching and
NON_MATCHING objects identical in section bytes and relocations.

- **BasePolyShape_avgTriColour(BasePolyShape *, int tri, u8 *out)**: vtxColours / triList / tris,
  PolyTri.v. Byte levers: the indexed tri address `*(char **)&shape->tris` (the plain member moves
  the t-ring) and the loop entry `*(unsigned char **)&shape->vtxColours` (the plain member swaps an addu).
- **PolyShape_getFaceNormal(BasePolyShape *, tri, corner) -> f32 \***: it returns the corner's
  *vertex* normal (vtxNormals row of tris[tri].v[corner], through the optional 6-byte remap
  rows), so the name is wrong (a rename candidate: BasePolyShape_getCornerNormal). Levers
  `*(PolyTri **)&shape->tris` and `*(char **)&shape->vtxNormals`; `remap[v * 3]` as a u16 *
  moves the t-ring, so remap stays a byte pointer.
- **gfx_newDLContext**: the int carrier is a `DLBuf *buf`.
- **coll_markZeroWeight_0003C7A4(CollShape *)**: every triangle whose face normal has y == 0 (a
  vertical face) gets CollTri.tag = -1, which the queries skip. A better name would be
  coll_disableVerticalTris.
- **ItemMgr_spawnItem(ItemMgr *, ItemType *, int) -> Node \***: newItem (vtable slot 10), attached
  under the type, Node.name = &type->tag, then NodeMsg {7, arg} through slot 4 (handleMsg). The
  old `pad1[4]` + `stk[2]` frame is the 12-byte NodeMsg (its unset reply is the dead word at 0x38).
- **BaseLight_ctor**: MNode mflags / mtx, BaseLight flags / parms, BaseLightParms name / unk04 /
  colHead (the Parm stores at m + 0xC / 0x10 / 0x20 stay raw: GdlParm is area h's gadget.h).
- **LightTarget** (light.h) is a QNode: +0xDC pos (cvqs.trans), +0x114 queryPos (f32[3]: pos is
  copied there and passed to gfx_selectLights, whose result goes to unk108). LightTarget_display,
  _doCommand (0x72 sets mask) and _hostioParms ("LightMask" = mask, "Fade" = scale) use it. The
  `scale` member is really the HostIO "Fade" but timproc / bootup sites use the name, so it stays.
- **HostioDev** (new include/gdl/hostio.h): gHostio (Bss 0x3C768, 8 bytes) = {flags (bit 0
  HOSTIO_READY: hostio_init's handshake), connected (hostio_connect sets 1 after msg 0x21)};
  hostio_reset clears both and re-runs hostio_init. hostio_reset / init / connect take
  HostioDev *; math_logFloatDiffs passes HOSTIODEV(&gHostio) (gl_proto_5c810 prototyped with
  HostioDev * / char *). The other ~80 `&gHostio` arguments are untyped K&R calls (no int casts).
  HostioDev_vtbl (gl_data.h, "vptr store by app_staticInit_000412E8") was not tied to gHostio:
  the NCC donor only zeroes gHostio's first word (gHostio_412E8_m); its one vtable store goes to
  the object behind gSysLib_412E8_l. Unverified which object that is, so the vtable name may be wrong.
- gl_data.h: the second `gWindowDefaults` define (wave 2 list) is gone; its notes are merged
  into the first.

Left alone: gfx_submitFrameTask_000469A8's 5 sites are register levers in a hand-tuned exact
body (`(s32)&...->win.flags`, `(int)&gGfxLib + 0x254`, folded `0 * (int)p` uses). ZoneShape_build
(7): BasePolyShape +0x78 is a per-triangle u8 mark array (parse cmd 7 or ZoneShape_build's
alloc(nTris), Mesh_paint fills it), but typing it `u8 *` forces a cast in area a's
game_libs_o2_52CD4.c (`BASEPOLY(arg0)->unk78 = *q`), so it needs a coordinated change.
MemberCallback_invoke_0003A0C4 (7): the Cfront member-callback struct exists only in game/sun.h
(area g); a shared gdl one would collide by name.

Next: ZoneShape_build with the unk78 type (coordinate with a); `<block>` (9) and
dbg_printThreads (7); then port-audit Parms_addParm (4, after h's gadget.h retype), Node_Load (3),
PolyShape_getNormal8 (3), coll_offsetPointsByMtx (3); the two rename candidates above.

## 24. Run 566 (agent-b): parm base (gdl/parm.h), BasePolyShape.triMarks, SysLib vtable, renames

Census (owner b raw struct-offset sites): 288 -> 246 (post0b 259 -> 217, post1b 26). port-audit
owner b: 94 -> 68 (A 29 -> 24, B 12 -> 9, C 3, D 50 -> 32; main had lowered run 560's 109 to 94
before this run). Six commits, two of them pure renames; every commit gated (ROM byte-identical,
3288/3288, 0 mismatches in all three source checks), and all 1149 matching + NON_MATCHING objects
(timproc / bootup and the .cpp donors included) stayed identical in section bytes and relocations
(the renames changed only the reloc symbol names). Note: the Makefile has no header dependencies,
so an incremental make after a header edit does NOT rebuild the includers; only the gate's clean
build (or `rm -rf build`) checks a header change.

- **Renames**: PolyShape_getFaceNormal -> **BasePolyShape_getCornerNormal** (the vertex normal of
  tris[tri].v[corner]; the face normal is BasePolyShape_getFaceNormal 0x54210);
  coll_markZeroWeight_0003C7A4 -> **coll_disableVerticalTris** (CollTri.tag = -1 where the face
  normal's y is 0); HostioDev_vtbl_1E1B8_412E8_k -> **SysLib_vtbl_1E1B8_412E8_k** (and the gl_data.h
  macro, hand edit).
- **SysLib vtable**: app_staticInit_000412E8's TextRelocs put both donor objects _i and _l on
  gSysLib (Bss 0x3C740, Sym 73): ConsoleDev_vtbl (Data 0x21DA0, slots ConsoleDev_vfn0..3: -1 / -1 /
  -1 / void stubs) is stored at gSysLib +0x18 by the base ctor, then Data 0x1E1B8 (hostio_devWrite
  0, hostio_devRead 1, hostio_devSlot2 0, app_loadUso) by the derived implicit ctor. So 0x1E1B8 is
  gSysLib's own class vtable; gHostio (Sym 338) has no vptr. ConsoleDev_vtbl is gSysLib's base
  vtable, so "ConsoleDev" is probably also a poor name (the base looks like an abstract device:
  read / write / slot2 / slot3 all unimplemented).
- **include/gdl/parm.h** (new, owner b): GdlParmTag (the 4-char tag, a by-value 4-byte struct),
  GdlParmBase (0x10: next, tag, unk08 = Parms_addParm's 4th arg, type), GdlParmList (the
  "<Class>::Parms" head as {name, first}). Parms_addParm(GdlParmBase *, GdlParmList *,
  GdlParmTag, int) -> GdlParmBase * is over it. light.h BaseLightParms = name / first /
  GdlParmBase colParm / col[4] / unk28. Suggestion for area h: gadget.h's `char head[0xC]` in
  GdlParm / GdlParmF / GdlParmRGBA (and dnode.h GdlParmV3) could become the first three
  GdlParmBase members (or the whole base with `type` inside it), and GdlParms.unk04 the list
  head `GdlParmBase *first`; GdlParmRGBA.type is still s32.
- **BasePolyShape +0x78 = u8 \*triMarks** (one byte per triangle: parse cmd 7, or ZoneShape_build's
  alloc(nTris) + clear; ZoneShape_build calls Mesh_paint for every unmarked triangle). The one
  cast in area a's game_libs_o2_52CD4.c (`(u8 *)*q`) went in with a's OK.
- dbg_printThreads walks OSThread (libultra/os_thread.h) by tlnext to the priority -1 tail
  (id, state, context.pc).
- Node vtable calls through VT_SLOT: Node_Load slots 8 / 0, Node_Save 7, ItemType_load 10
  (newItem) and 8 on the new item; Node_def uses the NODE(c) attach idiom; LightTarget_doCommand
  takes a NodeMsg * (0x72 consumes one int of the payload stream).
- K&R `<block>` group: ColourItemType_ctor (vptr, colour), BaseMat_forEachVarArg_00051ED8
  (BaseMat.vptr, VT_SLOT 3), gfx_texelBytes (BaseMat.format / id, MAT_FMT_* names).
- PolyShape_getNormal8's port-audit B hits were float -> int conversions behind a redundant
  `(float *)` on vtxNormals.

Left alone: Node_handleMsg's payload (+4 read as int for 0xC, as s16 for 0xE: no single payload
type yet); coll_offsetPointsByMtx (+0x8C list of 40-byte point records: the owner class is not
proven to be CollShape, whose +0x8C is unk8C); gSkinMgrs per-site alias stores; the varargs align
idioms; gfx_submitFrameTask_000469A8 (register levers).

Next: port-audit b top: gfx_submitFrameTask_000469A8 (5, levers), coll_offsetPointsByMtx (3, needs
the owner class), FogParms_hostioParms (2), BaseMat_hostioParms (2), gfx_clearScreen (2),
ItemMgr_firstItemOfType, gfx_drawFbSplash_00048184, gfx_queueGfxTask_0004CEFC, Window_runTaskHooks,
ImageFileMgr_newFile_000688F8 (2 each); census b top: MemberCallback_invoke_0003A0C4 (7, Cfront
member-callback struct lives in game/sun.h, area g), Mat_print, ShapeNode_ctor_000521F8,
Friction_applyContact (6 each). Rename candidate: ConsoleDev_vtbl / ConsoleDev_vfn* (gSysLib's
base class).

## 25. Run 571 (agent-b): SysLibBase renames, RcpTask.window, ShapeNode, NodeMsgPayload

Census (owner b raw struct-offset sites): 246 -> 200. port-audit owner b: 68 -> 41 (A 24 -> 10,
B 9 -> 7, C 3 -> 1, D 32 -> 23). Four commits, one a pure rename; every commit gated (ROM
byte-identical, 3288/3288, 0 mismatches in all three source checks), and every changed object of
the matching and NON_MATCHING builds kept identical .text (with relocations), .data and .rodata
(clean rebuild after the rcp.h / material.h edits).

- **Rename** (pure): ConsoleDev_vtbl_412E8_j -> **SysLibBase_vtbl_412E8_j**, ConsoleDev_vfn0..3 ->
  **SysLibBase_devWrite_00061ADC / devRead_00061AF0 / devSlot2_00061B04 / loadUso_00061B10**.
  Data 0x21DA0 is gSysLib's base-class vtable (section 24); its four stubs have exactly the
  signatures of the derived overrides in SysLib_vtbl_1E1B8 (hostio_devWrite_00035990 (a0,a1,a2),
  hostio_devRead_000359A4 (a0,a1,a2), hostio_devSlot2_000359B8 (a0), app_loadUso (a0,a1)).
  The gl_data.h macro is now SysLibBase_vtbl (hand edit). ConsoleDev_init / ConsoleDev_setOrigin
  (the debug-console origin halfwords) are unrelated and keep their names.
- **rcp.h**: RcpTask.clipShape / .window are `struct PolyShape *` / `struct ScreenWindow *`.
  gfx_queueGfxTask_0004CEFC stores rec->window and ends GfxLib.oneFrameDL[fbIndex].
- gfx_drawFbSplash_00048184(GfxLib *): mainWindow->fbOwner->win.colorBuf[fbIndex].
- ItemMgr_firstItemOfType(ItemMgr *, tag, ..) -> void *: ItemType.node.children->item.
- Window_runTaskHooks(Window *), Window_display: Cfront calls through VT_SLOT (the camera's slot
  11, the window's own slot 12, each task hook's slot 0).
- ImageFileMgr_newFile_000688F8 / BinFileMgr_newFile_0006877C return ImageFile * / BinFile *.
- material.h: BASEMAT(p); BaseMat_hostioParms / Mat_print use geomFlags & MAT_GEOM_TEXTURED,
  unk14, unk4C, id, unk58 (printed as "%s": a short name string), minCut / maxCut.
- **ShapeNode** (0x40, local to post0b): Node + unk2C, polyFlags (one-word struct, the
  gPolyFlags_3EEC4 snapshot), geomMode (8-byte pair, gPolyGeomMode_3EEC8), unk3C. BasePolyShape
  has the same +0x30 / +0x34 members (ncc_526D0.cpp m30 Flags / m34 Blk2) but in the derived
  class, not in its Base, so it is not proven to derive from ShapeNode.
- **GfxObj** (0x18, local): GfxObjBase (0x14: items = mem_new(20), cap 5, unk0C) + vptr at +0x14.
- **NodeMsgPayload** (local to post0b, Node_handleMsg): +0 name (FIND_NAME), +4 union {s32 on
  (SET_FLAG80); s16 serial (FIND_SERIAL)}. The serial read needs `*(short *)&pl->v.serial`; the
  plain member read recolours t1 / t2 / t3 in two arms. node.h is untouched: NodeMsg.arg could
  gain a `NodeMsgPayload *` member (agent-a's header).
- Friction_applyContact's contact normal is `f32 *`; the eight Node-derived ctor vptr stores go
  through NODE()->vptr.

Left alone: gfx_clearScreen's two B sites (agent-g's int/pointer carriers `cnt` / `g`, one variable
for a count and a packet pointer, a colouring lever); gfx_submitFrameTask_000469A8 (5, levers);
Window_setupView's `(float *)*(int *)(camera + 0x14C)` (the dead-web reuse lever); GfxObj_ctor's
`a0 + 0x134` store (owner class of a0 unknown).

Next: port-audit b: coll_offsetPointsByMtx (3, needs the owner class), the varargs `<block>` /
TextWin_printf / sys_sprintf align idioms, Window_hostioParms (1); census b:
MemberCallback_invoke_* (7 / 5 x4, the Cfront member-callback struct is game/sun.h, area g: a
shared gdl one needs a distinct name), BaseLight_ctor (5, Parm stores wait for gadget.h),
CMod_callbackInvoke_000551E0 (5).

## 26. Run 578 (agent-b): raw-offset closeout for post0b / post1b*

Owner-b raw `*(T *)(p + K)` sites (census): 200 -> 108 converted-to-field 92, and the 108 left
all carry a same-line `/* RAW: <reason> */` (unknown-object 77, data-table 20, byte-lock 7,
donor-mirror 4). Same-line placement keeps line numbers (the MemberCallback recipes are
statement-layout sensitive).
- Cfront vtable calls now spell `VT_SLOT(vt, N).fn / .delta` everywhere in these files: delta at
  vt + 8 + 8N, fn at vt + 0xC + 8N. Byte-identical in every site tried (16 call sites).
- New / extended header types: `ColourItem` (item.h, 0x3C: Node, next at +0x2C, rgb[3] at +0x30),
  `MemHeap.size` (+0x28; gMainHeap is 44 bytes).
- Left for later (biggest unknown-object groups): the Cfront pointer-to-member callback record
  (MemberCallback_invoke family, 31 sites; {obj +4, s16 delta +8, s16 vslot +0xA, fn/vt-off +0xC}),
  gSysLib (0x28-byte system-services object, +0x14 frame counter, +0x1C message queue), MCamera
  (+0x14C fov), CamMan / Spinner / SeekNode structs.

## 27. Run 583 (agent-b): PMF callback, SysLib, render state, DLContext chains

Owner-b raw sites (census): 108 -> 51 (unknown-object 77 -> 27, byte-lock 7 -> 0, data-table 20,
donor-mirror 4); all 51 left are tagged, 0 unjustified. Every changed .o byte-identical in the
matching and NON_MATCHING builds (whole-object `objdump -drz` diff).
- `include/gdl/pmf.h` (new): `GdlPmf` = Cfront's `__mptr` {s16 delta, s16 vslot, fn | vptr offset};
  the 8-byte vtable entries have the same layout. `GdlPmfCallback` {vptr, obj, pmf, arg0, arg1} is
  the callback object (game/sun.h MemberCallback, envobj.h Tv1Callback are views of its first 16
  bytes). The six dispatchers (MemberCallback_invoke + _0003A044 / _0003A0C4 / _0003EBDC /
  _0003EC5C, CMod_callbackInvoke_000551E0) take `GdlPmfCallback *`; the one-line statement layout
  of the 35A18 recipe survives the field spelling unchanged. Default vptr offset 0x28 (Node) for
  the family, 0x5C for CMod.
- `SysLib` (sysapi.h; gSysLib, 0x28): frameCount +0x14, vptr +0x18, msgQueue +0x1C; `SYSLIB_AT(sym)`.
- `smallnode.h` (new): Spinner (speed +0x2C), SeekNode (target +0x2C, rate +0x30).
- `GdlRenderState` (dlctx.h): {unk0, flags}; flags & 0xFF render mode, & 0xF00 combine, >> 12
  geometry, bits 19 / 23 two-cycle. gfx_initDdm builds {gfx count, GdlRenderState}.
- The "+0x1C record" / "+0x2C record" chains are DLContext.vtx.cur / light.cur (gfx_findVtx,
  MorphPoly_allocUpdateList, gfx_setLightDirs). gfx_queueGfxTask_0004CEFC returns an RcpTask.
- DynArr_init_000665A4 initialises a DynArrPool (chunkSize, cur, nChunks), not a DynArr; a rename to
  DynArrPool_init is open. CamMan's +0 store is Node.unk00 (CamMan = camera.h FreeCam).
- Byte-locks cracked: QNode_setAnimPose `*(W3 *)&((Animator *)a1)->dst.trans`; CamFollow_update
  cast-to-struct reads with the cb += 0x70 step kept (named sub-struct S36C08Sub); gfx curWindow
  store `((GfxLib *)(int)&gGfxLib)->curWindow` with the 0 * (int)&gGfxLib folds kept.
- Left (unknown-object 27): message-6 sender +0xEC Vec3 (3), CollShape(?) +0x8C point list (3; the
  old tag said CollObj, which is 0x34), the gfx_findFaceVtxs object (+0x594, 3; its word 0 is a
  DLContext), Cfront inline member ctors (FW64 x2, the col-tag block x5), button-map record (2),
  8-byte list head (2), vFP1 callback record (2), and singles (MNode_ctor +0x40, B68 at obj +60,
  gfx_copyField64, frame-start cb vptr +0x5C, BasePolyShape_emitTriPosUv arg4 +0x40).
