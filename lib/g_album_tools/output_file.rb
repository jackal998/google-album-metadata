require "csv"

module GAlbumTools
  class OutputFile
    attr_reader :file, :file_path, :logger

    def initialize(directory, logger)
      @logger = logger
      @file_path = build_file_path(directory)
      @file = File.new(file_path, "w")
      write_header
    end

    def write_header
      file.puts("Processed,Media File,JSON File,Messages,Errors")
    end

    def write_success(media_file, json_file, messages)
      file.puts("true,#{media_file},#{json_file},#{messages},")
    end

    def write_error(media_file, json_file, error_message)
      error_message = error_message.to_s.tr("\n", ";") if error_message
      file.puts("false,#{media_file},#{json_file},,#{error_message}")
    end

    def write_missing_json(media_file)
      file.puts("false,#{media_file},,,No JSON file found.")
    end

    def close
      file.close
    end

    def read_output_file
      unless File.exist?(file_path)
        logger&.info("No output file found for #{file_path}")
        return []
      end

      rows = []
      CSV.foreach(file_path, headers: true) do |row|
        rows << row
        yield row if block_given?
      end
      rows
    end

    def build_file_path(dir)
      File.join(File.dirname(dir), "#{File.basename(dir)}_output.csv")
    end
  end
end
