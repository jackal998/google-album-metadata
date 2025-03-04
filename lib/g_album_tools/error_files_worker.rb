require "csv"

module GAlbumTools
  class ErrorFilesWorker
    def initialize(destination_directory, nested = false)
      # default destination directory for testing
      @destination_directory = destination_directory || "//LinXiaoYun/home/Photos/Takeout/Google 相簿/測試"
      @nested = nested
    end

    def process
      destination_directories.each do |dir|
        OutputFile.read_output_file(dir) do |row|
          next unless row["Processed"] == "false"

          error_info = match_error(row)
          case error_info[:type]
          when "extension"
            ExtensionUpdater.new(row, error_info[:data]).call
          end

        end
      end
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

    def match_error(row)
      if (current_extension, expected_extension = row["Errors"].match(/Error: Not a valid (\w+) \(looks more like a (\w+)\).*/)&.captures)
        {type: "extension", data: {current_extension: current_extension, expected_extension: expected_extension}}
      end
    end
  end
end
