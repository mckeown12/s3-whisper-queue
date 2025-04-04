# pip install latest whisperX by cloning to fix https://github.com/m-bain/whisperX/issues/943
import os

# def pip_install_from_git(url):
#     #clone the repo
#     os.system(f"git clone {url}")
#     #get the name of the repo
#     repo_name = url.split('/')[-1].replace('.git', '')
#     #install the repo
#     os.system(f"pip3 install -e {repo_name} --break-system-packages")

# pip_install_from_git("https://github.com/m-bain/whisperX.git")
# # Reload site packages
# import site
# import importlib
# importlib.reload(site)

# importlib.invalidate_caches()
# whisperx = importlib.import_module("whisperx")

import boto3
import time
from time import sleep
import json
import httpx
from .myTypes import SalesforceRequest, GMTranscribeRequest, SalesforceExternalRequest
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
    sleep(60)
    os.system("sudo shutdown")
else:
    from operator import itemgetter
    transcription_queue['Contents'] = sorted(transcription_queue['Contents'], key=itemgetter('LastModified'))
    print(f"Found {len(transcription_queue['Contents'])} files to transcribe")
print('about to import transcribe_audio')
t1 = time.time()
# from .whisperPipe import transcribe_audio
# from .diarizePipe import diarize
from .wx2 import process_audio, transcription_model, diarization_model, device, batch_size
print(time.time() - t1, 'seconds to import transcribe_audio and diarize')

resp = httpx.post("https://salesforce.watsco.ai/token", data={"username": os.getenv('APP_USER'), "password": os.getenv('APP_PASS')})
tok = resp.json()['access_token']

def makeObj(uuid):
    req = s3.get_object(Bucket='gpt-api-temp',Key=f'transcribe-audio-requests/{uuid}')['Body'].read()
    print(req)
    req = json.loads(req)
    try:
        req2 = SalesforceRequest(**req)
        return req2
    except Exception as e:
        print(f"failed to make request: {e}. Trying gm")
    try:
        req2 = GMTranscribeRequest(**req)
        return req2
    except Exception as e:
        print(f"failed to make gm request: {e} trying external")
    try:
        req2 = SalesforceExternalRequest(**req)
        return req2
    except Exception as e:
        print(f"failed to make external request: {e} Total fail.")
        import traceback
        traceback.print_exc()
        return None

def make_request(uuid, req : SalesforceRequest | GMTranscribeRequest | SalesforceExternalRequest, transcription, duration, language):

    req.duration = duration
    req.transcription = transcription
    req.language = language
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + tok
    }
    payload = req.model_dump_json()
    print(payload)
    if isinstance(req, SalesforceRequest):
        res = httpx.post('https://salesforce.watsco.ai/transcribe/', data=payload, headers=headers, timeout=30)
        print(res)
        print(res.text)
        if res.status_code==200:
            print('deleting request from s3')
            s3.delete_object(Bucket='gpt-api-temp', Key=f'transcribe-audio-requests/{uuid}')
            return 1
        return 0
    elif isinstance(req, GMTranscribeRequest):
        res = httpx.post('https://salesforce.watsco.ai/gm/transcribe/', data=payload, headers=headers, timeout=30)
        print(res)
        print(res.text)
        if res.status_code==200:
            print('deleting request and transcript from s3')
            s3.delete_object(Bucket='gpt-api-temp', Key=f"transcribe-audio-requests/{uuid}")
            return 1
        return 0
    elif isinstance(req, SalesforceExternalRequest):
        res = httpx.post('https://salesforce.watsco.ai/transcribe/', data=payload, headers=headers, timeout=30)
        print(res)
        print(res.text)
        if res.status_code==200:
            print('deleting request and transcript from s3')
            s3.delete_object(Bucket='gpt-api-temp', Key=f"transcribe-audio-requests/{uuid}")
            return 1
        return 0

    
def processObj(obj):
    uuid = obj['Key'].split('/')[-1]
    audio_path = obj['Key']
    #copy the audio file to the local filesystem
    s3.download_file(bucket, audio_path, f"/tmp/{uuid}")
    print(f"Transcribing {audio_path}")
    t1 = time.time()
    req = makeObj(uuid)
    try:
        transcription, duration, language = process_audio(f"/tmp/{uuid}", transcription_model, diarization_model, device, batch_size, multiple_speakers=req.multiple_speakers)
    except Exception as e:
        #if the file is older than one day, delete both the audio file and the request
        print(f"Error transcribing {audio_path}")
        print(e)
        import traceback
        traceback.print_exc()
        if time.time() - obj['LastModified'].timestamp() > 86400:
            print(f"Deleting {audio_path} and request {uuid}")
            s3.delete_object(Bucket=bucket, Key=audio_path)
            s3.delete_object(Bucket='gpt-api-temp', Key=f'transcribe-audio-requests/{uuid}')
            os.remove(f"/tmp/{uuid}")
            return
        else:
            print(f"Transcription failed for {audio_path}, will try again in 5 minutes")
            #delete the audio file
            os.remove(f"/tmp/{uuid}")
            return
    t2 = time.time()
    print(f"Transcription took {t2 - t1} seconds")
    print(f"Transcription: {transcription}")
    went_through = make_request(uuid, req, transcription, duration, language)
    if not went_through:
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


def processTranscriptionQueue(transcription_queue):
    for obj in transcription_queue['Contents']:
        try:
            processObj(obj)
        except Exception as e:
            print(f"Error processing {obj['Key']}")
            print(e)
            import traceback
            traceback.print_exc()
            continue

#check if anything new has arrived since we started
print('finished first pass! Checking for new objects...')
while True:
    time_to_wait = 3000 # 50 minutes
    poll_interval = 5
    started_waiting = time.time()
    #poll every 5 seconds until we've waited time_to_wait seconds
    while time.time() - started_waiting < time_to_wait:
        time.sleep(poll_interval)
        new_transcription_queue = s3.list_objects_v2(Bucket=bucket, Prefix=bucket_audio_path)
        if 'Contents' in new_transcription_queue:
            print(f"found {len(new_transcription_queue['Contents'])} new files to process")
            transcription_queue = new_transcription_queue
            processTranscriptionQueue(transcription_queue)
            break
        else:
            print(f'No new files found, will wait for {time_to_wait - (time.time() - started_waiting)} more seconds.')
    else:
        print('nothing left to process, shutting down')
        #shut down computer
        os.system("sudo shutdown now")