# 1080 Snowboarding: the race camera (for port authors)

How the camera follows the rider. Types are in include/game/camera.h (1080 repo); names are the current repo
names. Written by agent-g run 475 from the matched code. "k" = a RoData constant not needed here.

## Index
- [1. Objects](#1-objects)
- [2. Who builds what (bootup cam_create)](#2-who-builds-what-bootup-cam_create)
- [2a. The course camera (game.uso CourseCam, 0x27C)](#2a-the-course-camera-gameuso-coursecam-0x27c)
- [3. The eye: SnowChaseActorCam](#3-the-eye-snowchaseactorcam)
- [4. The look-at point: SnowChaseActorLook](#4-the-look-at-point-snowchaseactorlook)
- [5. SnowChaseActor (the one-body variant)](#5-snowchaseactor-the-one-body-variant)
- [6. MCamera: view matrix and fov](#6-mcamera-view-matrix-and-fov)
- [7. Choosing the camera: CamDirector and RiderCam](#7-choosing-the-camera-camdirector-and-ridercam)
- [8. Debug cameras](#8-debug-cameras)
- [9. Open questions](#9-open-questions)

## 1. Objects

- **CamMNode** (0xB4): a libgdl matrix node. local matrix 0x30 (local[3] = its own translation), world matrix
  0x70 (world[3] = world position). The camera eye and the look-at point are both such nodes, and so is the rider
  (SnowBoarder's DNode base), so "the rider's axes" below are rows 0..2 of its world matrix.
- **MCamera** (game_libs, 0x150) = an MNode (the eye) + view matrix 0xB4, target node 0xF4, lookDir, pitch / yaw,
  up, fov 0x14C (85 by default).
- **Chase components** (game.uso): Node children whose parent (Node +0x14) is the body they move. They never set
  a velocity: each frame they call `math_mtxAddTranslation(&body->local, &delta)` with delta = gain * error,
  so every body eases exponentially toward its goal. Run at one step per frame (no dt).

## 2. Who builds what (bootup cam_create)

`cam_create(.., mode, parent, rider, pad)` (NCC donor bootup_uso_ncc_31C0.cpp; its classes carry these names
since run 485). The chase components' last ctor argument is their **parms file** (loaded when non-NULL), not a
parent; the parent link is a separate call:
- builds the look-at node "snowlookat" (LookAtNode, 0xB8: an MNode + its chase component at 0xB4);
- **modes 0 / 2:** the game.uso `CourseCam` (`cam_ctor_00000858(0, rider, lookat, 0, 500, -1500, pad,
  "rom/cam_info.bin")`, section 2a); under it a `SnowChaseActorCam(rider, rider->camSource, "rom/cam_ca.bin")`
  (stored at CourseCam.eyeChase); under the look-at node a `SnowChaseActorLook(anchor = the CourseCam, cam = that
  SnowChaseActorCam, "rom/lookat_ca2.bin")` named "LookAtChase". So in look modes 2 / 3 the look-at point goes
  1000 ahead of / behind the **eye**, along the rider's z axis;
- **mode 1:** a RiderCam (MCamera(lookat, 0, 500, -1500), section 7) and under the look-at node a
  `SnowChaseActor(rider, rider, "rom/lookat_ca.bin")` named "LookAtChase";
- all modes: both bodies go under `parent`; eye and look-at start at rider->startPos; the eye is then moved by
  (0, 0, -1000). `rider->camSource` (SnowBoarder 0x874, set by the rider ctor) is the body a mode-3 eye parks at.

The game.uso camera's views (cam_setView_00000AEC) switch the two components with
`SnowChaseActorCam_setMode(cam + 0x154, mode, &rider->vel)` and `SnowChaseActorLook_setMode(lookat + 0xB4, ..)`.

### 2a. The course camera (game.uso CourseCam, 0x27C)

The camera of modes 0 / 2 (`cam_ctor_00000858`, include/game/camera.h `CourseCam`; agent-g run 480) is an MCamera
that plays **scripted paths** from rom/cam_info.bin:
- `lists[view]` (0x158, `numLists` 0x1D0) is a CamList: up to 8 path indices played in order (`listPos` 0x254);
- `paths[i]` (0x1D4, `numPaths` 0x24C) is a CamPath (0x7C): per-channel modes plus `numKeys` and the key pointers;
- a CamKey (0x38) is look Vec3, eye Vec3, up Vec3, fov, frames (to the next key), rot Vec3 (pitch / yaw / roll).
`cam_updateView_00000B3C` evaluates a uniform cubic B-spline over keys k-1..k+2 at t = frame / key->frames for each
channel whose mode says "spline" (eye, look, up, fov, rot), else takes key k's value; `key` / `frame` (0x25C /
0x260) advance one frame per update, and the path ends after key numKeys (then the next path of the list).
`camPath_read` loads keys[1..numKeys] (at most 15) and pads keys[0] = keys[1], keys[numKeys + 1] = keys[numKeys];
a path with any spline channel (`camPath_hasSpline_00000674`) ends one key early, at numKeys.
Channel modes for look / eye (CamPath +0x00 / +0x10): 1 = chase component (camPath_init's default), 2 = keys
**relative** (`cam_applyRelative_0000052C`: eye += the chase aim point = rider->pos + rotated cof, then look +=
eye), 3 = keys absolute. Up is (0, 1, 0) on a chase path. The path writes the bodies it drives into local[3] and
copies local into world at once.
A path with `eyeMode == 1` / `lookMode == 1` hands the eye / look-at to the chase components (sections 3 and 4):
that is the in-race view. There the player cycles `chaseMode` (0x26C) with pad pressed 0x40 (0 -> 1 -> 2) and
holds 0x80 for 3 (look back; `savedChaseMode` 0x270 restores):

| chaseMode | eye component mode | look component mode | |
|---|---|---|---|
| 0 | 1 | 1 | normal chase (height toy) |
| 1 | 2 | 1 | chase at height ty2 |
| 2 | 3 | 2 | fixed eye, looking 1000 ahead |
| 3 | 3 | 3 | fixed eye, looking 1000 behind |

Modes 2 / 3 also set rider +0xA58 bit 0x2000. `view` (0x250) is picked by cam_command (commands 3..18) or, when
`rider->raceResult` changes (`lastResult` 0x264), by cam_pickResultView (result + game mode -> view 0..14).
`pad` (0x274) is the input pad: cam_create's p4.

## 3. The eye: SnowChaseActorCam

Parms (rom/cam_ca.bin; tags in construction order): cof (Vec3, default (0, 64, 0)), mxz, txz, cxz, miy, toy,
ty2, chy. Fields: target 0x38 (the rider), source 0x3C, mode 0x40, eyeOffset 0x2C.

- **Aim point** A = target position + target rotation * cof (`cam_toTargetLocal_000023D4` rotates cof by the
  rider's world matrix). With cof = (0, 64, 0) the camera aims a little above the board.
- **update (mode 1 / 2)**, with E = eye position (body world[3]):
  - horizontal: d = |A - E| in XZ, n = the XZ unit vector toward A. If d < mxz: move by n * (d - mxz) (back off
    at full rate); else move by n * (d - txz) * cxz (spring toward distance txz).
  - vertical: h = E.y - A.y (the eye's height above the aim point). If h < miy: move up by (miy - h); else move by
    (H - h) * chy, H = toy (mode 1) or ty2 (mode 2).
  - eyeOffset = n * txz - (0, H, 0) (stored, not used by the move).
- **mode 3:** eye = source position (both local and world translation): a fixed camera.
- **applyMode (snap on a mode change)**, v = the rider velocity passed by setMode: eye = A - normalize(v.xz) * txz
  + (0, H, 0) - (v.x / cxz, v.y / chy, v.z / cxz). The eye starts directly behind the direction of travel.

## 4. The look-at point: SnowChaseActorLook

Parm ch0 (gain). Fields: anchor 0x38, cam 0x3C (the SnowChaseActorCam), mode 0x40.
- **mode 1:** goal = cam's aim point A; move by normalize(goal - P) * |goal - P| * ch0, i.e. P += (goal - P) * ch0.
- **modes 2 / 3:** goal = anchor position + cam->target's z axis * 1000 (mode 2, ahead) / * -1000 (mode 3, behind).
- After moving, world[3] is set to local[3] at once (no wait for the matrix update).
The MCamera's target is the look-at node, so the view always points at P: the eye and the look-at point lag the
rider independently, which gives the swinging chase feel.

## 5. SnowChaseActor (the one-body variant)

Parms: off (Vec3), xxz, mxz, txz, mxy, miy, toy, cxz, chy (mxy / miy / toy unused by update). Fields: target 0x48,
lookBody 0x4C, toGoal 0x3C. update: goal = target position + target rotation * off; e = goal - body.
Vertical move e.y * chy. Horizontal distance t from lookBody: pull in by (t - xxz) beyond xxz, push out by
(t - mxz) below mxz. Then move by normalize(e) * (|e| - txz) * cxz plus that correction.

## 6. MCamera: view matrix and fov

`MCamera lookAt` (game_libs gl 33094, NCC donor game_libs_ncc_33094.cpp) builds `view` from the eye toward target's
world position (eye + lookDir * 10 without a target) with up (0, 1, 0), then turns it by pitch / yaw while
rotEnable. fov 0x14C is degrees (85 default).

## 7. Choosing the camera: CamDirector and RiderCam

**CamDirector** (bootup, 0x50): `window->cam` is the camera drawn. Auto mode: every 60 frames it looks up the
course "cam" node nearest rider->pos; when it changes, node kind 3..0x12 is sent to cams[0] (the game.uso path
camera) and other kinds to cams[1] (RiderCam) through the camera's command slot (vtable slot 12), and that camera
becomes active (`CamDirector_setActiveCam`, which also zeroes its pitch / yaw). Manual mode (pad pressed 0x40):
fov +-2 per frame (45..120) on held 8 / 4, pitch / yaw += stick * 2.

**RiderCam** (bootup, 0x15C; slot 3 cam_func_00004948, slot 12 cam_func_00004914): command(kind, node) puts the
eye at the node position + 100 up and sets mode = kind. Tick: kinds 0x13..0x17 (and 0x18..0x1C) pick fov from
the eye-to-target distance (row {far, near, nearFov, farFov}: linear in between); kinds 0x1D..0x26 from an angle row
{size, angle} clamped to [k, k']; mode 2 drifts the eye by rider->vel * k and restores baseFov.

## 8. Debug cameras

FreeCam (renames.tsv CamMan_*) is a fly camera (boom (0, 0, dist) turned by pitch / yaw around `pos`); CamFollow
is an orbit / pan controller. Neither is used for the race view.

## 9. Open questions

- Resolved in run 485: the cam_create chase classes (section 2), and CamDirector_update, the cam_create donor and
  the B3C donor (MIPSpro 7.2.1 edgcpfe) are on camera.h / snowboarder.h fields (bytes unchanged).
- CamPath unk08 / 0C / 18 / 1C / 24 / 2C (read with the mode words, never used) and CourseCam 0x278 are unread.
- What the rider body at camSource (0x874) is. Run 488: slot 22 of the shape-file node registry (bootup Bss
  0x3C058, Sym 550; docs/1080_GAME_CLASSES.md section 17); the body part needs the rider shape stream.
- Run 488: MCamera_ctor, CamFollow_ctor and CamDirector_ctor store their vptrs through the gl_data.h `_vtbl` aliases.
- The RiderCam fov tables (bu_4948_t16 / t8, k0 / k1 / klo / khi) are not resolved to RoData addresses.
