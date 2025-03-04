require "csv"
require "fileutils"

module GAlbumTools
  class ErrorFilesWorker
    attr_reader :destination_directory, :nested, :logger, :exiftool, :error_handler

    def initialize(destination_directory, logger, exiftool, nested = false)
      @destination_directory = destination_directory || "."
      @nested = nested
      @logger = logger
      @exiftool = exiftool
      @error_handler = ErrorHandler.new(logger, exiftool)
    end

    def process
      logger.info("Processing error files in #{destination_directory}")
      
      destination_directories.each do |dir|
        process_directory(dir)
      end
      
      logger.info("Error file processing completed")
    end

    private

    def process_directory(dir)
      logger.info("Processing errors in directory: #{dir}")
      
      # Read the output file for this directory
      rows = OutputFile.read_output_file(dir, logger)
      return logger.info("No output file found for #{dir}") if rows.empty?
      
      # Process each row with errors
      error_rows = rows.select { |row| row["Processed"] == "false" }
      logger.info("Found #{error_rows.size} errors to process in #{dir}")
      
      error_rows.each do |row|
        process_error_row(row, dir)
      end
    end

    def process_error_row(row, dir)
      media_file = row["Media File"]
      error_message = row["Errors"]
      
      logger.info("Processing error for file: #{media_file}")
      logger.info("Error message: #{error_message}")
      
      error_type = match_error(error_message)
      
      case error_type[:type]
      when "extension"
        logger.info("Handling extension error")
        handle_extension_error(media_file, error_type[:data])
      when "maker_notes"
        logger.info("Handling maker notes error")
        handle_maker_notes_error(media_file, dir)
      when "missing_metadata"
        logger.info("Handling missing metadata error")
        handle_missing_metadata_error(media_file, dir)
      when "truncated_media"
        logger.info("Handling truncated media error")
        # Nothing to do for truncated media, just log it
      else
        logger.info("Unknown error type, no special handling")
      end
    end

    def match_error(error_message)
      return {type: "missing_metadata"} if error_message == "No JSON file found."
      
      if (current_extension, expected_extension = error_message.match(/Error: Not a valid (\w+) \(looks more like a (\w+)\).*/)&.captures)
        {type: "extension", data: {current_extension: current_extension, expected_extension: expected_extension}}
      elsif error_message.match?(/Error: \[minor\] Maker notes could not be parsed/)
        {type: "maker_notes"}
      elsif error_message.match?(/Truncated mdat atom/)
        {type: "truncated_media"}
      else
        {type: "unknown"}
      end
    end

    def handle_extension_error(file_path, data)
      return unless File.exist?(file_path)
      
      # Create a new path with the correct extension
      new_file_path = file_path.sub(/\.#{data[:current_extension]}$/i, ".#{data[:expected_extension]}")
      
      logger.info("Renaming #{file_path} to #{new_file_path}")
      FileUtils.cp(file_path, new_file_path)
    end

    def handle_maker_notes_error(file_path, dir)
      return unless File.exist?(file_path)
      
      # Use ExifTool with "-m" flag to ignore minor errors
      cmd = ["exiftool", "-m", "-ext", File.extname(file_path)[1..-1], file_path]
      exiftool.execute_command(cmd)
    end

    def handle_missing_metadata_error(file_path, dir)
      # This would require more complex logic to find related metadata
      # For now, we'll just log it
      logger.info("Missing metadata for #{file_path}, manual review required")
    end

    def destination_directories
      if nested
        Dir.glob(File.join(destination_directory, "**/"))
      else
        [destination_directory]
      end
    end
  end
end
