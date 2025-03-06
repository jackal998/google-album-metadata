require "csv"
require "fileutils"
require_relative "error_manager"

module GAlbumTools
  class ErrorFilesWorker
    attr_reader :destination_directory, :logger, :exiftool, :error_manager

    def initialize(destination_directory, logger, exiftool)
      @destination_directory = destination_directory || "."
      @logger = logger
      @exiftool = exiftool
      @error_manager = ErrorManager.new(logger, exiftool)
    end

    def process
      logger.info("Processing error files in #{destination_directory}")

      process_directory(destination_directory)

      logger.info("Error file processing completed")
    end

    private

    def process_directory(dir)
      # Read the output file for this directory
      rows = OutputFile.new(dir, logger).read_output_file
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

      return unless File.exist?(media_file)

      logger.info("Processing error for file: #{media_file}")
      logger.info("Error message: #{error_message}")

      # Use the error manager to handle the error
      result = error_manager.handle_error(media_file, error_message, dir)

      logger.info("Error handling result: #{result[:message]}")
    end
  end
end
