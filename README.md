# Uyuni Saltboot and Retail

Development repository for Uyuni Saltboot related and retail tools.

## Uyuni Saltboot

Saltboot is salt based image deployment mechanism integrated with [Uyuni](https://www.uyuni-project.org/).


## Uyuni Retail

Retail images integrating saltboot deployment and related support formulas.

## Releasing

Release packages are built to `packages/` directory (git ignored).

Release packages are built from `origin/master` to ensure clean, reproducible artifacts.
Local uncommitted changes are never included.

Once release packages are built, they need to be submitted to the [retail project](https://build.opensuse.org/project/show/systemsmanagement:Uyuni:Retail).
From retail project, create submit requests to various target projects.

### Requirements

- `bash`
- `git` with access to `origin`

### Usage

```bash
# Build all packages
make all

# Build single package
make branch-network-formula

# Run version consistency checks (spec version vs changelog)
make test

# Clean build artifacts
make clean
```

Individual packages can also be built directly:

```bash
./build.sh saltboot-formula
```

### How it works

`make` delegates to `build.sh`. Before packaging or testing, `build.sh` fetches
`origin` and creates a temporary git worktree at `origin/master`. The operation
runs inside that worktree. For build targets, resulting `packages/` artifacts are
copied back to the repo root. The worktree is removed on exit.

## Related projects

- [SUSE salt formulas](https://github.com/SUSE/salt-formulas)
- [OS Image templates](https://github.com/SUSE/manager-build-profiles/tree/master/OSImage)

