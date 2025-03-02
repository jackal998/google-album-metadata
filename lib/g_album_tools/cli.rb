require "optparse"
require_relative "version"
require_relative "file_processor"
require_relative "metadata_processor"
require_relative "error_handler"

module GAlbumTools
  class CLI
    attr_reader :options, :parser

    def initialize
      @options = {
        verbose: false,
        nested: false,
        force: false
      }
    end

    # Parse command line arguments
    # @param args [Array<String>] Command line arguments
    # @return [Hash] Parsed options
    def parse(args)
      @parser = OptionParser.new do |opts|
        opts.banner = "Usage: g_album_tool [options] COMMAND [args]"
        opts.separator ""

        opts.separator "Commands:"
        opts.separator "  process SOURCE_DIR DESTINATION_DIR  Process files from SOURCE_DIR and save to DESTINATION_DIR"
        opts.separator "  analyze CSV_DIR                     Analyze error CSV files in CSV_DIR"
        opts.separator "  fix-errors SOURCE_DIR DESTINATION_DIR Fix files with errors"
        opts.separator ""

        opts.separator "Options:"
        opts.on("-v", "--verbose", "Run verbosely") do
          @options[:verbose] = true
        end

        opts.on("-n", "--nested", "Process nested directories") do
          @options[:nested] = true
        end

        opts.on("-f", "--force", "Force overwrite existing files") do
          @options[:force] = true
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
      case @command
      when "process"
        process_command
      when "analyze"
        analyze_command
      when "fix-errors"
        fix_errors_command
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
        if @command_args.size != 2
          puts "Error: 'fix-errors' command requires SOURCE_DIR and DESTINATION_DIR"
          puts @parser
          exit 1
        end
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
        offset_file: @options[:offset_file]
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
      puts "  Unknown errors: #{stats[:unknown]}"
    end

    # Fix errors command implementation
    def fix_errors_command
      source_dir = @command_args[0]
      destination_dir = @command_args[1]

      # Find all CSV files in the source directory
      csv_files = Dir.glob(File.join(source_dir, "**", "*_output.csv"))

      if csv_files.empty?
        puts "No CSV files found in #{source_dir}"
        exit 1
      end

      error_handler = ErrorHandler.new(verbose: @options[:verbose])
      errors = error_handler.load_errors_from_csv(csv_files)

      if errors.empty?
        puts "No errors found in CSV files"
        exit 0
      end

      error_handler.fix_errors(destination_dir)
    end
  end
end
