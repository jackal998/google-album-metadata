require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class Unknown < Base
      def handle
        copy_file_to_target_directory(file_details[:file])

        {processed: false, message: "Unknown error: #{error_message}"}
      end
    end
  end
end
