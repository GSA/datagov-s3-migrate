#!/bin/bash
# This assumes the source bucket is public and avoids us calling ListObjectsV2 on the source bucket.

set -o errexit
set -o pipefail
set -o nounset

concurrency=4

optstring=":c:s:d:p:"
while getopts ${optstring} option; do
  case "${option}" in
    c)
      concurrency="${OPTARG:-}"
      ;;
    d)
      dest_service="${OPTARG:-}"
      ;;
    p)
      src_prefix="${OPTARG:-}"
      ;;
    s)
      src_service="${OPTARG:-}"
      ;;
    :)
      echo "Option -${OPTARG:-} requires an argument"
      echo
      usage
      exit 1
      ;;
    ?)
      echo "Invalid option: -${OPTARG:-}"
      echo
      usage
      exit 1
      ;;
  esac
done
shift $((OPTIND-1))

function fail () {
  echo error: "$@" >&2
  exit 2
}

# TODO what to do with prefix?
if [[ -n "${src_prefix:-}" ]]; then
  SRC_PREFIX="$src_prefix"
fi

if [[ -n "${src_service:-}" ]]; then
  SRC_BUCKET_NAME="$(jq -r -e ".[\"s3\"][] | select(name==$src_service).credentials.bucket")"
  SRC_REGION="$(jq -r -e ".[\"s3\"][] | select(name==$src_service).credentials.region")"
fi

if [[ -n "${dest_service:-}" ]]; then
  DEST_BUCKET_NAME="$(jq -r -e ".[\"s3\"][] | select(name==$dest_service).credentials.bucket")"
  DEST_ACCESS_KEY_ID="$(jq -r -e ".[\"s3\"][] | select(name==$dest_service).credentials.access_key_id")"
  DEST_SECRET_ACCESS_KEY="$(jq -r -e ".[\"s3\"][] | select(name==$dest_service).credentials.secret_access_key")"
  DEST_REGION="$(jq -r -e ".[\"s3\"][] | select(name==$dest_service).credentials.region")"
fi

[[ -z "$SRC_BUCKET_NAME" ]] && fail SRC_BUCKET_NAME not set
[[ -z "$SRC_REGION" ]] && fail SRC_REGION not set
[[ -z "$DEST_BUCKET_NAME" ]] && fail DEST_BUCKET_NAME not set
[[ -z "$DEST_ACCESS_KEY_ID" ]] && fail DEST_ACCESS_KEY_ID not set
[[ -z "$DEST_SECRET_ACCESS_KEY" ]] && fail DEST_SECRET_ACCESS_KEY not set
[[ -z "$DEST_REGION" ]] && fail DEST_REGION not set



# Input comes from `aws s3 ls --recursive s3://bucket/`
# This assumes your source bucket is public.
# input looks like this
# 2021-12-10 12:16:25      18066 datagov/wordpress/ansible.cfg
awk '{print $4}' |
  AWS_ACCESS_KEY_ID="$DEST_ACCESS_KEY_ID" \
  AWS_SECRET_ACCESS_KEY="$DEST_SECRET_ACCESS_KEY" \
  xargs -n 1 -P "$concurrency" bin/aws_cp.sh
