# Changelog

All notable changes to the Standup Discord Bot project will be documented in this file.

## [1.1.0] - 2024-03-07

### Added
- Separated thread creation from reminder function
- Added 15-minute checks after midnight to create the day's thread early
- Added global tracking of today's thread with the `today_thread` variable
- Added `/refresh-thread` command to manually refresh the thread reference

### Changed
- Thread is now created after midnight instead of at reminder time
- Reminder now uses the existing thread instead of creating a new one
- Added explicit AM/PM clarification for reminder and follow-up times
- Improved message formatting for better readability
- Updated logs to be more descriptive

### Removed
- Removed `/test` command as it was redundant

### Fixed
- Thread creation and tracking now more reliable
- Reminder and followup functions now consistently use the same thread
- Clarified that reminder and deadline times are in 24-hour format (10:30 = 10:30 AM)

## [1.0.0] - Initial Release

### Features
- Daily standup reminders at configurable times
- Automatic thread creation with proper date formatting
- Follow-up reminders for users who haven't responded
- User management commands for the notification list
- Customizable reminder times, deadlines, and timezone settings
- Daily and weekly report generation
- Customizable standup templates
- Automatic tracking of user responses 