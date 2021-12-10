import argparse
import asyncio
import logging
import os
import sys
import tempfile

import boto3
import botocore.exceptions
from vcap_services import load_from_vcap_services

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


async def main():
    parser = argparse.ArgumentParser(description='S3 migration utility.')
    parser.add_argument('--use-ec2', action='store_true', help='Read source credentials from EC2 metadata.')
    parser.add_argument('--src-service-name', action='store', help='Name of the cloud.gov s3 service to copy from.')
    parser.add_argument('--dest-service-name', action='store', help='Name of the cloud.gov s3 service to copy to.')
    parser.add_argument('--clear', action='store_true', help='Clear the destination bucket before copying objects.')
    parser.add_argument('--concurrency', type=int, default=4, help='Number of copy workers to run concurrently.')
    parser.add_argument('--debug', action='store_true', help='Use debug logging.')
    parser.add_argument('--prefix', action='store', default='', help='Source S3 prefix to use.')
    args = parser.parse_args()


    log.setLevel(logging.INFO)
    if args.debug:
        log.setLevel(logging.DEBUG)

    if args.src_service_name:
        src_service = load_from_vcap_services('s3', None, args.src_service_name)
        src_access_key_id = src_service.get('access_key_id')
        src_secret_access_key = src_service.get('secret_access_key')
        src_bucket = src_service.get('bucket')
        src_prefix = args.prefix
        src_region = src_service.get('region')
    else:
        src_access_key_id = os.getenv('SRC_ACCESS_KEY_ID')
        src_secret_access_key = os.getenv('SRC_SECRET_ACCESS_KEY')
        src_bucket = os.getenv('SRC_BUCKET_NAME')
        src_prefix = args.prefix or os.getenv('SRC_PREFIX')
        src_region = os.getenv('SRC_REGION')

    if args.use_ec2:
        src_s3 = boto3.client('s3')
    else:
        src_s3 = boto3.client('s3',
            region_name=src_region,
            aws_access_key_id=src_access_key_id,
            aws_secret_access_key=src_secret_access_key,
        )

    if args.dest_service_name:
        dest_service = load_from_vcap_services('s3', None, args.dest_service_name)
        dest_access_key_id = dest_service.get('access_key_id')
        dest_secret_access_key = dest_service.get('secret_access_key')
        dest_bucket = dest_service.get('bucket')
        dest_prefix = ''
        dest_region = dest_service.get('region')
    else:
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

    async def worker(worker_num, queue):
        while True:
            # get a "work item" out of the queue.
            obj = await queue.get()

            key = obj.get('Key')
            if key_exists(dest_s3, dest_bucket, key):
                log.debug(f'worker={worker_num} skipping key={key} already exists on destination')
                continue

            log.info(f'worker={worker_num} copying key={key}')
            with tempfile.NamedTemporaryFile() as temp:
                # TODO use a pipe with asyncio to prevent serial download + upload
                src_s3.download_fileobj(src_bucket, key, temp)
                temp.seek(0)
                dest_s3.upload_fileobj(temp, dest_bucket, key)

            # Notify the queue that the "work item" has been processed.
            queue.task_done()

    # setup workers
    tasks = []
    queue = asyncio.Queue(maxsize=100)  # We put a maxsize to prevent queing 90k objects in memory
    log.debug(f'starting concurrency={args.concurrency} copy tasks...')
    for i in range(args.concurrency):
        task = asyncio.create_task(worker(i, queue))
        tasks.append(task)

    # iterate over each object
    for obj in list_objects(src_s3, src_bucket, src_prefix):
        await queue.put(obj)  # This will wait if the queue is full, preventing large queuing in memory

    # wait for queue to drain
    await queue.join()

    log.info('done processing queue')

    # Cancel our worker tasks who are waiting on an empty queue
    for task in tasks:
        task.cancel()

    log.info('cancelling tasks...')
    # Wait until all worker tasks are cancelled.
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info('done')



if __name__ == '__main__':
    asyncio.run(main())
