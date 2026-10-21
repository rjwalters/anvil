# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide triage agent.

---

## Archives

- [2026-08](work_log/WORK_LOG_2026-08.md)
- [2026-07](work_log/WORK_LOG_2026-07.md)
- [2026-06](work_log/WORK_LOG_2026-06.md)
- [2026-05](work_log/WORK_LOG_2026-05.md)

### 2026-10-21

- **PR #1394**: Bump Repo Skills 0.24.3 -> 0.24.7

### 2026-10-20

- **PR #1390**: fix: carry real skill description in Codex registration shims
- **Issue #1389** (closed): Preserve skill purpose descriptions in generated Codex registrations

### 2026-10-16

- **PR #1378**: feat(slides): honor BRIEF editorial_overrides in review and vision critics
- **Issue #1373** (closed): slides: BRIEF editorial_overrides so critics report operator-overridden findings as info instead of re-flagging
- **PR #1375**: feat(slides): add --polish/--reject paths to slides-revise
- **Issue #1369** (closed): slides-revise: port memo's operator-directed paths (`--polish` / `--reject`) and record operator overrides so critics stop re-flagging them
- **PR #1386**: Bump Repo Skills 0.24.1 -> 0.24.3

### 2026-10-15

- **PR #1382**: test(slides): add poppler-gated real-binary test for slides-import
- **PR #1379**: feat(slides): add slides-import for externally-authored PDF decks
- **PR #1377**: feat(slides): add rehearse script mode and cap D8 without timing evidence
- **PR #1376**: fix(vision): add score anchors, palette consistency fallback, agent-as-VLM mode
- **PR #1374**: fix(slides): separate on-slide disclosure from provenance and add talk_genre
- **PR #1366**: Bump Repo Skills 0.21.6 -> 0.24.1
- **Issue #1372** (closed): Vision critic without an API key: agent-as-VLM works but drifts, and palette_adherence assumes the anvil theme
- **Issue #1371** (closed): Time-budget realism (D8) is scored inconsistently without a rehearsal, and rehearse can't time script-style notes
- **Issue #1370** (closed): Critics over-apply disclosure and hedging; slides rubric assumes a technical lecture
- **Issue #1368** (closed): slides: no import path for a deck authored outside anvil (PDF / Keynote / code-built)

### 2026-10-13

- **PR #1363**: Remove Renovate config: Dependabot takes over
- **PR #1364**: chore(deps): update pydantic requirement from >=2.13.4 to >=2.13.5
- **PR #1362**: Dependabot: render dependabot.yml from the org policy

### 2026-10-09

- **PR #1357**: fix(deps): update dependency weasyprint to >=60.2 [security]

### 2026-10-08

- **PR #1319**: Adopt Renovate dependency security policy (14-day quarantine)
- **PR #1352**: fix: split sentences after terminator plus closing quote in rhetoric_lint
- **Issue #1348** (closed): rhetoric_lint: sentence splitter inflates long-sentence density
- **PR #1351**: feat(essay): define one canonical word-count method for the length envelope
- **Issue #1349** (closed): essay: define one canonical word-count method for the length envelope

### 2026-09-30

- **PR #1343**: fix: raise consumer pyproject setuptools floor to match source (>=84.0.0)
- **Issue #1333** (closed): installer consumer pyproject still requires setuptools>=68 while the source requires >=84
- **PR #1342**: fix(audience_check): drop bare "via" from the dependency vocabulary
- **Issue #1341** (closed): audience_check: dependency vocabulary suppresses ordinary "available via <link>" phrasings
- **Issue #1339** (closed): loom-daemon pr-queue subcommand missing from installed binary — blocks Judge/Doctor/Champion PR discovery
- **PR #1340**: fix(audience_check): stop offering a dependency link as the candidate repo
- **Issue #1329** (closed): audience_check: a dependency link inside the availability section is offered as the candidate repo URL
- **PR #1338**: fix: load longtable/array/calc before caption in anvil-paper.cls
- **Issue #1328** (closed): anvil-paper.cls loads caption before longtable; pandoc longtables fail with "No counter 'none' defined"
- **PR #1337**: fix: convert a corrupt _review.json into a parse_error finding (#1335)
- **Issue #1335** (closed): check_review_dir's documented no-crash contract does not cover a corrupt _review.json (JSONDecodeError / AttributeError)
- **PR #1336**: fix: add points:1/2/3/5/8/13 labels to the repo's label set
- **Issue #1331** (closed): Points-estimate labels (points:1/2/3/5/8/13) don't exist in this repo's label set
- **PR #1334**: fix(lib): stop warning on paper-review's canonical prose + _review.json co-write
- **Issue #1327** (closed): paper-review writes both _review.json and legacy prose files, so load_review warns on its own canonical output
- **PR #1330**: chore(deps): raise pydantic, pyyaml and numpy floors through to the consumer pyproject
- **PR #1194**: chore(deps-dev): update setuptools requirement from >=68 to >=84.0.0
- **PR #1196**: chore(deps-dev): update pytest requirement from >=7.4 to >=9.1.1
- **PR #1191**: chore(deps): bump actions/checkout from 4 to 7 in the github-actions group across 1 directory

