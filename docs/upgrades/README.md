# Upgrade Guides

Version-specific guides for upgrading the AE Toolkit itself and projects scaffolded by it.

## Toolkit upgrades

| From    | To      | Guide                                                  |
| ------- | ------- | ------------------------------------------------------ |
| v1.20.0 | v1.21.0 | [v1.20.0-to-v1.21.0.md](./v1.20.0-to-v1.21.0.md)       |
| v1.5.0  | v1.6.0  | [v1.5.0-to-v1.6.0.md](./v1.5.0-to-v1.6.0.md)           |
| v0.9.0  | v0.9.1  | [0.9.0-to-0.9.1.md](./0.9.0-to-0.9.1.md)               |

For routine updates between releases, run `aet update` (see [Updating](../../README.md#updating)).

## Project upgrades

For upgrading an existing project that uses AE Toolkit skills, see [reference/queue/upgrading-existing-project.md](../reference/queue/upgrading-existing-project.md).

To re-run the setup scaffold on a project, invoke `/aet-setup` from your agent. It will audit the current state and propose only the changes needed to bring the project up to date.
