require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class FileExists < Base
      def handle
        match = error_message.match(/Error: '(.*)' already exists/)
        file_path = match ? match[1] : file_details[:file]

        # In this case, we don't need to copy the file since it already exists in the destination
        # We'll just return a message indicating this
        {processed: true, message: "File already exists in destination: #{File.basename(file_path)}"}
      end
    end
  end
end
