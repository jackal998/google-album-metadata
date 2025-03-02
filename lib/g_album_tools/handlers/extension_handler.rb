require_relative "base_handler"

module GAlbumTools
  module Handlers
    class ExtensionHandler < BaseHandler
      protected

      def process
        log(:info, "Handling extension error for file: #{row["Media File"]}")
        log(:info, "Current extension: #{error_data[:current_extension]}, Expected: #{error_data[:expected_extension]}")

        # Get file details
        current_file = row["Media File"]
        dir_name = File.dirname(current_file)
        base_name = File.basename(current_file, ".*")
        File.extname(current_file).downcase
        expected_ext = ".#{error_data[:expected_extension].downcase}"

        # Create the new filename
        File.join(dir_name, "#{base_name}#{expected_ext}")

        # Build the destination file paths
        dest_dir = File.dirname(row["Destination File"] || current_file)
        dest_file_old = File.join(dest_dir, File.basename(current_file))
        dest_file_new = File.join(dest_dir, "#{base_name}#{expected_ext}")

        # Create destination directory if needed
        FileUtils.mkdir_p(dest_dir) unless Dir.exist?(dest_dir)

        # First, try to rename the file with the correct extension
        begin
          # Copy to destination with new extension
          FileUtils.cp(current_file, dest_file_new)
          log(:info, "Copied file with corrected extension: #{current_file} -> #{dest_file_new}")

          # Update the metadata with ExifTool
          cmd = [
            "exiftool",
            "-m", # Ignore minor errors
            "-overwrite_original",
            "-FileModifyDate>DateTimeOriginal",
            "-FileCreateDate>CreateDate",
            dest_file_new
          ]

          _, stderr_str, status = execute_command(cmd)

          if status.success?
            log(:info, "Updated metadata for: #{dest_file_new}")
            return true
          else
            log(:error, "Failed to update metadata: #{stderr_str}")
          end
        rescue => e
          log(:error, "Failed to copy/rename file: #{e.message}")
        end

        # If the above failed, try a different approach - just copy the file
        begin
          FileUtils.cp(current_file, dest_file_old)
          log(:info, "Copied file without extension change: #{current_file} -> #{dest_file_old}")
          return true
        rescue => e
          log(:error, "Failed to copy file: #{e.message}")
        end

        # If we get here, both approaches failed
        false
      end
    end
  end
end
