require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class TruncatedMedia < Base
      def handle
        copy_file_to_target_directory(file_details[:file])

        {processed: false, message: "File appears to be corrupted (truncated media)"}
      end
    end
  end
end
