require "rake/testtask"
require "yard"
begin
  require "rspec/core/rake_task"
  RSpec::Core::RakeTask.new(:spec)
rescue LoadError
  # RSpec not available
end

# Set default task to run RSpec tests
task :default => [:spec]

# Define documentation task with YARD
YARD::Rake::YardocTask.new do |t|
  t.files = ["lib/**/*.rb"]
  t.options = ["--markup", "markdown"]
end

desc "Run rubocop"
task :lint do
  sh "bundle exec rubocop"
end

desc "Check dependencies and system configuration"
task :check do
  ruby "./bin/g_album_tool info"
end

desc "Install dependencies"
task :setup do
  sh "bundle install"
end

desc "Clean generated files"
task :clean do
  FileUtils.rm_rf("doc")
  FileUtils.rm_rf(".rspec_status")
  puts "Cleaned documentation and RSpec status files"
end
