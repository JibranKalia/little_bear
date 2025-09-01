#!/usr/bin/env python3
"""
transcribe_episodes.py - Transcribe Little Bear episodes using local whisper
"""

import os
import sys
import json
import time
import rich
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()

@dataclass
class EpisodeTranscript:
    episode_id: str
    season: str
    episode_number: str
    full_text: str
    segments: List[Dict]  # Whisper segments instead of utterances
    duration_seconds: float
    processing_time_seconds: float
    word_count: int
    segment_count: int  # Number of segments instead of speaker count

class LittleBearWhisperTranscriber:
    def __init__(self, whisper_path: Optional[str] = None):
        # Set whisper-cli path and working directory
        self.whisper_path = whisper_path or "/Users/jibrankalia/side/whisper.cpp/build/bin/whisper-cli"
        self.whisper_dir = "/Users/jibrankalia/side/whisper.cpp"
        
        # Check if whisper-cli exists
        if not os.path.exists(self.whisper_path):
            console.print(f"[red]Error: whisper-cli not found at {self.whisper_path}![/red]")
            console.print("Please build whisper.cpp or provide the correct path with --whisper-path")
            sys.exit(1)
        
        console.print(f"[green]✓ whisper-cli found at {self.whisper_path}[/green]")
        
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
        """Process a single episode with retry logic"""
        episode_id, season, episode = self.parse_episode_id(audio_file)
        
        # Check if already processed (both our JSON and whisper JSON)
        output_file = self.output_dir / f"{episode_id}.json"
        whisper_json_path = f"{str(audio_file)}.json"
        
        if output_file.exists():
            console.print(f"[yellow]⟳ Skipping {episode_id} (already processed)[/yellow]")
            return None
        
        console.print(f"\n[cyan]━━━ Processing {episode_id} ━━━[/cyan]")
        console.print(f"Audio file: {audio_file}")
        file_size_mb = audio_file.stat().st_size / (1024*1024)
        console.print(f"File size: {file_size_mb:.1f} MB")
        
        start_time = time.time()
        transcript = None
        
        # Check if whisper JSON already exists from previous run
        if os.path.exists(whisper_json_path):
            console.print(f"[yellow]⟳ Using existing whisper output for {episode_id}[/yellow]")
            with open(whisper_json_path, 'r', encoding='utf-8') as f:
                transcript = json.load(f)
        else:
            # Retry logic for handling timeouts
            max_retries = 3
            retry_delay = 30  # Start with 30 seconds
            
            for attempt in range(max_retries):
                try:
                    # Transcribe with progress indicator
                    status_msg = f"[cyan]Transcribing {episode_id} with whisper-cli... (attempt {attempt + 1}/{max_retries})[/cyan]"
                    
                    with console.status(status_msg, spinner="dots"):
                        # Run whisper-cli subprocess from whisper.cpp directory
                        audio_full_path = audio_file.resolve()  # Get absolute path
                        cmd = [self.whisper_path, "-f", str(audio_full_path), "--output-json"]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=self.whisper_dir)
                        
                        if result.returncode != 0:
                            raise RuntimeError(f"whisper-cli failed: {result.stderr}")
                        
                        # Load the JSON output file
                        if not os.path.exists(whisper_json_path):
                            raise FileNotFoundError(f"Expected JSON output not found: {whisper_json_path}")
                        
                        with open(whisper_json_path, 'r', encoding='utf-8') as f:
                            transcript = json.load(f)
                    
                    # If we get here, transcription was successful
                    break
                    
                except subprocess.TimeoutExpired:
                    console.print(f"[red]✗ Attempt {attempt + 1} timed out after 10 minutes[/red]")
                    console.print(f"[yellow]File size: {file_size_mb:.1f} MB - large files may take longer[/yellow]")
                    
                    if attempt < max_retries - 1:
                        console.print(f"[yellow]Retrying in {retry_delay} seconds...[/yellow]")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        console.print(f"[red]Failed after {max_retries} attempts[/red]")
                        self.stats["errors"] += 1
                        return None
                except Exception as e:
                    console.print(f"[red]✗ Attempt {attempt + 1} failed: {str(e)}[/red]")
                    console.print(f"[red]Error type: {type(e).__name__}[/red]")
                    
                    if attempt < max_retries - 1:
                        console.print(f"[yellow]Retrying in {retry_delay} seconds...[/yellow]")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        console.print(f"[red]Failed after {max_retries} attempts[/red]")
                        self.stats["errors"] += 1
                        return None
        
        # Check if transcript was obtained
        if not transcript:
            console.print(f"[red]✗ Failed to transcribe {episode_id}[/red]")
            self.stats["errors"] += 1
            return None
        
        # Extract segments from whisper transcription
        segments = []
        full_text_parts = []
        if "transcription" in transcript:
            for segment in transcript["transcription"]:
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
        
        # Save to JSON
        self.save_transcript(result, output_file)
        
        # Update stats
        self.stats["processed"] += 1
        self.stats["total_duration"] += duration
        self.stats["total_words"] += word_count
        
        # Print summary
        self.print_episode_summary(result)
        
        return result
    
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
                "segment_count": transcript.segment_count,
                "processed_at": datetime.now().isoformat()
            },
            "full_text": transcript.full_text,
            "segments": transcript.segments
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
        table.add_row("Segments", str(transcript.segment_count))
        table.add_row("Processing Time", f"{transcript.processing_time_seconds:.1f} seconds")
        
        console.print(table)
        
        # Show segment sample
        if transcript.segments and len(transcript.segments) > 0:
            console.print("\n[cyan]Sample segments:[/cyan]")
            for i, segment in enumerate(transcript.segments[:3]):  # Show first 3 segments
                console.print(f"  [{segment['timestamp_from']} -> {segment['timestamp_to']}] {segment['text'][:50]}...")
            if len(transcript.segments) > 3:
                console.print(f"  ... and {len(transcript.segments) - 3} more segments")
    
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
        
        # Calculate estimated time
        total_minutes = sum(self.get_duration_minutes(f) for f in audio_files)
        console.print(f"Estimated processing time: ~{total_minutes:.1f} minutes of audio")
        
        console.print("[green]Starting transcription...[/green]")
        
        # Process each file
        for i, audio_file in enumerate(audio_files, 1):
            console.print(f"\n[bold]File {i}/{len(audio_files)}[/bold]")
            self.process_single_episode(audio_file)
            
            # Brief pause between files
            if i < len(audio_files):
                time.sleep(0.5)
        
        # Print final summary
        self.print_final_summary()
    
    def get_duration_minutes(self, audio_file: Path) -> float:
        """Estimate duration based on file size (rough estimate)"""
        # For 44.1kHz stereo: ~10.5 MB per minute
        size_mb = audio_file.stat().st_size / (1024 * 1024)
        return size_mb / 10.5
    
    def confirm_processing(self, count: int) -> bool:
        """Ask for confirmation before processing"""
        response = console.input(f"\n[yellow]Process {count} files with local whisper? (y/n): [/yellow]")
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
    
    parser = argparse.ArgumentParser(description="Transcribe Little Bear episodes with whisper")
    parser.add_argument("--limit", type=int, help="Limit number of episodes to process")
    parser.add_argument("--whisper-path", help="Path to whisper-cli binary (default: ./build/bin/whisper-cli)")
    args = parser.parse_args()
    
    try:
        transcriber = LittleBearWhisperTranscriber(whisper_path=getattr(args, 'whisper_path', None))
        transcriber.run(limit=args.limit)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

