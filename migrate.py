import argparse
import logging
import os
import sys

import boto3
import botocore.exceptions

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
log = logging.getLogger('s3migrate')

def clear_bucket(client, bucket_name):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket_name, client=client)
    bucket.object_versions.delete()
    bucket.objects.delete()

def key_exists(s3, bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            return False
        else:
            raise e

    return True

def list_objects(s3, bucket, prefix):
    kwargs = {
        'Bucket': bucket,
        'Prefix': prefix,
    }
    while True:
        response = s3.list_objects_v2(**kwargs)
        log.debug(f'list_objects_v2 response={response}')

        if 'Contents' not in response:
            break

        for obj in response['Contents']:
            yield obj

        # set the pagination token
        try:
            kwargs['ContinuationToken'] = response['NextContinuationToken']
        except KeyError:
            break



def main():
    parser = argparse.ArgumentParser(description='S3 migration utility.')
    parser.add_argument('--use-ec2', action='store_true', help='Read source credentials from EC2 metadata.')
    parser.add_argument('--clear', action='store_true', help='Clear the destination bucket before copying objects.')
    parser.add_argument('--debug', action='store_true', help='Use debug logging.')
    args = parser.parse_args()


    log.setLevel(logging.INFO)
    if args.debug:
        log.setLevel(logging.DEBUG)

    src_bucket = os.getenv('SRC_BUCKET_NAME')
    src_prefix = os.getenv('SRC_PREFIX')
    src_region = os.getenv('SRC_REGION')

    if args.use_ec2:
        src_s3 = boto3.client('s3')
    else:
        src_access_key_id = os.getenv('SRC_ACCESS_KEY_ID')
        src_secret_access_key = os.getenv('SRC_SECRET_ACCESS_KEY')

        src_s3 = boto3.client('s3',
            region_name=src_region,
            aws_access_key_id=src_access_key_id,
            aws_secret_access_key=src_secret_access_key,
        )

    dest_bucket = os.getenv('DEST_BUCKET_NAME')
    dest_access_key_id = os.getenv('DEST_ACCESS_KEY_ID')
    dest_secret_access_key = os.getenv('DEST_SECRET_ACCESS_KEY')
    dest_region = os.getenv('DEST_REGION')

    dest_s3 = boto3.client('s3',
        region_name=dest_region,
        aws_access_key_id=dest_access_key_id,
        aws_secret_access_key=dest_secret_access_key,
    )

    if args.clear:
        # clear destination
        log.info(f'clearing destination bucket={dest_bucket}')
        clear_bucket(dest_s3, dest_bucket)

    # iterate over each object
    for obj in list_objects(src_s3, src_bucket, src_prefix):
        key = obj.get('Key')
        if key_exists(dest_s3, dest_bucket, key):
            log.debug(f'skipping key={key} already exists on destination')
            continue

        log.info(f'copying key={key}')
        reader, writer = os.pipe()
        src_s3.download_fileobj(src_bucket, key, os.fdopen(writer, 'wb'))
        dest_s3.upload_fileobj(os.fdopen(reader, 'rb'), dest_bucket, key)

if __name__ == '__main__':
    main()
