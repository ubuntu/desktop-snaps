# updatesnap

A simple script that checks a snapcraft yaml file and shows possible new versions for each part

## Installing

Just run:

    sudo install.sh

will install it at /usr/local/bin

## Using it

Just run *updatesnap.py [-s] [-r] [--github-user=...] [--github-token=...] /path/to/snapcraft.yaml*.
Optionally, you can add a Part name, and updatesnap will check only that part, instead of all. Also,
you can replace the file path with a HTTP or HTTPS path, and updatesnap will download and process it.

The output is like this:

```
  Part: libsoup3 (https://gitlab.gnome.org/GNOME/libsoup.git)
    Current tag: 3.0.6
    Current tag date: 2022-03-31 13:33:55-05:00
    Tag updated

  Part: librest (https://gitlab.gnome.org/GNOME/librest.git)
    Current tag: 0.8.1
    Current tag date: 2017-05-12 10:16:04+02:00
    Newer tags:
      0.9.1 (2022-06-19 12:28:19+02:00)
      0.9.0 (2022-01-12 19:15:20+00:00)
      1.0.0 (2022-01-12 19:15:20+00:00)

  Part: gtk3 (https://gitlab.gnome.org/GNOME/gtk.git)
    Current tag: 3.24.34
    Current tag date: 2022-05-18 14:52:03-04:00
    Newer tags:
      4.6.5 (2022-05-30 16:26:00-04:00)

```

The first line contains the part name and the repository URI.
The second line contains the current branch or tag configured in the YAML file.
If this part uses a branch, it will recommend to switch to an specific tag.
The third line contains the date that the current tag was uploaded.
After that it can be a "Tag updated" text, which means that there are
no tags more recent that the current one, or the text "Newer tags", and
a list of all the tags pushed more recently than the current one.

In this example, libsoup3 is fully updated, librest has three newer tags,
but they seems to be a new major version (1.0.0) and a development version
(0.9.0 and 0.9.1), and Gtk3 has a newer tag, but it is for Gtk4, so we
must ignore it.

After this "running" data, a summary will be also shown, like this:

```
gjs current version: 1.72.3 (2022-09-20 20:05:01-07:00); available updates:
    1.75.1 (tagget at 2022-10-29 16:05:31-07:00)
    1.74.1 (tagget at 2022-10-29 15:57:47-07:00)
    1.74.0 (tagget at 2022-09-20 20:19:18-07:00)

glib current version: 2.74.1 (2022-10-25 13:53:22+01:00); available updates:
    2.74.2 (tagget at 2022-11-24 12:29:05+00:00)
    2.75.0 (tagget at 2022-11-10 09:18:47+00:00)
```

It contains only those parts that have available updates, or have any kind
of problem (like requiring a version format).

Setting the *-r* parameter, it won't search for a *snapcraft.yaml* file in
the specified folder, but will search it in each folder inside that folder.
This is useful when you have an specific folder with several *snap* projects,
each one in its own folder, and want to check all of them.

The *-s* parameter makes it *silent*, so nothing will be shown in the screen
during the process, only the final summary. It is useful for unnatended
processing.

The *--github-user=...* and *--github-token=* parameters allows to specify a
user and a token for the connections to github, allowing to avoid the access
limits.

## The .secrets file

Optionally it is possible to configure a YAML file named *updatesnap.secrets* and put it
at *~/.config/updatesnap/*. This file can contain a Github username and token to
avoid the access limits that Github imposes to anonymous API requests. The format
is the following:

```
github:  
    user: *username*  
    token: *github access token*
```

## Extra tokens in the snapcraft.yaml file

It is possible to add extra tokens in the snapcraft.yaml file to allow to specify
extra metadata about versions. These extra tokens are added as comments to avoid
them interferring with snap*. The format is the following:

```
parts:
  PART_NAME:
    PART_TOKENS
# ext:updatesnap
#   version-format:
#     EXTRA_TOKENS
# endext
    MORE_PART_TOKENS
```

The "# endext" line is optional. This format is designed to allow *update_snaps* to
just replace the '#' symbol with an space in the lines between 'ext:updatesnap' and
'endext', converting that in standard YAML code.

The available extra tokens are:

* format: includes an string specifying the version format. Thus, if the tags for this
  part are in the form "pixman-0.40.0", then the token should be:

    format: "pixman-%M.%m.%R"

  The %M token specifies where is the Major value; the %m specifies the minor, and
  the %R the revision.

  If the format is "%M.%m.%R", "%M.%m" or "v%M.%m.%R", *update_snap* will autodetect
  it, so in those cases it can be skipped.
* lower-than: followed by a version number in %M.%m.%R format, specifies that the only
  valid version values must be lower than that specified. An example is Gtk3, which
  has "lower-than: 4" to avoid showing Gtk4 updates.
* ignore-odd-minor: if specified as TRUE, version numbers with odd minor values will be
  ignored, because they are presumed to be development versions.
* same-major: if specified as TRUE, version numbers with a different major value than the
  current version will be ignored.
* same-minor: if specified as TRUE, version numbers with a different minor value than the
  current version will be ignored.
* no-9x-revisions: if specified as TRUE, version numbers with a revision value equal or
  greater than 90 will be ignored. Useful for projects that use these revision numbers
  as "prelude" to a new minor version.
* ignore: don't try to check this entry. Useful for "archived" projects.

## TODO

* Migrate to specific github and gitlab modules instead of using custom code