### 2026-09-29

- **Issue #1322** (closed): paper-review: audience-irrelevant governance notes and private/relative artifact pointers pass all critics; no operator revise path after READY
- **PR #1325**: feat(paper): audience-fit pre-flight, artifact link hygiene, and post-READY operator feedback
- **Issue #1320** (closed): install.sh records the new version while skipping consumer-modified skill files
- **PR #1324**: fix: surface per-skill install staleness at the two "am I current" read sites (#1320)

### 2026-09-28

- **Issue #1321** (closed): slide-content-overflow measures full-width even on bg right/left slides
- **PR #1323**: fix: slide-content-overflow measures bg right/left slides by actual text-column width

### 2026-09-16

- **Issue #1270** (closed, not planned): loom-worker-1: peer-coordination DEGRADED flapping ~21x/21h, stuck at 0/3 recovery (checkout 60 commits stale + RAM-throttled-dispatch correlation)
- **Issue #1318** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-15

- **Issue #1198** (closed): essay-review: cross-version claim ledger so review passes batch inherited-text checks instead of trickling them
- **PR #1317**: feat(essay): implement cross-version claim ledger for review/revise (#1198)
- **PR #1316**: docs(essay): resolve claim-ledger design questions for #1198 (decision record)
- **Issue #888** (closed): review loop has no lookahead and no cross-version claim ledger — each round's fix creates the next round's defect

### 2026-09-14

- **Issue #1315** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1314** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-13

- **Issue #1313** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1312** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1311** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-12

- **Issue #1310** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1309** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1308** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-11

- **Issue #1307** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1306** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-07

- **Issue #1304** (closed): Champion digest-issue lookup orphans pre-#7020 digest issues without the marker
- **PR #1305**: fix(champion): add digest-issue lookup fallback for pre-marker digests
- **Issue #1211** (closed, not planned): Champion: Merge-Risk Hold Digest

### 2026-09-05

- **Issue #1303** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1302** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1301** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1300** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1299** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1298** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1297** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1296** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1295** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1294** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1293** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-04

- **Issue #1292** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1291** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1290** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1289** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1288** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1287** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1286** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1285** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1284** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1283** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1282** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1281** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1280** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1279** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-03

- **Issue #1278** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1277** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1276** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1275** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1274** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1273** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1272** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1271** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1269** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1268** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-02

- **Issue #1267** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1266** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1265** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1264** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1263** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1262** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1261** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1260** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1259** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1258** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1257** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1256** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1254** (closed): loom-daemon-watchdog.sh's peer-coordination DEGRADED issue template may assert stale FROZEN reclamation behavior
- **Issue #1255** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1253** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1252** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1251** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1250** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1249** (closed, not planned): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1248** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1247** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-09-01

- **Issue #1246** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1245** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1244** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1243** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1242** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1241** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1240** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1239** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1238** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1237** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1236** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-08-29

- **Issue #1235** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1234** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1233** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-08-28

- **Issue #1232** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1231** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1230** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1229** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1228** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1227** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1226** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1225** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1223** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1222** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1221** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1220** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1219** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-08-27

- **Issue #1218** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1217** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-08-25

- **PR #1187**: fixtures + docs: synthetic disclaimer on the memo fixture, neutral memoir slug, neutralized render-gate fixture
- **Issue #1216** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1215** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-08-24

