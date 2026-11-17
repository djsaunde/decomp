# 1080 input recording, replay and ghosts (for port authors)

agent-c run 490. Sources: bootup_uso_o0_12B7C.c / 12DA4.c / 12BF8.c (replay_*),
bootup_uso.c (game_setupSolo / VsGhost / Replay), game_libs_o2_675A4.c (pad_update),
game_libs_post1b.c (pad_startRecord / pad_startPlay), game_libs_tail.c (Backup ghost),
titproc_uso_5DC.c (vs-ghost states). Types: include/game/input.h (InputMgr, InputPad,
InputFrame), include/gdl/backup.h (BackupGhost, BackupSession, Backup). Call targets were
read from the bootup TextReloc table (/tmp/claude-1000/c478/buxref.py), not guessed.

## Summary

1080 has no state snapshots. A replay or ghost is the **controller input of one rider, one
4-byte frame per game frame**, fed back through the pad object while the physics runs
again from the same start. A port must therefore keep the simulation deterministic for a
given input stream: the same course, rider, board, start state and frame order.

## The frame (InputFrame, 4 bytes)

| off | type | value |
|---|---|---|
| 0 | s8 | stick x (raw, before the /80 scaling and the 0.2 dead zone) |
| 1 | s8 | stick y |
| 2 | s16 | buttons: `recordMask & held & 0x1700` |

`held` is the pad's game-level button word (InputPad +0x10). pad_update rebuilds the four
stick-direction bits (0x4000 / 0x10000 / 0x2000 / 0x8000, |stick| > 0.5) every frame, so
they are not stored; only the 0x1700 buttons are. The replay_begin* functions set the
recording pad's recordMask to 0xFFFBFFFF (clears 0x40000 in the mask; it does not change
the 0x1700 bits that are stored).

## Pad side (game_libs, InputPad)

