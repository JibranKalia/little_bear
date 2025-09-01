#!/usr/bin/env python3
"""
test_whisper.py - Test whisper transcription matching the main script logic
"""
import os
import json
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class EpisodeTranscript:
    episode_id: str
    season: str
    episode_number: str
    full_text: str
    segments: List[Dict]
    duration_seconds: float
    processing_time_seconds: float
    word_count: int
    segment_count: int

class WhisperTranscriber:
    def __init__(self):
        self.whisper_path = "/Users/jibrankalia/side/whisper.cpp/build/bin/whisper-cli"
        self.whisper_dir = "/Users/jibrankalia/side/whisper.cpp"
        
        if not os.path.exists(self.whisper_path):
            print(f"Error: whisper-cli not found at {self.whisper_path}")
            exit(1)
        print(f"✓ whisper-cli found at {self.whisper_path}")

    def transcribe_episode(self, audio_file: Path) -> EpisodeTranscript:
        # Extract episode info from filename
        filename = audio_file.name
        if filename.startswith("S"):
            parts = filename.split("E")
            season = parts[0]
            episode = parts[1].split(".")[0]
            episode_id = f"{season}E{episode}"
        else:
            episode_id = filename.split(".")[0]
            season = "unknown"
            episode = "unknown"
        
        print(f"\n━━━ Processing {episode_id} ━━━")
        print(f"Audio file: {audio_file}")
        file_size_mb = audio_file.stat().st_size / (1024*1024)
        print(f"File size: {file_size_mb:.1f} MB")
        
        start_time = time.time()
        
        # Check if whisper JSON already exists
        whisper_json_path = f"{str(audio_file)}.json"
        if os.path.exists(whisper_json_path):
            print(f"⟳ Using existing whisper output for {episode_id}")
            with open(whisper_json_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
        else:
            # Run whisper-cli
            audio_full_path = audio_file.resolve()
            cmd = [self.whisper_path, "-f", str(audio_full_path), "--output-json"]
            print(f"Running whisper-cli...")
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=self.whisper_dir)
                if result.returncode != 0:
                    raise RuntimeError(f"whisper-cli failed: {result.stderr}")
                
                if not os.path.exists(whisper_json_path):
                    raise FileNotFoundError(f"Expected JSON output not found: {whisper_json_path}")
                
                with open(whisper_json_path, 'r', encoding='utf-8') as f:
                    transcript_data = json.load(f)
                    
            except subprocess.TimeoutExpired:
                print(f"✗ Transcription timed out after 10 minutes")
                return None
            except Exception as e:
                print(f"✗ Error: {e}")
                return None

        # Extract segments from whisper transcription
        segments = []
        full_text_parts = []
        if "transcription" in transcript_data:
            for segment in transcript_data["transcription"]:
                segments.append({
                    "text": segment["text"].strip(),
                    "start_ms": segment["offsets"]["from"],
                    "end_ms": segment["offsets"]["to"],
                    "timestamp_from": segment["timestamps"]["from"],
                    "timestamp_to": segment["timestamps"]["to"],
                    "words": len(segment["text"].split())
                })
                full_text_parts.append(segment["text"].strip())
        
        # Calculate statistics
        full_text = " ".join(full_text_parts)
        processing_time = time.time() - start_time
        word_count = len(full_text.split()) if full_text else 0
        
        # Estimate duration from last segment if available
        duration = 0
        if segments:
            duration = segments[-1]["end_ms"] / 1000  # Convert to seconds
        
        # Create result object
        result = EpisodeTranscript(
            episode_id=episode_id,
            season=season,
            episode_number=episode,
            full_text=full_text,
            segments=segments,
            duration_seconds=duration,
            processing_time_seconds=processing_time,
            word_count=word_count,
            segment_count=len(segments)
        )
        
        # Display results
        print(f"✓ Transcription completed!")
        print(f"Duration: {result.duration_seconds:.1f} seconds")
        print(f"Words: {result.word_count}")
        print(f"Segments: {result.segment_count}")
        print(f"Processing Time: {result.processing_time_seconds:.1f} seconds")
        
        # Show sample segments
        if result.segments:
            print("\nSample segments:")
            for i, segment in enumerate(result.segments[:3]):
                print(f"  [{segment['timestamp_from']} -> {segment['timestamp_to']}] {segment['text'][:80]}...")
            if len(result.segments) > 3:
                print(f"  ... and {len(result.segments) - 3} more segments")
        
        return result

def test_whisper_transcription():
    # Find first audio file
    audio_dir = Path("audio_extracted")
    if not audio_dir.exists():
        print("Error: audio_extracted directory not found")
        return
    
    # Find first .wav file
    audio_files = list(audio_dir.glob("**/*.wav"))
    if not audio_files:
        print("Error: No .wav files found")
        return
    
    audio_file = audio_files[0]
    print(f"Testing with: {audio_file}")
    
    transcriber = WhisperTranscriber()
    result = transcriber.transcribe_episode(audio_file)
    
    if result:
        print(f"\n✓ Test successful! Transcribed {result.episode_id}")
        
        # Save a test JSON output to verify our data structure
        output_data = {
            "episode_id": result.episode_id,
            "season": result.season,
            "episode_number": result.episode_number,
            "metadata": {
                "duration_seconds": result.duration_seconds,
                "processing_time_seconds": result.processing_time_seconds,
                "word_count": result.word_count,
                "segment_count": result.segment_count,
                "processed_at": "test_run"
            },
            "full_text": result.full_text,
            "segments": result.segments
        }
        
        test_output_path = Path("test_output.json")
        with open(test_output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Test output saved to: {test_output_path}")
    else:
        print("✗ Test failed")

if __name__ == "__main__":
    test_whisper_transcription()