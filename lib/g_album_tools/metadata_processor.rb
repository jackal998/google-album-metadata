require "json"
require "csv"

module GAlbumTools
  class MetadataProcessor
    attr_reader :logger, :exiftool

    def initialize(logger, exiftool)
      @logger = logger
      @exiftool = exiftool
    end

    def read_json(json_path)
      JSON.parse(File.read(json_path), encoding: "UTF-8")
    rescue JSON::ParserError => e
      logger.error("Invalid JSON format in #{json_path}: #{e.message}")
      nil
    end

    def update_metadata(file_path, data, destination_directory)
      return {} if data.nil?
      
      exif_args = []

      # Add timestamp data
      if data.dig("photoTakenTime", "timestamp")
        offset_time = exiftool.get_offset_time(file_path)
        taken_time = Time.at(data.dig("photoTakenTime", "timestamp").to_i, in: offset_time).strftime("%Y:%m:%d %H:%M:%S")
        exif_args << "-DateTimeOriginal='#{taken_time}'"
        exif_args << "-FileCreateDate='#{taken_time}'"
      end

      # Add GPS data if available
      if data["geoDataExif"]
        lat = data["geoDataExif"]["latitude"]
        lon = data["geoDataExif"]["longitude"]
        alt = data["geoDataExif"]["altitude"]

        if lat == 0 && lon == 0 && alt == 0
          exif_args << "-GPSLatitude*="
          exif_args << "-GPSLongitude*="
          exif_args << "-GPSAltitude*="
          # for video files
          exif_args << "-GPSCoordinates="
        else
          exif_args << "-GPSLatitude*=#{lat}"
          exif_args << "-GPSLongitude*=#{lon}"
          exif_args << "-GPSAltitude*=#{alt}"
          # for video files
          exif_args << "-GPSCoordinates=#{lat}, #{lon}, #{alt}"
        end
      end

      destination_path = File.join(destination_directory, File.basename(file_path))
      exiftool.update_metadata(file_path, exif_args, destination_path)
    end
  end
end 
