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
      super(options)
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

    def process
      destination_directories.each do |dir|
        read_output_file(dir) do |row|
          next unless row["Processed"] == "false"

          error_info = { type: categorize_error(row["Errors"].to_s) }
          next if error_info[:type] == :unknown

          handler_class = get_handler_class(error_info[:type])
          handler = handler_class.new(@handler_options.merge(
            row: row,
            error_data: nil
          ))

          handler.handle
        end
      end
    end

    # Load errors from CSV files
    # @param csv_files [Array<String>] List of CSV files to load
    # @return [Array<Hash>] List of errors loaded from CSV files
    def load_errors_from_csv(csv_files)
      loaded = 0
      log(:info, "Loading errors from #{csv_files.size} CSV files...")

      csv_files.each do |csv_file|
        begin
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
      end

      log(:info, "Loaded #{loaded} errors from CSV files")
      @errors
    end

    # Fix errors in files
    # @param destination_dir [String] Destination directory for fixed files
    def fix_errors(destination_dir)
      log(:info, "Fixing errors for #{@errors.size} files...")

      @errors.each do |error|
        begin
          case error[:error_type]
          when :no_json
            fix_no_json_error(error, destination_dir)
          when :unknown_pattern
            fix_unknown_pattern_error(error, destination_dir)
          when :live_photo_missing_part
            fix_live_photo_missing_part_error(error, destination_dir)
          when :invalid_or_truncated
            fix_invalid_or_truncated_error(error, destination_dir)
          else
            log(:warn, "No handler for error type: #{error[:error_type]} - #{error[:file]}")
          end
        rescue => e
          log(:error, "Failed to fix error for #{error[:file]}: #{e.message}")
        end
      end

      log(:info, "Fixed errors summary:")
      log(:info, "  No JSON: #{@fixed_errors[:no_json]}")
      log(:info, "  Unknown pattern: #{@fixed_errors[:unknown_pattern]}")
      log(:info, "  Live photo missing part: #{@fixed_errors[:live_photo_missing_part]}")
      log(:info, "  Invalid or truncated: #{@fixed_errors[:invalid_or_truncated]}")
      log(:info, "  Total fixed: #{@fixed_errors[:total]}")
    end

    private

    attr_reader :destination_directory, :nested

    def destination_directories
      if nested
        Dir.glob(File.join(destination_directory, "**/"))
      else
        [destination_directory]
      end
    end

    def read_output_file(dir)
      file_path = build_output_file_path(dir)

      unless File.exist?(file_path)
        log(:info, "No output file found for #{dir}")
        return
      end

      CSV.foreach(file_path, headers: true) do |row|
        yield row
      end
    end

    def build_output_file_path(dir)
      File.join(File.dirname(dir), "#{File.basename(dir)}_output.csv")
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

    # Fix "No JSON file found" error
    # @param error [Hash] Error information
    # @param destination_dir [String] Destination directory for fixed files
    def fix_no_json_error(error, destination_dir)
      file_path = error[:file]
      destination_file = File.join(destination_dir, File.basename(file_path))

      unless File.exist?(file_path)
        log(:error, "Source file does not exist: #{file_path}")
        return
      end

      # Create destination directory if it doesn't exist
      FileUtils.mkdir_p(File.dirname(destination_file))

      # Copy file to destination
      FileUtils.cp(file_path, destination_file)

      log(:info, "Copied file without metadata: #{file_path} -> #{destination_file}")

      @fixed_errors[:no_json] += 1
      @fixed_errors[:total] += 1
    end

    # Fix "Unknown filename pattern" error
    # @param error [Hash] Error information
    # @param destination_dir [String] Destination directory for fixed files
    def fix_unknown_pattern_error(error, destination_dir)
      file_path = error[:file]
      destination_file = File.join(destination_dir, File.basename(file_path))

      unless File.exist?(file_path)
        log(:error, "Source file does not exist: #{file_path}")
        return
      end

      # Create destination directory if it doesn't exist
      FileUtils.mkdir_p(File.dirname(destination_file))

      # Copy file to destination
      FileUtils.cp(file_path, destination_file)

      log(:info, "Copied file with unknown pattern: #{file_path} -> #{destination_file}")

      @fixed_errors[:unknown_pattern] += 1
      @fixed_errors[:total] += 1
    end

    # Fix "Live photo missing part" error
    # @param error [Hash] Error information
    # @param destination_dir [String] Destination directory for fixed files
    def fix_live_photo_missing_part_error(error, destination_dir)
      file_path = error[:file]
      destination_file = File.join(destination_dir, File.basename(file_path))

      unless File.exist?(file_path)
        log(:error, "Source file does not exist: #{file_path}")
        return
      end

      # Create destination directory if it doesn't exist
      FileUtils.mkdir_p(File.dirname(destination_file))

      # Copy file to destination
      FileUtils.cp(file_path, destination_file)

      log(:info, "Copied live photo with missing part: #{file_path} -> #{destination_file}")

      @fixed_errors[:live_photo_missing_part] += 1
      @fixed_errors[:total] += 1
    end

    # Fix "Invalid or truncated file" error
    # @param error [Hash] Error information
    # @param destination_dir [String] Destination directory for fixed files
    def fix_invalid_or_truncated_error(error, destination_dir)
      # For invalid or truncated files, we don't process them
      # Just log that they were skipped
      log(:info, "Skipped invalid or truncated file: #{error[:file]}")

      @fixed_errors[:invalid_or_truncated] += 1
      @fixed_errors[:total] += 1
    end
  end
end
