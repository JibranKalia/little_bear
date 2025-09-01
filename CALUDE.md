# CLAUDE.md - Little Bear Transcription Project

## Project Overview
Building a searchable web app to help a child with apraxia and autism communicate using phrases from the Little Bear TV show. The child says partial/mumbled words from the show, and the parent needs to quickly find the complete phrase.

## Technical Stack
- **Backend**: Rails with Hotwire, Stimulus, Tailwind
- **Database**: PostgreSQL with full-text search (pg_search)
- **Deployment**: Kamal on Hetzner
- **Transcription**: AssemblyAI with speaker diarization
- **Audio Processing**: FFmpeg for extraction, optional Demucs for separation

## Implementation Progress

### ✅ Phase 1: Audio Extraction
- Created Ruby script to extract audio from MKV files
- Processes multiple seasons automatically
- Outputs to `/Users/jibrankalia/side/little_bear/audio_extracted/`
- Settings: 44.1kHz stereo WAV for optimal transcription quality

### 🚧 Phase 2: Transcription with Speaker Diarization
- Python script using AssemblyAI SDK
- Enables speaker diarization (6 expected speakers)
- Cost: ~$7.02 for all 65 episodes
- Outputs JSON with full text and speaker-labeled utterances
- Currently debugging timeout issues with large file uploads

### 📋 Next Steps

#### Phase 3: Database Import
- Rails models: Episode, Segment
- PostgreSQL full-text search with trigram matching
- Import JSON transcripts with speaker labels

#### Phase 4: Character Identification
- Map SPEAKER_00 → "Little Bear", "Duck", etc.
- Use pattern matching on common phrases
- Build admin interface for manual mapping
- Consider voice embeddings with Resemblyzer

#### Phase 5: Search Interface
- Simple search bar with fuzzy matching
- Show full phrase with context
- Display character name and episode info
- Optimize for quick mobile access

## Key Decisions Made

1. **AssemblyAI over alternatives**: Best accuracy (2.9% error rate) at reasonable cost
2. **44.1kHz stereo audio**: Preserves character voice distinctions
3. **Skip audio separation initially**: Test if background music interferes first
4. **PostgreSQL search**: Simple and sufficient for ~65 episodes
5. **Semi-automated character mapping**: Start manual, build patterns over time

## File Structure
/Users/jibrankalia/side/little_bear/
├── season_01/           # Original MKV files
├── audio_extracted/     # Processed WAV files
│   └── season_01/
│       ├── S01E01.wav
│       └── ...
├── transcripts/         # JSON transcription results
│   ├── S01E01.json
│   └── ...
├── extract_audio.rb     # Audio extraction script
└── transcribe_episodes.py # Transcription script


## Resources
- [AssemblyAI Documentation](https://www.assemblyai.com/docs)
- [Forever Dreaming Transcripts](https://transcripts.foreverdreaming.org/viewforum.php?f=2277) - Reference transcripts
- Character voices research for speaker identification
