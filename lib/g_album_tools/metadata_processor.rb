require_relative "file_processor"
require "csv"

module GAlbumTools
  class MetadataProcessor < FileProcessor
    def initialize(options = {})
      super(options)
      @output_data = {}
    end

    def process_directory(dir, current_destination_directory)
      processed_files[dir].each do |file_info|
        file_path = file_info[:media_file]
        data = file_info[:data]

        begin
          update_metadata(file_path, data, current_destination_directory)
          @output_data[dir] ||= []
          @output_data[dir] << {
            "Media File" => file_path,
            "Destination File" => File.join(current_destination_directory, File.basename(file_path)),
            "Processed" => "true",
            "Errors" => nil
          }
        rescue => e
          log(:error, "Error processing file #{file_path}: #{e.message}")
          log(:error, e.backtrace.join("\n"))

          @output_data[dir] ||= []
          @output_data[dir] << {
            "Media File" => file_path,
            "Destination File" => File.join(current_destination_directory, File.basename(file_path)),
            "Processed" => "false",
            "Errors" => e.message
          }
        end
      end
    end

    def create_csv_output
      @output_data.each do |dir, data|
        next if data.empty?

        output_file = File.join(File.dirname(dir), "#{File.basename(dir)}_output.csv")
        CSV.open(output_file, "w") do |csv|
          csv << data.first.keys
          data.each do |row|
            csv << row.values
          end
        end

        log(:info, "Created output file: #{output_file}")
      end
    end

    private

    def update_metadata(file_path, data, current_destination_directory)
      exif_args = []

      # Add common metadata extraction and updating logic here
      # This will vary based on your specific requirements

      # Example for extracting metadata from JSON
      if data["title"] && !data["title"].empty?
        title = clean_string(data["title"])
        exif_args << "-Title=#{title}"
      end

      if data["description"] && !data["description"].empty?
        description = clean_string(data["description"])
        exif_args << "-Description=#{description}"
        exif_args << "-ImageDescription=#{description}"
      end

      # Execute exiftool command if we have arguments to pass
      unless exif_args.empty?
        destination_file = File.join(current_destination_directory, File.basename(file_path))

        # Copy file to destination
        FileUtils.cp(file_path, destination_file)

        # Update metadata
        cmd = ["exiftool", "-overwrite_original", *exif_args, destination_file]
        execute_command(cmd)
      end
    end
  end
end
