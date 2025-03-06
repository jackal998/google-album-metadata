require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class TruncatedMedia < Base
      def handle(file_path, error_message, destination_directory)
        copy_file_to_destination(file_path, destination_directory)

        { processed: false, message: "File appears to be corrupted (truncated media)" }
      end
    end
  end
end 
