# 1080 Snowboarding: rider physics (for port authors)

How one rider (`SnowBoarder`, bootup.uso, 0xA8C bytes, include/game/snowboarder.h) moves each frame.
Function names are the current repo names; offsets are SnowBoarder offsets. Written by agent-g run 470 from
the matched code. "k" means a RoData constant whose value was not needed for the explanation.

## Index
- [1. Object layout](#1-object-layout)
- [2. Frame order](#2-frame-order)
- [3. Orientation and edge (SnowBoarder_updateOrient)](#3-orientation-and-edge-snowboarder_updateorient)
- [4. Friction and edge grip (SnowBoarder_updateDyn)](#4-friction-and-edge-grip-snowboarder_updatedyn)
- [5. Ground and contacts (SnowBoarder_procColl)](#5-ground-and-contacts-snowboarder_proccoll)
- [6. Integration (game_libs DNode)](#6-integration-game_libs-dnode)
- [7. Speed limits and catch-up (SnowBoarder_limitSpeed, SnowAI)](#7-speed-limits-and-catch-up)
- [8. AI steering (game.uso SnowAI)](#8-ai-steering-gameuso-snowai)
- [9. Open questions](#9-open-questions)

## 1. Object layout

- **0x000..0x3D4: the game_libs DNode** (dynamics node). pos 0xB4, orient 0xCC (quat x y z w), lastPos 0xDC,
  lastOrient 0xF4, `dparms` 0x108 ("DNode::Parms": gvt = gravity, tsc = accumulator time scale, cog = centre of
  gravity, imp / spd / vsc = contact response values), surfImp / surfSpd / surfVsc 0x288 (the per-surface copies
  the contact solver uses), two force accumulators (impulseAcc 0x294, moveAcc 0x2C8), angVel 0x2FC (a rotation
  quat applied once per frame), velDir 0x30C, vel 0x318, worldCog 0x324, velDelta 0x330, lastVel 0x33C, speed
  0x348; body axes up 0x3B0, side 0x3BC, dir (forward) 0x3C8.
- **0x3EC: SnowBChild** with its own Parms (ground handling: ied ifr ded dfr efr nbf nel dbf del res flx sta).
- **0x540: SnowBoarder::Parms** (29 float parms: hpf snf dsf icf tfc edf bdf ure mro mpi mdr axr ayr azr tlt wfr
  sfr dts nts trt twt min max jmp djp ufs bdm cdm tch). Values come from the parms file; the struct comments say
  which reader uses each.
- **0x800 input**: the controller object the rider reads. +0x0 stick x (f32), +0x4 stick y, +0x10 held buttons.
  For a CPU rider SnowAI writes this same object (section 8), so the physics never knows who is steering.
- 0x804 ai, 0x840 anim (RiderAnim), 0x848 controller (0 pad, 2 CPU), 0x8C4 character, 0x908 rival.
- 0x820..0x874: model nodes from the rider node list (bootup Data 0xABBC, docs/1080_GAME_CLASSES.md section 20):
  bodyNodes (boarder_a, board_a, legL / legR joints 2-3, waist), 0x844 "top" (the root), 0x864 the board shape
  node, 0x874 camSource = the head node.
- 0x910..0x9E4: contact and ground state (section 5); 0x9F8..0xA00: edgeFriction, edgeGrip, turnRate
  (section 4); 0xA04 localUp; 0xA1C..0xA24 bump response; 0xA58 flags; 0xA78 maxSpeed.

## 2. Frame order

`SnowBoarder_update` (vtbl slot 3) runs perf sections "SnowBai" (AI), "SnowBDyn", "SnowBAnm" (RiderAnim),
"SnowBChild". SnowBDyn is `SnowBoarder_updateDyn`, which is the DNode_update pipeline with rider steps in front:

1. rebuild friction / edgeGrip / edgeFriction / turnRate from the parms (section 4);
2. `SnowBoarder_limitSpeed` (section 7);
3. `SnowBoarder_updateOrient` (section 3);
4. `SnowBoarder_procColl`: ground query, then `DNode_solveContacts` (collider contacts) (section 5);
5. `DNode_applyAccums_00065448`: apply the force accumulators;
6. if slowdown == 100 and speed < 30: vel.x = vel.z = 0 (stopped);
7. `DNode_integrate_00064DEC`: gravity, rotation, position;
8. `DNode_resetAccums_00065148`: clear the accumulators, recompute worldCog.

After it, SnowBoarder_update computes fwdSpeed 0xA38 = dot(dir, vel), applies the `shake` jitter to six body
nodes (board and both lower legs by shake, both upper legs by half, the waist by minus half), and feeds the sound object (0x808) with contactSurface and landImpact.

## 3. Orientation and edge (SnowBoarder_updateOrient)

Bootup 0xB75C; matched C is src/bootup_uso/bootup_uso_ncc_B75C.cpp (on snowboarder.h fields since run 475).
Every rotation is `math_quatRotateAxisAngle(&orient, axis, angle, this)`.

- **Steering input.** steer = stick x * 0.15, yaw = stick x * -0.04 (both 0 while slowdown == 100).
- **Edge angle.** edgeSteer -= edgeSteer * trt * turnRate, then += steer * turnRate. edgeSlope eases (factor 0.4)
  toward -side.y, the slope's roll under the board (0 while crouching). edge = edgeSteer + edgeSlope, negated when
  mirrored (flags 0x80 = stance), clamped to [-1, 1]. `edge` drives friction while crouching (section 4), the
  carve animation (RiderAnim_selectAnim) and `shake`.
- **Target up (localUp 0xA04).** World up expressed in body axes (dot with dir, -side, up). On gentle ground
  (groundGentle, procColl) with groundFlags bit 1 clear, the ground normal is used instead.
- **In the air (contactCount == 0).** angVel is reset to identity, shake = 0.
  - With groundFlags bit 1 set and pad button 0x200 held: after 11 frames, airSpin += stick x * 0.015
    (clamped +-0.2).
  - Otherwise, with groundFlags bit 1 set: yaw about up by -stick x * ayr. Without it: self-right about dir
    by -0.1 * side.y. While unkA18 is set, also the trick rotations: stick x * azr about dir, stick y * axr
    about side, -stick x * ayr about up.
  - With groundFlags bit 1 set: vel.x = 0 when up.y < 0.8, then yaw about up by -airSpin.
- **On the ground.** airSpin / spinHold reset; shake = 20 + 30 * |edge|.
  - With groundFlags bit 1 set: the sound object gets an update; when not slowed, vel.x += vel.x * hpf * |dir.x|;
    yaw doubles while up.y < 0.8.
  - Otherwise, a counter-steer test: when dot(dir, velDir) < mdr and the yaw input opposes the sideways slip
    (dot(side, velDir)), shake += 20, `pad_setIfNewer_00067A54(input, bootup Data 0x8170, 1, this)` is called (probably a rumble
    or effect event; unproven) and the yaw is cancelled. Then self-righting: when |localUp.y| > mro, rotate about dir by localUp.y * ure; when
    |localUp.x| > mpi, rotate about side by localUp.x * ure.
  - Finally yaw about up by `yaw`: this is the actual turn.
- **angVel decay.** k = 0.724 with groundFlags bit 1, else parms.tch: angVel.xyz *= k, angVel.w eases to 1.

## 4. Friction and edge grip (SnowBoarder_updateDyn)

Per frame, from SnowBChild Parms (`child.parms`) and SnowBoarder::Parms:

- crouch 0x990 = stick y < -0.75; useDParms 0x9CC = button 0x400 held (the alternate parm set).
- edgeFriction = efr; edgeGrip = del or nel; friction = dbf or nbf; turnRate = res * (dts or nts).
- Crouching: friction += |edge| * (0.5, or a RoData value with useDParms).
- By `surface` 0x9A2 (ground surface code while close to the ground, else 0): 'c' (0x63): friction *= ifr,
  edgeGrip *= ied; 'b' (0x62): * dfr / ded; 'a' (0x61): unchanged; anything else (airborne): friction += k,
  edgeGrip = edgeFriction = 0.
- edgeGrip *= edf, friction *= bdf. If slowdown 0x960 (percent, set by RiderAnim on crashes) is non-zero:
  edgeGrip = 0, friction += slowdown / 100, vel.xz *= 1 - sfr.

**Who consumes them.** SnowBCollider_edgeGrip_0000E2D0 (bootup_uso_o2_E2D0.c) is the edge-grip response: it projects
the velocity and the side axis onto the contact plane, takes the lateral component times edgeFriction, clamps it
to +-edgeGrip, scales by (1 + arg) and adds it as an impulse, so the edge resists sideways slip (carving).
`friction` (0x360) is read by the contact solver; turnRate scales the edge steering in section 3.

## 5. Ground and contacts (SnowBoarder_procColl)

Bootup 0xC234; matched C is bootup_uso_ncc_C234.cpp (on snowboarder.h fields since run 475).

- prevPos / prevVel snapshots; msgCooldown counts down.
- **Ground query.** `CollShape_nearestHit(course, &lastPos, 4000, &hit)`: groundSurface 0x9A0 and groundFlags
  0x9A8 from the hit triangle (BasePolyShape helpers), groundDist 0x9D0, surface = groundSurface when
  groundDist < k. onGround when the hit plane is within reach of lastPos (or there are contacts): groundNormal,
  groundPlaneD, groundGentle = normal.y > k; else normal (0, 1, 0). Below the ground (dist < 0) vel.y = 10.
- Contacts at speed > 10 on surface 'd' / 'c': shake 100 / 70 and `pad_setIfNewer_00067A54(input, table[kind + |edge| * 3], 2)` (Data 0x81C0).
- **Per-surface contact values.** 'a': surfImp / surfSpd / surfVsc = dparms imp / spd / vsc and impactScale =
  snf; 'b': 0, k, k and dsf; other: k, k, k and icf (ice). 'a' / 'b' also read the triangle colour into
  groundColor (BasePolyShape_avgTriColour; the display tints with it).
- No ground: noGroundFrames counts; after 151 frames the rider is put 200 units above the nearest course point
  (`DNode_resetXform_00065360`).
- **Collider contacts.** contactCount / contactNormal / contactDepth are cleared, then `DNode_solveContacts` runs
  the child colliders (SnowBCollider, 0x178: probe velocity 0x114, world point 0x120, touched triangle 0x14C, rider
  0x170, flags 0x174); each contact calls `SnowBCollider_onContact(collider, depth, normal)` (bootup_uso_ncc_8BD4.cpp):
  - body probes (flags & 0x1F0), depth < 0, triangle surface not 'a' / 'b' / 'c' (snow): count it, contactSurface =
    the code, depth clamped to -30, hitFlags |= flags (stumble), pos += normal * -depth * 0.5 (push out),
    contactNormal += normal, contactDepth += depth, impulse normal * -depth at the probe point;
  - board probes (flags & 0xF), depth < 50: count it, hitFlags |= flags, contactDepth += depth, contactNormal +=
    normal, then the edge grip (SnowBCollider_edgeGrip_0000E2D0 with edge^2, section 4) and the collider's
    friction method (Friction_vfn11_00063F34(collider, depth, normal, 0.1)). contactCount == 0 is the "in the air" test used everywhere
  (limitSpeed's wfr drag, updateOrient).
- **Averaging.** With contacts: contactNormal / contactDepth are averaged; penetration = normal * depth when
  depth < 0; impactVel = normal * -min(dot(lastVel, normal), 0); airFrames = 0. Without: airFrames++.
- **Bump response.** bumpSide += dot(side, impactVel) * impactScale, bumpUp += dot(up, impactVel) * impactScale,
  bumpFwd -= dot(dir, impactVel). RiderAnim reads bumpSide (stumble side); SnowBoarder_update clears them.
- groundFlags 0x400 switches the sound object; unk91C eases toward a value (1.0 off such ground) for the light at
  0x850.

## 6. Integration (game_libs DNode)

game_libs_post1b.c. Accumulator = {weight, pointSum, force, torque, origin} (SnowBAccum).

- `DNode_addImpulseAt_00065250(this, worldPoint, force)` / `DNode_addMoveAt_000652D8`:
  `DNodeAccum_addForce_000641DC(acc, worldPoint - worldCog, force)`, which adds |force| to weight, point * |force| to pointSum,
  force to force and cross(point, force) / |point| to torque.
- `DNode_applyAccums_00065448`: `DNodeAccum_apply_00064388(impulseAcc, &angVel, &vel, tsc)` and
  `(moveAcc, &orient, &pos, tsc)`. When weight is above epsilon, apply rotates the quat about the normalized
  torque by |torque| / k * tsc and adds force to the vector.
- `DNode_integrate_00064DEC`: normalize angVel; orient = angVel * orient; vel.y += gvt; pos += vel;
  velDelta = vel - lastVel; lastVel = vel; a helper call on orient (unresolved blank import, probably a normalize); lastPos / lastOrient snapshots; speed = |vel|;
  velDir = vel / speed.
- `DNode_resetAccums_00065148`: reset both accumulators (origin = lastPos), worldCog = node matrix * cog.

There is no explicit dt: one call per game frame. A port must run the same fixed step.

## 7. Speed limits and catch-up

`SnowBoarder_limitSpeed` (0xB520): with flags 0x100, input bits 4 / 8 nudge vel along dir. maxSpeed eases toward
parms.max; with flags 0x20000 (CPU rubber band) it gets +-k when the rival is more than k' ahead / behind in z.
vel is rescaled to maxSpeed when speed exceeds it. In the air (contactCount == 0) vel.xz *= 1 - wfr.
SnowAI (game.uso) also sets parms.max per rival character (ms1..ms8) and temporarily scales max / nts / dts / nbf
(SnowAI_scaleRiderParms, dd2..dd4) as a catch-up boost.

## 8. AI steering (game.uso SnowAI)

SnowAI (include/game/snowai.h) runs in the "SnowBai" section before the physics. It never moves the rider
directly: every state ends in `SnowAI_applyStickInput` (0x7538), which writes stick values (from a table at
game.uso Data 0x638) into the rider's input object, so CPU riders go through exactly the steering in sections
3 and 4. States: SnowAI_steer (follow course nodes; at forks it picks a branch by the bj / bt / bd / bu parms of
the current level), SnowAI_finishRun, SnowAI_timeoutRun, SnowAI_recoverStuck (after 75 frames below speed 30).
SnowAI_scanNodes / scanSegments re-acquire the path, one node per frame. The "course nodes" are CourseMarker
types (mrk, mk1..mk9, mkl, mkr), each resolved to the nearest marker of that type: docs/1080_COURSE.md section 6.

**The aim (agent-g run 502).** Each SnowAI_steer frame builds an XZ aim vector from the rider to a point, and
the stick follows the signed angle between the rider's dir and that aim (turnGain, turnSpeedRef). `SnowAI.aimMode`
picks the point:
- 0, `SnowAI_aimAlongSegment` (0x7C1C): the end of the current segment (the marker's `link`). While the rider
  leads the rival (sideBlock, a hysteresis on SnowAI_rivalLeadZ against +-leadLimit 1000) by at most 3000 in z,
  the point moves half the segment width (250 * wid / 2) to the rival's side, which blocks the rival's line.
  The point is kept inside the segment width.
- 1, `SnowAI_aimWeave` (0x8CD8): entered when rivalLeadZ <= weaveLead and speed >= minSpeed (70) on a plain
  segment, left when the lead passes the per-level `se` parm. It lays two waypoints (weaveAim / weavePrev) along
  the segment, speed * weaveLeadTime / 2 apart, and offsets each new one sideways by 250 * width * weaveSideScale
  times 0, -1, +1, +1 in turn (weavePhase): the CPU rider weaves across the course.
Two segment tests drive the rescans: `SnowAI_isInSegmentWidth` (0x9B88; the rider between the left and right
edges, half width 250 * wid + 50 at the marker, widening by the link's wid) and `SnowAI_isAboveSegmentFloor`
(0xA0E8; the rider above the marker -> link slope minus 400). When a marker flag asks for them and they fail,
steer starts SnowAI_startNodeScan / startSegmentScan. At the finish (MARKER_F_FINISH) a rider that trails
picks the nearer of the `mkl` / `mkr` branches (`SnowAI_pickFinishBranch`, 0x6FA8). `SnowAI_isRivalInPath_000097EC`
tests whether the rival is within 500 of the rider's relative path over the next 20 time units.
The tunables are in snowai.h with their ctor values.

## 9. Open questions

- groundFlags bit 1 (air-spin / yaw mode, 0.724 decay) and bit 0x400 (sound + light): which course attribute they are.
- unkA18 (enables the air trick rotations): no writer found in bootup; probably RiderAnim (game.uso) by offset.
- The contact solver's use of surfImp / surfSpd / surfVsc and `friction` (DNode_solveContacts, NCC donor
  game_libs_ncc_65494.cpp) is not yet written up.
- The exact RoData constants (the k values above) are in bootup RoData 0x8C8..0x9A0; read them from the ROM.
- Friction_vfn11_00063F34 (the collider's game_libs friction response) is not written up.

The camera that follows the rider is in docs/1080_CAMERA.md.
