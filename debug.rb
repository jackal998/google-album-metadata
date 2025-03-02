#!/usr/bin/env ruby
require_relative "lib/g_album_tools"

class GAlbumTools::MetadataProcessor
  # Override process_directory to fix the argument mismatch
  def process_directory(dir)
    # Calculate the current destination directory based on source & destination root
    rel_path = dir.sub(@source_directory, "")
    current_dest_dir = File.join(@destination_directory, rel_path)
    FileUtils.mkdir_p(current_dest_dir) unless File.directory?(current_dest_dir)

    # Call check_files to populate processed_files
    check_files(dir)

    # Now call the original implementation with both arguments
    processed_files[dir].each do |file_info|
      file_path = file_info[:media_file]
      data = file_info[:data]

      begin
        update_metadata(file_path, data, current_dest_dir, file_info[:is_live_photo])
        @output_data[dir] ||= []
        @output_data[dir] << {
          "Media File" => file_path,
          "Destination File" => File.join(current_dest_dir, File.basename(file_path)),
          "Processed" => "true",
          "Errors" => nil
        }
      rescue => e
        puts "Error processing file #{file_path}: #{e.message}"

        @output_data[dir] ||= []
        @output_data[dir] << {
          "Media File" => file_path,
          "Destination File" => File.join(current_dest_dir, File.basename(file_path)),
          "Processed" => "false",
          "Errors" => e.message
        }
      end
    end
  end
end

processor = GAlbumTools::MetadataProcessor.new(
  source_directory: "test_source",
  destination_directory: "test_destination",
  verbose: true
)

processor.process
