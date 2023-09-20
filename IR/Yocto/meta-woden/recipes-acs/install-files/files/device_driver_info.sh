#!/bin/bash

output_file="device_driver_info.log"

# Search within /sys for directories with non-empty drivers subdirectory
find /sys -type d -name drivers -exec bash -c '
    driver_dir=$(dirname "$0")  # Path to the driver subdirectory
    if [ -n "$(ls -A "$0")" ]; then
        parent_name=$(basename "$driver_dir")  # Extract the parent directory name
        for driver_name in $(ls "$0"); do
            echo "$parent_name : $driver_name" >> "$1"
        done
    fi
' {} "$output_file" \;
echo "$1"
echo "Device and Driver information saved to $output_file"
