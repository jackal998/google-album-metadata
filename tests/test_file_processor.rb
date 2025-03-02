#!/usr/bin/env ruby

require 'minitest/autorun'
require_relative '../lib/g_album_tools'

class TestFileProcessor < Minitest::Test
  def setup
    @test_source_dir = File.join(File.dirname(__FILE__), 'fixtures', 'source')
    @test_dest_dir = File.join(File.dirname(__FILE__), 'fixtures', 'destination')

    # Create test directories if they don't exist
    FileUtils.mkdir_p(@test_source_dir)
    FileUtils.mkdir_p(@test_dest_dir)

    # Create test options
    @options = {
      source_directory: @test_source_dir,
      destination_directory: @test_dest_dir,
      verbose: true
    }

    @processor = GAlbumTools::FileProcessor.new(@options)
  end

  def teardown
    # Clean up test files and directories
    # FileUtils.rm_rf(@test_dest_dir) if File.directory?(@test_dest_dir)
  end

  def test_initialization
    assert_equal @test_source_dir, @processor.source_directory
    assert_equal @test_dest_dir, @processor.destination_directory
    assert_equal({}, @processor.processed_files)
    assert_equal [], @processor.offset_time
  end

  def test_is_allowed_file_format
    assert @processor.is_allowed_file_format?('test.jpg')
    assert @processor.is_allowed_file_format?('test.jpeg')
    assert @processor.is_allowed_file_format?('test.png')
    assert @processor.is_allowed_file_format?('test.mp4')
    assert @processor.is_allowed_file_format?('test.mov')

    refute @processor.is_allowed_file_format?('test.txt')
    refute @processor.is_allowed_file_format?('test.pdf')
    refute @processor.is_allowed_file_format?('test.doc')
  end

  def test_live_photo_detection
    # This test would require setting up fixture files
    skip "Need to create proper fixture files for live photo testing"

    # Example of how the test would work:
    # Create test image and video files with matching names
    # FileUtils.touch(File.join(@test_source_dir, 'live_photo.jpg'))
    # FileUtils.touch(File.join(@test_source_dir, 'live_photo.mov'))
    # assert @processor.live_photo?(File.join(@test_source_dir, 'live_photo.jpg'))
    # assert @processor.live_photo?(File.join(@test_source_dir, 'live_photo.mov'))
  end

  def test_find_json_file
    # This test would require setting up fixture files
    skip "Need to create proper fixture files for JSON file finding"

    # Example of how the test would work:
    # Create test JSON file
    # json_path = File.join(@test_source_dir, 'photo.json')
    # FileUtils.touch(json_path)
    # assert_equal json_path, @processor.find_json_file(@test_source_dir, 'photo')
  end
end
