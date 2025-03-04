require "logger" 

module GAlbumTools
  class Logger
    attr_reader :logger, :verbose

    def initialize(log_file, verbose = false)
      @logger = ::Logger.new(log_file)
      @logger.level = ::Logger::INFO
      @verbose = verbose
    end

    def info(message, at_console: verbose)
      logger.info(message)
      puts message if at_console
    end

    def error(message, at_console: verbose)
      logger.error(message)
      puts "ERROR: #{message}" if at_console
    end
  end
end 