- **Issue #1214** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1213** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1212** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1210** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1205** (closed): project-book: support a title-relocation hook for docmute-based master documents
- **PR #1209**: feat(project-book): add relocate_title flag for docmute-based masters
- **Issue #1204** (closed): provenance_anchor: only the first range of a multi-range Line range cell is used as the drift hint — correct anchors self-report DRIFTED
- **PR #1208**: fix: consult every range in a multi-range provenance Line range hint (#1204)
- **Issue #1207** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1206** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1203** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)
- **Issue #1202** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-08-23

- **Issue #1201** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-08-22

- **Issue #1200** (closed): peer-claim coordination is DEGRADED on ip-172-31-74-176 (#6157 Layer 3)

### 2026-06-15 (epic close)

- **Epic #575 (tunable & private voice grounding) — epic-close pass**: all four child issues are merged and closed; this PR closes the coordination anchor itself with a single-line WORK_LOG entry and the `Closes #575` syntax on the PR. No code or doc changes beyond this entry — the epic's substance shipped across PRs #580 (closes #576, starter `STYLE_GUIDE.md` / `VOCABULARY.md` templates + idempotent scaffolder under `anvil/templates/voice/`), #581 (closes #577, the load-bearing new feature — `.gitignored` private voice grounding as a designed/protected posture: documented locus, auto-gitignore on scaffold, git-sync hook exclusion, committed-base + private-overlay layering), #582 (closes #578, de-personalized `VALUES.md` schema template + report dim-8 voice calibration broadening voice-grounding consumers beyond essay/memo), and #584 (closes #579, the `vocab` precision-vocabulary reminder tool wired to the essay drafter as a *reminder*, not an injector). The curator deliberately declined to promote this issue to `loom:curated` (per the issue comment: "Promoting this issue to `loom:curated` would mislead the Builder into attempting a multi-PR scope in a single pass"); the operator force-promoted it to `loom:issue` for the epic-close pass once #584 landed. Out-of-scope follow-ons sketched in the epic body (rhetoric-lint reopening, judgment-side `voice:` contract redefinition) remain out of scope and are NOT addressed here. Two structural wins shipped under the epic worth flagging for future canary signal: (1) the privacy posture (private grounding documented + scaffolded + protected from auto-commit, not merely "happens to work because the filesystem doesn't care about .gitignore"), and (2) the schema-not-content discipline (`VALUES.md` ships as instructive placeholders + shape, never one author's actual beliefs — the de-personalization is the load-bearing example for future personal-stance-shaped grounding docs).
  - **Touched**: MODIFIED this `WORK_LOG.md` entry. Zero `anvil/` changes, zero schema changes, zero new tests (epic-close-only PR; the substance shipped under #580/#581/#582/#584).

### Earlier (skills v0 implementation phase)

- **PR #20** → closed #4: implement `anvil:ip-uspto` skill
- **PR #19** → closed #6: implement `anvil:deck` skill (Marp)
- **PR #18** → closed #7: implement `anvil:slides` skill (Marp)
- **PR #17** → closed #8: implement `anvil:report` skill
- **PR #16** → closed #5: implement `anvil:pub` skill
- **PR #15** → closed #11: implement `scripts/install-anvil.sh`
- **PR #13** → closed #3: implement `anvil:memo` skill
- Initial commit + scaffolding

---

## Maintenance notes

- **PR #40 (canary-introduced regression)**: this PR shipped #32's inline-mermaid-as-default design. The studio canary's 12-deck render wave (resolved #65/#72) proved the claim false — inline mermaid leaks as raw code in the rendered PDF; `mmdc → PNG` is the only working diagram path. Both smoke tests at the time only checked "non-empty PDF + exit 0", which is why it slipped through review. Lesson recorded in #70: *"renders to a non-empty PDF" ≠ "renders correctly"*.
- **Decomposition pattern**: Three umbrellas were decomposed during this period (#21 → 9 issues; #51 → 2; #100 → 2). Decomposition is preferred over bundled umbrellas when items have different risk profiles or touch independent files.
- **Curator-skip pattern**: For one-line / mechanically-checkable fixes, we skipped the curator phase and built directly from the issue body (#77, #82, #87, #88). Same for direct-verify in lieu of a judge agent (#77, #87, #97, #98, #103). Reserve agent dispatch for substantive code review.
- **#105 introduced Anvil's first `pyproject.toml`**. The deps philosophy is documented in its top comment: subprocess-only by default; Python deps are optional extras with preflight + remediation.
