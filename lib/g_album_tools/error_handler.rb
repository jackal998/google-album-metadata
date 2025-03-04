require "fileutils"

module GAlbumTools
  class ErrorHandler
    ERROR_TYPES = {
      missing_metadata: /No JSON file found|No metadata found/,
      maker_notes: /Error: \[minor\] Maker notes could not be parsed/,
      incorrect_extension: /Not a valid (\w+) \(looks more like a (\w+)\)/,
      truncated_media: /Truncated mdat atom/
    }.freeze

    attr_reader :logger, :exiftool

    def initialize(logger, exiftool)
      @logger = logger
      @exiftool = exiftool
    end

    def handle_error(file_path, error_message, destination_directory)
      error_type = identify_error_type(error_message)
      
      logger.info("Handling error type: #{error_type} for file: #{file_path}")
      
      case error_type
      when :missing_metadata
        handle_missing_metadata(file_path, destination_directory)
      when :maker_notes
        handle_maker_notes(file_path, destination_directory)
      when :incorrect_extension
        handle_incorrect_extension(file_path, error_message, destination_directory)
      when :truncated_media
        handle_truncated_media(file_path, destination_directory)
      else
        handle_unknown_error(file_path, error_message, destination_directory)
      end
    end

    private

    def identify_error_type(error_message)
      return :missing_metadata unless error_message
      
      ERROR_TYPES.each do |type, pattern|
        return type if error_message.match?(pattern)
      end
      :unknown
    end

    def handle_missing_metadata(file_path, destination_directory)
      logger.info("Handling missing metadata for #{file_path}")
      
      # First, check if it's a live photo (we'd need a reference to FileDetector)
      # This is a simplified version - in a real implementation, we'd check if it's a live photo
      # and try to find the related photo's metadata
      
      # For now, we'll simply copy the file to the destination
      copy_file_to_destination(file_path, destination_directory)
      
      { processed: false, message: "No metadata available, file copied to destination" }
    end

    def handle_maker_notes(file_path, destination_directory)
      logger.info("Handling maker notes error for #{file_path}")
      destination_path = File.join(destination_directory, File.basename(file_path))
      
      # Use -m flag to ignore minor errors
      cmd = ["exiftool", "-m", "-o", destination_path, file_path]
      _, stderr_str, status = exiftool.execute_command(cmd)
      
      if status.success?
        { processed: true, message: "Fixed maker notes issue" }
      else
        copy_file_to_destination(file_path, destination_directory)
        { processed: false, message: "Failed to fix maker notes: #{stderr_str}" }
      end
    end

    def handle_incorrect_extension(file_path, error_message, destination_directory)
      logger.info("Handling incorrect extension for #{file_path}")
      match = error_message.match(/Not a valid (\w+) \(looks more like a (\w+)\)/)
      return { processed: false, message: "Failed to parse extension error" } unless match
      
      current_extension, expected_extension = match.captures
      logger.info("Fixing extension from #{current_extension} to #{expected_extension}")
      
      # Create a temporary file with correct extension
      temp_dir = File.dirname(file_path)
      temp_file = File.join(temp_dir, "#{File.basename(file_path, ".*")}.#{expected_extension.downcase}")
      FileUtils.cp(file_path, temp_file)
      
      # Copy the corrected file to destination
      destination_path = File.join(destination_directory, File.basename(temp_file))
      FileUtils.cp(temp_file, destination_path)
      
      # Clean up the temporary file (optional, depending on policy)
      FileUtils.rm(temp_file)
      
      { processed: true, message: "Updated file extension from #{current_extension} to #{expected_extension}" }
    end

    def handle_truncated_media(file_path, destination_directory)
      logger.info("Handling truncated media for #{file_path}")
      # Just copy the file to destination and mark as not processed
      copy_file_to_destination(file_path, destination_directory)
      { processed: false, message: "File appears to be corrupted (truncated media)" }
    end

    def handle_unknown_error(file_path, error_message, destination_directory)
      logger.info("Handling unknown error for #{file_path}: #{error_message}")
      copy_file_to_destination(file_path, destination_directory)
      { processed: false, message: "Unknown error: #{error_message}" }
    end

    def copy_file_to_destination(file_path, destination_directory)
      destination_path = File.join(destination_directory, File.basename(file_path))
      FileUtils.cp(file_path, destination_path)
    end
  end
end 
