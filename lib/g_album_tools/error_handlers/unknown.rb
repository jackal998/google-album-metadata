require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class Unknown < Base
      def handle(file_path, error_message, destination_directory)
        logger.info("Handling unknown error for #{file_path}: #{error_message}")
        copy_file_to_destination(file_path, destination_directory)
        { processed: false, message: "Unknown error: #{error_message}" }
      end
    end
  end
end 