| field | off | meaning |
|---|---|---|
| replayMode | 0x4C | 0 off, 1 PLAY (pad_startPlay), 2 RECORD (pad_startRecord) |
| replayFrame | 0x50 | frame index; pad_update increments it first, then stops at replayLen |
| replayLen | 0x54 | frames to play, or the record capacity |
| replayLenOut | 0x58 | RECORD: `*replayLenOut = replayFrame` every frame (the caller's length) |
| replayFrames | 0x5C | the InputFrame buffer |
| recordMask | 0x6C | ANDed into the stored buttons |
| mirrorX | 0x70 | nonzero: the stick x byte is negated before recording / use |

pad_update, per frame (when the pad is not paused, +0x68 == 0): read the controller
(when one is attached, +0x34), mirror x, then if replayMode != 0: `replayFrame++`; at
`replayFrame >= replayLen` replayMode = 0; RECORD writes frames[replayFrame] from the live
stick bytes and buttons, PLAY ORs frames[replayFrame].buttons into held and **replaces**
the stick bytes. The float stick (/80, dead zone 0.2) and the direction bits follow from
the bytes, so playback goes through the same path as live input.

pad_open(pad, port): 1 attaches the controller, 0 makes a pad that only plays back
(setupVsGhost's ghost pad, setupReplay's pad).

## Manager side (bootup, InputMgr)

| field | off | meaning |
|---|---|---|
| recordBuf / recordCap | 0x160 / 0x164 | player 1's buffer, allocated once by the GameFlow ctor: cap = Backup.ghostMaxFrames (6400), size cap * 4 |
| replayData[2] / replayLen[2] | 0x168 / 0x170 | the last recording per player; replayLen is the pad's replayLenOut |
| recCourse / recRider / recFlags / recBoard | 0x178..0x17B | course and rider setup of the recording (bytes) |
| ghostRider / ghostFlags / ghostBoard | 0x181..0x183 | the rider setup of the ghost (or replay) to spawn |
| session | 0x14C | open BackupSession; session->ghost is the saved ghost |

Functions (bootup):
- `replay_beginRecord1P(mgr, pad, -)`: replayData[0] = recordBuf if unset; copy course /
  playerRider / playerFlags / playerBoard into rec*; pad_startRecord(pad, replayData[0],
  recordCap, &replayLen[0]).
- `replay_beginRecord2P(mgr, pad1, pad2)`: as 1P for pad1; player 2 gets replayData[1] =
  mem_new(recordCap * 4) on first use.
- `replay_beginRecordWithGhost(mgr, pad, ghostPad)`: ghostPad plays session->ghost (data,
  count); pad records as 1P.
- `replay_beginPlayback(mgr, pad, ghostPad)`: pad plays replayData[0] / replayLen[0];
  ghostPad plays the saved ghost.
- `replay_saveGhost(mgr, mode)`: Backup_openSession(0, backup, 3, -1), mem_new + memcpy of
  replayLen[0] frames, Backup_ghostSetHeader(ghost, mode, recCourse, recRider, recFlags,
  recBoard, data, replayLen[0]), Backup_writeGhost, Backup_closeSession(session, 3);
  demoIndex = -1.
- `replay_freeRecord(mgr)` (mem_delete of replayData[1]), `replay_clearRecord_00012BF8`.

Race setup (bootup.uso, TextReloc-checked):
- `game_setupSolo`: pad_open(o, 1), input_addRacePad, **replay_beginRecordWithGhost(mgr, o,
  0)**: every solo race records player 1, which is what the post-race replay shows.
- `game_setupVsGhost`: live pad o1 (port 1) and playback pad o2 (port 0), both added,
  beginRecordWithGhost(mgr, o1, o2); the player rider from playerRider / Flags / Board
  (flags | 1 | 0x10000 | 0x40000, tag 0x1B), the ghost rider from ghostRider / Flags /
  Board (flags | 0x8 | 0x8000, tag 0x14). Both riders share one camera window.
- `game_setupReplay`: one playback pad, replay_beginPlayback(mgr, o, 0), the rider from
  ghostRider / Flags / Board (flags | 0x8001 | 0x10000 | 0x40000).
- h2h / mgr: `h2h_startReplay` restarts the race and pad_startPlay(replayData[p],
  replayLen[p]) on both pads, timeout (u16)(min len + 0xF); `mgr_startReplay` is the
  1-player twin (docs/1080_MODES.md, run 471).

## Saving the ghost (run 495)

Only the post-race "save ghost?" prompts call `replay_saveGhost`, read from each module's own
Sym import table (kind-1 entry: module 0 = bootup, word3 top half = bootup Sym index; script
/tmp/claude-1000/c495/xmod.py, statically, no emulator dump):
- timproc.uso (time attack) `TimMenu_handleInput_00002A8C`: `replay_saveGhost(&gInputMgr,
  BACKUP_MODE_TIME)`;
- trkproc.uso (trick attack) `TrkMenu_handleInput_00002C98`: the same with BACKUP_MODE_TRICK.
The stick (0x10001 / 0x4002) moves the cursor obj+0x58 between 0 (save) and 1 (skip). Confirm
(0x40100) on row 0 plays snd 5 and saves; otherwise it plays 0x802 and skips. No other module
(titproc, mgrproc, h2hproc, arcproc, trnproc, genproc, viewrec, game) imports it. So a ghost is
only ever written from a solo time / trick run that the player chose to keep. h2hproc imports
replay_freeRecord (5 sites) and pad_startPlay; mgrproc and titproc import pad_startPlay.

## The saved ghost (SRAM)

BackupGhost (0x10, SRAM 0x218, checksum 0x228, data words at 0x230, mirror header at
0x7FE8): bits = mode 0-1 (BACKUP_MODE_TIME 1 / TRICK 2), rider 2-4, board flag 5 (0x20),
board 6-9, course 10-13; count = frames; data = RAM pointer (zeroed in SRAM).
Backup_openSession keeps the ghost only when its mode and course match the request
(course -1 = any). titproc's vs-ghost states (tit_procMain 7 / 9) copy rider / board flag /
board into InputMgr ghostRider / ghostFlags / ghostBoard (tit_imp_Backup_ghostGet*) and take
the ghost's course as InputMgr.course before game_setupVsGhost runs. 6400 frames is the cap
of both the RAM buffer and the SRAM area (6400 * 4 = 0x6400 bytes).

## Open

- InputMgr +0x184 (cleared by every begin / save), recordMask bit 0x40000, the 0x1700
  button bits' meaning (game buttons after the pad remap).
- Resolved (run 495): `replay_addInput` is now `input_addRacePad`. InputMgr +0x100 racePads
  are the pads that input_pauseRacePads / input_unpauseRacePads pause (pad_setPause); it does not
  record anything.
- viewrec.uso: see the next section (it has a code segment now and is fully named).

## viewrec.uso: the records / options screens (agent-a run 796)

viewrec.uso ("GENNewRecords Process", ROM 0x642312) is not only a replay viewer: it is the records and
options module (course times / scores, arcade records, erase, replay the saved ghost, sound, language).
Types: include/viewrec.h. Sources: src/viewrec_uso/viewrec_uso.c plus the C++ donors
(viewrec_uso_ncc.cpp, _ncc_2d0.cpp, _mp72_3878.cpp, _mp72_4990.cpp, which keep their own layout mirrors).

Classes (the Node name strings in Data; vtables read from the Data Reloc section, slot 3 update, 4
handleMsg, 13 drawGui; the proc field each ctor result is stored in by GENNewRecordsProcess_ctor):

| class | ctor | size | vtable | proc field | proc->mode (VR_MODE_*) | shown by |
|---|---|---|---|---|---|---|
| GENNewRecordsProcess | 0x2D0 | 0xE0 | Data+0x18 | - | - | the title flow (mode = ctor arg 2) |
| MainOptions | 0x1748 | 0x58 | Data+0x98 | mainOptions | 0x10000 | vr_backToMainMenu |
| RecordOptions | 0x1B4C | 0xA0 | Data+0x118 | recordOptions | 0x1000 menu, 0x2000 times, 0x4000 scores, 0x8000 arcade | vr_showRecordOptions |
| EraseOptions | 0x36B4 | 0xC8 | Data+0x198 | eraseOptions | 0x80000 select, 0x2000000 confirm | vr_showEraseOptions |
| ReplayOptions | 0x4518 | 0x9C | Data+0x218 | replayOptions | 0x4000000 | vr_showReplayOptions |
| SoundOptions | 0x4854 | 0x98 | Data+0x298 | soundOptions | 0x40000 | vr_showSoundOptions |
| LanguageOptions | 0x5200 | 0x70 | Data+0x328 | languageOptions | 0x20000 | vr_showLanguageOptions |

The main menu rows (MainOptions_buildMenu) are the vr_show* callbacks; the Replay row is added only
when the word at 0xA0000284 is 0x240B17D7, and it is disabled when no ghost is saved
(Backup_ghostGetMode == 0). Data+0x3A0 is a 1-slot vtable whose slot is vr_resetColours.

**Replay.** ReplayOptions_drawGui shows the saved ghost (Backup_ghostGetCourse / Rider / Board /
Mode - 1, vr_drawGhostRow); ReplayOptions_input on A / Start sets GameFlow procState =
Backup_ghostGetMode + 6, nextProcState = 1 and fades out, so the title flow runs the ghost's mode
(time / trick) in replay; B returns to the main menu. viewrec never calls replay_saveGhost or
pad_startPlay itself.

**Erase.** EraseOptions_selectInput picks the set (0 course times, 1 course scores, 2 arcade, 3 ghost,
4 all) and for 0 / 1 a course on the 2 x 4 grid; the set goes into proc->nextMode (VR_ERASE_*).
EraseOptions_confirmInput (yes / no) calls Backup_sessionResetCourseTimes / Scores (session, course),
Backup_sessionResetArcade / Ghost (session), or for "all" Backup_resetAll_0000B710 and a game-flow
restart (procState = nextProcState, GameFlow +0x84 = 0, +0x88 = 1).

Helpers: vr_loadSprites / vr_initLabels (sVrSprites / sVrLabels; vr_initLabels re-runs on handleMsg
21, "recaching language"), vr_pushMenu / vr_popMenu (proc->menuStack), vr_drawBackground,
vr_drawTitleArrows, vr_drawCenteredLabel, vr_drawFooterLabels, vr_drawRankRider, vr_drawTimeDigits,
vr_drawTime ("%d[%02d]%02d"), vr_drawNumber ("%07d"), vr_drawTrickLabel. vr_emptyStub_00000278 /
280 / 288 are unreferenced `jr ra` stubs with no Sym entry.

Open: RecordOptions +0x84 / EraseOptions +0x58..0x68 / ReplayOptions +0x5C..0x7C, +0x84.. (layout
constants no viewrec code reads); GENNewRecordsProcess +0x80..0x84 and +0x8C..0x94.
