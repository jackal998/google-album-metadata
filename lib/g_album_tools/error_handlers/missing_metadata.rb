require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class MissingMetadata < Base
      def handle(file_path, error_message, destination_directory)
        logger.info("Handling missing metadata for #{file_path}")
        
        # First, check if it's a live photo (we'd need a reference to FileDetector)
        # This is a simplified version - in a real implementation, we'd check if it's a live photo
        # and try to find the related photo's metadata
        
        # For now, we'll simply copy the file to the destination
        copy_file_to_destination(file_path, destination_directory)
        
        { processed: false, message: "No metadata available, file copied to destination" }
      end
    end
  end
end 
