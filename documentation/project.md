# The structure of project.json

The file contains a Dictionary / Map with the following key/value pairs:

## Key: "todo"

The value to the todo key is a list of Maps. Each element of this list describes a ChronoNote:

### ChronoNote

Each ChronoNote is describes by two key/value pairs:

- "text": The note itself.
- "datetime": A ISO representation of the python datetime object, describing the time at which the note was created.

## Key: "name"

The name of the ChronoProject. This can be any (reasonable) string.

## Key: "path"

This should be "project", but can be any string that constitutes a valid file name (excluding the file extension).

## Key: "sevents"

A list of all ChronoTimes, which in turn a represented as Maps.

### ChronoTimes

Each ChronoNote is describes by two key/value pairs:

- "tdate": ISO string format representation of the date.
- "start": ISO string format representation of the time.
- "what": A short string describing the ChronoTime
- "tags": A list of user generated tags (strings).

## Key: "days"