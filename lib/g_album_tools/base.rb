require "logger"
require "json"
require "fileutils"
require "open3"
require "csv"
require "rchardet"

module GAlbumTools
  class Base
    SHOW_COMMAND = false
    LOG_FILE = "metadata_editor.log"

    attr_reader :logger, :verbose

    def initialize(options = {})
      @verbose = options[:verbose] || false
      @logger = Logger.new(options[:log_file] || LOG_FILE)
      @logger.level = options[:log_level] || Logger::INFO
    end

    def log(level, message, at_console: @verbose)
      case level
      when :info, :debug, :warn, :error, :fatal
        logger.send(level, message)
        puts message if at_console
      else
        logger.info(message)
        puts message if at_console
      end
    end

    def execute_command(cmd, log_result: true)
      log(:info, "Executing: #{cmd.join(" ")}") if SHOW_COMMAND

      stdout_str, stderr_str, status = Open3.capture3(*cmd)

      if log_result
        log(:info, "Result: #{stdout_str}") unless stdout_str.empty?
        log(:error, "Error: #{stderr_str}") unless stderr_str.empty? || stderr_str.include?("1 image files updated")
      end

      [stdout_str, stderr_str, status]
    end

    def clean_string(str)
      return nil if str.nil? || str.empty?

      str = str.scrub("?") # Replace any invalid UTF-8 sequences

      # Try to detect encoding if it looks like it might be non-UTF-8
      if str.match?(/[^\x00-\x7F]/) && !str.valid_encoding?
        cd = CharDet.detect(str)
        str = str.encode("UTF-8", cd["encoding"]) if cd["encoding"]
      end

      str
    end
  end
end
