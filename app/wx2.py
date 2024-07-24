import whisperx
import os
import time

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

def process_audio(audio_path, transcription_model, diarization_model, device, batch_size):
    print('Loading audio...')
    t_start = time.time()
    audio = whisperx.load_audio(audio_path)
    print(f'Audio loaded in {time.time() - t_start:.2f} seconds.')
    
    print('Transcribing audio...')
    t_start = time.time()
    transcribe_result = transcription_model.transcribe(audio, batch_size=batch_size)
    print(f'Transcription completed in {time.time() - t_start:.2f} seconds.')

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

    return format_segments(final_result)

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
    return formatted_output

# Set up
device = "cuda" 
batch_size = 16
compute_type = "float16"

# Load transcription and diarization models at the beginning
transcription_model, diarization_model = load_models(device, compute_type)

