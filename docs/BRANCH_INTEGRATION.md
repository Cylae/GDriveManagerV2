# Branch integration — 2026-10-18

## Scope and history

The source snapshot contains 86 divergent branches and 86 open pull requests, all based on the existing main history. Every branch diff was inspected and compared, including normalized Python syntax comparisons to distinguish behavior changes from repeated formatting proposals.

The integration commit uses the previous main head as its first parent and every source head as an additional parent. This preserves all source commits and records deliberate conflict resolution in a single consolidated tree. No source branch is deleted and no existing history is rewritten.

## Resolution decisions

- OAuth: retain the two-lock design, guarded cache reads, a second cache check after acquiring the refresh lock, and serialized interactive authorization. Logout holds the refresh lock until persisted credentials are removed. Return the locally captured token rather than rereading mutable shared state. The single-lock alternatives and variants allowing logout to race with token persistence are superseded.
- OAuth errors: a revoked refresh grant can start sign-in. Network failures propagate. Token payloads and lifetimes are validated before cache publication. Callback state is checked before accepting a result; unrelated callbacks cannot consume the authorization server's only request.
- Retry-After: consolidate the HTTP-date variants into one parser handling seconds, UTC dates, legacy naive dates, past dates, invalid input, and the configured delay bound. Use cancellation events for waits and restore readable HTTP error bodies. Preserve structured Drive quota reason detection.
- Atomic writes: consolidate the mkstemp and O_EXCL variants into one helper. mkstemp creates an exclusive private temporary file; data is flushed and synced and the descriptor closes before os.replace. Settings, cache, Unix fallback credentials, and DPAPI credentials use the helper.
- Credentials: retain compatibility with existing credential filenames, log a generic fallback warning without credential content, read fallback files even when keyring returns no entry, and remove obsolete fallback copies after a successful keyring save. Declare DPAPI pointer types for 64-bit Windows and propagate persistence failures.
- Code quality: retain useful import ordering, modern type annotations, unused-variable cleanup, and narrower parsing exceptions. A single formatter and checked-in lint/type configuration replace competing formatting-only variants. Repetitive tests are consolidated around observable behavior rather than exact lock names or O_EXCL implementation details.
- Generated patch.diff and git_patch.diff files from proposal branches are deliberately absent from the final tree; they duplicate Git history.

## Additional correctness fixes

- Use Drive content size rather than quotaBytesUsed for download verification.
- Never overwrite an existing user file, including concurrent same-name downloads and Workspace exports. Use separate identity-based partials, validate resume offsets, handle complete partials, and stop cancellation from entering retry backoff.
- Never trash folders or Workspace exports. After confirmation, reverify the local binary and request current remote size, MD5, and trash capability before the final request.
- Reuse OAuth across operations. Snapshot Tkinter destination values on the main thread. Send prompts through the UI event queue and prevent an overlapping operation from clearing another operation's cancellation event.
- Save settings transactionally, serialize log rotation/writes, escape whitespace-prefixed CSV formulas, and invalidate memoized Drive paths on inventory refresh.

## Validation and limits

The baseline had 44 passing tests. Consolidation adds deterministic concurrency, storage failure, no-overwrite, cancellation, live-metadata, and UI worker checks. The repository defines compilation, lint, formatting, type checks (including unannotated function bodies), coverage, optional real Tkinter smoke checks, and native Windows DPAPI checks. See GitHub Actions for the final platform results.

No real Google account was authorized or modified during testing. Local GUI checks require a graphical display. Remote file metadata and trash are separate API requests; they are not an atomic transaction against another client modifying the same file.

## Source branches

