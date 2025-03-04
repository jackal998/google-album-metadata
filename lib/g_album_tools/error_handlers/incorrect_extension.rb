require_relative "base"

module GAlbumTools
  module ErrorHandlers
    class IncorrectExtension < Base
      def handle(file_path, error_message, destination_directory)
        logger.info("Handling incorrect extension for #{file_path}")
        match = error_message.match(/Not a valid (\w+) \(looks more like a (\w+)\)/)
        return { processed: false, message: "Failed to parse extension error" } unless match
        
        current_extension, expected_extension = match.captures
        logger.info("Fixing extension from #{current_extension} to #{expected_extension}")
        
        # Create a temporary file with correct extension
        temp_dir = File.dirname(file_path)
        temp_file = File.join(temp_dir, "#{File.basename(file_path, ".*")}.#{expected_extension.downcase}")
        FileUtils.cp(file_path, temp_file)
        
        # Copy the corrected file to destination
        destination_path = File.join(destination_directory, File.basename(temp_file))
        FileUtils.cp(temp_file, destination_path)
        
        # Clean up the temporary file (optional, depending on policy)
        FileUtils.rm(temp_file)
        
        { processed: true, message: "Updated file extension from #{current_extension} to #{expected_extension}" }
      end
    end
  end
end 
