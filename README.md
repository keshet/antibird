AntiBird
========
This is a simple script to schedule playback from a volumio server.
Here it is used to play sounds to scare away birds at sunrise and sunset.
It has been tested on a Raspberry Pi 3B running the volumio image.

See: https://volumio.com/en/get-started/

Edit antibird.py to set your sounds and schedule and copy to the volumio host.

To start automatically at system start copy antibird.service to the volumio host to /etc/systemd/system.
Then run the command: `systemctl enable antibird`
