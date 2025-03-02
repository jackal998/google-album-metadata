require_relative "base_handler"

module GAlbumTools
  module Handlers
    class TruncatedMediaHandler < BaseHandler
      protected

      def process
        log(:info, "Handling truncated media error for file: #{row["Media File"]}")

        # Truncated media files are usually corrupted and can't be fixed automatically
        # We'll log this but not perform any operations on the file
        log(:warn, "File appears to be corrupted and may not be recoverable: #{row["Media File"]}")

        # Create a special output directory for truncated files if needed
        dest_dir = File.dirname(row["Destination File"] || row["Media File"])
        truncated_dir = File.join(dest_dir, "_truncated_media")

        begin
          FileUtils.mkdir_p(truncated_dir) unless Dir.exist?(truncated_dir)

          # Copy to the truncated directory for user reference
          dest_file = File.join(truncated_dir, File.basename(row["Media File"]))
          FileUtils.cp(row["Media File"], dest_file)

          log(:info, "Copied truncated file to: #{dest_file}")

          # Update the output file to mark this as not processed
          update_output_file(false, "File is corrupted and was copied to _truncated_media directory")
        rescue => e
          log(:error, "Failed to copy truncated file: #{e.message}")
        end

        # We return true to indicate we handled the file, even though
        # we're marking it as not processed in the CSV
        true
      end
    end
  end
end
