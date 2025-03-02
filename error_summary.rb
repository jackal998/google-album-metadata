#!/usr/bin/env ruby
require 'csv'
require 'set'

class ErrorSummary
  def initialize(base_path)
    @base_path = base_path
    @error_types = Hash.new(0)
    @error_files = Hash.new { |h, k| h[k] = [] }
    @total_files = 0
    @failed_files = 0
  end

  def analyze
    csv_files = Dir.glob(File.join(@base_path, "*_output.csv"))
    puts "Found #{csv_files.size} CSV files to analyze..."

    csv_files.each do |file|
      analyze_file(file)
    end

    print_summary
  end

  private

  def analyze_file(file)
    begin
      puts "Analyzing: #{File.basename(file)}"
      CSV.foreach(file, headers: true) do |row|
        @total_files += 1

        if row["Processed"]&.downcase == "false"
          @failed_files += 1
          error_msg = row["Errors"].to_s
          error_type = categorize_error(error_msg)

          @error_types[error_type] += 1
          @error_files[error_type] << {
            file: row["Media File"],
            error: error_msg,
            csv: File.basename(file)
          }
        end
      end
    rescue => e
      puts "Error analyzing file #{file}: #{e.message}"
    end
  end

  def categorize_error(error_msg)
    return "No error message" if error_msg.nil? || error_msg.empty?

    # Common error patterns
    case error_msg
    when /Truncated mdat atom/i
      "Truncated media data atom"
    when /Not a valid (\w+) \(looks more like a (\w+)\)/i
      "Incorrect file extension (#{$1} vs #{$2})"
    when /Failed to process.*encoding/i
      "Encoding error"
    when /Not a valid (\w+) file/i
      "Invalid file format (#{$1})"
    when /No metadata found/i
      "Missing metadata"
    when /Failed to copy file/i
      "File copy failure"
    when /Out of memory/i
      "Memory error"
    when /Error executing command/i
      "Command execution error"
    when /JSON parse error/i
      "JSON parsing failure"
    else
      # Extract first 30 chars for other errors
      "Other: #{error_msg[0..30]}..."
    end
  end

  def print_summary
    puts "\n==============================================="
    puts "ERROR SUMMARY REPORT"
    puts "==============================================="
    puts "Total files processed: #{@total_files}"
    puts "Failed files: #{@failed_files} (#{(@failed_files.to_f / @total_files * 100).round(2)}%)"
    puts "\nError Types:"
    puts "-----------------------------------------------"

    @error_types.sort_by { |_, count| -count }.each do |type, count|
      puts "#{type}: #{count} files (#{(count.to_f / @failed_files * 100).round(2)}%)"
    end

    puts "\nSample Files for Each Error Type:"
    puts "-----------------------------------------------"
    @error_types.keys.sort.each do |type|
      puts "\n#{type}:"
      @error_files[type].first(3).each do |error|
        puts "  - #{File.basename(error[:file])}: #{error[:error][0..80]}"
      end

      if @error_files[type].size > 3
        puts "  ... and #{@error_files[type].size - 3} more files"
      end
    end
  end
end

# Run the analysis
base_path = "/Volumes/home/Photos/Takeout/Google 相簿/"
ErrorSummary.new(base_path).analyze
