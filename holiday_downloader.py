import requests
import json
import time
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_us_holidays(start_year: int, end_year: int, output_file: str) -> None:
    """
    Download US holiday data from nager.at API for a range of years.
    Ensures dates are in YYYY-MM-DD format.
    
    Args:
        start_year: First year to download
        end_year: Last year to download (inclusive)
        output_file: Path to save the JSON file
    """
    base_url = "https://date.nager.at/api/v3/PublicHolidays/{year}/US"
    all_holidays = []
    
    try:
        logger.info(f"Downloading US holidays for years {start_year}-{end_year}")
        
        for year in range(start_year, end_year + 1):
            url = base_url.format(year=year)
            logger.info(f"Fetching data for {year}...")
            
            response = requests.get(url)
            response.raise_for_status()
            
            year_holidays = response.json()
            
            # Validate and standardize dates
            for holiday in year_holidays:
                try:
                    # Ensure date is in YYYY-MM-DD format
                    holiday['date'] = pd.to_datetime(holiday['date']).strftime('%Y-%m-%d')
                except ValueError as e:
                    logger.warning(f"Invalid date format for holiday: {holiday}. Error: {e}")
                    continue
                
            all_holidays.extend(year_holidays)
            
            # Be nice to the API
            if year != end_year:
                time.sleep(0.5)
        
        # Sort holidays by date
        all_holidays.sort(key=lambda x: x['date'])
        
        # Save to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w') as f:
            json.dump(all_holidays, f, indent=2)
            
        logger.info(f"Successfully saved {len(all_holidays)} holidays to {output_file}")
        
        # Show sample of the data and date range
        logger.info("\nSample of downloaded holidays:")
        for holiday in all_holidays[:3]:
            logger.info(f"{holiday['date']}: {holiday['name']} ({holiday['types']})")
            
        if all_holidays:
            logger.info(f"\nDate range: {all_holidays[0]['date']} to {all_holidays[-1]['date']}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading holiday data: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing holiday data: {str(e)}")
        raise

if __name__ == "__main__":
    # Calculate year range to include some historical data and future dates
    current_year = datetime.now().year
    start_year = 2017  # Adjust based on your needs
    end_year = current_year + 1  # Include next year's holidays
    
    output_file = "us_holidays.json"
    
    download_us_holidays(start_year, end_year, output_file)