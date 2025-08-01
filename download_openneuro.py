#!/usr/bin/env python3
"""
OpenNeuro Dataset Downloader

This script downloads datasets from OpenNeuro and prepares them for DIPY processing.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import glob


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


def run_command(command, description=""):
    """Run a shell command and handle errors."""
    print(f"\n🔄 {description}")
    print(f"Command: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def download_openneuro_dataset(dataset_id, subject_id, session_id=None, download_dir="data"):
    """Download dataset from OpenNeuro using openneuro-py."""
    print("=" * 60)
    print("DOWNLOADING OPENNEURO DATASET")
    print("=" * 60)
    
    # Create download directory
    Path(download_dir).mkdir(exist_ok=True)
    
    # Build openneuro-py download command
    cmd = ["openneuro", "download", dataset_id, download_dir]
    
    # Add subject filter
    if subject_id:
        cmd.extend(["--include", f"{subject_id}*"])
    
    # Add session filter if specified
    if session_id:
        cmd.extend(["--include", f"*{session_id}*"])
    
    run_command(cmd, f"Downloading {dataset_id}")
    
    return os.path.join(download_dir, dataset_id)


def find_dwi_files(dataset_path, subject_id, session_id=None):
    """Find DWI files in the downloaded dataset."""
    print("\n🔍 Searching for DWI files...")
    
    # Build search patterns
    if session_id:
        search_patterns = [
            f"{dataset_path}/{subject_id}/{session_id}/dwi/*.nii.gz",
            f"{dataset_path}/{subject_id}/{session_id}/dwi/*.bval",
            f"{dataset_path}/{subject_id}/{session_id}/dwi/*.bvec"
        ]
    else:
        search_patterns = [
            f"{dataset_path}/{subject_id}/*/dwi/*.nii.gz",
            f"{dataset_path}/{subject_id}/dwi/*.nii.gz",
            f"{dataset_path}/{subject_id}/*/dwi/*.bval",
            f"{dataset_path}/{subject_id}/dwi/*.bval",
            f"{dataset_path}/{subject_id}/*/dwi/*.bvec",
            f"{dataset_path}/{subject_id}/dwi/*.bvec"
        ]
    
    dwi_files = {}
    
    # Find files
    for pattern in search_patterns:
        files = glob.glob(pattern)
        for file_path in files:
            filename = os.path.basename(file_path)
            if filename.endswith('.nii.gz') and 'dwi' in filename:
                dwi_files['dwi'] = file_path
            elif filename.endswith('.bval'):
                dwi_files['bval'] = file_path
            elif filename.endswith('.bvec'):
                dwi_files['bvec'] = file_path
    
    print(f"Found DWI files:")
    for key, path in dwi_files.items():
        print(f"  {key}: {path}")
    
    return dwi_files


def main():
    """Main function to download dataset and prepare file information."""
    parser = argparse.ArgumentParser(
        description='Download OpenNeuro dataset for DIPY processing'
    )
    
    parser.add_argument(
        '--dataset-id',
        required=True,
        help='OpenNeuro dataset ID (e.g., ds000030)'
    )
    
    parser.add_argument(
        '--subject-id',
        required=True,
        help='Subject ID (e.g., sub-01)'
    )
    
    parser.add_argument(
        '--session-id',
        required=False,
        help='Session ID (optional, e.g., ses-01)'
    )
    
    args = parser.parse_args()
    
    # Print configuration
    print("=" * 60)
    print("OPENNEURO DATASET DOWNLOAD")
    print("=" * 60)
    print(f"Dataset ID: {args.dataset_id}")
    print(f"Subject ID: {args.subject_id}")
    print(f"Session ID: {args.session_id or 'Not specified'}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    try:
        # Download dataset
        dataset_path = download_openneuro_dataset(
            args.dataset_id,
            args.subject_id,
            args.session_id
        )
        
        # Find DWI files
        dwi_files = find_dwi_files(dataset_path, args.subject_id, args.session_id)
        
        if not dwi_files.get('dwi'):
            print("❌ No DWI files found in the dataset")
            sys.exit(1)
        
        # Create file paths info for GitHub Actions
        file_info = {
            'dataset_id': args.dataset_id,
            'subject_id': args.subject_id,
            'session_id': args.session_id,
            'dataset_path': dataset_path,
            'dwi_files': dwi_files,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save file information
        with open("dataset_info.json", 'w') as f:
            json.dump(file_info, f, indent=2)
        
        # Set GitHub Actions output variables
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"dwi_file={dwi_files.get('dwi', '')}\n")
                f.write(f"bval_file={dwi_files.get('bval', '')}\n")
                f.write(f"bvec_file={dwi_files.get('bvec', '')}\n")
                f.write(f"dataset_path={dataset_path}\n")
        
        print("\n" + "=" * 60)
        print("🎉 DOWNLOAD COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Dataset downloaded to: {dataset_path}")
        print(f"File information saved to: dataset_info.json")
        
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()