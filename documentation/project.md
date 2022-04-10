# The structure of project.json

The file contains a Dictionary / Map with the following key/value pairs:

## Key: "todo"

The value to the todo key is a list of Maps. Each element of this list describes a ChronoNote:

### ChronoNote

Each ChronoNote is described by two key/value pairs:

- "text": The note itself.
- "datetime": A ISO representation of the python datetime object, describing the time at which the note was created.

## Key: "name"

The name of the ChronoProject. This can be any (reasonable) string.

## Key: "path"

This should be "project", but can be any string that constitutes a valid file name (excluding the file extension).

## Key: "sevents"

A list of all ChronoTimes, which in turn a represented as Maps.

### ChronoTimes

Each ChronoTime is described by two key/value pairs:

- "tdate": ISO string format representation of the date.
- "start": ISO string format representation of the time.
- "what": A short string describing the ChronoTime
- "tags": A list of user-generated tags (strings).

## Key: "days"

A Map of ChronoDays. The key to each ChronoDay is the ISO formatted string of its date. 

### ChronoDay
Each day is a Map with the following key/value pairs:

- "date": same as the key
- A list of 3 values:
    - "bedtime_start" (HH:MM)
    - "bedtime_end" (HH:MM)
    - a boolean indicating if the bedtime start and the bedtime end are on different days.
- "events": Map of the form 
```javascript
{"start":"ISO_date","end":"ISO_date","what":"Description","tags":["List","of","tags"]}
```
- "sport": Map of the form
    - "runs" : List of Maps of the form 
        - "time" : Int
        - "distance": Float
        - "start_time" : String (HH:MM)
    - "pushups": List of Maps of the form
        - "times": List of floats
        - "mults": List of ints
        - "start_time" : String (HH:MM)
    - "planks": List of Maps of the form 
        - "time": Float
        - "start_time" : String (HH:MM)
    - "situps": List of Maps of the form 
        - "time": Float
        - "mult": Int
        - "start_time" : String (HH:MM)