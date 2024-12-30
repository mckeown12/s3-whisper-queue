import whisperX as whisperx
import os
import time
import re


def load_models(device, compute_type):
    print('Loading transcription model...')
    t_start = time.time()
    transcription_model = whisperx.load_model("large-v3", device, compute_type=compute_type)
    print(f'Transcription model loaded in {time.time() - t_start:.2f} seconds.')
    
    print('Loading diarization model...')
    t_start = time.time()
    diarization_model = whisperx.DiarizationPipeline(model_name="pyannote/speaker-diarization-3.1", use_auth_token=os.getenv('HF_TOKEN'), device=device)
    print(f'Diarization model loaded in {time.time() - t_start:.2f} seconds.')
    
    return transcription_model, diarization_model

def load_alignment_model(language_code, device):
    print(f'Loading alignment model for language: {language_code}...')
    t_start = time.time()
    align_model, metadata = whisperx.load_align_model(language_code=language_code, device=device)
    print(f'Alignment model loaded in {time.time() - t_start:.2f} seconds.')
    return align_model, metadata

def process_audio(audio_path, transcription_model, diarization_model, device, batch_size, multiple_speakers):
    print('Loading audio...')
    t_start = time.time()
    audio = whisperx.load_audio(audio_path)
    print(f'Audio loaded in {time.time() - t_start:.2f} seconds.')
    #see how long audio is assuming 16kHz
    print(f"Audio duration: {len(audio) / 16000} seconds")
    print('Transcribing audio...')
    t_start = time.time()
    transcribe_result = transcription_model.transcribe(audio, batch_size=batch_size)
    print(f'Transcription completed in {time.time() - t_start:.2f} seconds.')
    if transcribe_result['language'] not in ['en', 'es', 'fr']:
        transcribe_result['language'] = 'en' #if something else was detected it was probably wrong
    
    if multiple_speakers==False:
        return ' '.join([x['text'] for x in transcribe_result['segments']]), len(audio) / 16000, transcribe_result['language']
    
    # Load alignment model based on detected language
    align_model, metadata = load_alignment_model(transcribe_result["language"], device)

    print('Aligning...')
    t_start = time.time()
    aligned_result = whisperx.align(transcribe_result["segments"], align_model, metadata, audio, device, return_char_alignments=False)
    print(f'Alignment completed in {time.time() - t_start:.2f} seconds.')

    print('Diarizing...')
    t_start = time.time()
    diarize_segments = diarization_model(audio)
    print(f'Diarization completed in {time.time() - t_start:.2f} seconds.')
    
    print('Assigning speakers...')
    t_start = time.time()
    final_result = whisperx.assign_word_speakers(diarize_segments, aligned_result)
    print(f'Speaker assignment completed in {time.time() - t_start:.2f} seconds.')

    return format_segments(final_result), len(audio) / 16000, transcribe_result['language']


def clean_single_speaker_transcript(transcript):
    # Check if there's more than one speaker
    speakers = set(re.findall(r"\(SPEAKER_(\d+)\)", transcript))
    # If only one speaker, proceed to clean the transcript
    if len(speakers) == 1:
        # Remove all diarization and time information
        cleaned_transcript = re.sub(r"\[\d{1,2}:\d{2} -> \d{1,2}:\d{2}\]\(SPEAKER_\d{2}\) ", "", transcript)
    else:
        # If there are multiple speakers, return the original transcript
        cleaned_transcript = transcript
    return cleaned_transcript

def condense_conversation(conversation):
    condensed_lines = []
    current_speaker = None
    current_text = ""
    
    for line in conversation.split('\n'):
        match = re.match(r'\[(\d+:\d+) -> (\d+:\d+)\]\((SPEAKER_\d+|Unknown)\)\s*(.*)', line.strip())
        if match:
            start_time, end_time, speaker, text = match.groups()
            
            if speaker == current_speaker:
                current_text += " " + text
            else:
                if current_speaker:
                    condensed_lines.append(f"[{current_start_time} -> {current_end_time}]({current_speaker}) {current_text}")
                current_speaker = speaker
                current_text = text
                current_start_time = start_time
            
            current_end_time = end_time
    
    if current_speaker:
        condensed_lines.append(f"[{current_start_time} -> {current_end_time}]({current_speaker}) {current_text}")
    
    return "\n".join(condensed_lines)


def format_segments(result):
    formatted_output = ''
    for segment in result["segments"]:
        start_minutes = int(segment['start'] // 60)
        start_seconds = int(segment['start'] % 60)
        end_minutes = int(segment['end'] // 60)
        end_seconds = int(segment['end'] % 60)
        speaker = segment.get('speaker', 'Unknown')
        # print(segment)
        formatted_output += f"[{start_minutes}:{start_seconds:02d} -> {end_minutes}:{end_seconds:02d}]({speaker}) {segment['text']}\n"
    #if there is only one speaker, remove all the diarization and time info
    return clean_single_speaker_transcript(condense_conversation(formatted_output))

# Set up
device = "cuda" 
batch_size = 16
compute_type = "float16"

# Load transcription and diarization models at the beginning
transcription_model, diarization_model = load_models(device, compute_type)


