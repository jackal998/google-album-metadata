require_relative "base"
require_relative "constants"

module GAlbumTools
  class FileProcessor < Base
    include Constants

    attr_reader :source_directory, :destination_directory, :processed_files, :create_output_csv

    def initialize(options = {})
      super(options)
      @source_directory = options[:source_directory]
      @destination_directory = options[:destination_directory]
      @processed_files = {}
      @create_output_csv = options[:create_output_csv] || false
      @offset_time = nil
    end

    def process
      return log(:error, "Source directory does not exist: #{source_directory}") unless Dir.exist?(source_directory)

      log(:info, "Processing files in directory: #{source_directory}", at_console: true)

      FileUtils.mkdir_p(destination_directory) unless Dir.exist?(destination_directory)

      load_offset_times

      source_directories = Dir.glob(File.join(source_directory, "**/"))
      source_directories.each do |dir|
        check_files(dir)
        next log(:info, "#{dir} No valid media found.") if processed_files[dir].empty?

        current_destination_directory = dir.gsub(source_directory, destination_directory)
        FileUtils.mkdir_p(current_destination_directory) unless Dir.exist?(current_destination_directory)

        process_directory(dir, current_destination_directory)
      end

      create_csv_output if create_output_csv
    end

    private

    def magic_file_path(file_path, live_photo: false)
      magic_path = File.join(
        File.dirname(file_path),
        ".metadata",
        "#{File.basename(file_path, ".*")}#{live_photo ? ".lp" : ""}.json"
      )

      magic_path
    end

    def check_files(dir)
      media_files = Dir.glob(File.join(dir, "*.{#{SUPPORTED_EXTENSIONS.join(",")}}")).select { |f| File.file?(f) }
      json_files = Dir.glob(File.join(dir, ".metadata", "*.json"))

      processed_files[dir] = []

      media_files.each do |file_path|
        json_path = fetch_json_file(file_path, json_files)

        if json_path
          processed_files[dir] << {
            media_file: file_path,
            json_file: json_path,
            data: read_json(json_path)
          }
        else
          log(:warn, "No metadata found for file: #{file_path}")
        end
      end
    end

    def fetch_json_file(file_path, json_files)
      match_file_path = magic_file_path(file_path, live_photo: live_photo?(file_path))
      json_files.find { |path| path == match_file_path }
    end

    def live_photo?(file_path)
      return false unless LIVE_PHOTO_EXTENSIONS.include?(File.extname(file_path).downcase.delete("."))

      live_photo_base = File.basename(file_path, ".*")
      matching_image = Dir.glob(File.join(File.dirname(file_path), "#{live_photo_base}.{#{IMAGE_EXTENSIONS.join(",")}}"))

      !matching_image.empty?
    end

    def read_json(json_path)
      JSON.parse(File.read(json_path), encoding: "UTF-8")
    end

    def load_offset_times
      @offset_time = CSV.read(OFFSET_TIMES_PATH, headers: true, encoding: "bom|utf-16le:utf-8").filter_map do |row|
        row.to_h.transform_keys(&:to_s)
      end
    rescue Errno::ENOENT
      log(:warn, "No offset times file found at #{OFFSET_TIMES_PATH}")
      @offset_time = []
    end

    def process_directory(dir, current_destination_directory)
      # This method should be implemented in child classes
      raise NotImplementedError, "Subclass must implement process_directory method"
    end

    def create_csv_output
      # This method should be implemented in child classes
      raise NotImplementedError, "Subclass must implement create_csv_output method"
    end
  end
end
