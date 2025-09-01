#!/usr/bin/env python3
"""
transcribe_episodes.py - Transcribe Little Bear episodes with speaker diarization
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import assemblyai as aai
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

console = Console()

@dataclass
class EpisodeTranscript:
    episode_id: str
    season: str
    episode_number: str
    full_text: str
    utterances: List[Dict]
    duration_seconds: float
    processing_time_seconds: float
    word_count: int
    speaker_count: int

class LittleBearTranscriber:
    def __init__(self, api_key: Optional[str] = None):
        # Set API key from environment variable or parameter
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "AssemblyAI API key required!\n"
                "Set it with: export ASSEMBLYAI_API_KEY='your_key_here'\n"
                "Or pass it with: --api-key YOUR_KEY"
            )
        
        aai.settings.api_key = self.api_key
        
        # Configure transcription settings for Little Bear
        self.config = aai.TranscriptionConfig(
            speaker_labels=True,  # Enable speaker diarization
            speakers_expected=6,   # Typical number of characters per episode
            speech_model=aai.SpeechModel.best,  # Best model for accuracy
            language_code="en_us",
            punctuate=True,
            format_text=True,
        )
        
        self.transcriber = aai.Transcriber(config=self.config)
        
        # Paths
        self.base_dir = Path("/Users/jibrankalia/side/little_bear")
        self.audio_dir = self.base_dir / "audio_extracted"
        self.output_dir = self.base_dir / "transcripts"
        self.output_dir.mkdir(exist_ok=True)
        
        # Stats
        self.stats = {
            "processed": 0,
            "errors": 0,
            "total_duration": 0,
            "total_words": 0
        }
    
    def find_audio_files(self) -> List[Path]:
        """Find all WAV files to process"""
        wav_files = []
        for season_dir in sorted(self.audio_dir.glob("season_*")):
            wav_files.extend(sorted(season_dir.glob("*.wav")))
        return wav_files
    
    def parse_episode_id(self, file_path: Path) -> tuple:
        """Extract season and episode from filename like S01E02.wav"""
        stem = file_path.stem  # S01E02
        season = stem[1:3]      # 01
        episode = stem[4:6]     # 02
        return stem, season, episode
    
    def process_single_episode(self, audio_file: Path) -> Optional[EpisodeTranscript]:
        """Process a single episode"""
        episode_id, season, episode = self.parse_episode_id(audio_file)
        
        # Check if already processed
        output_file = self.output_dir / f"{episode_id}.json"
        if output_file.exists():
            console.print(f"[yellow]⟳ Skipping {episode_id} (already processed)[/yellow]")
            return None
        
        console.print(f"\n[cyan]━━━ Processing {episode_id} ━━━[/cyan]")
        start_time = time.time()
        
        try:
            # Transcribe with progress indicator
            with console.status(f"[cyan]Transcribing {episode_id}...[/cyan]", spinner="dots"):
                transcript = self.transcriber.transcribe(str(audio_file))
            
            # Check for errors
            if transcript.status == "error":
                console.print(f"[red]✗ Error: {transcript.error}[/red]")
                self.stats["errors"] += 1
                return None
            
            # Extract utterances with speaker labels
            utterances = []
            for utterance in transcript.utterances:
                utterances.append({
                    "speaker": utterance.speaker,
                    "text": utterance.text,
                    "start_ms": utterance.start,
                    "end_ms": utterance.end,
                    "confidence": utterance.confidence,
                    "words": len(utterance.text.split())
                })
            
            # Calculate statistics
            duration = (transcript.audio_duration or 0) / 1000  # Convert to seconds
            processing_time = time.time() - start_time
            word_count = len(transcript.text.split()) if transcript.text else 0
            unique_speakers = len(set(u["speaker"] for u in utterances))
            
            # Create result object
            result = EpisodeTranscript(
                episode_id=episode_id,
                season=season,
                episode_number=episode,
                full_text=transcript.text,
                utterances=utterances,
                duration_seconds=duration,
                processing_time_seconds=processing_time,
                word_count=word_count,
                speaker_count=unique_speakers
            )
            
            # Save to JSON
            self.save_transcript(result, output_file)
            
            # Update stats
            self.stats["processed"] += 1
            self.stats["total_duration"] += duration
            self.stats["total_words"] += word_count
            
            # Print summary
            self.print_episode_summary(result)
            
            return result
            
        except Exception as e:
            console.print(f"[red]✗ Error processing {episode_id}: {str(e)}[/red]")
            self.stats["errors"] += 1
            return None
    
    def save_transcript(self, transcript: EpisodeTranscript, output_file: Path):
        """Save transcript to JSON file"""
        data = {
            "episode_id": transcript.episode_id,
            "season": transcript.season,
            "episode_number": transcript.episode_number,
            "metadata": {
                "duration_seconds": transcript.duration_seconds,
                "processing_time_seconds": transcript.processing_time_seconds,
                "word_count": transcript.word_count,
                "speaker_count": transcript.speaker_count,
                "processed_at": datetime.now().isoformat()
            },
            "full_text": transcript.full_text,
            "utterances": transcript.utterances
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✓ Saved to {output_file.name}[/green]")
    
    def print_episode_summary(self, transcript: EpisodeTranscript):
        """Print summary of processed episode"""
        table = Table(title=f"Episode {transcript.episode_id} Summary", show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Duration", f"{transcript.duration_seconds:.1f} seconds")
        table.add_row("Words", str(transcript.word_count))
        table.add_row("Speakers", str(transcript.speaker_count))
        table.add_row("Processing Time", f"{transcript.processing_time_seconds:.1f} seconds")
        table.add_row("Utterances", str(len(transcript.utterances)))
      
