# 1080 audio driver (game_libs 0x1C9E4-0x2D374) and sound glue (0x2D374-0x31DF8)

Area C of the readability phase (agent-c runs 444, 446, 450, 455). Uncommitted area doc.

## State for porters (agent-c run 574, final wave)

**Correspondence.** game_libs 0x1C9E4-0x2D374 is OoT's `src/audio/internal/` driver
(synthesis, heap, load, thread, os, playback, effects, seqplayer), in OoT's unit and function
order, with OoT's names (renames.tsv maps every address). It is the older 1998 driver: 8-layer
SequenceChannel (0xE4), no RANDPTR / RUNSEQ opcodes, older NoteAttributes / SynthesisReverb,
and a smaller AudioContext (0x5C30, notes at 0x2CFC). game_libs 0x2D374-0x31DF8 (`snd_*`) is
1080's own glue. It queues OoT-encoded audio-thread commands, and bootup's `snd_*` wrappers are
the API the game calls. The section below ("For port authors") gives the layer split. In short:
replace the driver and libultra, reimplement the glue, keep the bootup API.

**Typed (include/audio.h; every offset is asserted against the matched code).** AudioContext
is typed end to end, from 0 to 0x5C30. That covers the reverbs, the sample-preload stack, the
slow loads, the load tables, the caches, seqPlayers / sequenceLayers / sequenceChannelNone,
the note free lists, the mesg queues and threadCmdBuf. The sub-structs are: AudioTask (OSTask_t);
AudioAllocPool; the cache entries and caches (seq / font / sample caches and the pool splits);
Sample / AdpcmLoop / AdpcmBook / TunedSample; AudioPreloadReq; **AudioSlowLoad** (run 574, 0x64,
OoT layout with a u8 instId); Instrument / Drum / SoundEffect / SoundFont; AudioTable and its
header / entry; SampleBankRelocInfo; SynthesisReverb and its ring items; AudioListItem /
NotePool; SeqScriptState; AdsrEnvelope / AdsrSettings / AdsrState; AudioCmd; SequencePlayer;
SequenceChannel; SequenceLayer; Portamento / VibratoState; Note (synthesis / playback / sample
state) and NoteAttributes; and the glue's SoundObj. Only AudioAsyncLoad is still opaque: its
0x54 stride is verified, its fields are not.

**What stays raw, and why.** game_libs_post.c has 46 census sites left (run 574). In all of them the
raw spelling is load-bearing or the target is unknown:
- **gAudioCtx is not a linked symbol.** Each function reaches it through its own base-0 extern
  (`gl_<addr>_gAudioCtx`, `gAudioContext_23B98`, ...) or `&D_00000000`. Those per-function
  symbols carry the matched relocations and the lui / addiu CSE shapes, so a port collapses
  them into one real `AudioContext gAudioCtx`.
- **Container width steers the loads.** Some byte read-modify-writes on a u32 bitfield word
  stay bytes (SequenceChannelEnable enabled / finished, Sample.medium through the u8 view),
  because the u32 member would compile to a word RMW. Audio_NoteDisable converted cleanly in
  run 574. The bitfield member and a `volatile NoteSampleState` view give the same bytes.
- **Coloring levers.** These are recorded in each function's comment: the `s32 dflt` in
  SequencePlayerDisableChannels, the u32 table bases in snd_SoundObjUpdateChannel,
  AudioLoad_RelocateFont's u32 copy, and the `gl_2495C_Rec` / `gl_2495C_GS` view in
  SlowLoadSample / ProcessSlowLoads. That view is AudioSlowLoad's layout, but its struct-member
  `addu` order is what matched, so it was left as it is.
- **AudioSynth_* command builders.** They write Acmd words as raw u32 pairs, the same words a
  port's ABI interpreter reads.

**Where to start replacing the RSP audio microcode on PC.** The seam is one function.
`AudioThread_UpdateImpl` (game_libs 0x26214, src/game_libs/game_libs_o2_26214.c) calls
`AudioSynth_Update(curAbiCmdBuf, &abiCmdCnt, curAiBuffer, aiBufLengths[i])`. That call builds
the frame's ABI command list. UpdateImpl then fills an AudioTask (OSTask_t, ucode = aspMain:
the image at game_libs 0x31DF8, 0xF7C bytes of data) and returns it. `snd_AudioUpdate_31DA4`
-> `AudioThread_Update` is called from `RcpMgr_service`, which runs that task on the RSP.

On PC:
1. Keep `AudioSynth_*`, or the OoT PC port's synthesis.
2. Do not hand the task to the scheduler. Run the command list through a CPU ABI implementation
   instead (the OoT / MM PC ports' mixer).
3. Send the AI buffer to the host audio stream. This replaces `osAiSetNextBuffer` (os.c,
   0x27704-0x27804).
4. Check each Acmd opcode that `AudioSynth_*` emits against the mixer before you trust it. This
   is the 1998 aspMain, not OoT's.

The rest of the driver (heap / load / seq player) is plain C on AudioContext and ports as-is.
The ROM archives are OoT's format (see "Cartridge data formats").

## Overview

game_libs 0x1C9E4-0x2D374 is the 1998 EAD audio driver that OoT's
`src/audio/internal/` descends from (references/oot). It is C, IDO 7.1 -O2, and
its units appear in the same order as OoT's, with OoT's function order inside
each unit:

| range | OoT unit | prefix |
|---|---|---|
| 0x1C9E4-0x1F6B4 | synthesis.c | AudioSynth_ |
| 0x1F6B4-0x22674 | heap.c | AudioHeap_ |
| 0x22674-0x261F4 | load.c | AudioLoad_ |
| 0x261F4-0x27704 | thread.c | AudioThread_ |
| 0x27704-0x27804 | os.c | Audio_InvalDCache / Audio_WritebackDCache / osAiSetNextBuffer |
| 0x27804-0x295C4 | playback.c | Audio_ |
| 0x295C4-0x2A014 | effects.c | Audio_ |
| 0x2A014-0x2D374 | seqplayer.c | AudioSeq_ |

Differences from OoT seen so far (it is the older driver): SequenceChannel has
EIGHT layers (SM64 LAYERS_MAX), so everything after `layers` is +0x10 vs OoT
and the channel is 0xE4; no Audio_SetFontInstrument, no
AudioSeq_SequencePlayerDisableAsFinished, no 0xBD RANDPTR / 0xC4 RUNSEQ; the
AudioContext is smaller (notes at 0x2CFC, OoT 0x3530). OoT's
func_800E82C0 (original name __Nas_InterTrack) is named Audio_NoteInterTrack.

gAudioCtx is not a linked global: it is bootup.uso's audio data block (section
base, D_00000000 + 0). Matched functions reach it through per-function base-0
externs (gl_<addr>_gAudioCtx etc.) or `*(T *)&D_00000000`; keep those symbols
when retyping (they carry the matched relocations), retype the extern.

## For port authors: what to replace, what to keep (agent-c run 503)

Audio splits into four layers. Replace layers 1 and 2. Reimplement layer 3 against
your driver's command queue. Keep layer 4 (the game API) as the interface.

**1. The OoT-derived driver: replaceable.** game_libs 0x1C9E4-0x2D374 (the table above)
is the EAD driver that OoT's `src/audio/internal/` descends from. A PC port can use an
existing OoT audio implementation for the sequence player, note / ADSR / vibrato code,
the heap / load cache and the audio thread command queue. The CPU-side ABI synthesis
of the OoT and MM PC ports also stands in for the RSP. Port these differences:
- `SequenceChannel` has 8 layers (SM64-style), not 4. Everything after `layers` is
  +0x10; the channel is 0xE4.
- There are no 0xBD RANDPTR / 0xC4 RUNSEQ sequence opcodes, and no
  `AudioSeq_SequencePlayerDisableAsFinished` / `Audio_SetFontInstrument`. A sequence
  that hits an opcode the port does not know is a port bug: check `AudioSeq_*` here.
- `NoteAttributes` is older (u8 combFilterGain + u16 combFilterSize, no filterBuf).
  `SynthesisReverb` drops OoT's unk_14..unk_1B. The AudioContext is smaller.
  include/audio.h asserts every offset.
- `AudioLoad_Init` takes no heap parameters. It clears `gAudioHeap` for
  `gAudioHeapInitSizes.heapSize`. That size block is bootup.uso Data +0x1CDD0:
  {0x14000030, heapSize 0x34000, initPoolSize 0x8B00, permanentPoolSize 0x67A0}.
  It sets refresh 50 / 60 Hz from osTvType, and it allocates three 0xB00-byte AI
  buffers (aiBufLengths 0xA0).
- The RSP microcode image is at game_libs 0x31DF8-0x32D74 (0xF7C bytes, data, not
  functions; N64_FORENSICS `#game-libs-rsp-ucode-31df8-reclass`). The synthesis task
  that `AudioSynth_*` builds runs on it. On PC: CPU ABI emulation, AI buffer -> host
  stream.

**2. libultra pieces: replace.** os.c (0x27704-0x27804: Audio_InvalDCache /
WritebackDCache / osAiSetNextBuffer) and the statically linked `gl_os*` copies.

**3. 1080 glue: reimplement.** game_libs 0x2D374-0x31DF8, the `snd_*` names (85
functions, see below). It is game logic, not driver code: it computes values and
queues OoT-encoded audio-thread commands (`op << 24 | player << 16 | channel << 8 |
arg` through AudioThread_QueueCmd*). Port it as C against the replacement driver's
command queue. The opcode table is in the next section. The command words are the
whole contract, so a port only has to keep their meaning. The parts:
- seq players: 0 = effects / rider (SoundObjs drive channels 3 / 7, 8, 10), 1 = music
  (snd_PlayPlayer1Seq*, snd_ScheduleSeq + snd_UpdateTimers), 2 = cue scripts (the
  cue queues), 3 = stick-driven freq scale and seq 15;
- per-object sound state `SoundObj` (0x64, include/audio.h). The bootup
  `snd_updatePlayer` updates it every frame from the rider (speed, angle,
  contactSurface, reverbOn);
- the channel-8 ambient fade / cue state and the three cue queues (`SndCueQueues`,
  bootup Bss 0x338);
- volume levels / mute / output mode wrappers (0x2D618-0x2DF64).

**4. Game API (bootup.uso): keep as the port's interface.** Game code calls only these
(they wrap the layer-3 functions; mode USOs import them, e.g. genproc's `gen_imp_snd_*`):

| bootup | what |
|---|---|
| 0x1C8 snd_setLevelRampTarget, 0x21C / 0x25C snd_setPlayer1 / 2VolumeLevel, 0x2BC snd_unmuteAll | volume / mute |
| 0x2DC snd_postEvent, 0x2FC snd_sendEvent | UI / game sound events (select screens, menus) |
| 0x31C snd_updateChannel10Emitter | positional emitter (distance, pan) |
| 0x360 / 0x38C snd_add / removeSoundHeap | external sample pool (AudioThread_InitExternalPool / ResetExternalPool) |
| 0x3B8 snd_setPlayer1Channel15IO, 0x3D8 snd_setPlayer3FreqScaleFromStick | music IO, stick pitch |
| 0x610 snd_updatePlayer | per-frame rider sound |
| 0x85C..0xA9C SndHandle_* (start, stop, triggerEvent0-3, setScaleIdx15 / 31, disable, setFlag1A, setContactSurface, contactEventType), 0xB14 snd_soundObjSetReverb, 0xB2C snd_soundObjSetPan_00000B2C | SoundObj handle {obj, unk04, eventArg} |
| 0x120A8 snd_playSeq_000120A8 | start a sequence |

**Boot.** `SnowBoard_ctor` (bootup 0xE800) looks up three ROM files with
`fs_gdlFileInfo`: "rom/audio_seq.uso", "rom/audio_wave.uso" and "rom/audio_bank.uso"
(bootup Data 0x8D34 / 0x8D48 / 0x8D5C). It calls `snd_Init(seq, bank, wave)`, which
stores them to bootup Bss 0x498 / 0x49C / 0x4A0. `AudioLoad_Init` reads those as
seqRom / fontRom / sampleRom. `AudioLoad_InitTable` (0x22F60) adds the base to each
table entry's offset, as in OoT.

### Cartridge data formats

The three audio USOs are data-only modules. Each is one Data section (USO section
type 6, not Yay0-compressed) holding OoT's three archives. The four tables that index
them live in bootup.uso Data. They use OoT's `AudioTable` layout: a 0x10 header {s16
numEntries, s16 unkMediumParam, u32 romAddr, pad 8}, then 0x10-byte entries {u32
romAddr (offset in the file), u32 size, s8 medium, s8 cachePolicy, s16 shortData1..3}.
medium is 2 (cart) everywhere.

