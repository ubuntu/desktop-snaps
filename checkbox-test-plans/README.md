The following instructions were developed from setting up the checkbox testing tool on a lunar VM.

# Setting up checkbox dependencies



# Setting up checkbox

$ sudo snap install checkbox --classic
$ sudo snap install checkbox22

If you have not made a provider yet (very first run), then go ahead and do that

$ checkbox.checkbox-cli startprovider --empty com.gnome-calculator:myprovider

Test cases (aka "jobs") are listed in .pxu files in units/

$ cd com.desktop-snaps\:myprovider
$ mkdir units && cd units
