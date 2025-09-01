#!/usr/bin/env ruby

require 'json'
require 'fileutils'

class TranscriptCleaner
  BASE_DIR = "/Users/jibrankalia/side/little_bear"
  TRANSCRIPTS_DIR = File.join(BASE_DIR, "transcripts")
  NOISE_PATTERNS = [
    /^\[Music\]$/i,
    /^\[Applause\]$/i,
    /^\[Laughter\]$/i,
    /^\[Sound\]$/i,
    /^\[Background music\]$/i,
    /^\[Silence\]$/i,
    /^\[Noise\]$/i,
    /^\[Inaudible\]$/i,
    /^\[Crosstalk\]$/i,
    /^\[.*music.*\]$/i,
    /^\[.*applause.*\]$/i,
    /^\[.*laughter.*\]$/i,
    /^\[.*background.*\]$/i,
    /^\([^)]*music[^)]*\)$/i,
    /^\([^)]*sound[^)]*\)$/i,
    /^\([^)]*noise[^)]*\)$/i,
    /^\([^)]*growling[^)]*\)$/i,
    /^\([^)]*laughing[^)]*\)$/i,
    /^\([^)]*sighing[^)]*\)$/i,
    /^\([^)]*crying[^)]*\)$/i,
    /^\([^)]*breathing[^)]*\)$/i,
    /^\([^)]*"[^"]*"\)$/i,
    /^\(.*\)$/i,
    /^um+$/i,
    /^uh+$/i,
    /^hmm+$/i,
    /^ah+$/i,
    /^oh+$/i,
    /^like$/i,
    /^you know$/i,
    /^I mean$/i,
    /^basically$/i,
    /^actually$/i,
    /^literally$/i
  ].freeze

  def initialize(options = {})
    @skip_existing = options[:skip_existing] != false
    @stats = {
      total: 0,
      processed: 0,
      skipped: 0,
      errors: 0
    }
  end

  def run
    puts "🧹 Cleaning Little Bear Transcripts"
    puts "=" * 50
    
    # Find and process all transcript files
    transcript_files = find_transcript_files
    
    if transcript_files.empty?
      puts "No transcript JSON files found in #{TRANSCRIPTS_DIR}!"
      exit 1
    end
    
    puts "Found #{transcript_files.length} transcript file(s) to clean"
    puts
    
    transcript_files.each_with_index do |file, index|
      process_transcript(file, index + 1, transcript_files.length)
    end
    
    print_summary
  end

  def clean_single_file(input_file, output_file = nil)
    output_file ||= input_file.gsub(/\.json$/, '_cleaned.json')
    process_transcript(input_file, 1, 1)
  end

  private

  def find_transcript_files
    Dir.glob(File.join(TRANSCRIPTS_DIR, "**/*.json")).sort
  end

  def process_transcript(file, current, total)
    @stats[:total] += 1
    
    filename = File.basename(file)
    output_file = file.gsub(/\.json$/, '_cleaned.json')
    
    # Progress indicator
    progress = "[#{current}/#{total}]"
    
    # Skip if file exists
    if @skip_existing && File.exist?(output_file)
      puts "  #{progress} ⟳ Skipping #{filename} (already cleaned)"
      @stats[:skipped] += 1
      return
    end
    
    print "  #{progress} 🧹 Cleaning #{filename}..."
    
    begin
      data = load_transcript(file)
      
      # Handle the transcript structure with full_text and segments
      if data.is_a?(Hash) && data['segments']
        original_segments = data['segments']
        original_count = original_segments.length
        cleaned_segments = remove_noise_segments(original_segments)
        
        # Clean the full_text as well
        cleaned_full_text = clean_full_text(data['full_text'] || '')
        
        # Create cleaned transcript structure
        cleaned_data = data.dup
        cleaned_data['segments'] = cleaned_segments
        cleaned_data['full_text'] = cleaned_full_text
        
        # Update metadata if it exists
        if cleaned_data['metadata']
          cleaned_data['metadata']['segment_count'] = cleaned_segments.length
          cleaned_data['metadata']['word_count'] = cleaned_segments.sum { |s| s['words'] || s['text'].split.length }
        end
        
        save_transcript(cleaned_data, output_file)
        
        removed_count = original_count - cleaned_segments.length
        print "\r" + " " * 80 + "\r"  # Clear line
        puts "  #{progress} ✓ #{filename} cleaned (#{original_count} → #{cleaned_segments.length} segments, removed #{removed_count})"
      else
        # Handle array format (fallback)
        original_count = data.length
        cleaned_data = remove_noise_segments(data)
        save_transcript(cleaned_data, output_file)
        
        removed_count = original_count - cleaned_data.length
        print "\r" + " " * 80 + "\r"  # Clear line
        puts "  #{progress} ✓ #{filename} cleaned (#{original_count} → #{cleaned_data.length} segments, removed #{removed_count})"
      end
      
      @stats[:processed] += 1
    rescue => e
      print "\r" + " " * 80 + "\r"  # Clear line
      puts "  #{progress} ✗ Error cleaning #{filename}: #{e.message}"
      @stats[:errors] += 1
    end
  end

  def load_transcript(file_path)
    JSON.parse(File.read(file_path))
  rescue JSON::ParserError => e
    raise "Error parsing JSON: #{e.message}"
  rescue Errno::ENOENT
    raise "File not found: #{file_path}"
  end

  def remove_noise_segments(segments)
    segments.reject do |segment|
      text = segment['text'].to_s.strip
      is_noise_pattern?(text) || is_too_short?(text) || is_only_punctuation?(text)
    end
  end

  def is_noise_pattern?(text)
    NOISE_PATTERNS.any? { |pattern| text.match?(pattern) }
  end

  def is_too_short?(text)
    text.length <= 2
  end

  def is_only_punctuation?(text)
    text.match?(/^[[:punct:]\s]*$/)
  end

  def clean_full_text(full_text)
    return '' if full_text.nil? || full_text.empty?
    
    cleaned_text = full_text.dup
    
    # Remove parenthetical expressions and bracketed content
    cleaned_text = cleaned_text.gsub(/\([^)]*\)/, ' ')  # Remove (anything)
    cleaned_text = cleaned_text.gsub(/\[[^\]]*\]/, ' ')  # Remove [anything]
    
    # Remove extra whitespace 
    cleaned_text = cleaned_text.gsub(/\s+/, ' ').strip
    
    # Split into words and filter out noise words and very short words
    words = cleaned_text.split(/\s+/)
    cleaned_words = words.reject do |word|
      word.length <= 2 || 
      word.match?(/^[[:punct:]]*$/) ||
      %w[um uh hmm ah oh like actually basically literally].include?(word.downcase) ||
      ['you know', 'i mean'].include?(word.downcase)
    end
    
    cleaned_words.join(' ')
  end

  def save_transcript(data, output_file)
    File.write(output_file, JSON.pretty_generate(data))
  end

  def print_summary
    puts "=" * 50
    puts "📊 Summary"
    puts "=" * 50
    
    puts "  Total files:        #{@stats[:total]}"
    puts "  ✓ Processed:        #{@stats[:processed]}" if @stats[:processed] > 0
    puts "  ⟳ Skipped:          #{@stats[:skipped]}" if @stats[:skipped] > 0
    puts "  ✗ Errors:           #{@stats[:errors]}" if @stats[:errors] > 0
    
    puts
    puts "Cleaned files saved with '_cleaned.json' suffix"
  end
