require_relative "base"
require "csv"

module GAlbumTools
  class ErrorHandler < Base
    def initialize(options = {})
      super(options)
      @destination_directory = options[:destination_directory]
      @nested = options[:nested] || false
    end

    def process
      destination_directories.each do |dir|
        read_output_file(dir) do |row|
          next unless row["Processed"] == "false"

          error_info = match_error(row)

          case error_info[:type]
          when "extension"
            handle_extension_error(row, error_info[:data])
          when "encoding"
            handle_encoding_error(row, error_info[:data])
          when nil
            log(:warn, "Unknown error type for file: #{row["Media File"]}")
          end
        end
      end
    end

    private

    attr_reader :destination_directory, :nested

    def destination_directories
      if nested
        Dir.glob(File.join(destination_directory, "**/"))
      else
        [destination_directory]
      end
    end

    def read_output_file(dir)
      file_path = build_output_file_path(dir)

      unless File.exist?(file_path)
        log(:info, "No output file found for #{dir}")
        return
      end

      CSV.foreach(file_path, headers: true) do |row|
        yield row
      end
    end

    def build_output_file_path(dir)
      File.join(File.dirname(dir), "#{File.basename(dir)}_output.csv")
    end

    def match_error(row)
      if (current_extension, expected_extension = row["Errors"].to_s.match(/Error: Not a valid (\w+) \(looks more like a (\w+)\).*/)&.captures)
        {type: "extension", data: {current_extension: current_extension, expected_extension: expected_extension}}
      elsif row["Errors"].to_s.match?(/Error: Failed to process.*encoding/)
        {type: "encoding", data: {file: row["Media File"]}}
      else
        {type: nil, data: nil}
      end
    end

    def handle_extension_error(row, error_data)
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

      if status.success?
        log(:info, "Successfully fixed extension for: #{row["Media File"]}")
        update_output_file(row, true, nil)
      else
        log(:error, "Failed to fix extension for: #{row["Media File"]}")
      end
    end

    def handle_encoding_error(row, error_data)
      log(:info, "Handling encoding error for file: #{row["Media File"]}")

      # Implement logic to handle encoding errors
      # This would vary depending on your specific requirements

      log(:warn, "Encoding error handling not fully implemented")
    end

    def update_output_file(row, processed, error_message)
      # Read the entire CSV file
      file_path = build_output_file_path(File.dirname(row["Media File"]))
      rows = CSV.read(file_path, headers: true)

      # Find and update the row
      rows.each do |csv_row|
        if csv_row["Media File"] == row["Media File"]
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
    end
  end
end
