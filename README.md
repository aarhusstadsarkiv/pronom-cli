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

- **Identifier**: `fmt/128`, `x-fmt/111`, `aca-fmt/100`, `fileproinfo/1`, `filext/...`
- **Extension**: `.pdf`, `.docx`, `.wav`

### Options

- `--verbose` — include extended metadata and byte sequence output.
- `--update` - refreshes expired formats and searches and fetches new pronom releases, if any.
- `--filter FILTERS` — filter out sources, when retrieving data
- `--limit LIMIT` — limit the output, when searching with extensions

## Examples

```bash
# Lookup by identifier
pronom fmt/18
pronom aca-fmt/1

# Once an extension-only source has been identified
# you can access it via our custom identifier
pronom fileproinfo/1

# Lookup by extension
pronom .pdf

# Lookup by extension with a filter
pronom --filter fileinfo,fileformats .pdf

# Show full metadata
pronom --verbose fmt/18

# Limit the output
pronom --verbose --limit 10 .pdf

# Refresh expired formats and searches and fetches new PRONOM releases, if any.
pronom --update
```