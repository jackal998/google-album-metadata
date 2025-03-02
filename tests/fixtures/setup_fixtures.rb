#!/usr/bin/env ruby
require "fileutils"
require "json"

# Setup script for test fixtures
module TestFixtures
  FIXTURES_ROOT = File.expand_path(File.dirname(__FILE__))

  class << self
    def setup_all
      setup_directories
      setup_media_files
      setup_json_files
      setup_csv_files
      puts "All test fixtures created successfully."
    end

    def setup_directories
      %w[source destination media csv].each do |dir|
        dir_path = File.join(FIXTURES_ROOT, dir)
        FileUtils.mkdir_p(dir_path)
        puts "Created directory: #{dir_path}"
      end
    end

    def setup_media_files
      # Create test media files in the source directory
      source_dir = File.join(FIXTURES_ROOT, "source")

      # Regular image
      create_dummy_file(File.join(source_dir, "photo1.jpg"), "JPEG image data")

      # Live photo pair
      create_dummy_file(File.join(source_dir, "live_photo.jpg"), "JPEG image data for live photo")
      create_dummy_file(File.join(source_dir, "live_photo.mov"), "QuickTime movie data for live photo")

      # Files with incorrect extensions
      create_dummy_file(File.join(source_dir, "wrong_extension.heic"), "JPEG image data but with HEIC extension")

      # Truncated media
      create_dummy_file(File.join(source_dir, "truncated.mp4"), "Truncated MP4 file data")

      # File with maker notes issues
      create_dummy_file(File.join(source_dir, "maker_notes.jpg"), "JPEG with maker notes issues")
    end

    def setup_json_files
      source_dir = File.join(FIXTURES_ROOT, "source")

      # Create JSON metadata for photo1.jpg
      json_data = {
        "title" => "Test Photo",
        "description" => "This is a test photo",
        "photoTakenTime" => {
          "timestamp" => "1609459200", # 2021-01-01
          "formatted" => "Jan 1, 2021, 12:00:00 AM UTC"
        },
        "geoData" => {
          "latitude" => 37.7749,
          "longitude" => -122.4194,
          "altitude" => 0,
          "latitudeSpan" => 0.01,
          "longitudeSpan" => 0.01
        }
      }

      create_json_file(File.join(source_dir, "photo1.json"), json_data)
      create_json_file(File.join(source_dir, "live_photo.json"), json_data.merge("title" => "Live Photo Test"))

      # No JSON for wrong_extension.heic (to test missing metadata)
      # No JSON for truncated.mp4 (to test missing metadata)

      # Create JSON for maker_notes.jpg
      create_json_file(File.join(source_dir, "maker_notes.json"), json_data.merge("title" => "Maker Notes Test"))
    end

    def setup_csv_files
      csv_dir = File.join(FIXTURES_ROOT, "csv")
      source_dir = File.join(FIXTURES_ROOT, "source")
      dest_dir = File.join(FIXTURES_ROOT, "destination")

      # Create a test output CSV file with various error types
      csv_content = <<~CSV
        Media File,Destination File,Processed,Errors
        #{File.join(source_dir, "photo1.jpg")},#{File.join(dest_dir, "photo1.jpg")},true,
        #{File.join(source_dir, "wrong_extension.heic")},#{File.join(dest_dir, "wrong_extension.heic")},false,Not a valid HEIC (looks more like a JPEG)
        #{File.join(source_dir, "truncated.mp4")},#{File.join(dest_dir, "truncated.mp4")},false,Invalid or truncated file
        #{File.join(source_dir, "maker_notes.jpg")},#{File.join(dest_dir, "maker_notes.jpg")},false,Error: [minor] Maker notes could not be parsed
        #{File.join(source_dir, "missing_json.jpg")},#{File.join(dest_dir, "missing_json.jpg")},false,No JSON file found
        #{File.join(source_dir, "live_photo_missing.jpg")},#{File.join(dest_dir, "live_photo_missing.jpg")},false,Live photo missing video part
      CSV

      File.write(File.join(csv_dir, "test_output.csv"), csv_content)
      puts "Created test CSV file"
    end

    private

    def create_dummy_file(path, content)
      File.write(path, content)
      puts "Created dummy file: #{path}"
    end

    def create_json_file(path, data)
      File.write(path, JSON.pretty_generate(data))
      puts "Created JSON file: #{path}"
    end
  end
end

# Run the setup if this file is executed directly
TestFixtures.setup_all if __FILE__ == $PROGRAM_NAME
