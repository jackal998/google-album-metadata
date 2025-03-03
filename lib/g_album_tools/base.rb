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

    # Platform detection constants
    WINDOWS = RbConfig::CONFIG["host_os"] =~ /mswin|mingw|cygwin/
    MAC = RbConfig::CONFIG["host_os"] =~ /darwin/
    LINUX = RbConfig::CONFIG["host_os"] =~ /linux/

    attr_reader :logger, :verbose, :options

    def initialize(options = {})
      @options = options
      @verbose = options[:verbose] || false
      @logger = Logger.new(options[:log_file] || LOG_FILE)
      @logger.level = options[:log_level] || Logger::INFO
      @logger.formatter = proc do |severity, datetime, progname, msg|
        formatted_datetime = datetime.strftime("%Y-%m-%d %H:%M:%S")
        "[#{formatted_datetime}] #{severity}: #{msg}\n"
      end
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
      # Handle Windows-specific command adjustments
      if WINDOWS
        # Convert forward slashes to backslashes in paths for Windows tools that require it
        cmd = cmd.map do |arg|
          if arg.is_a?(String) && arg.include?("/") && !arg.start_with?("-")
            arg.tr("/", "\\")
          else
            arg
          end
        end

        # For Windows, ensure ExifTool is invoked correctly with .exe extension if needed
        if cmd[0] == "exiftool" && !cmd[0].end_with?(".exe")
          # First check if exiftool.exe exists in PATH
          exiftool_exe_exists = system("where exiftool.exe >nul 2>nul")
          cmd[0] = "exiftool.exe" if exiftool_exe_exists
        end
      end

      log(:info, "Executing: #{cmd.join(" ")}") if SHOW_COMMAND

      # Handle potential encoding issues, especially on Windows
      old_external_encoding = Encoding.default_external
      begin
        # Temporarily set UTF-8 as default encoding for command execution
        Encoding.default_external = Encoding::UTF_8 if WINDOWS
        stdout_str, stderr_str, status = Open3.capture3(*cmd)
      rescue => e
        log(:error, "Command execution failed: #{e.message}")
        return ["", "Command execution failed: #{e.message}", OpenStruct.new(success?: false)]
      ensure
        # Restore original encoding
        Encoding.default_external = old_external_encoding if WINDOWS
      end

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

    # Checks if ExifTool is installed and available
    # @return [Boolean] true if ExifTool is available
    def exiftool_available?
      # On Windows, we need to check both exiftool and exiftool.exe
      if is_windows?
        system("where exiftool > nul 2>&1") || system("where exiftool.exe > nul 2>&1")
      else
        # On Unix systems
        system("which exiftool > /dev/null 2>&1")
      end
    end

    # Gets system information for troubleshooting
    # @return [Hash] System information
    def system_info
      {
        ruby_version: RUBY_VERSION,
        ruby_platform: RUBY_PLATFORM,
        operating_system: RbConfig::CONFIG["host_os"],
        is_windows: is_windows?,
        is_mac: is_mac?,
        is_linux: is_linux?,
        exiftool_available: exiftool_available?,
        exiftool_version: exiftool_version
      }
    end

    # Gets ExifTool version
    # @return [String, nil] ExifTool version or nil if not available
    def exiftool_version
      if is_windows?
        # On Windows, redirect error output to NUL
        `exiftool -ver 2> nul`.strip
      else
        # On Unix systems
        `exiftool -ver 2>/dev/null`.strip
      end
    rescue
      nil
    end

    # Check if running on Windows
    # @return [Boolean] True if running on Windows
    def is_windows?
      RUBY_PLATFORM =~ /mswin|mingw|cygwin/ || RbConfig::CONFIG['host_os'] =~ /mswin|mingw|cygwin/
    end

    # Check if running on macOS
    # @return [Boolean] True if running on macOS
    def is_mac?
      RUBY_PLATFORM =~ /darwin/ || RbConfig::CONFIG['host_os'] =~ /darwin/
    end

    # Check if running on Linux
    # @return [Boolean] True if running on Linux
    def is_linux?
      RUBY_PLATFORM =~ /linux/ || RbConfig::CONFIG['host_os'] =~ /linux/
    end

    # Utility method to check path encoding and fix if necessary
    # @param path [String] Path to check and possibly fix
    # @return [String] Fixed path
    def fix_path_encoding(path)
      # Only attempt to fix on Windows with non-ASCII characters
      if is_windows? && path.encode("UTF-8").chars.any? { |c| c.ord > 127 }
        # Ensure consistent UTF-8 encoding for Windows paths with non-ASCII characters
        path.encode("UTF-8")
      else
        path
      end
    rescue
      # If encoding conversion fails, return original path
      path
    end
  end
end
