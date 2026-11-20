# Release pipeline

The distribution zip is built **only from pinned sources** — nothing
sensitive is committed to this (public) repo, and a release is
reproducible byte-for-byte from what CI checks out.

## The zip

`packaging/build_release.py` assembles one standard add-on zip,
`jka-anim-tools-<version>.zip`, installable via **Install from Disk…**:

```
jka-anim-tools-<version>.zip
  README-install.md        ← generated: install steps + the exact source stamps
  jka_anim_tools/          ← the add-on package at the ZIP ROOT
    lib/animkit/           ← the format library (MIT, pure stdlib), bundled
```

Self-checks (build fails on any): the zip must contain the README + the
`jka_anim_tools/` package (with `lib/animkit`), and it must contain
**no `jediacademy` file** (asserted by name scan — review item #1).

## Pinned sources

| Source | Pin | How CI gets it |
|--------|-----|----------------|
| `Jrbesse/jka-animator` | the pushed ref (main or the tag) | `actions/checkout` |
| `Jrbesse/jka-animkit` (private) | the full SHA in **`packaging/animkit.lock`** | a **read-only deploy key** (repo secret `JKA_ANIMKIT_DEPLOY_KEY`, base64 single line) applied over ssh; `git fetch --depth 1 origin <sha>` |

The `jediacademy` (mrwonko) add-on is a **user-side dependency, not a
CI input**: CI never fetches or bundles it (its own license — review
item #1). Users install it separately from
`mrwonko/Blender-Jedi-Academy-Tools` at tag **`v2.1.0`**; the
README-install, the panel's error message and the repo README all point
there.

**Bumping the animkit pin:** change `packaging/animkit.lock` to the new
full SHA, **then** run the unit tests + a local release build at that SHA
before cutting any tag. The lock, not `main`, is what releases ship.

**Why the deploy key:** the default `GITHUB_TOKEN` on a public repo
**cannot read other private repos** (empirically: "Repository not found")
— so the private source is read with a read-only deploy key registered on
`Jrbesse/jka-animkit`. The key material lives only in the repo secret;
local key material used during setup was deleted.

## The three workflows (`.github/workflows/`)

- **`build.yml`** (reusable, `workflow_call`): input `version`; secret
  `JKA_ANIMKIT_DEPLOY_KEY` (declared in `on.workflow_call.secrets`);
  output `zip_path`. Steps: read the lock → write + validate the deploy
  key → checkout the pinned animkit → **unit tests**
  (`python -m unittest -v tests.test_anims tests.test_checkop
  tests.test_fingers` with `JKA_ANIMKIT_DIR=vendor/jka-animkit`, then
  `python tests/test_paths.py` — that one is a standalone script, not a
  unittest module) → `build_release.py --version <v> --animkit-src
  vendor/jka-animkit --out /tmp/dist` → upload the zip as an artifact
  `jka-anim-tools-<v>`. (No jediacademy step — see "Pinned sources".)
- **`ci.yml`**: push to `main` + manual dispatch → calls build with
  `version: ci`; the zip stays a workflow artifact for inspection.
- **`release.yml`**: push of a tag `v*` (version = tag minus `v`) or
  manual with a `version` input → calls build → publishes a GitHub
  Release (`softprops/action-gh-release`) with the zip attached.

**Reusable-workflow contract (both halves):** the caller must map the
secret (`secrets:` on the `uses:` job) **and** the called workflow must
declare it (`on.workflow_call.secrets`) — missing either gives empty
expansion or a startup failure. Permissions work the same way: the nested
job's `permissions:` can't exceed what the caller's `uses:` job requests.

## Tag convention

`vX.Y.Z`, cut at the commit you want to ship:

```
git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z
```

- The tag's commit is the release; CI builds exactly that tree + the
  pinned sources.
- **Before a release has ever been published**, you may re-point the tag
  to a green commit if the pipeline was broken (nothing is orphaned).
- **Never move a tag that already has a published release.**
- **Verify every cut:** download the release asset and byte-compare with a
  local build at the same commit (the zip is deterministic; only the
  README's commit-stamp line may differ between local and CI builds).

## Local flows

**Dev build** (uses the local dev animkit clone):

```
cd ~/work/jka-animator && python3 packaging/build_release.py --version X.Y.Z
```

**CI-equivalent local build** (fresh pinned clone — the verification
recipe): clone `Jrbesse/jka-animkit` (full clone, then
`git checkout <lock sha>` — GitHub won't shallow-fetch a bare SHA), then

```
python3 packaging/build_release.py --version X.Y.Z \
  --animkit-src <animkit-clone> \
  --out /tmp/dist
```

Then run the shipped-zip register smoke
([testing.md](testing.md#the-registered-zip-smoke)) on the extracted zip
before shipping.
