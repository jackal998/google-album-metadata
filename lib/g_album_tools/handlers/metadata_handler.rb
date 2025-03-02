require_relative "base_handler"

module GAlbumTools
  module Handlers
    class MetadataHandler < BaseHandler
      protected

      def process
        log(:info, "Handling missing metadata for file: #{row["Media File"]}")

        # Check if file exists
        unless File.exist?(row["Media File"])
          log(:warn, "File does not exist: #{row["Media File"]}")
          return false
        end

        # For missing metadata, we can try to extract what we can from the file itself
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

        # Try to extract basic metadata from file
        cmd = [
          "exiftool",
          "-m", # Ignore minor errors
          "-overwrite_original",
          "-FileModifyDate>DateTimeOriginal",
          "-FileCreateDate>CreateDate",
          dest_file
        ]

        stdout_str, stderr_str, status = execute_command(cmd)

        # For missing metadata, we'll consider it handled
        # even if we couldn't extract much from the file
        true
      end
    end
  end
end
