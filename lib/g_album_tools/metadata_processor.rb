require "json"
require "csv"

module GAlbumTools
  class MetadataProcessor
    OFFSET_TIMES_KEYS = %w[OffsetTime OffsetTimeOriginal OffsetTimeDigitized]
    OFFSET_TIMES_PATH = "./local_data/offset_times.csv".freeze

    attr_reader :logger, :exiftool, :offset_time

    def initialize(logger, exiftool)
      @logger = logger
      @exiftool = exiftool
      @offset_time = {}
      load_offset_times
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
        taken_time = Time.at(data.dig("photoTakenTime", "timestamp").to_i, in: offset_time[file_path]).strftime("%Y:%m:%d %H:%M:%S")
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

    private

    def load_offset_times
      @offset_time = CSV.read(OFFSET_TIMES_PATH, headers: true, encoding: "bom|utf-16le:utf-8").filter_map do |row|
        offset_time_values = row.values_at(*OFFSET_TIMES_KEYS)
        next if offset_time_values.all? { _1 == "-" }
        next logger.info("Invalid offset time data in #{row}") if offset_time_values.uniq.size > 1

        [row["SourceFile"], offset_time_values.first]
      end.to_h
    rescue => e
      logger.error("Failed to load offset times: #{e.message}")
      {}
    end
  end
end 
