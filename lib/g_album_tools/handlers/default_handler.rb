require_relative "base_handler"

module GAlbumTools
  module Handlers
    class DefaultHandler < BaseHandler
      protected

      def process
        log(:info, "Handling generic error for file: #{row["Media File"]}")
        log(:info, "Error: #{row["Errors"]}")

        # Check if file exists
        unless File.exist?(row["Media File"])
          log(:warn, "File does not exist: #{row["Media File"]}")
          return false
        end

        # For generic errors, we'll try a generic approach
        dest_dir = File.dirname(row["Destination File"] || row["Media File"])
        file_name = File.basename(row["Media File"])
        dest_file = File.join(dest_dir, file_name)

        # Create destination directory if it doesn't exist
        FileUtils.mkdir_p(dest_dir) unless Dir.exist?(dest_dir)

        # Copy file to destination if they're different
        if row["Media File"] != dest_file
          begin
            FileUtils.cp(row["Media File"], dest_file)
            log(:info, "Copied file to destination: #{dest_file}")
          rescue => e
            log(:error, "Failed to copy file: #{e.message}")
            return false
          end
        end

        # For generic errors, we'll just mark it as handled
        # and copy the file without processing
        true
      end
    end
  end
end
