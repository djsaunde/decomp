# 1080 Snowboarding: the race camera (for port authors)

How the camera follows the rider. Types are in include/game/camera.h (1080 repo); names are the current repo
names. Written by agent-g run 475 from the matched code. "k" = a RoData constant not needed here.

## Index
- [1. Objects](#1-objects)
- [2. Who builds what (bootup cam_create)](#2-who-builds-what-bootup-cam_create)
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

`cam_create(.., mode, parent, rider, p4)` (NCC donor bootup_uso_ncc_31C0.cpp):
- builds the look-at node "snowlookat" (an MNode + a chase-component pointer at 0xB4);
- **modes 0 / 2:** the game.uso camera `cam_ctor_00000858(0, rider, lookat, 0, 500, -1500, p4,
  "rom/cam_info.bin")` (0x27C, MCamera base, course camera paths: docs/1080_GAME_CLASSES.md section 12); a chase
  component from "rom/cam_ca.bin" under it (stored at cam + 0x154: the SnowChaseActorCam the views drive) and one
  from "rom/lookat_ca2.bin" under the look-at node (lookat + 0xB4, name "LookAtChase");
- **mode 1:** a RiderCam (section 7) and a "LookAtChase" component from "rom/lookat_ca.bin";
- all modes: eye and look-at start at rider->startPos; the eye is then moved by (0, 0, -1000).

The game.uso camera's views (cam_setView_00000AEC) switch the two components with
`SnowChaseActorCam_setMode(cam + 0x154, mode, &rider->vel)` and `SnowChaseActorLook_setMode(lookat + 0xB4, ..)`.

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

- cam_create's p4 (player or window index?), and the exact classes of the cam_ca / lookat_ca chase objects
  (WR / W4 / WV in the 31C0 donor; likely SnowChaseActorCam / Look / SnowChaseActor by file name).
- The game.uso camera (0x27C) fields beyond 0x150 rider / 0x154 chase component / 0x274 p4 are not typed yet.
- The RiderCam fov tables (bu_4948_t16 / t8, k0 / k1 / klo / khi) are not resolved to RoData addresses.
