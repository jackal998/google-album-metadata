require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class MissingMetadata < Base
      def handle
        copy_file_to_target_directory(file_details[:file])

        {processed: false, message: "No metadata available, file copied to destination"}
      end
    end
  end
end
