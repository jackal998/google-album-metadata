require "open3"
require "rchardet"

module GAlbumTools
  class ExifToolWrapper
    DEFAULT_OFFSET_TIME = "+08:00"

    attr_reader :logger, :show_command

    def initialize(logger, show_command = false)
      @logger = logger
      @show_command = show_command
      @offset_time_cache = {}
    end

    def execute_command(cmd, log_result: true)
      logger.info("Executing: #{cmd.join(" ")}") if show_command

      stdout_str, stderr_str, status = Open3.capture3(*cmd)

      stdout_str = clean_string(stdout_str)
      stderr_str = clean_string(stderr_str)

      if log_result
        status.success? ? logger.info("Success: #{stdout_str} #{cmd[2]}") : logger.error("Failed: #{stderr_str}")
      end

      [stdout_str, stderr_str, status]
    end

    def get_duration(file_path)
      cmd = ["exiftool", "-duration", file_path]
      stdout_str, _, _ = execute_command(cmd, log_result: false)

      stdout_str.match(/Duration *: (\d+(\.\d+)?)/)[1].to_f
    rescue NoMethodError => e
      logger.error("Failed to get duration for #{file_path}, #{stdout_str}, #{e.message}")
      nil
    end

    def get_offset_time(file_path)
      # Return cached value if available
      return @offset_time_cache[file_path] if @offset_time_cache.key?(file_path)
      @offset_time_cache[file_path] = DEFAULT_OFFSET_TIME

      # Extract OffsetTime, OffsetTimeOriginal, and OffsetTimeDigitized
      cmd = ["exiftool", "-fast", "-ee", "-OffsetTimeOriginal", "-OffsetTimeDigitized", "-OffsetTime", file_path]
      stdout_str, _, status = execute_command(cmd, log_result: false)
      
      if status.success? && stdout_str
        offset_times = stdout_str.split("\n").filter_map do |line|
          line.match(/Offset Time \w* *: (.+0)$/)[1]
        end
        @offset_time_cache[file_path] = offset_times.first
      end
    rescue => e
      logger.error("Failed to get offset time for #{file_path}: #{e.message}")
    ensure
      @offset_time_cache[file_path]
    end

    def update_file_extension(file_path, current_extension, expected_extension)
      cmd = [
        "exiftool",
        "-ext",
        current_extension.downcase,
        "-FileName=#{File.basename(file_path, ".*")}.#{expected_extension.downcase}",
        file_path
      ]
      
      execute_command(cmd)
    end

    def update_metadata(file_path, exif_args, destination_path)
      return {} if exif_args.empty?

      cmd = ["exiftool", "-o", destination_path, *exif_args, file_path]
      stdout_str, stderr_str, status = execute_command(cmd)

      {
        success: status.success?,
        errors: stderr_str&.tr("\n", ";"),
        messages: stdout_str&.tr("\n", ";")
      }
    end

    private

    def clean_string(str)
      return if str.nil? || str.empty?

      encoding = CharDet.detect(str)["encoding"]
      str.force_encoding(encoding).encode("UTF-8").strip
    end
  end
end 
