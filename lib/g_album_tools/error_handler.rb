require_relative "base"
require_relative "error_types"
require_relative "handlers/extension_handler"
require_relative "handlers/metadata_handler"
require_relative "handlers/truncated_media_handler"
require_relative "handlers/maker_notes_handler"
require_relative "handlers/default_handler"
require "csv"

module GAlbumTools
  class ErrorHandler < Base
    include ErrorTypes

    attr_reader :errors, :fixed_errors

    def initialize(options = {})
      super
      @destination_directory = options[:destination_directory]
      @nested = options[:nested] || false
      @handler_options = options
      @errors = []
      @fixed_errors = {
        no_json: 0,
        unknown_pattern: 0,
        live_photo_missing_part: 0,
        invalid_or_truncated: 0,
        total: 0
      }
    end

    # Process and fix errors found in destination directories
    # This is the main entry point for the fix-errors command
    def process
      log(:info, "Fixing errors in destination directories...")

      # Build list of directories to process
      dirs = destination_directories
      log(:info, "Found #{dirs.size} directories to process")

      # Process each directory
      dirs.each do |dir|
        log(:info, "Processing directory: #{dir}")
        process_directory(dir)
      end

      # Output summary
      log(:info, "Fixed errors summary:")
      log(:info, "  No JSON: #{@fixed_errors[:no_json]}")
      log(:info, "  Unknown pattern: #{@fixed_errors[:unknown_pattern]}")
      log(:info, "  Live photo missing part: #{@fixed_errors[:live_photo_missing_part]}")
      log(:info, "  Invalid or truncated: #{@fixed_errors[:invalid_or_truncated]}")
      log(:info, "  Total fixed: #{@fixed_errors[:total]}")
    end

    # Process a single directory
    # @param dir [String] Directory to process
    def process_directory(dir)
      output_file = build_output_file_path(dir)

      unless File.exist?(output_file)
        log(:info, "No output file found for #{dir}")
        return
      end

      log(:info, "Reading output file: #{output_file}")
      processed = 0

      CSV.foreach(output_file, headers: true) do |row|
        next unless row["Processed"] == "false"

        log(:info, "Processing error for file: #{row["Media File"]}")
        error_type = categorize_error(row["Errors"].to_s)

        next if error_type == :unknown

        if handle_error(row, error_type)
          processed += 1
          update_fixed_error_count(error_type)
          update_output_file(output_file, row)
        end
      end

      log(:info, "Processed #{processed} errors in #{dir}")
    end

    # Load errors from CSV files
    # @param csv_files [Array<String>] List of CSV files to load
    # @return [Array<Hash>] List of errors loaded from CSV files
    def load_errors_from_csv(csv_files)
      loaded = 0
      log(:info, "Loading errors from #{csv_files.size} CSV files...")

      csv_files.each do |csv_file|
        CSV.foreach(csv_file, headers: true) do |row|
          next if row["Processed"] == "true" || row["Errors"].nil? || row["Errors"].empty?

          @errors << {
            file: row["Media File"],
            destination: row["Destination File"],
            error: row["Errors"],
            csv_file: csv_file,
            error_type: categorize_error(row["Errors"])
          }
          loaded += 1
        end
      rescue => e
        log(:error, "Failed to process CSV file #{csv_file}: #{e.message}")
      end

      log(:info, "Loaded #{loaded} errors from CSV files")
      @errors
    end

    # Get error statistics
    # @param errors [Array<Hash>] List of errors
    # @return [Hash] Statistics for error types
    def error_stats(errors)
      stats = {
        no_json: 0,
        unknown_pattern: 0,
        live_photo_missing_part: 0,
        invalid_or_truncated: 0,
        unknown: 0,
        total: 0
      }

      errors.each do |error|
        stats[error[:error_type]] += 1
        stats[:total] += 1
      end

      stats
    end

    private

    attr_reader :destination_directory, :nested

    # Get list of directories to process
    # @return [Array<String>] List of directories
    def destination_directories
      if nested
        Dir.glob(File.join(destination_directory, "**/"))
      else
        [destination_directory]
      end
    end

    # Build output file path for a directory
    # @param dir [String] Directory
    # @return [String] Output file path
    def build_output_file_path(dir)
      File.join(File.dirname(dir), "#{File.basename(dir)}_output.csv")
    end

    # Handle an error
    # @param row [CSV::Row] CSV row with error information
    # @param error_type [Symbol] Type of error
    # @return [Boolean] True if error was handled successfully
    def handle_error(row, error_type)
      log(:info, "Handling error type: #{error_type} for #{row["Media File"]}")

      # Get appropriate handler class
      handler_class = get_handler_class(error_type)
      handler = handler_class.new(@handler_options.merge(
        row: row,
        error_data: extract_error_data(row["Errors"], error_type)
      ))

      # Process the error
      result = handler.handle

      if result
        log(:info, "Successfully handled error for #{row["Media File"]}")
      else
        log(:warn, "Failed to handle error for #{row["Media File"]}")
      end

      result
    end

    # Extract additional data from error message
    # @param error_msg [String] Error message
    # @param error_type [Symbol] Type of error
    # @return [Hash] Extracted data
    def extract_error_data(error_msg, error_type)
      case error_type
      when :unknown_pattern
        # Extract current and expected extension
        if error_msg =~ /expected:\s*(\w+)/i
          {expected_extension: $1}
        else
          {}
        end
      else
        {}
      end
    end

    # Update the fixed error count
    # @param error_type [Symbol] Type of error
    def update_fixed_error_count(error_type)
      @fixed_errors[error_type] += 1
      @fixed_errors[:total] += 1
    end

    # Update the output file to mark error as fixed
    # @param output_file [String] Output file path
    # @param row [CSV::Row] Row to update
    def update_output_file(output_file, row)
      # Read the entire file
      rows = []
      CSV.foreach(output_file, headers: true) do |r|
        rows << r
      end

      # Find and update the matching row
      rows.each do |r|
        if r["Media File"] == row["Media File"]
          r["Processed"] = "true"
          r["Errors"] = "Fixed: #{r["Errors"]}"
        end
      end

      # Write the updated file
      CSV.open(output_file, "w") do |csv|
        csv << rows.first.headers
        rows.each { |r| csv << r }
      end
    end

    # Get the appropriate handler class for an error type
    # @param error_type [Symbol] The error type
    # @return [Class] The handler class
    def get_handler_class(error_type)
      case error_type
      when :no_json
        Handlers::MetadataHandler
      when :unknown_pattern
        Handlers::ExtensionHandler
      when :live_photo_missing_part
        Handlers::MetadataHandler
      when :invalid_or_truncated
        Handlers::TruncatedMediaHandler
      else
        Handlers::DefaultHandler
      end
    end
  end
end
