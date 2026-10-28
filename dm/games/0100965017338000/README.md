# Super Mario Party Jamboree (`0100965017338000`)

Update 2.3.0 (v458752), SDK 17, Bezel engine on NVN. Modules `main`,
`subsdk0` (movie decoder) and `sdk`, plus 139 collected runtime NROs.
Main build `d70ce1726c979e45ed4200e9c2b23b2a`.

## Validation and status

The gameplay results below are from the original local bring-up on
`1a93086e2d4c3ec592bd3cafe9d792f7cab4bfcd`. This contribution ports only
the remaining BEA, movie-output and indirect-base mechanisms to current
`main` (`9ac535bb4de0915ad1dc6f6ce114287ee4e28e6d`). The newer upstream
module storage, rasterizer-discard and subgroup implementations are kept.
A full shader rebuild, GPU regression and gameplay run of this port are pending;
the earlier results do not establish compatibility of this revision.

Mac bring-up on an Apple M2 with 8 GB RAM: startup, opening movie with
picture and audio, character selection and entry into a board. The user
confirmed corrected character geometry, including Toad, Boo and hair
under hats, with the static-position workaround disabled. Captured Luigi
parts used the real alternate streams 11 and 12; all 496 and 298 sampled
vertices respectively had finite, bounded positions after their producer
programs ran. The production-path GPU regression test passed 262 checks.

All 25,693 shaders compile, including the three instance-culling programs
that previously failed. Captured indirect records select instance buckets
at bases 0, 128 and 256; the driver constant must carry the record's base
rather than the command wrapper's zero placeholder. The user confirmed
corrected scenery and blue/red board-space markers with the synchronized
indirect-base implementation in the focused Mac test. The final integrated
chain rebuild also produced 25,693 OK shaders, and its Mac app passed deep/strict
signature verification. Final packaged-app gameplay and the new indirect-base
GPU regression are pending.

Full boards, every minigame, motion controls and iOS are unverified. This profile
is bring-up work, not a claim of complete compatibility; the title is not added
to the main README's playable gallery.

## What it needs

| Setting | Where | Why |
|---|---|---|
| `modules main subsdk0 sdk` | [`game.tsv`](game.tsv) | the movie module must be loaded with the game's code |
| `sys_resource 0x1000000` | `game.tsv` | the NPDM declares 16 MB of system resource; the SDK uses virtual address memory |
| `mem_reserve 0x1030000000`, `mem_alias 0x1008000000`, `mem_stack 0x10000000` | `game.tsv` | the tested main build's `nninitStartup` at +0x982840 requests `0xe00000000` (56 GiB) for StandardAllocator; reserve virtual space for it, without committing that amount of physical RAM |
| `app_pool 0xCD500000` | `game.tsv` | application-pool accounting, separate from virtual address-space reservation |
| archive source groups | `game.tsv` | labels for BNSH extraction from Bezel archives and main |

No title-specific host branches, rewriter cuts or `patches.py` are added.
`render_cond` keeps its default: enabling it did not resolve the observed
geometry defects. A temporary base-position override was only a diagnostic
and is not part of this profile or the fix.

## Running on the Mac

Pack with `scripts/build_ipa_from_nsp.py <NSP folder> --platform mac-app`
using this profile and the game's own keys. The generated app keeps saves in
`~/Library/Application Support/nxnative/0100965017338000/save`.
In its window, use WASD for the left stick, arrows for the D-pad, J for A,
K for B, Q/E for L/R and Return for +. A connected controller is also supported.
Start a local board to check the instance-driven scenery and space markers;
character selection exercises the alternate-position producers. Motion-based
modes have not been validated.

## Found on this game

General fixes, linked to their mechanisms rather than repeated here:

- [NRO tables sized from the manifest and snapshots taken on demand](../../../docs/reference/services.md#nro-tables-sized-from-the-manifest-and-snapshots-taken-on-demand): three core modules and 139 NROs exceed the previous 128-entry limit.
- [BNSH in Bezel Engine archives](../../../docs/reference/shaders.md#bnsh-in-bezel-engine-archives): version-6 archives use inline ASST records, not an array of record pointers.
- [Native-texture output consumes the decoder slot](../../../docs/reference/movies.md#native-texture-output-consumes-the-decoder-slot): copying into the client's texture also releases the output slot and resumes pending decoding.
- [Indirect draws use the record's base instance in driver constants](../../../docs/reference/rendering.md#indirect-draws-use-the-records-base-instance-in-driver-constants): propagate GPU-written per-bucket offsets to the shaders that select instance transforms.
- [Rasterizer discard preserves vertex storage writes](../../../docs/reference/rendering.md#rasterizer-discard-preserves-vertex-storage-writes): preserve the programs that produce alternate position buffers even with transform feedback inactive.
- [Subgroup operations rewritten for a one-lane subgroup](../../../docs/reference/shaders.md#subgroup-operations-rewritten-for-a-one-lane-subgroup): scalar accesses to subgroup mask components must be rewritten too.

The captured position-buffer producers include `031c6c0e475e171c_b`
(Luigi's 505- and 886-vertex parts), `6be6273b0719b37c_b`,
`0cc9619a2a12f891_b` and `b0ffebef7852f0cd_b`.

## Shader data and rebuilding

The profile contains extraction metadata and shader-pair tables. Game
files, extracted shader code, keys, compiled libraries and captures are
not included. Generate chain-specific `c1_full.tsv` and `cb_extent.tsv`
from the rebuilt Mac outputs, as for other profiles. The offline builder
emits `main0_discard` for writable vertex programs and records its entry
in reflection; runtime source compilation is not needed by this change.

The three subgroup failures were `32815c04910d6118`, `f442a85d504cb1d2`
and `2b5485a2a731a231` (BNSH in main, variants 0–2). The fix was checked
against their real SPIR-V locally, without adding those binaries to the
repository. All three compiled in the full 25,693-shader build. See the validation status
above for the subsequent driver-bank and indirect-instance findings.
