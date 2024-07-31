#delete every file from s3://gpt-api-temp/transcribe-audio-queue/uuid where uuid not in
#s3://gpt-api-temp/transcribe-audio-requests/uuid

import boto3
import os
import json

s3 = boto3.client('s3')
for obj in s3.list_objects(Bucket='gpt-api-temp', Prefix='transcribe-audio-queue/')['Contents']:
    uuid = obj['Key'].split('/')[-1]
    if not any([uuid in x['Key'] for x in s3.list_objects(Bucket='gpt-api-temp', Prefix='transcribe-audio-requests/')['Contents']]):
        s3.delete_object(Bucket='gpt-api-temp', Key=obj['Key'])