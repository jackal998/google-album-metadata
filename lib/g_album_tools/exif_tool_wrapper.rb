require "open3"
require "rchardet"

module GAlbumTools
  class ExifToolWrapper
    attr_reader :logger, :show_command

    def initialize(logger, show_command = false)
      @logger = logger
      @show_command = show_command
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
