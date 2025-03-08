require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class MakerNotes < Base
      def handle
        destination_path = File.join(file_details[:target_directory], File.basename(file_details[:file]))

        # Use -m flag to ignore minor errors when processing with exiftool
        cmd = ["exiftool", "-m", "-o", destination_path, file_details[:file]]
        _, stderr_str, status = exiftool.execute_command(cmd)

        if status.success?
          {processed: true, message: "Fixed maker notes issue"}
        else
          copy_file_to_target_directory(file_details[:file])

          {processed: false, message: "Failed to fix maker notes: #{stderr_str}"}
        end
      end
    end
  end
end
