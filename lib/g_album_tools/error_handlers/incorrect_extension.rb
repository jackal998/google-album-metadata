require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class IncorrectExtension < Base
      def handle
        match = error_message.match(/Not a valid (\w+) \(looks more like a (\w+)\)/)
        return {processed: false, message: "Failed to parse extension error"} unless match

        current_extension, expected_extension = match.captures

        # Create a temporary file with correct extension
        origin_dir = File.dirname(file_details[:file])
        file_with_correct_extension = File.join(origin_dir, "#{File.basename(file_details[:file], ".*")}.#{expected_extension.downcase}")
        FileUtils.cp(file_details[:file], file_with_correct_extension)

        # Copy the corrected file to destination
        # target_path = File.join(file_details[:target_directory], File.basename(file_with_correct_extension))
        # FileUtils.cp(file_with_correct_extension, target_path)
        result = update_metadata(file_path: file_with_correct_extension)

        # Clean up the temporary file (optional, depending on policy)
        # FileUtils.rm(file_with_correct_extension)

        {processed: true, message: "Updated file extension from #{current_extension} to #{expected_extension}", result: result}
      end
    end
  end
end
