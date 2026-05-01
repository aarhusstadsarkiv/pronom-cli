# pronom_cli

Search the PRONOM database locally from the command line.

## Requirements

- Python 3.13+

## Installation

```bash
uv tool install git+https://github.com/aarhusstadsarkiv/pronom-cli.git
```

This installs the `pronom` CLI command.

## Usage

```bash
pronom [OPTIONS] <query>
pronom update
```

### Query types (auto-detected)

- **PUID**: `fmt/128`, `x-fmt/111`, `aca-fmt/100`
- **Extension**: `.pdf`, `.docx`, `.wav`

### Options

- `--detailed` — include extended metadata and byte sequence output.
- `--update-cache` — updates saved cache
- `--filter FILTERS` — filter out sources, when retrieving data
- `--limit LIMIT` — limit the output, when searching with extensions

## Examples

```bash
# Lookup by PUID
pronom fmt/18

# Lookup by extension
pronom .pdf

# Lookup by extension with a filter
pronom --filter fileinfo,fileformats .pdf

# Show full metadata
pronom --detailed fmt/18

# Limit the output
pronom --detailed --limit 10 .pdf

# Update local PRONOM data from release notes
pronom update
```

## How updates work

- `pronom update` checks PRONOM release notes.
- New or changed formats are fetched and stored in the local repository.
- Progress is checkpointed so interrupted updates can continue from the last processed release.