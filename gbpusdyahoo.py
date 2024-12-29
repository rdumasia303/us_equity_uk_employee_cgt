import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_gbpusd_data(start_date: str, end_date: str, output_file: str) -> None:
    """
    Download GBP/USD forex data from Yahoo Finance, calculate daily average from High/Low,
    and save to CSV. Ensures dates are in YYYY-MM-DD format.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        output_file: Path to save the CSV file
    """
    try:
        # Validate date formats
        try:
            pd.to_datetime(start_date).strftime('%Y-%m-%d')
            pd.to_datetime(end_date).strftime('%Y-%m-%d')
        except ValueError as e:
            raise ValueError(f"Dates must be in YYYY-MM-DD format: {str(e)}")

        logger.info(f"Downloading GBP/USD data from {start_date} to {end_date}")
        
        # Add one day to end_date to ensure we include the end date
        end = pd.to_datetime(end_date) + timedelta(days=1)
        
        # Download forex data - Yahoo uses "GBPUSD=X" for GBP/USD
        forex = yf.Ticker("GBPUSD=X")
        hist = forex.history(start=start_date, end=end)
        
        if hist.empty:
            raise ValueError(f"No data returned for GBP/USD between {start_date} and {end_date}")
        
        # Calculate daily average from High and Low prices
        hist['Average'] = (hist['High'] + hist['Low']) / 2
        
        # Keep only the Date and Average price
        hist = hist[['Average']].round(6)
        
        # Reset index to make Date a column and ensure YYYY-MM-DD format
        hist.reset_index(inplace=True)
        hist['Date'] = pd.to_datetime(hist['Date']).dt.strftime('%Y-%m-%d')
        
        # Remove any potential duplicates
        hist = hist.drop_duplicates(subset=['Date'], keep='first')
        
        # Save to CSV
        hist.to_csv(output_file, index=False)
        logger.info(f"Data saved to {output_file}")
        
        # Show sample and date range
        logger.info("\nFirst few rows of downloaded data:")
        logger.info(hist.head().to_string())
        logger.info(f"\nDate range: {hist['Date'].min()} to {hist['Date'].max()}")
        logger.info(f"Total trading days: {len(hist)}")
        
    except Exception as e:
        logger.error(f"Error downloading forex data: {str(e)}")
        raise

if __name__ == "__main__":
    # Example usage - getting roughly 8 years of historical data
    start_date = (datetime.now() - timedelta(days=8*365)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    output_file = "gbpusd_rates.csv"
    
    download_gbpusd_data(start_date, end_date, output_file)
