require_relative "base_handler"

module GAlbumTools
  module Handlers
    class TruncatedMediaHandler < BaseHandler
      protected

      def process
        log(:info, "Handling truncated media error for file: #{row["Media File"]}")

        # Truncated media files are usually corrupted and can't be fixed
        # We'll note this in the CSV but mark it as handled
        log(:warn, "File appears to be corrupted and may not be recoverable: #{row["Media File"]}")

        # We could try to repair the file using specialized tools for certain formats
        # but that's beyond the scope of this simple handler

        # For now, we'll just mark it as processed
        update_output_file(true, "File is corrupted but marked as processed for tracking")

        true
      end
    end
  end
end
