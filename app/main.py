import boto3
import os
import time
from time import sleep

region_name = "us-east-1"
bucket = os.getenv('BUCKET_NAME')
bucket_audio_path = os.getenv("BUCKET_AUDIO_PATH")
bucket_transcript_path = os.getenv("BUCKET_TRANSCRIPT_PATH")
boto3.setup_default_session(region_name=region_name)
session = boto3.session.Session()
s3 = session.client(service_name='s3', region_name=region_name)
#s3 ls s3://gpt-api-temp/transcription-queue/
transcription_queue = s3.list_objects_v2(Bucket=bucket, Prefix=bucket_audio_path)

if 'Contents' not in transcription_queue:
    print("No audio files to transcribe")
    sleep(120)
    os.system("sudo shutdown")
else:
    print(f"Found {len(transcription_queue['Contents'])} files to transcribe")
print('about to import transcribe_audio')
t1 = time.time()
# from .whisperPipe import transcribe_audio
# from .diarizePipe import diarize
from .wx2 import process_audio, transcription_model, diarization_model, device, batch_size
print(time.time() - t1, 'seconds to import transcribe_audio and diarize')


def processObj(obj):
    uuid = obj['Key'].split('/')[-1]
    audio_path = obj['Key']
    #copy the audio file to the local filesystem
    s3.download_file(bucket, audio_path, f"/tmp/{uuid}")
    print(f"Transcribing {audio_path}")
    t1 = time.time()
    transcription = process_audio(f"/tmp/{uuid}", transcription_model, diarization_model, device, batch_size)
    t2 = time.time()
    print(f"Transcription took {t2 - t1} seconds")
    print(f"Transcription: {transcription}")
    #write the transcription output to a local file
    with open(f"/tmp/{uuid}.txt", "w", encoding='utf-8') as file:
        file.write(transcription)
    #upload the transcription output to S3
    print(f"uploading /tmp/{uuid}.txt to {bucket} path {bucket_transcript_path}/{uuid}")
    upload_res = s3.upload_file(f"/tmp/{uuid}.txt", bucket, f"{bucket_transcript_path}/{uuid}")
    print(upload_res)
    #delete the local file
    os.remove(f"/tmp/{uuid}.txt")
    #delete the local audio file
    os.remove(f"/tmp/{uuid}")
    #delete the object from the queue
    s3.delete_object(Bucket=bucket, Key=audio_path)
    print(f"Transcription {audio_path} complete")


#check if anything new has arrived since we started
while True:
    transcription_queue = s3.list_objects_v2(Bucket=bucket, Prefix=bucket_audio_path)
    if 'Contents' not in transcription_queue:
        print('nothing left to process, shutting down')
        #shut down computer
        os.system("sudo shutdown now")
    for obj in transcription_queue['Contents']:
        try:
            processObj(obj)
        except Exception as e:
            print(f"Error processing {obj['Key']}")
            print(e)
            import traceback
            traceback.print_exc()
            continue