| archive (OoT name) | file (USO info ROM) | size | table (bootup Data) | entries |
|---|---|---|---|---|
| sequences (Audioseq) | audio_seq.uso (0x1E940) | 0x208B0 | gSequenceTable +0x1DA40 | 90. 0-23 are real (cachePolicy 0 for 0-1, 3 for 15, else 2). 24 / 25 have size 0, so they alias seq 0x15 / 0x16 (OoT: a size-0 entry's romAddr is the real id). 26-89 alias seq 1 |
| soundfonts (Audiobank) | audio_bank.uso (0xB810) | 0x130B0 | gSoundFontTable +0x1D620 | 30. shortData1 = sampleBankId1 << 8 \| sampleBankId2 (0xFF = none), shortData2 = numInstruments << 8 \| numDrums, shortData3 = numSfx. cachePolicy 0 (fonts 0-3, 12-13), 1 (4-11), 4 (14-29); fonts 9 / 10 are size-0 aliases of font 8 |
| sample banks (Audiotable) | audio_wave.uso (0x3F270) | 0x4FEE30 | gSampleBankTable +0x1DFF0 | 13. cachePolicy 4. Samples are VADPCM, with codebooks and loops in the soundfont (Sample / AdpcmBook / AdpcmLoop, include/audio.h) |
| seq -> fonts | (in bootup) | | gSequenceFontTable +0x1D810 | OoT layout: u16 offset per sequence (90), then {u8 count, u8 fontId...}. seq 0 (sound effects) = fonts 13 12 3 2 1 0; seq 1 = 12 x4; music seqs 2-25 use one font each (14-29); 26-29 = 12 13 4..7 4 |

These are OoT's on-cart formats, so OoT tools (seq / font / sample extractors, e.g. the
OoT decomp's audio extraction or Seq64) read the archives once the table offsets above
are applied. The sequence bytecode is the 1998 opcode set (see the differences above).
Data +0x1CDD0 (gAudioHeapInitSizes, above) is the fifth AudioLoad_Init data reference.

## Game-side sound glue (0x2D374-0x31DF8, 85 functions)

1080's own code between the game and the driver. It mostly builds audio-thread
command words and hands them to the blank (USO-relocated) AudioThread_QueueCmd*
entry. The words use OoT's encoding `op << 24 | player << 16 | channel << 8 |
arg` (verified: 0x2DE9C / 0x2DF30 test seqPlayers[1] / [0].enabled at
gAudioCtx+0x2E60 / +0x2D00 before issuing 0x83 for player 1 / 0; 0x2DC74's
R_MIPS_26 is AudioThread_QueueCmdF32). Opcodes from OoT include/audiothread_cmd.h:
0x01 CHANNEL_SET_VOL_SCALE, 0x04 CHANNEL_SET_FREQ_SCALE, 0x06 CHANNEL_SET_IO,
0x41 SEQPLAYER_FADE_VOLUME_SCALE, 0x46 SEQPLAYER_SET_IO, 0x4D SET_BEND,
0x4E CHANGE_TEMPO_SEQTICKS, 0x81 SYNC_LOAD_SEQ_PARTS, 0x82 INIT_SEQPLAYER,
0x83 DISABLE_SEQPLAYER, 0x90 SET_CHANNEL_MASK, 0xF0 SET_SOUND_OUTPUT_MODE,
0xF1 MUTE, 0xF2 UNMUTE, 0xF8 STOP_AUDIOCMDS.

Named (run 446): the 22 wrappers 0x2D618-0x2DF64 (`snd_*_<addr>`, address
suffix kept: behaviour inferred, no OoT source). Still unnamed, with what is
known:
- Named in run 450 (14): snd_UpdateTimers_2D374, snd_SetPlayer1Channel15IO_2D910,
  snd_SetPlayer0ChannelPanIO_2F638, snd_Player0ChannelIOPreset_2F8A0 / _2F934,
  snd_SetPlayer0ChannelParams_2F9D4, snd_SetPlayer0ChannelIO12_2FA90,
  snd_ResetPlayer0ChannelIO1_2FB10, snd_HandleEvent_2FB74,
  snd_SetPlayer0Channel0IO_30504, snd_SetPlayer0Channel8IO1_30564,
  snd_SetPlayer0Channel8Pan_305CC, snd_HandleSeqEvent_30AF4,
  snd_SetPlayer2ChannelIO_3190C (0x03 = CHANNEL_SET_PAN).
- Named in run 455 (49): the rest of the glue; every function in
  0x2D374-0x31DF8 now has a name. Groups (evidence per name in the run-455
  commit message and the mapping table below):
  - sound objects (0x64 bytes, allocated by bootup 0x57C = mem_new(0x64) +
    snd_SoundObjInit_2DF98; kind byte 0x21 picks player-0 channel 3 (kind 0)
    or 7; driven per frame by bootup snd_updatePlayer -> snd_SoundObjSetAngle_2F720
    + snd_SoundObjUpdate_2E354): Init / Reset / SetScaleIdx15 / 31 / SetFlag1A /
    TriggerEvent / Disable / Start / Stop / EventIndex / Update /
    UpdateChannel (2F288) / Play (2F578) / RequestCue (31608); bootup
    0x85C..0xA68 are one-call wrappers over them.
  - delayed seq start: snd_ScheduleSeq_2DDBC (seq, delay, arg, vol) sets
    D_1C0BC / timer0 D_1C084 / import 0x202C0 / 0x202C4; snd_UpdateTimers_2D374
    starts it at expiry (seq 15 -> player 3, else player 1).
  - channel 8 of player 0 (ambient layer): snd_SetChannel8Mode_308AC,
    snd_TickChannel8Fade_307A8 (0x01000800 volume), snd_TriggerChannel8Cue_30610
    (+ IfIdle_3058C); state block = the 308AC/307A8 donors' file static
    (import 0x202D8 in the reloc table).
  - channel 0xA emitter: snd_UpdateChannel10Emitter_31A74 (mode, distance,
    pan) from bootup 0x31C (func_3F8 = position -> distance / projection).
  - cue queues (0x64 records at D+0x368 / 0x3CC / 0x430, 16-entry ring of
    cue-script pointers, halfword (cmd, wait) scripts): snd_CueQueueSet /
    Push / Step / Pop / Update_31754..31898; player-2 IO from them in
    snd_SetPlayer2ChannelIO_3190C.
  - bootup debug strings: 0x148 "Poop start" -> snd_HandleSeqEvent_30AF4,
    0x188 "Poop end" -> snd_HandleSeqEnd_31334, 0x360 / 0x38C "Poop: Added /
    Removed sound heap" -> snd_AddSoundHeap_31520 / snd_RemoveSoundHeap_31540
    (AudioThread_InitExternalPool / ResetExternalPool); "NA_UpdPl" in
    snd_updatePlayer.
- Caller finding: /tmp/claude-1000/c455/callers.py and calls.py (bootup.uso
  TextReloc + bootup_uso.symnames.json). Baked intra-module jals show as
  `bu:func_00000008`; resolve them from the jal word (target - 0x1466C =
  game_libs offset), e.g. gl_func_00043BE4 = snd_SoundObjPlay_2F578 (its old
  comment "no-op epilogue stub" is wrong), gl_ref_00043824 = 2F1B8,
  gl_func_000438F4 = 2F288, gl_func_000428FC = 2E290, 0x45DC0..0x45F04 =
  the cue-queue functions, 0x46314 / 0x46324 = snd_RampInit / RampTick.
OoT's game-side files (src/audio/game/general.c, sfx.c, sequence.c) are a
different, later design; use them only for opcode semantics, not names.

## Struct layouts (include/audio.h)

All offsets are compile-time asserted (negative-array typedefs).

- AudioContext: see the header; 0x2D00 seqPlayers[4] (0x160), 0x3280
  sequenceLayers[64] (0x80), 0x5280 sequenceChannelNone (0xE4), 0x5364
  noteSubEuOffset, 0x5368 layerFreeList, 0x5378 noteFreeLists (NotePool),
  0x53B8 thread-cmd ring bytes.
- SequencePlayer 0x160: OoT layout unchanged (tempo 0x8, seqData 0x18, bend
  0x34, channels 0x38, scriptState 0x78, note tables 0x94/0x98, notePool 0x9C,
  skipTicks 0xDC, scriptCounter 0xE0, seqScriptIO 0x158).
- SequenceChannel 0xE4: OoT to 0x4C, layers[8] 0x50, scriptState 0x70, adsr
  0x8C, notePool 0x94, seqScriptIO 0xD4, filter 0xDC, stereo 0xE0.
- SequenceLayer 0x80: flags 0x0, adsr 0x18, channel 0x50, scriptState 0x54,
  listItem 0x70; rest padding (pre-OoT layout, unverified).
- AudioListItem 0x10, NotePool 0x40, SeqScriptState 0x1C, AdsrSettings 0x8,
  Stereo 0x1, AudioAllocPool 0x10.
- Opaque (stride only): AudioAsyncLoad 0x54.
- Note 0xD0 (run 450): listItem 0x0, NoteSynthesisState 0x10 (0x20),
  NotePlaybackState 0x30 (0x80: priority 0x0, unk_04 0x4, stereoHeadsetEffects
  0x5, adsrVolScaleUnused 0x6, portamento/vibratoFreqScale 0x8/0xC, prev /
  parent / wantedParentLayer 0x10/0x14/0x18, NoteAttributes 0x1C (0x14, older:
  u8 combFilterGain + u16 combFilterSize, no filterBuf), AdsrState 0x30 (OoT
  0x20), Portamento 0x50 (0xC: u8 mode, u16 cur, u16 speed, f32 extent),
  VibratoState 0x5C (OoT 0x1C)), NoteSampleState 0xB0 (0x18 named + 8 pad; the
  flag bits are a u32 bitfield run; Audio_InitSampleState's donor uses u8
  containers, keep each donor's own container when converting).
- SynthesisReverb 0x158 (run 450): OoT's fields to 0x13, then OoT - 8 (no
  unk_14..unk_1B): nextRingBufPos 0x14, unk_18 (OoT unk_20), bufSizePerChan
  0x1C, ring buffers 0x20/0x24, resample states 0x28..0x34, 0x14-byte
  ReverbRingBufferItem items[2][5] at 0x38 (no items2), filters 0x100..0x10C,
  tunedSample 0x110, sample 0x118, loop 0x128. Sample / TunedSample /
  AdpcmLoop (flat, 0x30) / AdpcmBook added. gAudioCtx.notes is Note *.
- Bitfield flag words use the u32 container the matched donors used (IDO's
  bitfield loads follow the declared container); keep it when converting.

Users: game_libs_o2_240A0.c, _2B5F4.c, _27804.c (AudioContext alias),
_2C7A4.c and _2BB7C.c (AudioContext + SequencePlayer / SequenceChannel /
SequenceLayer / SeqScriptState / AdsrSettings / Stereo aliases).
game_libs_post.c includes audio.h since run 450. After the last per-function
gAudioCtx alias block (#undef after AudioLoad_*), post.c defines
`#define gAudioCtx (*(AudioContext *)&D_00000000)` (same symbol and offsets,
relocations unchanged). Converted so far: AudioThread_SetFadeOutTimer /
SetFadeInTimer / GetSeqPlayerIO, AudioSeq_InitSequenceChannel /
SequencePlayerDisableChannels (&sequenceChannelNone), SeqChannelSetLayer /
SeqLayerFree (&layerFreeList), snd_StopPlayer0/1Seq (seqPlayers[n].enabled).
Run 455: the D_00000000_345c0-alias functions use a scoped
`#define gAudioCtx_<addr> (*(AudioContext *)&D_00000000_345c0)`:
AudioSeq_InitLayerFreelist, AudioSeq_ProcessSequences,
AudioLoad_DecreaseSampleDmaTtls, AudioThread_ScheduleProcessCmds (all
byte-identical first try). Per-function views moved onto audio.h types:
ProcessNote (sample types, NoteSampleState, Note, AudioContext extern),
LeakReverb / SaveReverbSamples (ctx->synthesisReverbs), DoOneAudioUpdate
(SynthesisReverb), ProcessNotes / SeqLayerDecayRelease (Stereo,
NoteAttributes), AllocNote (AudioListItem / NotePool), 2ABC0 (TunedSample);
donors 2119C (Note) and 2B09C (TunedSample / Portamento / AdsrSettings).
Byte-sensitive, left raw: AudioThread_GetChannelIO (tried: bytes change),
AudioSynth_FilterReverb as `&ctx->synthesisReverbs[a2]` (tried: the +0x18
fold changes bytes; keep `base + a2 * 0x158` + 0x118..), pointer walks
(AudioHeap_DiscardSequence, AudioSeq_InitSequencePlayers,
InitSequencePlayerChannels), the dcb4 volatile-enabled sample-state view
(lever), the 2119C volatile resetStatus context view. NOTE: in the glue range most `&D_00000000 + K` reads are NOT
gAudioCtx (D+0x16E0 / 0x1724 / 0x1C1D8 are game_libs data: the USO reloc
targets another section); only convert offsets whose target is proven.

Run 478 (agent-c, commit aff387302, **pure rename**): 45 names lost their address suffix. In game_libs:
the AudioThread-op wrappers (MuteAll 0xF1, Unmute / UnmuteAll 0xF2, SetSoundOutputMode 0xF0,
StopAudioCmds 0xF8, StopPlayer0Seq / StopPlayer1Seq 0x83), the string-backed ones (AddSoundHeap /
RemoveSoundHeap / HandleSeqEnd), the loop entries (Init, AudioUpdate, FrameUpdate, UpdateTimers, PreNMI,
ScheduleSeq, PostEvent) and the SoundObj methods (Init, Reset, SetScaleIdx15 / 31, SetFlag1A, Disable,
Start, Stop, Update, Play). In bootup: the 18 one-call wrappers (`snd_postEvent`, `snd_addSoundHeap`, ...,
`SndHandle_start` / `stop` / `disable` / `setScaleIdx15` / `31` / `setFlag1A` / `setEventArg`), whose
callees were checked against bootup TextReloc jals (/tmp/claude-1000/c478/buxref.py). Bootup keeps
lowerCamel (`snd_addSoundHeap` wraps game_libs `snd_AddSoundHeap`). These kept their suffix:
TriggerEvent / EventIndex / SetAngle / UpdateChannel, the channel-8 / cue-queue / player-N IO helpers,
`SndHandle_triggerEvent0-3` / `setUnk1F`, and `snd_soundObjSetByte1D` / `SetScaled`. The mapping table
below uses the old names; renames.tsv has the chains.

Run 490 (agent-c, commit 391b5617c, **pure rename**): 41 more glue names lost their suffix
(volume levels, PlayPlayerN / Schedule seq helpers, the cue queues + RequestCue*, Ramp*,
SoundObj TriggerEvent / EventIndex / SetAngle / UpdateChannel, the channel-8 / 10 helpers,
FreqScale). Still suffixed (kind only): snd_Stub_2DD30 / 2F630 / 309A4, FindNearestF32_2F1B8,
Player0ChannelIOPreset_2F8A0 / 2F934, SetPlayer0ChannelPanIO_2F638 / Params_2F9D4 / IO12_2FA90,
ResetPlayer0ChannelIO1_2FB10, SetPlayer0Channel0IO_30504 / Channel8IO1_30564 / Channel8Pan_305CC,
SetPlayer1Channel15IO_2D910, SetPlayer2ChannelIO_3190C, HandleEvent_2FB74, HandleSeqEvent_30AF4,
AudioThread_Set / ClearExtWord, bootup snd_soundObjSetScaled_00000B2C / SetByte1D_00000B14 (callers
bootup 0xBD04 / 0xC790 / 0xC7A8), snd_playSeq_000120A8.

**Run 495.** `SndHandle_contactEventType` (was snd_soundObjEventIndex_00000A9C): the four
SndHandle_triggerEvent* call it as f(h, h->contactSurface). SndHandle +0x8 `contactSurface` is set each
frame by SnowBoarder_update through `SndHandle_setContactSurface` (0xA94) from SnowBoarder.contactSurface
(0x9A4, the surface code of the last obstacle hit). It maps 0 -> 1, 'e' 4, 'd' 0x10, 'm' 0x40, 't' 0x20,
'n' / 's' 8, other 2: the SoundObj eventType of the hit sound. game.uso calls the triggers.
**Cue queues: include/audio.h `SndCueQueues`** (bootup Bss 0x338, Sym 1448, 0x160 bytes). +0x0..0x1C is
the channel-8 cue / fade state: mode, cue (cmd 0x06000800), fadeInFrames, holdFrames, level (cmd 0x01000800),
floor, upStep, downStep. +0x20 timer[3] (snd_UpdateTimers). +0x30 `SndCueQueue queue[3]` (0x64 each: ring[16],
wr, rd, timer, script, mode, limit, pending, cmd, cue). Spell the Sym-1448 sites `SND_CUEQ(gSndCueQueues)`
(converted: TriggerChannel8CueIfIdle, the TriggerChannel8Cue NM body). Spell the Bss-base sites
`SND_CUEQ_AT_BASE(D_00000000)` (converted: RequestCue2 / Cue2Prio / SetPlayer2ChannelIO queue[2]).
Not converted: the two NCC donors (TickChannel8Fade, SetChannel8Mode; module-local static).
**Run 499 (agent-c, f7dd3f3b2):** +0x20..0x28 are not timers but snd_UpdateTimers' ramp floats
(rampBase / rampValue / rampStep, its D_2D37C_f358s.. aliases now spell `SND_CUEQ_AT_BASE(alias).rampX`);
InitCueQueues and RequestCue converted (`(SndCueQueue *)&gl_ref_00000368 + a0` keeps the strength-reduced
stride). SoundObjRequestCue stays: its NM body grows 3 words typed, the match_imports port has its own
context types. Renamed (d7872181c): snd_soundObjSetPan_00000B2C (SoundObj +0x10, sent as (x + 1) * 63.5
for kind 0). Not renamed: snd_soundObjSetByte1D_00000B14 (+0x1D: Update sends 0x40 when 1, else 8, on
change, as channel IO 0x0500FF00 / 0x0502xx00; meaning unknown) and the 0x2Dxxx..0x31xxx suffixed
snd_* names (not reached).

