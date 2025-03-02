require "optparse"
require_relative "version"
require_relative "metadata_processor"
require_relative "error_handler"

module GAlbumTools
  class CLI
    def initialize(args = ARGV)
      @args = args
      @options = {
        verbose: false,
        create_output_csv: true
      }
      parse_options
    end

    def run
      case @command
      when "process"
        process_metadata
      when "fix-errors"
        fix_errors
      when "help"
        puts @parser
      else
        puts "Unknown command: #{@command}"
        puts @parser
      end
    end

    private

    def parse_options
      @parser = OptionParser.new do |opts|
        opts.banner = "Usage: g_album_tool [options] COMMAND"
        opts.separator ""
        opts.separator "Commands:"
        opts.separator "  process SOURCE_DIR DEST_DIR   Process metadata from SOURCE_DIR to DEST_DIR"
        opts.separator "  fix-errors DEST_DIR          Fix errors in processed files in DEST_DIR"
        opts.separator "  help                         Show this help message"
        opts.separator ""
        opts.separator "Options:"

        opts.on("-v", "--verbose", "Run verbosely") do
          @options[:verbose] = true
        end

        opts.on("--no-csv", "Don't create CSV output files") do
          @options[:create_output_csv] = false
        end

        opts.on("--nested", "Process nested directories for fix-errors command") do
          @options[:nested] = true
        end

        opts.on("-h", "--help", "Show this help message") do
          puts opts
          exit
        end

        opts.on("--version", "Show version") do
          puts "GAlbumTool version #{GAlbumTools::VERSION}"
          exit
        end
      end

      @parser.parse!(@args)

      @command = @args.shift
      @command = "help" if @command.nil?

      case @command
      when "process"
        @options[:source_directory] = @args.shift
        @options[:destination_directory] = @args.shift

        if @options[:source_directory].nil? || @options[:destination_directory].nil?
          puts "Error: Source and destination directories are required for the process command"
          puts @parser
          exit 1
        end
      when "fix-errors"
        @options[:destination_directory] = @args.shift

        if @options[:destination_directory].nil?
          puts "Error: Destination directory is required for the fix-errors command"
          puts @parser
          exit 1
        end
      end
    end

    def process_metadata
      processor = MetadataProcessor.new(@options)
      processor.process
    end

    def fix_errors
      handler = ErrorHandler.new(@options)
      handler.process
    end
  end
end
