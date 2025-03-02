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
    def initialize(options = {})
      super(options)
      @destination_directory = options[:destination_directory]
      @nested = options[:nested] || false
      @handler_options = options
    end

    def process
      destination_directories.each do |dir|
        read_output_file(dir) do |row|
          next unless row["Processed"] == "false"

          error_info = ErrorTypes.categorize(row["Errors"].to_s)
          next if error_info.nil?

          handler_class = Object.const_get(ErrorTypes.handler_for(error_info[:type]))
          handler = handler_class.new(@handler_options.merge(
            row: row,
            error_data: error_info[:data]
          ))

          handler.handle
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
  end
end
