require_relative "base_handler"

module GAlbumTools
  module Handlers
    class MetadataHandler < BaseHandler
      protected

      def process
        log(:info, "Handling missing metadata for file: #{row["Media File"]}")

        # Check if file exists
        unless File.exist?(row["Media File"])
          log(:warn, "File does not exist: #{row["Media File"]}")
          return false
        end

        # Check if this is a live photo - if so, try to use metadata from the related file
        if is_live_photo(row["Media File"])
          success = handle_live_photo(row["Media File"])
          return success if success
        end

        # For missing metadata, we can try to extract what we can from the file itself
        dest_dir = File.dirname(row["Destination File"] || row["Media File"])
        file_name = File.basename(row["Media File"])
        dest_file = File.join(dest_dir, file_name)

        # Create destination directory if it doesn't exist
        FileUtils.mkdir_p(dest_dir) unless Dir.exist?(dest_dir)

        # Copy file to destination if they're different
        if row["Media File"] != dest_file
          begin
            FileUtils.cp(row["Media File"], dest_file)
            log(:info, "Copied file to destination: #{dest_file}")
          rescue => e
            log(:error, "Failed to copy file: #{e.message}")
            return false
          end
        end

        # Try to extract basic metadata from file
        cmd = [
          "exiftool",
          "-m", # Ignore minor errors
          "-overwrite_original",
          "-FileModifyDate>DateTimeOriginal",
          "-FileCreateDate>CreateDate",
          dest_file
        ]

        stdout_str, stderr_str, status = execute_command(cmd)

        # For missing metadata, we'll consider it handled
        # even if we couldn't extract much from the file
        true
      end

      private

      def is_live_photo(file_path)
        ext = File.extname(file_path).downcase
        base_name = File.basename(file_path, ".*")
        dir_name = File.dirname(file_path)

        # Check if this is a video file with a corresponding image
        if VIDEO_EXTENSIONS.include?(ext)
          IMAGE_EXTENSIONS.each do |image_ext|
            image_path = File.join(dir_name, "#{base_name}#{image_ext}")
            return true if File.exist?(image_path)
          end
        # Check if this is an image file with a corresponding video
        elsif IMAGE_EXTENSIONS.include?(ext)
          VIDEO_EXTENSIONS.each do |video_ext|
            video_path = File.join(dir_name, "#{base_name}#{video_ext}")
            return true if File.exist?(video_path)
          end
        end

        false
      end

      def handle_live_photo(file_path)
        ext = File.extname(file_path).downcase
        base_name = File.basename(file_path, ".*")
        dir_name = File.dirname(file_path)
        dest_dir = File.dirname(row["Destination File"] || file_path)
        dest_file = File.join(dest_dir, File.basename(file_path))

        # Find the related file (image or video)
        related_file = nil
        related_json = nil

        if VIDEO_EXTENSIONS.include?(ext)
          # This is a video, look for the image
          IMAGE_EXTENSIONS.each do |image_ext|
            image_path = File.join(dir_name, "#{base_name}#{image_ext}")
            if File.exist?(image_path)
              related_file = image_path
              # Look for JSON for the image
              json_path = File.join(dir_name, "#{base_name}.json")
              related_json = json_path if File.exist?(json_path)
              break
            end
          end
        elsif IMAGE_EXTENSIONS.include?(ext)
          # This is an image, look for the video
          VIDEO_EXTENSIONS.each do |video_ext|
            video_path = File.join(dir_name, "#{base_name}#{video_ext}")
            if File.exist?(video_path)
              related_file = video_path
              # Look for JSON for the image (since that's usually where the metadata is)
              json_path = File.join(dir_name, "#{base_name}.json")
              related_json = json_path if File.exist?(json_path)
              break
            end
          end
        end

        # If we found a related file and its JSON, use its metadata
        if related_file && related_json
          log(:info, "Found related live photo file and JSON: #{related_file}")

          # Create destination directory if needed
          FileUtils.mkdir_p(dest_dir) unless Dir.exist?(dest_dir)

          # Copy the file to destination
          begin
            FileUtils.cp(file_path, dest_file)
            log(:info, "Copied file to destination: #{dest_file}")
          rescue => e
            log(:error, "Failed to copy file: #{e.message}")
            return false
          end

          # Apply metadata from the related file's JSON
          begin
            json_data = JSON.parse(File.read(related_json))

            # Extract relevant metadata
            cmd = ["exiftool", "-m", "-overwrite_original"]

            # Add date/time if available
            if json_data["photoTakenTime"] && json_data["photoTakenTime"]["timestamp"]
              timestamp = json_data["photoTakenTime"]["timestamp"].to_i
              date_time = Time.at(timestamp).strftime("%Y:%m:%d %H:%M:%S")
              cmd << "-DateTimeOriginal=#{date_time}"
              cmd << "-CreateDate=#{date_time}"
            end

            # Add location if available
            if json_data["geoData"] && json_data["geoData"]["latitude"] && json_data["geoData"]["longitude"]
              lat = json_data["geoData"]["latitude"]
              lng = json_data["geoData"]["longitude"]
              alt = json_data["geoData"]["altitude"] || 0

              cmd << "-GPSLatitude=#{lat}"
              cmd << "-GPSLongitude=#{lng}"
              cmd << "-GPSAltitude=#{alt}"
              cmd << "-GPSLatitudeRef=#{lat >= 0 ? 'N' : 'S'}"
              cmd << "-GPSLongitudeRef=#{lng >= 0 ? 'E' : 'W'}"
            end

            # Add title and description if available
            if json_data["title"] && !json_data["title"].empty?
              title = clean_string(json_data["title"])
              cmd << "-Title=#{title}"
            end

            if json_data["description"] && !json_data["description"].empty?
              description = clean_string(json_data["description"])
              cmd << "-Description=#{description}"
              cmd << "-ImageDescription=#{description}"
            end

            # Add destination file to command
            cmd << dest_file

            # Execute command if we have metadata to add
            if cmd.size > 3
              stdout_str, stderr_str, status = execute_command(cmd)
              log(:info, "Applied metadata from related live photo to: #{dest_file}")
              return status.success?
            end
          rescue => e
            log(:error, "Failed to apply metadata from related live photo: #{e.message}")
          end
        end

        # If we get here, we either didn't find a related file/JSON, or failed to apply metadata
        false
      end
    end
  end
end
