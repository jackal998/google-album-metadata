require_relative "file_processor"
require "csv"

module GAlbumTools
  class MetadataProcessor < FileProcessor
    def initialize(options = {})
      super(options)
      @output_data = {}
    end

    # Process a directory of files
    # @param dir [String] Source directory
    # @param current_destination_directory [String] Destination directory
    def process_directory(dir, current_destination_directory)
      processed_files[dir].each do |file_info|
        file_path = file_info[:media_file]
        data = file_info[:data]

        begin
          update_metadata(file_path, data, current_destination_directory, file_info[:is_live_photo])
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

    # Create CSV output files with processing results
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

    # Update metadata for a file
    # @param file_path [String] Path to the media file
    # @param data [Hash] Metadata from JSON file
    # @param current_destination_directory [String] Destination directory
    # @param is_live_photo [Boolean] Whether the file is part of a live photo
    def update_metadata(file_path, data, current_destination_directory, is_live_photo)
      exif_args = []
      destination_file = File.join(current_destination_directory, File.basename(file_path))

      # Extract metadata from JSON
      add_title_metadata(exif_args, data)
      add_description_metadata(exif_args, data)
      add_date_metadata(exif_args, data)
      add_location_metadata(exif_args, data)
      add_offset_time_metadata(exif_args, file_path)

      # Execute exiftool command to copy file and update metadata in one step
      unless exif_args.empty?
        cmd = [
          "exiftool",
          *EXIFTOOL_COMMON_OPTIONS,
          "-TagsFromFile", file_path,
          "-all:all",
          *exif_args,
          "-o", destination_file,
          file_path
        ]

        stdout_str, stderr_str, status = execute_command(cmd)

        unless status.success?
          raise "Failed to update metadata: #{stderr_str}"
        end
      else
        # Just copy the file if no metadata to update
        FileUtils.cp(file_path, destination_file)
      end
    end

    # Add title metadata to exif arguments
    # @param exif_args [Array] Array of exiftool arguments
    # @param data [Hash] Metadata from JSON file
    def add_title_metadata(exif_args, data)
      if data["title"] && !data["title"].empty?
        title = clean_string(data["title"])
        exif_args << "-Title=#{title}"
        exif_args << "-XMP:Title=#{title}"
      end
    end

    # Add description metadata to exif arguments
    # @param exif_args [Array] Array of exiftool arguments
    # @param data [Hash] Metadata from JSON file
    def add_description_metadata(exif_args, data)
      if data["description"] && !data["description"].empty?
        description = clean_string(data["description"])
        exif_args << "-Description=#{description}"
        exif_args << "-ImageDescription=#{description}"
        exif_args << "-XMP:Description=#{description}"
      end
    end

    # Add date metadata to exif arguments
    # @param exif_args [Array] Array of exiftool arguments
    # @param data [Hash] Metadata from JSON file
    def add_date_metadata(exif_args, data)
      if data["photoTakenTime"] && data["photoTakenTime"]["timestamp"]
        timestamp = data["photoTakenTime"]["timestamp"].to_i
        date_time = Time.at(timestamp).strftime("%Y:%m:%d %H:%M:%S")
        exif_args << "-DateTimeOriginal=#{date_time}"
        exif_args << "-CreateDate=#{date_time}"
      end
    end

    # Add location metadata to exif arguments
    # @param exif_args [Array] Array of exiftool arguments
    # @param data [Hash] Metadata from JSON file
    def add_location_metadata(exif_args, data)
      if data["geoData"] && data["geoData"]["latitude"] && data["geoData"]["longitude"]
        lat = data["geoData"]["latitude"]
        lng = data["geoData"]["longitude"]
        alt = data["geoData"]["altitude"] || 0

        exif_args << "-GPSLatitude=#{lat}"
        exif_args << "-GPSLongitude=#{lng}"
        exif_args << "-GPSAltitude=#{alt}"

        # Set latitude/longitude reference based on value
        exif_args << "-GPSLatitudeRef=#{lat >= 0 ? 'N' : 'S'}"
        exif_args << "-GPSLongitudeRef=#{lng >= 0 ? 'E' : 'W'}"
      end
    end

    # Add offset time metadata to exif arguments
    # @param exif_args [Array] Array of exiftool arguments
    # @param file_path [String] Path to the file
    def add_offset_time_metadata(exif_args, file_path)
      # If offset time is available in the metadata from the CSV file, use it
      found_offset = false

      if offset_time && !offset_time.empty?
        filename = File.basename(file_path)
        offset_entry = offset_time.find { |entry| entry["FileName"] == filename }

        if offset_entry && offset_entry["OffsetTime"]
          OFFSET_TIMES_KEYS.each do |key|
            exif_args << "-#{key}=#{offset_entry["OffsetTime"]}"
          end
          found_offset = true
        end
      end

      # If no offset time was found in the CSV, use the default
      unless found_offset
        OFFSET_TIMES_KEYS.each do |key|
          exif_args << "-#{key}=#{DEFAULT_OFFSET_TIME}"
        end
      end
    end
  end
end
