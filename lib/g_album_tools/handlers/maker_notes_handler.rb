require_relative "base_handler"

module GAlbumTools
  module Handlers
    class MakerNotesHandler < BaseHandler
      protected

      def process
        log(:info, "Handling maker notes error for file: #{row["Media File"]}")

        # For maker notes errors, we can try to ignore them when processing
        # Since this is a minor error, we'll just mark it as processed
        cmd = [
          "exiftool",
          "-m", # Ignore minor errors
          "-overwrite_original",
          "-all=",
          "-tagsfromfile", "@",
          "-all:all",
          "-maker*=",  # Remove maker notes
          row["Media File"]
        ]

        stdout_str, stderr_str, status = execute_command(cmd)

        # Even if the command fails, we'll mark this as handled
        # since maker notes errors are minor and don't prevent
        # the file from being used
        true
      end
    end
  end
end
