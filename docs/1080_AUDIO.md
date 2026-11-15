# 1080 audio driver (game_libs 0x1C9E4-0x2D374) and sound glue (0x2D374-0x31DF8)

Area C of the readability phase (agent-c runs 444, 446). Uncommitted area doc.

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
- 0x2D374 per-frame timer tick (six countdowns, fade to 0x1010300 / 0x4E/0x4D
  player-1 ramps) -- likely snd_UpdateTimers.
- 0x2D910 player-1 channel IO (0x06010F00) driven by two state inputs.
- 0x2DF98 0x64-byte sound-object init; 0x2E06C..0x2E24C sound-object helpers
  (flags +0x16, kind +0x21) calling 0x43BE4 (sfx start, 80.0f).
- 0x2E354 (0xE64) big per-object sound update, 0x2F1B8 f32 binary search,
  0x2F288 / 0x2F638 / 0x2F8A0 / 0x2F934 / 0x2F9D4 / 0x2FA90 / 0x2FB10 player-0
  channel IO sequences (0x06000x00 = CHANNEL_SET_IO player 0), 0x2FB74 (0x990)
  event -> sound command dispatcher, 0x30504..0x3061C more IO wrappers,
  0x307A8 / 0x308AC (C++ NCC donors) fade timer ticks, 0x30AF4 (0x840) another
  dispatcher, 0x31334 stepped cue driver, 0x3190C player-2 IO (0x0602xxxx),
  0x31A74 IO sequences on channel 0xA.
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
- Opaque (stride only): SynthesisReverb 0x158, AudioAsyncLoad 0x54. Not yet
  modelled: Note (0xD0; Audio_InitSampleState / Audio_NoteInit / NoteDisable
  give flags 0x30/0x34, priorities 0x40/0x44, parentLayer 0x44?, noteSub 0xB0)
  and NoteSampleState.
- Bitfield flag words use the u32 container the matched donors used (IDO's
  bitfield loads follow the declared container); keep it when converting.

Users: game_libs_o2_240A0.c, _2B5F4.c, _27804.c (AudioContext alias),
_2C7A4.c and _2BB7C.c (AudioContext + SequencePlayer / SequenceChannel /
SequenceLayer / SeqScriptState / AdsrSettings / Stereo aliases).

## Next

1. Note (0xD0) / NoteSampleState from Audio_InitSampleState (27804 donor),
   Audio_NoteInit, NoteDisable, ProcessNotes, AllocNote; SynthesisReverb fields
   from AudioSynth_*.
2. Convert game_libs_post.c's raw `(char *)&D_00000000 + 0xNN` audio accesses
   (e.g. 0x2D00 + i * 0x160, 0x5280, 0x5368) to audio.h fields; post.c does
   not include audio.h yet -- check its typedef names first.
3. Name the rest of 0x2D374-0x31DF8 (list above).
4. Rename-tool note: a function whose REPLACE_FUNC_BODY donor lives in
   src/match_imports/<NAME>.c is "defined in several segments"; run 446's
   wrapper (/tmp/claude-1000/c446/rn.py) tolerates exactly that case when the
   Makefile has `REPLACE_FUNC_BODY += OLD=build/src/match_imports/OLD.c.o`; the
   tool then renames the donor file, bindings, origins .ld and Makefile rules
   together (AudioSeq_SeqChannelSetLayer, AudioSeq_InitSequencePlayer).

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
