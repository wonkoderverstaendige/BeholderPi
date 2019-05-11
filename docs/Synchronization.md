# NTP synchronization
## Chrony
Chrony acts as both NTP client as well as NTP server. We want to quickly synchronize on startup and then keep all
devices closely locked to within ~1 ms.

- Beholder acts as NTP server (with the `allow` directive).
- Spectator as secondary server to keep all log files and events synchronized?

## Current state (11-May-2019)
- chrony on Beholder keeps halting. Perhaps networking issue to sources on startup?

## Logging
- track logging information on the eyes to see actual offsets and throw into influxdb?
