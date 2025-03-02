require "optparse"
require_relative "version"
require_relative "file_processor"
require_relative "metadata_processor"
require_relative "error_handler"

module GAlbumTools
  class CLI < Base
    attr_reader :options, :parser

    def initialize
      @options = {
        verbose: false,
        nested: false,
        force: false,
        no_csv: false
      }
      super(@options)
    end

    # Parse command line arguments
    # @param args [Array<String>] Command line arguments
    # @return [Hash] Parsed options
    def parse(args)
      @parser = OptionParser.new do |opts|
        opts.banner = "Usage: g_album_tool [options] COMMAND [args]"
        opts.separator ""

        opts.separator "Commands:"
        opts.separator "  process SOURCE_DIR DEST_DIR  Process files from SOURCE_DIR and save to DEST_DIR"
        opts.separator "  fix-errors DEST_DIR          Fix errors in already processed files"
        opts.separator "  analyze CSV_DIR              Analyze error CSV files in CSV_DIR (additional utility)"
        opts.separator "  info                         Display system information for troubleshooting"
        opts.separator ""

        opts.separator "Options:"
        opts.on("-v", "--verbose", "Run verbosely") do
          @options[:verbose] = true
        end

        opts.on("-n", "--nested", "Process nested directories") do
          @options[:nested] = true
        end

        opts.on("--no-csv", "Disable CSV output file creation") do
          @options[:no_csv] = true
        end

        opts.on("-o", "--offset-file FILE", "CSV file with offset times") do |file|
          @options[:offset_file] = file
        end

        opts.on("--version", "Show version") do
          puts "Google Album Metadata Tool v#{VERSION}"
          exit
        end

        opts.on_tail("-h", "--help", "Show this message") do
          puts opts
          exit
        end
      end

      @parser.parse!(args)
      @command = args.shift
      @command_args = args

      validate_args

      @options
    end

    # Run the command with the parsed options
    def run
      # Perform dependency check for commands that require ExifTool
      if %w[process fix-errors].include?(@command) && !exiftool_available?
        log(:error, "ERROR: ExifTool is not installed or not available in your PATH", at_console: true)
        log(:error, "This tool requires ExifTool to function properly.", at_console: true)
        log(:error, "Please install ExifTool:", at_console: true)
        log(:error, "  - Mac: brew install exiftool", at_console: true)
        log(:error, "  - Linux: apt install libimage-exiftool-perl or equivalent", at_console: true)
        log(:error, "  - Windows: Download from https://exiftool.org/", at_console: true)
        log(:error, "    and ensure it's in your PATH", at_console: true)
        exit 1
      end

      case @command
      when "process"
        process_command
      when "analyze"
        analyze_command
      when "fix-errors"
        fix_errors_command
      when "info"
        show_info_command
      else
        puts @parser
        exit 1
      end
    end

    private

    # Validate command line arguments
    def validate_args
      case @command
      when "process"
        if @command_args.size != 2
          puts "Error: 'process' command requires SOURCE_DIR and DESTINATION_DIR"
          puts @parser
          exit 1
        end
      when "analyze"
        if @command_args.size != 1
          puts "Error: 'analyze' command requires CSV_DIR"
          puts @parser
          exit 1
        end
      when "fix-errors"
        if @command_args.size != 1
          puts "Error: 'fix-errors' command requires DEST_DIR"
          puts @parser
          exit 1
        end
      when "info"
        # No arguments needed
      when nil
        puts "Error: No command specified"
        puts @parser
        exit 1
      else
        puts "Error: Unknown command '#{@command}'"
        puts @parser
        exit 1
      end
    end

    # Process command implementation
    def process_command
      source_dir = @command_args[0]
      destination_dir = @command_args[1]

      processor = MetadataProcessor.new(
        source_directory: source_dir,
        destination_directory: destination_dir,
        nested: @options[:nested],
        verbose: @options[:verbose],
        force: @options[:force],
        offset_file: @options[:offset_file],
        no_csv: @options[:no_csv]
      )

      processor.process
    end

    # Analyze command implementation
    def analyze_command
      csv_dir = @command_args[0]

      # Find all CSV files in the specified directory
      csv_files = Dir.glob(File.join(csv_dir, "**", "*_output.csv"))

      if csv_files.empty?
        puts "No CSV files found in #{csv_dir}"
        exit 1
      end

      error_handler = ErrorHandler.new(verbose: @options[:verbose])
      errors = error_handler.load_errors_from_csv(csv_files)

      if errors.empty?
        puts "No errors found in CSV files"
        exit 0
      end

      stats = error_handler.error_stats(errors)

      puts "Error Analysis Summary:"
      puts "  Total files analyzed: #{stats[:total]}"
      puts "  No JSON errors: #{stats[:no_json]}"
      puts "  Unknown pattern errors: #{stats[:unknown_pattern]}"
      puts "  Live photo missing part errors: #{stats[:live_photo_missing_part]}"
      puts "  Invalid or truncated errors: #{stats[:invalid_or_truncated]}"
      puts "  Maker notes errors: #{stats[:maker_notes]}" if stats[:maker_notes]
      puts "  Unknown errors: #{stats[:unknown]}"
    end

    # Fix errors command implementation
    def fix_errors_command
      dest_dir = @command_args[0]

      # Updated to match spec.md, using destination directory as both
      # source and destination. Files will be fixed in place.
      error_handler = ErrorHandler.new(
        destination_directory: dest_dir,
        nested: @options[:nested],
        verbose: @options[:verbose]
      )

      error_handler.process
    end

    # Show system info command implementation
    def show_info_command
      info = system_info

      puts "Google Album Metadata Tool v#{VERSION}"
      puts ""
      puts "System Information:"
      puts "  Ruby version: #{info[:ruby_version]}"
      puts "  Ruby platform: #{info[:ruby_platform]}"
      puts "  Operating system: #{info[:operating_system]}"
      puts "  Platform: #{(info[:is_windows] ? 'Windows' : (info[:is_mac] ? 'macOS' : (info[:is_linux] ? 'Linux' : 'Unknown')))}"
      puts ""
      puts "Dependencies:"
      puts "  ExifTool available: #{info[:exiftool_available] ? 'Yes' : 'No'}"
      if info[:exiftool_version]
        puts "  ExifTool version: #{info[:exiftool_version]}"
      else
        puts "  ExifTool: Not found or not in PATH"
        puts "  Please install ExifTool to use this tool."
      end
    end
  end
end
