require_relative "base_handler"

module GAlbumTools
  module Handlers
    class ExtensionHandler < BaseHandler
      protected

      def process
        log(:info, "Handling extension error for file: #{row["Media File"]}")
        log(:info, "Current extension: #{error_data[:current_extension]}, Expected: #{error_data[:expected_extension]}")

        # Build the command to rename the file with the correct extension
        cmd = [
          "exiftool",
          "-ext",
          error_data[:current_extension].downcase,
          "-FileName=#{File.basename(row["Media File"], ".*")}.#{error_data[:expected_extension].downcase}",
          row["Media File"]
        ]

        stdout_str, stderr_str, status = execute_command(cmd)

        status.success?
      end
    end
  end
end
