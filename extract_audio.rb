#!/usr/bin/env ruby

require 'fileutils'
require 'pathname'
require 'open3'

class LittleBearAudioExtractor
  # Base directories
  BASE_DIR = "/Users/jibrankalia/side/little_bear"
  OUTPUT_BASE_DIR = File.join(BASE_DIR, "audio_extracted")
  
  # Terminal colors
  COLORS = {
    red: "\033[0;31m",
    green: "\033[0;32m",
    blue: "\033[0;34m",
    yellow: "\033[1;33m",
    cyan: "\033[0;36m",
    reset: "\033[0m"
  }

  def initialize(options = {})
    @sample_rate = options[:sample_rate] || 44100  # Changed from 16000
    @channels = options[:channels] || 2             # Changed from 1
    @skip_existing = options[:skip_existing] != false
    @stats = {
      total: 0,
      processed: 0,
      skipped: 0,
      errors: 0
    }
  end
  
  def run
    puts colorize("🎬 Little Bear Audio Extraction", :cyan)
    puts colorize("=" * 50, :cyan)
    
    # Create main output directory
    FileUtils.mkdir_p(OUTPUT_BASE_DIR)
    
    # Find and process all season directories
    season_dirs = find_season_directories
    
    if season_dirs.empty?
      puts colorize("No season directories found!", :red)
      exit 1
    end
    
    puts "Found #{season_dirs.length} season(s) to process"
    puts
    
    season_dirs.each do |season_dir|
      process_season(season_dir)
    end
    
    print_summary
  end
  
  private
  
  def find_season_directories
    Dir.glob(File.join(BASE_DIR, "season_*")).select { |d| File.directory?(d) }.sort
  end
  
  def process_season(season_dir)
    season_name = File.basename(season_dir)
    
    puts colorize("━" * 50, :yellow)
    puts colorize("📁 Processing #{season_name}", :yellow)
    puts colorize("━" * 50, :yellow)
    
    # Create season output directory
    output_dir = File.join(OUTPUT_BASE_DIR, season_name)
    FileUtils.mkdir_p(output_dir)
    
    # Find all MKV files
    mkv_files = Dir.glob(File.join(season_dir, "*.mkv")).sort
    
    if mkv_files.empty?
      puts colorize("  No MKV files found in #{season_name}", :red)
      return
    end
    
    puts "  Found #{mkv_files.length} episode(s)"
    puts
    
    mkv_files.each_with_index do |mkv_file, index|
      process_mkv(mkv_file, output_dir, index + 1, mkv_files.length)
    end
    
    puts
  end
  
  def process_mkv(mkv_file, output_dir, current, total)
    @stats[:total] += 1
    
    # Extract episode ID (e.g., S01E01)
    filename = File.basename(mkv_file)
    episode_id = filename[/S\d{2}E\d{2}/]
    
    unless episode_id
      puts colorize("  ✗ Could not extract episode ID from: #{filename}", :red)
      @stats[:errors] += 1
      return
    end
    
    output_file = File.join(output_dir, "#{episode_id}.wav")
    
    # Progress indicator
    progress = "[#{current}/#{total}]"
    
    # Skip if file exists
    if @skip_existing && File.exist?(output_file)
      size = human_readable_size(File.size(output_file))
      puts colorize("  #{progress} ⟳ Skipping #{episode_id} (already exists, #{size})", :yellow)
      @stats[:skipped] += 1
      return
    end
    
    print "  #{progress} ↓ Extracting #{episode_id}..."
    
    # Build ffmpeg command
    cmd = [
      'ffmpeg',
      '-i', mkv_file,
      '-vn',                      # no video
      '-acodec', 'pcm_s16le',     # 16-bit PCM WAV
      '-ar', @sample_rate.to_s,   # sample rate
      '-ac', @channels.to_s,      # audio channels
      output_file,
      '-y',                        # overwrite
      '-loglevel', 'error'
    ]
    
    # Execute ffmpeg
    success = run_command(cmd)
    
    if success && File.exist?(output_file)
      size = human_readable_size(File.size(output_file))
      duration = get_duration(output_file)
      print "\r" + " " * 80 + "\r"  # Clear line
      puts colorize("  #{progress} ✓ #{episode_id} extracted (#{size}, #{duration})", :green)
      @stats[:processed] += 1
    else
      print "\r" + " " * 80 + "\r"  # Clear line
      puts colorize("  #{progress} ✗ Error processing #{episode_id}", :red)
      @stats[:errors] += 1
    end
  end
  
  def run_command(cmd)
    _, stderr, status = Open3.capture3(*cmd)
    status.success?
  rescue => e
    puts colorize("\n  Error: #{e.message}", :red)
    false
  end
  
  def get_duration(file)
    cmd = [
      'ffprobe',
      '-v', 'error',
      '-show_entries', 'format=duration',
      '-of', 'default=noprint_wrappers=1:nokey=1',
      file
    ]
    
    stdout, = Open3.capture3(*cmd)
    seconds = stdout.to_f
    format_duration(seconds)
  rescue
    "unknown"
  end
  
  def format_duration(seconds)
    return "unknown" if seconds <= 0
    
    mins = (seconds / 60).to_i
    secs = (seconds % 60).to_i
    "#{mins}m #{secs}s"
  end
  
  def human_readable_size(size)
    units = ['B', 'KB', 'MB', 'GB']
    unit_index = 0
    size = size.to_f
    
    while size > 1024 && unit_index < units.length - 1
      size /= 1024.0
      unit_index += 1
    end
    
    "%.1f%s" % [size, units[unit_index]]
  end
  
  def colorize(text, color)
    "#{COLORS[color]}#{text}#{COLORS[:reset]}"
  end
  
  def print_summary
    puts colorize("=" * 50, :cyan)
    puts colorize("📊 Summary", :cyan)
    puts colorize("=" * 50, :cyan)
    
    puts "  Total episodes:     #{@stats[:total]}"
    puts colorize("  ✓ Processed:       #{@stats[:processed]}", :green) if @stats[:processed] > 0
    puts colorize("  ⟳ Skipped:         #{@stats[:skipped]}", :yellow) if @stats[:skipped] > 0
    puts colorize("  ✗ Errors:          #{@stats[:errors]}", :red) if @stats[:errors] > 0
    
    puts
    puts "Output directory: #{OUTPUT_BASE_DIR}"
    
    # Show total size
    if Dir.exist?(OUTPUT_BASE_DIR)
      total_size = Dir.glob(File.join(OUTPUT_BASE_DIR, "**/*.wav"))
                      .sum { |f| File.size(f) }
      puts "Total size: #{human_readable_size(total_size)}"
    end
  end
end

# Command-line interface
if __FILE__ == $0
  require 'optparse'
  
  options = {}
  
  OptionParser.new do |opts|
    opts.banner = "Usage: extract_audio.rb [options]"
    
    opts.on("-r", "--sample-rate RATE", Integer, "Sample rate (default: 16000)") do |r|
      options[:sample_rate] = r
    end
    
    opts.on("-c", "--channels N", Integer, "Audio channels (1=mono, 2=stereo, default: 1)") do |c|
      options[:channels] = c
    end
    
    opts.on("-f", "--force", "Process all files, don't skip existing") do
      options[:skip_existing] = false
    end
    
    opts.on("-h", "--help", "Show this help message") do
      puts opts
      exit
    end
  end.parse!
  
  extractor = LittleBearAudioExtractor.new(options)
  extractor.run
end
