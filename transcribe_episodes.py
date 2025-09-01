#!/usr/bin/env python3
"""
transcribe_episodes.py - Transcribe Little Bear episodes with speaker diarization
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import assemblyai as aai
from rich.console import Console
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
        self.api_key = api_key or os.environ.get("ASSEMBLYAI_API_KEY")
        if not self.api_key:
            console.print("[red]Error: AssemblyAI API key not found![/red]")
            console.print("Set it with: export ASSEMBLYAI_API_KEY='your_key_here'")
            console.print("Or pass it with: --api-key YOUR_KEY")
            sys.exit(1)
        
        console.print(f"[green]✓ API key found (ending in ...{self.api_key[-4:]})[/green]")
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
        
        # Debug: Check if paths exist
        console.print(f"[cyan]Base directory: {self.base_dir}[/cyan]")
        console.print(f"[cyan]Audio directory: {self.audio_dir}[/cyan]")
        console.print(f"[cyan]Audio dir exists: {self.audio_dir.exists()}[/cyan]")
        
        if not self.audio_dir.exists():
            console.print(f"[red]Error: Audio directory not found at {self.audio_dir}[/red]")
            console.print("[yellow]Have you run the audio extraction script first?[/yellow]")
            sys.exit(1)
        
        self.output_dir.mkdir(exist_ok=True)
        console.print(f"[cyan]Output directory: {self.output_dir}[/cyan]")
        
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
        
        console.print("\n[cyan]Searching for audio files...[/cyan]")
        
        # List all directories in audio_extracted
        season_dirs = list(self.audio_dir.glob("season_*"))
        console.print(f"Found {len(season_dirs)} season directories")
        
        for season_dir in sorted(season_dirs):
            season_files = list(season_dir.glob("*.wav"))
            console.print(f"  {season_dir.name}: {len(season_files)} WAV files")
            wav_files.extend(sorted(season_files))
        
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
        console.print(f"Audio file: {audio_file}")
        console.print(f"File size: {audio_file.stat().st_size / (1024*1024):.1f} MB")
        
        start_time = time.time()
        
        try:
            # Transcribe with progress indicator
            with console.status(f"[cyan]Uploading and transcribing {episode_id}... (this may take a few minutes)[/cyan]", spinner="dots"):
                transcript = self.transcriber.transcribe(str(audio_file))
            
            # Check for errors
            if transcript.status == "error":
                console.print(f"[red]✗ Error: {transcript.error}[/red]")
                self.stats["errors"] += 1
                return None
            
            # Extract utterances with speaker labels
            utterances = []
            if transcript.utterances:
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
            unique_speakers = len(set(u["speaker"] for u in utterances)) if utterances else 0
            
            # Create result object
            result = EpisodeTranscript(
                episode_id=episode_id,
                season=season,
                episode_number=episode,
                full_text=transcript.text or "",
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
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
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
        
        console.print(table)
        
        # Show speaker distribution
        if transcript.utterances:
            speaker_counts = {}
            for u in transcript.utterances:
                speaker = u["speaker"]
                speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            
            console.print("\n[cyan]Speaker Distribution:[/cyan]")
            for speaker, count in sorted(speaker_counts.items()):
                console.print(f"  {speaker}: {count} utterances")
    
    def run(self, limit: Optional[int] = None):
        """Process all episodes"""
        console.print("[bold cyan]🎬 Little Bear Transcription Pipeline[/bold cyan]")
        console.print("=" * 50)
        
        # Find audio files
        audio_files = self.find_audio_files()
        
        if not audio_files:
            console.print("[red]No audio files found![/red]")
            console.print("[yellow]Please run the audio extraction script first.[/yellow]")
            return
        
        if limit:
            audio_files = audio_files[:limit]
            console.print(f"\n[yellow]Limiting to first {limit} file(s)[/yellow]")
        
        console.print(f"\n[green]Ready to process {len(audio_files)} audio file(s)[/green]")
        
        # Calculate costs
        total_minutes = sum(self.get_duration_minutes(f) for f in audio_files)
        estimated_cost = total_minutes * 0.0045  # $0.0045 per minute
        console.print(f"Estimated cost: [green]${estimated_cost:.2f}[/green] for ~{total_minutes:.1f} minutes")
        
        # Confirm
        if not self.confirm_processing(len(audio_files), estimated_cost):
            console.print("[yellow]Cancelled by user[/yellow]")
            return
        
        # Process each file
        for i, audio_file in enumerate(audio_files, 1):
            console.print(f"\n[bold]File {i}/{len(audio_files)}[/bold]")
            self.process_single_episode(audio_file)
            
            # Rate limiting (AssemblyAI allows 5 concurrent)
            if i < len(audio_files):
                time.sleep(1)
        
        # Print final summary
        self.print_final_summary()
    
    def get_duration_minutes(self, audio_file: Path) -> float:
        """Estimate duration based on file size (rough estimate)"""
        # For 44.1kHz stereo: ~10.5 MB per minute
        size_mb = audio_file.stat().st_size / (1024 * 1024)
        return size_mb / 10.5
    
    def confirm_processing(self, count: int, cost: float) -> bool:
        """Ask for confirmation before processing"""
        response = console.input(f"\n[yellow]Process {count} files for ~${cost:.2f}? (y/n): [/yellow]")
        return response.lower() in ['y', 'yes']
    
    def print_final_summary(self):
        """Print final processing summary"""
        console.print("\n" + "=" * 50)
        console.print("[bold cyan]📊 Final Summary[/bold cyan]")
        console.print("=" * 50)
        
        table = Table(show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Episodes Processed", str(self.stats["processed"]))
        table.add_row("Errors", str(self.stats["errors"]))
        table.add_row("Total Duration", f"{self.stats['total_duration']:.1f} seconds")
        table.add_row("Total Words", f"{self.stats['total_words']:,}")
        
        if self.stats["processed"] > 0:
            avg_words = self.stats["total_words"] / self.stats["processed"]
            table.add_row("Avg Words/Episode", f"{avg_words:.0f}")
        
        console.print(table)
        console.print(f"\n[green]Transcripts saved to: {self.output_dir}[/green]")

if __name__ == "__main__":
    import argparse
    
    console.print("[cyan]Starting Little Bear Transcriber...[/cyan]")
    
    parser = argparse.ArgumentParser(description="Transcribe Little Bear episodes")
    parser.add_argument("--limit", type=int, help="Limit number of episodes to process")
    parser.add_argument("--api-key", help="AssemblyAI API key (or set ASSEMBLYAI_API_KEY env)")
    args = parser.parse_args()
    
    try:
        transcriber = LittleBearTranscriber(api_key=args.api_key)
        transcriber.run(limit=args.limit)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

