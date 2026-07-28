#!/usr/bin/env bash
set -euo pipefail

echo "StarX production content is S3-compatible object storage; this local upload backup is retired." >&2
echo "Verify provider versioning/replication and the documented object-store recovery policy instead." >&2
exit 2
