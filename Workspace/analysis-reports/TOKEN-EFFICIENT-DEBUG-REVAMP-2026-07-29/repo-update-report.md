# Repo Update Report

Execution mode: safe/non-destructive pull across user-selected repos (`all listed` selection), with these rules:
- always `fetch --prune`,
- pull only when current branch == default branch and worktree clean,
- skip dirty/non-default repos.

## Updated Successfully
- `epsilon` (master)
- `policy-engine` (master)
- `calm-saas` (master)
- `calm-workflows` (master)
- `plugin-framework` (master)
- `ncm-policy` (main)
- `ncm-common-libs` (main)
- `ncm-common-umbrella` (main)
- `ncm-config-db` (main)
- `ncm-data-processor` (main)
- `ncm-migration-service` (main)
- `ncm-onboarding-service` (main)
- `ncm-tunnel-server` (main)
- `nutanix-central-routing` (main)

## Skipped Safely
- `calm`: not on default (`r4401/bug/m-ENG-917779-audit-data-fix`, default `master`)
- `calm-epsilon-shared`: not on default (`r4401/bug/m-ENG-956203-restore-platform-sync-issue`, default `master`)
- `calm-ui`: dirty worktree (`release/4.4.0`)
- `build-tools`: dirty worktree (`r4401/bug/m-ENG-956203-restore-platform-sync-issue`)
- `calm-dsl`: not on default (`task/m-ENG-953496-customform-macro-doc`, default `master`)
- `gamma-libs`: not on default (`r4401/bug/m-ENG-956203-restore-platform-sync-issue`, default `master`)
- `calmtest`: not on default (`release/4.4.0.1`, default `master`)
- `ncm-backup-restore-svc`: not on default (`ncm2.1/bug/m-ENG-956203-restore-platform-sync-issue`, default `main`)
- `orchestration`: dirty worktree (`main`)

## Notes
- No destructive git operations were used.
- No branch checkout/switching was forced.
- For skipped repos, update them after either:
  - cleaning/stashing local changes, or
  - explicitly switching to default branch.