| PR | Branch | Source commit | Consolidated behavior |
| --- | --- | --- | --- |
| [#28](https://github.com/Cylae/GDriveManagerV2/pull/28) | `fix-oauth-thread-safety-14924463312199944957` | `7be373e4e4f2` | OAuth concurrency; retain applicable quality fixes |
| [#29](https://github.com/Cylae/GDriveManagerV2/pull/29) | `jules-3574376871340425940-d1793a39` | `2986d67c170b` | OAuth concurrency; retain applicable quality fixes |
| [#30](https://github.com/Cylae/GDriveManagerV2/pull/30) | `oauth-thread-safety-12792288205778071329` | `96189b501e55` | OAuth concurrency; retain applicable quality fixes |
| [#31](https://github.com/Cylae/GDriveManagerV2/pull/31) | `thread-safe-oauth-refresh-12098265721496726201` | `40e7bb8e7f9a` | OAuth concurrency; retain applicable quality fixes |
| [#32](https://github.com/Cylae/GDriveManagerV2/pull/32) | `oauth-lock-13778694181441602512` | `55c1ef5c01a5` | OAuth concurrency; retain applicable quality fixes |
| [#33](https://github.com/Cylae/GDriveManagerV2/pull/33) | `fix-oauth-thread-safety-17654867503526136002` | `10306e56074b` | OAuth concurrency; retain applicable quality fixes |
| [#34](https://github.com/Cylae/GDriveManagerV2/pull/34) | `fix/oauth-thread-safety-14054625305145970221` | `53ff9cb946dd` | OAuth concurrency; retain applicable quality fixes |
| [#35](https://github.com/Cylae/GDriveManagerV2/pull/35) | `jules-16689361214774091588-9451cf55` | `14e0323658be` | OAuth concurrency; retain applicable quality fixes |
| [#36](https://github.com/Cylae/GDriveManagerV2/pull/36) | `oauth-thread-safety-10250100969147517061` | `129322c1ccce` | OAuth concurrency; retain applicable quality fixes |
| [#37](https://github.com/Cylae/GDriveManagerV2/pull/37) | `fix-oauth-thread-safety-6665343613538761061` | `5dc574325a02` | OAuth concurrency; retain applicable quality fixes |
| [#38](https://github.com/Cylae/GDriveManagerV2/pull/38) | `jules-oauth-dcl-16300374200624284514` | `8f754b6e5bba` | OAuth concurrency; retain applicable quality fixes |
| [#39](https://github.com/Cylae/GDriveManagerV2/pull/39) | `fix/oauth-thread-safety-13441244918181736579` | `c07649a9cece` | OAuth concurrency; retain applicable quality fixes |
| [#40](https://github.com/Cylae/GDriveManagerV2/pull/40) | `fix-oauth-thread-safety-13905470050784094568` | `99403dd53b99` | OAuth concurrency; retain applicable quality fixes |
| [#41](https://github.com/Cylae/GDriveManagerV2/pull/41) | `main-6337621606359944164` | `5b387145b8e6` | OAuth concurrency; retain applicable quality fixes |
| [#42](https://github.com/Cylae/GDriveManagerV2/pull/42) | `oauth-thread-safety-7825116029863123989` | `1bd604266d5f` | OAuth concurrency; retain applicable quality fixes |
| [#43](https://github.com/Cylae/GDriveManagerV2/pull/43) | `fix-oauth-thread-safety-4012310005345134880` | `ecc68dd1a085` | OAuth concurrency; retain applicable quality fixes |
| [#44](https://github.com/Cylae/GDriveManagerV2/pull/44) | `jules-7467349115283377699-97ccdf12` | `99129f30ea5b` | OAuth concurrency; retain applicable quality fixes |
| [#45](https://github.com/Cylae/GDriveManagerV2/pull/45) | `fix-oauth-thread-safety-5941215845212700977` | `007d54c14bba` | OAuth concurrency; retain applicable quality fixes |
| [#46](https://github.com/Cylae/GDriveManagerV2/pull/46) | `oauth-thread-safety-12128105538851722337` | `328beca6dcaf` | OAuth concurrency; retain applicable quality fixes |
| [#47](https://github.com/Cylae/GDriveManagerV2/pull/47) | `fix/oauth-thread-safety-14837956573130312721` | `6da82cbe80a3` | OAuth concurrency; retain applicable quality fixes |
| [#48](https://github.com/Cylae/GDriveManagerV2/pull/48) | `oauth-thread-safety-495773387258249329` | `1927aa241baf` | OAuth concurrency; retain applicable quality fixes |
| [#49](https://github.com/Cylae/GDriveManagerV2/pull/49) | `improve-retry-after-parsing-11575911946017988552` | `8c9b4398ba52` | HTTP-date retries |
| [#50](https://github.com/Cylae/GDriveManagerV2/pull/50) | `fix/oauth-thread-safety-10261780674372415926` | `db3de1779d44` | OAuth concurrency; retain applicable quality fixes |
| [#51](https://github.com/Cylae/GDriveManagerV2/pull/51) | `fix/atomic-file-writes-o-excl-17446332475636838373` | `2fb4ac5508b6` | Atomic storage / credential fallback |
| [#52](https://github.com/Cylae/GDriveManagerV2/pull/52) | `fix-oauth-thread-safety-18321154144409539761` | `09e8f505b3f4` | OAuth concurrency; retain applicable quality fixes |
| [#53](https://github.com/Cylae/GDriveManagerV2/pull/53) | `fix-oauth-thread-safety-2652138752659168240` | `d7a108855662` | OAuth concurrency; retain applicable quality fixes |
| [#54](https://github.com/Cylae/GDriveManagerV2/pull/54) | `feat/oauth-thread-safety-213200729856448044` | `cb48a1e09818` | OAuth concurrency; retain applicable quality fixes |
| [#55](https://github.com/Cylae/GDriveManagerV2/pull/55) | `fix/oauth-thread-safety-1406640692394890668` | `a14b3ab26407` | OAuth concurrency; retain applicable quality fixes |
| [#56](https://github.com/Cylae/GDriveManagerV2/pull/56) | `fix-oauth-thread-safety-5875695308902406834` | `6108e637a117` | OAuth concurrency; retain applicable quality fixes |
| [#57](https://github.com/Cylae/GDriveManagerV2/pull/57) | `oauth-thread-safety-17143201986975291840` | `47a3dd663f44` | OAuth concurrency; retain applicable quality fixes |
| [#58](https://github.com/Cylae/GDriveManagerV2/pull/58) | `jules-15837071320507064831-44abd9b8` | `8fc3ec0c20d8` | OAuth concurrency; retain applicable quality fixes |
| [#59](https://github.com/Cylae/GDriveManagerV2/pull/59) | `fix/oauth-thread-safety-13565396908999051633` | `7a0b97691f46` | OAuth concurrency; retain applicable quality fixes |
| [#60](https://github.com/Cylae/GDriveManagerV2/pull/60) | `jules-oauth-thread-safe-7087387770613662686` | `8d8b8ba80ec3` | OAuth concurrency; retain applicable quality fixes |
| [#61](https://github.com/Cylae/GDriveManagerV2/pull/61) | `thread-safe-oauth-12418207539663549488` | `574bbee5e77e` | OAuth concurrency; retain applicable quality fixes |
| [#62](https://github.com/Cylae/GDriveManagerV2/pull/62) | `fix-oauth-thread-safety-3372854085286098066` | `89a146da5210` | OAuth concurrency; retain applicable quality fixes |
| [#63](https://github.com/Cylae/GDriveManagerV2/pull/63) | `fix-oauth-thread-safety-677739072284006712` | `1b6e2f0f7737` | OAuth concurrency; retain applicable quality fixes |
| [#64](https://github.com/Cylae/GDriveManagerV2/pull/64) | `jules-3296917993811856708-06fdda36` | `905c07807069` | Atomic storage / credential fallback |
| [#65](https://github.com/Cylae/GDriveManagerV2/pull/65) | `main-2575108822767409281` | `fb44db47450f` | OAuth concurrency; retain applicable quality fixes |
| [#66](https://github.com/Cylae/GDriveManagerV2/pull/66) | `main-10516882985307432271` | `4ed27969b06b` | Atomic storage / credential fallback |
| [#67](https://github.com/Cylae/GDriveManagerV2/pull/67) | `fix/oauth-thread-safety-14445168528324717729` | `cb0bf2575b00` | OAuth concurrency; retain applicable quality fixes |
| [#68](https://github.com/Cylae/GDriveManagerV2/pull/68) | `oauth-thread-safety-15347571624739767771` | `fd436bfd0037` | OAuth concurrency; retain applicable quality fixes |
| [#69](https://github.com/Cylae/GDriveManagerV2/pull/69) | `fix/oauth-thread-safety-12870399716963811845` | `a83ec1bd660e` | OAuth concurrency; retain applicable quality fixes |
| [#70](https://github.com/Cylae/GDriveManagerV2/pull/70) | `fix-oauth-thread-safety-4073723761765260123` | `1cf9a5933ad9` | OAuth concurrency; retain applicable quality fixes |
| [#71](https://github.com/Cylae/GDriveManagerV2/pull/71) | `fix/oauth-thread-safety-10338340995728690326` | `88a70043a04d` | OAuth concurrency; retain applicable quality fixes |
| [#72](https://github.com/Cylae/GDriveManagerV2/pull/72) | `feat/retry-after-http-date-9742157961440392350` | `315fea3fa9bb` | HTTP-date retries |
| [#73](https://github.com/Cylae/GDriveManagerV2/pull/73) | `improve-retry-after-parsing-12785514622858676942` | `37362aada9ae` | HTTP-date retries |
| [#74](https://github.com/Cylae/GDriveManagerV2/pull/74) | `improve-retry-after-parsing-9179417830910012804` | `b18c8b5174f6` | HTTP-date retries |
| [#75](https://github.com/Cylae/GDriveManagerV2/pull/75) | `fix-retry-after-http-date-13187100763401187623` | `58c2844fd920` | HTTP-date retries |
| [#76](https://github.com/Cylae/GDriveManagerV2/pull/76) | `main-10147469390958973407` | `f5ad910bb649` | OAuth concurrency; retain applicable quality fixes |
| [#77](https://github.com/Cylae/GDriveManagerV2/pull/77) | `oauth-thread-safety-8665193677562047995` | `1219ed8e0cab` | OAuth concurrency; retain applicable quality fixes |
| [#78](https://github.com/Cylae/GDriveManagerV2/pull/78) | `jules-11200897009414748344-a591d6f1` | `2202acd4a39c` | OAuth concurrency; retain applicable quality fixes |
| [#79](https://github.com/Cylae/GDriveManagerV2/pull/79) | `feat/oauth-thread-safety-2602106903885286225` | `59164b2fc9ff` | OAuth concurrency; retain applicable quality fixes |
| [#80](https://github.com/Cylae/GDriveManagerV2/pull/80) | `retry-after-http-date-4326404934760379077` | `8c2906050620` | HTTP-date retries |
| [#81](https://github.com/Cylae/GDriveManagerV2/pull/81) | `jules-12936104819455708715-97cb1205` | `4e53e8dd90b0` | HTTP-date retries |
| [#82](https://github.com/Cylae/GDriveManagerV2/pull/82) | `fix-oauth-thread-safety-3783854460974308757` | `ff6aa8bb114d` | OAuth concurrency; retain applicable quality fixes |
| [#83](https://github.com/Cylae/GDriveManagerV2/pull/83) | `oauth-thread-safety-10955731041664526257` | `14ea651270cc` | OAuth concurrency; retain applicable quality fixes |
| [#84](https://github.com/Cylae/GDriveManagerV2/pull/84) | `fix/thread-safe-oauth-token-refresh-524822309876830174` | `b606593dd402` | OAuth concurrency; retain applicable quality fixes |
| [#85](https://github.com/Cylae/GDriveManagerV2/pull/85) | `fix-oauth-thread-safety-9278769750664907010` | `349fd6214ff0` | OAuth concurrency; retain applicable quality fixes |
| [#86](https://github.com/Cylae/GDriveManagerV2/pull/86) | `fix/oauth-thread-safety-174168116427388972` | `0a00e6d227ce` | OAuth concurrency; retain applicable quality fixes |
| [#87](https://github.com/Cylae/GDriveManagerV2/pull/87) | `make-oauth-thread-safe-14939236661179088919` | `65c781a2b525` | OAuth concurrency; retain applicable quality fixes |
| [#88](https://github.com/Cylae/GDriveManagerV2/pull/88) | `oauth-thread-safety-6083305546192124360` | `9a53ac32f100` | OAuth concurrency; retain applicable quality fixes |
| [#89](https://github.com/Cylae/GDriveManagerV2/pull/89) | `fix/thread-safe-oauth-refresh-11518636164546462146` | `48719827fbf4` | OAuth concurrency; retain applicable quality fixes |
| [#90](https://github.com/Cylae/GDriveManagerV2/pull/90) | `fix-ruff-linting-warnings-6833187552513233255` | `707351fc0d0e` | OAuth concurrency; retain applicable quality fixes |
| [#91](https://github.com/Cylae/GDriveManagerV2/pull/91) | `feature/thread-safe-oauth-refresh-14232793097781153628` | `2f3634e9d5e7` | OAuth concurrency; retain applicable quality fixes |
| [#92](https://github.com/Cylae/GDriveManagerV2/pull/92) | `improve-code-quality-1449504609584729849` | `f4cb05ac3fe8` | OAuth concurrency; retain applicable quality fixes |
| [#93](https://github.com/Cylae/GDriveManagerV2/pull/93) | `fix/oauth-thread-safety-11636593710149424149` | `1e05ab6d9028` | OAuth concurrency; retain applicable quality fixes |
| [#94](https://github.com/Cylae/GDriveManagerV2/pull/94) | `fix/oauth-thread-safety-7086773048545026362` | `af341f3d82c6` | OAuth concurrency; retain applicable quality fixes |
| [#95](https://github.com/Cylae/GDriveManagerV2/pull/95) | `fix-oauth-thread-safety-3205643271573254974` | `a8dc56d2470f` | OAuth concurrency; retain applicable quality fixes |
| [#96](https://github.com/Cylae/GDriveManagerV2/pull/96) | `fix-retry-after-http-date-14695750001285515604` | `4558e174dcda` | HTTP-date retries |
| [#97](https://github.com/Cylae/GDriveManagerV2/pull/97) | `main-16573345702332457417` | `55212787362d` | OAuth concurrency; retain applicable quality fixes |
| [#98](https://github.com/Cylae/GDriveManagerV2/pull/98) | `oauth-thread-safety-6296249374734175822` | `3c53483d0f7a` | OAuth concurrency; retain applicable quality fixes |
| [#99](https://github.com/Cylae/GDriveManagerV2/pull/99) | `main-2331191837934899532` | `d65993e3ca9d` | OAuth concurrency; retain applicable quality fixes |
| [#100](https://github.com/Cylae/GDriveManagerV2/pull/100) | `fix-oauth-thread-safety-14314982256235188349` | `8b6113acbc49` | OAuth concurrency; retain applicable quality fixes |
| [#101](https://github.com/Cylae/GDriveManagerV2/pull/101) | `oauth-thread-safety-7881570048548258361` | `f2f37ccabc6b` | OAuth concurrency; retain applicable quality fixes |
| [#102](https://github.com/Cylae/GDriveManagerV2/pull/102) | `jules-thread-safe-oauth-refresh-10393958890776198366` | `a092cb5161de` | OAuth concurrency; retain applicable quality fixes |
| [#103](https://github.com/Cylae/GDriveManagerV2/pull/103) | `fix-ruf059-unused-variables-11826214579834533461` | `eb3ff8138179` | Code quality and formatting |
| [#104](https://github.com/Cylae/GDriveManagerV2/pull/104) | `fix-oauth-thread-safety-640309578012211436` | `e75e7988650c` | OAuth concurrency; retain applicable quality fixes |
| [#105](https://github.com/Cylae/GDriveManagerV2/pull/105) | `jules/thread-safe-oauth-refresh-12547151891545842833` | `7600b3e394e8` | OAuth concurrency; retain applicable quality fixes |
| [#106](https://github.com/Cylae/GDriveManagerV2/pull/106) | `fix-oauth-thread-safety-1607642818145453588` | `4e281bba5b9a` | OAuth concurrency; retain applicable quality fixes |
| [#107](https://github.com/Cylae/GDriveManagerV2/pull/107) | `fix-oauth-thread-safety-12441435504512357310` | `8dc6c8d7222f` | OAuth concurrency; retain applicable quality fixes |
| [#108](https://github.com/Cylae/GDriveManagerV2/pull/108) | `fix-atomic-writes-15492729102489706728` | `514b2fc8c1a9` | Atomic storage / credential fallback |
| [#109](https://github.com/Cylae/GDriveManagerV2/pull/109) | `oauth-thread-safety-7640625089892560156` | `11a6ae9498a9` | OAuth concurrency; retain applicable quality fixes |
| [#110](https://github.com/Cylae/GDriveManagerV2/pull/110) | `fix/retry-after-http-date-4637471679245964085` | `cac7b90a28c2` | HTTP-date retries |
| [#111](https://github.com/Cylae/GDriveManagerV2/pull/111) | `jules-6218892931001648547-532b9d22` | `47853bc445fe` | OAuth concurrency; retain applicable quality fixes |
| [#112](https://github.com/Cylae/GDriveManagerV2/pull/112) | `jules-16762927828434011061-821474d1` | `0725bc952e52` | HTTP-date retries |
| [#113](https://github.com/Cylae/GDriveManagerV2/pull/113) | `jules-retry-after-http-date-13972372188352458833` | `fec511517240` | HTTP-date retries |
