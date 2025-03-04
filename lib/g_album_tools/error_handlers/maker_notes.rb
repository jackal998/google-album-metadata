require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class MakerNotes < Base
      def handle(file_path, error_message, destination_directory)
        logger.info("Handling maker notes error for #{file_path}")
        destination_path = File.join(destination_directory, File.basename(file_path))
        
        # Use -m flag to ignore minor errors
        cmd = ["exiftool", "-m", "-o", destination_path, file_path]
        _, stderr_str, status = exiftool.execute_command(cmd)
        
        if status.success?
          { processed: true, message: "Fixed maker notes issue" }
        else
          copy_file_to_destination(file_path, destination_directory)
          { processed: false, message: "Failed to fix maker notes: #{stderr_str}" }
        end
      end
    end
  end
end 
