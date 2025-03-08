require_relative "base"

module GAlbumTools
  module ErrorHandlers
    # Handles missing metadata errors like:
    # "No JSON file found."
    # "No metadata found"
    class MissingMetadata < Base
      def handle
        # Simply copy the file to the target directory as is
        # without applying any metadata since none is available
        copy_file_to_target_directory(file_details[:file])

        {processed: false, message: "No metadata available, file copied to destination"}
      end
    end
  end
end
