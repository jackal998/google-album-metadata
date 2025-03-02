#!/usr/bin/env ruby

require 'minitest/autorun'
require_relative '../lib/g_album_tools'

class TestErrorHandler < Minitest::Test
  def setup
    @test_dir = File.join(File.dirname(__FILE__), 'fixtures')
    @csv_dir = File.join(@test_dir, 'csv')
    @media_dir = File.join(@test_dir, 'media')
    @dest_dir = File.join(@test_dir, 'destination')

    # Create test directories if they don't exist
    FileUtils.mkdir_p(@csv_dir)
    FileUtils.mkdir_p(@media_dir)
    FileUtils.mkdir_p(@dest_dir)

    # Create a test CSV file
    create_test_csv

    # Create test media files
    create_test_media_files

    @handler = GAlbumTools::ErrorHandler.new(verbose: true)
  end

  def teardown
    # Clean up test files and directories
    # FileUtils.rm_rf(@test_dir) if File.directory?(@test_dir)
  end

  def test_error_categorization
    # Test error categorization for different error types
    assert_equal :no_json, @handler.categorize_error("No JSON file found")
    assert_equal :no_json, @handler.categorize_error("Could not find JSON metadata")

    assert_equal :unknown_pattern, @handler.categorize_error("Unknown filename pattern")
    assert_equal :unknown_pattern, @handler.categorize_error("Filename does not match expected pattern")

    assert_equal :live_photo_missing_part, @handler.categorize_error("Live photo missing video part")
    assert_equal :live_photo_missing_part, @handler.categorize_error("Could not find corresponding image file")

    assert_equal :invalid_or_truncated, @handler.categorize_error("Invalid or truncated file")
    assert_equal :invalid_or_truncated, @handler.categorize_error("File is truncated")

    assert_equal :unknown, @handler.categorize_error("Some other random error")
    assert_equal :unknown, @handler.categorize_error("")
    assert_equal :unknown, @handler.categorize_error(nil)
  end

  def test_load_errors_from_csv
    # Test loading errors from CSV
    errors = @handler.load_errors_from_csv([File.join(@csv_dir, 'test_output.csv')])

    assert_equal 4, errors.size

    # Check error types
    error_types = errors.map { |e| e[:error_type] }
    assert_includes error_types, :no_json
    assert_includes error_types, :unknown_pattern
    assert_includes error_types, :live_photo_missing_part
    assert_includes error_types, :invalid_or_truncated
  end

  def test_error_stats
    # Test error statistics
    errors = @handler.load_errors_from_csv([File.join(@csv_dir, 'test_output.csv')])
    stats = @handler.error_stats(errors)

    assert_equal 4, stats[:total]
    assert_equal 1, stats[:no_json]
    assert_equal 1, stats[:unknown_pattern]
    assert_equal 1, stats[:live_photo_missing_part]
    assert_equal 1, stats[:invalid_or_truncated]
    assert_equal 0, stats[:unknown]
  end

  private

  def create_test_csv
    csv_path = File.join(@csv_dir, 'test_output.csv')

    File.open(csv_path, 'w') do |f|
      f.puts "Media File,Destination File,Processed,Errors"

      # Create a row for each error type
      f.puts "#{File.join(@media_dir, 'test1.jpg')},#{File.join(@dest_dir, 'test1.jpg')},false,No JSON file found"
      f.puts "#{File.join(@media_dir, 'test2.jpg')},#{File.join(@dest_dir, 'test2.jpg')},false,Unknown filename pattern"
      f.puts "#{File.join(@media_dir, 'test3.jpg')},#{File.join(@dest_dir, 'test3.jpg')},false,Live photo missing video part"
      f.puts "#{File.join(@media_dir, 'test4.mp4')},#{File.join(@dest_dir, 'test4.mp4')},false,Invalid or truncated file"

      # Create a row for a successful file
      f.puts "#{File.join(@media_dir, 'test5.jpg')},#{File.join(@dest_dir, 'test5.jpg')},true,"
    end
  end

  def create_test_media_files
    # Create dummy media files
    ['test1.jpg', 'test2.jpg', 'test3.jpg', 'test4.mp4', 'test5.jpg'].each do |file|
      File.open(File.join(@media_dir, file), 'w') do |f|
        f.puts "Dummy file content"
      end
    end
  end
end
