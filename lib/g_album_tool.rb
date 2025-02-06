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

  attr_reader :verbose, :logger, :source_directory, :destination_directory, :offset_time, :processed_files, :create_output_csv

  def initialize(verbose, source_directory, destination_directory, create_output_csv)
    @verbose = verbose
    @source_directory = source_directory
    @destination_directory = destination_directory
    @processed_files = {}
    @logger = Logger.new(LOG_FILE)
    @logger.level = Logger::INFO
    @create_output_csv = create_output_csv
  end

  def process
    return log(:error, "Source directory does not exist: #{source_directory}") unless Dir.exist?(source_directory)

    log(:info, "Processing files in directory: #{source_directory}", at_console: true)

    FileUtils.mkdir_p(destination_directory) unless Dir.exist?(destination_directory)

    load_offset_times

    source_directories = Dir.glob(File.join(source_directory, "**/"))
    source_directories.each do |dir|
      check_files(dir)
      next log(:info, "#{dir} No valid media found.") if processed_files[dir].empty?

      current_destination_directory = dir.gsub(source_directory, destination_directory)
      FileUtils.mkdir_p(current_destination_directory) unless Dir.exist?(current_destination_directory)

      if create_output_csv
        @output_csv = File.new(File.join(File.dirname(current_destination_directory), "#{File.basename(current_destination_directory)}_output.csv"), "w")
        @output_csv.puts("Processed,Media File,JSON File,Messages,Errors")
      end

      processed_files[dir].each do |file, info|
        if info[:json_file]
          result = update_metadata(file, read_json(info[:json_file]), current_destination_directory)

          if result[:success]
            info[:processed] = true # not used for now
            @output_csv.puts("true,#{file},#{info[:json_file]},#{result[:messages]},") if create_output_csv
          else
            @output_csv.puts("false,#{file},#{info[:json_file]},,#{result[:errors]}") if create_output_csv
            FileUtils.cp(file, File.join(current_destination_directory, File.basename(file)))
          end
        else
          @output_csv.puts("false,#{file},,,No JSON file found.") if create_output_csv
          FileUtils.cp(file, File.join(current_destination_directory, File.basename(file)))
        end
      end

      @output_csv.close if create_output_csv
    end

    log(:info, "Processing completed.", at_console: true)
  end

  private

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
    return if str.nil? || str.empty?

    encoding = CharDet.detect(str)["encoding"]
    str.force_encoding(encoding).encode("UTF-8").strip
  end

  def execute_command(cmd, log_result: true)
    log(:info, "Executing: #{cmd.join(" ")}") if SHOW_COMMAND

    stdout_str, stderr_str, status = Open3.capture3(*cmd)

    stdout_str = clean_string(stdout_str)
    stderr_str = clean_string(stderr_str)

    if log_result
      status.success? ? log(:info, "Success: #{stdout_str} #{cmd[2]}") : log(:error, "Failed: #{stderr_str}")
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

  def check_files(dir)
    media_files = Dir.glob(File.join(dir, "*.{#{SUPPORTED_EXTENSIONS.join(",")}}")).select { |f| File.file?(f) }
    json_files = Dir.glob(File.join(dir, "*.json")).select { |f| File.file?(f) }

    media_files_from_json = json_files.map { _1[0...-5] }

    missing_json = media_files - media_files_from_json
    missing_media = media_files_from_json - media_files

    @processed_files[dir] = {}

    media_files.each do |media_file|
      json_file =
        if missing_json.include?(media_file)
          log(:info, "JSON file is missing for media file: #{media_file}")
          fetch_json_file(media_file, json_files)
        else
          "#{media_file}.json"
        end

      @processed_files[dir][media_file] = {json_file: json_file, processed: false}
    end

    missing_media.each do |file_path|
      log(:info, "Media file is missing for JSON file: #{file_path}")
    end
  end

  def fetch_json_file(file_path, json_files)
    match_file_path = magic_file_path(file_path, live_photo: live_photo?(file_path))

    json_files.each do |json_file|
      next unless magic_file_path(json_file).include?(match_file_path)

      log(:info, "Using JSON file via magic: #{json_file}")
      return json_file
    end

    nil
  end

  def live_photo?(file_path)
    return false unless LIVE_PHOTO_EXTENSIONS.include?(File.extname(file_path).downcase.delete("."))

    cmd = ["exiftool", "-duration", file_path]
    stdout_str, _, _ = execute_command(cmd, log_result: false)

    stdout_str.match(/Duration *: *(\d+\.\d+) s/)[1].to_f < 3
  end

  def load_offset_times
    @offset_time = CSV.read(OFFSET_TIMES_PATH, headers: true, encoding: "bom|utf-16le:utf-8").filter_map do |row|
      offset_time_values = row.values_at(*OFFSET_TIMES_KEYS)
      next if offset_time_values.all? { _1 == "-" }
      next log(:info, "Invalid offset time data in #{row}") if offset_time_values.uniq.size > 1

      [row["SourceFile"], offset_time_values.first]
    end.to_h
  end

  def update_metadata(file_path, data, current_destination_directory)
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

    cmd = ["exiftool", "-o", File.join(current_destination_directory, File.basename(file_path)), *exif_args, file_path]
    stdout_str, stderr_str, status = execute_command(cmd)

    {}.tap do |result|
      result[:success] = status.success?
      result[:errors] = stderr_str&.tr("\n", ";")
      result[:messages] = stdout_str&.tr("\n", ";")
    end
  end
end
