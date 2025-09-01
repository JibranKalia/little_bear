import assemblyai as aai

aai.settings.api_key = "ff2c5e1943f747f283c59b2f5bb037fe"

config = aai.TranscriptionConfig(
    speaker_labels=True,  # Enable speaker diarization
    speakers_expected=6,   # Typical number of characters per episode
    speech_model=aai.SpeechModel.best,  # Best model for accuracy
    language_code="en_us",
    punctuate=True,
    format_text=True,
)

transcriber = aai.Transcriber(config=config)

transcript = transcriber.transcribe("https://pub-f2f01ac518c14ad7b74e36ea97a290bc.r2.dev/S01E01.wav")

print(transcript.export_subtitles_srt())
print(transcript.export_subtitles_vtt())