end

# Command-line interface
if __FILE__ == $0
  require 'optparse'
  
  options = {}
  single_file_mode = false
  
  OptionParser.new do |opts|
    opts.banner = "Usage: ruby step_3_clean_transcript.rb [options] [input_file.json] [output_file.json]"
    
    opts.on("-f", "--force", "Process all files, don't skip existing") do
      options[:skip_existing] = false
    end
    
    opts.on("-s", "--single FILE", "Clean a single file instead of walking directories") do |file|
      single_file_mode = true
      options[:single_file] = file
    end
    
    opts.on("-h", "--help", "Show this help message") do
      puts opts
      puts
      puts "Examples:"
      puts "  ruby step_3_clean_transcript.rb                      # Clean all files in transcripts/"
      puts "  ruby step_3_clean_transcript.rb -s transcript.json   # Clean single file"
      puts "  ruby step_3_clean_transcript.rb -f                   # Force reprocess all files"
      exit
    end
  end.parse!
  
  cleaner = TranscriptCleaner.new(options)
  
  if single_file_mode || !ARGV.empty?
    # Single file mode
    input_file = options[:single_file] || ARGV[0]
    output_file = ARGV[1]
    
    if input_file.nil?
      puts "Error: No input file specified"
      exit 1
    end
    
    cleaner.clean_single_file(input_file, output_file)
  else
    # Directory walking mode
    cleaner.run
  end
end