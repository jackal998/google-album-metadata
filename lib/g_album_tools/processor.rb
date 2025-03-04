require "fileutils"

module GAlbumTools
  class Processor
    LOG_FILE = "metadata_editor.log".freeze

    attr_reader :verbose, :source_directory, :destination_directory, :create_output_csv, 
                :processed_files, :logger, :exiftool, :file_detector, :metadata_processor, :error_handler

    def initialize(verbose, source_directory, destination_directory, create_output_csv)
      @verbose = verbose
      @source_directory = source_directory
      @destination_directory = destination_directory
      @processed_files = {}
      
      # Initialize helper classes
      @logger = Logger.new(LOG_FILE, verbose)
      @exiftool = ExifToolWrapper.new(@logger, false)
      @file_detector = FileDetector.new(@logger, @exiftool)
      @metadata_processor = MetadataProcessor.new(@logger, @exiftool)
      @error_handler = ErrorHandler.new(@logger, @exiftool)
      
      @create_output_csv = create_output_csv
    end

    def process
      return logger.error("Source directory does not exist: #{source_directory}") unless Dir.exist?(source_directory)

      logger.info("Processing files in directory: #{source_directory}", at_console: true)

      FileUtils.mkdir_p(destination_directory) unless Dir.exist?(destination_directory)

      source_directories = Dir.glob(File.join(source_directory, "**/"))
      source_directories.each do |dir|
        process_directory(dir)
      end

      logger.info("Processing completed.", at_console: true)
    end

    private

    def process_directory(dir)
      @processed_files[dir] = file_detector.check_directory(dir)
      return logger.info("#{dir} No valid media found.") if processed_files[dir].empty?

      current_destination_directory = dir.gsub(source_directory, destination_directory)
      FileUtils.mkdir_p(current_destination_directory) unless Dir.exist?(current_destination_directory)

      output_file = create_output_csv ? OutputFile.new(current_destination_directory, logger) : nil

      processed_files[dir].each do |file, info|
        process_file(file, info, current_destination_directory, output_file)
      end

      output_file&.close
    end

    def process_file(file, info, destination_directory, output_file)
      if info[:json_file]
        json_data = metadata_processor.read_json(info[:json_file])
        result = metadata_processor.update_metadata(file, json_data, destination_directory)

        if result[:success]
          info[:processed] = true 
          output_file&.write_success(file, info[:json_file], result[:messages])
        else
          output_file&.write_error(file, info[:json_file], result[:errors])
          # Handle errors based on error type
          error_result = error_handler.handle_error(file, result[:errors], destination_directory)
          logger.info("Error handled: #{error_result[:message]}")
        end
      else
        output_file&.write_missing_json(file)
        # Handle missing metadata case
        error_result = error_handler.handle_error(file, "No JSON file found", destination_directory)
        logger.info("Missing metadata handled: #{error_result[:message]}")
      end
    end
  end
end 
