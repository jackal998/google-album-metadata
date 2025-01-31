#encoding: UTF-8

require "json"
require "logger"
require "fileutils"
require "open3"
require "pry"
require "csv"
require "rchardet"

class GooglePhotosMetadataEditor
  LOG_COMMAND = false

  IMAGE_EXTENSIONS = %w[jpg jpeg heic dng png gif bmp tiff].freeze
  VIDEO_EXTENSIONS = %w[mp4 mov avi mkv].freeze
  SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
  LOG_FILE = "metadata_editor.log".freeze

  OFFSET_TIMES_KEYS = %w[OffsetTime OffsetTimeOriginal OffsetTimeDigitized]
  OFFSET_TIMES_PATH = "./local_data/offset_times.csv".freeze

  attr_reader :logger, :origin_directory, :destination_directory, :offset_time

  def initialize(origin_directory, destination_directory)
    @origin_directory = origin_directory
    @destination_directory = destination_directory
    @logger = Logger.new(LOG_FILE)
    @logger.level = Logger::INFO
  end

  def process
    log(:info, "Processing files in directory: #{origin_directory}")

    media_files = Dir.glob(File.join(origin_directory, "*.{#{SUPPORTED_EXTENSIONS.join(",")}}")).select { |f| File.file?(f) }
    json_files = Dir.glob(File.join(origin_directory, "*.json")).select { |f| File.file?(f) }
  
    media_files = check_files(media_files, json_files)
    return log(:info, "No valid media found.") if media_files.empty?

    load_offset_times
  
    media_files.each do |file|
      extension = File.extname(file).downcase.delete(".")
      data = read_json(file)
  
      if SUPPORTED_EXTENSIONS.include?(extension)
        update_metadata(file, data)
      else
        log(:info, "Unsupported file type: #{file}")
      end
    end
    
    log(:info, "Processing completed.")
  end

  private
  
  def log(level, message)
    case level
    when :info
      logger.info(message)
      puts message
    when :error
      logger.error(message)
      puts "ERROR: #{message}"
    end
  end

  def clean_string(str)
    encoding = CharDet.detect(str)["encoding"]

    str.force_encoding(encoding).encode("UTF-8").strip
  end

  def execute_command(cmd)
    log(:info, "Executing: #{cmd.join(" ")}") if LOG_COMMAND
    
    stdout_str, stderr_str, status = Open3.capture3(*cmd)
  
    status.success? ? log(:info, "Success: #{clean_string(stdout_str)}") : log(:error, "Failed: #{clean_string(stderr_str)}")
  end

  def read_json(file_path)
    json_path = "#{file_path}.json"
  
    begin
      data = JSON.parse(File.read(json_path), encoding: 'UTF-8')
      log(:info, "Loaded JSON for #{file_path}")
      return data
    rescue JSON::ParserError => e
      log(:error, "Invalid JSON format in #{json_path}: #{e.message}")
      return nil
    end
  end

  def check_files(media_files, json_files)
    media_files_from_json = json_files.map { |f| f.match(/(.*)\.json/)[1] }
  
    missing_json = media_files - media_files_from_json
    missing_media = media_files_from_json - media_files

    missing_json.each do |file_path|
      log(:info, "JSON data is missing for media file: #{file_path}")
    end
  
    missing_media.each do |file_path|
      log(:info, "Media file is missing for JSON data: #{file_path}")
    end
  
    media_files & media_files_from_json
  end

  def load_offset_times
    @offset_time = CSV.read(OFFSET_TIMES_PATH, headers: true, encoding: "bom|utf-16le:utf-8").filter_map do |row|
      offset_time_values = row.values_at(*OFFSET_TIMES_KEYS)
      next if offset_time_values.all? { _1 == "-" }
      next log(:info, "Invalid offset time data in #{row}") if offset_time_values.uniq.size > 1

      [row["SourceFile"], offset_time_values.first]
    end.to_h
  end

  def update_metadata(file_path, data)
    exif_args = []

    creation_time = Time.at(data.dig("creationTime", "timestamp").to_i, in: offset_time[file_path]).strftime('%Y:%m:%d %H:%M:%S')
    exif_args << "-FileCreateDate='#{creation_time}'"
  
    taken_time = Time.at(data.dig("photoTakenTime", "timestamp").to_i, in: offset_time[file_path]).strftime('%Y:%m:%d %H:%M:%S')
    exif_args << "-DateTimeOriginal='#{taken_time}'"
  
    # Update GPS Data
    lat = data["geoDataExif"]["latitude"]
    lon = data["geoDataExif"]["longitude"]
    alt = data["geoDataExif"]["altitude"]
  
    if lat == 0 && lon == 0 && alt == 0
      exif_args << "-GPSLatitude="
      exif_args << "-GPSLongitude="
      exif_args << "-GPSAltitude="
    else
      exif_args << "-GPSLatitude=#{lat}"
      exif_args << "-GPSLongitude=#{lon}"
      exif_args << "-GPSAltitude=#{alt}"
    end
  
    return if exif_args.empty?

    cmd = ["exiftool", "-o", File.join(destination_directory, File.basename(file_path)), *exif_args, file_path]
    execute_command(cmd)
  end
end

# Entry Point
if __FILE__ == $0
  origin_directory = ARGV[0]
  destination_directory = ARGV[1]

  unless origin_directory && destination_directory
    puts "Usage: ruby metadata_editor.rb <origin_directory> <destination_directory>"
    exit
  end

  unless Dir.exist?(origin_directory)
    puts "Directory does not exist: #{origin_directory}"
    exit
  end

  unless Dir.exist?(destination_directory)
    puts "Directory does not exist: #{destination_directory}"
    exit
  end

  GooglePhotosMetadataEditor.new(origin_directory, destination_directory).process
end
