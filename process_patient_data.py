#!/usr/bin/env python3
"""
Patient Data Processing Script

This script processes patient data configuration from command line arguments
and saves the configuration as a JSON file.
"""

import argparse
import json
import sys
from datetime import datetime


def str_to_bool(value):
    """Convert string to boolean value."""
    if isinstance(value, bool):
        return value
    if value.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif value.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def main():
    """Main function to process command line arguments and save configuration."""
    parser = argparse.ArgumentParser(
        description='Process patient data configuration and save as JSON'
    )

    parser.add_argument(
        '--patient-name',
        required=True,
        help='Name of the patient'
    )

    parser.add_argument(
        '--session-name',
        required=True,
        help='Name of the session'
    )

    parser.add_argument(
        '--remove-skull',
        type=str_to_bool,
        required=True,
        help='Whether to remove skull (true/false)'
    )

    parser.add_argument(
        '--denoise',
        type=str_to_bool,
        required=True,
        help='Whether to apply denoising (true/false)'
    )

    parser.add_argument(
        '--output',
        default='patient_config.json',
        help='Output JSON file path (default: patient_config.json)'
    )

    args = parser.parse_args()

    # Create configuration dictionary
    config = {
        'patient_name': args.patient_name,
        'session_name': args.session_name,
        'remove_skull': args.remove_skull,
        'denoise': args.denoise,
        'timestamp': datetime.now().isoformat(),
        'processing_options': {
            'skull_removal': args.remove_skull,
            'denoising': args.denoise
        }
    }

    # Print configuration to terminal by default
    print("=" * 50)
    print("PATIENT DATA PROCESSING CONFIGURATION")
    print("=" * 50)
    print(f"Patient Name: {args.patient_name}")
    print(f"Session Name: {args.session_name}")
    print(f"Remove Skull: {args.remove_skull}")
    print(f"Denoise: {args.denoise}")
    print(f"Timestamp: {config['timestamp']}")
    print("=" * 50)

    try:
        # Save configuration to JSON file
        with open(args.output, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"\n✅ Configuration saved to {args.output}")

    except Exception as e:
        print(f"❌ Error saving configuration: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
