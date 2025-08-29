#!/usr/bin/env python3
"""
Script to reduce size of GFS forecast grib file.
"""

import argparse
import eccodes
from pathlib import Path


def parse_vtable(vtable_path):
    """
    Parses a GFS vtable file and extracts GRIB2 filter dictionaries.
    """
    filters = []
    with Path.open(vtable_path, "r") as f:
        for line in f:
            var_line = line.strip()
            # Skipcomments  and  header separator lines
            if not var_line or var_line.startswith(("#", "-----")):
                continue

            # Skip the main header line explicitly
            if var_line.startswith(("GRIB1", "Param|")):
                continue

            # Split by '|'
            parts = [part.strip() for part in var_line.split("|")]

            if len(parts) < 11:
                print(f"Warning: Not enough columns after splitting by '|' (skipping): {var_line}")
                continue

            try:
                # Extract GRIB2 relevant columns
                grib2_discp = int(parts[7])
                grib2_catgy = int(parts[8])
                grib2_param = int(parts[9])
                grib2_level_type = int(parts[10]) # This is typeOfFirstFixedSurface

                level1_str = parts[2].replace("*", "").strip()

                current_filter = {
                    "discipline": grib2_discp,
                    "parameterCategory": grib2_catgy,
                    "parameterNumber": grib2_param,
                    "typeOfFirstFixedSurface": grib2_level_type
                }

                # Handle specific level types and add additional filters when necessary
                if grib2_level_type == 103 and level1_str.isdigit(): # for height above ground
                    current_filter["scaledValueOfFirstFixedSurface"] = int(level1_str)
                    current_filter["scaleFactorOfFirstFixedSurface"] = 0

                filters.append(current_filter)

            except ValueError as e:
                print(f"Warning: Could not parse data in line (skipping): {var_line} - Error: {e}")
            except IndexError as e:
                print(f"Warning: Indexing error in line (skipping): {var_line} - Error: {e}")

    return filters

def extract_grib_messages(input_file, output_file, filters):
    num_extracted = 0
    with Path.open(input_file, "rb") as f_in, Path.open(output_file, "wb") as f_out:
        while True:
            gid = eccodes.codes_grib_new_from_file(f_in)
            if gid is None:
                break

            for filter_keys in filters:
                current_grib_message_matches_this_filter = True

                # Check for direct key matches first
                for key, expected_value in filter_keys.items():
                    try:
                        actual_value = eccodes.codes_get_long(gid, key)
                        if actual_value != expected_value:
                            current_grib_message_matches_this_filter = False
                            break
                    except eccodes.MissingKeyError:
                        current_grib_message_matches_this_filter = False
                        break

                if not current_grib_message_matches_this_filter:
                    continue

                if current_grib_message_matches_this_filter:
                    eccodes.codes_write(gid, f_out)
                    num_extracted += 1
                    break

            eccodes.codes_release(gid)
    print(f"Extracted {num_extracted} GRIB messages to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter GRIB2 forecast files based on GFS Vtable")

    parser.add_argument("vtable_file", help="Path to GFS Vtable file")
    parser.add_argument("forecast_file", help="Path to GFS GRIB2 forecast file")
    parser.add_argument("outfile", help="Path to output filtered grib file")

    args = parser.parse_args()

    print(f"Parsing vtable from: {args.vtable_file}")
    grib_filters = parse_vtable(args.vtable_file)

    if not grib_filters:
        print("No filters generated from vtable. Exiting.")
    else:
        print(f"Generated {len(grib_filters)} filters.")
        print("Generated filters:")
        for f in grib_filters:
            print(f)
        print("Starting GRIB message extraction...")
        extract_grib_messages(args.forecast_file, args.outfile, grib_filters)
        print("Extraction complete.")
