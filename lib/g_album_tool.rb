require "json"
require "logger"
require "fileutils"
require "open3"
require "csv"
require "rchardet"

class GAlbumTool
  SHOW_COMMAND = false

  IMAGE_EXTENSIONS = %w[jpg jpeg heic dng png gif bmp tiff webp].freeze
  VIDEO_EXTENSIONS = %w[mp4 mov avi mkv].freeze
  SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
  LIVE_PHOTO_EXTENSIONS = %w[mov mp4].freeze

  LOG_FILE = "metadata_editor.log".freeze

  OFFSET_TIMES_KEYS = %w[OffsetTime OffsetTimeOriginal OffsetTimeDigitized]
  OFFSET_TIMES_PATH = "./local_data/offset_times.csv".freeze

  ALLOWED_SUFFIXES = ["-已編輯", "(1)", " Copy"].freeze

  attr_reader :verbose, :logger, :origin_directory, :destination_directory, :offset_time, :processed_files

  def initialize(verbose, origin_directory, destination_directory)
    @verbose = verbose
    @origin_directory = origin_directory
    @destination_directory = destination_directory
    @processed_files = {}
    @logger = Logger.new(LOG_FILE)
    @logger.level = Logger::INFO
  end

  def process
    return unless valid_paths?

    log(:info, "Processing files in directory: #{origin_directory}", at_console: true)

    media_files = Dir.glob(File.join(origin_directory, "*.{#{SUPPORTED_EXTENSIONS.join(",")}}")).select { |f| File.file?(f) }
    json_files = Dir.glob(File.join(origin_directory, "*.json")).select { |f| File.file?(f) }

    check_files(media_files, json_files)
    return log(:info, "No valid media found.") if processed_files.empty?

    load_offset_times

    processed_files.each do |file, info|
      extension = File.extname(file).downcase.delete(".")

      if info[:json_file]
        stdout_str, stderr_str, status = update_metadata(file, read_json(info[:json_file]))

        status.success? ? info[:processed] = true : FileUtils.cp(file, File.join(destination_directory, File.basename(file)))
      else
        FileUtils.cp(file, File.join(destination_directory, File.basename(file)))
      end
    end

    log(:info, "Processing completed.", at_console: true)
  end

  private

  def valid_paths?
    dir_exist = [origin_directory, destination_directory].filter_map do |dir|
      Dir.exist?(dir) || log(:error, "Directory does not exist: #{dir}")
    end

    !dir_exist.compact.empty?
  end

  def log(level, message, at_console: verbose)
    case level
    when :info
      logger.info(message)
      puts message if at_console
    when :error
      logger.error(message)
      puts "ERROR: #{message}" if at_console
    end
  end

  def clean_string(str)
    encoding = CharDet.detect(str)["encoding"]

    str.force_encoding(encoding).encode("UTF-8").strip
  end

  def execute_command(cmd, log_result: true)
    log(:info, "Executing: #{cmd.join(" ")}") if SHOW_COMMAND

    stdout_str, stderr_str, status = Open3.capture3(*cmd)

    if log_result
      status.success? ? log(:info, "Success: #{clean_string(stdout_str)} #{cmd[2]}") : log(:error, "Failed: #{clean_string(stderr_str)}")
    end

    [stdout_str, stderr_str, status]
  end

  def magic_file_path(file_path, live_photo: false)
    magic_path = File.join(
      File.dirname(file_path),
      File.basename(file_path)
        .gsub(
          /#{ALLOWED_SUFFIXES.map { Regexp.quote(_1) }.join("|")}/,
          ""
        )
    )

    return magic_path unless live_photo

    # remove live photo extension
    magic_path[0...-4]
  end

  def read_json(json_path)
    JSON.parse(File.read(json_path), encoding: "UTF-8")
  rescue JSON::ParserError => e
    log(:error, "Invalid JSON format in #{json_path}: #{e.message}")
    nil
  end

  def check_files(media_files, json_files)
    media_files_from_json = json_files.map { _1[0...-5] }

    missing_json = media_files - media_files_from_json
    missing_media = media_files_from_json - media_files

    base_status = {json_file: nil, processed: false}

    media_files.each do |media_file|
      if missing_json.include?(media_file)
        log(:info, "JSON file is missing for media file: #{media_file}")

        if json_file = fetch_json_file(media_file, json_files)
          log(:info, "Using JSON file via magic: #{json_file}")
          @processed_files[media_file] = base_status.merge(json_file: json_file)
        else
          @processed_files[media_file] = base_status
        end
      else
        @processed_files[media_file] = base_status.merge(json_file: "#{media_file}.json")
      end
    end

    missing_media.each do |file_path|
      log(:info, "Media file is missing for JSON file: #{file_path}")
    end
  end

  def fetch_json_file(file_path, json_files)
    match_file_path = magic_file_path(file_path, live_photo: live_photo?(file_path))

    json_files.each do |json_file|
      return json_file if magic_file_path(json_file).include?(match_file_path)
    end

    nil
  end

  def live_photo?(file_path)
    return false unless LIVE_PHOTO_EXTENSIONS.include?(File.extname(file_path).downcase.delete("."))

    cmd = ["exiftool", "-duration", file_path]
    stdout_str, _, _ = execute_command(cmd, log_result: false)

    stdout_str.match(/Duration *: *(\d+\.\d+) s\n/)[1].to_f < 3
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

    taken_time = Time.at(data.dig("photoTakenTime", "timestamp").to_i, in: offset_time[file_path]).strftime("%Y:%m:%d %H:%M:%S")
    exif_args << "-DateTimeOriginal='#{taken_time}'"
    exif_args << "-FileCreateDate='#{taken_time}'"

    # Update GPS Data
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

    return if exif_args.empty?

    cmd = ["exiftool", "-o", File.join(destination_directory, File.basename(file_path)), *exif_args, file_path]
    execute_command(cmd)
  end
end