**Run 503 (agent-c).** fa70d1b0a (**pure rename**) snd_soundObjSetByte1D_00000B14 ->
`snd_soundObjSetReverb`; hand edit: SoundObj +0x1D `reverbOn`, +0x34 `reverbOnSent`. On a change,
snd_SoundObjUpdate queues 0x05 (CHANNEL_SET_REVERB_VOLUME): 0x40 when on, else 8. It goes to player 0
on all channels (0xFF) and to player 2 channel 0 (kind 0) / 1 (kind 1-2), after a 0x90
SET_CHANNEL_MASK (6 / 0x60). Port-author section added above (layers, game API, boot, cart formats).
The 0x2Dxxx..0x31xxx snd_* names keep their suffixes: only the command words are known, not
their game meaning.

**Run 579 (agent-c), raw-offset close-out.** Owner c went from 108 raw struct-offset sites to 55,
all 55 justified (`/* RAW: <keyword>: ... */`). Converted 53 (all byte-identical in both builds):
the AudioContext load-status arrays, numSequences (`*(unsigned short *)&ctx->numSequences`),
seqPlayers[i].skipTicks, specId, resetTimer / resetStatus, externalPool; SynthesisReverb
left/rightRingBuf through REVERB_AT in Load/SaveRingBufferPart, and LoadAuxBufferC's 0x05 packet
through the `*(T *)&REVERB_AT(rec)->field` lever (the plain member read re-ranks; this does not);
InitSequencePlayers' cursor as `((AudioContext *)p)->sequenceLayers[-1]` (p runs one layer
ahead); new `AudioHeapInitSizes` (audio.h); Instrument / Drum / AudioSlowLoad / Portamento /
VibratoState / AudioListItem / SequenceChannel / SequenceLayer fields; GfxLib.frameTime, DmaSlot.busy,
Node.parent; genproc SelVEntry slots, SelItemInfo.pos, SelectWin curItem / fade,
SelItemsMgr.lists. Left (justified): 38 data-table (RoData constants, section-relative words /
tables in the match_imports and the edg donors), 10 unknown-object (D_2DE24_b +0xC, the cue-queue
record, gen_createScene's three game_libs imports, the import_000A5D38 display object, ...),
6 donor-mirror (SelectWin_update's placeholder body), 1 byte-lock (InitSequenceChannel's
`changes` byte: the bitfield-store form emits an lbu RMW).

### Run 585 additions (agent-c)

- `SndTimers` (Data 0x1C080, Sym 1425, 0x1C): snd_UpdateTimers' per-frame countdowns; +0xC is the
  256-frame ramp (snd_HandleSeqEnd(6) sets 256, snd_PlayPlayer1Seq clears it). `SND_TIMERS(tok)`.
- `AudioHeapInitSizes` +0x2 = `tatumsPerBeat` (s16 48, OoT gTatumsPerBeat), AudioHeap_Init's divisor.
- snd_CueQueueStep's argument is a `SndCueQueue`.
- Named section offsets for per-site token reads (audio.h): `kRoF_tempoScale_E90` (2880000),
  `kRoF_maxTempoPal_EC8` / `Mpal_ECC` / `Ntsc_ED0`, and the Data tables inside Sym 1450's span:
  `kD_sndLevelWobble_1C330`, `kD_sndScaleWobble_1C3B0`, `kD_sndGainWobble_1C430` (f32[32] each) and
  `kD_sndWobbleCount_1C740`. Owner c's raw sites: 1 left (AudioSeq_InitSequenceChannel byte-lock).

## Next

1. Model more of SequenceLayer / SequenceChannel (the 27E24 / 28604 / 291C0
   / 26790 Note views carry their own layer / channel views; once the
   fields exist in audio.h those Note views can go too). The 27E24 sample
   state is a union of two bitfield views (bitField0 / bitField1 names);
   converting it means renaming its accesses to audio.h bit names.
2. Remaining D_00000000_345c0 users: the D_345c0_1CC98 / _27E24 / _21498 /
   _201B8 typed aliases (SyncSampleStates, ProcessNotes, AudioHeap_Init,
   AllocCached) and GS_24E28 (2495C/24E28 slow loads) -> AudioContext where
   the view's fields agree.
3. SoundObj is in include/audio.h since run 464 (SoundObj 0x64 + bootup SndHandle {obj, unk04,
   eventArg}). Converted so far: snd_SoundObjInit / Reset / SetScaleIdx15 / 31 / SetFlag1A / Disable /
   Start / Stop and the 12 bootup wrappers (now `SndHandle_*_<addr>`). Run 484 (commit d8d943852):
   snd_SoundObjPlay (exact body, identical bytes) and the NON_MATCHING bodies of TriggerEvent_2E0C4,
   UpdateChannel_2F288, snd_SoundObjUpdate (131 accesses) and bootup snd_updatePlayer (SndHandle *)
   are typed; SoundObj 0x22 = `surface` (cue key with kind), 0x2A / 0x2B split out. Left: the
   s16-as-u16 0x1A and s8-as-u8 0x63 reads in Update; EventIndex and SetAngle are splice placeholders
   (their real bodies are the donors game_libs_o2_2E290.c / game_libs_ncc_2F720.cpp, which do not
   include audio.h); the match_imports donors keep their GlState2E0C4 / `char *` views.
4. Rename-tool note: a function whose REPLACE_FUNC_BODY donor lives in
   src/match_imports/<NAME>.c is "defined in several segments"; run 446's
   wrapper (/tmp/claude-1000/c446/rn.py) tolerates exactly that case when the
   Makefile has `REPLACE_FUNC_BODY += OLD=build/src/match_imports/OLD.c.o`; the
   tool then renames the donor file, bindings, origins .ld and Makefile rules
   together (AudioSeq_SeqChannelSetLayer, AudioSeq_InitSequencePlayer).
   rename-symbol.py's check() now takes a 6th argument; run 455's copy
   (/tmp/claude-1000/c455/rn.py) passes it through.

## Mapping (renames.tsv is authoritative)

| addr | old name | name | evidence |
|---|---|---|---|
| 1C9E4 | game_libs_func_0001C9E4 | AudioSynth_InitNextRingBuf | OoT synthesis.c order + reverb items/downsample ring copy |
| 1CC98 | game_libs_func_0001CC98 | AudioSynth_SyncSampleStates | OoT func_800DB03C (__Nas_PushDrvReg); called by AudioSynth_Update per tick |
| 1CD64 | gl_func_0001CD64 | AudioSynth_Update | OoT AudioSynth_Update: ticksPerUpdate loop over ProcessSequences + 1CC98 |
| 1CF68 | game_libs_func_0001CF68 | AudioSynth_DisableSampleStates | OoT func_800DB2C0 (__Nas_WaveTerminateProcess) |
| 1CFDC | gl_func_0001CFDC | AudioSynth_LoadRingBuffer1AtTemp | OoT; twin of SaveRingBuffer1AtTemp, called by MaybeMixRingBuffer1 |
| 1D0AC | gl_func_0001D0AC | AudioSynth_SaveRingBuffer1AtTemp | OoT |
| 1D17C | game_libs_func_0001D17C | AudioSynth_LeakReverb | comment + gl_1dcb4 order |
| 1D200 | gl_func_0001D200 | AudioSynth_LoadAuxBufferC | OoT func_800DB4E4 (Nas_LoadAuxBufferC); LoadReverbSamples else-arm (0x3186C) |
| 1D3E0 | game_libs_func_0001D3E0 | AudioSynth_FilterReverb | gl_1dcb4_f3 pin 0x31A4C |
| 1D4B0 | game_libs_func_0001D4B0 | AudioSynth_MaybeMixRingBuffer1 | gl_1dcb4_f5 pin 0x31B1C |
| 1D554 | game_libs_func_0001D554 | AudioSynth_Stub_800DBB94 | OoT stub sequence |
| 1D55C | game_libs_func_0001D55C | AudioSynth_ClearBuffer | gl_e134_ClearBuffer pin 0x31BC8 |
| 1D57C | game_libs_func_0001D57C | AudioSynth_Stub_800DBBBC | OoT stub sequence |
| 1D584 | game_libs_func_0001D584 | AudioSynth_Stub_800DBBC4 | OoT stub sequence |
| 1D58C | game_libs_func_0001D58C | AudioSynth_Stub_800DBBCC | OoT stub sequence |
| 1D594 | game_libs_func_0001D594 | AudioSynth_Mix | gl_e134_Mix pin 0x31C00 |
| 1D5C8 | game_libs_func_0001D5C8 | AudioSynth_Stub_800DBC08 | OoT stub sequence |
| 1D5D0 | game_libs_func_0001D5D0 | AudioSynth_Stub_800DBC10 | OoT stub sequence |
| 1D5D8 | game_libs_func_0001D5D8 | AudioSynth_Stub_800DBC18 | OoT stub sequence |
| 1D5E0 | game_libs_func_0001D5E0 | AudioSynth_SetBuffer | gl_e134_SetBuffer pin 0x31C4C |
| 1D614 | game_libs_func_0001D614 | AudioSynth_Stub_800DBC54 | OoT stub sequence |
| 1D61C | game_libs_func_0001D61C | AudioSynth_Stub_800DBC5C | OoT stub sequence |
| 1D624 | game_libs_func_0001D624 | AudioSynth_DMemMove | gl_e134_DMemMove pin 0x31C90 |
| 1D650 | game_libs_func_0001D650 | AudioSynth_Stub_800DBC90 | OoT stub sequence |
| 1D658 | game_libs_func_0001D658 | AudioSynth_Stub_800DBC98 | OoT stub sequence |
| 1D660 | game_libs_func_0001D660 | AudioSynth_Stub_800DBCA0 | OoT stub sequence |
| 1D668 | game_libs_func_0001D668 | AudioSynth_Stub_800DBCA8 | OoT stub sequence |
| 1D670 | game_libs_func_0001D670 | AudioSynth_InterL | gl_e134_InterL pin 0x31CDC |
| 1D694 | game_libs_func_0001D694 | AudioSynth_EnvSetup1 | gl_ref_00031D00 macro |
| 1D6C8 | game_libs_func_0001D6C8 | AudioSynth_Stub_800DBD08 | OoT stub sequence |
| 1D6D0 | game_libs_func_0001D6D0 | AudioSynth_LoadBuffer | gl_e134_LoadBuffer pin 0x31D3C |
| 1D6F8 | game_libs_func_0001D6F8 | AudioSynth_SaveBuffer | gl_e134_SaveBuffer pin 0x31D64 |
| 1D720 | game_libs_func_0001D720 | AudioSynth_EnvSetup2 | gl_ref_00031D8C macro |
| 1D73C | game_libs_func_0001D73C | AudioSynth_Stub_800DBD7C | OoT stub sequence |
| 1D744 | game_libs_func_0001D744 | AudioSynth_Stub_800DBD84 | OoT stub sequence |
| 1D74C | game_libs_func_0001D74C | AudioSynth_Stub_800DBD8C | OoT stub sequence |
| 1D754 | game_libs_func_0001D754 | AudioSynth_S8Dec | gl_e134_S8Dec pin 0x31DC0 |
| 1D770 | game_libs_func_0001D770 | AudioSynth_HiLoGain | gl_e134_HiLoGain pin 0x31DDC |
| 1D7A4 | game_libs_func_0001D7A4 | AudioSynth_UnkCmd19 | gl_e134_UnkCmd19 pin 0x31E10 |
| 1D7D8 | game_libs_func_0001D7D8 | AudioSynth_Stub_800DBE18 | OoT stub sequence |
| 1D7E0 | game_libs_func_0001D7E0 | AudioSynth_Stub_800DBE20 | OoT stub sequence |
| 1D7E8 | game_libs_func_0001D7E8 | AudioSynth_Stub_800DBE28 | OoT stub sequence |
| 1D7F0 | game_libs_func_0001D7F0 | AudioSynth_Stub_800DBE30 | OoT stub sequence |
| 1D7F8 | game_libs_func_0001D7F8 | AudioSynth_UnkCmd3 | gl_e134_UnkCmd3 pin 0x31E64 |
| 1D81C | game_libs_func_0001D81C | AudioSynth_Stub_800DBE5C | OoT stub sequence |
| 1D824 | game_libs_func_0001D824 | AudioSynth_Stub_800DBE64 | OoT stub sequence |
| 1D82C | game_libs_func_0001D82C | AudioSynth_Stub_800DBE6C | OoT stub sequence |
| 1D834 | game_libs_func_0001D834 | AudioSynth_LoadFilterBuffer | gl_e134_LoadFilterBuffer pin 0x31EA0 |
| 1D858 | game_libs_func_0001D858 | AudioSynth_LoadFilterSize | gl_e134_LoadFilterSize pin 0x31EC4 |
| 1D870 | gl_func_0001D870 | AudioSynth_LoadRingBuffer1 | 0x31EDC: LoadReverbSamples downsampleRate==1 arm; calls LoadRingBufferPart twice |
| 1D944 | game_libs_func_0001D944 | AudioSynth_LoadRingBufferPart | two A_LOADBUFF(0x14) packets from leftRingBuf/rightRingBuf |
| 1D9E0 | game_libs_func_0001D9E0 | AudioSynth_SaveRingBufferPart | two A_SAVEBUFF(0x15) packets |
| 1DA7C | gl_func_0001DA7C | AudioSynth_LoadReverbSamples | gl_1dcb4_f1 pin 0x320E8 |
| 1DB88 | gl_func_0001DB88 | AudioSynth_SaveReverbSamples | gl_1dcb4_f4 pin 0x321F4 |
| 1DCB4 | gl_func_0001DCB4 | AudioSynth_DoOneAudioUpdate | calls Load/SaveReverbSamples, ProcessNote, FilterReverb, MaybeMix |
| 1E134 | gl_func_0001E134 | AudioSynth_ProcessNote | gl_1dcb4_f2 pin 0x327A0 |
| 1EE78 | gl_func_0001EE78 | AudioSynth_FinalResample | gl_e134_FinalResample pin 0x334E4 |
| 1EF20 | gl_func_0001EF20 | AudioSynth_ProcessEnvelope | gl_e134_ProcessEnvelope pin 0x3358C |
| 1F248 | gl_func_0001F248 | AudioSynth_LoadWaveSamples | gl_e134_LoadWaveSamples pin 0x338B4 |
| 1F3C8 | gl_func_0001F3C8 | AudioSynth_ApplyHaasEffect | gl_e134_ApplyHaasEffect pin 0x33A34 |
| 1F6B4 | game_libs_func_0001F6A8 | AudioHeap_InitAdsrDecayTable | heap.c head; fills 256-entry f32 adsrDecayTable from updatesPerFrameInv (CalculateAdsrDecay inlined) |
| 1FA20 | game_libs_func_0001FA20 | AudioHeap_ResetLoadStatus | three load-status byte arrays, keep LOAD_STATUS_PERMANENT (5) |
| 1FAE8 | gl_func_0001FAE8 | AudioHeap_DiscardFont | notes with fontId==a0: disable layer, NoteDisable, list remove/push |
| 1FBCC | game_libs_func_0001FBCC | AudioHeap_DiscardSequence | seqPlayers (stride 0x160) enabled && seqId==a0 -> SequencePlayerDisable |
| 1FC50 | gl_func_0001FC50 | AudioHeap_WritebackDCache | one-call wrapper at OoT position |
| 1FC70 | gl_func_0001FC78 | AudioHeap_AllocZeroedAttemptExternal | externalPool (0x2178) first, then pool |
| 1FCC8 | gl_func_0001FCD0 | AudioHeap_AllocAttemptExternal | twin of 1FC78 |
| 1FD20 | gl_func_0001FD20 | AudioHeap_AllocDmaMemory | alloc then cache op, OoT position |
| 1FD5C | gl_func_0001FD5C | AudioHeap_AllocDmaMemoryZeroed | twin, OoT position |
| 1FD98 | gl_func_0001FD98 | AudioHeap_AllocZeroed | alloc then zero-fill |
| 1FDF4 | game_libs_func_0001FDF4 | AudioHeap_Alloc | ALIGN16 bump allocator, numEntries++ |
| 1FE4C | game_libs_func_0001FE4C | AudioHeap_InitPool | cur=start=ALIGN16(addr); size-=addr&0xF; numEntries=0 |
| 1FE74 | game_libs_func_0001FE74 | AudioHeap_InitPersistentCache | numEntries, pool.numEntries=0; cur=start |
| 1FE88 | game_libs_func_0001FE88 | AudioHeap_InitTemporaryCache | entries[0/1].ramAddr, ids=-1 |
| 1FEB8 | game_libs_func_0001FEB8 | AudioHeap_ResetPool | numEntries=0; cur=start |
| 1FEC8 | gl_func_0001FEC8 | AudioHeap_InitMainPools | InitPool(initPool 0x2188), InitPool(sessionPool 0x2168), externalPool=0 |
| 1FF28 | game_libs_func_0001FF28 | AudioHeap_InitSessionPools | OoT order |
| 1FFAC | game_libs_func_0001FFAC | AudioHeap_InitCachePools | OoT order |
| 20030 | game_libs_func_00020030 | AudioHeap_InitPersistentPoolsAndCaches | OoT order |
| 200F4 | game_libs_func_000200F4 | AudioHeap_InitTemporaryPoolsAndCaches | OoT order |
| 201B8 | gl_func_000201B8 | AudioHeap_AllocCached | OoT order, size |
| 208BC | gl_func_000208BC | AudioHeap_SearchCaches | SearchPermanentCache; if CACHE_PERMANENT(3) NULL; SearchRegularCaches |
| 20914 | gl_func_00020914 | AudioHeap_SearchRegularCaches | per-tableType cache switch |
| 20A20 | game_libs_func_00020A20 | AudioHeap_CalcFilterCoefs | OoT func_800DF1D8 (filter maths, float consts) |
| 20DF4 | game_libs_func_00020DF4 | AudioHeap_ClearFilter | 8 s16 zero |
| 20E24 | game_libs_func_00020E24 | AudioHeap_LoadLowPassFilter | 8-short record copy |
| 20E78 | game_libs_func_00020E78 | AudioHeap_LoadHighPassFilter | record cutoff-1 copy |
| 20ED0 | gl_func_00020ED0 | AudioHeap_LoadFilter | lowpass/highpass/average dispatch |
| 20FFC | game_libs_func_00020FFC | AudioHeap_UpdateReverbs | gl_func_00035668 alias in the ResetStep donor |
| 21130 | game_libs_func_00021130 | AudioHeap_ClearCurrentAiBuffer | gl_func_0003579C alias |
| 2119C | gl_func_0002119C | AudioHeap_ResetStep | comment: OoT ResetStep verbatim |
| 21498 | gl_func_00021498 | AudioHeap_Init | gl_func_00035B04 alias |
| 21D2C | game_libs_func_00021D2C | AudioHeap_SearchPermanentCache | 12-byte permanentCache entries at 0x2538 |
| 21D84 | gl_func_00021D84 | AudioHeap_AllocPermanent | appends permanent cache entry |
| 21E08 | gl_func_00021E08 | aud_AllocSampleCacheTemporary | OoT AllocSampleCache, CACHE_TEMPORARY half (calls AllocTemporarySampleCacheEntry) |
| 21E58 | gl_func_00021E58 | aud_AllocSampleCachePersistent | OoT AllocSampleCache, persistent half (calls AllocPersistentSampleCacheEntry) |
| 21EA8 | gl_func_00021EA8 | AudioHeap_InitSampleCaches | persistent/temporary sample cache pools |
| 21F40 | gl_func_00021F40 | AudioHeap_AllocTemporarySampleCacheEntry | temporarySampleCache 0x294C |
| 221D8 | gl_func_000221D8 | AudioHeap_DiscardSampleCacheEntry | gl_func_00036844 alias |
| 22398 | game_libs_func_00022398 | AudioHeap_UnapplySampleCache | gl_func_00036A04 alias |
| 223DC | gl_func_000223DC | AudioHeap_AllocPersistentSampleCacheEntry | 0x36A48 callee of the persistent AllocSampleCache half |
| 22464 | gl_func_00022464 | AudioHeap_DiscardSampleCaches | gl_func_00036AD0 alias |
| 22674 | game_libs_func_00022674 | AudioLoad_DecreaseSampleDmaTtls | load.c head; ttl countdown + free-list push |
| 22760 | gl_func_00022760 | AudioLoad_DmaSampleData | gl_e134_DmaSampleData; sample DMA buffers |
| 22A9C | gl_func_00022A9C | AudioLoad_InitSampleDmaBuffers | OoT order, Alloc/AllocAttemptExternal |
| 22D68 | gl_func_00022D68 | AudioLoad_IsFontLoadComplete | OoT order |
| 22DE0 | gl_func_00022DE0 | AudioLoad_IsSeqLoadComplete | OoT order |
| 22E58 | gl_func_00022E58 | AudioLoad_IsSampleLoadComplete | OoT order |
| 22ED0 | game_libs_func_00022ED0 | AudioLoad_SetFontLoadStatus | OoT order |
| 22F00 | game_libs_func_00022F00 | AudioLoad_SetSeqLoadStatus | OoT order |
| 22F30 | game_libs_func_00022F30 | AudioLoad_SetSampleFontLoadStatus | OoT order |
| 22F60 | game_libs_func_00022F60 | AudioLoad_InitTable | numEntries/unkMediumParam/romAddr, cart entries rebased |
| 22FC0 | gl_func_00022FC0 | AudioLoad_SyncLoadSeqFonts | sequenceFontTable run list |
| 23070 | game_libs_func_00023070 | AudioLoad_SyncLoadSeqParts | flags &1 fonts, &2 seq |
| 230D0 | gl_func_000230D0 | AudioLoad_SyncLoadSample | comment |
| 231B4 | gl_func_000231B4 | AudioLoad_SyncLoadInstrument | instId >= 0x7F drum path |
| 23284 | gl_func_00023284 | AudioLoad_AsyncLoadSampleBank | GetRealTableIndex(SAMPLE_TABLE) + AsyncLoadInner, osSendMesg on fail |
| 232E8 | gl_func_000232E8 | AudioLoad_AsyncLoadFont | per seq font: AsyncLoadInner(FONT_TABLE, GetRealTableIndex(...)) |
| 233A0 | game_libs_func_000233A0 | AudioLoad_GetFontsForSequence | sequenceFontTable cursor |
| 233E4 | gl_func_000233E4 | AudioLoad_DiscardSeqFonts | per font: DiscardFont when not loaded elsewhere |
| 23494 | game_libs_func_00023494 | AudioLoad_DiscardFont | fontCache temporary ids -> -1 |
| 2353C | game_libs_func_0002353C | AudioLoad_SyncInitSeqPlayer | seqPlayers stride 0x160, resetTimer gate |
| 2358C | game_libs_func_0002358C | AudioLoad_SyncInitSeqPlayerSkipTicks | twin storing skipTicks |
| 235E4 | gl_func_000235E4 | AudioLoad_SyncInitSeqPlayerInternal | OoT order |
| 2372C | gl_func_0002372C | AudioLoad_SyncLoadSeq | OoT order |
| 23760 | gl_func_00023760 | AudioLoad_GetSampleBank | gl_ref_00037DCC alias (TrySyncLoadSampleBank inlined) |
| 23838 | gl_func_00023838 | AudioLoad_SyncLoadFont | soundFontList sampleBankId1/2 -> GetSampleBank |
| 23914 | gl_func_00023914 | AudioLoad_SyncLoad | 0x37F80 callee of SyncLoadSimple |
| 23B08 | gl_func_00023B08 | AudioLoad_GetRealTableIndex | 0x38174 (tableType, id) callee everywhere |
| 23B44 | gl_func_00023B44 | AudioLoad_SearchCaches | gl_ref_000381B0 alias |
| 23B98 | game_libs_func_00023B98 | AudioLoad_GetLoadTable | gl_ref_00038204 alias |
| 23BDC | gl_func_00023BDC | AudioLoad_RelocateFont | comment + gl_25504_RelocateFont pin |
| 23E60 | gl_func_00023E60 | AudioLoad_SyncDma | comment |
| 23F84 | game_libs_func_00023F84 | AudioLoad_SyncDmaUnkMedium | empty 4-arg stub (OoT empty too) |
| 23F98 | game_libs_func_00023F98 | AudioLoad_Dma | comment + gl_ref_00038604 alias |
| 24070 | game_libs_func_00024070 | AudioLoad_Unused1 | empty, OoT order |
| 24078 | game_libs_func_00024078 | aud_LoadStub_00024078 | extra empty stub, no OoT counterpart |
| 24080 | gl_func_00024080 | AudioLoad_SyncLoadSimple | SyncLoad(tableType, id, &didAllocate) |
| 240A0 | gl_func_000240A0 | AudioLoad_AsyncLoadInner | comment |
| 24330 | gl_func_00024330 | AudioLoad_ProcessLoads | 3-call wrapper (slow/async/preload) |
| 24360 | game_libs_func_00024360 | AudioLoad_SetDmaHandler | setter |
| 2436C | game_libs_func_0002436C | AudioLoad_SetUnusedHandler | setter |
| 24378 | gl_func_00024378 | AudioLoad_Init | comment |
| 24948 | game_libs_func_00024948 | AudioLoad_InitSlowLoads | two slowLoads state bytes |
| 2495C | gl_func_0002495C | AudioLoad_SlowLoadSample | slowLoads (0x157C) |
| 24B28 | gl_func_00024B28 | AudioLoad_GetFontSample | instId < 0x80 instrument else drum |
| 24B8C | game_libs_func_00024B8C | AudioLoad_Unused2 | empty |
| 24B94 | gl_func_00024B94 | AudioLoad_FinishSlowLoad | GetFontSample + copy |
| 24C08 | gl_func_00024C08 | AudioLoad_ProcessSlowLoads | two-slot pump |
| 24D90 | gl_func_00024D90 | AudioLoad_DmaSlowCopy | AudioLoad_Dma(... "SLOWCOPY") |
| 24E14 | game_libs_func_00024E14 | AudioLoad_DmaSlowCopyUnkMedium | empty stub |
| 24E28 | game_libs_func_00024E28 | AudioLoad_SlowLoadSeq | OoT order |
| 24F30 | gl_func_00024F30 | AudioLoad_StartAsyncLoad | gl_25504_StartAsyncLoad pin 0x3959C |
| 25044 | gl_func_00025044 | AudioLoad_ProcessAsyncLoads | resetTimer==1 gate; status==1 -> ProcessAsyncLoad |
| 250C8 | gl_func_000250C8 | AudioLoad_ProcessAsyncLoad | FinishAsyncLoad inlined |
| 25320 | gl_func_00025320 | AudioLoad_AsyncDma | comment + gl_ref_0003998C |
| 253B0 | game_libs_func_000253B0 | AudioLoad_AsyncDmaUnkMedium | gl_ref_00039A1C |
| 253C4 | game_libs_func_000253C4 | AudioLoad_RelocateSample | comment + gl_ref_00039A30 |
| 25504 | gl_func_00025504 | AudioLoad_RelocateFontAndPreloadSamples | comment + gl_ref_00039B70 |
| 258C0 | game_libs_func_000258C0 | AudioLoad_ProcessSamplePreloads | preloadSampleStack drain |
| 25A80 | game_libs_func_00025A80 | AudioLoad_AddToSampleSet | OoT order |
| 25AC8 | gl_func_00025AC8 | AudioLoad_GetSamplesForFont | OoT order |
| 25BFC | game_libs_func_00025BFC | AudioLoad_AddUsedSample | gl_ref_0003A268 alias |
| 25C54 | gl_func_00025C54 | AudioLoad_PreloadSamplesForFont | comment |
| 260B4 | gl_func_000260B4 | AudioLoad_LoadPermanentSamples | GetLoadTable/GetRealTableIndex sweep |
| 261F4 | gl_func_000261F4 | AudioThread_Update | return UpdateImpl() (0x3A880) |
| 26214 | gl_func_00026214 | AudioThread_UpdateImpl | comment |
| 26790 | gl_func_00026790 | AudioThread_ProcessGlobalCmd | comment |
| 26AA4 | game_libs_func_00026AA4 | AudioThread_SetFadeOutTimer | state=2, fadeVelocity=-(fadeVolume/time) |
| 26AF8 | game_libs_func_00026AF8 | AudioThread_SetFadeInTimer | state=1, fadeTimer/fadeTimerUnkEu |
| 26B40 | game_libs_func_00026B40 | AudioThread_InitMesgQueuesImpl | cmd ring indices + 3 osCreateMesgQueue |
| 26BD8 | game_libs_func_00026BD8 | AudioThread_QueueCmd | 8-byte cmd ring push |
| 26C24 | gl_func_00026C24 | AudioThread_QueueCmdF32 | QueueCmd(op, &arg) |
| 26C48 | gl_func_00026C48 | AudioThread_QueueCmdS32 | QueueCmd(op, &arg) |
| 26C6C | gl_func_00026C6C | AudioThread_QueueCmdS8 | char param |
| 26C9C | gl_func_00026C9C | AudioThread_QueueCmdU16 | short param |
| 26CCC | game_libs_func_00026CCC | AudioThread_ScheduleProcessCmds | OoT order |
| 26D4C | game_libs_func_00026D4C | AudioThread_ResetCmdQueue | curCmdRdPos = cmdWrPos; cmdQueueFinished=0 |
| 26D64 | gl_func_00026D64 | AudioThread_ProcessCmds | gl_ref_0003B3D0 alias |
| 270FC | gl_func_000270FC | AudioThread_GetAsyncLoadStatus | OoT func_800E5E20: externalLoadQueue recv, split >>24 / &0xFFFFFF |
| 27160 | gl_func_00027160 | AudioThread_GetFontsForSequence | wrapper, OoT order |
| 2722C | gl_func_0002722C | AudioThread_ResetAudioHeap | OoT order |
| 272C4 | gl_func_000272C4 | AudioThread_PreNMIInternal | resetTimer store |
| 27300 | game_libs_func_00027300 | AudioThread_GetChannelIO | seqPlayers[i].channels[j]->soundScriptIO |
| 27354 | game_libs_func_00027354 | AudioThread_GetSeqPlayerIO | seqPlayers[i].soundScriptIO[j] |
| 2737C | gl_func_0002737C | AudioThread_InitExternalPool | InitPool(&externalPool 0x2178, ...) |
| 273AC | game_libs_func_000273AC | AudioThread_ResetExternalPool | externalPool.startRamAddr = NULL |
| 273B8 | game_libs_func_000273B8 | AudioThread_ProcessSeqPlayerCmd | 14-case op switch |
| 276E4 | gl_func_000276E4 | AudioThread_InitMesgQueues | return InitMesgQueuesImpl() (0x3B1AC) |
| 27704 | gl_func_00027704 | Audio_InvalDCache | osSetIntMask(1); osInvalDCache; restore |
| 27744 | gl_func_00027744 | Audio_WritebackDCache | osSetIntMask(1); osWritebackDCache; restore |
| 27784 | game_libs_func_00027784 | osAiSetNextBuffer | comment: libultra aisetnextbuf.c (OoT audio os.c copy) |
| 27804 | gl_func_00027804 | Audio_InitSampleState | comment: OoT Audio_InitSampleState (older InitNoteSub) |
| 27C48 | game_libs_func_00027C48 | Audio_NoteSetResamplingRate | gl_ref_0003C2B4 alias in the InitSampleState donor |
| 27D00 | gl_func_00027D00 | Audio_NoteInit | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 27DC0 | game_libs_func_00027DC0 | Audio_NoteDisable | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 27E24 | gl_func_00027E24 | Audio_ProcessNotes | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2831C | game_libs_func_0002831C | Audio_GetInstrumentTunedSample | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28358 | gl_func_00028358 | Audio_GetInstrumentInner | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2842C | gl_func_0002842C | Audio_GetDrum | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28510 | gl_func_00028510 | Audio_GetSoundEffect | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28604 | gl_func_00028604 | Audio_SeqLayerDecayRelease | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2886C | gl_func_0002886C | Audio_SeqLayerNoteDecay | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2888C | gl_func_0002888C | Audio_SeqLayerNoteRelease | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 288AC | game_libs_func_000288AC | Audio_BuildSyntheticWave | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 289B0 | gl_func_000289B0 | Audio_InitSyntheticWave | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28A08 | game_libs_func_00028A08 | Audio_InitNoteList | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28A18 | gl_func_00028A18 | Audio_InitNoteLists | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28A68 | gl_func_00028A68 | Audio_InitNoteFreeList | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28B0C | gl_func_00028B0C | Audio_NotePoolClear | comment: OoT verbatim |
| 28C6C | gl_func_00028C6C | Audio_NotePoolFill | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28DA8 | game_libs_func_00028DA8 | Audio_AudioListPushFront | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28DE8 | game_libs_func_00028DE8 | Audio_AudioListRemove | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28E14 | game_libs_func_00028E14 | Audio_FindNodeWithPrioLessThan | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28E94 | gl_func_00028E94 | Audio_NoteInitForLayer | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 28FCC | gl_func_00028FCC | Audio_NoteInterTrack | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29000 | game_libs_func_00029000 | Audio_NoteReleaseAndTakeOwnership | gl_ref_0003D66C alias in AllocNote |
| 2902C | gl_func_0002902C | Audio_AllocNoteFromDisabled | gl_ref_0003D698 alias |
| 29078 | gl_func_00029078 | Audio_AllocNoteFromDecaying | gl_ref_0003D6E4 alias |
| 290C8 | gl_func_000290C8 | Audio_AllocNoteFromActive | gl_ref_0003D734 alias |
| 291C0 | gl_func_000291C0 | Audio_AllocNote | comment: OoT verbatim |
| 29494 | gl_func_00029494 | Audio_NoteInitAll | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 295C4 | game_libs_func_000295BC | Audio_SequenceChannelProcessSound | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2978C | gl_func_0002978C | Audio_SequencePlayerProcessSound | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 298D8 | game_libs_func_000298D8 | Audio_GetPortamentoFreqScale | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29934 | game_libs_func_00029934 | Audio_GetVibratoPitchChange | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29978 | gl_func_00029978 | Audio_GetVibratoFreqScale | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29B6C | gl_func_00029B6C | Audio_NoteVibratoUpdate | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29BC8 | game_libs_func_00029BC8 | Audio_NoteVibratoInit | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29C80 | game_libs_func_00029C80 | Audio_NotePortamentoInit | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29CAC | game_libs_func_00029CAC | Audio_AdsrInit | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 29CCC | game_libs_func_00029CCC | Audio_AdsrUpdate | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A014 | gl_func_0002A014 | AudioSeq_GetScriptControlFlowArgument | gl_func_0003E680 alias in seqplayer donors |
| 2A07C | game_libs_func_0002A07C | AudioSeq_HandleScriptFlowControl | gl_func_0003E6E8 alias + comment |
| 2A258 | game_libs_func_0002A258 | AudioSeq_InitSequenceChannel | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A3AC | gl_func_0002A3AC | (AudioSeq_SeqChannelSetLayer, NOT renamed) | alias 0x3EA18; tool refuses: also defined in src/match_imports |
| 2A3AC | gl_func_0002A3AC | AudioSeq_SeqChannelSetLayer | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A4D0 | gl_func_0002A4D0 | AudioSeq_SeqLayerDisable | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A50C | gl_func_0002A50C | AudioSeq_SeqLayerFree | gl_func_0003EB78 alias |
| 2A55C | gl_func_0002A55C | AudioSeq_SequenceChannelDisable | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A5C8 | game_libs_func_0002A5C8 | AudioSeq_SequencePlayerSetupChannels | gl_func_0003EC34 alias |
| 2A6C0 | gl_func_0002A6C0 | AudioSeq_SequencePlayerDisableChannels | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A740 | gl_func_0002A740 | AudioSeq_SequenceChannelEnable | gl_func_0003EDAC alias |
| 2A7D8 | gl_func_0002A7D8 | AudioSeq_SequencePlayerDisable | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A884 | game_libs_func_0002A884 | AudioSeq_AudioListPushBack | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A8C4 | game_libs_func_0002A8C4 | AudioSeq_AudioListPopBack | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A904 | gl_func_0002A904 | AudioSeq_InitLayerFreelist | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2A9A4 | game_libs_func_0002A9A4 | AudioSeq_ScriptReadU8 | gl_func_0003F010 alias |
| 2A9B8 | game_libs_func_0002A9B8 | AudioSeq_ScriptReadS16 | gl_func_0003F024 alias |
| 2A9F0 | game_libs_func_0002A9F0 | AudioSeq_ScriptReadCompressedU16 | gl_func_0003F05C alias |
| 2AA30 | gl_func_0002AA30 | AudioSeq_SeqLayerProcessScript | gl_func_0003F09C alias |
| 2AB34 | gl_func_0002AB34 | AudioSeq_SeqLayerProcessScriptStep1 | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2ABC0 | gl_func_0002ABC0 | AudioSeq_SeqLayerProcessScriptStep5 | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2AD1C | gl_func_0002AD1C | AudioSeq_SeqLayerProcessScriptStep2 | comment |
| 2B09C | gl_func_0002B09C | AudioSeq_SeqLayerProcessScriptStep4 | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2B5F4 | gl_func_0002B5F4 | AudioSeq_SeqLayerProcessScriptStep3 | comment |
| 2BA08 | game_libs_func_0002BA08 | AudioSeq_SetChannelPriorities | gl_func_00040074 alias |
| 2BA38 | gl_func_0002BA38 | AudioSeq_GetInstrument | gl_func_000400A4 alias |
| 2BAAC | gl_func_0002BAAC | AudioSeq_SetInstrument | gl_func_00040118 alias |
| 2BB58 | game_libs_func_0002BB58 | AudioSeq_SequenceChannelSetVolume | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2BB7C | gl_func_0002BB7C | AudioSeq_SequenceChannelProcessScript | gl_func_000401E8 alias + comment |
| 2C7A4 | gl_func_0002C7A4 | AudioSeq_SequencePlayerProcessSequence | comment |
| 2CF60 | game_libs_func_0002CF60 | AudioSeq_ProcessSequences | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2D014 | gl_func_0002D014 | AudioSeq_SkipForwardSequence | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2D064 | gl_func_0002D064 | AudioSeq_ResetSequencePlayer | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2D130 | gl_func_0002D130 | AudioSeq_InitSequencePlayerChannels | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2D224 | gl_func_0002D224 | AudioSeq_InitSequencePlayer | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2D2F4 | gl_func_0002D2F4 | AudioSeq_InitSequencePlayers | OoT playback.c / effects.c / seqplayer.c order + body check (run 446) |
| 2D618 | gl_func_0002D620 | snd_MuteAll_2D618 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D670 | gl_func_0002D670 | snd_UnmuteAll_2D670 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D6A0 | gl_func_0002D6A0 | snd_Unmute_2D6A0 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D6C8 | gl_func_0002D6C8 | snd_SetSoundOutputMode_2D6C8 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D70C | gl_func_0002D710 | snd_SetPlayer1VolumeLevel_2D70C | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D748 | gl_func_0002D74C | snd_SetPlayer0VolumeLevel_2D748 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D784 | gl_func_0002D788 | snd_SetPlayer2VolumeLevel_2D784 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D7C0 | gl_func_0002D7D0 | snd_ResetVolumeLevels_2D7C0 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D830 | game_libs_func_0002D830 | snd_ApplyPlayer3VolumeLevel_2D830 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D868 | game_libs_func_0002D868 | snd_ApplyPlayer1VolumeLevel_2D868 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D8A0 | game_libs_func_0002D8A0 | snd_ApplyPlayer0VolumeLevel_2D8A0 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2D8D8 | gl_func_0002D8D8 | snd_ApplyPlayer2VolumeLevel_2D8D8 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DC74 | game_libs_func_0002DC74 | snd_SetPlayer3FreqScaleFromStick_2DC74 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DCF8 | gl_func_0002DCF8 | snd_StopAudioCmds_2DCF8 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DD58 | gl_func_0002DD58 | snd_PlayPlayer3Seq_2DD58 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DDEC | game_libs_func_0002DDEC | snd_PlayPlayer1SeqDefault_2DDEC | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DE24 | gl_func_0002DE24 | snd_PlayPlayer1Seq_2DE24 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DE9C | game_libs_func_0002DE9C | snd_StopPlayer1Seq_2DE9C | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DED0 | gl_func_0002DED0 | snd_PlayPlayer0Seq0_2DED0 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DEF4 | game_libs_func_0002DEF4 | snd_PlayPlayer2Seq_2DEF4 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DF30 | game_libs_func_0002DF30 | snd_StopPlayer0Seq_2DF30 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DF64 | gl_func_0002DF68 | snd_SetPlayer0ChannelFreqScale_2DF64 | command-word encoding (OoT audiothread_cmd.h ops); 1080-specific, address suffix kept (run 446) |
| 2DD30 | game_libs_func_0002DD30 | snd_Stub_2DD30 | empty jr ra; nop stub in the sound glue (run 455) |
| 2DD38 | game_libs_func_0002DD38 | snd_ScheduleSeqDefault_2DD38 | seq id -> D_1C0BC, 210 (0xD2) -> timer0 D_1C084; snd_UpdateTimers_2D374 starts that seq at expiry (15 -> player 3, else player 1); baked call from snd_HandleEvent_2FB74 case 512 (run 455) |
| 2DD90 | gl_func_0002DD90 | snd_ScheduleSeqAfter_2DD90 | snd_ScheduleSeq_2DDBC((u8)seq, delay, 0, 1.0f) (baked jal 0x42428 = 0x2DDBC) (run 455) |
| 2DDBC | game_libs_func_0002DDBC | snd_ScheduleSeq_2DDBC | seq id, delay (timer0), arg, volume -> the delayed seq-start record read by snd_UpdateTimers_2D374 (run 455) |
| 2DF98 | gl_func_0002DF98 | snd_SoundObjInit_2DF98 | 0x64-byte sound object init (kind byte 0x21); called by the bootup ctor 0x57C right after mem_new(0x64); then the channel IO preset 2F8A0 (run 455) |
| 2E06C | gl_func_0002E06C | snd_SoundObjReset_2E06C | clears 0x20/0x23 and floats 0/4, then the 2F934 IO preset for kind 0x21; called from the object update (run 455) |
| 2E0A0 | game_libs_func_0002E0A0 | snd_SoundObjSetScaleIdx15_2E0A0 | o->0x32 = 0xF: index into the freq / vol multiplier tables (D+0x1C330 / 0x1C3B0) read by 2F288; bootup wrapper 0x8B4 (run 455) |
| 2E0AC | game_libs_func_0002E0AC | snd_SoundObjSetScaleIdx31_2E0AC | o->0x32 = 0x1F, twin of 2E0A0; bootup wrapper 0x8D4 (run 455) |
| 2E0B8 | game_libs_func_0002E0B8 | snd_SoundObjSetFlag1A_2E0B8 | o->0x1A (u16) = 1; bootup wrapper 0xA68 (run 455) |
| 2E0C4 | game_libs_func_0002E0C4 | snd_SoundObjTriggerEvent_2E0C4 | event type 0x30, level 0x29 (from speed o->0: 25/38/50 thresholds), 0x2E/0x2D; bootup wrappers 0x8F4/0x940/0x98C/0x9D8 pass 0..3 (run 455) |
| 2E1A8 | game_libs_func_0002E1A8 | snd_SoundObjDisable_2E1A8 | o->0x16 /= 1 (disabled), clear the 0x20 fired latch; bootup wrapper 0xA24 (run 455) |
| 2E1C0 | gl_func_0002E1C0 | snd_SoundObjStart_2E1C0 | one-shot: latch bit5 of 0x16, then snd_SoundObjPlay_2F578(o, 0x29 / 0x2A, 0, 80.0f, o->0x28); bootup wrapper 0x85C (run 455) |
| 2E24C | gl_func_0002E24C | snd_SoundObjStop_2E24C | clears the 0x16 bit5 latch set by 2E1C0 and requests cue 0x3D (2E1C0 counterpart); bootup wrapper 0x888 (run 455) |
| 2E290 | game_libs_func_0002E290 | snd_SoundObjEventIndex_2E290 | o->0x31 (event type low byte) -> table index 0..16 for the update (gl_func_000428FC call in 2E354) (run 455) |
| 2E354 | gl_func_0002E354 | snd_SoundObjUpdate_2E354 | per-object sound update (0xE64): channel IO / freq / vol commands, called from bootup snd_updatePlayer with the object (run 455) |
| 2F1B8 | game_libs_func_0002F1B8 | snd_FindNearestF32_2F1B8 | binary search of a sorted f32 table, nearest index (gl_ref_00043824 in 2F720 / 2E354) (run 455) |
| 2F288 | gl_func_0002F288 | snd_SoundObjUpdateChannel_2F288 | integrates o->0 and issues CHANNEL_SET_IO 6/5 + FREQ_SCALE + VOL_SCALE on player-0 channel 3 or 7 (kind); gl_func_000438F4 in 2E354 (run 455) |
| 2F578 | game_libs_func_0002F578 | snd_SoundObjPlay_2F578 | /v/+15 clamped to 0x7F (x o->0x54 when bit0 of 0x1C), then snd_SetPlayer0ChannelPanIO_2F638(kind, id, ...); the 0x43BE4 callee of 2E1C0 / 2E354 (run 455) |
| 2F630 | game_libs_func_0002F630 | snd_Stub_2F630 | empty stub (run 455) |
| 2F720 | game_libs_func_0002F720 | snd_SoundObjSetAngle_2F720 | angle*180 -> pan byte 0x60, table lookups via 2F1B8, delta -> 0x58 clamp; called from bootup snd_updatePlayer (run 455) |
| 2FB54 | gl_func_0002FB54 | snd_PostEvent_2FB54 | snd_HandleEvent_2FB74(ev, 0); 18 callers (run 455) |
| 3058C | gl_func_00030598 | snd_TriggerChannel8CueIfIdle_3058C | starts at 0x3058C; calls the 0x30610 cue start only when its fade count (+8) and hold (+0xC) are 0 (run 455) |
| 30610 | gl_func_0003061C | snd_TriggerChannel8Cue_30610 | starts at 0x30610; (duration, hold, mode): fade-up step (1-acc)/duration, CHANNEL_SET_IO 0x06000800 = mode (run 455) |
| 307A8 | game_libs_func_000307A8 | snd_TickChannel8Fade_307A8 | per-frame: fade up for the count, hold, then decay to the floor; CHANNEL_SET_VOL_SCALE 0x01000800 (run 455) |
| 308AC | game_libs_func_000308AC | snd_SetChannel8Mode_308AC | mode 0/1/2 -> floor / IO port 0 / decay; emits 0x06000800 IO + 0x01000800 volume (run 455) |
| 309A4 | game_libs_func_000309A4 | snd_Stub_309A4 | empty stub (run 455) |
| 309AC | game_libs_func_000309AC | snd_SetLevelRampTarget_309AC | sel 0/1/2 -> snd_RampInit_31CA8(&D_1C0C0, 0/30/70, 30); D_1C0C4 (current) feeds 2F288; bootup 0x1C8 (run 455) |
| 30A20 | gl_func_00030A20 | snd_StartPlayer2Seq_30A20 | snd_PlayPlayer2Seq_2DEF4(a0, a1), stores both, then the cue-2 requests 316CC / 31710; bootup wrapper 0x27C (run 455) |
| 31334 | gl_func_00031334 | snd_HandleSeqEnd_31334 | bootup 0x188 prints "Poop end" then calls it (0x148 "Poop start" -> snd_HandleSeqEvent_30AF4); DISABLE_SEQPLAYER 0x83010000 with per-state fades (run 455) |
| 31520 | gl_func_00031520 | snd_AddSoundHeap_31520 | AudioThread_InitExternalPool wrapper; bootup 0x360 prints "Poop: Added sound heap" (run 455) |
| 31540 | gl_func_00031540 | snd_RemoveSoundHeap_31540 | AudioThread_ResetExternalPool wrapper; bootup 0x38C prints "Poop: Removed sound heap" (run 455) |
| 31560 | gl_func_00031560 | snd_PreNMI_31560 | AudioThread_PreNMIInternal wrapper; called from RcpMgr_service (run 455) |
| 31580 | game_libs_func_00031580 | snd_InitCueQueues_31580 | ids / ring indices of the two 0x64 cue queues at D+0x368 (run 455) |
| 315BC | game_libs_func_000315BC | snd_RequestCue_315BC | snd_CueQueueSet_31754(&queue[a0], 1, cue, 0x7F) (run 455) |
| 31608 | gl_func_00031608 | snd_SoundObjRequestCue_31608 | object (0x22 surface, 0x21 kind) -> queue id 0x62 and snd_CueQueueSet_31754; from 2E24C / 2E354 (run 455) |
| 316CC | gl_func_000316CC | snd_RequestCue2Prio_316CC | queue D+0x430: CueQueueSet(mode 1 = priority interrupt, a0+0x17F, 0x7F) + push (run 455) |
| 31710 | gl_func_00031710 | snd_RequestCue2_31710 | queue D+0x430: CueQueueSet(mode 0 = append) + push (run 455) |
| 31754 | game_libs_func_00031754 | snd_CueQueueSet_31754 | (queue, mode, cueId, prio): 0x54 mode, 0x58 prio, 0x5C = cue script from the halfword offset table (gl_ref_00045DC0) (run 455) |
| 31784 | game_libs_func_00031784 | snd_CueQueuePush_31784 | pushes the pending 0x5C script into the 16-entry ring; mode 1 flushes when prio >= current (gl_ref_00045DF0) (run 455) |
| 317F0 | game_libs_func_000317F0 | snd_CueQueueStep_317F0 | countdown 0x48; at 0 read the next (cmd, wait) halfwords from the 0x50 cursor (gl_ref_00045E5C) (run 455) |
| 3183C | game_libs_func_0003183C | snd_CueQueuePop_3183C | dequeue the next nonzero ring entry into the 0x50 cursor (gl_ref_00045EA8) (run 455) |
| 31898 | gl_func_00031898 | snd_CueQueueUpdate_31898 | push pending, step, else pop; returns 1 on a new cmd (gl_ref_00045F04 in snd_SetPlayer2ChannelIO_3190C) (run 455) |
| 31A64 | game_libs_func_00031A64 | snd_ResetChannel10Mode_31A64 | D+0x1CAA8 (31A74's current mode) = -1 (run 455) |
| 31A74 | gl_func_00031A74 | snd_UpdateChannel10Emitter_31A74 | (mode, distance, pan): channel 0xA IO 0 = mode, VOL_SCALE from distance vs per-mode range, PAN = pan+63; bootup 0x31C passes func_3F8's distance / projection (run 455) |
| 31CA8 | game_libs_func_00031CA8 | snd_RampInit_31CA8 | ramp {target, cur, count, frac}: target, count, frac = 0 (run 455) |
| 31CB8 | game_libs_func_00031CB8 | snd_RampTick_31CB8 | 8.8 fixed-point step of cur toward target over count; called by snd_UpdateTimers_2D374 (run 455) |
| 31D70 | game_libs_func_00031D70 | snd_Init_31D70 | stores three config words then calls AudioLoad_Init; called from bootup SnowBoard_func_0000E800 (run 455) |
| 31DA4 | gl_func_00031DA4 | snd_AudioUpdate_31DA4 | return AudioThread_Update(); called from RcpMgr_service (run 455) |
| 31DD8 | gl_func_00031DD8 | snd_FrameUpdate_31DD8 | snd_UpdateTimers_2D374(); called from app_run (run 455) |

### Run 513 (agent-c): SoundObj channel glue names

Commit a6d00146b (**pure rename**, gate PASS, 3 renamed). Callers from `scripts/uso-imports.py callers`:
- snd_Player0ChannelIOPreset_2F8A0 -> **snd_soundObjChannelsOn**: only snd_SoundObjInit(kind) calls it.
  It sets io port 0 = 1 on the kind's channels (1 + 3 / 5 + 7 / 5).
- snd_Player0ChannelIOPreset_2F934 -> **snd_soundObjChannelsOff**: snd_SoundObjReset, snd_HandleSeqEvent_30AF4
  and snd_HandleSeqEnd call it with the kind. It puts the same io ports back to -1 / 0.
- snd_SetPlayer0ChannelPanIO_2F638 -> **snd_soundObjSendPlay**: only snd_SoundObjPlay calls it. It sends
  the pan, the volume io and the note (sel + base) to the kind's channel.
- **Held back:** snd_HandleEvent_2FB74 -> snd_dispatchEvent (the event switch that snd_sendEvent and
  snd_PostEvent forward to). Its RoData pool macro `kRo_snd_HandleEvent_2FB74` (include/gdl/gl_data.h)
  embeds the function name. rename-symbol.py does not rename `kRo_<OLD>` pools, so `uso-data-sites.py
  check` fails after the rename. Fix the tool (treat `kRo_OLD` / `kRo_OLD_<K>` as derived names), then rename.
- The remaining suffixed glue (SetPlayer0ChannelParams_2F9D4 / IO12_2FA90 / ResetPlayer0ChannelIO1_2FB10,
  all called only by snd_SoundObjUpdate; SetPlayer1Channel15IO_2D910; SetPlayer2ChannelIO_3190C;
  Channel0IO_30504 / Channel8IO1_30564 / Channel8Pan_305CC) has no game-code caller that names its
  purpose; the io-port meanings would need the sequence scripts.
- Step 6 (audio struct conversions in game_libs_post.c) was not reached this run.

### Run 518 (agent-c): placeholder calls, heap caches, Note / seq / reverb fields

Three commits, all gated (PASS, 3288/3288, ROM identical):
- 5a30b70a1 (**tool output**, name-placeholder-calls.py `plan --write`): 35 sites. game_libs_o2_23914.c 9,
  _26790.c 8, _2C7A4.c 13 (the 30 audio-driver sites), timproc_uso_b5_ncc_BDEC.cpp 5. The other 15
  driver donors and the genproc files have no provable site left (timproc_uso_b5.c: 3 no-jal).
  Oddity worth knowing: in AudioSeq_SequencePlayerProcessSequence (2C7A4) the two calls after the
  load-complete test both resolve to AudioLoad_IsSeqLoadComplete, the second with defaultFont.
- 33d289fb6 (hand edit): **heap cache types in include/audio.h.** AudioCacheEntry 0xC, SampleCacheEntry
  0x14 (u8 sampleBankId), AudioSampleCache 0x294, AudioPersistentCache 0xD4, AudioTemporaryCache 0x2C,
  AudioCache 0x110, Session / Cache / Common pool splits, AudioPreloadReq 0x14. AudioContext now models
  0x21C8 cachePool, 0x21D8 / 0x21E8 persistent / temporaryCommonPool, 0x21F8 / 0x2308 / 0x2418 seq / font
  / sampleBankCache, 0x2528 permanentPool, 0x2538 permanentCache[32], 0x26B8 / 0x294C persistent /
  temporarySampleCache, 0x2BE0..0x2C10 the splits (OoT offsets - 0x828). 0x21A8..0x21C8 stays padding
  (OoT: two unused pools). Converted: AudioHeap_Alloc / AllocZeroed / InitPool / ResetPool /
  InitPersistentCache / InitTemporaryCache / AllocAttemptExternal / AllocZeroedAttemptExternal /
  InitMainPools / InitSessionPools / InitCachePools / InitPersistent- and InitTemporaryPoolsAndCaches /
  AllocPermanent / InitSampleCaches / AllocPersistentSampleCacheEntry, and AllocTemporarySampleCacheEntry's
  gl_heap_* views. A scoped `#define gAudioCtx (*(AudioContext *)&gAudioContext)` covers
  AllocZeroedAttemptExternal..DiscardSampleCaches (#undef after it).
- 978b570cd (hand edit): Audio_NoteInit, Audio_NoteVibratoUpdate (Note *), Audio_NoteReleaseAndTakeOwnership
  (ticksPerUpdateInv), AudioSeq_SequencePlayerDisable (SequencePlayer *, fontCache.temporary entries[].id
  -> nextSide, which independently confirms the cache layout), SkipForwardSequence, SeqLayerFree,
  AudioListPopBack. **Reverb:** `REVERB_AT(rec)` = `(SynthesisReverb *)(rec + 0x18)` names
  synthesisReverbs[idx] off the kept `&gAudioCtx + idx * 0x158` base (IDO folds the 0x18): FilterReverb,
  LoadAuxBufferC, UpdateReverbs. **Byte trap:** in LoadAuxBufferC's 0x05 packet, resampleFlags /
  unk_0E as member reads re-rank the `|` operands (.text changes); they stay raw derefs.
- Per-.o check: /tmp/claude-1000/c518/ocmp.py compares every non-debug section and the relocation
  lists (symbol names) of two .o files; all 23 audio objects identical to the pre-run build.
- Raw-access census (/tmp/claude-1000/c518/census2.py: typed `*(T *)(` derefs + `(char *)` casts in
  Audio* / aud_ / snd_ functions of game_libs_post.c): 495 -> 396. The donors are mostly typed already
  (o2_26D64 18, o2_273B8 20, ncc_28A68 6, o2_23914 7 left).
- Not converted (reasons): Gl29000Obj (u32-container bitfield lever), AudioHeap_DiscardSampleCaches
  (s8 sampleBankId view; audio.h has u8), the gl_221D8 / gl_22464 font views (no SoundFont / Instrument
  types in audio.h yet), NON_MATCHING bodies (Audio_NoteVibratoInit).
- **Next:** SoundFont / Instrument / Drum types into audio.h (gl_221D8 / gl_22464 / 23BDC views);
  the remaining AudioLoad_* raw sites (GetSamplesForFont, SyncLoadFont, DiscardFont); the o2_26D64 /
  o2_273B8 donors; then the select-screen items (SelectionMgr split-screen fields 0x3C..0x54, the 8FC8
  0x70 list ctors onto SelItemList, a shared select-model base, Character / BoardList_createItem).

### Run 522 (agent-c): font / instrument / command types, donors 26D64 / 273B8, ProcessChannelCmd

Four commits on agent-c (base 0e408e5bf), each gated PASS (3288/3288, ROM identical, placeholder
check 0 mismatches); every rebuilt .o identical to the pre-run build (sections + relocations, and
`objdump -d -r`):
- f354a46c9 (hand edit): **include/audio.h font types**, OoT layouts with offset / size asserts:
  AdsrEnvelope 0x4 (OoT EnvelopePoint), SoundFontSound (alias of TunedSample), Instrument 0x20,
  Drum 0x10, SoundEffect 0x8, SoundFont 0x14, SampleBankRelocInfo 0x18, AudioTableHeader /
  AudioTableEntry / AudioTable. AudioContext's sequence / font / sample-bank tables are now
  `AudioTable *`, soundFontList `SoundFont *`, usedSamples `Sample *[0x80]`; AdsrSettings /
  AdsrState.envelope `AdsrEnvelope *`. Views deleted and converted: DiscardSampleCacheEntry (221D8),
  DiscardSampleCaches (22464; the entry keeps an s8 sampleBankId view, cast from the typed
  persistentSampleCache.entries[j]), RelocateFont (23BDC), SyncLoadSample (230D0), AudioLoad_Init
  tables (24378), ProcessAsyncLoad (250C8), RelocateSample (253C4), RelocateFontAndPreloadSamples
  (25504), donors o2_25C54 (now includes audio.h) and o2_240A0. Raw sites: AudioLoad_DiscardFont
  (fontCache.temporary.entries[0/1].id, persistent.entries[i].id, each alias symbol still its own
  base), SyncLoadFont (soundFontList[a0].sampleBankId1/2), GetSamplesForFont (SoundFont / Drum /
  Instrument; its baked fold jal 0x3A0EC = splat 0x25A80 = AudioLoad_AddToSampleSet).
- e26855212 (hand edit): **AudioCmd** (0x8; op / arg0 / arg1 / arg2 / AudioCmdArg arg). 1080 has the
  older layout: every value form (asFloat / asInt / asSbyte / asUbyte / asUShort) is at +4, not OoT's
  +7 / +6. o2_273B8 is now (SequenceChannel *, AudioCmd *) on audio.h fields (20 -> 0 raw);
  o2_26D64 (ProcessCmds) uses AudioCmd for the queue slot and SequencePlayer field names on its
  per-player view (18 -> 0 by census2; the flags-byte view and the enabled-bit test stay, they are the
  dead-mask lever). **Byte lever:** with typed operands, the target's `c.eq.s $f0,$f4` /
  `beq v0,t4` needs the struct field FIRST (`channel->volumeScale != cmd->arg.asFloat`); the
  command-first field spelling swaps both registers. The run-132 raw f2C read in 26D64 is retired by it.
- 1b8140ecb (**tool output**, rename-symbol.py): AudioThread_ProcessSeqPlayerCmd ->
  **AudioThread_ProcessChannelCmd**. Evidence: 0x273B8 = USO 0x3BA24 = ProcessCmds' callee
  f(seqPlayer->channels[arg1], cmd) for each enabled channel; its cases write SequenceChannel fields.
  1080 inlines the seq-player commands (0x41..0x4E) into ProcessCmds' switch. gl_func_0003ADFC in
  26D64 is AudioThread_ProcessGlobalCmd (splat 0x26790); both stay pinned gl_func_ names.
- a5e71bace (hand edit): select.h / genproc (see 1080_MODES.md run 522).
- Census (census2: typed derefs + char* casts in Audio* / aud_ / snd_ fns): game_libs_post.c 396 -> 368,
  o2_26D64 18 -> 0, o2_273B8 20 -> 0 (o2_25C54 / o2_240A0 were 0 by this metric; their local views
  are gone).
- **Next:** the 22464 / 221D8 entries could drop their s8 view if SampleCacheEntry.sampleBankId
  went s8 and AllocTemporarySampleCacheEntry's u8 read were kept another way (untested); AudioLoad_Init
  (24378) still has its own Ctx view (MesgQueue / pool padding) to fold onto AudioContext; the
  remaining game_libs_post.c audio raw sites (368) are mostly AudioSynth_* command builders and
  the NON_MATCHING bodies; ncc_28A68 (6) and o2_23914 (7).

### Run 525 (agent-c): AudioTask, AudioLoad_Init on AudioContext, s8 sampleBankId

26d402122 on agent-c (hand edit; gate PASS 3288/3288, placeholder check 0 mismatches). Every
audio.h includer is identical to a fresh pre-run build, in both trees where built: sections and
relocations match, and so does `objdump -d -r`. The includers are game_libs_post.c, bootup_uso.c
and the 10 o2 donors.
- **include/audio.h:**
  - `AudioTask` (0x50, OoT): OSTask_t task (libultra/os_task.h) + taskQueue / unk_44 / unk_48.
  - AudioContext: curTask is `AudioTask *` and rspTask[2] is `AudioTask`. 0x2138 is
    `maxTempoTvTypeFactors` (f32) and 0x213C is `refreshRate` (50 PAL / 60); both are asserted.
- **AudioLoad_Init (24378):** the local gl_24378_Ctx / Pool / MesgQueue view is deleted, and the
  body runs on `(*(AudioContext *)&gAudioContext)`. The two dataSize words are
  rspTask[0/1].task.data_size; 0x1644 / 0x1648 are cartHandle / driveHandle. Only the
  heap-init-sizes view (gl_24378_HeapInitSizes) is left.
- **s8 sampleBankId (run-522 "untested" item): it works.** SampleCacheEntry.sampleBankId is now
  s8, as in OoT. No matched reader used the u8 (AllocTemporary / PersistentSampleCacheEntry never
  read the field). AudioHeap_DiscardSampleCacheEntry (221D8) and AudioHeap_DiscardSampleCaches
  (22464) take `SampleCacheEntry *` directly, and their s8 entry views are deleted.
- **Census:** game_libs segment raw 1760 -> 1758; game_libs_post.c 387 -> 385 by
  readability-census.py. The run-518 census2 metric was not rerun.
- **Next:** the AudioSynth_* command builders in game_libs_post.c (most of the remaining ~368
  census2 sites), ncc_28A68 (6) and o2_23914 (7). None were attempted this run (time).
  o2_26214 still keeps its own gl_26214_Ctx / AudioTask / OSTask_t view, which can now fold onto
  AudioContext.rspTask / AudioTask.

### Run 530 (agent-c): sequence channel / player / note bodies on audio.h members

3b778d68a on agent-c (hand edit, game_libs_post.c only; gate PASS 3288/3288, placeholder check
0 mismatches; game_libs_post.c.o identical to the pre-run build in both trees by sections,
relocations and `objdump -d -r`).
- **Correction to the run-525 "next":** the AudioSynth_* command builders are NOT where the raw
  sites are. They take `int *a0` and write a0[0] / a0[1], which the census does not count (no
  `*(T *)(p + K)` form); only AudioSynth_LoadReverbSamples (5) and LoadAuxBufferC (4) have any.
  The 385 game_libs_post.c casts were: Audio_SequenceChannelProcessSound 41, AudioSeq_
  InitSequenceChannel 32, three fs_bufWrite / Read bodies 23 each and MCamera_ctor 19 / sys_fatal
  13 (not audio), Audio_NoteInitForLayer 21, AudioSeq_ResetSequencePlayer 19,
  Audio_SequencePlayerProcessSound 15, Audio_AllocNoteFromActive 13, Audio_NoteDisable 10.
- Converted:
  - AudioSeq_InitSequenceChannel: all SequenceChannel reset stores (adsr.decayIndex = 240 is
    OoT's releaseRate slot). The byte-0 bit cascade and the +1 changes byte stay byte RMWs.
  - Audio_SequenceChannelProcessSound: channel / seqPlayer fields. **Byte levers:** as members
    the float products want member-first order ((volume * volumeScale) * appliedFadeVolume,
    layer 0x38 * appliedVolume); the layer pan sum keeps raw `FW(arg0, 0x30)` (pan): as a
    member, in either operand order, the addu operands and later t-temps swap.
  - AudioSeq_ResetSequencePlayer, Audio_SequencePlayerProcessSound (product fadeVolume *
    fadeVolumeScale, same order lever), Audio_NoteDisable (Note playbackState).
- **Census:** game_libs_post.c 385 + 28 -> 313 + 16; game_libs segment 1408 / 450 -> 1336 / 438.
- **Not done (time):** ncc_28A68 (6), o2_23914 (7), Audio_NoteInitForLayer (Note / layer:
  SequenceLayer is padding past 0x18, so the layer side needs OoT layer fields verified first),
  Audio_AllocNoteFromActive. **o2_26214 fold:** every field it uses exists in AudioContext
  (offsets asserted), but audio.h declares curAudioFrameDmaQueue as `u8[0x18]` while the donor
  needs an OSMesgQueue (MQ_GET_COUNT reads validCount): make it `OSMesgQueue`
  (libultra/os_message.h) in audio.h and check the other includers first, then replace
  gl_26214_Ctx / AudioTask / OSTask_t with AudioContext / AudioTask (field renames: t -> task,
  msgQueue -> taskQueue).

### Run 535 (agent-c): o2_26214 fold, NoteInitForLayer / AllocNoteFromActive, the non-audio post.c bodies

Four hand-edit commits on agent-c (base 4bd1f80f4), each gated PASS (3288/3288, ROM identical,
placeholder and gameflow checks 0 mismatches). After the last gate's clean build all 1278 objects
(matching and NON_MATCHING) are identical to a pre-run build by `objdump -d -r`, data sections and
relocations.
- 78a42aad8: **audio.h** includes libultra/os_message.h; `curAudioFrameDmaQueue` (0x16BC) is an
  `OSMesgQueue`. No other includer declares OSMesgQueue / OSThread / OSMesg itself, and none
  touches the member (DmaSampleData / InitMesgQueues in game_libs_post.c keep their own views).
  **game_libs_o2_26214.c** (AudioThread_UpdateImpl) now uses AudioContext / AudioTask / OSTask_t
  from audio.h (t -> task, msgQueue -> taskQueue); the five local typedefs are gone.
- 7a1de52ec: **SequenceLayer** gains note 0x2C, noteVelocity 0x40, tunedSample 0x4C and the byte-0
  bits in OoT's order. bit3 and notePropertiesNeedInit (bits 4 and 7 from the MSB) are proven by
  Audio_NoteInitForLayer; stopSomething / continuousNotes / ignoreDrumPan / bit1 are OoT's names
  only. Byte 0x02 (OoT `u8 instOrWave`) is inside the u32 bitfield container, so it stays a byte
  read. **Audio_NoteInitForLayer** matches OoT's body field for field. The local Gl28E94Desc /
  Gl28E94Xf views are replaced by SequenceLayer / NoteSampleState, which have the same u32
  containers. **Audio_AllocNoteFromActive** = OoT's (pool releasing / active,
  layer->channel->notePriority, playbackState priority / wantedParentLayer). Neither needed a
  lever.
- d9cb403a6 (the non-audio bodies, include/gdl/dma.h): **FsStream** (0x40) = gFsStream0/1/2, the
  record fs_piXfer_00065EE4 sets up (post1b keeps its local view Save65EE4, owner b). Fields:
  stage[8] (unaligned-head bounce buffer), wrPos 0x8, rdPos 0xC, handshake 0x10, committed 0x14,
  data 0x24, hdr 0x28 (the PI header address; not `base`, which is a macro in fs_bufWrite_334E8),
  end 0x2C, size 0x30, unk34. The three fs_buf* bodies use `FsStream *g`. **Lever:** the end
  tests must be spelled cursor first (`g->wrPos == g->end`). As members, end-first loads +0x2C
  before the cursor, and the cast form did the opposite. MCamera_ctor is on game/camera.h MCamera
  plus gdl/node.h Node (vptr / name / flags). sys_fatalHaltLoop is on gdl/console.h ConsoleMgr
  (input 0x34, unk38, the Node vtable slot-2 call through VT_SLOT) and gdl/pad.h PadCtl (the
  0x80 record pad_open fills: held / pressed / released).
- **Census:** game_libs_post.c 313 + 16 -> 181 + 16; game_libs segment 1258 -> 1126 raw.
  Per owner: c 1147 -> 1063, and the post.c non-audio bodies are counted under a (1182 -> 1083).
- **Not done (time):** ncc_28A68 (Audio_InitNoteFreeList, 6). It is an edg donor, and audio.h
  is not edg-safe: common.h / os_task.h / os_message.h / os_thread.h and the audio.h asserts all
  use the `&((T *)0)->f` form, so they need `#ifndef __cplusplus` guards first, as select.h
  has. o2_23914 (AudioLoad_SyncLoad, 7): the table entry is an AudioTableEntry
  (romAddr 0x10 / size 0x14 / medium 0x18 / cachePolicy 0x19 after a 0x10 header, OoT's
  AudioTable) and tbl + 2 is the header's unkMediumParam. It can take audio.h's AudioTable
  directly. Save65EE4 (post1b) can become FsStream (owner b).

### Run 539 (agent-c): C++-safe audio.h, Audio_InitNoteFreeList donor, AudioLoad_SyncLoad, layer ProcessSound fields

Commits on agent-c (base dc60769de), each gated PASS (3288/3288, ROM identical, placeholder and
gameflow checks 0 mismatches). Every build/ object, matching and NON_MATCHING, is identical to
the pre-run build by `objdump -d -r -s` (.mdebug excluded).
- c1477208b: **audio.h and libultra/os_message.h / os_thread.h / os_task.h** wrap their
  `&((T *)0)->f` offset asserts in `#ifndef __cplusplus`, so edg donors can include audio.h.
  **game_libs_ncc_28A68.cpp** (Audio_InitNoteFreeList) is on AudioContext.noteFreeLists /
  numNotes / notes and Note.listItem (u.value, prev), with CALL(Audio_InitNoteLists) /
  CALL(AudioSeq_AudioListPushBack). The byte offset `off` stays because NCC keeps the source
  operand order. **Gotcha:** edg resolves `#include "libultra/os_thread.h"` (inside
  os_message.h) only with `-I include`, so the donor's Makefile block adds
  `$(GAMELIBS_28A68_DONOR): NCC_CFLAGS += -I include`. Any other edg donor that includes
  audio.h needs the same line. **game_libs_o2_23914.c** (AudioLoad_SyncLoad) uses AudioTable,
  `&tbl->entries[a1]` and header.unkMediumParam. The member form gives the same tbl-first
  addu as the old int-sum spelling.
- d2a98a59f: **SequenceLayer** gains pan 0x05 (u8), notePan 0x06 (s8), freqScale 0x30,
  velocitySquare 0x38 and noteFreqScale 0x44. Audio_SequenceChannelProcessSound's layer loop
  is OoT's (noteFreqScale = freqScale * the channel freq, noteVelocity = velocitySquare *
  appliedVolume, notePan = (pan * (0x80 - panChannelWeight) + channel->pan) >> 7), and
  `enabled` reads as the bitfield. Kept as they were: the byte-0 bit-0 test, and the
  FW(arg0, 0x30) pan addend (the run 530 lever).
- **Census:** game_libs_post.c 181 + 16 -> 177 + 6. game_libs segment 1100 -> 1090 raw.
- **Next:** post.c's top functions by raw count (run the census `--top`). Channel byte 0x1
  (`*(u8 *)(arg0 + 1)`, the channel change bits) is still raw in ProcessSound. Save65EE4
  (post1b, owner b) can become FsStream.

### Run 544 (agent-c): ProcessSound change bits, InitSequencePlayerChannels, SetInstrument

96afed053 on agent-c (hand edit; gate PASS 3288/3288, checks 0 mismatches; game_libs_post.c.o,
matching and NON_MATCHING, identical by `objdump -d -r`, `-r` and `-s`).
- **ProcessSound:** the channel change-bits byte 0x1 is `CH_CHANGES(c)` and its tests are
  `CH_CHANGED_FREQSCALE / VOLUME / PAN` (0x80 / 0x40 / 0x20 = audio.h changesFreqScale /
  changesVolume / changesPan). The macros keep the matched spellings: the signed 1-bit lb read
  and the `<< 8 << 1` / `<< 9 << 1` word tests. The audio.h u32 bitfield reads were not tried in
  the tests (the 2026-10-15 ring levers depend on those exact forms). The pan addend
  `FW(arg0, 0x30)` became `*(int *)&CH->pan` (agent-h's lever: the same bytes, where the plain
  member swaps the addu operands).
- **AudioSeq_InitSequencePlayerChannels:** `&ctx->seqPlayers[a0]`, sequenceChannelNone and
  miscPool; the new channel's seqPlayer and layers[1..3] go through `*(int *)&member`. The
  post-increment `p + 0x40` store (the previous p's layers[0]) stays raw.
- **AudioSeq_SetInstrument:** instOrWave, instrument, `&instrument` / `&adsr` reader args.
  The flag bit is audio.h's `SequenceChannel.hasInstrument`: the u32 bitfield gives the same
  bytes as the old u8 view, so Gl2BAACFlags is gone.
- **Census:** game_libs_post.c 177 + 6 -> 163 + 0. game_libs segment 981 -> 967 raw.
- **Next:** AudioThread_GetLayerSamplesLeft (7: gAudioContext_275F4 + a0 * 0x160 is
  seqPlayers[a0]; the header notes ring levers on the operand names), cam_createDefault (8),
  then post.c `--top`.

### Run 548 (agent-c): AudioThread_GetLayerSamplesLeft, cam_createDefault

0dd4b14fb on agent-c (hand edit; gate PASS 3288/3288, checks 0 mismatches; game_libs_post.c.o,
matching and NON_MATCHING, identical by `objdump -d -r`, `-r` and `-s`).
- **AudioThread_GetLayerSamplesLeft:** `&((AudioContext *)gAudioContext_275F4)->seqPlayers[a0]`
  (the alias extern kept) -> channels[a1] -> layers[a2] -> note. It returns
  `tunedSample->sample->loop->end - note->synthesisState.samplePosInt` (0 when any link is
  disabled or null, the layer's bit3 (bit 27) is clear, or the note now plays another layer:
  `note->playbackState.parentLayer != layer`). The `word >> 31` enabled tests and the
  `flags << 3 << 1` bit-27 test keep their matched spellings. No lever needed: the typed
  player base folds 0x2D00 into the loads the same way.
- **cam_createDefault_00033228:** the new MCamera is attached with the Node child-attach idiom
  (`&NODE(lst)->children`, parent, unk04). The owner's 0x0C / 0x10 / 0x28 / 0x3C stay raw: 0x28
  takes the camera, so the owner is not a Node, and its class is still unknown (Node_def in
  post0b is its sibling).
- **Census:** game_libs_post.c 163 -> 153; game_libs segment 714 -> 704 raw.
- **Next:** port-audit `--owner c` for audio: AudioSeq_SeqChannelSetLayer (match_imports, 6),
  AudioSynth_LoadAuxBufferC / AudioLoad_RelocateFont (2 each), snd_SoundObjUpdate.

### Run 574 (agent-c): AudioSlowLoad, NoteDisable bitfields, GetLoadTable, channels[] walks

1ba066e5c on agent-c (base da8d26426; hand edit, no renames; gate PASS 3288/3288, ROM identical,
the three source checks 0 mismatches). Every build/src object is identical to the pre-run build
(`objdump -d -r` .text, `-s` .data / .rodata, `-r`, symbol names).
- **audio.h AudioSlowLoad** (0x64, OoT layout, u8 instId) and AudioContext.slowLoads[2] at 0x157C
  (asserted, with sizeof == 0x64). **AudioLoad_DmaSlowCopy** is on it: curRamAddr, msgQueue / msg,
  ioMesg, curDevAddr, medium.
- **AudioLoad_GetLoadTable** returns `AudioTable *`: sequenceTable / soundFontTable /
  sampleBankTable, NULL otherwise.
- **Audio_NoteDisable:** `sampleState.needsInit == 1` / `= 0`. enabled / finished go through a
  `volatile NoteSampleState *` view. These are the same bytes as the old volatile u8 RMWs.
- **AudioSeq_ResetSequencePlayer:** `stopScript = 0`, plus the channels[] walk.
  **SequencePlayerSetupChannels** (the K&R block) and **SequencePlayerDisableChannels** load
  channels[i] with the `*(T *)&` lever.
- **sys_fatalSwapBuffer:** `NODE(dev)->vptr`, VT_SLOT(vt, 2) / VT_SLOT(vt, 11).
- **Census / port-audit (owner c):** raw sites 128 -> 108 (game_libs_post.c 63 -> 46,
  timproc_uso_b5.c 25 + 5 -> 22 + 5). port-audit `--owner c` 10 -> 8 (A 3, B 5, C 1 -> 0,
  D 1 -> 0).
- **Left:** snd_SoundObjUpdateChannel's u32 table bases (A, load-bearing), the s32 dflt (A),
  snd_SoundObjUpdate / snd_CueQueueSet / SaveReverbSamples / RelocateFont (B). The
  gl_2495C_Rec view could fold onto AudioSlowLoad, but its member-array `addu` order is the
  matching lever.

### Run 569 (agent-c): AudioContext mesg queues / threadCmdBuf, port-audit D sites, NotePool / AdsrInit / SampleCache

fdca02565 + e4639db81 on agent-c (base 3f4755e0b; hand edits, no renames; gate PASS 3288/3288 before
each commit, ROM identical, the three source checks 0 mismatches). Every object of the full build,
matching and NON_MATCHING (1149), identical to the pre-run build by `objdump -d -r`, `-r` and `-s`
(.mdebug excluded).
- **AudioContext (audio.h)** now runs to its end: taskStartQueue / threadCmdProcQueue /
  audioResetQueue (OSMesgQueue at 0x53D0 / 0x53E8 / 0x5400), taskStartMsgBuf / audioResetMesgBuf /
  threadCmdProcMsgBuf (0x5418 / 0x541C / 0x5420), threadCmdBuf[0x100] (AudioCmd, 0x5430); size
  0x5C30 = gl_data.h's gAudioContext Bss symbol (asserted). AudioThread_InitMesgQueuesImpl is OoT's
  body on them; CheckSpecChange and the two reset-queue drains read audioResetQueueP;
  AudioThread_WaitForAudioTask reads taskStartQueueP.
- **AudioThread_QueueCmd:** threadCmdBuf / threadCmdWritePos / threadCmdReadPos through the inline
  `(AudioContext *)&D_00000000` macro. Lever: the member compare must be written
  `writePos == readPos` (the old byte-index form had them the other way round; the member form loads
  the operands in the opposite order, `bne v1,t2` vs `bne t2,v1`).
- **AudioHeap_UnapplySampleCache(SampleCacheEntry *, Sample *):** same lever: OoT's
  `sample->sampleAddr == entry->allocatedAddr` gives the target `lw 8(a0)` / `lw 4(a1)` order (the
  entry-first compare swaps the two loads once the operands are typed pointers). The medium store
  stays on the B22398 u8 bitfield view (a u32 Sample.medium store would be a word RMW).
- **Audio_NotePortamentoInit(Note *):** OoT's two statements; the Portamento struct assignment is
  the inline struct copy (base computed in the expression, no named local), same bytes.
- **Audio_InitNoteList(AudioListItem *) / Audio_InitNoteLists(NotePool *), Audio_AdsrInit(AdsrState *,
  AdsrEnvelope *, s16 *):** OoT's member stores.
- **AudioSeq_SequenceChannelEnable(SequencePlayer *, idx, u8 *script):** channels[idx],
  scriptState.depth / pc, delay; layers[] read through the shifted cursor; the enabled / finished
  byte RMWs stay raw (load-bearing byte form).
- **AudioHeap_DiscardSequence:** numSequencePlayers; CTX_SEQP(p) = the shifted seqPlayers[0]
  (enabled / seqId), stride sizeof(SequencePlayer).
- **AudioSeq_SeqLayerProcessScriptStep4 (2B09C donor):** tunedSample->sample->loop->end.
- **MCamera_hostioParms(MCamera *):** NODE(a0)->name, &a0->fov; gl_func_00000000_33338 typed
  (void *, const char *, f32 *, float, float, int). **cam_createDefault_00033228(NodeListState *):**
  the o + 0x3C holder is NodeListState.parent (obj / mnode / node stores, lst = o->parent->node).
- **Census / port-audit (owner c):** raw sites 202 -> 138 (game_libs_post.c 95 -> 63, timproc_uso_b5.c
  60 + 9 accessor -> 35 + 5). port-audit `--owner c` A 4 -> 3, B 6 -> 5, C 1, D 10 -> 1 (21 -> 10).
- **Next:** snd_SoundObjUpdateChannel tableC330 / C3B0 u32 bases (load-bearing), AudioLoad_GetLoadTable
  (0x201C.. tables), AudioLoad_DmaSlowCopy (AudioSlowLoad), AudioSeq_ResetSequencePlayer's stopScript
  byte RMW, AudioSeq_SequencePlayerDisableChannels (A: sequenceChannelNone), Audio_NoteDisable's
  0xB0 bitfield RMWs.

### Run 564 (agent-c): SequenceLayer instOrWave / portamento, SndLevelRamp, sequenceFontTable

4b447e239 + 389e48643 on agent-c (base 04a1501e8; hand edits, no renames; gate PASS 3288/3288
before each commit, ROM identical, the three source checks 0 mismatches). All 420
timproc_uso_b5 / game_libs_post / match_imports objects, matching and NON_MATCHING, identical to
the pre-run build by `objdump -d -r`, `-r` and `-s` (.mdebug excluded).
- **SequenceLayer:** the 24-bit `rest` bitfield is now `u8 unk_01; u8 instOrWave; u8 unk_03`
  (u8 members pack into the u32 bitfield container's spare bytes, as SequencePlayer.state already
  does); `Portamento portamento` at 0x20 (the struct moved above SequenceLayer). Asserts added.
- **Audio_InitSyntheticWave(Note *, SequenceLayer *):** OoT's body on members (instOrWave,
  channel->instOrWave, playbackState.harmonicIndex, sampleState.harmonicIndexCurAndPrev).
- **AudioSeq_SeqLayerProcessScriptStep1:** ObjFlags2AB34's b3 / b7 are continuousNotes /
  notePropertiesNeedInit (same u32 container, same bytes); note->playbackState.wantedParentLayer;
  portamento.mode.
- **AudioSeq_InitSequencePlayerChannels:** CHANNEL_SLOT(cursor) = the shifted
  SequencePlayer.channels[0]; typed seqPlayer / layers stores (NULL for the int 0: same bytes).
  Audio_SequencePlayerProcessSound / Audio_SequenceChannelProcessSound read their shifted cursors
  the same way (channels[0] / layers[0]).
- **SndLevelRamp (audio.h, 0x14):** game_libs Data sym1443 @0x1C0C0 (found with
  `scripts/uso-sym-oracle.py baserom.z64 0xD9FE28 <section offset>`; game_libs section offset =
  ROM - 0xDD0A6C, so splat 0x2F2AC is 0x43918): target / current / count / frac / mode, from
  snd_RampInit (now `(SndLevelRamp *, target, count)`), snd_RampTick and snd_SetLevelRampTarget.
  The match_import snd_SoundObjUpdateChannel's `D_00000000 + 4` / `+ 0x10` reads are
  `gSndLevelRamp.current` / `.mode`, a view macro over the unchanged D_00000000 sentinel (the
  native-port binding keys on the symbol, so no rename).
- **AudioLoad_GetFontsForSequence** returns `u8 *`; both reads are
  `((AudioContext *)gAudioContext_233A0)->sequenceFontTable` (the array view keeps the one
  materialised base).
- **AudioSynth_LoadAuxBufferC:** `ReverbRingBufferItem *e`. **AudioLoad_RelocateFont:** the drum
  list is read as u32 offsets; the SFX `soundOffset = (u32)(((SoundEffect *)fontData[1]) + i)`
  copy must stay (without it the function loses a register and one instruction).
- **aud_AllocSampleCacheTemporary / Persistent:** SampleCacheEntry members.
- **MCamera_doCommand:** NodeMsg.arg.payload is the command cursor; the pick is stored as
  `*(int *)&((MCamera *)o)->target = val`. MCamera_ctor: NODE(b)->name.
- **Census / port-audit (owner c):** raw sites 267 -> 202 (game_libs_post.c 127 -> 95,
  timproc_uso_b5.c 93 -> 60; BoardList_createItem's 20, owner a, -> 0). port-audit `--owner c`
  A 4, B 10 -> 7, C 7 -> 1, D 36 -> 10 (57 -> 22).
- **Next:** MCamera_hostioParms (A + B), cam_createDefault (2 D: the o + 0x3C holder), the
  snd_SoundObjUpdateChannel tableC330 / C3B0 u32 bases (load-bearing, see run 561),
  AudioThread_WaitForAudioTask (+0x53C8), Audio_NotePortamentoInit (the inline struct copy is
  the match), AudioSeq_SeqLayerProcessScriptStep4 (o2_2B09C).

### Run 561 (agent-c): LoadReverbSamples, InitTable, GetSampleBank

85b7a0491 on agent-c (hand edit; gate PASS 3288/3288, checks 0 mismatches; game_libs_post.c.o and
the match_imports objects, matching and NON_MATCHING, identical by `objdump -d -r`, `-r` and `-s`).
- **AudioSynth_LoadReverbSamples:** REVERB_AT(rec) (= synthesisReverbs[a2]) for downsampleRate,
  decayRatio (+ 0x8000) and the leakRtl / leakLtr gate. volume stays a u16 load through
  `*(u16 *)&REVERB_AT(rec)->volume`: the field is s16 (other readers use lh) and this one is lhu.
- **AudioLoad_InitTable:** OoT's (AudioTable *, romAddr, unkMediumParam) on AudioTableHeader. The walk
  keeps its cursor at the header (the matched colouring needs the +0x10 offsets), typed
  `AudioTableEntry *` with entry i read as `cursor[1]`.
- **AudioLoad_GetSampleBank:** the gl_ref_00038204(2) result is the sample-bank AudioTable:
  `entries[x].cachePolicy / medium / romAddr`. Identical bytes.
- **snd_SoundObjUpdateChannel (match_imports):** the two `(u32)&gl_2F288_tableC330 + aux * 4 +
  0x1C330` reads must keep the u32 base. As `(char *)&sym + ...` the native-port check fails
  ("native linked body changed"): the pointer sum reassociates.
- **Census / port-audit (owner c, both commits of the run):** owner c raw sites 299 -> 267 (timproc_uso_b5 segment 116 + 26 -> 109 + 16; game_libs_post.c 142 -> 127; _o2_5FC0 7 + 10 -> off the per-file list). port-audit `--owner c` A 20 -> 4, B 10, C 10 -> 7, D 36 (76 -> 57): SelectWin_display 9 -> 0, BoardItem_drawStats 4 -> 0, LevelItem_drawStats 3 -> 0, CommonInfo_init 3 -> 0.
- **Next:** Audio_InitSyntheticWave (5: layer instOrWave byte 2 / channel->instOrWave 0x24 /
  note playbackState 0x32 / 0xB6; not reached this run), InitSequencePlayerChannels (5),
  snd_SoundObjUpdateChannel's D_00000000 + 4 / + 0x10 reads (identify the snd globals),
  AudioSynth_LoadAuxBufferC / AudioLoad_RelocateFont (B 2 each), AudioSeq_SeqLayerProcessScriptStep1
  (C 2), AudioLoad_GetFontsForSequence / InitSequencePlayerChannels (D 2), MCamera_hostioParms.

### Run 554 (agent-c): SeqChannelSetLayer, SearchRegularCaches, SearchPermanentCache

a9c885c62 on agent-c (hand edit; gate PASS 3288/3288, checks 0 mismatches; game_libs_post.c.o and
the match_imports objects, matching and NON_MATCHING, identical by `objdump -d -r`, `-r` and `-s`).
- **AudioSeq_SeqChannelSetLayer** (match_imports): `LAYER = ((Gl2AD1CState *)slot)->slots50[0]`,
  with slot = the channel shifted by idx words, so it is channel->layers[idx] with the 0x50 folded
  into each lw / sw. The typed `&base->slots50[idx]` adds 0x50 once and recolours the function
  (the native-port check fails: "native linked body changed").
- **AudioHeap_SearchRegularCaches:** seqCache / fontCache / sampleBankCache on AudioContext; the
  temporary cache's nextSide and entries[0..1].id / ramAddr; the persistent walk keeps its
  12-byte cursor, read as `((AudioPersistentCache *)v1)->entries[0]`. ramAddr returns through
  `*(int *)&` (the function returns int).
- **AudioHeap_SearchPermanentCache:** permanentPool.numEntries; permanentCache[i] through the
  shifted cursor (PERM): the arguments are OoT's (tableType, id).
- **Census:** game_libs_post.c 153 -> 142; match_imports 186 -> 180 raw.
- **Next:** post.c `--top`: AudioLoad_GetSampleBank, AudioLoad_InitTable, InitSequencePlayerChannels'
  last 5, AudioSynth_LoadReverbSamples, Audio_InitSyntheticWave (5 each), MCamera_ctor /
  hostioParms; snd_SoundObjUpdateChannel (match_imports, 6).
