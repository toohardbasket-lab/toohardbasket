#!/usr/bin/env bash
# Fetch every document the source test reads, and record how it came back.
#
# A register rebuilt weekly needs sources that answer the same way every week,
# so the test is to run this twice into two empty directories and compare the
# manifests. Anything that redirected, refused, or came back with a different
# checksum shows up in the diff.
#
#     bash fetch.sh <empty directory>
#
# Writes the files and a manifest of
# name, http code, redirects, bytes, content type, sha256, final URL, fetched at.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:?usage: fetch.sh <directory>}"
mkdir -p "$out"
: > "$out/manifest.tsv"
while IFS=$'\t' read -r name url; do
  [ -z "${name:-}" ] && continue
  read -r code redirects bytes ctype final <<<"$(curl -sS -L --max-time 300 \
    -H 'User-Agent: Mozilla/5.0' -H 'Origin: https://www.aph.gov.au' \
    -H 'Referer: https://www.aph.gov.au/' \
    -o "$out/$name" -w '%{http_code} %{num_redirects} %{size_download} %{content_type} %{url_effective}' "$url")"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$name" "$code" "$redirects" "$bytes" "$ctype" \
    "$(sha256sum "$out/$name" | cut -d' ' -f1)" "$final" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    >> "$out/manifest.tsv"
done < "$here/sources.tsv"
cut -f1,2,3,6 "$out/manifest.tsv"
