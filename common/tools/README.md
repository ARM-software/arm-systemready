# Tools

## config_update_tool.sh

### Overview
`config_update_tool.sh` is a Bash script designed to update the ACS configuration files in a prebuilt image. It provides two modes of operation, which can be changed from within the script:
- **get**: Retrieves the `config` directory from the image and copies it to a local path.
- **put**: Uploads a local `acs_config.txt` file to the image.

### Usage
```bash
./config_update_tool.sh <path to ACS prebuilt image> <path to acs_config file> <path to copy acs_results or n to skip copying of the results>
```

#### Arguments:
1. **`<path to ACS prebuilt image>`**: The path to the ACS prebuilt image that will be mounted.
2. **`<path to acs_config file>`**: The path to the local configuration file to be updated in the image.
3. **`<path to copy acs_results or n>`**: *(Optional)* The directory where `acs_results` will be copied. If omitted, the ACS image directory is used by default. Use `n` to skip copying results.

#### Help Option
To display usage information, run:
```bash
./config_update_tool.sh -h
```
---
This script streamlines the process of updating ACS configuration files in prebuilt images, incorporating error handling and automation. Additionally, it can be used to copy the ACS image results directory.

### Notes

- The script requires `sudo` privileges for mounting and copying files.

--------------

*Copyright (c) 2025, Arm Limited and Contributors. All rights reserved.*
