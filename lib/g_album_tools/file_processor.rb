require_relative "base"
require "json"
require "fileutils"

module GAlbumTools
  class FileProcessor < Base
    attr_reader :source_directory, :destination_directory, :processed_files, :offset_time

    def initialize(options = {})
      super
      @source_directory = options[:source_directory]
      @destination_directory = options[:destination_directory]
      @nested = options[:nested] || false
      @force = options[:force] || false
      @offset_file = options[:offset_file]
      @processed_files = {}
      @offset_time = []

      load_offset_times if @offset_file
    end

    # Process files in the source directory
    def process
      unless File.directory?(@source_directory)
        raise "Source directory does not exist: #{@source_directory}"
      end

      # Create destination directory if it doesn't exist
      FileUtils.mkdir_p(@destination_directory) unless File.directory?(@destination_directory)

      log(:info, "Processing files from #{@source_directory} to #{@destination_directory}")

      dirs = @nested ? Dir.glob(File.join(@source_directory, "**", "*")).select { |f| File.directory?(f) } : [@source_directory]

      dirs.each do |dir|
        process_directory(dir)
      end

      create_csv_output

      log(:info, "Processing complete")
    end

    # Get path to corresponding metadata file for a media file
    # @param file_path [String] Path to the media file
    # @return [String, nil] Path to the metadata file or nil if not found
    def metadata_file_path(file_path)
      # Google Photos uses .json files with the same base name for metadata
      base_name = File.basename(file_path, ".*")
      dir_name = File.dirname(file_path)

      # Try to find a matching JSON file
      json_file = find_json_file(dir_name, base_name)

      if json_file.nil?
        log(:warn, "No JSON file found for #{file_path}")
        return nil
      end

      json_file
    end

    # Check if files should be processed
    # @param dir [String] Directory containing the files
    # @return [Hash] Hash with directory as key and array of file info as value
    def check_files(dir)
      log(:info, "Checking files in #{dir}")

      @processed_files[dir] = []

      # Find all media files in the directory
      media_files = Dir.glob(File.join(dir, "*"))
        .select { |f| File.file?(f) }
        .select do |f|
          ext = File.extname(f).downcase
          IMAGE_EXTENSIONS.include?(ext) || VIDEO_EXTENSIONS.include?(ext)
        end

      media_files.each do |file|
        File.extname(file).downcase
        # Skip files that don't match allowed formats
        unless is_allowed_file_format?(file)
          log(:debug, "Skipping file with unsupported format: #{file}")
          next
        end

        is_live = live_photo?(file)
        json_file = metadata_file_path(file)

        if json_file
          data = read_json(json_file)
          @processed_files[dir] << {media_file: file, json_file: json_file, data: data, is_live_photo: is_live}
        else
          # Add without JSON data, will be handled as an error case
          @processed_files[dir] << {media_file: file, json_file: nil, data: {}, is_live_photo: is_live}
        end
      rescue => e
        log(:error, "Error processing file #{file}: #{e.message}")
      end

      log(:info, "Found #{@processed_files[dir].size} files to process in #{dir}")
      @processed_files
    end

    # Find corresponding JSON file for a media file
    # @param dir_name [String] Directory containing the files
    # @param base_name [String] Base name of the media file
    # @return [String, nil] Path to the JSON file or nil if not found
    def find_json_file(dir_name, base_name)
      # Try exact match first
      json_path = File.join(dir_name, "#{base_name}.json")
      return json_path if File.exist?(json_path)

      # Google sometimes adds a (1), (2), etc. to the filename, but the JSON keeps the original name
      # Try with different patterns
      ALLOWED_FILENAME_SUFFIXES.each do |suffix|
        base_without_suffix = base_name.gsub(/#{Regexp.escape(suffix)}$/, "")
        json_path = File.join(dir_name, "#{base_without_suffix}.json")
        return json_path if File.exist?(json_path)
      end

      nil
    end

    # Check if the file is part of a live photo
    # @param file_path [String] Path to the file
    # @return [Boolean] True if the file is part of a live photo
    def live_photo?(file_path)
      base_name = File.basename(file_path, ".*")
      dir_name = File.dirname(file_path)
      ext = File.extname(file_path).downcase

      # Live photos typically have paired image/video files with the same base name
      if IMAGE_EXTENSIONS.include?(ext)
        # If this is an image, check for a video with the same base name
        VIDEO_EXTENSIONS.each do |video_ext|
          video_path = File.join(dir_name, "#{base_name}#{video_ext}")
          return true if File.exist?(video_path)
        end
      elsif VIDEO_EXTENSIONS.include?(ext)
        # If this is a video, check for an image with the same base name
        IMAGE_EXTENSIONS.each do |image_ext|
          image_path = File.join(dir_name, "#{base_name}#{image_ext}")
          return true if File.exist?(image_path)
        end
      end

      false
    end

    # Read and parse JSON file
    # @param json_file [String] Path to the JSON file
    # @return [Hash] Parsed JSON data
    def read_json(json_file)
      json_content = File.read(json_file)
      JSON.parse(json_content)
    rescue JSON::ParserError => e
      log(:error, "Failed to parse JSON file #{json_file}: #{e.message}")
      {}
    rescue => e
      log(:error, "Failed to read JSON file #{json_file}: #{e.message}")
      {}
    end

    # Load offset times from CSV file
    def load_offset_times
      return unless @offset_file && File.exist?(@offset_file)

      begin
        CSV.foreach(@offset_file, headers: true) do |row|
          @offset_time << row.to_h
        end
        log(:info, "Loaded #{@offset_time.size} offset time entries")
      rescue => e
        log(:error, "Failed to load offset times from #{@offset_file}: #{e.message}")
      end
    end

    # Check if the file format is allowed
    # @param file_path [String] Path to the file
    # @return [Boolean] True if the file format is allowed
    def is_allowed_file_format?(file_path)
      ext = File.extname(file_path).downcase
      IMAGE_EXTENSIONS.include?(ext) || VIDEO_EXTENSIONS.include?(ext)
    end

    # Process a directory
    # This is a placeholder method to be overridden by subclasses
    # @param dir [String] Directory to process
    def process_directory(dir)
      check_files(dir)
    end

    # Create CSV output
    # This is a placeholder method to be overridden by subclasses
    def create_csv_output
      log(:info, "CSV output generation is handled by subclasses")
    end
  end
end
