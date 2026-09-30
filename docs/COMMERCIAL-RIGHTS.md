# Commercial-rights enforcement

`LICENSE` reserves every money-making use of this code **exclusively to
Pravesh Kumar**. A license file cannot physically stop copying, so this page
is the automated backstop: what runs on its own, and the one-click steps for
what legally needs a human.

## What is automatic

1. **License guard (CI + local tests).** `scripts/check_license.py` runs as
   the `license` job in `.github/workflows/ci.yml` and as
   `backend/tests/test_license_guard.py` in the normal suite. It fails the
   build if `LICENSE` goes missing, loses the exclusivity grant to Pravesh
   Kumar, or is swapped for a permissive license (MIT/Apache/GPL) — whoever
   makes that change, including the repo owner. Check locally any time:

   ```sh
   python scripts/check_license.py
   ```

2. **Fork watch (scheduled).** The `forks` workflow lists every public fork
   once a week and files a tracking issue if a *new* fork appears, so
   nothing commercial can quietly grow unnoticed. Reviewing that issue is a
   2-minute human job: open the fork, check for ads, paywalls, paid tiers,
   or resale of the code.

## What needs Pravesh Kumar (cannot be automated)

Only the exclusive rights holder can file a takedown — GitHub requires a
legal attestation under penalty of perjury, which no bot can sign. When a
fork is being monetised:

1. Collect evidence: fork URL, screenshots of the ads/paywall/pricing, and
   a link to this repo's `LICENSE`.
2. File GitHub's DMCA form at <https://github.com/contact/dmca> (choose
   "copyright infringement", reporter = Pravesh Kumar, work = this
   repository, infringing material = the fork URL).
3. Suggested statement of authority: *"I, Pravesh Kumar, am the exclusive
   holder of all commercial rights to the GramShiksha software under its
   LICENSE. The fork at <URL> uses that software commercially without my
   written permission."*
4. Keep the submission receipt; GitHub normally disables the fork within
   days, and repeat infringers lose their accounts.

No fork, deploy, or derivative may be used commercially without prior
written permission from Pravesh Kumar — permission, when granted, should be
recorded here with date and scope.
