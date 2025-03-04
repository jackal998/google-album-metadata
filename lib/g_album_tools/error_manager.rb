require_relative "error_handlers/factory"

module GAlbumTools
  class ErrorManager
    attr_reader :logger, :exiftool

    def initialize(logger, exiftool)
      @logger = logger
      @exiftool = exiftool
    end

    def handle_error(file_path, error_message, destination_directory)
      error_type = ErrorHandlers::Factory.identify_error_type(error_message)
      
      logger.info("Handling error type: #{error_type} for file: #{file_path}")
      
      # Create the appropriate handler and delegate the error handling
      handler = ErrorHandlers::Factory.create_handler(error_type, logger, exiftool)
      handler.handle(file_path, error_message, destination_directory)
    end
  end
end 
