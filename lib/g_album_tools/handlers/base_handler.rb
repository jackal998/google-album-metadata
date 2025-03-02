require_relative "../base"

module GAlbumTools
  module Handlers
    class BaseHandler < Base
      attr_reader :row, :error_data

      def initialize(options = {})
        super(options)
        @row = options[:row]
        @error_data = options[:error_data]
      end

      def handle
        log(:info, "Handling error for file: #{@row["Media File"]}")
        success = process

        if success
          log(:info, "Successfully handled error for: #{@row["Media File"]}")
          update_output_file(true, nil)
          true
        else
          log(:error, "Failed to handle error for: #{@row["Media File"]}")
          false
        end
      end

      protected

      # This method should be implemented in each subclass
      def process
        raise NotImplementedError, "Subclass must implement process method"
      end

      def update_output_file(processed, error_message)
        file_path = build_output_file_path(File.dirname(@row["Media File"]))

        begin
          # Read the entire CSV file
          rows = CSV.read(file_path, headers: true)

          # Find and update the row
          rows.each do |csv_row|
            if csv_row["Media File"] == @row["Media File"]
              csv_row["Processed"] = processed.to_s
              csv_row["Errors"] = error_message
              break
            end
          end

          # Write back to the file
          CSV.open(file_path, "w") do |csv|
            csv << rows.headers
            rows.each do |csv_row|
              csv << csv_row
            end
          end

          log(:info, "Updated output file: #{file_path}")
          true
        rescue => e
          log(:error, "Failed to update output file: #{e.message}")
          false
        end
      end

      def build_output_file_path(dir)
        File.join(File.dirname(dir), "#{File.basename(dir)}_output.csv")
      end
    end
  end
end
