require "fileutils"
require_relative "error_manager"

module GAlbumTools
  class Processor
    LOG_FILE = "metadata_editor.log".freeze

    attr_reader :verbose, :source_directory, :destination_directory, :create_output_csv,
      :logger, :exiftool, :file_detector, :metadata_processor, :error_manager

    def initialize(verbose, source_directory, destination_directory, create_output_csv)
      @verbose = verbose
      @source_directory = source_directory
      @destination_directory = destination_directory

      # Initialize helper classes
      @logger = Logger.new(LOG_FILE, verbose)
      @exiftool = ExifToolWrapper.new(@logger, false)
      @file_detector = FileDetector.new(@logger, @exiftool)
      @metadata_processor = MetadataProcessor.new(@logger, @exiftool)
      @error_manager = ErrorManager.new(@logger, @exiftool, @metadata_processor)

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
      files_with_json = file_detector.map_json_files(dir)
      return logger.info("#{dir} No valid media found.") if files_with_json.empty?

      target_directory = dir.gsub(source_directory, destination_directory)
      FileUtils.mkdir_p(target_directory) unless Dir.exist?(target_directory)

      output_file = create_output_csv ? OutputFile.new(target_directory, logger) : nil

      files_with_json.each do |file, json_file|
        process_file(file, json_file, target_directory, output_file)
      end

      output_file&.close
    end

    def process_file(file, json_file, target_directory, output_file)
      json_data = json_file ? metadata_processor.read_json(json_file) : nil

      file_details = {
        file: file,
        json_data: json_data,
        json_file: json_file,
        target_directory: target_directory
      }

      if json_data
        result = metadata_processor.update_metadata(**file_details)
        return output_file&.write_success(file, json_file, result[:messages]) if result[:success]

        output_file&.write_error(file, json_file, result[:errors])
        error_manager.handle_error(result[:errors], file_details)
      else
        output_file&.write_missing_json(file)
        error_manager.handle_error("No JSON file found", file_details)
      end
    end
  end
end
