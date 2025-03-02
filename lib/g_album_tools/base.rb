require "logger"
require "json"
require "fileutils"
require "open3"
require "csv"
require "rchardet"
require_relative "constants"

module GAlbumTools
  class Base
    include Constants

    SHOW_COMMAND = false
    LOG_FILE = "metadata_editor.log"

    attr_reader :logger, :verbose

    def initialize(options = {})
      @verbose = options[:verbose] || false
      @logger = Logger.new(options[:log_file] || LOG_FILE)
      @logger.level = options[:log_level] || Logger::INFO
    end

    # Logs a message at the specified level and optionally to the console
    # @param level [Symbol] The log level (:info, :debug, :warn, :error, :fatal)
    # @param message [String] The message to log
    # @param at_console [Boolean] Whether to also output to the console
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

    # Executes a shell command with error handling
    # @param cmd [Array<String>] The command and its arguments
    # @param log_result [Boolean] Whether to log the command output
    # @return [Array] stdout, stderr, status of the command
    def execute_command(cmd, log_result: true)
      log(:info, "Executing: #{cmd.join(" ")}") if SHOW_COMMAND

      stdout_str, stderr_str, status = Open3.capture3(*cmd)

      if log_result
        log(:info, "Result: #{stdout_str}") unless stdout_str.empty?
        log(:error, "Error: #{stderr_str}") unless stderr_str.empty? || stderr_str.include?("1 image files updated")
      end

      [stdout_str, stderr_str, status]
    end

    # Cleans a string by handling encoding issues
    # @param str [String] The string to clean
    # @return [String, nil] The cleaned string, or nil if input was nil/empty
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
