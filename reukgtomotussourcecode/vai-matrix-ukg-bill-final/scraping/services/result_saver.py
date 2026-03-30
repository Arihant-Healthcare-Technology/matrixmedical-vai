"""Result saving service."""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class ResultSaver:
    """Service for saving scraping results."""

    def __init__(self, output_dir: Path):
        """Initialize result saver.

        Args:
            output_dir: Directory to save results
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

    def save_json(
        self,
        data: List[Dict[str, Any]],
        filename: str = 'scraping-results.json'
    ) -> Path:
        """Save results to a JSON file.

        Args:
            data: Data to save
            filename: Output filename

        Returns:
            Path to saved file
        """
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f'[INFO] Results saved to: {filepath}')
        return filepath

    def save_csv(
        self,
        data: List[Dict[str, Any]],
        filename: str = 'scraping-results.csv'
    ) -> Path:
        """Save results to a CSV file.

        Args:
            data: Data to save (list of dicts)
            filename: Output filename

        Returns:
            Path to saved file
        """
        if not data:
            print('[WARN] No data to save to CSV')
            return self.output_dir / filename

        filepath = self.output_dir / filename

        # Get columns from first element
        fieldnames = list(data[0].keys())

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        print(f'[INFO] CSV saved to: {filepath}')
        return filepath

    def save_with_timestamp(
        self,
        data: List[Dict[str, Any]],
        prefix: str = 'scraping-results'
    ) -> tuple:
        """Save results with timestamp suffix.

        Args:
            data: Data to save
            prefix: Filename prefix

        Returns:
            Tuple of (json_path, csv_path)
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        json_path = self.save_json(data, f'{prefix}-{timestamp}.json')
        csv_path = self.save_csv(data, f'{prefix}-{timestamp}.csv')

        return json_path, csv_path
