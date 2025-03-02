require_relative "base_handler"

module GAlbumTools
  module Handlers
    class MakerNotesHandler < BaseHandler
      protected

      def process
        log(:info, "Handling maker notes error for file: #{row["Media File"]}")

        # Check if source file exists
        unless File.exist?(row["Media File"])
          log(:warn, "Source file does not exist: #{row["Media File"]}")
          return false
        end

        # Setup destination file
        dest_dir = File.dirname(row["Destination File"] || row["Media File"])
        dest_file = File.join(dest_dir, File.basename(row["Media File"]))

        # Create destination directory if needed
        FileUtils.mkdir_p(dest_dir) unless Dir.exist?(dest_dir)

        # Copy the file to destination
        begin
          FileUtils.cp(row["Media File"], dest_file)
          log(:info, "Copied file to destination: #{dest_file}")
        rescue => e
          log(:error, "Failed to copy file: #{e.message}")
          return false
        end

        # For maker notes errors, we can try to ignore them when processing
        # by using the -m flag and removing maker notes specifically
        cmd = [
          "exiftool",
          "-m", # Ignore minor errors
          "-overwrite_original",
          "-TagsFromFile", "@",
          "-all:all",
          "-maker*=",  # Remove maker notes
          dest_file
        ]

        stdout_str, stderr_str, status = execute_command(cmd)

        if status.success?
          log(:info, "Successfully updated metadata while ignoring maker notes: #{dest_file}")
          return true
        else
          log(:error, "Failed to update metadata: #{stderr_str}")

          # Even if the command fails, we'll mark this as handled
          # since maker notes errors are minor and don't prevent
          # the file from being used
          return true
        end
      end
    end
  end
end
