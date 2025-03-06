require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class MissingMetadata < Base
      def handle(file_path, error_message, destination_directory)
        copy_file_to_destination(file_path, destination_directory)

        {processed: false, message: "No metadata available, file copied to destination"}
      end
    end
  end
end
