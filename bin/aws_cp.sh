#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

object=$1


# Test if object exists
if aws --region "$DEST_REGION" s3 ls "s3://$DEST_BUCKET_NAME/$object" > /dev/null; then
  echo "skipping, already exists key=$object"
else
  echo "copying key=$object"
  # Object doesn't exist, copy it
  aws s3 cp --region "$DEST_REGION" --source-region "$SRC_REGION" "s3://$SRC_BUCKET_NAME/$object" "s3://$DEST_BUCKET_NAME/$object"
fi
